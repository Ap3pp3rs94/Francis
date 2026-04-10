from __future__ import annotations

import logging

from francis.kernel.paths import repo_root

from .adversary_profiler import AdversaryProfile, AdversaryProfiler
from .attack_scenario_generator import AttackScenario, AttackScenarioGenerator
from .attack_surface_mapper import AttackSurface, AttackSurfaceMapper
from .vulnerability_scanner import VulnerabilityFinding, VulnerabilityScanner

logger = logging.getLogger(__name__)

__all__ = [
    "AdversaryProfile",
    "AdversaryProfiler",
    "AttackScenario",
    "AttackScenarioGenerator",
    "AttackSurface",
    "AttackSurfaceMapper",
    "VulnerabilityFinding",
    "VulnerabilityScanner",
    "ThreatModelingModule",
]


class ThreatModelingModule:
    """
    Class to encapsulate threat modeling functionalities.

    Attributes:
        adversary_profiler (Any): Instance of the adversary profiler.
        attack_scenario_generator (Any): Instance of the attack scenario generator.
        attack_surface_mapper (Any): Instance of the attack surface mapper.
        vulnerability_scanner (Any): Instance of the vulnerability scanner.
    """

    def __init__(
        self,
        adversary_profiler: AdversaryProfiler | None = None,
        attack_scenario_generator: AttackScenarioGenerator | None = None,
        attack_surface_mapper: AttackSurfaceMapper | None = None,
        vulnerability_scanner: VulnerabilityScanner | None = None,
    ):
        self.adversary_profiler = adversary_profiler or AdversaryProfiler()
        self.attack_scenario_generator = attack_scenario_generator or AttackScenarioGenerator()
        self.attack_surface_mapper = attack_surface_mapper or AttackSurfaceMapper(root=repo_root())
        self.vulnerability_scanner = vulnerability_scanner or VulnerabilityScanner()

    def profile_adversaries(self) -> list[AdversaryProfile]:
        try:
            return [self.adversary_profiler.profile([])]
        except Exception:
            logger.error("Error profiling adversaries", exc_info=True)
            return []

    def generate_attack_scenarios(self, profiles: list[AdversaryProfile]) -> list[AttackScenario]:
        if not profiles:
            return []
        try:
            out: list[AttackScenario] = []
            for p in profiles:
                out.extend(self.attack_scenario_generator.generate(p))
            return out
        except Exception:
            logger.error("Error generating attack scenarios", exc_info=True)
            return []

    def map_attack_surface(self, scenarios: list[AttackScenario]) -> AttackSurface:
        try:
            # AttackSurfaceMapper expects scenario metadata dicts (entry points, boundaries).
            # We don't currently derive those from AttackScenario objects, so we focus on
            # mapping the workspace files to build the surface.
            return self.attack_surface_mapper.map(None)
        except Exception:
            logger.error("Error mapping attack surface", exc_info=True)
            return AttackSurface(assets=[], entry_points=[], trust_boundaries=[])

    def scan_vulnerabilities(self, surface: AttackSurface) -> list[VulnerabilityFinding]:
        try:
            return self.vulnerability_scanner.scan(surface)
        except Exception:
            logger.error("Error scanning vulnerabilities", exc_info=True)
            return []
