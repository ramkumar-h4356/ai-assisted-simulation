"""Interactive M13 project workbench over the existing M4-M12 services."""

from __future__ import annotations

import json
from pathlib import Path
import webbrowser

from conceptual.model import MappingType, ReviewStatus
from execution import ExperimentConfig
from experimentation import GridFactor
from readiness import Paradigm
from workbench import ArtifactType, WorkspaceError, WorkspaceManager, WorkbenchService


_ARTIFACT_OPTIONS = (
    (ArtifactType.IDEA_PROJECT, "M4 conceptual idea project"),
    (ArtifactType.IDEA_SESSION, "M6 idea-assistant session"),
    (ArtifactType.KNOWLEDGE_BASE, "M5 knowledge base (JSON corpus)"),
    (ArtifactType.READINESS_REPORT, "M7 readiness report"),
    (ArtifactType.COMPILATION_PROFILE, "M8 compilation profile"),
    (ArtifactType.COMPILATION_ARTIFACT, "M8 compiled specification"),
    (ArtifactType.EXECUTION_RESULT, "M9 execution result"),
    (ArtifactType.ANALYSIS_REPORT, "M10 comparative analysis"),
    (ArtifactType.UNCERTAINTY_PLAN, "M11 uncertainty plan"),
    (ArtifactType.UNCERTAINTY_REPORT, "M11 uncertainty report"),
    (ArtifactType.VISUALIZATION_BUNDLE, "M12 visualization bundle"),
    (ArtifactType.VISUALIZATION_HTML, "M12 standalone HTML dashboard"),
    (ArtifactType.OTHER, "Other project document / file"),
)


def _print_overview(workspace) -> None:
    overview = workspace.overview()
    print(f"\n=== {overview.title} ===")
    print(f"Workspace ID: {overview.workspace_id}")
    print(f"Idea project ID: {overview.idea_project_id or 'Not linked yet'}")
    print(f"Artifacts: {overview.artifact_count}")
    print("\nWorkflow progress:")
    for stage in overview.stages:
        print(f"  [{stage.status.value:11}] {stage.title:<34} artifacts={stage.artifact_count}")
        print(f"               {stage.explanation}")
    if overview.recent_activity:
        print("\nRecent activity:")
        for event in overview.recent_activity[:5]:
            print(f"  {event.occurred_at}  {event.action}: {event.detail}")


def _list_workspaces(manager: WorkspaceManager) -> None:
    items = manager.list_workspaces()
    if not items:
        print("No project workspaces have been created yet.")
        return
    print("\nSaved workspaces:")
    for index, item in enumerate(items, start=1):
        complete = sum(stage.status.value == "completed" for stage in item.stages)
        print(f"  {index}. {item.title} | {item.workspace_id} | {item.artifact_count} artifacts | {complete}/{len(item.stages)} stages")


