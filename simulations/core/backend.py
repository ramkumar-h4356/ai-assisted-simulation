"""Define the common interface for simulation execution backends."""

from dataclasses import dataclass
from typing import Protocol

from simulations.core.specification import (
    SimulationParadigm,
    SimulationSpecification,
)

@dataclass(frozen=True, slots=True)
class SimulationMetric:
    """Represent one backend-independent simulation metric."""

    name: str
    value: str | int | float | bool
    unit: str | None = None

@dataclass(frozen=True, slots=True)
class SimulationExecutionResult:
    """Represent the common outcome of a simulation execution."""

    specification_name: str
    paradigm: SimulationParadigm
    backend_name: str
    metrics: tuple[SimulationMetric, ...]
    native_result: object

class SimulationBackend(Protocol):
    """Contract that all simulation backends must implement."""

    name: str
    paradigm: SimulationParadigm

    def execute(
        self,
        specification: SimulationSpecification,
    ) -> SimulationExecutionResult:
        """Execute a validated paradigm-specific simulation."""
        ...