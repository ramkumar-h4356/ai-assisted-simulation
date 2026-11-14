# M13 Architecture — Integrated Project Workspace and Lifecycle

## Goal

M13 turns the existing M4–M12 components into a project-centred workbench. A user captures an original idea once, develops and maps its conceptual representation, assesses readiness, compiles a supported paradigm, runs experiments, reviews uncertainty, visualizes results and exports the complete project workspace.

M13 coordinates existing milestone services. It does not replace their model semantics, invent scientific rules or bypass their validation gates.

## Integrated workflow

```text
Create persistent workspace and capture immutable original idea
             |
             v
M6 interpretation and bounded clarification (or import existing M4/M6 files)
             |
             v
M4 conceptual project and append-only revisions
             |
             v
M5 local knowledge retrieval, candidate mappings and human review
             |
             v
M7 readiness assessment for supported paradigms
             |
             v
Import an explicit M8 compilation profile
             |
             v
M8 compile + native model validation (DES V1 / ABM V1)
             |
             v
M9 execution
             |
       +-----+---------------------+
       |                           |
       v                           v
M10 analysis / parameter       M11 uncertainty plan /
sweep                        sensitivity / robustness
       |                           |
       +-------------+-------------+
                     |
                     v
M12 provenance-checked visualization bundle and offline HTML dashboard
                     |
                     v
             Verify and export workspace ZIP
```

M6 can run inside the workbench using the existing Groq interpreter and `GROQ_API_KEY`; a stub or another provider can be injected programmatically. The original idea is the exact immutable text captured when the workspace is created. M5 uses the most recently imported knowledge base, or the bundled sample corpus if no custom corpus is present. Mapping candidates remain unreviewed until the user explicitly accepts or rejects them.

A user may also import existing M4 conceptual projects, M6 sessions, M5 knowledge bases and other milestone artifacts. Imported source files are copied; the source files are not moved or changed.

## Package responsibilities

- `workbench/models.py`: typed artifact categories, manifest, artifact ledger, activity and workflow progress records.
- `workbench/serialization.py`: strict schema-versioned JSON serialization; rejects unknown and missing manifest fields.
- `workbench/validators.py`: format-specific validation adapters for M4, M5, M6, M7, M8, M9, M10, M11 and M12 artifacts.
- `workbench/workspace.py`: workspace creation, reopening, immutable idea copy, artifact storage, checksums, project/revision lineage checks, activity history, ZIP import/export and integrity checks.
- `workbench/extensions.py`: explicit, trusted simulation-paradigm extension descriptor, lifecycle protocol and registry. Built-in adapters are registered for the implemented DES V1 and ABM V1 paths.
- `workbench/service.py`: M5/M6 project integration and project-scoped M7–M12 orchestration.
- `workbench/cli.py`: project-centred interactive workbench, also available from the main menu.

## Workspace layout

```text
workspaces/
  <slug>-<workspace-id>/
    workspace.json           # schema-versioned manifest and artifact ledger
    original_idea.md          # human-readable copy checked against manifest
    artifacts/
      idea_project/
      idea_session/
      knowledge_base/
      readiness_report/
      compilation_profile/
      compilation_artifact/
      execution_result/
      analysis_report/
      uncertainty_plan/
      uncertainty_report/
      visualization_bundle/
      visualization_html/
      other/
    notes/
```

The manifest stores the workspace ID, title, timestamps, immutable original idea, associated conceptual project ID, artifact records and a bounded activity history. Each artifact record stores its type, display name, relative path, byte size, UTC import time, SHA-256 digest and extracted provenance metadata. The workbench copies artifacts into the workspace and verifies the copies.

## Artifact validation and lineage

Known artifact types are loaded through the originating milestone serializers. The workbench adds a SHA-256 digest and byte-size check around every copied or generated artifact.

The workspace enforces the following rules:

- An M4 project must preserve the exact original statement captured by the workspace.
- M5 knowledge bases are validated using the M5 corpus schema.
- M6 sessions, M7 reports, M8 profiles/artifacts, M9 results and M10/M11/M12 artifacts must belong to the workspace's conceptual project where the source format carries project identity.
- Project-scoped artifacts may reference only a revision present in the saved conceptual revision history.
- An M8 compiled artifact must record an M7-ready status and have a matching ready M7 report for the same project, revision and paradigm.
- An M9 result must point to the exact M8 artifact and fingerprint stored in the workspace.
- M10 reports must reference execution IDs and result fingerprints already in the workspace.
- M11 reports and M12 bundles must reference the exact matching M9 result and M8 artifact fingerprints.
- Workspace ZIP import rejects unsafe paths, duplicate paths, symbolic links, special files, multiple roots and archives above the configured size limit.
- Artifact paths are resolved and checked to remain inside the workspace directory.

An M7 assessment can complete while still concluding that a model is not executable. The workbench distinguishes an assessment being completed from a paradigm being ready for compilation.

## Simulation extension boundary

`ExtensionDescriptor`, `SimulationParadigmExtension` and `ExtensionRegistry` define the controlled extension point. A trusted application component registers an adapter that declares a stable ID, version, paradigm, supported model-schema versions and required lifecycle capabilities (`validate`, `compile`, `execute`, `serialize_result`, `validate_result`). Duplicate extension IDs and duplicate active paradigm registrations are rejected.

The current registry contains adapters for the existing DES V1 and ABM V1 M7/M8/M9 workflows. Mathematical and data-driven paradigms are not advertised as executable because their engines are not implemented. The registry is explicit: M13 does not dynamically import third-party code. Integrating a future engine requires implementing and testing its model schema, semantic validation, compiler, executor, result serializer and any needed M10–M12 adapters. A wholly new paradigm outside the currently declared M7/M8 paradigm identifiers may also require a deliberate schema/enum evolution.

## Operational entry points

- `python main.py`, then choose option `17`.
- `python -m workbench`.
- Programmatic integration: `WorkbenchService(workspace)`.

The workbench can create/open/list projects; run M6 interpretation/clarification; run M5 knowledge retrieval and explicit mapping review; import M4/M5/M6/M7/M8/M9/M10/M11/M12 files; assess M7 readiness; compile an imported M8 profile; execute the resulting DES/ABM artifact; run M10 parameter sweeps and analysis; run M11 uncertainty analysis; build M12 bundles and offline HTML dashboards; verify files; and export/import a portable ZIP.

M8 profiles remain explicit user-approved inputs. The workbench does not silently infer executable model details from an M6 idea or manufacture missing parameters.

## Integrity, portability and privacy

- Manifest and copied artifact writes use temporary files followed by atomic replacement.
- The readable `original_idea.md` copy is checked against the manifest's immutable source text when a workspace opens.
- Artifact hashes and byte sizes are verified before ZIP export and on demand.
- ZIP imports validate paths and file types before extraction, stream data to disk, and verify imported artifacts before registration.
- Local workspace data is stored under the Git-ignored `workspaces/` directory and is not included in the source-code ZIP.
- Exported workspace ZIPs contain user ideas, model data and simulation outputs. Users should store and share them with appropriate care.

## Explicit M13 exclusions

M13 delivers a local project workbench, not the planned full web application or a real-time spatial 2D renderer. It does not implement mathematical or data-driven simulation execution, automatic ML rule discovery, arbitrary universal simulation grammar, live third-party plugin loading or scientific proof/validation of a theory. Those remain separately scoped future capabilities.
