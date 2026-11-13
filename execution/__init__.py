"""Controlled execution and traceable result capture (M9)."""

from execution.models import (
    ExperimentConfig, ExperimentResult, ExperimentStatus, MetricRecord,
    ParameterOverride, ParameterSet, RunRecord, RunStatus,
)
from execution.runner import execute_artifact, execute_artifact_file
from execution.serialization import (
    ExperimentSerializationError, dumps_result, load_result, loads_result,
    result_to_dict, save_result,
)

__all__ = [
    "ExperimentConfig", "ExperimentResult", "ExperimentSerializationError",
    "ExperimentStatus", "MetricRecord", "ParameterOverride", "ParameterSet",
    "RunRecord", "RunStatus",
    "dumps_result", "execute_artifact", "execute_artifact_file", "load_result",
    "loads_result", "result_to_dict", "save_result",
]
