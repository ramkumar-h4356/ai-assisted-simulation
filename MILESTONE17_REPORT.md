# Milestone 17 — Advanced Spatial Mechanics

## Objective

Deliver actual spatial-engine mechanics after M16 coordinates and neighbourhood rules: obstacle geometry, body-aware collision handling, movement limits and obstacle-aware navigation. Preserve sequential ABM semantics, M9 provenance and M15/M16 replay compatibility.

## Delivered

1. Added typed rectangle and circle obstacle models, with strict geometry and identifier validation.
2. Added optional circular agent body radius and per-agent cumulative maximum travel distance per simulation step.
3. Added configurable agent-agent collision checks and `block`/deterministic `slide` collision response.
4. Made `move_by` and `move_to` collision-aware along their complete movement segment, not just at the endpoint.
5. Added bounded `move_towards` action with direct routing or deterministic A* routing.
6. Implemented 8-connected A* with diagonal corner-cutting prevention, continuous segment clearance checks, a clamp-boundary requirement and a 100,000-cell safety limit.
7. Added wrap-aware direct movement collision checks using periodic obstacle/agent copies. A* remains clamp-only.
8. Added immutable movement-event records and persisted them into M9 ABM run traces.
9. Extended M15/M16 replay validation and frame data to carry movement events and collision geometry metadata.
10. Extended M9 trace-size estimation for movement action records and updated the ABM natural-language interpreter schema guidance.
11. Added a full obstacle navigation scenario at `scenarios/spatial_obstacles_pathfinding_abm.json`.

## Included scenario result

The example places one navigator at `(2, 10)` in a 20 × 20 world. A rectangular wall blocks the direct route, and a circular rock adds another static obstacle. The navigator has radius `0.4`, a per-step travel budget of `2.5`, and uses A* with cell size `1` to reach `(18, 10)`. The deterministic run completed 12 steps, reached `(18, 10)`, and recorded 12 movement events.

## Verification in the build environment

- M17 advanced spatial tests: 16 passed.
- ABM + execution + replay + web API focused suite: 199 passed.
- Non-DES regression suite: 440 passed, 1 non-fatal warning.
- Python `compileall`: passed.
- Browser JavaScript syntax check (`node --check webapp/static/app.js`): passed.
- Included obstacle-navigation scenario: passed, final coordinate `(18, 10)` with 12 movement events.
- Full suite: not collected in the build environment because the environment does not have `simpy` or `groq`; the package index could not be reached to install them. Run the complete suite on the Windows project environment where those dependencies are already installed.

## Verification still required on the user's Windows environment

Run the targeted and full commands in `M17_APPLY_STEPS.txt`. M17 is packaged and build-tested, but it is not labelled Windows-verified until those tests pass locally.

## Known limitations

- Rectangle collision uses a conservative expanded AABB around corners.
- Agent bodies are circles; arbitrary polygons and non-circular shapes are not supported.
- Block rejects the movement action as a whole; slide tries X then Y. Neither mode is a physical contact/impulse solver.
- A* uses an 8-connected grid and requires clamp boundaries. Narrow corridors may need a finer grid. It is capped at 100,000 cells.
- Other agents are treated as stationary blockers while the active agent plans and moves. Sequential declaration-order activation is unchanged.
- No simultaneous collision solver, moving obstacles, velocity/acceleration, continuous physics, or DES visualization is included.
- The browser UI is intentionally unchanged pending the later user-centred interface milestone.
