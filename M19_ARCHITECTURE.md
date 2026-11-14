# M19 Architecture — Discrete-Event Simulation Replay

## Goal

M19 turns the existing DES event log into a deterministic, inspectable replay projection. It exposes the chronological event timeline, each entity's ordered service journey, waiting and service intervals, resource occupancy, queue lengths and utilization. The projection is read-only: it does not modify SimPy scheduling, event order, or simulation outcomes.

## Existing execution contract retained

The DES runtime continues to record the canonical event types:

- `arrived`: an entity reaches a service stage and requests its resource;
- `service_started`: the entity obtains the resource;
- `service_completed`: the entity finishes that service stage.

Each event still contains simulation time, entity ID, event type and resource name. M19 does not add a new scheduler or inject replay events into the running simulation.

## Components

### `simulations/des/replay.py`

`build_des_replay(events, resource_capacities=...)` validates the event log and produces a JSON-compatible document containing:

- `timeline`: one stable record per canonical event, with a zero-based sequence number;
- `entities`: each completed entity's arrival/completion, total waiting/service/time-in-system, and ordered stage-level timings;
- `resources`: configured capacity, resource-time busy total, normalized utilization percentage, peak concurrent use, stage-level wait intervals, queue-length intervals, peak queue length, and occupancy intervals;
- `summary`: run horizon, event/entity/resource counts and aggregate entity timings.

Equal-time events retain their input order. Non-chronological events, incomplete stage sequences, invalid capacities, negative/non-finite timestamps and capacity overuse are rejected rather than silently corrected. Zero-duration service is supported: simultaneous start/completion deltas are aggregated at the timestamp so the replay does not invent negative occupancy.

Utilization is `busy_time / (observed_system_duration × resource_capacity) × 100`. `busy_time` is resource-time, so two servers occupied for four time units contribute eight busy resource-time units. The observed horizon begins at the first entity arrival and ends at the last entity completion; warm-up/cool-down exclusions are not inferred.

### Inspection helpers

- `query_des_events(...)` filters by entity, resource, event type and inclusive time bounds while preserving event sequence.
- `get_des_event(replay, sequence)` retrieves one timeline record.
- `get_entity_journey(replay, entity_id)` retrieves an entity and all its ordered stages.
- `get_resource_replay(replay, resource_name)` retrieves queue and occupancy history.

Inspection helpers return copies, so editing a returned object does not mutate the replay source.

### `simulations/des/backend.py`

`ScenarioResult` now retains configured resource capacities alongside its existing canonical event log. The new field has an empty-tuple default to preserve older direct construction patterns. `run_scenario` fills it from the engine configuration.

### `execution/runner.py`

M9 trace capture now includes a derived `replay` projection and `resource_capacities` mapping for DES runs. Existing top-level `events`, `entities` and `resources` trace fields remain present. The result's normal SHA-256 fingerprint covers the new replay data. The DES trace-record estimate was increased to budget for the additional timeline, entity stages, queue intervals and occupancy segments.

### `simulation_studio/des_replay.py`

`build_des_run_replay(result, compilation, run_index=...)` rebuilds a selected replay from a saved M9 result. It verifies both fingerprints, M8/M9 artifact and project/revision lineage, successful run status, the canonical event log, and consistency between the persisted M19 projection and a fresh projection. It supports older M9 DES result files by deriving resource capacities from the linked M8 model when the old trace did not store them.

## Data flow

```text
M8 DES compilation artifact
          |
          v
M9 SimPy execution
          |
          +--> canonical ordered SimulationEvent log
          +--> existing entity/resource metrics
          +--> configured resource capacities
                    |
                    v
          build_des_replay (M19)
                    |
          +---------+----------+-------------+
          |                    |             |
       timeline            journeys      queues/resources
          |                    |             |
          +---------- inspection helpers ----+
                    |
                    v
          fingerprinted M9 result JSON
                    |
                    v
       provenance-checked saved-run replay
```

## Backward compatibility

- SimPy scheduling and the three canonical event types are unchanged.
- Existing M9 trace keys (`events`, `entities`, `resources`) remain unchanged.
- `ScenarioResult.resource_capacities` has a default, so old constructors using the prior fields continue to work.
- Old M9 result files without the M19 replay or capacity mapping can still be replayed when linked to the original M8 compilation artifact.
- ABM replay and M15–M18 spatial functionality are untouched.

## Example

`scenarios/des/two_stage_clinic_replay.json` contains a two-stage, three-patient scenario with intentional queueing. It can be parsed with `scenario_from_json`, executed with `run_scenario`, and passed to `build_des_replay` using the scenario resource capacities. It demonstrates entity movement from registration to consultation, queue waiting and resource occupancy.

## Explicit limitations

- Replay is post-run, not live streaming, pausing, stepping or time-travel editing.
- The runtime currently records only arrival, service-start and service-completion events. Cancellation, reneging, preemption, breakdown, repair and arbitrary user-defined events are not represented.
- A replay requires a completed, internally consistent entity stage sequence. Failed or partial DES runs are not visualized by this API.
- Queue intervals are derived from arrival-to-service-start gaps; SimPy's internal request queue position and ordering metadata are not persisted separately.
- Utilization uses the complete observed simulation horizon and does not infer warm-up periods or scheduled availability windows.
- This milestone supplies structured replay data and inspection functions, not the redesigned browser UI or animated 2D rendering.

## Verification boundary

The projection validates internal trace consistency and resource capacity. It does not prove that the conceptual model is empirically valid or that its assumptions match a real system. M19 is a trace inspection and observability capability, not scientific validation.
