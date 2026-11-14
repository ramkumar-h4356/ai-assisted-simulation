# Milestone 14 Report — Local Browser Workbench

## Status

M14 adds a local browser application and versioned HTTP API around the M13 workspace lifecycle. It also fixes a Windows artifact-copy temporary-path length defect discovered by the user's full local test run.

## Delivered

### 1. Browser workbench
- Static, responsive, dependency-free HTML/CSS/JavaScript UI.
- Create and select project workspaces.
- View original idea, lifecycle progress, recent activity and artifact ledger.
- Upload known milestone artifacts through M13 schema/lineage validation.
- Trigger M7 readiness, M8 compilation, M9 execution, M10 sweeps/analysis, M11 uncertainty and M12 visualization.
- Download artifacts, open M12 HTML in a sandboxed browser document, verify workspace integrity and export a project ZIP.

### 2. Versioned API
- FastAPI app factory and `python -m webapp` entry point.
- REST endpoints under `/api/v1`, OpenAPI JSON at `/api/openapi.json`.
- Structured errors for missing workspaces, lineage conflicts, invalid artifacts and upload limits.
- Uploads are streamed to a temporary staging directory, bounded to 20 MiB by default, and passed to the existing M13 validator. API responses do not disclose local artifact filesystem paths.

### 3. Preserved lifecycle semantics
- M14 delegates to `WorkspaceManager`, `ProjectWorkspace` and `WorkbenchService`. It does not reimplement or bypass M7 readiness, M8 compilation validation, M9 execution lineage or M10–M12 provenance checks.
- M11-generated execution results remain paired with their own M11 reports. The UI/API require an attached M10/M11 report to match the exact selected M9 result.

### 4. Windows path-length defect fixed
- The M13 copy routine appended a long UUID to the full artifact destination filename for its temporary file. A Windows test path could exceed the legacy path-length limit although the final filename was still valid.
- M14 now creates a short exclusive temporary file in the destination directory, fsyncs it, checks its SHA-256 and atomically replaces the final destination.

## Verification summary

See `M14_TEST_REPORT.md` for commands and limitations.

## Boundaries

M14 is a local single-user application. It does not provide authentication or remote hosting. M6's interactive clarification and M5's explicit mapping review remain on the M13 CLI. It does not add mathematical/data-driven execution, ML rule discovery or a real-time spatial 2D renderer.
