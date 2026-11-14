# M17 Architecture — Advanced Spatial Mechanics

## Goal

M17 extends the M16 spatial ABM engine with static obstacles, body-aware collision handling, per-step movement constraints and deterministic route planning. These are simulation semantics: they determine M9 state transitions and are persisted as execution evidence. M17 does not add a new browser interaction design; the existing M15/M16 browser replay receives the new trace records for later UI refinement.

## Spatial model contract

M16's `space` object is extended with optional geometry and collision settings:

```json
{
  "space": {
    "width": 20,
    "height": 20,
    "boundary": "clamp",
    "agent_collisions": true,
    "collision_resolution": "block",
    "obstacles": [
      {"id": "wall", "type": "rectangle", "x": 8, "y": 3, "width": 2, "height": 12},
      {"id": "rock", "type": "circle", "x": 14, "y": 5, "radius": 1}
    ]
  },
  "agents": [
    {
      "reference": "walker",
      "agent_type": "person",
      "state": "active",
      "attributes": {},
      "position": {"x": 2, "y": 10},
      "radius": 0.4,
      "max_step_distance": 2.5
    }
  ]
}
```

- Obstacles are static. Rectangle geometry is axis-aligned and specified by top-left coordinate, positive width and positive height. Circle geometry is specified by centre and positive radius. IDs must be unique and all obstacle geometry must fit within the declared world.
- `Agent.radius` is the circular body radius in model-defined units. It defaults to zero, preserving earlier point-agent models.
- `Agent.max_step_distance` is optional. When specified, it is a cumulative movement budget for that agent over one ABM step, shared by all successful movement actions. It resets at the beginning of the next step.
- `space.agent_collisions` defaults to `true`; it controls agent-agent body collision checks. Agent bodies are circles and overlap is rejected during initial validation or movement.
- `space.collision_resolution` is `block` or `slide`, defaulting to `block`. Slide resolution is deterministic: try X movement first, then Y movement. It is not a physical friction or impulse solver.

## Declarative movement actions

Existing actions remain supported:

- `move_by`: request a relative displacement.
- `move_to`: request an absolute destination. Without a movement budget this retains its immediate-destination semantics, but the direct segment is checked for collisions before the destination is committed. With a per-step movement budget, it advances only as far as the remaining budget permits.

New bounded action:

```json
{"type": "move_towards", "x": 18, "y": 10,
 "max_distance": 2.5, "pathfinding": "astar", "grid_cell_size": 1}
```

- `pathfinding: "direct"` follows a straight segment and obeys the same collision policy.
- `pathfinding: "astar"` computes a deterministic 8-connected grid route. Diagonal corner-cutting is prevented. Each route edge is checked against the continuous collision geometry before acceptance.
- `grid_cell_size` defines grid resolution; a smaller cell may resolve narrower passages but increases search work.
- A* currently requires clamp boundaries and has a hard safety limit of 100,000 grid cells. A* treats other collidable agents at their current positions as blocked cells/segments. It recomputes the route when the action executes; it does not maintain a long-lived navigation plan.

## Collision and geometry semantics

- Circular agent bodies are checked against circular obstacles using centre-to-segment distance.
- Rectangular obstacles use a conservatively expanded AABB for circular agent bodies. This prevents corner penetration but can reject some routes that would fit around a rounded rectangle corner under exact geometry.
- Agent-agent collision uses the sum of body radii and the shortest wrapped distance when the world boundary is `wrap`.
- Movement is checked along the full requested segment or route, not just at its endpoint, preventing tunnelling through supported static obstacles and stationary agents.
- Tangential contact between circles is allowed; penetration is blocked. Rectangle segment tests are conservative and include contact with the expanded AABB.
- Direct movement in wrap worlds checks periodic obstacle/agent copies along the unwrapped movement segment. A* is not supported with wrap boundaries.

## Execution and update order

ABM activation remains sequential in agent declaration order, and rules remain in declaration order. Each successful rule commits its state, attributes and movement together. Later rules and later agents in the same step observe earlier committed positions. A rule action batch remains atomic: if another action in the same rule raises a runtime error, the state, attributes, position, movement budget and movement events from that rule are not committed.

The `max_step_distance` budget is cumulative within the step. If a movement action requests more distance than remains, the action advances only the remaining distance and marks `distance_limit_reached` in its movement event.

## Movement-event trace and M9 integration

Each movement action generates a `MovementEvent` containing:

- step, agent ID, rule ID and action index;
- action type and requested target;
- actual committed position;
- outcome (`moved`, `blocked`, `slid`, `no_path`, or `unchanged`);
- optional blocker/no-path reason;
- traversed waypoints and distance travelled;
- whether a movement-distance limit was reached.

M9 serializes these events inside each ABM run trace. M15/M16 replay validates the event schema and, for clamp worlds, verifies that the last movement event for an agent in a step agrees with the final recorded position. Replay frames expose the step's movement events so a future user-facing UI can inspect actual engine outcomes.

The M9 trace-size estimator includes the maximum number of movement action records. It does not estimate every nested A* waypoint individually; A* cell and grid limits constrain route planning.

## Component flow

```text
M8 ABM model/profile
      |
      v
Strict schema parser
      |
      v
Typed SpatialSpace + obstacles + agent bodies + movement actions
      |
      v
Semantic validation (initial geometry, bodies, movement budget, A* limits)
      |
      v
Sequential ABM engine
      |-- collision/segment checks
      |-- deterministic block/slide response
      |-- bounded movement budget
      |-- direct/A* navigation
      v
Snapshots + trajectories + MovementEvent trace
      |
      v
M9 persisted execution result + lineage/fingerprint
      |
      v
M15/M16 replay validation + step movement-event details
```

## Backward compatibility

- `space.obstacles`, `agent_collisions`, and `collision_resolution` are optional; old M16 spatial JSON remains valid.
- Agent `radius` defaults to zero and `max_step_distance` defaults to `null`.
- Non-spatial ABM models are unchanged.
- Historical M9 traces without `radius` or `movement_events` remain replayable; missing radius is interpreted as the historical zero-radius body and missing events as an empty trace.
- The web API version is `17.0.0`.

## Explicit exclusions

M17 does not implement polygon obstacles, moving obstacles, physical forces, velocity/acceleration, friction, impulse-based multi-agent collision resolution, simultaneous activation, agent births/deaths, continuous-time movement, wrapped-world A*, or DES visual replay. A* is a grid approximation and may miss narrow corridors at coarse resolution. Rectangle clearance is intentionally conservative near corners. The browser UI is not redesigned in this milestone.
