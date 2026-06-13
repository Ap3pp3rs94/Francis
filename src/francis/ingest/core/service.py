from __future__ import annotations

from typing import Any

from ..ingest.capabilities import CapabilityCandidateExtractor
from ..ingest.repo_adapter import RepoAdapter
from ..lab.lab_runtime import CapabilityRebuilder, SandboxExecutor
from .acquisition_service import AcquisitionIngestService
from .builder_service import BuilderIngestService
from .forge_service import ForgeSynthesisIngestService
from .lab_service import LabIngestService
from .registry import CapabilityRegistry, ReceiptWriter, SourceRegistry
from .service_base import BaseIngestService


class IngestService(
    BaseIngestService,
    LabIngestService,
    AcquisitionIngestService,
    BuilderIngestService,
    ForgeSynthesisIngestService,
):
    def __init__(
        self,
        *,
        source_registry: SourceRegistry | None = None,
        capability_registry: CapabilityRegistry | None = None,
        receipt_writer: ReceiptWriter | None = None,
        repo_adapter: RepoAdapter | None = None,
        extractor: CapabilityCandidateExtractor | None = None,
        sandbox_executor: SandboxExecutor | None = None,
        rebuilder: CapabilityRebuilder | None = None,
        command_runner: Any | None = None,
    ) -> None:
        self.sources = source_registry or SourceRegistry()
        self.capabilities = capability_registry or CapabilityRegistry()
        self.receipts = receipt_writer or ReceiptWriter()
        self.repo_adapter = repo_adapter or RepoAdapter()
        self.extractor = extractor or CapabilityCandidateExtractor()
        # Lab v0 runtime. `command_runner` lets tests inject a fake (no Docker).
        self.sandbox = sandbox_executor or SandboxExecutor(command_runner)
        self.rebuilder = rebuilder or CapabilityRebuilder()
        self._lab_command_runner = command_runner
