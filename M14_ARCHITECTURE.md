# M14 Architecture — Local Web Workbench

## Goal

Expose the existing M13 project lifecycle through a usable local browser interface and a versioned API without changing the conceptual, readiness, compilation, execution or analysis semantics delivered in M4–M13.

## System boundary

```text
Browser UI (static HTML/CSS/JS)
          | same-origin fetch
          v
FastAPI application (/api/v1)
          |
          +-- WorkspaceManager / ProjectWorkspace (M13 persistence, hash and lineage checks)
          |
          +-- WorkbenchService (M5/M7/M8/M9/M10/M11/M12 orchestration)
          |
          +-- Existing milestone packages and registered DES/ABM adapters
          |
          v
Local workspace root (manifest, source idea, typed artifacts, activity)
```

The application factory is `webapp.app.create_app(workspace_root, max_upload_bytes=...)`. The CLI entry point is `python -m webapp`. The default host and port are `127.0.0.1:8765`; the CLI rejects non-loopback host values.

## API responsibilities

- Create/list/open workspaces and return a JSON overview with stage progress, immutable idea text, artifacts and recent activity.
- Accept bounded `multipart/form-data` uploads. Filenames are reduced to safe display names; uploaded bytes are streamed to a temporary staging location and immediately passed to `ProjectWorkspace.add_artifact`. The M13 validators enforce known artifact schemas and lineage. The source upload is not moved.
- Expose M7 readiness, M8 compilation, M9 execution, M10 parameter sweep/analysis, M11 uncertainty analysis and M12 visualization by delegating to `WorkbenchService`.
- Expose hash/size verification and workspace ZIP export.
- Download typed artifacts only after integrity verification. Generated M12 HTML can be previewed through a separate route, only for artifacts recorded as `visualization_html`.
- Return stable versioned JSON shapes and structured HTTP errors. Local filesystem paths are not returned in artifact summaries.

## Browser UI

The static single-page UI is intentionally dependency-free: no Node build chain, external CDN, remote fonts or external chart package. It supports workspace creation/selection, progress/status review, artifact upload/download, M7–M12 operations, verification and ZIP export. User-controlled strings are inserted with `textContent`, not interpreted as HTML. The generated M12 dashboard is opened in a separate sandboxed document.

M6's interactive clarification dialogue and M5's explicit mapping accept/reject review are still operated through the M13 CLI in this milestone. M14 includes only a M5 retrieval suggestion API endpoint; it does not misrepresent an unreviewed mapping as accepted.

## Windows artifact path regression

M13 created temporary artifact-copy names by appending a 32-character UUID plus `.tmp` to the complete destination filename. Long M9 result names could therefore exceed the traditional Windows path limit even when the final artifact path itself was valid. M14 changes the copy step to use a short exclusive `.a-*.tmp` file in the same destination directory, flushes/fsyncs the bytes, verifies SHA-256, and atomically replaces the final path. This preserves atomicity while avoiding redundant filename length.

## Security and deployment

The web server is local-only by default and contains no authentication or multi-user ownership system. It is not safe to expose to a network. Upload size is bounded (20 MiB by default), upload paths are not user-controlled, downloads are integrity checked, artifact summaries omit absolute paths, and generated dashboard preview uses a sandbox CSP (`sandbox allow-scripts`, no same-origin permission, and no network/default external resource access).

A future remote deployment needs a separate security milestone: authentication, workspace ownership/authorization, CSRF and origin policy, rate limits, isolated/background jobs, audit controls, secrets management, safe deployment configuration, and multi-user concurrency handling.

## Explicit exclusions

M14 does not implement M6 interactive clarification or M5 review UI, mathematical/data-driven simulation engines, universal simulation grammar, ML rule discovery, real-time 2D spatial rendering, multi-user collaboration, authentication, cloud hosting or public network deployment. M12's existing offline dashboard remains the visualization output; M14 provides safe local preview, not an animated spatial simulator.
