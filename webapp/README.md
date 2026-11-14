# M14–M16 Local Browser Workbench

M14 adds a browser-based interface and a versioned HTTP API around the M13 project workspace. M15 adds an interactive, trace-backed 2D replay. M16 adds explicit spatial ABM model semantics and makes the viewer render engine-recorded positions. The application deliberately reuses `WorkspaceManager`, `ProjectWorkspace` and `WorkbenchService`; the web layer does not implement alternate simulation semantics.

## Start

```bash
python -m pip install -r requirements-dev.txt
python -m webapp
```

Open `http://127.0.0.1:8765`. Optional CLI settings:

```bash
python -m webapp --host 127.0.0.1 --port 8765 --workspace-root workspaces
```

The CLI allows only loopback hosts (`127.0.0.1`, `localhost`, `::1`). Workspaces are stored under the selected workspace root. Local uploads are staged in a hidden `.incoming/` directory and removed after validation/import. Workspace ZIP exports are saved in `.exports/`. Both are Git-ignored.

## Browser workflow

1. Create a workspace; its original idea is captured as the immutable workspace source.
2. Upload an existing M4 conceptual project or other supported milestone artifact. Uploads are streamed with a 20 MiB default limit and validated by the existing M13 artifact validators.
3. Run M7 readiness for a selected paradigm.
4. Select an imported M8 profile and compile it under the existing readiness/lineage gates.
5. Execute a compiled artifact with bounded run count and an optional seed.
6. Run M10 sweeps or descriptive analysis, M11 uncertainty analysis, and M12 dashboard generation.
7. Inspect the artifact ledger/activity, verify hashes, download artifacts, preview the generated M12 HTML in a sandboxed document, and export the workspace.
8. Select an M9 ABM execution result in the M16 replay panel to inspect either a non-spatial network layout or a spatial world with recorded agent coordinates and movement; move through recorded steps and inspect per-agent attributes and rule evaluations.

**M11 lineage note:** an uncertainty analysis generates its own paired M9 execution artifact. An M12 bundle can only attach M10/M11 reports derived from the exact same selected execution artifact. The UI therefore lists all M9 artifacts separately; choose the M11-generated execution result when attaching its M11 report.

M6's interactive clarification loop and M5 mapping acceptance/rejection remain in the M13 CLI in this milestone. They are not silently represented as completed browser capabilities.

## API

Base path: `/api/v1`. OpenAPI JSON: `/api/openapi.json`. Main routes:

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Local service status |
| GET / POST | `/workspaces` | List or create workspaces |
| GET | `/workspaces/{id}` | Workspace overview, original idea and artifact ledger |
| POST | `/workspaces/{id}/artifacts` | Upload and validate a milestone artifact (`multipart/form-data`) |
| GET | `/workspaces/{id}/artifacts/{artifact_id}/download` | Integrity-check and download one artifact |
| GET | `/workspaces/{id}/artifacts/{artifact_id}/preview` | Sandboxed preview for an M12 HTML dashboard only |
| POST | `/workspaces/{id}/readiness` | M7 assessment |
| POST | `/workspaces/{id}/compile` | M8 compilation from an imported profile |
| POST | `/workspaces/{id}/execute` | M9 simulation execution |
| POST | `/workspaces/{id}/parameter-sweep` | M10 parameter sweep |
| POST | `/workspaces/{id}/analysis` | M10 descriptive analysis |
| POST | `/workspaces/{id}/uncertainty` | M11 uncertainty analysis |
| POST | `/workspaces/{id}/visualization` | M12 bundle and standalone dashboard |
| GET | `/workspaces/{id}/executions/{artifact_id}/replay?run_index=1` | M15/M16 replay scene from an exact, integrity-verified M9 ABM result and linked M8 artifact; includes recorded model-space coordinates when the model declares a spatial world |
| GET | `/workspaces/{id}/verification` | SHA-256 and size checks |
| POST | `/workspaces/{id}/export` | Export workspace ZIP |
| POST | `/workspaces/{id}/mappings/suggest` | M5 mapping candidate retrieval |
| GET | `/exports/{filename}` | Download a generated workspace ZIP |

The API does not accept arbitrary local file paths. Artifact upload uses a temporary staged file and the same typed M13 validation/lineage logic as the CLI. Response payloads omit local filesystem paths.

## Security boundary

This is a single-user local development interface, not a production or multi-user service. The CLI binds only to loopback, has no authentication layer, and must not be exposed to a LAN, public IP or reverse proxy. The M12 preview is served only for typed `visualization_html` artifacts after integrity verification, with a restrictive sandbox Content Security Policy.

A remote deployment milestone must add authentication, authorization, CSRF/origin policy, rate limiting, job isolation, audit controls, secrets management and stronger multi-user workspace ownership before any network exposure.

## M15/M16 replay semantics

The viewer renders agent states, attributes, relationships and rule evaluations from recorded M9 snapshots. Non-spatial models retain M15's deterministic display-only network layout. Spatial models use M16's actual recorded coordinates at every frame, display the configured world boundary and show model-space coordinates in the inspector.

The M16 spatial extension supports a rectangular 2D world with `clamp` or `wrap` boundaries, initial agent coordinates, relative/absolute movement actions, and Euclidean radius-based state counts. Under the existing sequential activation policy, a later agent in a step observes movements already committed by earlier agents. Coordinates use model-defined units and a top-left origin; the platform does not infer physical units.

M16 does not implement simultaneous activation, collisions, obstacles, velocity/acceleration physics, dynamic relationships, or DES event playback. Those capabilities require separate model semantics and engine work. See `M16_ARCHITECTURE.md` and `M16_TEST_REPORT.md`.
