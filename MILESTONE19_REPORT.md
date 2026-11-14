# Milestone 19 Report — Discrete-Event Simulation Replay

## Delivered

M19 adds a read-only replay layer to the DES execution path. It turns M9's canonical arrival/service-start/service-completion event log into a chronological timeline, per-entity multi-stage journeys, resource occupancy intervals, queue intervals and queue-length history. It also provides inspection helpers to query events and retrieve one entity's journey or one resource's history.

M9 trace capture now persists the replay projection and exact configured resource capacities for DES runs. The experiment result fingerprint therefore covers these replay details. A saved-run helper rechecks the M8 compilation fingerprint, M9 result fingerprint, project and conceptual-revision lineage, run completion status, and consistency of the cached projection against the canonical event log. Pre-M19 saved DES results remain replayable by reading resource capacities from their linked M8 model artifact.

A bundled two-stage clinic queue scenario demonstrates how three patients move from registration to consultation and how waits and resource utilization can be inspected.

## Key engineering decisions

- Replay is derived from the recorded event log; no scheduler changes or replay-side simulation.
- Stable event sequence numbers preserve equal-time event order.
- Resource utilization accounts for configured capacity and the observed system horizon.
- Same-timestamp service deltas are aggregated to handle zero-duration work safely.
- Replay inspection returns copies to keep the source replay immutable from the caller's perspective.
- The DES trace estimate now accounts for duplicated replay timelines, entity stages, queue intervals and occupancy segments.

## Verification performed in the build container

- `python -m pytest -q tests/des/test_replay.py tests/simulation_studio/test_des_replay.py`
- Result: **20 passed** (pure replay, trace-capture and synthetic saved-run provenance tests).

The build container lacks the optional `simpy` package and has no network access to install it. Accordingly, this report does not claim that the complete DES execution integration or full project suite passed here. The user's M18 Windows environment has SimPy and previously passed 578 tests; M19 must be verified there using `M19_APPLY_STEPS.txt` before commit.

## Non-goals

M19 does not add live event streaming, play/pause/step controls, event types beyond arrival/start/completion, cancellation or preemption semantics, animated UI components, or scientific validation. The UI redesign remains deferred.
