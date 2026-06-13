# mypy: disable-error-code=arg-type
from __future__ import annotations

from pathlib import Path
from typing import Any


class AcquisitionIngestService:
    def acquire_source_candidate(
        self,
        source_or_path: str | Path,
        candidate_id: str = "",
        *,
        opt_in: bool = False,
        actor: str = "francis/system",
        lab_image: str = "",
    ) -> dict[str, Any]:
        """Start a governed ingest acquisition run (pushes the pipeline to the first gate)."""
        from .acquisition import IngestAcquisitionOrchestrator

        return IngestAcquisitionOrchestrator(self).acquire_source_candidate(
            source_or_path, candidate_id, opt_in=opt_in, actor=actor, lab_image=lab_image
        )

    def continue_acquisition_after_approval(self, run_id: str, *, actor: str = "francis/system") -> dict[str, Any]:
        """Resume a paused acquisition run after the operator approved the pending gate."""
        from .acquisition import IngestAcquisitionOrchestrator

        return IngestAcquisitionOrchestrator(self).continue_acquisition_after_approval(run_id, actor=actor)
