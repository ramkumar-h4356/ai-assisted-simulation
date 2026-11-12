"""Shared contracts for all simulation paradigms."""

from .backend import SimulationBackend, SimulationExecutionResult, SimulationMetric
from .registry import BackendRegistry
from .specification import SimulationParadigm, SimulationSpecification

__all__ = [
    "BackendRegistry",
    "SimulationBackend",
    "SimulationExecutionResult",
    "SimulationMetric",
    "SimulationParadigm",
    "SimulationSpecification",
]
