# Discrete-Event Simulation (DES)

The DES package provides the scenario model, strict schema/parser, SimPy runtime and backend adapter. The runtime records canonical `arrived`, `service_started` and `service_completed` events. M19 adds a deterministic replay projection over those events without changing the simulation scheduler.

## Build and inspect a replay

```python
from simulations.des.backend import run_scenario
from simulations.des.replay import (
    build_des_replay,
    get_entity_journey,
    get_resource_replay,
    query_des_events,
)
from pathlib import Path
from simulations.des.schema import scenario_from_json

scenario_path = Path("scenarios/des/two_stage_clinic_replay.json")
scenario = scenario_from_json(scenario_path.read_text(encoding="utf-8"))
result = run_scenario(scenario)
replay = build_des_replay(
    result.events,
    resource_capacities=dict(result.resource_capacities),
)

patient = get_entity_journey(replay, "Patient-C")
registration = get_resource_replay(replay, "Registration")
service_starts = query_des_events(replay, event_type="service_started")
```

The replay contains a stable `timeline`, complete entity-stage journeys, resource occupancy and queue intervals, and aggregate timing summaries. Query helpers preserve event order and return copies of the selected records.

For an end-to-end console example, run:

```powershell
python -m simulations.des.replay_demo
```

## Saved M9 results

M9 now persists the DES replay projection and resource capacities in each successful DES run trace. To rebuild a replay from a saved `ExperimentResult`, linked with its exact M8 `CompilationArtifact`:

```python
from simulation_studio import build_des_run_replay

replay = build_des_run_replay(experiment_result, compilation_artifact, run_index=1)
```

This helper validates the artifact/result fingerprints and project/revision lineage before reconstructing the replay from the canonical event log. See `M19_ARCHITECTURE.md` for the full data contract and limitations.

Replay is post-run. It does not add live streaming, playback controls, cancellation, preemption or arbitrary event types.
