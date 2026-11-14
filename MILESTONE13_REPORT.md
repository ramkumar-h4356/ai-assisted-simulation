# Milestone 13 Report — Integrated Project Workspace and Lifecycle

## Status

M13 delivers a persistent local project workbench that coordinates the existing M4–M12 services. It adds a workspace lifecycle, integrated M5/M6 entry points, project-scoped M7–M12 workflows, integrity checks, portability and an explicit simulation-paradigm extension point.

## What was implemented

### 1. Persistent project workspaces

- Create, list, open and resume local workspaces.
- Capture the original idea as immutable workspace source text.
- Keep a checked human-readable `original_idea.md` copy.
- Store milestone artifacts under a workspace-local artifact ledger.
- Retain bounded, timestamped activity history and workflow progress.

### 2. M5 and M6 integrated entry points

- Run the existing M6 `IdeaAssistantService` against the workspace's original idea.
- Use the existing Groq interpreter by default, with `GROQ_API_KEY`; allow an injected interpreter for other providers and tests.
- Store the M4 conceptual project and M6 clarification session automatically.
- Run M5 retrieval against the bundled sample corpus or a custom imported M5 knowledge base.
- Record mapping candidates as unreviewed conceptual revisions, then preserve explicit accept/reject decisions as later revisions.
- Preserve evidence references, mapping types and the M5 source/review provenance. Retrieval relevance is not treated as confidence or proof.

### 3. Typed artifact intake and lineage checks

- Validate known artifact files through their originating milestone serializers.
- Copy-on-import; original source files remain unchanged.
- Record SHA-256 digest and byte size for every imported/generated artifact.
- Check project ID and conceptual revision lineage.
- Require a matching M7-ready report for the same project, revision and paradigm before storing an M8 compiled artifact.
- Require exact M8 artifact and fingerprint lineage for M9; exact M9 experiment/result fingerprints for M10, M11 and M12 records.
- Reject unsafe workspace-relative paths and verify artifact integrity before export.

### 4. Project-scoped orchestration

- Run M7 readiness assessment.
- Compile an imported M8 profile through the registered paradigm adapter.
- Execute an M8 artifact through DES/ABM adapters.
- Run M10 parameter sweeps and descriptive analysis.
- Run M11 uncertainty plans.
- Build and save M12 visualization bundles and offline HTML dashboards.
- Automatically register generated artifacts in the active workspace.

M8 profiles remain explicit user-approved inputs. M13 does not silently generate executable rules or bypass readiness and model validation.

### 5. Extensible paradigm boundary

- Define an explicit full-lifecycle adapter protocol and extension descriptor/registry.
- Register the existing DES V1 and ABM V1 adapters.
- Reject incomplete adapters, duplicate IDs and duplicate active paradigm registrations.
- Do not advertise mathematical or data-driven execution before those engines exist.
- Do not dynamically import third-party code.

### 6. Portability and safety

- Atomic manifest and artifact writes.
- SHA-256 and byte-size verification.
- Portable ZIP export after integrity verification.
- Guarded ZIP import with traversal, duplicate-path, symlink, special-file, multi-root and size checks; archive members are streamed to disk rather than read wholly into memory.
- Local `workspaces/` is Git-ignored and is excluded from the source archive.

## Verification summary

See `M13_TEST_REPORT.md` for exact commands and limitations. The M13-focused suite verifies workspace creation/reopening, M4/M5/M6 artifact flows, M7–M12 orchestration, extension registration, ZIP import/export and corruption/path rejection. The non-DES regression suite is run separately because this environment does not have the optional DES/AI dependencies `simpy` and `groq` installed and network access prevented installation.

A full DES/Groq run and live Groq API verification were not completed in this environment; they are not counted as successful tests.

## Operational entry points

- `python main.py` → option `17`.
- `python -m workbench`.
- Programmatic service: `WorkbenchService(workspace)`.

## Boundaries

M13 provides a local CLI/service workbench. It does not deliver the planned full web application, real-time spatial 2D renderer, mathematical engine, data-driven engine, trained rule-discovery model or scientific proof/validation of theories. The extension registry is explicit and controlled; new paradigms still need their own complete engine/validation implementation and any host schema integration required by that paradigm.
