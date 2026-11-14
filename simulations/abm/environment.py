"""Spatial environment queries, grid helpers and deterministic spatial indexing.

This module is independent of the simulation engine. Its data source is the
immutable SpatialSpace definition, while SpatialIndex is a mutable utility for
runtime populations and large object collections.
"""

from __future__ import annotations

from collections import defaultdict
from math import floor, hypot, isfinite
from typing import Iterable, Mapping

from simulations.abm.model import (
    EnvironmentalObject,
    Position,
    SpatialRegion,
    SpatialSpace,
    SpatialZone,
)

_EPSILON = 1e-10


def _finite_non_negative(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise TypeError(f"{name} must be a finite number")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return float(value)


def _point_on_segment(point: Position, start: Position, end: Position) -> bool:
    cross = (point.x - start.x) * (end.y - start.y) - (point.y - start.y) * (end.x - start.x)
    if abs(cross) > _EPSILON:
        return False
    return (
        min(start.x, end.x) - _EPSILON <= point.x <= max(start.x, end.x) + _EPSILON
        and min(start.y, end.y) - _EPSILON <= point.y <= max(start.y, end.y) + _EPSILON
    )


def point_in_polygon(point: Position, polygon: tuple[Position, ...]) -> bool:
    """Return whether a point is in a polygon; its boundary counts as inside."""
    if not isinstance(point, Position):
        raise TypeError("point must be a Position")
    if len(polygon) < 3:
        return False
    inside = False
    previous = polygon[-1]
    for current in polygon:
        if _point_on_segment(point, previous, current):
            return True
        if (current.y > point.y) != (previous.y > point.y):
            intersection_x = (
                (previous.x - current.x) * (point.y - current.y)
                / (previous.y - current.y)
                + current.x
            )
            if point.x < intersection_x:
                inside = not inside
        previous = current
    return inside


def _segment_intersection_parameter(
    start: Position, end: Position, edge_start: Position, edge_end: Position
) -> float | None:
    """Return segment parameter t for a non-parallel intersection in [0, 1]."""
    dx, dy = end.x - start.x, end.y - start.y
    ex, ey = edge_end.x - edge_start.x, edge_end.y - edge_start.y
    denominator = dx * ey - dy * ex
    qx, qy = edge_start.x - start.x, edge_start.y - start.y
    if abs(denominator) <= _EPSILON:
        if abs(qx * dy - qy * dx) <= _EPSILON:
            # Collinear overlap is handled conservatively by endpoint checks.
            if _point_on_segment(edge_start, start, end):
                length_sq = dx * dx + dy * dy
                return 0.0 if length_sq <= _EPSILON else ((edge_start.x - start.x) * dx + (edge_start.y - start.y) * dy) / length_sq
            if _point_on_segment(edge_end, start, end):
                length_sq = dx * dx + dy * dy
                return 0.0 if length_sq <= _EPSILON else ((edge_end.x - start.x) * dx + (edge_end.y - start.y) * dy) / length_sq
        return None
    t = (qx * ey - qy * ex) / denominator
    u = (qx * dy - qy * dx) / denominator
    if -_EPSILON <= t <= 1 + _EPSILON and -_EPSILON <= u <= 1 + _EPSILON:
        return min(1.0, max(0.0, t))
    return None


def segment_intersects_polygon(
    start: Position, end: Position, polygon: tuple[Position, ...]
) -> bool:
    """Detect any segment crossing, touching, or entering a polygon."""
    if point_in_polygon(start, polygon) or point_in_polygon(end, polygon):
        return True
    for left, right in zip(polygon, polygon[1:] + polygon[:1]):
        parameter = _segment_intersection_parameter(start, end, left, right)
        if parameter is not None:
            return True
        # For a segment that runs along a polygon edge, any boundary contact
        # is an intersection even when the endpoints are outside the polygon.
        if _point_on_segment(left, start, end) or _point_on_segment(right, start, end):
            return True
    return False


def regions_at(space: SpatialSpace, position: Position) -> tuple[SpatialRegion, ...]:
    """Return all semantic regions containing a point, ordered by declaration."""
    if not isinstance(space, SpatialSpace):
        raise TypeError("space must be a SpatialSpace")
    return tuple(item for item in space.regions if point_in_polygon(position, item.polygon))


def zones_at(space: SpatialSpace, position: Position) -> tuple[SpatialZone, ...]:
    """Return all navigation zones containing a point, ordered by declaration."""
    if not isinstance(space, SpatialSpace):
        raise TypeError("space must be a SpatialSpace")
    return tuple(item for item in space.zones if point_in_polygon(position, item.polygon))


def navigation_cost_at(space: SpatialSpace, position: Position) -> float:
    """Multiply overlapping zone costs; every zone cost is at least one."""
    cost = 1.0
    for zone in zones_at(space, position):
        if not zone.passable:
            return float("inf")
        cost *= zone.navigation_cost
    return cost


def environment_objects_near(
    space: SpatialSpace, position: Position, radius: float
) -> tuple[EnvironmentalObject, ...]:
    """Return object footprints intersecting a query radius around a point."""
    distance = _finite_non_negative(radius, "query radius")
    if not isinstance(space, SpatialSpace):
        raise TypeError("space must be a SpatialSpace")
    if not isinstance(position, Position):
        raise TypeError("position must be a Position")
    query_position = space.normalize(position)
    return tuple(
        item for item in space.objects
        if space.distance(query_position, item.position) <= distance + item.radius + _EPSILON
    )


class SpatialIndex:
    """Uniform-hash index for deterministic point-neighbourhood queries.

    The index stores one point per identifier. Radius and bounds queries inspect
    only intersecting buckets, then perform exact geometric filtering. Results
    are sorted by identifier so query output does not depend on set/dict order.
    """

    def __init__(self, cell_size: float) -> None:
        if isinstance(cell_size, bool) or not isinstance(cell_size, (int, float)) or not isfinite(cell_size) or cell_size <= 0:
            raise ValueError("cell_size must be positive and finite")
        self.cell_size = float(cell_size)
        self._positions: dict[str, Position] = {}
        self._buckets: dict[tuple[int, int], set[str]] = defaultdict(set)

    def __len__(self) -> int:
        return len(self._positions)

    def __contains__(self, identifier: object) -> bool:
        return identifier in self._positions

    def _cell(self, position: Position) -> tuple[int, int]:
        return floor(position.x / self.cell_size), floor(position.y / self.cell_size)

    def add(self, identifier: str, position: Position) -> None:
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError("identifier must be a non-empty string")
        if not isinstance(position, Position):
            raise TypeError("position must be a Position")
        if identifier in self._positions:
            raise ValueError(f"identifier {identifier!r} is already indexed")
        self._positions[identifier] = position
        self._buckets[self._cell(position)].add(identifier)

    def move(self, identifier: str, position: Position) -> None:
        if identifier not in self._positions:
            raise KeyError(identifier)
        if not isinstance(position, Position):
            raise TypeError("position must be a Position")
        old_cell = self._cell(self._positions[identifier])
        new_cell = self._cell(position)
        self._positions[identifier] = position
        if old_cell != new_cell:
            bucket = self._buckets[old_cell]
            bucket.remove(identifier)
            if not bucket:
                del self._buckets[old_cell]
            self._buckets[new_cell].add(identifier)

    def remove(self, identifier: str) -> Position:
        if identifier not in self._positions:
            raise KeyError(identifier)
        position = self._positions.pop(identifier)
        cell = self._cell(position)
        bucket = self._buckets[cell]
        bucket.remove(identifier)
        if not bucket:
            del self._buckets[cell]
        return position

    def position(self, identifier: str) -> Position:
        return self._positions[identifier]

    def _candidate_ids(
        self, first_column: int, last_column: int, first_row: int, last_row: int
    ) -> set[str]:
        column_count = last_column - first_column + 1
        row_count = last_row - first_row + 1
        # Large query windows should scan the stored identifiers rather than
        # iterating through an enormous empty rectangle of hash buckets.
        if column_count * row_count > max(16, len(self._buckets) * 2):
            return set(self._positions)
        candidates: set[str] = set()
        for column in range(first_column, last_column + 1):
            for row in range(first_row, last_row + 1):
                candidates.update(self._buckets.get((column, row), ()))
        return candidates

    def query_radius(self, center: Position, radius: float) -> tuple[tuple[str, Position], ...]:
        if not isinstance(center, Position):
            raise TypeError("center must be a Position")
        radius = _finite_non_negative(radius, "query radius")
        bounds = (center.x - radius, center.x + radius, center.y - radius, center.y + radius)
        if any(not isfinite(value) for value in bounds):
            candidates = set(self._positions)
        else:
            min_x, max_x = floor(bounds[0] / self.cell_size), floor(bounds[1] / self.cell_size)
            min_y, max_y = floor(bounds[2] / self.cell_size), floor(bounds[3] / self.cell_size)
            candidates = self._candidate_ids(min_x, max_x, min_y, max_y)
        return tuple(
            (identifier, self._positions[identifier])
            for identifier in sorted(candidates)
            if hypot(self._positions[identifier].x - center.x, self._positions[identifier].y - center.y) <= radius + _EPSILON
        )

    def query_bounds(
        self, min_x: float, min_y: float, max_x: float, max_y: float
    ) -> tuple[tuple[str, Position], ...]:
        values = [min_x, min_y, max_x, max_y]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) for value in values):
            raise TypeError("query bounds must be finite numbers")
        if min_x > max_x or min_y > max_y:
            raise ValueError("query bounds must have min values no greater than max values")
        first_x, last_x = floor(min_x / self.cell_size), floor(max_x / self.cell_size)
        first_y, last_y = floor(min_y / self.cell_size), floor(max_y / self.cell_size)
        candidates = self._candidate_ids(first_x, last_x, first_y, last_y)
        return tuple(
            (identifier, self._positions[identifier])
            for identifier in sorted(candidates)
            if min_x <= self._positions[identifier].x <= max_x
            and min_y <= self._positions[identifier].y <= max_y
        )

    @classmethod
    def from_positions(
        cls, positions: Mapping[str, Position] | Iterable[tuple[str, Position]], cell_size: float
    ) -> "SpatialIndex":
        index = cls(cell_size)
        items = positions.items() if isinstance(positions, Mapping) else positions
        for identifier, position in items:
            index.add(identifier, position)
        return index
