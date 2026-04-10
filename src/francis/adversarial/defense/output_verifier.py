from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "OutputSignal",
    "OutputRisk",
    "OutputVerificationResult",
    "JsonContract",
    "OutputVerifierPolicy",
    "OutputVerifier",
    "main",
]


InputSanitizer: type[Any] | None
SanitizerPolicy: type[Any] | None

try:  # best-effort reuse
    from .input_sanitizer import InputSanitizer, SanitizerPolicy
except Exception:  # pragma: no cover
    InputSanitizer = None
    SanitizerPolicy = None


@dataclass(frozen=True)
class OutputSignal:
    code: str
    weight: int
    message: str = ""


@dataclass(frozen=True)
class OutputRisk:
    score: int
    signals: tuple[OutputSignal, ...] = ()

    def summary(self) -> str:
        if not self.signals:
            return "score=0"
        top = sorted(self.signals, key=lambda s: s.weight, reverse=True)[:6]
        codes = ", ".join([f"{s.code}({s.weight})" for s in top])
        return f"score={self.score} [{codes}]"


@dataclass(frozen=True)
class OutputVerificationResult:
    original_len: int
    cleaned: str
    truncated: bool
    redacted_secrets: bool
    risk: OutputRisk
    meta: dict[str, str] = field(default_factory=dict)

    def is_high_risk(self, threshold: int = 7) -> bool:
        return self.risk.score >= threshold


@dataclass(frozen=True)
class JsonContract:
    required_keys: set[str] = field(default_factory=set)
    allowed_keys: set[str] | None = None
    require_object: bool = True


@dataclass(frozen=True)
class OutputVerifierPolicy:
    max_chars: int = 20_000
    enable_secret_leak_detection: bool = True
    redact_secrets_default: bool = False
    enable_command_risk_detection: bool = True
    enable_sensitive_path_detection: bool = True
    high_risk_threshold: int = 7


_RE_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----", re.I)
_RE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")
_RE_OPENAI = re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")
_RE_GH_PAT = re.compile(r"\bghp_[A-Za-z0-9]{30,}\b")
_RE_AWS_AKID = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_RE_KV_SECRET = re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s\"']{6,})")

_SENSITIVE_PATH_PATTERNS: list[tuple[str, re.Pattern, int, str]] = [
    ("sensitive_linux_shadow", re.compile(r"(?i)\b/etc/shadow\b"), 5, "/etc/shadow"),
    ("sensitive_linux_passwd", re.compile(r"(?i)\b/etc/passwd\b"), 2, "/etc/passwd"),
    ("sensitive_ssh_keys", re.compile(r"(?i)\b(\.ssh/(id_rsa|id_ed25519)|authorized_keys)\b"), 4, "ssh_keys"),
    ("sensitive_windows_sam", re.compile(r"(?i)\bC:\\Windows\\System32\\config\\SAM\b"), 5, "windows_sam"),
    ("sensitive_ntds", re.compile(r"(?i)\bNTDS\.dit\b"), 5, "ntds"),
    ("sensitive_kubeconfig", re.compile(r"(?i)\b(\.kube/config|kubeconfig)\b"), 3, "kubeconfig"),
]

