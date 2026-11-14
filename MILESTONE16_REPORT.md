# Milestone 16 — Spatial ABM

## Objective

Move the ABM 2D experience from M15's deterministic display layout to a real, trace-backed spatial model. Spatial coordinates and interactions must affect the simulation engine; the browser must render the engine's recorded positions rather than invent movement.

## Delivered

1. Optional 2D `space` with positive finite `width`, `height`, and `clamp` or `wrap` boundary handling.
2. Per-agent initial `position` coordinates, with strict requirements and bounds validation.
3. `move_by` and `move_to` declarative actions.
4. `spatial_neighbour_state_count` condition using inclusive Euclidean radius; wrapped worlds use shortest periodic distance.
5. Explicit sequential update semantics: later agents observe earlier agents' committed movements in the same step.
6. Atomic per-rule application for state, attributes and movement.
7. Spatial coordinates in ABM snapshots, trajectories and M9 trace records.
8. Replay validation for spatial positions and initial M8/M9 agreement, plus model-space visualization in the browser.
9. Natural-language construction prompt/clarification guidance that requires user-supplied spatial dimensions, coordinates, units and boundary choices instead of inventing them.
10. A runnable spatial example at `scenarios/spatial_neighbour_movement_abm.json`.

## Example behaviour

The example uses a 100 × 100 clamp-bounded world. A beacon begins at `(10, 50)` and moves east by two model units per step. A person at `(16, 50)` becomes aware when the beacon is within radius five; a distant person at `(80, 50)` remains unaware. The engine run was manually exercised and produced the expected coordinate/state progression through five steps.

## Boundaries of the milestone

The milestone adds spatial coordinates and neighbourhood semantics, not physical dynamics. There are no collisions, obstacles, velocities, acceleration, simultaneous updates, agent births/deaths or spatial DES behaviours. Model-space units are not assumed to represent metres or another real-world unit.

## Backward compatibility

Non-spatial models do not need a `space` or positions and continue to use the M15 deterministic replay layout. Existing workspace data is not migrated or rewritten. M9 provenance and M15/M16 replay fingerprint checks remain in place.
