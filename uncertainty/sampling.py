"""Reproducible, bounded Monte Carlo parameter sampling for M11."""

from __future__ import annotations

import random
from typing import Any

from compilation import BindingSource, CompilationArtifact, verify_artifact
from execution import ParameterOverride, ParameterSet
from uncertainty.models import UncertaintyPlan
from experimentation.grid import _path_tokens, _read_path


def generate_parameter_samples(
    artifact: CompilationArtifact,
    plan: UncertaintyPlan,
) -> tuple[ParameterSet, ...]:
    """Sample only explicitly declared numeric M8 user parameters.

    Integer targets use integer-valued sampling. Float targets use floating
    point sampling. A fixed plan.sampling_seed reproduces the exact sample set.
    """
    if not isinstance(artifact, CompilationArtifact):
        raise TypeError("artifact must be a CompilationArtifact")
    if not verify_artifact(artifact):
        raise ValueError("M8 artifact integrity verification failed; uncertainty sampling blocked")
    if not isinstance(plan, UncertaintyPlan):
        raise TypeError("plan must be an UncertaintyPlan")

    allowed = {
        binding.target_path
        for binding in artifact.bindings
        if binding.source is BindingSource.USER_PARAMETER
    }
    path_tokens: dict[str, list[str | int]] = {}
    kinds: dict[str, type] = {}
    for parameter in plan.parameters:
        if parameter.target_path not in allowed:
            raise ValueError(
                f"Parameter path {parameter.target_path!r} is not an explicitly bound M8 user_parameter"
            )
        tokens = _path_tokens(parameter.target_path)
        baseline = _read_path(artifact.model_data, tokens)
        if isinstance(baseline, bool) or not isinstance(baseline, (int, float)):
            raise ValueError(f"Uncertain parameter {parameter.target_path!r} must refer to a numeric model value")
        if type(baseline) is not type(parameter.lower):
            raise TypeError(
                f"Parameter {parameter.target_path!r} expects {type(baseline).__name__} bounds, "
                f"not {type(parameter.lower).__name__}"
            )
        path_tokens[parameter.target_path] = tokens
        kinds[parameter.target_path] = type(baseline)

    for index, left in enumerate(plan.parameters):
        left_tokens = path_tokens[left.target_path]
        for right in plan.parameters[index + 1:]:
            right_tokens = path_tokens[right.target_path]
            common = min(len(left_tokens), len(right_tokens))
            if left_tokens[:common] == right_tokens[:common]:
                raise ValueError(f"Uncertain parameter paths {left.target_path!r} and {right.target_path!r} overlap")

    rng = random.Random(plan.sampling_seed)
    samples: list[ParameterSet] = []
    for sample_index in range(1, plan.sample_count + 1):
        overrides: list[ParameterOverride] = []
        for parameter in plan.parameters:
            target_type = kinds[parameter.target_path]
            if parameter.distribution == "uniform":
                if target_type is int:
                    value = rng.randint(parameter.lower, parameter.upper)
                else:
                    value = rng.uniform(parameter.lower, parameter.upper)
            elif target_type is int:
                value = int(round(rng.triangular(parameter.lower, parameter.upper, parameter.mode)))
                value = min(parameter.upper, max(parameter.lower, value))
            else:
                value = rng.triangular(parameter.lower, parameter.upper, parameter.mode)
            overrides.append(ParameterOverride(parameter.target_path, value))
        samples.append(ParameterSet(f"sample_{sample_index:03d}", tuple(overrides)))
    return tuple(samples)