_COMMAND_RISK_PATTERNS: list[tuple[str, re.Pattern, int, str]] = [
    ("cmd_rm_rf_root", re.compile(r"(?i)\brm\s+-rf\s+/(?:\s|$)"), 7, "rm -rf /"),
    ("cmd_rm_rf_no_preserve", re.compile(r"(?i)\brm\s+-rf\b.*\b--no-preserve-root\b"), 7, "rm -rf --no-preserve-root"),
    ("cmd_mkfs", re.compile(r"(?i)\bmkfs(\.\w+)?\b|\bnewfs\b"), 6, "mkfs/newfs"),
    ("cmd_format_disk", re.compile(r"(?i)\bformat\s+[a-z]:\b|\bdiskpart\b|\bclean all\b"), 7, "format/diskpart"),
    ("cmd_windows_del_tree", re.compile(r"(?i)\b(rmdir|rd)\s+/s\s+/q\b|\bdel\s+/s\s+/q\b"), 6, "delete tree"),
    (
        "cmd_powershell_remove_item_force",
        re.compile(r"(?i)\bRemove-Item\b.*\b-Recurse\b.*\b-Force\b"),
        6,
        "Remove-Item -Recurse -Force",
    ),
    ("cmd_reg_delete", re.compile(r"(?i)\breg\s+delete\b"), 5, "reg delete"),
    ("cmd_shutdown_reboot", re.compile(r"(?i)\bshutdown\b.*\b(/s|/r|/f)\b"), 3, "shutdown/reboot"),
    ("cmd_fork_bomb", re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"), 8, "fork bomb"),
]

_DOWNLOAD_EXEC_PATTERNS: list[tuple[str, re.Pattern, int, str]] = [
    ("dex_curl_pipe_sh", re.compile(r"(?i)\bcurl\b[^|\n]*\|\s*(sh|bash)\b"), 7, "curl | sh"),
    ("dex_wget_pipe_sh", re.compile(r"(?i)\bwget\b[^|\n]*\|\s*(sh|bash)\b"), 7, "wget | sh"),
    (
        "dex_iwr_iex",
        re.compile(r"(?i)\b(iwr|Invoke-WebRequest)\b[^|\n]*\|\s*(iex|Invoke-Expression)\b"),
        7,
        "iwr | iex",
    ),
    (
        "dex_powershell_encoded",
        re.compile(r"(?i)\bpowershell(\.exe)?\b.*\s-(enc|encodedcommand)\s+[A-Za-z0-9+/=]{20,}"),
        6,
        "powershell -encodedcommand",
    ),
    (
        "dex_certutil_download",
        re.compile(r"(?i)\bcertutil\b.*\b-urlcache\b.*\b-split\b.*\b-f\b"),
        6,
        "certutil download",
    ),
    ("dex_bitsadmin", re.compile(r"(?i)\bbitsadmin\b.*\b/transfer\b"), 5, "bitsadmin"),
]

_CRED_SOLICIT_PATTERNS: list[tuple[str, re.Pattern, int, str]] = [
    (
        "phish_ask_password",
        re.compile(r"(?i)\b(enter|provide|send|paste)\b.*\b(password|api key|token|secret|private key)\b"),
        6,
        "credential request",
    ),
    (
        "phish_ask_mfa",
        re.compile(r"(?i)\b(enter|provide|send|paste)\b.*\b(otp|mfa|2fa|verification code)\b"),
        5,
        "mfa request",
    ),
]


class OutputVerifier:
    _active: bool = False

    @classmethod
    def initialize(cls) -> None:
        cls._active = True

    @classmethod
    def is_active(cls) -> bool:
        return cls._active

    def __init__(self, policy: OutputVerifierPolicy | None = None) -> None:
        self.policy = policy or OutputVerifierPolicy()
        self._sanitizer = None
        if InputSanitizer and SanitizerPolicy:
            self._sanitizer = InputSanitizer(
                SanitizerPolicy(
                    max_chars=self.policy.max_chars,
                    normalize_newlines=True,
                    collapse_whitespace=False,
                    strip_control_chars=True,
                    strip_ansi_escapes=True,
                    strip_zero_width=True,
                    enable_prompt_injection_detection=True,
                    enable_secret_detection=True,
                )
            )

    def verify_text(self, text: str, *, redact_secrets: bool | None = None) -> OutputVerificationResult:
        redact = self.policy.redact_secrets_default if redact_secrets is None else redact_secrets
        cleaned = text or ""
        truncated = False
        redacted = False
        meta: dict[str, str] = {}

        if self._sanitizer:
            san = self._sanitizer.sanitize_user_text(cleaned, redact_secrets=bool(redact))
            cleaned = san.cleaned
            truncated = bool(getattr(san, "truncated", False))
            redacted = bool(getattr(san, "redacted_secrets", False))
            meta = dict(getattr(san, "meta", {}) or {})
        elif self.policy.max_chars > 0 and len(cleaned) > self.policy.max_chars:
            cleaned = cleaned[: self.policy.max_chars]
            truncated = True

        signals: list[OutputSignal] = []

        if self.policy.enable_secret_leak_detection:
            secret_hits = self._detect_secrets(cleaned)
            if secret_hits:
                meta["secrets_detected"] = ",".join(sorted(set(secret_hits)))
                signals.append(OutputSignal(code="secret_leak_detected", weight=7))

        if self.policy.enable_command_risk_detection:
            signals.extend(self._detect_patterns(cleaned, _COMMAND_RISK_PATTERNS))
            signals.extend(self._detect_patterns(cleaned, _DOWNLOAD_EXEC_PATTERNS))
            signals.extend(self._detect_patterns(cleaned, _CRED_SOLICIT_PATTERNS))

        if self.policy.enable_sensitive_path_detection:
            signals.extend(self._detect_patterns(cleaned, _SENSITIVE_PATH_PATTERNS))

        score = min(30, sum(s.weight for s in signals))
        return OutputVerificationResult(
            original_len=len(text or ""),
            cleaned=cleaned,
            truncated=truncated,
            redacted_secrets=redacted,
            risk=OutputRisk(score=score, signals=tuple(signals)),
            meta=meta,
        )

    def verify_json(
        self,
        text: str,
        *,
        contract: JsonContract | None = None,
        redact_secrets: bool | None = None,
    ) -> tuple[OutputVerificationResult, Any | None]:
        res = self.verify_text(text, redact_secrets=redact_secrets)
        signals = list(res.risk.signals)
        meta = dict(res.meta)

        parsed: Any | None = None
        try:
            parsed = json.loads(res.cleaned)
        except Exception as exc:
            signals.append(OutputSignal(code="invalid_json", weight=7, message=str(exc)))
            score = min(30, sum(s.weight for s in signals))
            return (
                OutputVerificationResult(
                    original_len=res.original_len,
                    cleaned=res.cleaned,
                    truncated=res.truncated,
                    redacted_secrets=res.redacted_secrets,
                    risk=OutputRisk(score=score, signals=tuple(signals)),
                    meta=meta,
                ),
                None,
            )

        if contract:
            c_signals, c_meta = self._validate_json_contract(parsed, contract)
            signals.extend(c_signals)
            if c_meta:
                meta.update(c_meta)

        score = min(30, sum(s.weight for s in signals))
        return (
            OutputVerificationResult(
                original_len=res.original_len,
                cleaned=res.cleaned,
                truncated=res.truncated,
                redacted_secrets=res.redacted_secrets,
                risk=OutputRisk(score=score, signals=tuple(signals)),
                meta=meta,
            ),
            parsed,
        )

    def _detect_secrets(self, text: str) -> list[str]:
        hits: list[str] = []
        if not text:
            return hits
        if _RE_PRIVATE_KEY.search(text):
            hits.append("private_key_block")
        if _RE_JWT.search(text):
            hits.append("jwt")
        if _RE_OPENAI.search(text):
            hits.append("openai_key_like")
        if _RE_GH_PAT.search(text):
            hits.append("github_pat")
        if _RE_AWS_AKID.search(text):
            hits.append("aws_access_key_id")
        if _RE_KV_SECRET.search(text):
            hits.append("kv_secret_pair")
        return hits

    def _detect_patterns(self, text: str, patterns: list[tuple[str, re.Pattern, int, str]]) -> list[OutputSignal]:
        out: list[OutputSignal] = []
        if not text:
            return out
        for code, rx, weight, msg in patterns:
            try:
                if rx.search(text):
                    out.append(OutputSignal(code=code, weight=int(weight), message=msg))
            except Exception:
                continue
        return out

    def _validate_json_contract(self, parsed: Any, contract: JsonContract) -> tuple[list[OutputSignal], dict[str, str]]:
        signals: list[OutputSignal] = []
        meta: dict[str, str] = {}

        if contract.require_object and not isinstance(parsed, dict):
            signals.append(
                OutputSignal(
                    code="json_contract_not_object",
                    weight=6,
                    message=f"Expected dict, got {type(parsed).__name__}",
                )
            )
            return signals, meta

        if isinstance(parsed, dict):
            keys = set(parsed.keys())
            meta["json_keys"] = ",".join(sorted(keys))
            missing = set(contract.required_keys) - keys
            if missing:
                signals.append(
                    OutputSignal(
                        code="json_contract_missing_keys",
                        weight=6,
                        message="Missing keys: " + ", ".join(sorted(missing)),
                    )
                )
            if contract.allowed_keys is not None:
                extra = keys - set(contract.allowed_keys)
                if extra:
                    signals.append(
                        OutputSignal(
                            code="json_contract_extra_keys",
                            weight=3,
                            message="Extra keys: " + ", ".join(sorted(extra)),
                        )
                    )

        return signals, meta


def _format(res: OutputVerificationResult) -> str:
    lines = [
        f"original_len: {res.original_len}",
        f"cleaned_len: {len(res.cleaned)}",
        f"truncated: {res.truncated}",
        f"redacted_secrets: {res.redacted_secrets}",
        f"risk: {res.risk.summary()}",
    ]
    if res.meta:
        lines.append(f"meta: {res.meta}")
    lines.append("")
    lines.append(res.cleaned)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="output_verifier")
    parser.add_argument("--text", default="")
    parser.add_argument("--redact", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require", default="")
    parser.add_argument("--allow", default="")
    args = parser.parse_args(argv)

    verifier = OutputVerifier(OutputVerifierPolicy())

    if args.json:
        req = {k.strip() for k in args.require.split(",") if k.strip()}
        allow = {k.strip() for k in args.allow.split(",") if k.strip()} if args.allow.strip() else None
        contract = JsonContract(required_keys=req, allowed_keys=allow, require_object=True)
        res, parsed = verifier.verify_json(args.text, contract=contract, redact_secrets=args.redact)
        print(_format(res))
        if parsed is not None:
            print("\nPARSED_JSON_OK")
        return 1 if res.is_high_risk(verifier.policy.high_risk_threshold) else 0

    res = verifier.verify_text(args.text, redact_secrets=args.redact)
    print(_format(res))
    return 1 if res.is_high_risk(verifier.policy.high_risk_threshold) else 0


if __name__ == "__main__":
    raise SystemExit(main())
