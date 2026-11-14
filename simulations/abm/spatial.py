"""Deterministic geometry, collision and grid pathfinding for spatial ABM.

The routines in this module contain no simulation state. The ABM engine calls
these functions when a model action requests movement, then records the
resulting positions in its normal step snapshots.
"""

from __future__ import annotations

from heapq import heappop, heappush
from math import ceil, hypot, inf, sqrt
from typing import Iterable, Protocol

from simulations.abm.model import (
    CircleObstacle,
    Position,
    RectangleObstacle,
    SpatialSpace,
)

MAX_ASTAR_CELLS = 100_000
_EPSILON = 1e-10


class PositionedAgent(Protocol):
    identifier: str
    position: Position | None
    radius: float


def _point_segment_distance_squared(point: Position, start: Position, end: Position) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    length_squared = dx * dx + dy * dy
    if length_squared <= _EPSILON:
        return (point.x - start.x) ** 2 + (point.y - start.y) ** 2
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_squared
    t = min(1.0, max(0.0, t))
    nearest_x = start.x + t * dx
    nearest_y = start.y + t * dy
    return (point.x - nearest_x) ** 2 + (point.y - nearest_y) ** 2


def _segment_intersects_rectangle(
    start: Position,
    end: Position,
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> bool:
    """Liang-Barsky segment/AABB test, including endpoints and boundary touch."""
    dx = end.x - start.x
    dy = end.y - start.y
    lower, upper = 0.0, 1.0
    for p, q in (
        (-dx, start.x - left),
        (dx, right - start.x),
        (-dy, start.y - top),
        (dy, bottom - start.y),
    ):
        if abs(p) <= _EPSILON:
            if q < -_EPSILON:
                return False
            continue
        ratio = q / p
        if p < 0:
            lower = max(lower, ratio)
        else:
            upper = min(upper, ratio)
        if lower - upper > _EPSILON:
            return False
    return True


def _translations(space: SpatialSpace, start: Position, end: Position, margin: float):
    if space.boundary.value != "wrap":
        return ((0.0, 0.0),)
    min_x = min(start.x, end.x) - margin
    max_x = max(start.x, end.x) + margin
    min_y = min(start.y, end.y) - margin
    max_y = max(start.y, end.y) + margin
    first_x = int((min_x - space.width) // space.width)
    last_x = int((max_x + space.width) // space.width)
    first_y = int((min_y - space.height) // space.height)
    last_y = int((max_y + space.height) // space.height)
    translations_x = last_x - first_x + 1
    translations_y = last_y - first_y + 1
    if translations_x * translations_y > MAX_ASTAR_CELLS:
        raise ValueError(
            "Wrapped movement crosses too many world copies for safe collision checking; "
            "reduce the requested displacement or use smaller movement increments"
        )
    return tuple(
        (kx * space.width, ky * space.height)
        for kx in range(first_x, last_x + 1)
        for ky in range(first_y, last_y + 1)
    )


def _obstacle_blocks_segment(
    obstacle: RectangleObstacle | CircleObstacle,
    start: Position,
    end: Position,
    radius: float,
    dx: float = 0.0,
    dy: float = 0.0,
) -> bool:
    if isinstance(obstacle, RectangleObstacle):
        # Expanding the AABB by the agent radius is conservative around corners
        # and guarantees that the moving circular body cannot cut the rectangle.
        return _segment_intersects_rectangle(
            start,
            end,
            obstacle.x + dx - radius,
            obstacle.y + dy - radius,
            obstacle.x + dx + obstacle.width + radius,
            obstacle.y + dy + obstacle.height + radius,
        )
    center = Position(obstacle.x + dx, obstacle.y + dy)
    combined_radius = obstacle.radius + radius
    if combined_radius <= 0:
        return False
    return _point_segment_distance_squared(center, start, end) < (combined_radius - _EPSILON) ** 2


def path_is_clear(
    space: SpatialSpace,
    start: Position,
    end: Position,
    radius: float,
    other_agents: Iterable[PositionedAgent] = (),
    active_agent_id: str | None = None,
) -> tuple[bool, str | None]:
    """Check an entire straight movement segment against world geometry.

    Rectangle expansion is deliberately conservative at corners. Tangential
    circle/agent contact is allowed; penetration is not.
    """
    for obstacle in space.obstacles:
        margin = radius + (obstacle.radius if isinstance(obstacle, CircleObstacle) else 0.0)
        for dx, dy in _translations(space, start, end, margin):
            if _obstacle_blocks_segment(obstacle, start, end, radius, dx, dy):
                return False, f"obstacle:{obstacle.identifier}"

    if space.agent_collisions:
        for other in other_agents:
            if other.identifier == active_agent_id or other.position is None:
                continue
            combined_radius = radius + other.radius
            if combined_radius <= 0:
                continue
            for dx, dy in _translations(space, start, end, combined_radius):
                center = Position(other.position.x + dx, other.position.y + dy)
                if _point_segment_distance_squared(center, start, end) < (combined_radius - _EPSILON) ** 2:
                    return False, f"agent:{other.identifier}"
    return True, None


def _cell_center(space: SpatialSpace, column: int, row: int, cell_size: float) -> Position:
    left = column * cell_size
    top = row * cell_size
    right = min((column + 1) * cell_size, space.width)
    bottom = min((row + 1) * cell_size, space.height)
    return Position((left + right) / 2.0, (top + bottom) / 2.0)


def astar_path(
    space: SpatialSpace,
    start: Position,
    goal: Position,
    radius: float,
    grid_cell_size: float,
    other_agents: Iterable[PositionedAgent] = (),
    active_agent_id: str | None = None,
) -> tuple[Position, ...] | None:
    """Find a deterministic 8-connected A* route around static/dynamic blockers.

    The grid is a planning approximation. Every returned segment is checked
    against continuous obstacle and agent geometry before it is accepted.
    A finer cell size can resolve narrower passages at higher computational
    cost. Wrapped worlds are intentionally excluded from A* in this version.
    """
    if space.boundary.value != "clamp":
        raise ValueError("A* pathfinding currently requires a clamp-boundary world")
    if grid_cell_size <= 0:
        raise ValueError("grid_cell_size must be positive")

    columns = max(1, ceil(space.width / grid_cell_size))
    rows = max(1, ceil(space.height / grid_cell_size))
    if columns * rows > MAX_ASTAR_CELLS:
        raise ValueError(
            f"A* grid would contain {columns * rows:,} cells; increase grid_cell_size "
            f"so it stays at or below {MAX_ASTAR_CELLS:,} cells"
        )

    blockers = tuple(other_agents)
    start_ok, _ = path_is_clear(space, start, start, radius, blockers, active_agent_id)
    goal_ok, _ = path_is_clear(space, goal, goal, radius, blockers, active_agent_id)
    if not start_ok or not goal_ok:
        return None

    def index_for(position: Position) -> tuple[int, int]:
        column = min(columns - 1, max(0, int(position.x / grid_cell_size)))
        row = min(rows - 1, max(0, int(position.y / grid_cell_size)))
        return column, row

    start_index = index_for(start)
    goal_index = index_for(goal)
    centers: dict[tuple[int, int], Position] = {}

    def center(index: tuple[int, int]) -> Position:
        if index not in centers:
            centers[index] = _cell_center(space, index[0], index[1], grid_cell_size)
        return centers[index]

    def clear_point(index: tuple[int, int]) -> bool:
        point = center(index)
        return path_is_clear(space, point, point, radius, blockers, active_agent_id)[0]

    start_center = center(start_index)
    goal_center = center(goal_index)
    if not path_is_clear(space, start, start_center, radius, blockers, active_agent_id)[0]:
        return None
    if not path_is_clear(space, goal_center, goal, radius, blockers, active_agent_id)[0]:
        return None

    if start_index == goal_index:
        return (start, goal) if path_is_clear(space, start, goal, radius, blockers, active_agent_id)[0] else None

    directions = (
        (-1, -1, sqrt(2.0)), (0, -1, 1.0), (1, -1, sqrt(2.0)),
        (-1, 0, 1.0),                         (1, 0, 1.0),
        (-1, 1, sqrt(2.0)),  (0, 1, 1.0),  (1, 1, sqrt(2.0)),
    )

    def heuristic(index: tuple[int, int]) -> float:
        dx = abs(index[0] - goal_index[0])
        dy = abs(index[1] - goal_index[1])
        return max(dx, dy) + (sqrt(2.0) - 1.0) * min(dx, dy)

    open_heap: list[tuple[float, float, int, int]] = []
    heappush(open_heap, (heuristic(start_index), 0.0, start_index[1], start_index[0]))
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score = {start_index: 0.0}
    closed: set[tuple[int, int]] = set()

    while open_heap:
        _, current_cost, row, column = heappop(open_heap)
        current = (column, row)
        if current in closed or current_cost > g_score.get(current, inf) + _EPSILON:
            continue
        if current == goal_index:
            break
        closed.add(current)

        for dx, dy, cost in directions:
            neighbour = (column + dx, row + dy)
            nx, ny = neighbour
            if not (0 <= nx < columns and 0 <= ny < rows) or neighbour in closed:
                continue
            if not clear_point(neighbour):
                continue
            if dx and dy:
                horizontal = (column + dx, row)
                vertical = (column, row + dy)
                if not clear_point(horizontal) or not clear_point(vertical):
                    continue
            if not path_is_clear(space, center(current), center(neighbour), radius, blockers, active_agent_id)[0]:
                continue
            tentative = current_cost + cost
            if tentative + _EPSILON >= g_score.get(neighbour, inf):
                continue
            came_from[neighbour] = current
            g_score[neighbour] = tentative
            heappush(open_heap, (tentative + heuristic(neighbour), tentative, ny, nx))

    if goal_index not in came_from:
        return None
    indices = [goal_index]
    while indices[-1] != start_index:
        indices.append(came_from[indices[-1]])
    indices.reverse()
    route = [start]
    route.extend(center(index) for index in indices)
    route.append(goal)

    compact: list[Position] = []
    for point in route:
        if not compact or hypot(point.x - compact[-1].x, point.y - compact[-1].y) > _EPSILON:
            compact.append(point)
    for left, right in zip(compact, compact[1:]):
        if not path_is_clear(space, left, right, radius, blockers, active_agent_id)[0]:
            return None
    return tuple(compact)


def advance_along_path(path: tuple[Position, ...], distance: float) -> tuple[Position, tuple[Position, ...]]:
    """Advance a bounded distance along a polyline and return the travelled path."""
    if not path:
        raise ValueError("path cannot be empty")
    if distance <= 0:
        return path[0], (path[0],)
    remaining = distance
    travelled = [path[0]]
    current = path[0]
    for waypoint in path[1:]:
        segment = hypot(waypoint.x - current.x, waypoint.y - current.y)
        if segment <= _EPSILON:
            current = waypoint
            continue
        if remaining >= segment - _EPSILON:
            travelled.append(waypoint)
            current = waypoint
            remaining -= segment
            if remaining <= _EPSILON:
                break
        else:
            ratio = remaining / segment
            current = Position(
                current.x + (waypoint.x - current.x) * ratio,
                current.y + (waypoint.y - current.y) * ratio,
            )
            travelled.append(current)
            remaining = 0.0
            break
    return current, tuple(travelled)
