"""Define the common specification for simulation models."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

class SimulationParadigm(Enum):
    """Identify the mathematical or computational simulation approach."""

    DISCRETE_EVENT = "discrete_event"
    AGENT_BASED = "agent_based"
    SYSTEM_DYNAMICS = "system_dynamics"
    CONTINUOUS = "continuous"
    MONTE_CARLO = "monte_carlo"

@dataclass(frozen=True, slots=True)
class SimulationSpecification:
    """Wrap a paradigm-specific model in a common specification."""

    name: str
    paradigm: SimulationParadigm
    model: Any

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Simulation name must be non-empty")

        if not isinstance(self.paradigm, SimulationParadigm):
            raise TypeError("paradigm must be a SimulationParadigm")

        if self.model is None:
            raise ValueError("Simulation model must not be None")