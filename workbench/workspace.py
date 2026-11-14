"""Persistent project workspace, artifact lifecycle and provenance checks (M13)."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import shutil
import tempfile
from uuid import uuid4
import zipfile

from workbench.models import (
    ActivityEvent, ArtifactRecord, ArtifactType, ArtifactVerification,
    StageStatus, WorkflowStage, WorkspaceManifest, WorkspaceOverview,
)
from workbench.serialization import WorkspaceSerializationError, dumps_manifest, loads_manifest
from workbench.validators import ArtifactValidationError, validate_artifact


class WorkspaceError(ValueError):
    """Base exception for workspace operations."""


class WorkspaceConflictError(WorkspaceError):
    """Raised when an artifact conflicts with the workspace's project lineage."""


class WorkspaceIntegrityError(WorkspaceError):
    """Raised when the stored manifest or an artifact fails integrity checks."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:48]
    return slug or "project"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


class ProjectWorkspace:
    """A resumable workspace containing one idea and its milestone artifacts."""

    MANIFEST_NAME = "workspace.json"

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory).resolve()
        self.manifest_path = self.directory / self.MANIFEST_NAME
        if not self.manifest_path.is_file():
            raise WorkspaceError(f"Workspace manifest not found: {self.manifest_path}")
        self._manifest = self._read_manifest()
        self._ensure_directory_layout()

    @property
    def manifest(self) -> WorkspaceManifest:
        self._manifest = self._read_manifest()
        return self._manifest

    @property
    def workspace_id(self) -> str:
        return self.manifest.workspace_id

    @property
    def artifacts_directory(self) -> Path:
        return self.directory / "artifacts"

    def _ensure_directory_layout(self) -> None:
        self.artifacts_directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "notes").mkdir(exist_ok=True)
        original_idea_path = self.directory / "original_idea.md"
        expected = self.manifest.original_idea + "\n"
        if not original_idea_path.exists():
            _atomic_write(original_idea_path, expected.encode("utf-8"))
        else:
            try:
                actual = original_idea_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                raise WorkspaceIntegrityError(f"Could not read immutable original idea copy: {error}") from error
            if actual != expected:
                raise WorkspaceIntegrityError("original_idea.md does not match the immutable original idea in workspace.json")

    def _read_manifest(self) -> WorkspaceManifest:
        try:
            manifest = loads_manifest(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, WorkspaceSerializationError) as error:
            raise WorkspaceIntegrityError(f"Could not load workspace manifest: {error}") from error
        if self.directory.name != manifest.workspace_id and not self.directory.name.endswith("-" + manifest.workspace_id):
            raise WorkspaceIntegrityError("Workspace directory does not match its manifest ID")
        return manifest

    def _save_manifest(self, manifest: WorkspaceManifest) -> None:
        _atomic_write(self.manifest_path, dumps_manifest(manifest).encode("utf-8"))
        self._manifest = manifest

    def _event(self, action: str, detail: str) -> ActivityEvent:
        return ActivityEvent(f"evt-{uuid4().hex[:12]}", _now(), action, detail)

    def _update(
        self,
        *,
        artifacts: tuple[ArtifactRecord, ...] | None = None,
        idea_project_id: str | None | object = ...,
        event: ActivityEvent | None = None,
    ) -> None:
        current = self.manifest
        activity = current.activity + ((event,) if event else ())
        if len(activity) > 500:
            activity = activity[-500:]
        updated = WorkspaceManifest(
            schema_version=current.schema_version,
            workspace_id=current.workspace_id,
            title=current.title,
            created_at=current.created_at,
            updated_at=_now(),
            original_idea=current.original_idea,
            idea_project_id=current.idea_project_id if idea_project_id is ... else idea_project_id,
            artifacts=current.artifacts if artifacts is None else artifacts,
            activity=activity,
        )
        self._save_manifest(updated)

    def _safe_artifact_path(self, relative_path: str) -> Path:
        candidate = (self.directory / relative_path).resolve()
        try:
            candidate.relative_to(self.directory)
        except ValueError as error:
            raise WorkspaceIntegrityError("Artifact path escapes its workspace") from error
        return candidate

    def artifacts(self, artifact_type: ArtifactType | str | None = None) -> tuple[ArtifactRecord, ...]:
        manifest = self.manifest
        if artifact_type is None:
            return manifest.artifacts
        kind = artifact_type.value if isinstance(artifact_type, ArtifactType) else str(artifact_type)
        return tuple(item for item in manifest.artifacts if item.artifact_type == kind)

    def artifact_path(self, artifact_id: str) -> Path:
        for item in self.manifest.artifacts:
            if item.artifact_id == artifact_id:
                return self._safe_artifact_path(item.relative_path)
        raise LookupError(f"No artifact with ID {artifact_id!r} exists in this workspace")

    def _primary_idea_metadata(self) -> dict | None:
        for item in reversed(self.manifest.artifacts):
            if item.artifact_type == ArtifactType.IDEA_PROJECT.value:
                return item.metadata
        return None

    def _check_lineage(self, artifact_type: ArtifactType, metadata: dict, *, replace_primary: bool) -> str | None:
        manifest = self.manifest
        current_project_id = manifest.idea_project_id
        incoming_project_id = metadata.get("project_id")
        existing = manifest.artifacts

        if artifact_type is ArtifactType.IDEA_PROJECT:
            source_statement = metadata.get("original_statement")
            if source_statement is not None and source_statement.strip() != manifest.original_idea.strip():
                raise WorkspaceConflictError("Conceptual project original_statement does not match the workspace source idea")
            if current_project_id and incoming_project_id != current_project_id:
                downstream = {
                    ArtifactType.IDEA_SESSION.value, ArtifactType.READINESS_REPORT.value, ArtifactType.COMPILATION_PROFILE.value,
                    ArtifactType.COMPILATION_ARTIFACT.value, ArtifactType.EXECUTION_RESULT.value,
                    ArtifactType.ANALYSIS_REPORT.value, ArtifactType.UNCERTAINTY_REPORT.value,
                    ArtifactType.VISUALIZATION_BUNDLE.value,
                }
                has_downstream = any(item.artifact_type in downstream for item in manifest.artifacts)
                if not replace_primary or has_downstream:
                    raise WorkspaceConflictError(
                        "This conceptual project has a different ID. A primary project can only be replaced before downstream artifacts are linked."
                    )
            return incoming_project_id

        project_scoped = {
            ArtifactType.IDEA_SESSION, ArtifactType.READINESS_REPORT,
            ArtifactType.COMPILATION_PROFILE, ArtifactType.COMPILATION_ARTIFACT,
            ArtifactType.EXECUTION_RESULT, ArtifactType.ANALYSIS_REPORT,
            ArtifactType.UNCERTAINTY_REPORT, ArtifactType.VISUALIZATION_BUNDLE,
        }
        if artifact_type in project_scoped:
            if not current_project_id:
                raise WorkspaceConflictError("Import the conceptual idea project before importing project-scoped artifacts")
            if incoming_project_id != current_project_id:
                raise WorkspaceConflictError(
                    f"Artifact project_id {incoming_project_id!r} does not match workspace project_id {current_project_id!r}"
                )
            idea_metadata = self._primary_idea_metadata() or {}
            known_revisions = set(idea_metadata.get("revision_ids", []))
            revision_id = metadata.get("revision_id")
            if revision_id and known_revisions and revision_id not in known_revisions:
                raise WorkspaceConflictError(f"Artifact references unknown conceptual revision {revision_id!r}")

        if artifact_type is ArtifactType.COMPILATION_ARTIFACT:
            status = metadata.get("m7_readiness_status")
            if status != "ready_for_implementation_planning":
                raise WorkspaceConflictError("Compilation artifact does not record an M7-ready status")
            matching_readiness = any(
                item.artifact_type == ArtifactType.READINESS_REPORT.value
                and item.metadata.get("project_id") == metadata.get("project_id")
                and item.metadata.get("revision_id") == metadata.get("revision_id")
                and item.metadata.get("selected_paradigm") == metadata.get("paradigm")
                and item.metadata.get("readiness_status") == "ready_for_implementation_planning"
                for item in existing
            )
            if not matching_readiness:
                raise WorkspaceConflictError("M8 compilation must be linked to a matching M7-ready report for this revision and paradigm")

        if artifact_type is ArtifactType.UNCERTAINTY_PLAN:
            if not any(item.artifact_type == ArtifactType.COMPILATION_ARTIFACT.value for item in existing):
                raise WorkspaceConflictError("Import an M8 compilation artifact before its M11 uncertainty plan")

        if artifact_type is ArtifactType.EXECUTION_RESULT:
            parents = [item.metadata for item in existing if item.artifact_type == ArtifactType.COMPILATION_ARTIFACT.value]
            if not any(item.get("artifact_id") == metadata.get("artifact_id") and item.get("artifact_fingerprint") == metadata.get("artifact_fingerprint") for item in parents):
                raise WorkspaceConflictError("Execution result has no matching M8 compilation artifact in this workspace")

        if artifact_type is ArtifactType.ANALYSIS_REPORT:
            known_results = {
                (item.metadata.get("experiment_id"), item.metadata.get("result_fingerprint"))
                for item in existing if item.artifact_type == ArtifactType.EXECUTION_RESULT.value
            }
            requested = set(zip(metadata.get("input_experiment_ids", []), metadata.get("input_result_fingerprints", [])))
            if not requested or not requested.issubset(known_results):
                raise WorkspaceConflictError("M10 analysis references execution results that are not linked to this workspace")

        if artifact_type is ArtifactType.UNCERTAINTY_REPORT:
            matching = any(
                item.artifact_type == ArtifactType.EXECUTION_RESULT.value
                and item.metadata.get("experiment_id") == metadata.get("experiment_id")
                and item.metadata.get("result_fingerprint") == metadata.get("experiment_fingerprint")
                and item.metadata.get("artifact_id") == metadata.get("artifact_id")
                and item.metadata.get("artifact_fingerprint") == metadata.get("artifact_fingerprint")
                for item in existing
            )
            if not matching:
                raise WorkspaceConflictError("M11 report has no exact matching M9 execution result in this workspace")

        if artifact_type is ArtifactType.VISUALIZATION_BUNDLE:
            matching = any(
                item.artifact_type == ArtifactType.EXECUTION_RESULT.value
                and item.metadata.get("experiment_id") == metadata.get("experiment_id")
                and item.metadata.get("result_fingerprint") == metadata.get("experiment_fingerprint")
                and item.metadata.get("artifact_id") == metadata.get("artifact_id")
                and item.metadata.get("artifact_fingerprint") == metadata.get("artifact_fingerprint")
                for item in existing
            )
            if not matching:
                raise WorkspaceConflictError("M12 dashboard bundle has no exact matching M9 result and M8 artifact in this workspace")
        return current_project_id

    def add_artifact(
        self,
        source_path: str | Path,
        artifact_type: ArtifactType | str,
        *,
        display_name: str | None = None,
        replace_primary: bool = False,
    ) -> ArtifactRecord:
        source = Path(source_path).expanduser().resolve()
        try:
            kind = artifact_type if isinstance(artifact_type, ArtifactType) else ArtifactType(artifact_type)
        except ValueError as error:
            raise WorkspaceError(f"Unsupported artifact type {artifact_type!r}") from error
        if not source.is_file():
            raise WorkspaceError(f"Artifact source is not a file: {source}")
        try:
            metadata = validate_artifact(source, kind)
        except ArtifactValidationError as error:
            raise WorkspaceError(str(error)) from error
        new_project_id = self._check_lineage(kind, metadata, replace_primary=replace_primary)
        digest = _sha256(source)
        manifest = self.manifest
        duplicate = next((item for item in manifest.artifacts if item.artifact_type == kind.value and item.sha256 == digest), None)
        if duplicate:
            return duplicate

        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source.name).strip("._") or "artifact.dat"
        relative = Path("artifacts") / kind.value / f"{digest[:12]}_{safe_name}"
        destination = self._safe_artifact_path(relative.as_posix())
        if destination.exists() and _sha256(destination) != digest:
            destination = destination.with_name(f"{uuid4().hex[:8]}_{destination.name}")
            relative = destination.relative_to(self.directory)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Do not append a UUID to the complete destination filename here. On
        # Windows that can push an otherwise valid artifact path beyond the
        # traditional MAX_PATH limit (the M9 execution filenames are long).
        # A short, exclusive temporary filename in the same directory keeps
        # the final os.replace atomic without inflating the path length.
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".a-", suffix=".tmp", dir=destination.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as target, source.open("rb") as origin:
                shutil.copyfileobj(origin, target, length=1024 * 1024)
                target.flush()
                os.fsync(target.fileno())
            if _sha256(temporary) != digest:
                raise WorkspaceIntegrityError("Artifact changed while being copied")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

        record = ArtifactRecord(
            artifact_id=f"art-{uuid4().hex[:12]}", artifact_type=kind.value,
            display_name=(display_name or source.stem).strip() or source.stem,
            relative_path=relative.as_posix(), sha256=digest,
            size_bytes=destination.stat().st_size, created_at=_now(), metadata=metadata,
        )
        artifacts = manifest.artifacts + (record,)
        event = self._event("artifact_imported", f"Imported {kind.value}: {record.display_name}")
        effective_project_id = new_project_id if kind is ArtifactType.IDEA_PROJECT else manifest.idea_project_id
        self._update(artifacts=artifacts, idea_project_id=effective_project_id, event=event)
        return record

    def verify_artifacts(self) -> tuple[ArtifactVerification, ...]:
        results = []
        for item in self.manifest.artifacts:
            try:
                path = self._safe_artifact_path(item.relative_path)
                if not path.is_file():
                    results.append(ArtifactVerification(item.artifact_id, item.relative_path, False, "File is missing"))
                    continue
                actual_size = path.stat().st_size
                actual_hash = _sha256(path)
                if actual_hash != item.sha256:
                    results.append(ArtifactVerification(item.artifact_id, item.relative_path, False, "SHA-256 checksum does not match"))
                elif actual_size != item.size_bytes:
                    results.append(ArtifactVerification(item.artifact_id, item.relative_path, False, "File size does not match manifest"))
                else:
                    results.append(ArtifactVerification(item.artifact_id, item.relative_path, True, "Integrity verified"))
            except OSError as error:
                results.append(ArtifactVerification(item.artifact_id, item.relative_path, False, f"Verification failed: {error}"))
        return tuple(results)


    def export_zip(self, destination: str | Path) -> Path:
        """Create a portable workspace archive after verifying every artifact."""
        checks = self.verify_artifacts()
        failures = [item for item in checks if not item.valid]
        if failures:
            details = "; ".join(f"{item.relative_path}: {item.message}" for item in failures)
            raise WorkspaceIntegrityError(f"Cannot export a workspace with invalid artifacts: {details}")
        target = Path(destination).expanduser().resolve()
        try:
            target.relative_to(self.directory)
        except ValueError:
            pass
        else:
            raise WorkspaceError("ZIP export destination must be outside the workspace directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + f".{uuid4().hex}.tmp")
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for item in sorted(self.directory.rglob("*")):
                    if not item.is_file():
                        continue
                    if item.is_symlink():
                        raise WorkspaceIntegrityError("Workspace export refuses symbolic links")
                    archive.write(item, (Path(self.directory.name) / item.relative_to(self.directory)).as_posix())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        self._update(event=self._event("workspace_exported", f"Workspace exported to {target.name}"))
        return target

    def workflow_stages(self) -> tuple[WorkflowStage, ...]:
        manifest = self.manifest
        grouped: dict[str, list[ArtifactRecord]] = {}
        for item in manifest.artifacts:
            grouped.setdefault(item.artifact_type, []).append(item)

        idea_ready = bool(manifest.original_idea.strip())
        idea_records = grouped.get(ArtifactType.IDEA_PROJECT.value, [])
        conceptual = bool(idea_records)
        latest_idea_metadata = idea_records[-1].metadata if idea_records else {}
        mapping_count = int(latest_idea_metadata.get("mapping_count", 0) or 0)
        session_count = len(grouped.get(ArtifactType.IDEA_SESSION.value, []))
        readiness_records = grouped.get(ArtifactType.READINESS_REPORT.value, [])
        readiness_ready = any(
            item.metadata.get("readiness_status") == "ready_for_implementation_planning"
            for item in readiness_records
        )
        compilation = bool(grouped.get(ArtifactType.COMPILATION_ARTIFACT.value))
        execution_records = grouped.get(ArtifactType.EXECUTION_RESULT.value, [])
        execution = any(item.metadata.get("successful_run_count", 0) > 0 for item in execution_records)

        def status(count: int, prerequisite: bool) -> StageStatus:
            if count:
                return StageStatus.COMPLETED
            return StageStatus.NOT_STARTED if prerequisite else StageStatus.BLOCKED

        stages = [
            WorkflowStage("idea", "Original idea", StageStatus.COMPLETED if idea_ready else StageStatus.NOT_STARTED, 1 if idea_ready else 0, "Immutable source idea captured in the workspace."),
            WorkflowStage("conceptual_model", "Conceptual formalization", status(len(idea_records), idea_ready), len(idea_records), "M4 model and append-only revision history."),
            WorkflowStage("interpretation", "AI interpretation and clarification", status(session_count, conceptual), session_count, "M6 interpretation and clarification audit trail; AI proposals remain reviewable."),
            WorkflowStage("knowledge_mapping", "Knowledge retrieval and mapping", status(mapping_count, conceptual), mapping_count, "M5 source-linked mapping claims in the current conceptual revision; unreviewed claims are not accepted facts."),
            WorkflowStage("readiness", "Readiness assessment", status(len(readiness_records), conceptual), len(readiness_records), "M7 assessment for a specific conceptual revision and selected paradigm."),
            WorkflowStage("compilation", "Paradigm compilation", status(len(grouped.get(ArtifactType.COMPILATION_ARTIFACT.value, [])), readiness_ready), len(grouped.get(ArtifactType.COMPILATION_ARTIFACT.value, [])), "M8 validated executable specification; only a matching M7-ready report can pass the workspace gate."),
            WorkflowStage("execution", "Simulation execution", status(len(execution_records), compilation), len(execution_records), "M9 reproducible execution records linked to exact M8 artifacts."),
            WorkflowStage("experimentation", "Comparative experimentation", status(len(grouped.get(ArtifactType.ANALYSIS_REPORT.value, [])), execution), len(grouped.get(ArtifactType.ANALYSIS_REPORT.value, [])), "M10 comparison, descriptive analysis and parameter-sweep reports."),
            WorkflowStage("uncertainty", "Uncertainty and robustness", status(len(grouped.get(ArtifactType.UNCERTAINTY_REPORT.value, [])), execution), len(grouped.get(ArtifactType.UNCERTAINTY_REPORT.value, [])), "M11 uncertainty distributions, sensitivity screening and robustness reports."),
            WorkflowStage("visualization", "Visualization", status(len(grouped.get(ArtifactType.VISUALIZATION_BUNDLE.value, [])), execution), len(grouped.get(ArtifactType.VISUALIZATION_BUNDLE.value, [])), "M12 provenance-checked visualization bundle and standalone dashboard."),
        ]

        if readiness_records and not readiness_ready and not compilation:
            stages[4] = WorkflowStage(
                "readiness", "Readiness assessment", StageStatus.COMPLETED, len(readiness_records),
                "Assessment completed; its result does not yet permit compilation.",
            )
        if execution_records and not execution:
            stages[6] = WorkflowStage(
                "execution", "Simulation execution", StageStatus.BLOCKED, len(execution_records),
                "Execution artifacts exist, but none contains a successful run.",
            )
        elif execution and not compilation:
            stages[6] = WorkflowStage(
                "execution", "Simulation execution", StageStatus.BLOCKED, len(execution_records),
                "Execution artifact is present but its compilation lineage is not represented.",
            )
        return tuple(stages)

    def overview(self) -> WorkspaceOverview:
        manifest = self.manifest
        return WorkspaceOverview(
            workspace_id=manifest.workspace_id, title=manifest.title,
            created_at=manifest.created_at, updated_at=manifest.updated_at,
            idea_project_id=manifest.idea_project_id, artifact_count=len(manifest.artifacts),
            stages=self.workflow_stages(), recent_activity=manifest.activity[-10:][::-1],
        )


class WorkspaceManager:
    """Create, discover and reopen project workspaces under one local directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, title: str, original_idea: str) -> ProjectWorkspace:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Project title must not be empty")
        if not isinstance(original_idea, str) or not original_idea.strip():
            raise ValueError("Original idea must not be empty")
        workspace_id = f"ws-{uuid4().hex[:12]}"
        directory = self.root / f"{_slug(title)}-{workspace_id}"
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "artifacts").mkdir()
        (directory / "notes").mkdir()
        created = _now()
        manifest = WorkspaceManifest(
            schema_version=1, workspace_id=workspace_id, title=title.strip(),
            created_at=created, updated_at=created, original_idea=original_idea.strip(),
            idea_project_id=None, artifacts=(),
            activity=(ActivityEvent(f"evt-{uuid4().hex[:12]}", created, "workspace_created", "Workspace created; original idea captured."),),
        )
        _atomic_write(directory / ProjectWorkspace.MANIFEST_NAME, dumps_manifest(manifest).encode("utf-8"))
        _atomic_write(directory / "original_idea.md", (original_idea.strip() + "\n").encode("utf-8"))
        return ProjectWorkspace(directory)

    def open(self, workspace_id: str) -> ProjectWorkspace:
        if not isinstance(workspace_id, str) or not re.fullmatch(r"ws-[a-f0-9]{12}", workspace_id):
            raise WorkspaceError("Invalid workspace ID")
        matches = [item for item in self.root.iterdir() if item.is_dir() and item.name.endswith("-" + workspace_id)]
        if len(matches) != 1:
            raise LookupError(f"Workspace {workspace_id!r} was not found")
        return ProjectWorkspace(matches[0])

    def import_zip(self, archive_path: str | Path) -> ProjectWorkspace:
        """Import a portable workspace archive with path and checksum validation."""
        source = Path(archive_path).expanduser().resolve()
        if not source.is_file():
            raise WorkspaceError(f"Workspace archive does not exist: {source}")
        # Keep the staging directory name very short: its path is a prefix for
        # every extracted member, and Windows MAX_PATH applies to the full
        # destination path, not just the temporary leaf filename.
        staging = Path(tempfile.mkdtemp(prefix=".i-", dir=self.root))
        try:
            with zipfile.ZipFile(source, "r") as archive:
                entries = archive.infolist()
                if not entries or len(entries) > 10000:
                    raise WorkspaceError("Workspace archive is empty or contains too many entries")
                total_size = sum(item.file_size for item in entries)
                if total_size > 1024 * 1024 * 1024:
                    raise WorkspaceError("Workspace archive exceeds the 1 GiB import limit")
                roots = set()
                seen_paths: set[str] = set()
                for item in entries:
                    member = Path(item.filename)
                    if (not item.filename or "\\" in item.filename or not member.parts
                            or ":" in member.parts[0] or member.is_absolute()
                            or ".." in member.parts):
                        raise WorkspaceError("Workspace archive contains an unsafe path")
                    normalized = member.as_posix().rstrip("/")
                    if normalized in seen_paths:
                        raise WorkspaceError("Workspace archive contains duplicate paths")
                    seen_paths.add(normalized)
                    roots.add(member.parts[0])
                    mode = (item.external_attr >> 16) & 0xFFFF
                    file_type = mode & 0o170000
                    if file_type == 0o120000:
                        raise WorkspaceError("Workspace archive contains a symbolic link")
                    if file_type not in (0, 0o100000, 0o040000):
                        raise WorkspaceError("Workspace archive contains an unsupported special file")
                if len(roots) != 1:
                    raise WorkspaceError("Workspace archive must contain exactly one top-level directory")
                root_name = next(iter(roots))
                for item in entries:
                    member = Path(item.filename)
                    destination = (staging / member).resolve()
                    try:
                        destination.relative_to(staging.resolve())
                    except ValueError as error:
                        raise WorkspaceError("Workspace archive path escapes the import directory") from error
                    if item.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        # Keep the temporary leaf name short. Appending a UUID to
                        # the full artifact filename can exceed Windows MAX_PATH
                        # during restoration even when the final artifact path fits.
                        descriptor, temporary_name = tempfile.mkstemp(
                            prefix=".i-", suffix=".tmp", dir=destination.parent
                        )
                        temporary = Path(temporary_name)
                        try:
                            with os.fdopen(descriptor, "wb") as writer, archive.open(item, "r") as reader:
                                shutil.copyfileobj(reader, writer, length=1024 * 1024)
                                writer.flush()
                                os.fsync(writer.fileno())
                            if temporary.stat().st_size != item.file_size:
                                raise WorkspaceIntegrityError("Imported ZIP member size does not match its directory record")
                            os.replace(temporary, destination)
                        finally:
                            temporary.unlink(missing_ok=True)
            imported_dir = staging / root_name
            candidate = ProjectWorkspace(imported_dir)
            checks = candidate.verify_artifacts()
            failures = [item for item in checks if not item.valid]
            if failures:
                raise WorkspaceIntegrityError("Imported workspace failed artifact verification")
            workspace_id = candidate.workspace_id
            if any(item.workspace_id == workspace_id for item in self.list_workspaces()):
                raise WorkspaceConflictError(f"Workspace {workspace_id!r} already exists in this workspace directory")
            destination = self.root / f"{_slug(candidate.manifest.title)}-{workspace_id}"
            if destination.exists():
                raise WorkspaceConflictError(f"Import destination already exists: {destination}")
            shutil.move(str(imported_dir), str(destination))
            return ProjectWorkspace(destination)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def list_workspaces(self) -> tuple[WorkspaceOverview, ...]:
        results = []
        for directory in sorted(self.root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if not directory.is_dir() or not (directory / ProjectWorkspace.MANIFEST_NAME).is_file():
                continue
            try:
                results.append(ProjectWorkspace(directory).overview())
            except WorkspaceError:
                continue
        return tuple(results)
