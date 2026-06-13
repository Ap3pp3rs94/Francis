# mypy: disable-error-code=attr-defined
from __future__ import annotations

from pathlib import Path
from typing import Any

from .local_builder import (
    FrancisCapabilitySpec,
    LocalOllamaBuilder,
    OllamaBuilderConfig,
    OllamaBuildRequest,
    compile_capability_spec_from_candidate,
)
from .registry import write_ingest_record_artifact
from .service_base import (
    _artifact_readbacks,
    _bounded_limit,
    _display_payload,
    _load_ingest_record_payload,
    _no_lab_execution_payload,
    _safe_str,
)


class BuilderIngestService:
    def compile_capability_spec(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        *,
        actor: str = "francis/system",
        allowed_files: list[str] | None = None,
        forbidden_files: list[str] | None = None,
    ) -> dict[str, Any]:
        """Compile ingest evidence into a Francis-native capability spec.

        Deterministic only: no LLM call, no code generation, no patch application.
        """

        source = self._record_from_source_or_path(source_or_path, actor=actor)
        candidate = self._candidate_from_ref(source, candidate_ref, actor=actor)
        if candidate is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_candidate_unavailable",
                    "source": source.to_dict(),
                    "execution": _no_lab_execution_payload(reason="capability_candidate_unavailable"),
                }
            )
        repo_map = self._load_repo_map(source)
        if repo_map is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": "repo_map_unavailable",
                    "source": source.to_dict(),
                    "candidate": candidate.to_dict(),
                    "execution": _no_lab_execution_payload(reason="repo_map_unavailable"),
                }
            )

        spec = compile_capability_spec_from_candidate(
            source=source,
            candidate=candidate,
            repo_map=repo_map,
            allowed_files=allowed_files,
            forbidden_files=forbidden_files,
        )
        artifact_path = write_ingest_record_artifact(
            "capability_specs",
            spec.id,
            {"capability_spec": spec.to_dict()},
        )
        receipt, receipt_path = self.receipts.write(
            operation="builder.capability_spec.compile",
            source_id=source.id,
            actor=actor,
            input_paths=[source.canonical_path],
            input_hashes=[source.fingerprint, candidate.id, spec.id],
            result_status="compiled",
            warnings=[],
            generated_artifact_paths=[str(artifact_path)],
            validation_performed=[
                "ingest_candidate_loaded",
                "repo_map_loaded",
                "francis_native_spec_compiled",
                f"copy_policy:{spec.copy_policy}",
                "conceptual_rebuild_only",
            ],
        )
        return _display_payload(
            {
                "ok": True,
                "status": "compiled",
                "source": source.to_dict(),
                "candidate": candidate.to_dict(),
                "capability_spec": spec.to_dict(),
                "artifact_path": str(artifact_path),
                "receipt": receipt.to_dict(),
                "receipt_path": str(receipt_path),
                "execution": _no_lab_execution_payload(reason="spec_compile_only_no_execution"),
            }
        )

    def run_local_ollama_builder(
        self,
        source_or_path: str | Path,
        candidate_ref: str,
        *,
        actor: str = "francis/system",
        model: str = "",
        host: str = "",
        allowed_files: list[str] | None = None,
        forbidden_files: list[str] | None = None,
    ) -> dict[str, Any]:
        """Request a local Ollama proposal artifact for a compiled capability spec.

        This never applies a patch and never validates/promotes a capability.
        """

        compiled = self.compile_capability_spec(
            source_or_path,
            candidate_ref,
            actor=actor,
            allowed_files=allowed_files,
            forbidden_files=forbidden_files,
        )
        if not bool(compiled.get("ok")):
            return compiled
        spec = FrancisCapabilitySpec.from_dict(compiled.get("capability_spec"))
        if spec is None:
            return _display_payload(
                {
                    "ok": False,
                    "status": "failed",
                    "error": "capability_spec_unavailable",
                    "execution": _no_lab_execution_payload(reason="capability_spec_unavailable"),
                }
            )
        config = OllamaBuilderConfig.from_env()
        if host:
            config = OllamaBuilderConfig(host=host, model=model or config.model, timeout_seconds=config.timeout_seconds)
        elif model:
            config = OllamaBuilderConfig(host=config.host, model=model, timeout_seconds=config.timeout_seconds)
        request = OllamaBuildRequest.from_spec(spec, model=config.model)
        if allowed_files is not None or forbidden_files is not None:
            request = OllamaBuildRequest(
                task_id=request.task_id,
                spec=request.spec,
                model=request.model,
                allowed_files=list(allowed_files or request.allowed_files),
                forbidden_files=list(forbidden_files or request.forbidden_files),
                max_files_changed=request.max_files_changed,
                max_iterations=request.max_iterations,
                validation_commands=request.validation_commands,
                risk_level=request.risk_level,
                stop_conditions=request.stop_conditions,
                required_receipt_kind=request.required_receipt_kind,
            )
        builder = LocalOllamaBuilder(config=config, receipt_writer=self.receipts)
        result = builder.run(request, actor=actor)
        payload = result.to_dict()
        payload.update(
            {
                "kind": "francis.ingest.local_ollama_builder",
                "source": compiled.get("source"),
                "candidate": compiled.get("candidate"),
                "capability_spec": spec.to_dict(),
                "capability_spec_artifact_path": compiled.get("artifact_path", ""),
                "capability_spec_receipt_path": compiled.get("receipt_path", ""),
                "execution": _no_lab_execution_payload(reason="builder_proposal_only_no_execution"),
            }
        )
        return _display_payload(payload)

    def list_builder_runs(self, *, source_id: str = "", limit: int = 100) -> dict[str, Any]:
        clean_source_id = _safe_str(source_id).strip()
        safe_limit = _bounded_limit(limit)
        runs = _artifact_readbacks("builder_runs", "builder_run", source_id=clean_source_id, limit=safe_limit)
        return _display_payload(
            {
                "ok": True,
                "status": "readback",
                "source_id": clean_source_id,
                "builder_runs": runs,
                "count": len(runs),
                "execution": _no_lab_execution_payload(reason="readback_only_no_execution"),
            }
        )

    def get_builder_run(self, builder_run_id: str) -> dict[str, Any]:
        record = _load_ingest_record_payload("builder_runs", "builder_run", builder_run_id)
        return _display_payload(
            {
                "ok": bool(record),
                "status": "found" if record else "missing",
                "builder_run_id": _safe_str(builder_run_id).strip(),
                "builder_run": record,
                "execution": _no_lab_execution_payload(reason="readback_only_no_execution"),
            }
        )
