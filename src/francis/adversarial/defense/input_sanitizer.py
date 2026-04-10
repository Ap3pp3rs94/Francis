from __future__ import annotations

import argparse
import json
import logging
import re
import string
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = [
    "RiskSignal",
    "RiskAssessment",
    "SanitizationResult",
    "SanitizerPolicy",
    "InputSanitizer",
    "main",
]


_RE_ANSI = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_RE_CONTROL = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_RE_ZW = re.compile(r"[\u200B-\u200F\u2060-\u206F\uFEFF]")
_RE_NEWLINES = re.compile(r"\r\n|\r")
_RE_WS = re.compile(r"[ \t\f\v]+")


_INJECTION_SIGNALS: list[tuple[str, re.Pattern, int]] = [
    ("pi_ignore_rules", re.compile(r"\bignore\b.*\b(instruction|policy|rules)\b", re.I | re.S), 4),
    ("pi_system_prompt", re.compile(r"\b(system prompt|developer message|hidden instructions)\b", re.I), 4),
    (
        "pi_reveal_secrets",
        re.compile(r"\b(reveal|show|print|expose)\b.*\b(secret|key|token|password)\b", re.I | re.S),
        4,
    ),
    (
        "pi_role_override",
        re.compile(r"\b(act as|roleplay as|pretend to be)\b.*\b(system|developer|admin)\b", re.I | re.S),
        3,
    ),
    ("pi_jailbreak", re.compile(r"\b(jailbreak|dan mode|do anything now)\b", re.I), 5),
    (
        "pi_delimiters",
        re.compile(r"```(?:system|developer)\b|<\s*/?\s*(system|developer)\s*>|\bBEGIN\s+SYSTEM\b", re.I),
        3,
    ),
    (
        "pi_tool_override",
        re.compile(r"\bcall\s+the\s+tool\b|\bfunction_call\b|\bexecute\b.*\bcommand\b", re.I | re.S),
        2,
    ),
    ("pi_data_exfil", re.compile(r"\b(upload|send|exfiltrate|leak)\b.*\b(data|logs|files)\b", re.I | re.S), 4),
]

_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----", re.I)),
    ("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("aws_secret_key_like", re.compile(r"\b[0-9A-Za-z/+]{40}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")),
    ("generic_api_key_kv", re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s\"']{6,})")),
    ("openai_key_like", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("github_pat", re.compile(r"\bghp_[A-Za-z0-9]{30,}\b")),
]


@dataclass(frozen=True)
class RiskSignal:
    code: str
    weight: int


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    signals: tuple[RiskSignal, ...] = ()

    def summary(self) -> str:
        if not self.signals:
            return "score=0"
        top = sorted(self.signals, key=lambda s: s.weight, reverse=True)[:5]
        codes = ", ".join([f"{s.code}({s.weight})" for s in top])
        return f"score={self.score} [{codes}]"


@dataclass(frozen=True)
class SanitizationResult:
    original_len: int
    cleaned: str
    truncated: bool
    removed_control_chars: bool
    removed_ansi_escapes: bool
    removed_zero_width: bool
    redacted_secrets: bool
    risk: RiskAssessment
    meta: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SanitizerPolicy:
    max_chars: int = 12_000
    normalize_newlines: bool = True
    collapse_whitespace: bool = False
    strip_control_chars: bool = True
    strip_ansi_escapes: bool = True
    strip_zero_width: bool = True
    enable_prompt_injection_detection: bool = True
    enable_secret_detection: bool = True
    prompt_wrapper_prefix: str = "USER_INPUT_BEGIN"
    prompt_wrapper_suffix: str = "USER_INPUT_END"


def _looks_like_binary(text: str) -> bool:
    if "\x00" in text:
        return True
    non_printable = sum(1 for c in text if c not in string.printable and c not in "\n\r\t")
    return (non_printable / max(1, len(text))) > 0.18 if text else False


