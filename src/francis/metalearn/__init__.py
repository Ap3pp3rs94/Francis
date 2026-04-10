from __future__ import annotations

from .architectural_evolution.ab_testing import AbTestPlan, AbTester
from .architectural_evolution.architecture_proposer import ArchitectureProposal, ArchitectureProposer
from .architectural_evolution.evolution_manager import EvolutionManager, EvolutionResult
from .architectural_evolution.subsystem_evaluator import SubsystemEvaluator, SubsystemScore
from .capability_discovery.frontier_mapper import CapabilityFrontier, FrontierMapper
from .capability_discovery.gap_identifier import CapabilityGap, GapIdentifier
from .capability_discovery.innovation_tracker import InnovationRecord, InnovationTracker
from .capability_discovery.synthesis_suggester import SynthesisSuggestion, SynthesisSuggester
from .learning_optimization.active_learning import ActiveLearningLoop, ActiveLearningResult
from .learning_optimization.curriculum_optimizer import CurriculumOptimizer, CurriculumResult
from .learning_optimization.sample_efficiency import SampleEfficiencyOptimizer
from .learning_optimization.transfer_learning_engine import TransferLearningEngine, TransferLearningOutcome
from .performance_analysis.blindspot_detector import BlindspotDetector, BlindspotReport
from .performance_analysis.capability_profiler import CapabilityProfile, CapabilityProfiler
from .performance_analysis.error_pattern_analyzer import ErrorPatternAnalyzer, ErrorPatternReport
from .performance_analysis.improvement_recommender import ImprovementRecommendation, ImprovementRecommender

__all__ = [
    "AbTestPlan",
    "AbTester",
    "ArchitectureProposal",
    "ArchitectureProposer",
    "EvolutionManager",
    "EvolutionResult",
    "SubsystemEvaluator",
    "SubsystemScore",
    "CapabilityFrontier",
    "FrontierMapper",
    "CapabilityGap",
    "GapIdentifier",
    "InnovationRecord",
    "InnovationTracker",
    "SynthesisSuggestion",
    "SynthesisSuggester",
    "ActiveLearningLoop",
    "ActiveLearningResult",
    "CurriculumOptimizer",
    "CurriculumResult",
    "SampleEfficiencyOptimizer",
    "TransferLearningEngine",
    "TransferLearningOutcome",
    "BlindspotDetector",
    "BlindspotReport",
    "CapabilityProfile",
    "CapabilityProfiler",
    "ErrorPatternAnalyzer",
    "ErrorPatternReport",
    "ImprovementRecommendation",
    "ImprovementRecommender",
]
