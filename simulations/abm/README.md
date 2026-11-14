# Agent-Based Modelling — ABM V1 plus M16 spatial extension

This package provides a declarative ABM model, deterministic validation, a
sequential execution engine, a shared backend adapter, and an AI-assisted
natural-language construction pipeline. M16 adds optional 2D spatial semantics
without changing existing non-spatial ABM model files.

## Model concepts

- **Agent** — an individual entity with an identifier, type, state, scalar attributes, and an optional 2D position.
- **Environment** — global scalar attributes retained as model context.
- **SpatialSpace** — optional width/height coordinate domain with `clamp` or `wrap` boundary handling.
- **AgentRelationship** — a static directed or undirected connection between two agents.
- **BehaviourRule** — a condition, ordered actions, optional agent-type filter, and execution probability.
- **ActivationPolicy** — sequential activation in agent declaration order.
- **MaxSteps** — fixed positive simulation horizon.

Non-spatial models remain valid as before. When `space` is present, every agent must have an initial `position`.

## M16 spatial schema

A spatial model adds a `space` object and a position for each agent:

```json
{
  "space": {"width": 100, "height": 100, "boundary": "clamp"},
  "agents": [
    {"reference": "a", "agent_type": "person", "state": "active",
     "attributes": {}, "position": {"x": 10, "y": 10}}
  ]
}
```

`width` and `height` must be positive finite numbers. `boundary` is `clamp` by default or `wrap`:

- `clamp`: positions stay in the closed rectangle `[0,width] × [0,height]`.
- `wrap`: positions wrap modulo width and height; the coordinate domain is half-open `[0,width) × [0,height)`.

Coordinates use model-defined units with the origin at the top-left, x increasing to the right and y increasing downward. The engine does not assign metres, kilometres, pixels, or other physical units unless the model documents them.

## Supported conditions

- `AgentStateIs`: compare the active agent's state.
- `AgentAttributeComparison`: compare one active-agent scalar attribute.
- `RelatedAgentStateCount`: count connected agents by state and relationship type, respecting directed/undirected links.
- `SpatialNeighbourStateCount`: count *other* agents with a specified state within an inclusive Euclidean radius of the active agent.
- `AllOf` and `AnyOf`: combine nested conditions.

A wrapped space uses shortest periodic distance across opposite edges. Spatial conditions use current runtime positions. The active agent is excluded from its own neighbourhood count.

## Supported actions

- `SetState`: replace the active agent's state.
- `SetAttribute`: add or replace a scalar agent attribute.
- `IncrementAttribute`: increment an existing numeric attribute.
- `MoveBy`: apply a relative `{ "dx": number, "dy": number }` displacement.
- `MoveTo`: move to an absolute `{ "x": number, "y": number }` coordinate.

Movement requires a configured `space` and an initial coordinate for every agent. Boundary policy is applied after each movement action. Actions in one rule remain atomic: a failed later action does not partially commit an earlier movement or attribute update from that same rule.

## Execution semantics

`AgentBasedSimulationEngine.run(model)` validates the model before execution.

1. The result records the initial population as step `0`.
2. Each step activates agents in declaration order; rules execute in behaviour declaration order.
3. Successful actions commit immediately. Later rules and later agents in that step observe earlier state, attribute, and position changes.
4. Spatial neighbourhood membership is evaluated at the instant the condition is checked, not from a stale step-start index.
5. For spatial models, each history snapshot records every agent's position as well as state and attributes.
6. Probabilities `0` and `1` are deterministic; intermediate probabilities use the model's seeded random generator.
7. The model runs for exactly the configured `MaxSteps` unless a runtime error occurs.

Simultaneous activation, random activation order, dynamic relationships, environment mutation, collision geometry, velocity/acceleration physics, obstacle avoidance, and early-stop conditions are not implemented by M16.

## AI model-construction pipeline

`run_agent_prompt(request, ...)` asks Groq for a declarative model, normalizes internal aliases, parses typed objects, asks for clarification where validation identifies missing facts, validates, and executes only valid models. The AI may use spatial fields only when the user's scenario explicitly describes a spatial world. It must not invent world dimensions, coordinates, units, or boundary policies. Missing spatial facts are retained as clarification needs.

The interpreter cannot generate Python functions, callbacks, code snippets, or arbitrary expressions.

## Results, provenance, and replay

`ABMSimulationResult` contains step snapshots, rule evaluations, final state counts, and per-agent trajectories. For spatial models, snapshots and trajectories also include coordinates.

M9 persists coordinates in its trace. M16's 2D replay uses those recorded coordinates for spatial models and retains M15's deterministic network layout for non-spatial models. The replay is a rendering of engine-produced data, not a second movement simulator. M8/M9 fingerprint and lineage checks remain in force.

## Examples

- `scenarios/disease_transmission_abm.json` — non-spatial network example.
- `scenarios/spatial_neighbour_movement_abm.json` — moving beacon and radius-based awareness example.


## M17 advanced spatial mechanics

M17 extends spatial ABM with explicit static geometry, collision-aware movement, per-agent
movement budgets and deterministic route planning. It is an engine feature: collision checks
and pathfinding determine recorded simulation positions, not merely the browser display.

A spatial world can declare rectangular and circular obstacles:

```json
{
  "space": {
    "width": 20,
    "height": 20,
    "boundary": "clamp",
    "obstacles": [
      {"id": "wall", "type": "rectangle", "x": 8, "y": 3, "width": 2, "height": 12},
      {"id": "rock", "type": "circle", "x": 14, "y": 5, "radius": 1}
    ],
    "agent_collisions": true,
    "collision_resolution": "block"
  },
  "agents": [
    {"reference": "walker", "agent_type": "person", "state": "active",
     "attributes": {}, "position": {"x": 2, "y": 10},
     "radius": 0.4, "max_step_distance": 2.5}
  ]
}
```

- `rectangle` obstacles are axis-aligned boxes defined by their top-left coordinate and positive width/height.
- `circle` obstacles are defined by centre and positive/non-negative radius.
- Obstacle identifiers must be unique and geometry must lie inside the declared world.
- `agent_collisions` enables circular agent-body overlap prevention. A zero-radius agent is a point body; non-zero radii participate in collision checks.
- `collision_resolution` is `block` or deterministic `slide`. Slide tries the X axis first, then Y; it never teleports through an obstruction.
- `max_step_distance` is an optional cumulative movement budget per agent per simulation step. All movement actions in that step share it.
- Existing `move_by` and `move_to` become collision-aware when used in an M17 spatial world. `move_to` remains an immediate destination request unless a movement budget limits it.
- `move_towards` advances toward a target by a bounded distance. `pathfinding: "direct"` requests a straight route; `pathfinding: "astar"` computes an 8-connected grid route with corner-cutting prevention. `grid_cell_size` controls route resolution.
- A* currently requires `clamp` boundaries and is limited to 100,000 cells. Narrow passages may require a smaller cell size, at greater computational cost.
- M9 traces record requested target, actual destination, collision/path outcome, travelled distance and traversed waypoints. M15 replay carries those events forward with the exact M8/M9 lineage.

Collision detection uses circular agent bodies. Rectangle collision tests use a conservative expanded axis-aligned box around the rectangle, so clearance near rectangle corners may be stricter than exact circle/rectangle geometry. Movement is sequential under the existing declaration-order activation policy. Earlier agents' committed positions block later agents in the same step. Simultaneous collision resolution, moving obstacles, polygon geometry, continuous-time physics and globally optimal continuous path planning remain out of scope.
