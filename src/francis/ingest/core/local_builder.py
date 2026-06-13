"""Governed local Ollama builder adapter for Francis capability proposals.

This module is a bounded builder foundation. It compiles ingest evidence into a
Francis-native capability specification and can ask a localhost-only Ollama model
for a proposal artifact. It never applies patches, never promotes capabilities,
and never treats model output as authority.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from ..ingest.runtime_requirements import RuntimeRequirements, classify_runtime_requirements
from ..shared.models import CapabilityCandidate, RepoMap, SourceRecord
from .registry import ReceiptWriter, utc_now, write_ingest_record_artifact

DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5-coder:7b"
COPY_POLICY_DO_NOT_COPY = "do_not_copy_third_party_code"
BUILDER_OPERATION = "builder.local.ollama.run"
SPEC_OPERATION = "builder.capability_spec.compile"
MAX_PROMPT_CHARS = 16000
MAX_PROPOSAL_EXCERPT_CHARS = 12000

DEFAULT_FORBIDDEN_FILES: tuple[str, ...] = (
    "AGENTS.md",
    "ROADMAP.md",
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
    ".github/secrets/**",
    "docs/operations/COMPLETION_LEDGER.md",
    "src/francis/governance/**",
    "apps/chat_ui/src/App.tsx",
    "apps/chat_ui/src/orb/**",
    "apps/chat_ui/src/hud/**",
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [text for item in value if (text := _safe_str(item).strip())]


def _stable_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _text_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _record_id(prefix: str) -> str:
    stamp = utc_now().replace(":", "").replace("-", "").replace("+", "")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def _excerpt(text: str, limit: int = MAX_PROPOSAL_EXCERPT_CHARS) -> tuple[str, bool]:
    clean = _safe_str(text)
    if len(clean) <= limit:
        return clean, False
    half = max(1, limit // 2)
    return f"{clean[:half]}\n...[{len(clean) - limit} chars truncated]...\n{clean[-half:]}", True


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").strip().lstrip("./")


def _static_prefix(pattern: str) -> str:
    clean = _normalize_path(pattern).lower()
    wildcard_positions = [pos for pos in (clean.find("*"), clean.find("?"), clean.find("[")) if pos >= 0]
    if not wildcard_positions:
        return clean
    return clean[: min(wildcard_positions)].rstrip("/")


def _pattern_overlaps_forbidden(allowed: str, forbidden: str) -> bool:
    allowed_norm = _normalize_path(allowed).lower()
    forbidden_norm = _normalize_path(forbidden).lower()
    if not allowed_norm or not forbidden_norm:
        return False
    if fnmatch.fnmatchcase(allowed_norm, forbidden_norm):
        return True
    if fnmatch.fnmatchcase(forbidden_norm, allowed_norm):
        return True
    allowed_prefix = _static_prefix(allowed_norm)
    forbidden_prefix = _static_prefix(forbidden_norm)
    return bool(
        allowed_prefix
        and forbidden_prefix
        and (allowed_prefix.startswith(forbidden_prefix) or forbidden_prefix.startswith(allowed_prefix))
    )


def forbidden_scope_violations(allowed_files: list[str], forbidden_files: list[str]) -> list[str]:
    violations: list[str] = []
    for allowed in allowed_files:
        for forbidden in forbidden_files:
            if _pattern_overlaps_forbidden(allowed, forbidden):
                violations.append(f"allowed_file_overlaps_forbidden:{allowed}")
                break
    return sorted(set(violations))


@dataclass(frozen=True)
class CapabilityInterfaceSpec:
    allowed_inputs: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityRiskSpec:
    risk_level: str
    required_permissions: dict[str, bool] = field(default_factory=dict)
    forbidden_behaviors: list[str] = field(default_factory=list)
    environment_requirements: dict[str, Any] = field(default_factory=dict)
    default_lab_compatible: bool = True
    recommended_next_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityValidationSpec:
    validation_commands: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    promotion_requirements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityBuildTask:
    task_id: str
    allowed_files: list[str] = field(default_factory=list)
    forbidden_files: list[str] = field(default_factory=lambda: list(DEFAULT_FORBIDDEN_FILES))
    max_files_changed: int = 3
    max_iterations: int = 1
    stop_conditions: list[str] = field(default_factory=list)
    required_receipt_kind: str = "builder.local.ollama.run"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FrancisCapabilitySpec:
    id: str
    source_id: str
    candidate_id: str
    capability_name: str
    capability_summary: str
    francis_native_purpose: str
    user_facing_description: str
    capability_class: str
    interface: CapabilityInterfaceSpec
    risk: CapabilityRiskSpec
    validation: CapabilityValidationSpec
    build_task: CapabilityBuildTask
    source_evidence_references: list[str] = field(default_factory=list)
    license_attribution_note: str = ""
    copy_policy: str = COPY_POLICY_DO_NOT_COPY
    conceptual_rebuild_only: bool = True
    created_at: str = ""
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["interface"] = self.interface.to_dict()
        data["risk"] = self.risk.to_dict()
        data["validation"] = self.validation.to_dict()
        data["build_task"] = self.build_task.to_dict()
        return data

    @classmethod
    def from_dict(cls, value: Any) -> "FrancisCapabilitySpec | None":
        if not isinstance(value, dict):
            return None
        spec_id = _safe_str(value.get("id")).strip()
        source_id = _safe_str(value.get("source_id")).strip()
        candidate_id = _safe_str(value.get("candidate_id")).strip()
        if not spec_id or not source_id or not candidate_id:
            return None
        interface_value = value.get("interface")
        risk_value = value.get("risk")
        validation_value = value.get("validation")
        build_value = value.get("build_task")
        interface_raw: dict[str, Any] = interface_value if isinstance(interface_value, dict) else {}
        risk_raw: dict[str, Any] = risk_value if isinstance(risk_value, dict) else {}
        validation_raw: dict[str, Any] = validation_value if isinstance(validation_value, dict) else {}
        build_raw: dict[str, Any] = build_value if isinstance(build_value, dict) else {}
        return cls(
            id=spec_id,
            source_id=source_id,
            candidate_id=candidate_id,
            capability_name=_safe_str(value.get("capability_name")).strip(),
            capability_summary=_safe_str(value.get("capability_summary")).strip(),
            francis_native_purpose=_safe_str(value.get("francis_native_purpose")).strip(),
            user_facing_description=_safe_str(value.get("user_facing_description")).strip(),
            capability_class=_safe_str(value.get("capability_class")).strip() or "general",
            interface=CapabilityInterfaceSpec(
                allowed_inputs=_string_list(interface_raw.get("allowed_inputs")),
                expected_outputs=_string_list(interface_raw.get("expected_outputs")),
            ),
            risk=CapabilityRiskSpec(
                risk_level=_safe_str(risk_raw.get("risk_level")).strip() or "medium",
                required_permissions={
                    str(key): bool(item) for key, item in (risk_raw.get("required_permissions") or {}).items()
                },
                forbidden_behaviors=_string_list(risk_raw.get("forbidden_behaviors")),
                environment_requirements=risk_raw.get("environment_requirements") or {},
                default_lab_compatible=bool(risk_raw.get("default_lab_compatible", True)),
                recommended_next_action=_safe_str(risk_raw.get("recommended_next_action")).strip(),
            ),
            validation=CapabilityValidationSpec(
                validation_commands=_string_list(validation_raw.get("validation_commands")),
                acceptance_criteria=_string_list(validation_raw.get("acceptance_criteria")),
                promotion_requirements=_string_list(validation_raw.get("promotion_requirements")),
            ),
            build_task=CapabilityBuildTask(
                task_id=_safe_str(build_raw.get("task_id")).strip() or f"task_{spec_id}",
                allowed_files=_string_list(build_raw.get("allowed_files")),
                forbidden_files=_string_list(build_raw.get("forbidden_files")) or list(DEFAULT_FORBIDDEN_FILES),
                max_files_changed=int(build_raw.get("max_files_changed") or 3),
                max_iterations=int(build_raw.get("max_iterations") or 1),
                stop_conditions=_string_list(build_raw.get("stop_conditions")),
                required_receipt_kind=_safe_str(build_raw.get("required_receipt_kind")).strip()
                or "builder.local.ollama.run",
            ),
            source_evidence_references=_string_list(value.get("source_evidence_references")),
            license_attribution_note=_safe_str(value.get("license_attribution_note")).strip(),
            copy_policy=_safe_str(value.get("copy_policy")).strip() or COPY_POLICY_DO_NOT_COPY,
            conceptual_rebuild_only=bool(value.get("conceptual_rebuild_only", True)),
            created_at=_safe_str(value.get("created_at")).strip(),
            schema_version=int(value.get("schema_version") or 1),
        )


def _purpose_for_candidate(
    candidate: CapabilityCandidate, repo_map: RepoMap, req: RuntimeRequirements
) -> tuple[str, str, str]:
    name = candidate.name
    if not req.default_lab_compatible:
        return (
            "isolated desktop / GUI automation / sandbox environment",
            "study the capability concept and environment contract for a future specialized Lab profile without "
            "default execution.",
            "Classify a complex runtime capability and prepare a specialized profile design.",
        )
    if name == "inspect_project_structure":
        return (
            "source_inspection",
            "inspect a source tree, summarize structure, detect manifests, tests, risk signals, and environment "
            "requirements without executing source code.",
            "Inspect a source tree and report its structure, manifests, tests, risk signals, and environment needs.",
        )
    if name == "run_project_tests":
        return (
            "lab_validation",
            "validate a source candidate by running an approved command in a governed Lab profile, with receipts "
            "and no host mutation.",
            "Run an approved validation command inside Francis Lab and record evidence.",
        )
    summary = (
        candidate.description or "Translate an observed capability concept into a Francis-native bounded build task."
    )
    return ("general", summary, summary)


def compile_capability_spec_from_candidate(
    *,
    source: SourceRecord,
    candidate: CapabilityCandidate,
    repo_map: RepoMap,
    runtime_requirements: RuntimeRequirements | None = None,
    allowed_files: list[str] | None = None,
    forbidden_files: list[str] | None = None,
) -> FrancisCapabilitySpec:
    """Compile ingest evidence into a deterministic Francis-native capability spec."""

    req = runtime_requirements or classify_runtime_requirements(repo_map)
    capability_class, purpose, user_description = _purpose_for_candidate(candidate, repo_map, req)
    validation_commands = [cmd for cmd in candidate.suggested_validation if cmd]
    if not validation_commands:
        validation_commands = [
            _safe_str(item.get("command")).strip()
            for item in repo_map.suggested_validation_commands
            if isinstance(item, dict) and _safe_str(item.get("command")).strip()
        ]
    required_permissions = candidate.permissions_required.to_dict()
    default_forbidden = list(forbidden_files or DEFAULT_FORBIDDEN_FILES)
    default_allowed = list(
        allowed_files
        or [
            "src/francis/ingest/**",
            "tests/unit/**",
            "tests/test_api_ingest.py",
            "docs/CODE_BORN_CAPABILITY_INGESTION.md",
            "docs/INGEST_CORE_LAB_SHARED_CONTRACTS.md",
        ]
    )
    evidence: list[str] = []
    evidence.extend(f"manifest:{item}" for item in repo_map.manifest_files[:20])
    evidence.extend(f"test:{item}" for item in repo_map.test_files[:20])
    evidence.extend(f"risk:{item.id}:{item.severity}" for item in repo_map.risk_signals[:20])
    if repo_map.license_file:
        evidence.append(f"license:{repo_map.license_file}")
    if req.evidence:
        evidence.extend(f"runtime:{item}" for item in req.evidence)

    recommended_next_action = (
        "capability study / specialized Lab profile design"
        if not req.default_lab_compatible
        else "bounded Francis-native conceptual rebuild proposal"
    )
    forbidden_behaviors = [
        "copy_third_party_implementation_code_without_license_attribution_and_explicit_operator_approval",
        "modify_forbidden_files",
        "apply_patches_without_operator_approval",
        "promote_capability_without_lab_validation_receipt",
        "execute_networked_or_destructive_commands",
    ]
    if required_permissions.get("network"):
        forbidden_behaviors.append("default_lab_network_access")
    if required_permissions.get("destructive"):
        forbidden_behaviors.append("destructive_host_mutation")
    acceptance = [
        "proposal_is_francis_native_and_conceptual_rebuild_only",
        "proposal_does_not_copy_third_party_implementation_code",
        "proposal_respects_allowed_files_and_forbidden_files",
        "proposal_includes_validation_plan",
        "no_patch_is_applied_without_explicit_operator_approval",
    ]
    promotion_requirements = [
        "operator_review_required",
        "lab_validation_required",
        "receipt_required",
        "no_blocked_risk_flags",
        "no_forbidden_file_mutation",
    ]
    if not req.default_lab_compatible:
        acceptance.append("default_lab_execution_not_attempted")
        promotion_requirements.append("specialized_lab_profile_required_before_execution")

    spec_payload = {
        "source_id": source.id,
        "candidate_id": candidate.id,
        "candidate_name": candidate.name,
        "purpose": purpose,
        "copy_policy": COPY_POLICY_DO_NOT_COPY,
    }
    spec_id = "cap_spec_" + hashlib.sha256(json.dumps(spec_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return FrancisCapabilitySpec(
        id=spec_id,
        source_id=source.id,
        candidate_id=candidate.id,
        capability_name=candidate.name,
        capability_summary=candidate.description,
        francis_native_purpose=purpose,
        user_facing_description=user_description,
        capability_class=capability_class,
        interface=CapabilityInterfaceSpec(
            allowed_inputs=["source_id", "candidate_id", "repo_map", "governed_operator_task"],
            expected_outputs=[
                "Francis-native implementation plan or patch proposal artifact",
                "validation commands",
                "receipt-backed builder run record",
            ],
        ),
        risk=CapabilityRiskSpec(
            risk_level=candidate.risk_level,
            required_permissions=required_permissions,
            forbidden_behaviors=forbidden_behaviors,
            environment_requirements=req.to_dict(),
            default_lab_compatible=req.default_lab_compatible,
            recommended_next_action=recommended_next_action,
        ),
        validation=CapabilityValidationSpec(
            validation_commands=validation_commands,
            acceptance_criteria=acceptance,
            promotion_requirements=promotion_requirements,
        ),
        build_task=CapabilityBuildTask(
            task_id=f"build_{spec_id}",
            allowed_files=default_allowed,
            forbidden_files=default_forbidden,
            stop_conditions=[
                "attempt_to_edit_forbidden_path",
                "request_to_copy_third_party_code",
                "request_to_apply_patch_without_operator_approval",
                "network_or_secret_request",
            ],
        ),
        source_evidence_references=evidence,
        license_attribution_note=(
            f"License evidence file detected: {repo_map.license_file}."
            if repo_map.license_file
            else "No license evidence file detected by ingest; default to conceptual rebuild only."
        ),
        copy_policy=COPY_POLICY_DO_NOT_COPY,
        conceptual_rebuild_only=True,
        created_at=utc_now(),
    )


@dataclass(frozen=True)
class OllamaBuilderConfig:
    host: str = DEFAULT_OLLAMA_HOST
    model: str = DEFAULT_OLLAMA_MODEL
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "OllamaBuilderConfig":
        return cls(
            host=os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST).strip() or DEFAULT_OLLAMA_HOST,
            model=os.getenv("FRANCIS_LOCAL_BUILDER_MODEL", DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL,
        )


@dataclass(frozen=True)
class OllamaBuildRequest:
    task_id: str
    spec: FrancisCapabilitySpec
    model: str = DEFAULT_OLLAMA_MODEL
    allowed_files: list[str] = field(default_factory=list)
    forbidden_files: list[str] = field(default_factory=lambda: list(DEFAULT_FORBIDDEN_FILES))
    max_files_changed: int = 3
    max_iterations: int = 1
    validation_commands: list[str] = field(default_factory=list)
    risk_level: str = "medium"
    stop_conditions: list[str] = field(default_factory=list)
    required_receipt_kind: str = BUILDER_OPERATION

    @classmethod
    def from_spec(cls, spec: FrancisCapabilitySpec, *, model: str = "") -> "OllamaBuildRequest":
        return cls(
            task_id=spec.build_task.task_id,
            spec=spec,
            model=model or DEFAULT_OLLAMA_MODEL,
            allowed_files=list(spec.build_task.allowed_files),
            forbidden_files=list(spec.build_task.forbidden_files),
            max_files_changed=spec.build_task.max_files_changed,
            max_iterations=spec.build_task.max_iterations,
            validation_commands=list(spec.validation.validation_commands),
            risk_level=spec.risk.risk_level,
            stop_conditions=list(spec.build_task.stop_conditions),
            required_receipt_kind=spec.build_task.required_receipt_kind,
        )


@dataclass(frozen=True)
class BuilderPatchProposal:
    text_excerpt: str = ""
    text_digest: str = ""
    truncated: bool = False
    patch_proposed: bool = False
    plan_proposed: bool = False
    files_intended: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BuilderRunRecord:
    builder_run_id: str
    task_id: str
    spec_id: str
    source_id: str
    candidate_id: str
    candidate_name: str
    model: str
    started_at: str
    completed_at: str
    status: str
    prompt_digest: str
    response_digest: str
    allowed_files: list[str]
    forbidden_files: list[str]
    max_files_changed: int
    max_iterations: int
    validation_commands_requested: list[str]
    validation_commands_suggested: list[str]
    validation_commands_run: list[str]
    risk_level: str
    stop_conditions: list[str]
    required_receipt_kind: str
    ollama_host: str
    ollama_available: bool
    patch_proposed: bool
    patch_applied: bool
    validation_status: str
    refusal_reason: str = ""
    blocker_reason: str = ""
    proposal: BuilderPatchProposal = field(default_factory=BuilderPatchProposal)
    artifact_path: str = ""
    receipt_path: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["proposal"] = self.proposal.to_dict()
        return data


@dataclass(frozen=True)
class OllamaBuildResult:
    ok: bool
    status: str
    record: BuilderRunRecord
    artifact_path: str = ""
    receipt_path: str = ""
    proposed_patch_text: str = ""
    plan_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "builder_run": self.record.to_dict(),
            "artifact_path": self.artifact_path,
            "receipt_path": self.receipt_path,
            "proposed_patch_text": self.proposed_patch_text,
            "plan_text": self.plan_text,
        }


OllamaClient = Callable[[str, str, str, int], str]


def _host_is_localhost(host: str) -> bool:
    parsed = urllib.parse.urlparse(host)
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in {
        "127.0.0.1",
        "localhost",
        "::1",
    }


def _ollama_generate(host: str, model: str, prompt: str, timeout_seconds: int) -> str:
    if not _host_is_localhost(host):
        raise ValueError("ollama_host_must_be_localhost")
    url = host.rstrip("/") + "/api/generate"
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=max(1, int(timeout_seconds))) as response:  # noqa: S310
        raw = json.loads(response.read().decode("utf-8", errors="replace"))
    return _safe_str(raw.get("response")).strip()


def build_ollama_prompt(request: OllamaBuildRequest) -> str:
    """Build a bounded prompt. Exact forbidden paths are intentionally omitted."""

    spec = request.spec
    prompt_payload = {
        "role": "You are a local Francis builder model. You are not Francis and you have no authority.",
        "task_id": request.task_id,
        "capability_spec": {
            "id": spec.id,
            "capability_name": spec.capability_name,
            "francis_native_purpose": spec.francis_native_purpose,
            "user_facing_description": spec.user_facing_description,
            "capability_class": spec.capability_class,
            "copy_policy": spec.copy_policy,
            "conceptual_rebuild_only": spec.conceptual_rebuild_only,
            "risk": spec.risk.to_dict(),
            "interface": spec.interface.to_dict(),
            "validation": spec.validation.to_dict(),
            "source_evidence_references": spec.source_evidence_references[:40],
            "license_attribution_note": spec.license_attribution_note,
        },
        "edit_scope": {
            "allowed_files": request.allowed_files,
            "forbidden_paths_enforced_but_omitted": True,
            "max_files_changed": request.max_files_changed,
            "max_iterations": request.max_iterations,
        },
        "hard_rules": [
            "Return a proposed patch or implementation plan only.",
            "Do not claim authority to apply changes.",
            "Do not copy third-party implementation code.",
            "Do not request secrets or external network access.",
            "Do not edit outside allowed_files.",
            "If the task requires forbidden paths or unclear licensing, refuse with blockers.",
        ],
        "validation_commands": request.validation_commands,
        "stop_conditions": request.stop_conditions,
    }
    prompt = json.dumps(prompt_payload, indent=2, sort_keys=True, ensure_ascii=False)
    if len(prompt) > MAX_PROMPT_CHARS:
        return prompt[:MAX_PROMPT_CHARS] + "\n...[prompt truncated]..."
    return prompt


def _proposal_from_text(text: str) -> BuilderPatchProposal:
    excerpt, truncated = _excerpt(text)
    lower = text.lower()
    patch = "diff --git " in lower or "*** begin patch" in lower or lower.lstrip().startswith("--- ")
    files: list[str] = []
    for line in text.splitlines():
        if line.startswith("+++ b/") or line.startswith("--- b/"):
            files.append(_normalize_path(line[6:]))
        elif line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4 and parts[3].startswith("b/"):
                files.append(_normalize_path(parts[3][2:]))
    return BuilderPatchProposal(
        text_excerpt=excerpt,
        text_digest=_text_digest(text) if text else "",
        truncated=truncated,
        patch_proposed=patch,
        plan_proposed=bool(text and not patch),
        files_intended=sorted(set(files)),
    )


def _looks_like_model_refusal(text: str) -> bool:
    clean = text.strip().lower()
    return clean.startswith("refused") or '"response": "refused' in clean or "cannot comply" in clean


class LocalOllamaBuilder:
    """Localhost-only Ollama adapter that records proposals but never applies them."""

    def __init__(
        self,
        config: OllamaBuilderConfig | None = None,
        *,
        client: OllamaClient | None = None,
        receipt_writer: ReceiptWriter | None = None,
    ) -> None:
        self.config = config or OllamaBuilderConfig.from_env()
        self._client = client or _ollama_generate
        self._receipts = receipt_writer or ReceiptWriter()

    def run(self, request: OllamaBuildRequest, *, actor: str = "francis/system") -> OllamaBuildResult:
        started = utc_now()
        run_id = _record_id("builder_run")
        model = request.model or self.config.model or DEFAULT_OLLAMA_MODEL
        prompt = build_ollama_prompt(request)
        prompt_digest = _text_digest(prompt)
        warnings: list[str] = []
        errors: list[str] = []
        status = "blocked"
        response_text = ""
        ollama_available = False
        refusal_reason = ""
        blockers = forbidden_scope_violations(request.allowed_files, request.forbidden_files)
        if not _host_is_localhost(self.config.host):
            blockers.append("ollama_host_not_localhost")
        if request.max_files_changed < 1:
            blockers.append("max_files_changed_invalid")
        if request.max_iterations < 1:
            blockers.append("max_iterations_invalid")

        if blockers:
            status = "blocked"
            errors.extend(blockers)
        else:
            try:
                response_text = self._client(self.config.host, model, prompt, self.config.timeout_seconds)
                ollama_available = True
                if _looks_like_model_refusal(response_text):
                    status = "refused"
                    refusal_reason = "model_refused"
                    warnings.append("model_refused")
                else:
                    status = "proposed" if response_text else "completed"
            except (OSError, TimeoutError, urllib.error.URLError, ConnectionError) as exc:
                status = "unavailable"
                warnings.append("ollama_unavailable")
                errors.append(f"ollama_unavailable:{exc}")
            except Exception as exc:  # defensive: model adapters must not crash callers
                status = "failed"
                errors.append(f"ollama_builder_failed:{exc}")

        proposal = _proposal_from_text(response_text)
        completed = utc_now()
        record = BuilderRunRecord(
            builder_run_id=run_id,
            task_id=request.task_id,
            spec_id=request.spec.id,
            source_id=request.spec.source_id,
            candidate_id=request.spec.candidate_id,
            candidate_name=request.spec.capability_name,
            model=model,
            started_at=started,
            completed_at=completed,
            status=status,
            prompt_digest=prompt_digest,
            response_digest=proposal.text_digest,
            allowed_files=list(request.allowed_files),
            forbidden_files=list(request.forbidden_files),
            max_files_changed=request.max_files_changed,
            max_iterations=request.max_iterations,
            validation_commands_requested=list(request.validation_commands),
            validation_commands_suggested=list(request.validation_commands),
            validation_commands_run=[],
            risk_level=request.risk_level,
            stop_conditions=list(request.stop_conditions),
            required_receipt_kind=request.required_receipt_kind,
            ollama_host=self.config.host,
            ollama_available=ollama_available,
            patch_proposed=proposal.patch_proposed,
            patch_applied=False,
            validation_status="not_run",
            refusal_reason=refusal_reason,
            blocker_reason=";".join(blockers),
            proposal=proposal,
            errors=errors,
            warnings=warnings,
        )
        artifact_path = write_ingest_record_artifact("builder_runs", run_id, {"builder_run": record.to_dict()})
        receipt, receipt_path = self._receipts.write(
            operation=BUILDER_OPERATION,
            source_id=request.spec.source_id,
            actor=actor,
            input_paths=[],
            input_hashes=[request.spec.id, prompt_digest, proposal.text_digest],
            result_status=status,
            warnings=warnings,
            errors=errors,
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "localhost_ollama_host_checked",
                "forbidden_file_scope_checked",
                "patch_not_applied",
                "validation_not_run",
                f"copy_policy:{request.spec.copy_policy}",
            ],
        )
        record = BuilderRunRecord(
            **{
                **record.to_dict(),
                "artifact_path": str(artifact_path),
                "receipt_path": str(receipt_path),
                "proposal": proposal,
            }
        )
        artifact_path = write_ingest_record_artifact("builder_runs", run_id, {"builder_run": record.to_dict()})
        ok = status in {"proposed", "completed"}
        return OllamaBuildResult(
            ok=ok,
            status=status,
            record=record,
            artifact_path=str(artifact_path),
            receipt_path=str(receipt_path),
            proposed_patch_text=response_text if proposal.patch_proposed else "",
            plan_text=response_text if proposal.plan_proposed else "",
        )


__all__ = [
    "BUILDER_OPERATION",
    "COPY_POLICY_DO_NOT_COPY",
    "DEFAULT_FORBIDDEN_FILES",
    "DEFAULT_OLLAMA_HOST",
    "DEFAULT_OLLAMA_MODEL",
    "CapabilityBuildTask",
    "CapabilityInterfaceSpec",
    "CapabilityRiskSpec",
    "CapabilityValidationSpec",
    "FrancisCapabilitySpec",
    "LocalOllamaBuilder",
    "OllamaBuilderConfig",
    "OllamaBuildRequest",
    "OllamaBuildResult",
    "BuilderPatchProposal",
    "BuilderRunRecord",
    "build_ollama_prompt",
    "compile_capability_spec_from_candidate",
    "forbidden_scope_violations",
]
