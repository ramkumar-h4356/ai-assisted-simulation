# Milestone 18 Report — Spatial Environment and Environment-Aware Navigation

## Outcome

M18 extends the M17 spatial ABM engine with a typed spatial environment layer and environment-aware navigation. The work was applied to the M17 project archive as a full-project update, retaining the existing collision, movement-budget, A*, movement-event and replay contracts.

## Delivered capabilities

- Added `GridSpec` with deterministic world-coordinate-to-cell lookup, clipped edge-cell bounds and cell-centre calculations.
- Added polygonal `SpatialRegion` definitions with attributes and tags.
- Added polygonal `SpatialZone` definitions supporting impassable terrain and navigation-cost multipliers.
- Added `EnvironmentalObject` definitions with optional circular footprints, tags, attributes and blocking behavior.
- Added strict schema parsing and model validation for M18 environment data, including shared ID uniqueness, polygon validity and world bounds.
- Added spatial hash `SpatialIndex` with insert, move, remove, radius query and rectangle query operations.
- Integrated the index into live `SpatialNeighbourStateCount` evaluation, including updates after committed movement and periodic lookup for wrapped worlds.
- Extended M17 segment clearance to block impassable zones and blocking environmental objects.
- Extended A* to prefer lower-cost terrain while preserving deterministic tie-breaking and the 100,000-cell safety limit.
- Added the `spatial_environment_navigation_m18.json` example and dedicated M18 tests.
- Incremented the local web API version from `17.0.0` to `18.0.0`.

## New and updated files

- `simulations/abm/environment.py`
- `simulations/abm/model.py`
- `simulations/abm/schema.py`
- `simulations/abm/spatial.py`
- `simulations/abm/engine.py`
- `simulations/abm/__init__.py`
- `tests/abm/test_environment_m18.py`
- `scenarios/spatial_environment_navigation_m18.json`
- `M18_ARCHITECTURE.md`
- `M18_TEST_REPORT.md`
- `M18_APPLY_STEPS.txt`
- Updated root and ABM READMEs, project structure, and web API version assertions.

## Explicit exclusions

The milestone does not add polygon collision obstacles, dynamic environment/object updates, environmental interaction action types, continuous environmental fields, wrap-world A*, simultaneous movement, continuous-time physics, or a redesigned browser UI. The current browser replay still consumes the existing trace format; rendering M18 zones and objects as editable UI layers is deferred to a later UI milestone.

## Verification status

The M18 ABM tests and all non-DES tests passed in the build environment. The full test command could not collect the DES suite because this build container did not have the declared `simpy` and `groq` dependencies installed. The Windows project environment should run the complete suite after applying the archive.
