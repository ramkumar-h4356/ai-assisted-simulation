"""Domain object representing an item that moves through a simulation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any


@dataclass(slots=True)
class Entity:
    """A uniquely identified item handled by a discrete-event simulation.

    ``created_at`` is measured in the simulation's own time unit. Attributes
    hold scenario-specific data, such as a customer's priority or an item's
    destination, without coupling the simulation engine to one domain.
    """

    identifier: str
    created_at: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.identifier, str) or not self.identifier.strip():
            raise ValueError("identifier must be a non-empty string")

        if isinstance(self.created_at, bool) or not isinstance(
            self.created_at, (int, float)
        ):
            raise TypeError("created_at must be a finite number")
        if not isfinite(self.created_at) or self.created_at < 0:
            raise ValueError("created_at must be a finite, non-negative number")

        if not isinstance(self.attributes, Mapping):
            raise TypeError("attributes must be a mapping")

        # Keep the entity independent from a caller-owned mapping.
        self.attributes = dict(self.attributes)

    def get(self, name: str, default: Any = None) -> Any:
        """Return an attribute value, or ``default`` when it has not been set."""
        return self.attributes.get(name, default)

    def set(self, name: str, value: Any) -> None:
        """Store scenario-specific data under a non-empty attribute name."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("attribute name must be a non-empty string")
        self.attributes[name] = value

    def update(self, values: Mapping[str, Any]) -> None:
        """Set several named attributes at once."""
        if not isinstance(values, Mapping):
            raise TypeError("values must be a mapping")
        for name, value in values.items():
            self.set(name, value)
