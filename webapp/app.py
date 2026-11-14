"""FastAPI application for the local M14 browser workbench.

The web layer is intentionally thin: M13's WorkbenchService remains the
orchestrator and the existing milestone packages remain the source of model
semantics and validation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import tempfile
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from execution import ExperimentConfig, load_result
from compilation import CompilationParadigm, load_artifact
from simulation_studio import ReplayError, build_abm_replay
from experimentation import GridFactor
from readiness import Paradigm
from workbench import ArtifactType, WorkbenchService, WorkspaceManager
from workbench.workspace import WorkspaceConflictError, WorkspaceError


STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_UPLOAD_LIMIT = 20 * 1024 * 1024


def _jsonable(value: Any) -> Any:
    """Convert project dataclasses/enums/tuples into strict JSON data."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable")


def _artifact_summary(record) -> dict[str, Any]:
    data = _jsonable(record)
    data.pop("relative_path", None)  # Never expose local filesystem layout.
    return data


class CreateWorkspaceRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    original_idea: str = Field(min_length=1, max_length=20_000)


class ReadinessRequest(BaseModel):
    selected_paradigm: Literal["discrete_event", "agent_based", "mathematical", "data_driven"] | None = None


class CompileRequest(BaseModel):
    profile_artifact_id: str = Field(min_length=1, max_length=100)


class ExecuteRequest(BaseModel):
    compilation_artifact_id: str = Field(min_length=1, max_length=100)
    runs: int = Field(default=1, ge=1, le=100)
    base_seed: int | None = Field(default=None, ge=0)
    continue_on_error: bool = True


class SweepFactorRequest(BaseModel):
    target_path: str = Field(min_length=1, max_length=300)
    levels: list[str | int | float | bool | None] = Field(min_length=1, max_length=100)


class ParameterSweepRequest(BaseModel):
    compilation_artifact_id: str = Field(min_length=1, max_length=100)
    factors: list[SweepFactorRequest] = Field(min_length=1, max_length=10)
    runs: int = Field(default=1, ge=1, le=100)
    base_seed: int | None = Field(default=None, ge=0)
    include_baseline: bool = True


class AnalyzeRequest(BaseModel):
    execution_artifact_id: str = Field(min_length=1, max_length=100)


class UncertaintyRequest(BaseModel):
    compilation_artifact_id: str = Field(min_length=1, max_length=100)
    plan_artifact_id: str = Field(min_length=1, max_length=100)
    execution_base_seed: int | None = Field(default=None, ge=0)


class VisualizationRequest(BaseModel):
    execution_artifact_id: str = Field(min_length=1, max_length=100)
    analysis_artifact_id: str | None = Field(default=None, max_length=100)
    uncertainty_artifact_id: str | None = Field(default=None, max_length=100)
    point_limit: int = Field(default=20_000, ge=100, le=100_000)


class IdeaMappingRequest(BaseModel):
    concept_id: str = Field(min_length=1, max_length=120)
    query: str | None = Field(default=None, max_length=300)
    limit: int = Field(default=5, ge=1, le=20)


