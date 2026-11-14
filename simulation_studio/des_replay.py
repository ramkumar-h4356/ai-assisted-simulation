"""Provenance-checked replay access for saved discrete-event executions (M19)."""

from __future__ import annotations

from typing import Any

from compilation.compiler import verify_artifact
from compilation.models import CompilationArtifact, CompilationParadigm
from execution.models import ExperimentResult, RunStatus
from execution.serialization import fingerprint_result
from simulation_studio.replay import ReplayError
from simulations.des.replay import build_des_replay


def build_des_run_replay(
    result: ExperimentResult,
    compilation: CompilationArtifact,
    *,
    run_index: int = 1,
) -> dict[str, Any]:
    """Rebuild the selected DES run's replay after validating M8/M9 lineage.

    The replay is recomputed from the persisted canonical event log. The M19
    cached projection, when present, must match the recomputed content.
    """
    if not isinstance(result, ExperimentResult):
        raise TypeError("result must be an ExperimentResult")
    if not isinstance(compilation, CompilationArtifact):
        raise TypeError("compilation must be a CompilationArtifact")
    if fingerprint_result(result) != result.result_fingerprint:
        raise ReplayError("M9 execution fingerprint verification failed")
    if not verify_artifact(compilation):
        raise ReplayError("M8 compilation artifact fingerprint verification failed")
    if result.paradigm != CompilationParadigm.DISCRETE_EVENT.value:
        raise ReplayError("DES replay supports discrete-event execution results only")
    if compilation.paradigm is not CompilationParadigm.DISCRETE_EVENT:
        raise ReplayError("The linked M8 artifact is not a DES specification")
    if (
        result.artifact_id,
        result.artifact_fingerprint,
        result.project_id,
        result.revision_id,
        result.revision_version,
    ) != (
        compilation.artifact_id,
        compilation.artifact_fingerprint,
        compilation.project_id,
        compilation.revision_id,
        compilation.revision_version,
    ):
        raise ReplayError("M9 result and M8 compilation provenance do not match")
    if isinstance(run_index, bool) or not isinstance(run_index, int) or run_index < 1:
        raise ReplayError("run_index must be a positive integer")
    run = next((item for item in result.runs if item.run_index == run_index), None)
    if run is None:
        raise ReplayError(f"Run {run_index} does not exist in this execution result")
    if run.status is not RunStatus.COMPLETED:
        raise ReplayError(f"Run {run_index} did not complete and cannot be replayed")

    raw_events = run.trace.get("events")
    if not isinstance(raw_events, list):
        raise ReplayError("Selected DES run does not contain a recorded event log")

    capacities = run.trace.get("resource_capacities")
    if capacities is None:
        # M9 files created before M19 did not persist capacities in the trace.
        capacities = {
            item["name"]: item["capacity"]
            for item in compilation.model_data.get("resources", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
    if not isinstance(capacities, dict):
        raise ReplayError("Selected DES run has invalid resource-capacity metadata")

    try:
        replay = build_des_replay(raw_events, resource_capacities=capacities)
    except (TypeError, ValueError) as error:
        raise ReplayError(f"Selected DES event log cannot be replayed: {error}") from error

    stored_replay = run.trace.get("replay")
    if stored_replay is not None and stored_replay != replay:
        raise ReplayError("Stored M19 replay projection does not match the canonical DES event log")

    replay["lineage"] = {
        "experiment_id": result.experiment_id,
        "execution_fingerprint": result.result_fingerprint,
        "compilation_artifact_id": compilation.artifact_id,
        "project_id": result.project_id,
        "revision_id": result.revision_id,
        "revision_version": result.revision_version,
        "run_index": run.run_index,
        "parameter_set": run.parameter_set,
    }
    return replay
