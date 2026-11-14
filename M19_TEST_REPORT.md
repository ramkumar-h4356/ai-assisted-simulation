# M19 Test Report — Discrete-Event Simulation Replay

## Scope covered

- Canonical event ordering, sequence numbers and validation.
- Entity journeys with one or multiple service stages.
- Queue wait intervals, queue-length timeline and peak queue length.
- Resource occupancy, capacity enforcement, busy resource-time and utilization.
- Multi-capacity resources and zero-duration service handling.
- Empty runs and configured but idle resources.
- Event filtering, event lookup, entity journey lookup and resource replay lookup.
- M9 trace persistence of replay and capacities.
- Saved-run replay provenance checks, old M9 trace compatibility and cached projection consistency.

## Test modules

- `tests/des/test_replay.py`
- `tests/simulation_studio/test_des_replay.py`

## Build-container result

`python -m pytest -q tests/des/test_replay.py tests/simulation_studio/test_des_replay.py` — **20 passed**.

`python -m compileall -q .` — passed. The bundled two-stage scenario also parsed successfully through the strict DES schema.

Web API regression checks: `python -m pytest -q tests/webapp/test_api.py tests/webapp/test_spatial_api.py` — **4 passed** (including the M19 API version update).

## Environment note

The build container used to assemble M19 does not currently have the optional
`simpy` and `groq` packages installed. Pure replay-projection tests, synthetic
M9 trace capture and saved-run provenance tests can be run without SimPy. A live
SimPy scenario execution and the complete suite must be verified in the project's
configured Windows virtual environment where the user's M18 suite passed. No full-suite pass is claimed by this report.

## Required Windows verification

```powershell
python -m pytest -q tests/des/test_replay.py
python -m pytest -q tests/simulation_studio/test_des_replay.py
python -m pytest -q
```

The M19 package is ready for local verification. It should not be committed
until those commands pass in the project environment.