class InputSanitizer:
    _active: bool = False

    @classmethod
    def initialize(cls) -> None:
        cls._active = True

    @classmethod
    def is_active(cls) -> bool:
        return cls._active

    def __init__(self, policy: SanitizerPolicy | None = None) -> None:
        self.policy = policy or SanitizerPolicy()

    def sanitize_user_text(self, text: str, *, redact_secrets: bool = False) -> SanitizationResult:
        cleaned = text or ""
        original_len = len(cleaned)

        removed_ansi = False
        removed_ctl = False
        removed_zw = False
        truncated = False
        did_redact = False
        meta: dict[str, str] = {}

        if self.policy.normalize_newlines:
            cleaned = _RE_NEWLINES.sub("\n", cleaned)

        if self.policy.strip_ansi_escapes:
            cleaned, n = _RE_ANSI.subn("", cleaned)
            removed_ansi = n > 0

        if self.policy.strip_zero_width:
            cleaned, n = _RE_ZW.subn("", cleaned)
            removed_zw = n > 0

        if self.policy.strip_control_chars:
            cleaned, n = _RE_CONTROL.subn("", cleaned)
            removed_ctl = n > 0

        if self.policy.collapse_whitespace:
            cleaned = _RE_WS.sub(" ", cleaned)
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

        if self.policy.max_chars > 0 and len(cleaned) > self.policy.max_chars:
            cleaned = cleaned[: self.policy.max_chars]
            truncated = True

        if _looks_like_binary(cleaned):
            meta["binary_like"] = "true"

        risk = RiskAssessment(score=0, signals=())
        if self.policy.enable_prompt_injection_detection:
            risk = self._assess_prompt_injection(cleaned)

        if self.policy.enable_secret_detection:
            found = self.find_secrets(cleaned)
            if found:
                meta["secrets_found"] = ",".join(sorted(set(found)))
                if redact_secrets:
                    cleaned = self.redact_secrets(cleaned)
                    did_redact = True

        return SanitizationResult(
            original_len=original_len,
            cleaned=cleaned,
            truncated=truncated,
            removed_control_chars=removed_ctl,
            removed_ansi_escapes=removed_ansi,
            removed_zero_width=removed_zw,
            redacted_secrets=did_redact,
            risk=risk,
            meta=meta,
        )

    def wrap_for_prompt(self, cleaned_text: str) -> str:
        pfx = self.policy.prompt_wrapper_prefix
        sfx = self.policy.prompt_wrapper_suffix
        safe = cleaned_text.replace(pfx, f"{pfx}_ESC").replace(sfx, f"{sfx}_ESC")
        return f"[{pfx}]\n{safe}\n[{sfx}]"

    def sanitize_filename(self, name: str, *, max_len: int = 120) -> str:
        if not name:
            return "unnamed"
        n = name.replace("\\", "_").replace("/", "_")
        n = re.sub(r'[<>:"|?*\x00-\x1F]', "_", n).strip()
        n = re.sub(r"\s+", " ", n).rstrip(" .")
        if not n:
            n = "unnamed"
        if max_len > 0 and len(n) > max_len:
            n = n[:max_len].rstrip(" .")
        return n

    def find_secrets(self, text: str) -> list[str]:
        labels: list[str] = []
        if not text:
            return labels

        aws_context = bool(re.search(r"(?i)\baws\b|\bsecret\b|\baccess\b|\bkey\b", text))
        for label, rx in _SECRET_PATTERNS:
            if label == "aws_secret_key_like" and not aws_context:
                continue
            if rx.search(text):
                labels.append(label)
        return labels

    def redact_secrets(self, text: str) -> str:
        if not text:
            return text

        def _kv_repl(match: re.Match) -> str:
            return f"{match.group(1)}=[REDACTED:kv]"

        out = re.sub(
            r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s\"']{6,})",
            _kv_repl,
            text,
        )
        out = re.sub(
            r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----", "[REDACTED:private_key_block]", out, flags=re.I
        )
        out = re.sub(r"\bsk-[A-Za-z0-9]{20,}\b", "[REDACTED:openai_key_like]", out)
        out = re.sub(r"\bghp_[A-Za-z0-9]{30,}\b", "[REDACTED:github_pat]", out)
        out = re.sub(r"\bAKIA[0-9A-Z]{16}\b", "[REDACTED:aws_access_key_id]", out)
        out = re.sub(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b", "[REDACTED:jwt]", out)
        return out

    def safe_json_load(self, text: str, *, max_chars: int = 200_000) -> object:
        if text is None:
            raise ValueError("json text is None")
        if max_chars > 0 and len(text) > max_chars:
            raise ValueError(f"JSON input too large (>{max_chars} chars)")
        return json.loads(text)

    def _assess_prompt_injection(self, text: str) -> RiskAssessment:
        if not text:
            return RiskAssessment(score=0, signals=())

        signals: list[RiskSignal] = []
        for code, rx, weight in _INJECTION_SIGNALS:
            if rx.search(text):
                signals.append(RiskSignal(code=code, weight=weight))

        density_terms = [
            "instruction",
            "policy",
            "rules",
            "system",
            "developer",
            "override",
            "bypass",
            "ignore",
            "confidential",
            "secret",
            "token",
            "password",
        ]
        term_hits = sum(1 for t in density_terms if re.search(rf"(?i)\b{re.escape(t)}\b", text))
        if term_hits >= 5:
            signals.append(RiskSignal(code="pi_high_instruction_density", weight=3))

        if re.search(r"[\u202A-\u202E]", text):
            signals.append(RiskSignal(code="pi_bidi_obfuscation", weight=4))

        if len(text) > 1500 and "\n" not in text:
            signals.append(RiskSignal(code="pi_long_single_line", weight=2))

        score = min(20, sum(s.weight for s in signals))
        return RiskAssessment(score=score, signals=tuple(signals))


def _format_result(result: SanitizationResult) -> str:
    parts = [
        f"original_len: {result.original_len}",
        f"cleaned_len: {len(result.cleaned)}",
        f"truncated: {result.truncated}",
        f"removed_ansi_escapes: {result.removed_ansi_escapes}",
        f"removed_zero_width: {result.removed_zero_width}",
        f"removed_control_chars: {result.removed_control_chars}",
        f"redacted_secrets: {result.redacted_secrets}",
        f"risk: {result.risk.summary()}",
    ]
    if result.meta:
        parts.append(f"meta: {result.meta}")
    parts.append("")
    parts.append(result.cleaned)
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="input_sanitizer")
    parser.add_argument("--text", default="")
    parser.add_argument("--redact", action="store_true")
    parser.add_argument("--collapse", action="store_true")
    parser.add_argument("--max", type=int, default=12_000)
    parser.add_argument("--wrap", action="store_true")
    args = parser.parse_args(argv)

    policy = SanitizerPolicy(max_chars=args.max, collapse_whitespace=bool(args.collapse))
    sanitizer = InputSanitizer(policy)
    result = sanitizer.sanitize_user_text(args.text, redact_secrets=bool(args.redact))

    if args.wrap:
        wrapped = sanitizer.wrap_for_prompt(result.cleaned)
        result = SanitizationResult(
            original_len=result.original_len,
            cleaned=wrapped,
            truncated=result.truncated,
            removed_control_chars=result.removed_control_chars,
            removed_ansi_escapes=result.removed_ansi_escapes,
            removed_zero_width=result.removed_zero_width,
            redacted_secrets=result.redacted_secrets,
            risk=result.risk,
            meta=result.meta,
        )

    print(_format_result(result))
    return 1 if result.risk.score >= 7 else 0


if __name__ == "__main__":
    raise SystemExit(main())
