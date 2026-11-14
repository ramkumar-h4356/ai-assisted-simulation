"""Project-scoped orchestration across the existing M7-M12 workflows (M13)."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from compilation import load_artifact, load_profile, save_artifact
from conceptual import load_idea_project, save_idea_project
from conceptual.model import MappingType, ReviewStatus
from execution import ExperimentConfig, load_result, save_result
from experimentation import GridFactor, analyze_results, load_report as load_analysis_report, run_parameter_sweep, save_report as save_analysis_report
from readiness import Paradigm, assess_readiness, save_report as save_readiness_report
from uncertainty import load_plan, load_report as load_uncertainty_report, run_uncertainty_analysis, save_report as save_uncertainty_report
from visualization import build_visualization_bundle, load_bundle, save_bundle, save_html

from workbench.models import ArtifactType
from workbench.workspace import ProjectWorkspace, WorkspaceConflictError, WorkspaceError


class WorkbenchService:
    """Run supported simulation workflows and persist every result in a workspace.

    The service deliberately delegates model semantics to the existing M4-M12
    packages. It coordinates project identity, artifact storage and provenance;
    it does not invent missing conceptual rules or bypass readiness gates.
    """

    def __init__(self, workspace: ProjectWorkspace, *, extension_registry=None) -> None:
        if not isinstance(workspace, ProjectWorkspace):
            raise TypeError("workspace must be a ProjectWorkspace")
        self.workspace = workspace
        if extension_registry is None:
            from workbench.extensions import create_builtin_registry
            extension_registry = create_builtin_registry()
        self.extension_registry = extension_registry

    def _idea_project(self):
        records = self.workspace.artifacts(ArtifactType.IDEA_PROJECT)
        if not records:
            raise WorkspaceError("Import an M4 conceptual idea project before running this workflow")
        return load_idea_project(self.workspace.artifact_path(records[-1].artifact_id))

    def current_idea_project(self):
        """Return the latest conceptual project stored in this workspace."""
        return self._idea_project()

    def _knowledge_base(self):
        """Load the latest workspace corpus, or the bundled M5 sample corpus."""
        from knowledge import load_knowledge_base

        records = self.workspace.artifacts(ArtifactType.KNOWLEDGE_BASE)
        if records:
            return load_knowledge_base(self.workspace.artifact_path(records[-1].artifact_id))
        default_path = Path(__file__).resolve().parent.parent / "knowledge" / "sample_knowledge_base.json"
        if default_path.is_file():
            return load_knowledge_base(default_path)
        return None

    def formalize_idea(
        self,
        *,
        interpreter=None,
        clarification_handler=None,
        max_clarification_rounds: int = 3,
        max_questions_per_round: int = 3,
    ):
        """Run M6 against the workspace's immutable idea and save M4/M6 outputs.

        An interpreter can be injected for local providers and tests. Without one,
        the existing Groq interpreter is selected lazily and uses GROQ_API_KEY.
        """
        if self.workspace.manifest.idea_project_id is not None:
            raise WorkspaceConflictError(
                "This workspace already has a conceptual project. Create a new workspace to reinterpret the original idea independently."
            )
        from idea_assistant import GroqIdeaInterpreter, IdeaAssistantService, save_session

        selected_interpreter = interpreter or GroqIdeaInterpreter()
        result = IdeaAssistantService(
            selected_interpreter, knowledge_base=self._knowledge_base()
        ).build(
            self.workspace.manifest.original_idea,
            clarification_handler=clarification_handler,
            max_clarification_rounds=max_clarification_rounds,
            max_questions_per_round=max_questions_per_round,
        )
        project_record = self._persist(
            save_idea_project, result.project, ArtifactType.IDEA_PROJECT,
            f"idea_{result.project.id}", f"Conceptual project — {result.project.title}",
        )
        session_record = self._persist(
            save_session, result.session, ArtifactType.IDEA_SESSION,
            f"session_{result.session.id}", f"Clarification session — {result.project.title}",
        )
        return result, project_record, session_record

    def suggest_mappings(self, concept_id: str, *, query: str | None = None, limit: int = 5):
        """Return M5 mapping candidates from the workspace or bundled knowledge base."""
        from knowledge import KnowledgeMappingService

        base = self._knowledge_base()
        if base is None:
            raise WorkspaceError("No M5 knowledge base is available. Import a knowledge_base JSON artifact first.")
        project = self._idea_project()
        return KnowledgeMappingService(base).suggest_for_concept(
            project, concept_id, query=query, limit=limit
        )

    def record_mapping_candidate(
        self, candidate, *, mapping_type: MappingType = MappingType.ANALOGOUS,
        review_status: ReviewStatus = ReviewStatus.UNREVIEWED,
    ):
        """Record a retrieved M5 candidate as a new, provenance-preserving revision."""
        from knowledge import KnowledgeMappingService

        base = self._knowledge_base()
        if base is None:
            raise WorkspaceError("No M5 knowledge base is available")
        project = self._idea_project()
        updated = KnowledgeMappingService(base).record_candidate(
            project, candidate, mapping_type=mapping_type, review_status=review_status,
        )
        record = self._persist(
            save_idea_project, updated, ArtifactType.IDEA_PROJECT,
            f"idea_{updated.id}_r{updated.current_revision.version}",
            f"Conceptual project — revision {updated.current_revision.version}",
        )
        return updated, record

    def review_mapping(
        self, mapping_id: str, decision: ReviewStatus, *, reviewer_note: str = "",
    ):
        """Append an explicit M5 accept/reject decision as another project revision."""
        from knowledge import KnowledgeMappingService

        base = self._knowledge_base()
        if base is None:
            raise WorkspaceError("No M5 knowledge base is available")
        project = self._idea_project()
        updated = KnowledgeMappingService(base).review_mapping(
            project, mapping_id, decision, reviewer_note=reviewer_note,
        )
        record = self._persist(
            save_idea_project, updated, ArtifactType.IDEA_PROJECT,
            f"idea_{updated.id}_r{updated.current_revision.version}",
            f"Conceptual project — revision {updated.current_revision.version}",
        )
        return updated, record

    def _record(self, artifact_id: str, expected_type: ArtifactType):
        for item in self.workspace.artifacts(expected_type):
            if item.artifact_id == artifact_id:
                return item
        raise LookupError(f"Artifact {artifact_id!r} is not a {expected_type.value} in this workspace")

    def _persist(self, saver, value, artifact_type: ArtifactType, suffix: str, display_name: str):
        with tempfile.TemporaryDirectory(prefix="m13-stage-", dir=self.workspace.directory) as temporary:
            path = Path(temporary) / f"{suffix}.json"
            saver(value, path)
            return self.workspace.add_artifact(path, artifact_type, display_name=display_name)

    def assess(self, selected_paradigm: Paradigm | str | None = None):
        """Run deterministic M7 assessment for this workspace's latest idea revision."""
        project = self._idea_project()
        if isinstance(selected_paradigm, str):
            selected_paradigm = Paradigm(selected_paradigm)
        if selected_paradigm is None:
            report = assess_readiness(project)
        else:
            try:
                adapter = self.extension_registry.for_paradigm(selected_paradigm.value)
            except LookupError:
                # M7 may assess a paradigm before an executable adapter exists.
                # The registry is used only when a complete paradigm adapter is registered.
                report = assess_readiness(project, selected_paradigm=selected_paradigm)
            else:
                _assessment, report = adapter.validate(project, project.current_revision.id)
        record = self._persist(
            save_readiness_report, report, ArtifactType.READINESS_REPORT,
            f"readiness_{report.revision_id}", f"Readiness assessment — revision {report.revision_version}",
        )
        return report, record

    def compile(self, profile_artifact_id: str):
        """Compile an imported M8 profile through its registered paradigm adapter."""
        project = self._idea_project()
        profile_record = self._record(profile_artifact_id, ArtifactType.COMPILATION_PROFILE)
        profile = load_profile(self.workspace.artifact_path(profile_record.artifact_id))
        adapter = self.extension_registry.for_paradigm(profile.paradigm.value)
        result = adapter.compile(project, project.current_revision.id, profile)
        if not result.is_ready:
            return result, None
        artifact = result.artifact
        record = self._persist(
            save_artifact, artifact, ArtifactType.COMPILATION_ARTIFACT,
            f"compiled_{artifact.artifact_id}", f"{artifact.paradigm.value} specification — {artifact.artifact_id}",
        )
        return result, record

    def execute(self, compilation_artifact_id: str, config: ExperimentConfig | None = None):
        """Execute one imported/compiled M8 artifact through its registered adapter."""
        record = self._record(compilation_artifact_id, ArtifactType.COMPILATION_ARTIFACT)
        artifact = load_artifact(self.workspace.artifact_path(record.artifact_id))
        adapter = self.extension_registry.for_paradigm(artifact.paradigm.value)
        result = adapter.execute(artifact, config)
        stored = self._persist(
            save_result, result, ArtifactType.EXECUTION_RESULT,
            f"execution_{result.experiment_id}", f"Execution — {result.experiment_id}",
        )
        return result, stored

    def parameter_sweep(
        self,
        compilation_artifact_id: str,
        factors: tuple[GridFactor, ...],
        *,
        runs: int = 1,
        base_seed: int | None = None,
        include_baseline: bool = True,
    ):
        """Run M10's bounded parameter sweep and persist both M9 and M10 outputs."""
        record = self._record(compilation_artifact_id, ArtifactType.COMPILATION_ARTIFACT)
        artifact = load_artifact(self.workspace.artifact_path(record.artifact_id))
        result, report = run_parameter_sweep(
            artifact, factors, runs=runs, base_seed=base_seed, include_baseline=include_baseline,
        )
        result_record = self._persist(
            save_result, result, ArtifactType.EXECUTION_RESULT,
            f"execution_{result.experiment_id}", f"Parameter sweep execution — {result.experiment_id}",
        )
        report_record = self._persist(
            save_analysis_report, report, ArtifactType.ANALYSIS_REPORT,
            f"analysis_{report.analysis_id}", f"Parameter sweep analysis — {report.analysis_id}",
        )
        return result, report, result_record, report_record

    def uncertainty_analysis(self, compilation_artifact_id: str, plan_artifact_id: str, *, execution_base_seed: int | None = None):
        """Run M11 sampling through M9 and persist the exact result/report pair."""
        artifact_record = self._record(compilation_artifact_id, ArtifactType.COMPILATION_ARTIFACT)
        plan_record = self._record(plan_artifact_id, ArtifactType.UNCERTAINTY_PLAN)
        artifact = load_artifact(self.workspace.artifact_path(artifact_record.artifact_id))
        plan = load_plan(self.workspace.artifact_path(plan_record.artifact_id))
        result, report = run_uncertainty_analysis(artifact, plan, execution_base_seed=execution_base_seed)
        result_record = self._persist(
            save_result, result, ArtifactType.EXECUTION_RESULT,
            f"execution_{result.experiment_id}", f"Uncertainty sample execution — {result.experiment_id}",
        )
        report_record = self._persist(
            save_uncertainty_report, report, ArtifactType.UNCERTAINTY_REPORT,
            f"uncertainty_{report.report_id}", f"Uncertainty analysis — {report.report_id}",
        )
        return result, report, result_record, report_record

    def analyze_result(self, experiment_artifact_id: str):
        """Create an M10 descriptive analysis from one saved M9 result."""
        record = self._record(experiment_artifact_id, ArtifactType.EXECUTION_RESULT)
        result = load_result(self.workspace.artifact_path(record.artifact_id))
        report = analyze_results((result,))
        stored = self._persist(
            save_analysis_report, report, ArtifactType.ANALYSIS_REPORT,
            f"analysis_{report.analysis_id}", f"Comparative analysis — {report.analysis_id}",
        )
        return report, stored

    def build_visualization(
        self,
        experiment_artifact_id: str,
        *,
        analysis_artifact_id: str | None = None,
        uncertainty_artifact_id: str | None = None,
        point_limit: int = 20000,
    ):
        """Build and persist an integrity/provenance-checked M12 bundle and HTML."""
        experiment_record = self._record(experiment_artifact_id, ArtifactType.EXECUTION_RESULT)
        result = load_result(self.workspace.artifact_path(experiment_record.artifact_id))
        analysis = None
        uncertainty = None
        if analysis_artifact_id:
            analysis_record = self._record(analysis_artifact_id, ArtifactType.ANALYSIS_REPORT)
            analysis = load_analysis_report(self.workspace.artifact_path(analysis_record.artifact_id))
        if uncertainty_artifact_id:
            uncertainty_record = self._record(uncertainty_artifact_id, ArtifactType.UNCERTAINTY_REPORT)
            uncertainty = load_uncertainty_report(self.workspace.artifact_path(uncertainty_record.artifact_id))
        bundle = build_visualization_bundle(
            result, analysis_report=analysis, uncertainty_report=uncertainty, point_limit=point_limit,
        )
        bundle_record = self._persist(
            save_bundle, bundle, ArtifactType.VISUALIZATION_BUNDLE,
            f"visualization_{bundle.bundle_id}", f"Visualization bundle — {bundle.bundle_id}",
        )
        with tempfile.TemporaryDirectory(prefix="m13-html-", dir=self.workspace.directory) as temporary:
            html_path = Path(temporary) / f"dashboard_{bundle.bundle_id}.html"
            save_html(bundle, html_path)
            html_record = self.workspace.add_artifact(
                html_path, ArtifactType.VISUALIZATION_HTML,
                display_name=f"Interactive dashboard — {bundle.bundle_id}",
            )
        return bundle, bundle_record, html_record

    def verify(self):
        """Verify every persisted workspace artifact's size and SHA-256 digest."""
        return self.workspace.verify_artifacts()
