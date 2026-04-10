from __future__ import annotations

from .adaptation.continuous_learning import ContinuousLearning, LearningState
from .adaptation.drift_correction import DriftCorrection, DriftCorrectionResult
from .adaptation.incremental_update import IncrementalUpdate, UpdateState
from .forecasting.capability_obsolescence import CapabilityObsolescence, ObsolescenceReport
from .forecasting.domain_drift_predictor import DomainDriftPrediction, DomainDriftPredictor
from .forecasting.regulatory_change_tracker import RegulatoryChange, RegulatoryChangeTracker
from .forecasting.technology_horizon_scanner import HorizonScan, TechnologyHorizonScanner
from .history.counterfactual_analysis import CounterfactualAnalysis, CounterfactualOutcome
from .history.decision_replay import DecisionReplay, ReplayResult
from .history.domain_archaeology import DomainArchaeology, ArchaeologyResult
from .versioning.backward_compatibility import CompatibilityReport, BackwardCompatibility
from .versioning.domain_version_manager import DomainVersion, DomainVersionManager
from .versioning.migration_planner import MigrationPlan, MigrationPlanner
from .versioning.rollback_manager import RollbackManager, RollbackResult

__all__ = [
    "ContinuousLearning",
    "LearningState",
    "DriftCorrection",
    "DriftCorrectionResult",
    "IncrementalUpdate",
    "UpdateState",
    "CapabilityObsolescence",
    "ObsolescenceReport",
    "DomainDriftPrediction",
    "DomainDriftPredictor",
    "RegulatoryChange",
    "RegulatoryChangeTracker",
    "HorizonScan",
    "TechnologyHorizonScanner",
    "CounterfactualAnalysis",
    "CounterfactualOutcome",
    "DecisionReplay",
    "ReplayResult",
    "DomainArchaeology",
    "ArchaeologyResult",
    "CompatibilityReport",
    "BackwardCompatibility",
    "DomainVersion",
    "DomainVersionManager",
    "MigrationPlan",
    "MigrationPlanner",
    "RollbackManager",
    "RollbackResult",
]