def _records(workspace, kind: ArtifactType, label: str):
    items = workspace.artifacts(kind)
    if not items:
        print(f"No {label} artifacts are stored in this workspace yet.")
        return None
    print(f"\n{label}:")
    for index, item in enumerate(items, start=1):
        print(f"  {index}. {item.display_name} | {item.artifact_id}")
    selection = input("Select number (Enter to cancel): ").strip()
    if not selection:
        return None
    try:
        return items[int(selection) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return None


def _import_artifact(workspace) -> None:
    print("\nArtifact type:")
    for index, (kind, label) in enumerate(_ARTIFACT_OPTIONS, start=1):
        print(f"  {index}. {label} ({kind.value})")
    choice = input("Choose artifact type: ").strip()
    try:
        kind, label = _ARTIFACT_OPTIONS[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid artifact type selection.")
        return
    source = input("Path to artifact file: ").strip().strip('"')
    if not source:
        print("No file selected.")
        return
    display_name = input(f"Display name [{Path(source).stem}]: ").strip() or None
    try:
        record = workspace.add_artifact(source, kind, display_name=display_name)
    except (WorkspaceError, OSError) as error:
        print(f"Import failed: {error}")
        return
    print(f"Imported {label}.")
    print(f"Artifact ID: {record.artifact_id}")
    print(f"Stored at: {workspace.directory / record.relative_path}")
    print(f"SHA-256: {record.sha256}")


def _run_idea_interpretation(workspace, service: WorkbenchService) -> None:
    if workspace.manifest.idea_project_id is not None:
        print("This workspace already contains a conceptual project. Reinterpretation should start in a separate workspace so its lineage remains unambiguous.")
        return

    def collect_answers(questions):
        print("\n--- Clarification questions ---")
        answers = {}
        for index, question in enumerate(questions, start=1):
            print(f"\n{index}. [{question.priority.upper()}] {question.question}")
            if question.reason:
                print(f"   Why it matters: {question.reason}")
            answer = input("   Your answer (Enter to leave unresolved): ").strip()
            if answer:
                answers[question.id] = answer
        return answers

    print("\nM6 will interpret the original idea stored in this workspace.")
    print("AI-generated elements remain proposals; unresolved questions are preserved.")
    try:
        result, project_record, session_record = service.formalize_idea(
            clarification_handler=collect_answers,
        )
    except Exception as error:
        print(f"M6 interpretation failed: {error}")
        print("Check GROQ_API_KEY and the network connection, or import an existing M4 project artifact.")
        return

    revision = result.project.current_revision
    print("\nConceptual interpretation saved.")
    print(f"Title: {result.project.title}")
    print(f"Working statement: {revision.working_statement}")
    print(f"Concepts: {len(revision.concepts)} | Mechanisms: {len(revision.mechanisms)} | Open questions: {len(revision.open_questions)}")
    print(f"M4 project artifact: {project_record.artifact_id}")
    print(f"M6 session artifact: {session_record.artifact_id}")
    print(f"Conceptual validation: {result.validation_report.readiness.value}")
    for item in result.validation_report.errors:
        print(f"  [error] {item.path}: {item.message}")

def _run_mapping(service: WorkbenchService) -> None:
    try:
        project = service.current_idea_project()
    except WorkspaceError as error:
        print(f"M5 mapping cannot run: {error}")
        return
    concepts = project.current_revision.concepts
    if not concepts:
        print("The current conceptual revision has no concepts to map.")
        return

    print("\nConcepts in the current revision:")
    for index, concept in enumerate(concepts, start=1):
        print(f"  {index}. {concept.name} [{concept.id}]")
    choice = input("Select a concept number: ").strip()
    try:
        concept = concepts[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid concept selection.")
        return

    query = input("Search query (Enter uses the concept definition): ").strip() or None
    try:
        candidates = service.suggest_mappings(concept.id, query=query, limit=5)
    except Exception as error:
        print(f"M5 retrieval failed: {error}")
        return
    if not candidates:
        print("No mapping candidates were found. Try a broader query or import a richer M5 knowledge base.")
        return

    print("\nRetrieved candidates (lexical relevance is not confidence or proof):")
    for index, candidate in enumerate(candidates, start=1):
        print(f"\n{index}. {candidate.target_label}")
        print(f"   Source document: {candidate.document_id}")
        print(f"   Relevance: {candidate.relevance_score:.4f} | Matched terms: {', '.join(candidate.matched_terms)}")
        print(f"   Rationale: {candidate.rationale}")

    selection = input("Record candidate number (Enter to cancel): ").strip()
    if not selection:
        return
    try:
        candidate = candidates[int(selection) - 1]
    except (ValueError, IndexError):
        print("Invalid candidate selection.")
        return

    mapping_types = tuple(MappingType)
    print("\nMapping classification:")
    for index, kind in enumerate(mapping_types, start=1):
        print(f"  {index}. {kind.value}")
    mapping_choice = input("Select classification [2 = analogous]: ").strip()
    try:
        mapping_type = mapping_types[int(mapping_choice) - 1] if mapping_choice else MappingType.ANALOGOUS
    except (ValueError, IndexError):
        print("Invalid mapping classification.")
        return

    try:
        updated, record = service.record_mapping_candidate(candidate, mapping_type=mapping_type)
    except Exception as error:
        print(f"Could not record the mapping: {error}")
        return
    mapping_id = f"mapping-{candidate.id}"
    print(f"Recorded as unreviewed in revision {updated.current_revision.version}.")
    print(f"Conceptual project artifact: {record.artifact_id}")
    decision = input("Review now? [a]ccept / [r]eject / Enter to leave unreviewed: ").strip().lower()
    if decision in {"a", "r"}:
        status = ReviewStatus.ACCEPTED if decision == "a" else ReviewStatus.REJECTED
        note = input("Reviewer note (optional): ").strip()
        try:
            reviewed, reviewed_record = service.review_mapping(mapping_id, status, reviewer_note=note)
        except Exception as error:
            print(f"Mapping review could not be saved: {error}")
            return
        print(f"Mapping {status.value}; revision {reviewed.current_revision.version} saved as {reviewed_record.artifact_id}.")
    else:
        print("Mapping remains unreviewed. It is not treated as an accepted fact.")

def _run_readiness(service: WorkbenchService) -> None:
    print("\nM7 readiness assessment")
    print("1. Assess all paradigms")
    for index, paradigm in enumerate(Paradigm, start=2):
        print(f"{index}. Assess {paradigm.value}")
    choice = input("Select assessment (1-5): ").strip()
    try:
        paradigm = None if choice == "1" else tuple(Paradigm)[int(choice) - 2]
        report, record = service.assess(paradigm)
    except (ValueError, IndexError, WorkspaceError) as error:
        print(f"Assessment could not run: {error}")
        return
    print(f"Assessment status: {report.status.value}")
    print(f"Saved report: {record.artifact_id}")
    print(report.explanation)
    for item in report.clarification_items:
        marker = "BLOCKING" if item.blocking else "NON-BLOCKING"
        print(f"  [{marker}] {item.question}")


def _run_compile(workspace, service: WorkbenchService) -> None:
    record = _records(workspace, ArtifactType.COMPILATION_PROFILE, "M8 profiles")
    if record is None:
        return
    try:
        result, stored = service.compile(record.artifact_id)
    except Exception as error:
        print(f"Compilation failed: {error}")
        return
    if not result.is_ready:
        print("Compilation did not produce an executable artifact.")
        for issue in result.issues:
            print(f"  [{issue.severity.value}] {issue.code}: {issue.message}")
        return
    print(f"Compiled and validated: {stored.artifact_id}")
    print(f"Paradigm: {stored.metadata.get('paradigm')} | Backend: {stored.metadata.get('backend_name')}")


def _run_execution(workspace, service: WorkbenchService) -> None:
    record = _records(workspace, ArtifactType.COMPILATION_ARTIFACT, "M8 compiled specifications")
    if record is None:
        return
    try:
        runs_text = input("Replications [1]: ").strip()
        runs = int(runs_text) if runs_text else 1
        if record.metadata.get("paradigm") == "agent_based":
            seed_text = input("Base random seed (blank for model default): ").strip()
            seed = int(seed_text) if seed_text else None
        else:
            print("DES V1 is deterministic; no random seed is used.")
            seed = None
        result, stored = service.execute(record.artifact_id, ExperimentConfig(runs=runs, base_seed=seed))
    except Exception as error:
        print(f"Execution failed: {error}")
        return
    successes = sum(item.status.value == "completed" for item in result.runs)
    print(f"Execution {result.status.value}: {successes}/{len(result.runs)} successful runs")
    print(f"Saved M9 result: {stored.artifact_id}")


def _load_grid_factors(path_text: str) -> tuple[GridFactor, ...]:
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Grid-factor JSON must contain a top-level array")
    return tuple(GridFactor(target_path=item["target_path"], levels=tuple(item["levels"])) for item in raw)


def _run_parameter_sweep(workspace, service: WorkbenchService) -> None:
    record = _records(workspace, ArtifactType.COMPILATION_ARTIFACT, "M8 compiled specifications")
    if record is None:
        return
    factor_path = input("Path to JSON grid-factor file: ").strip().strip('"')
    if not factor_path:
        return
    try:
        factors = _load_grid_factors(factor_path)
        runs_text = input("Replications per variant [1]: ").strip()
        runs = int(runs_text) if runs_text else 1
        if record.metadata.get("paradigm") == "agent_based":
            seed_text = input("Base random seed (blank for model default): ").strip()
            seed = int(seed_text) if seed_text else None
        else:
            print("DES V1 is deterministic; no random seed is used.")
            seed = None
        include_text = input("Include baseline? [Y/n]: ").strip().lower()
        result, report, result_record, report_record = service.parameter_sweep(
            record.artifact_id, factors, runs=runs, base_seed=seed,
            include_baseline=include_text not in {"n", "no"},
        )
    except Exception as error:
        print(f"Parameter sweep failed: {error}")
        return
    print(f"M9 result saved: {result_record.artifact_id}")
    print(f"M10 comparison saved: {report_record.artifact_id}")
    print(f"Variants: {len(report.variants)} | Runs: {len(result.runs)}")


def _run_analysis(workspace, service: WorkbenchService) -> None:
    record = _records(workspace, ArtifactType.EXECUTION_RESULT, "M9 execution results")
    if record is None:
        return
    try:
        report, stored = service.analyze_result(record.artifact_id)
    except Exception as error:
        print(f"Analysis failed: {error}")
        return
    print(f"M10 analysis saved: {stored.artifact_id}")
    print(f"Variants compared: {len(report.variants)}")


def _run_uncertainty(workspace, service: WorkbenchService) -> None:
    artifact = _records(workspace, ArtifactType.COMPILATION_ARTIFACT, "M8 compiled specifications")
    if artifact is None:
        return
    plan = _records(workspace, ArtifactType.UNCERTAINTY_PLAN, "M11 uncertainty plans")
    if plan is None:
        return
    try:
        if artifact.metadata.get("paradigm") == "agent_based":
            seed_text = input("Execution base seed (blank for model default): ").strip()
            seed = int(seed_text) if seed_text else None
        else:
            print("DES V1 is deterministic; no random seed is used.")
            seed = None
        result, report, result_record, report_record = service.uncertainty_analysis(
            artifact.artifact_id, plan.artifact_id, execution_base_seed=seed,
        )
    except Exception as error:
        print(f"Uncertainty analysis failed: {error}")
        return
    print(f"M9 sample execution saved: {result_record.artifact_id}")
    print(f"M11 uncertainty report saved: {report_record.artifact_id}")
    print(f"Samples: {report.sample_count} | Failed executions: {report.failed_runs}")


def _build_visualization(workspace, service: WorkbenchService) -> None:
    experiment = _records(workspace, ArtifactType.EXECUTION_RESULT, "M9 execution results")
    if experiment is None:
        return
    print("Optional analysis reports must refer to this exact M9 result.")
    analysis_id = None
    analyses = workspace.artifacts(ArtifactType.ANALYSIS_REPORT)
    if analyses:
        analysis = _records(workspace, ArtifactType.ANALYSIS_REPORT, "M10 reports")
        analysis_id = analysis.artifact_id if analysis else None
    uncertainty_id = None
    uncertainties = workspace.artifacts(ArtifactType.UNCERTAINTY_REPORT)
    if uncertainties:
        uncertainty = _records(workspace, ArtifactType.UNCERTAINTY_REPORT, "M11 reports")
        uncertainty_id = uncertainty.artifact_id if uncertainty else None
    try:
        bundle, bundle_record, html_record = service.build_visualization(
            experiment.artifact_id, analysis_artifact_id=analysis_id,
            uncertainty_artifact_id=uncertainty_id,
        )
    except Exception as error:
        print(f"Visualization could not be built: {error}")
        return
    html_path = workspace.directory / html_record.relative_path
    print(f"Visualization bundle: {bundle_record.artifact_id}")
    print(f"Standalone dashboard: {html_path}")
    if input("Open dashboard in your browser? [Y/n]: ").strip().lower() not in {"n", "no"}:
        webbrowser.open(html_path.as_uri())


def _list_artifacts(workspace) -> None:
    records = workspace.artifacts()
    if not records:
        print("No milestone artifacts have been imported or generated yet.")
        return
    print("\nWorkspace artifacts:")
    for item in records:
        print(f"  {item.artifact_type:<23} {item.artifact_id}  {item.display_name}")
        print(f"      {item.relative_path} ({item.size_bytes} bytes)")


def _verify(workspace) -> None:
    checks = workspace.verify_artifacts()
    if not checks:
        print("Workspace has no artifact files to verify.")
    for item in checks:
        status = "OK" if item.valid else "FAILED"
        print(f"  [{status}] {item.relative_path}: {item.message}")
    print(f"Verified {sum(item.valid for item in checks)}/{len(checks)} files.")


def _open_workspace(workspace) -> None:
    service = WorkbenchService(workspace)
    while True:
        _print_overview(workspace)
        print("\nProject actions")
        print("1. Run M6 idea interpretation and clarification")
        print("2. Import milestone artifact / M5 knowledge base")
        print("3. Run M5 knowledge mapping and review")
        print("4. Run M7 readiness assessment")
        print("5. Compile an M8 specification from an imported profile")
        print("6. Run M9 simulation")
        print("7. Run M10 parameter sweep")
        print("8. Create M10 analysis from an M9 result")
        print("9. Run M11 uncertainty analysis")
        print("10. Build M12 visualization and dashboard")
        print("11. List workspace artifacts")
        print("12. Verify workspace integrity")
        print("13. Export workspace as ZIP")
        print("14. Return to workspace list")
        choice = input("Choose an action (1-14): ").strip()
        if choice == "1":
            _run_idea_interpretation(workspace, service)
        elif choice == "2":
            _import_artifact(workspace)
        elif choice == "3":
            _run_mapping(service)
        elif choice == "4":
            _run_readiness(service)
        elif choice == "5":
            _run_compile(workspace, service)
        elif choice == "6":
            _run_execution(workspace, service)
        elif choice == "7":
            _run_parameter_sweep(workspace, service)
        elif choice == "8":
            _run_analysis(workspace, service)
        elif choice == "9":
            _run_uncertainty(workspace, service)
        elif choice == "10":
            _build_visualization(workspace, service)
        elif choice == "11":
            _list_artifacts(workspace)
        elif choice == "12":
            _verify(workspace)
        elif choice == "13":
            destination = input("ZIP export destination: ").strip().strip('"')
            if destination:
                try:
                    print(f"Exported: {workspace.export_zip(destination)}")
                except Exception as error:
                    print(f"Export failed: {error}")
        elif choice == "14":
            return
        else:
            print("Choose a number from 1 to 14.")


def run_workbench(root: str | Path | None = None) -> None:
    """Run the project-centric M13 workspace manager."""
    project_root = Path(__file__).resolve().parent.parent
    manager = WorkspaceManager(root or (project_root / "workspaces"))
    print("\n=== M13 Project Workbench ===")
    print("Create a project once, then keep conceptual, readiness, compilation, execution, analysis and visualization artifacts together.")
    while True:
        print("\n1. Create project workspace")
        print("2. Open existing workspace")
        print("3. List workspaces")
        print("4. Return to main menu")
        choice = input("Choose an option (1-4): ").strip()
        if choice == "1":
            title = input("Project title: ").strip()
            idea = input("Original idea / problem statement: ").strip()
            try:
                workspace = manager.create(title, idea)
            except (ValueError, OSError) as error:
                print(f"Could not create workspace: {error}")
                continue
            print(f"Created workspace {workspace.workspace_id}")
            print(f"Workspace directory: {workspace.directory}")
            print("Next: run M6 idea interpretation from this workspace. Its conceptual project and session will be saved here automatically.")
            _open_workspace(workspace)
        elif choice == "2":
            _list_workspaces(manager)
            workspace_id = input("Workspace ID: ").strip()
            try:
                workspace = manager.open(workspace_id)
            except (LookupError, WorkspaceError) as error:
                print(f"Could not open workspace: {error}")
                continue
            _open_workspace(workspace)
        elif choice == "3":
            _list_workspaces(manager)
        elif choice == "4":
            return
        else:
            print("Choose a number from 1 to 4.")
