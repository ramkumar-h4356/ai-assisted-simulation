# M13 Project Workbench

The `workbench/` package provides a persistent, resumable project workspace around the existing M4–M12 capabilities.

## Start

```bash
python -m workbench
```

Or run `python main.py` and choose option **17**.

## Typical workflow

1. Create a workspace and capture the original idea. The original statement is immutable within that workspace.
2. Run M6 interpretation and clarification directly from the workspace. The existing Groq interpreter uses `GROQ_API_KEY`; alternatively, inject another `IdeaInterpreter` in code. You may instead import an existing M4 conceptual project and M6 session.
3. Run M5 mapping from a selected concept. By default it uses `knowledge/sample_knowledge_base.json`. Import a custom M5 knowledge-base JSON corpus to use that corpus instead. Retrieved mappings are proposals; explicitly accept or reject them.
4. Run M7 readiness assessment for the desired paradigm.
5. Import an explicit M8 compilation profile bound to the current project revision and selected paradigm. M13 does not fabricate missing model rules or parameters.
6. Compile the profile and execute the validated DES or ABM artifact inside the workspace.
7. Run M10 analysis/parameter sweeps, M11 uncertainty analysis and M12 visualization. Generated artifacts are stored automatically.
8. Verify artifact integrity and export the workspace as a ZIP.

## Programmatic use

```python
from workbench import WorkspaceManager, WorkbenchService

manager = WorkspaceManager("workspaces")
workspace = manager.create(
    "Community resource sharing",
    "A community coordinates access to a shared resource.",
)
service = WorkbenchService(workspace)

# M6 can use its default Groq interpreter, or accept an injected provider.
# result, project_record, session_record = service.formalize_idea(interpreter=my_interpreter)

# After a conceptual project has been created/imported:
# candidates = service.suggest_mappings("shared-resource")
# updated_project, mapping_record = service.record_mapping_candidate(candidates[0])
# report, readiness_record = service.assess("agent_based")
```

`WorkbenchService.formalize_idea()` runs the existing M6 service against the workspace's original idea and saves both the M4 project and M6 session. It refuses to create a second independent conceptual project in the same workspace; use a new workspace to preserve unambiguous project identity.

`WorkbenchService.suggest_mappings()` and `record_mapping_candidate()` use the M5 retrieval and mapping services. `review_mapping()` creates a new conceptual revision containing the explicit accept/reject decision.

## Workspace API

- `WorkspaceManager.create(title, original_idea)` creates a local workspace.
- `WorkspaceManager.list_workspaces()` lists resumable workspaces.
- `WorkspaceManager.open(workspace_id)` reopens an existing workspace.
- `ProjectWorkspace.add_artifact(path, artifact_type)` validates and copies an artifact.
- `ProjectWorkspace.verify_artifacts()` verifies stored file sizes and SHA-256 digests.
- `ProjectWorkspace.export_zip(path)` exports an integrity-checked workspace.
- `WorkspaceManager.import_zip(path)` safely imports and verifies a portable workspace.
- `ProjectWorkspace.overview()` returns current workflow progress and recent activity.

Known import types are defined by `ArtifactType`, including conceptual projects, M6 sessions, M5 knowledge bases, readiness reports, compilation profiles/artifacts, execution results, experiment reports, uncertainty plans/reports and visualization bundles/HTML dashboards.

## Provenance and execution gates

Each workspace is bound to one conceptual project ID and its immutable original statement. Revision references are checked against the project's saved history. An M8 compiled artifact requires a matching M7-ready report for the same revision and paradigm. M9 results must reference the exact M8 artifact; M10/M11/M12 records must match the corresponding execution fingerprints.

M7 readiness assessment is not a truth test. It determines whether the model is sufficiently specified for a particular supported paradigm. A completed readiness assessment may still report blockers.

## Extension point

`workbench/extensions.py` defines the controlled paradigm adapter protocol and explicit registry. The built-in registry exposes the currently executable DES V1 and ABM V1 adapters. Registration is performed by trusted application code; M13 does not dynamically load arbitrary third-party Python packages. A future engine must supply its own schema, validation, compilation, execution and result serialization, and the host must provide any M10–M12 integration needed for its outputs.

## Data, boundaries and security

Local workspace data is saved under `<project-root>/workspaces/`, which is Git-ignored. It is not included in a source-code ZIP unless the user explicitly exports the workspace separately. Workspace exports can contain sensitive ideas or proprietary data.

M13 is a local CLI/service workbench. It does not include the full web application, live spatial 2D renderer, mathematical/data-driven engines or ML rule-discovery model. M8 compilation profiles are explicit inputs; the workbench does not invent missing operational rules.