def create_app(
    workspace_root: str | Path | None = None,
    *,
    max_upload_bytes: int = DEFAULT_UPLOAD_LIMIT,
) -> FastAPI:
    """Create the local web workbench application.

    The CLI runner binds to loopback only. An explicit app factory is exposed
    for tests and embedding, but public deployment is outside M14's security
    scope and requires authentication, authorization and deployment hardening.
    """
    root = Path(
        workspace_root
        or os.getenv("SIMULATOR_WORKSPACE_ROOT", "workspaces")
    ).expanduser().resolve()
    if max_upload_bytes < 1:
        raise ValueError("max_upload_bytes must be positive")
    manager = WorkspaceManager(root)
    app = FastAPI(
        title="AI-Assisted Simulation Workbench",
        version="17.0.0",
        description="Local project workspaces, simulation lifecycle, and spatial ABM replay API.",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.workspace_manager = manager
    app.state.workspace_root = root
    app.state.max_upload_bytes = max_upload_bytes

    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'",
        )
        return response

    @app.exception_handler(LookupError)
    async def lookup_error_handler(_request, exc: LookupError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(WorkspaceConflictError)
    async def conflict_error_handler(_request, exc: WorkspaceConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(WorkspaceError)
    async def workspace_error_handler(_request, exc: WorkspaceError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def value_error_handler(_request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    def open_workspace(workspace_id: str):
        return manager.open(workspace_id)

    def overview_payload(workspace):
        manifest = workspace.manifest
        return {
            "overview": _jsonable(workspace.overview()),
            "original_idea": manifest.original_idea,
            "artifacts": [_artifact_summary(item) for item in manifest.artifacts],
        }

    def service_for(workspace_id: str) -> WorkbenchService:
        return WorkbenchService(open_workspace(workspace_id))

    @app.get("/", include_in_schema=False)
    async def home():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok", "service": "simulation-workbench", "version": app.version}

    @app.get("/api/v1/workspaces")
    async def list_workspaces():
        return {"workspaces": _jsonable(manager.list_workspaces())}

    @app.post("/api/v1/workspaces", status_code=201)
    async def create_workspace(payload: CreateWorkspaceRequest):
        workspace = manager.create(payload.title, payload.original_idea)
        return overview_payload(workspace)

    @app.get("/api/v1/workspaces/{workspace_id}")
    async def get_workspace(workspace_id: str):
        return overview_payload(open_workspace(workspace_id))

    @app.post("/api/v1/workspaces/{workspace_id}/artifacts", status_code=201)
    async def upload_artifact(
        workspace_id: str,
        artifact_type: str = Query(...),
        display_name: str | None = Query(default=None, max_length=160),
        file: UploadFile = File(...),
    ):
        workspace = open_workspace(workspace_id)
        try:
            kind = ArtifactType(artifact_type)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Unsupported artifact_type: {artifact_type}") from exc

        original_filename = file.filename or "artifact.json"
        safe_filename = PureWindowsPath(original_filename).name
        safe_filename = PurePosixPath(safe_filename).name
        safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "_", safe_filename).strip("._") or "artifact.json"
        suffix = Path(safe_filename).suffix[:16]
        incoming_dir = root / ".incoming"
        incoming_dir.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(prefix="upload-", suffix=suffix, dir=incoming_dir)
        temp_path = Path(temp_name)
        total = 0
        try:
            with os.fdopen(descriptor, "wb") as target:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_upload_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"Upload exceeds the {max_upload_bytes}-byte limit",
                        )
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            if total == 0:
                raise HTTPException(status_code=422, detail="Uploaded artifact is empty")
            record = workspace.add_artifact(
                temp_path, kind, display_name=display_name or Path(safe_filename).stem
            )
            return {
                "artifact": _artifact_summary(record),
                "workspace": overview_payload(workspace),
            }
        finally:
            temp_path.unlink(missing_ok=True)
            await file.close()

    @app.get("/api/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/download")
    async def download_artifact(workspace_id: str, artifact_id: str):
        workspace = open_workspace(workspace_id)
        record = next((item for item in workspace.artifacts() if item.artifact_id == artifact_id), None)
        if record is None:
            raise LookupError(f"Artifact {artifact_id!r} was not found in this workspace")
        verification = next(item for item in workspace.verify_artifacts() if item.artifact_id == artifact_id)
        if not verification.valid:
            raise HTTPException(status_code=409, detail=f"Artifact integrity check failed: {verification.message}")
        path = workspace.artifact_path(artifact_id)
        return FileResponse(path, filename=Path(path).name, media_type="application/octet-stream")

    @app.get("/api/v1/workspaces/{workspace_id}/executions/{artifact_id}/replay")
    async def replay_execution(
        workspace_id: str,
        artifact_id: str,
        run_index: int = Query(default=1, ge=1, le=100),
    ):
        """Return an integrity-checked, exact-lineage ABM replay scene."""
        workspace = open_workspace(workspace_id)
        execution_record = next(
            (item for item in workspace.artifacts() if item.artifact_id == artifact_id), None
        )
        if execution_record is None:
            raise LookupError(f"Artifact {artifact_id!r} was not found in this workspace")
        if execution_record.artifact_type != ArtifactType.EXECUTION_RESULT.value:
            raise HTTPException(status_code=415, detail="Replay requires an M9 execution_result artifact")

        checks = {item.artifact_id: item for item in workspace.verify_artifacts()}
        if artifact_id not in checks or not checks[artifact_id].valid:
            message = checks[artifact_id].message if artifact_id in checks else "Artifact is not verifiable"
            raise HTTPException(status_code=409, detail=f"M9 artifact integrity check failed: {message}")
        try:
            result = load_result(workspace.artifact_path(artifact_id))
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Could not load M9 execution result: {exc}") from exc

        if result.paradigm != CompilationParadigm.AGENT_BASED.value:
            raise HTTPException(
                status_code=415,
                detail="Interactive replay currently supports ABM results. DES event playback is a later extension.",
            )

        compilation_record = next((
            item for item in workspace.artifacts(ArtifactType.COMPILATION_ARTIFACT)
            if item.metadata.get("artifact_id") == result.artifact_id
            and item.metadata.get("artifact_fingerprint") == result.artifact_fingerprint
        ), None)
        if compilation_record is None:
            raise HTTPException(status_code=409, detail="The exact M8 compilation artifact linked to this M9 result is missing")
        if compilation_record.artifact_id not in checks or not checks[compilation_record.artifact_id].valid:
            raise HTTPException(status_code=409, detail="Linked M8 compilation artifact failed integrity verification")
        try:
            compilation = load_artifact(workspace.artifact_path(compilation_record.artifact_id))
            scene = build_abm_replay(result, compilation, run_index=run_index)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Could not build ABM replay: {exc}") from exc
        return scene

    @app.get("/api/v1/workspaces/{workspace_id}/artifacts/{artifact_id}/preview")
    async def preview_dashboard(workspace_id: str, artifact_id: str):
        workspace = open_workspace(workspace_id)
        record = next((item for item in workspace.artifacts() if item.artifact_id == artifact_id), None)
        if record is None:
            raise LookupError(f"Artifact {artifact_id!r} was not found in this workspace")
        if record.artifact_type != ArtifactType.VISUALIZATION_HTML.value:
            raise HTTPException(status_code=415, detail="Only generated M12 HTML dashboards can be previewed")
        verification = next(item for item in workspace.verify_artifacts() if item.artifact_id == artifact_id)
        if not verification.valid:
            raise HTTPException(status_code=409, detail=f"Artifact integrity check failed: {verification.message}")
        path = workspace.artifact_path(artifact_id)
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise HTTPException(status_code=422, detail="Could not read the generated dashboard") from exc
        return HTMLResponse(
            content=content,
            headers={
                "Content-Security-Policy": "sandbox allow-scripts; default-src 'none'; "
                "script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:",
                "Content-Disposition": "inline",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            },
        )

    @app.post("/api/v1/workspaces/{workspace_id}/readiness")
    async def assess_readiness(workspace_id: str, payload: ReadinessRequest):
        report, record = service_for(workspace_id).assess(payload.selected_paradigm)
        return {"report": _jsonable(report), "artifact": _artifact_summary(record)}

    @app.post("/api/v1/workspaces/{workspace_id}/compile")
    async def compile_model(workspace_id: str, payload: CompileRequest):
        result, record = service_for(workspace_id).compile(payload.profile_artifact_id)
        return {
            "compilation": _jsonable(result),
            "artifact": _artifact_summary(record) if record else None,
        }

    @app.post("/api/v1/workspaces/{workspace_id}/execute")
    async def execute_model(workspace_id: str, payload: ExecuteRequest):
        config = ExperimentConfig(
            runs=payload.runs,
            base_seed=payload.base_seed,
            continue_on_error=payload.continue_on_error,
        )
        result, record = service_for(workspace_id).execute(payload.compilation_artifact_id, config)
        return {"result": _jsonable(result), "artifact": _artifact_summary(record)}

    @app.post("/api/v1/workspaces/{workspace_id}/parameter-sweep")
    async def parameter_sweep(workspace_id: str, payload: ParameterSweepRequest):
        factors = tuple(GridFactor(item.target_path, tuple(item.levels)) for item in payload.factors)
        result, report, result_record, report_record = service_for(workspace_id).parameter_sweep(
            payload.compilation_artifact_id,
            factors,
            runs=payload.runs,
            base_seed=payload.base_seed,
            include_baseline=payload.include_baseline,
        )
        return {
            "result": _jsonable(result),
            "analysis": _jsonable(report),
            "execution_artifact": _artifact_summary(result_record),
            "analysis_artifact": _artifact_summary(report_record),
        }

    @app.post("/api/v1/workspaces/{workspace_id}/analysis")
    async def analyze_execution(workspace_id: str, payload: AnalyzeRequest):
        report, record = service_for(workspace_id).analyze_result(payload.execution_artifact_id)
        return {"analysis": _jsonable(report), "artifact": _artifact_summary(record)}

    @app.post("/api/v1/workspaces/{workspace_id}/uncertainty")
    async def analyze_uncertainty(workspace_id: str, payload: UncertaintyRequest):
        result, report, result_record, report_record = service_for(workspace_id).uncertainty_analysis(
            payload.compilation_artifact_id,
            payload.plan_artifact_id,
            execution_base_seed=payload.execution_base_seed,
        )
        return {
            "result": _jsonable(result),
            "report": _jsonable(report),
            "execution_artifact": _artifact_summary(result_record),
            "uncertainty_artifact": _artifact_summary(report_record),
        }

    @app.post("/api/v1/workspaces/{workspace_id}/visualization")
    async def build_visualization(workspace_id: str, payload: VisualizationRequest):
        bundle, bundle_record, html_record = service_for(workspace_id).build_visualization(
            payload.execution_artifact_id,
            analysis_artifact_id=payload.analysis_artifact_id,
            uncertainty_artifact_id=payload.uncertainty_artifact_id,
            point_limit=payload.point_limit,
        )
        return {
            "bundle": _jsonable(bundle),
            "bundle_artifact": _artifact_summary(bundle_record),
            "html_artifact": _artifact_summary(html_record),
            "html_download_url": f"/api/v1/workspaces/{workspace_id}/artifacts/{html_record.artifact_id}/download",
            "html_preview_url": f"/api/v1/workspaces/{workspace_id}/artifacts/{html_record.artifact_id}/preview",
        }

    @app.get("/api/v1/workspaces/{workspace_id}/verification")
    async def verify_workspace(workspace_id: str):
        workspace = open_workspace(workspace_id)
        checks = workspace.verify_artifacts()
        return {
            "valid": all(item.valid for item in checks),
            "checks": _jsonable(checks),
        }

    @app.post("/api/v1/workspaces/{workspace_id}/export")
    async def export_workspace(workspace_id: str):
        workspace = open_workspace(workspace_id)
        export_dir = root / ".exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        title = re.sub(r"[^A-Za-z0-9._-]+", "_", workspace.manifest.title).strip("._") or "workspace"
        export_path = export_dir / f"{title}-{workspace_id}.zip"
        workspace.export_zip(export_path)
        return {
            "filename": export_path.name,
            "download_url": f"/api/v1/exports/{export_path.name}",
        }

    @app.get("/api/v1/exports/{filename}")
    async def download_export(filename: str):
        if not re.fullmatch(r"[A-Za-z0-9._-]+\.zip", filename):
            raise HTTPException(status_code=404, detail="Export not found")
        path = (root / ".exports" / filename).resolve()
        try:
            path.relative_to((root / ".exports").resolve())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Export not found") from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Export not found")
        return FileResponse(path, filename=filename, media_type="application/zip")

    @app.post("/api/v1/workspaces/{workspace_id}/mappings/suggest")
    async def suggest_mappings(workspace_id: str, payload: IdeaMappingRequest):
        candidates = service_for(workspace_id).suggest_mappings(
            payload.concept_id, query=payload.query, limit=payload.limit
        )
        return {"candidates": _jsonable(candidates)}

    return app


app = create_app()
