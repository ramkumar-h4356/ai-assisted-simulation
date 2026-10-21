"""Domain definition for a capacity-limited simulation resource."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Resource:
    """Describe a resource that processes may request during a simulation.

    This stores the resource's name and capacity. SimPy will manage requests,
    waiting queues, and releases when we connect resources to the runtime.
    """

    name: str
    capacity: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")

        if isinstance(self.capacity, bool) or not isinstance(self.capacity, int):
            raise TypeError("capacity must be a positive integer")
        if self.capacity <= 0:
            raise ValueError("capacity must be a positive integer")