# M18 Architecture — Spatial Environment and Environment-Aware Navigation

## Goal

M18 extends M17's collision-aware spatial ABM with a reusable environment description. It adds grid-coordinate helpers, polygon regions and navigation zones, positioned environmental objects, spatial hashing for neighbourhood queries, and weighted/blocked-terrain routing. M18 remains a backend capability milestone; it does not redesign the browser UI.

## Spatial-space contract

The existing `space` contract remains valid. M18 adds four optional fields:

```json
{
  "space": {
    "width": 100,
    "height": 80,
    "boundary": "clamp",
    "grid": {"cell_size": 2},
    "regions": [
      {
        "id": "park",
        "polygon": [
          {"x": 0, "y": 0}, {"x": 40, "y": 0},
          {"x": 40, "y": 30}, {"x": 0, "y": 30}
        ],
        "attributes": {"access": "public"},
        "tags": ["green-space"]
      }
    ],
    "zones": [
      {
        "id": "mud",
        "polygon": [
          {"x": 45, "y": 20}, {"x": 60, "y": 20},
          {"x": 60, "y": 40}, {"x": 45, "y": 40}
        ],
        "passable": true,
        "navigation_cost": 3.0,
        "tags": ["rough-terrain"]
      }
    ],
    "objects": [
      {
        "id": "tree",
        "position": {"x": 20, "y": 20},
        "radius": 1,
        "blocks_movement": true,
        "attributes": {"species": "oak"},
        "tags": ["tree"]
      }
    ]
  }
}
```

### GridSpec

- `space.grid.cell_size` must be positive and finite.
- The grid is a uniform square grid with origin `(0, 0)`.
- Column and row counts use ceiling division, so a partial last cell is retained at the right/bottom world edge.
- `GridSpec.cell_for`, `cell_bounds`, and `cell_center` expose deterministic coordinate conversion; a world-edge coordinate maps to the final valid cell for clamp worlds.
- The grid does not discretize or quantize agent coordinates. The simulation continues to store continuous `Position` values.
- `space.grid.cell_size` also selects the spatial-hash bucket size used by the engine. It does not override `move_towards.grid_cell_size`, which remains the A* search resolution.

### Regions

`SpatialRegion` is a named-by-ID simple polygon with optional JSON-compatible scalar attributes and string tags. Regions support semantic grouping and point queries through `regions_at`. They do not alter movement or behaviour automatically.

### Navigation zones

`SpatialZone` is a simple polygon with:

- `passable`: `true` by default; `false` blocks movement and route planning.
- `navigation_cost`: a finite multiplier greater than or equal to `1.0`; the default is `1.0`.
- optional string tags.

Polygon boundaries count as inside. A segment that crosses or touches an impassable zone is blocked. For non-zero-radius agents, the zone boundary is expanded conservatively by the agent radius when testing a movement segment. When passable zones overlap, their navigation-cost multipliers are multiplied. A* applies the destination cell's effective cost to the edge entering that cell. Costs are never below one, so the existing octile heuristic remains admissible.

### Environmental objects

`EnvironmentalObject` is a point-anchored environment entity with scalar attributes and tags. It may have an optional circular footprint (`radius`). When `blocks_movement` is true, a positive radius is mandatory and the object blocks movement using the same circle/segment rule as circular obstacles. Non-blocking objects can represent landmarks, furniture, resources, or other queryable objects. Blocking objects are static during a run.

Region, zone and environmental-object identifiers share one uniqueness namespace. Polygons must have at least three unique adjacent vertices, non-zero area, and no self-intersections. All region and zone vertices and all object footprints must fit within the declared world.

## Spatial indexing

`simulations.abm.environment.SpatialIndex` implements a uniform spatial hash over point positions:

- `add(identifier, position)` inserts a unique item.
- `move(identifier, position)` updates its bucket without rebuilding the index.
- `remove(identifier)` removes an item and returns its last position.
- `query_radius(center, radius)` returns exact-radius matches.
- `query_bounds(min_x, min_y, max_x, max_y)` returns points inside an inclusive rectangle.
- Results are sorted by identifier to make output deterministic.

The implementation uses bucket filtering followed by exact geometric filtering. Very large query windows fall back to scanning stored identifiers instead of iterating through enormous empty bucket ranges.

The ABM engine builds an index for positioned agents once per run. `SpatialNeighbourStateCount` queries this index and then applies the world's distance function; for wrap worlds it queries periodic centre offsets and verifies shortest wrapped distance. When a rule's actions commit a new position, the active agent's index entry is updated before subsequent agents/rules are evaluated. If a rule action batch fails, the active state and spatial index remain unchanged.

## Environment-aware route planning

M17 A* remains an 8-connected, deterministic grid search with diagonal corner-cutting prevention, current-agent collision checks, and final continuous-segment validation. M18 adds:

1. impassable-zone checks to candidate cells and route segments;
2. static blocking-object footprints to the collision checks;
3. multiplicative destination-cell terrain cost to A* edge costs.

A* still requires a clamp-boundary world and remains limited to 100,000 search cells. Its grid resolution comes from the `move_towards` action. It is a discrete planning approximation and does not guarantee a globally optimal continuous route. Coarse cells can miss narrow passages; the final continuous checks prevent accepted paths from crossing the supported blocking geometry.

`move_by`, `move_to`, and direct `move_towards` use the same updated segment-clearance checks. Thus they are blocked by impassable zones and blocking environmental objects even when no A* route is requested. Existing movement-event records continue to report the requested destination, actual position, status/reason, waypoints and distance.

## Schema and validation

The strict ABM JSON parser accepts `grid`, `regions`, `zones`, and `objects` only under `space`. Unknown fields remain errors. The parser converts the data into typed immutable definitions before engine execution. Initial-agent validation reuses M17's path-clearance logic, so an agent cannot start inside a blocking object, an impassable zone, or a pre-existing obstacle.

The new types and query helpers are exported from `simulations.abm`. The web API version is incremented to `18.0.0` to identify this engine/schema revision.

## Component flow

```text
M8/M9 ABM model data
       |
       v
Strict schema parser
       |
       v
SpatialSpace
  |-- GridSpec
  |-- SpatialRegion / SpatialZone
  |-- EnvironmentalObject
  |-- M17 obstacle and boundary definitions
       |
       +--> Semantic validation (IDs, polygons, bounds, initial positions)
       |
       v
Sequential ABM engine
  |-- SpatialIndex for live agent neighbourhood queries
  |-- movement checks against obstacles, objects and zones
  |-- weighted A* for move_towards
       |
       v
Snapshots + trajectories + MovementEvent trace
       |
       v
M9 persistence and M15/M16 replay lineage
```

## Backward compatibility

- All M16/M17 `space` fields remain unchanged.
- `grid`, `regions`, `zones`, and `objects` are optional and default to empty/no grid.
- A model without `space.grid` still gets a computed spatial-index bucket size; a model without M18 environment elements behaves as in M17.
- Existing `move_towards.grid_cell_size` remains independent and unchanged.
- Non-spatial models are unchanged.
- M9 movement-event structure and replay trace schema are unchanged.

## Explicit limitations

M18 does not add polygon-shaped collision obstacles (blocking environment objects are circular), dynamic environment mutation, movable objects, object-agent interaction actions, environment-dependent behavioural conditions, environmental fields such as continuous temperature/wind, wrap-world A*, simultaneous movement, continuous-time physics, or new 2D rendering controls. Region and zone polygons are static for the duration of one run. The browser workbench is not redesigned in this milestone.
