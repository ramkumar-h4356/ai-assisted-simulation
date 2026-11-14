"""M13 project lifecycle and integrated workspace services."""

from workbench.extensions import (
    BuiltInParadigmAdapter, ExtensionDescriptor, ExtensionRegistry,
    SimulationParadigmExtension, create_builtin_registry,
)
from workbench.models import (
    ActivityEvent, ArtifactRecord, ArtifactType, ArtifactVerification,
    StageStatus, WorkflowStage, WorkspaceManifest, WorkspaceOverview,
)
from workbench.serialization import (
    WorkspaceSerializationError, dumps_manifest, loads_manifest, manifest_from_dict,
    manifest_to_dict,
)
from workbench.validators import ArtifactValidationError, validate_artifact
from workbench.service import WorkbenchService
from workbench.workspace import (
    ProjectWorkspace, WorkspaceConflictError, WorkspaceError,
    WorkspaceIntegrityError, WorkspaceManager,
)

__all__ = [
    "ActivityEvent", "ArtifactRecord", "ArtifactType", "ArtifactValidationError",
    "ArtifactVerification", "BuiltInParadigmAdapter", "ExtensionDescriptor", "ExtensionRegistry",
    "ProjectWorkspace", "SimulationParadigmExtension", "StageStatus", "WorkflowStage",
    "WorkspaceConflictError", "WorkspaceError", "WorkspaceIntegrityError",
    "WorkspaceManifest", "WorkspaceOverview", "WorkspaceSerializationError",
    "WorkspaceManager", "WorkbenchService", "dumps_manifest", "loads_manifest", "manifest_from_dict",
    "manifest_to_dict", "validate_artifact", "create_builtin_registry",
]
