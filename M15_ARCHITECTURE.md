# M15 Architecture — Interactive ABM 2D State Replay

## Goal

M15 adds an interactive browser replay for recorded ABM V1 executions. It turns the existing M9 agent snapshots and rule-evaluation trace into a step-by-step 2D view without changing the ABM engine, M8 compilation contract, or stored M9 result.

## Data path

```text
Workspace artifact ledger
        |
        +-- integrity-verified M9 execution_result
        |        |
        |        +-- strict M9 JSON load + result fingerprint check
        |        +-- selected completed run
        |        +-- per-step agent snapshots and rule evaluations
        |
        +-- exact linked M8 compilation_artifact
                 |
                 +-- workspace SHA-256 check
                 +-- M8 artifact fingerprint check
                 +-- normalized ABM model parse
                 +-- agent relationships

             M15 replay scene (JSON response)
                       |
                       v
             Browser canvas + timeline
```

The replay API is:

```text
GET /api/v1/workspaces/{workspace_id}/executions/{artifact_id}/replay?run_index=1
```

`artifact_id` must identify an `execution_result` in the selected workspace. M15 locates the exact M8 compilation artifact by matching the M9 `artifact_id` and `artifact_fingerprint`; it will not use a similarly named or merely same-project specification. Both artifacts pass workspace integrity checks and their own internal fingerprint validation before a scene is built.

## Replay representation

- Each compiled ABM agent is a node. The node set is checked against every recorded snapshot; missing, duplicated or unexpected agents cause replay construction to fail.
- M8 relationships are rendered as labelled edges. Directed edges include arrowheads.
- Every M9 history snapshot becomes a replay frame, including the initial step 0 snapshot.
- Node state is read from the selected frame. The browser assigns a stable display color to each state label.
- Agents whose state or attributes changed from the previous frame receive a transition ring.
- The inspector shows the selected agent's type, state and attributes, and lists the recorded rule evaluations for the current step.
- Playback controls support play/pause, first/previous/next/last, timeline scrubbing and 0.5×/1×/2×/4× speed.

## Spatial and scientific semantics boundary

ABM V1 has explicit agents, scalar attributes, static relationships, sequential activation and fixed-step termination. It does **not** define physical coordinates, movement, collision, distance, neighbourhood radius, or spatial interaction rules.

M15 therefore computes a deterministic circular layout solely to make the agent network readable. These coordinates are presentation metadata, not model variables. Nodes remain in the same display positions while the replay advances; only recorded states and attributes change. The viewer labels this limitation explicitly. It must not be described as a spatially accurate or movement-capable simulation.

DES event playback is not included in M15. A later DES replay can use the existing event trace to render queues, resources and event-time progression, but that is a separate visual adapter.

## Persistence and provenance

M15 creates no new simulation artifact and does not modify M8 or M9 files. The scene is deterministically reconstructed from the verified source artifacts on request. The response carries experiment ID, exact M8 artifact ID, M9 fingerprint, project/revision identifiers, selected run, and seed for traceability.

## Safety and limits

- Unknown workspaces/artifacts return not-found errors.
- Non-M9 artifact IDs and non-ABM execution results are rejected.
- Missing or tampered M9/M8 artifacts are rejected before replay.
- A run must exist and have completed successfully.
- The local-only M14 security boundary remains unchanged; do not expose the server to a network.
- The API returns recorded data, not executable code. The browser uses canvas drawing and text nodes rather than interpreting trace values as HTML.

## Explicit exclusions

M15 does not add spatial coordinates to the ABM schema, movement or collision mechanics, dynamic relationships, simultaneous activation, agent creation/deletion, DES animation, mathematical/data-driven execution, remote hosting, or multi-user collaboration.
