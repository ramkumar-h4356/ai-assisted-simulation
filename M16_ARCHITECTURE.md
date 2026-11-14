# M16 Architecture — Spatial Agent-Based Modelling

## Goal

M16 adds explicit spatial semantics to ABM V1. It is an engine capability, not a presentation-only coordinate system: world dimensions, initial positions, movement, boundary policies and spatial neighbourhood queries are part of the declarative model and affect deterministic execution. M15 replay consumes the coordinates recorded by M9; it does not independently simulate movement.

## Model contract

Spatial behaviour is opt-in. Existing non-spatial M8 model data remains valid and retains the M15 deterministic display layout.

A spatial M8 model declares:

```json
{
  "space": {"width": 100, "height": 100, "boundary": "clamp"},
  "agents": [
    {
      "reference": "agent-a",
      "agent_type": "person",
      "state": "active",
      "attributes": {},
      "position": {"x": 10, "y": 20}
    }
  ]
}
```

`space.width` and `space.height` are positive finite numbers. Coordinates use model-defined units; the origin is the top-left, x increases rightward and y downward. No physical unit is inferred. A spatial model must give every agent an initial position. Agent positions without a declared space are rejected.

Boundary mode:

- `clamp` (default): coordinates are kept in the closed rectangle `[0,width] × [0,height]`.
- `wrap`: coordinates wrap modulo width and height into `[0,width) × [0,height)`; opposite edges are neighbours for distance calculations.

## Declarative spatial rules

Two actions are supported:

- `move_by` with numeric `dx` and `dy`.
- `move_to` with numeric `x` and `y`.

One condition is supported:

- `spatial_neighbour_state_count` with `radius`, `state`, `operator` and `count`.

Neighbour counts exclude the active agent, include agents exactly on the radius boundary, and use Euclidean distance. In `wrap` spaces, the engine uses the shortest periodic distance on each axis.

Movement actions in a rule are applied to temporary state and committed together with other actions only after the entire rule succeeds. Boundary normalization occurs after each movement action.

## Execution semantics

ABM V1 remains sequential in agent declaration order. Rules run in declaration order for each activated agent. Successful actions are committed immediately; later rules and later agents in the same step see the updated state, attributes and coordinates. This is an intentional asynchronous update policy, not simultaneous activation.

The engine records the initial snapshot and every completed step. Spatial snapshots and per-agent trajectories include coordinates. M9 persists these values in its trace. Replay validates the recorded positions against the linked M8 space and initial positions before building the browser scene.

## Components and data flow

```text
M8 compilation profile
       |
       v
ABM strict schema parser -> typed SpatialSpace / Position / rules
       |
       v
ABM semantic validation
       |
       v
Sequential ABM engine
       |  movement + current-position neighbourhood evaluation
       v
Snapshots / trajectories / rule evaluations
       |
       v
M9 execution result + fingerprints + M8 lineage
       |
       v
M16 replay builder (validates exact M8/M9 provenance and trace)
       |
       v
Browser canvas (draws recorded model-space positions)
```

## Extension points

The `SpatialSpace` type owns coordinate normalization and distance semantics. New spatial conditions/actions should remain declarative typed objects, be parsed by `simulations/abm/schema.py`, checked by `validation.py`, evaluated/applied by `engine.py`, and covered by trace/replay tests. The browser remains a renderer of verified results.

## Explicit exclusions

M16 does not implement simultaneous activation, random activation order, velocity or acceleration, collision geometry, obstacles, path finding, agent births/deaths, moving environment objects, dynamic relationships, continuous-time movement, or DES visualization. Coordinates are abstract model-space units. These features require further model and engine contracts; they must not be simulated only by client-side animation.

## Compatibility

The `space` property and agent positions are optional. Non-spatial model profiles, execution traces, workspaces and M15 replays remain supported. M16 does not rewrite existing workspace artifacts. The web API reports version `16.0.0`.
