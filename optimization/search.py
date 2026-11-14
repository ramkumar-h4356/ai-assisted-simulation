"""Deterministic bounded candidate generation for M23 random search."""

from __future__ import annotations

from itertools import product
import json
import math
import random
import re
from typing import Any

from compilation import BindingSource, CompilationArtifact, verify_artifact
from execution import ParameterOverride, ParameterSet
from optimization.models import OptimizationPlan


def _path_tokens(path: str) -> list[str | int]:
    if not isinstance(path, str) or not path:
        raise ValueError(f"Invalid parameter path: {path!r}")
    first = re.match(r"[A-Za-z_][A-Za-z0-9_]*", path)
    if first is None:
        raise ValueError(f"Invalid parameter path: {path!r}")
    tokens: list[str | int] = [first.group(0)]
    position = len(first.group(0))
    while position < len(path):
        if path[position] == ".":
            position += 1
            match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", path[position:])
            if match is None:
                raise ValueError(f"Invalid parameter path: {path!r}")
            tokens.append(match.group(0))
            position += len(match.group(0))
        elif path[position] == "[":
            match = re.match(r"\[(0|[1-9][0-9]*)\]", path[position:])
            if match is None:
                raise ValueError(f"Invalid parameter path: {path!r}")
            tokens.append(int(match.group(1)))
            position += len(match.group(0))
        else:
            raise ValueError(f"Invalid parameter path: {path!r}")
    return tokens


def _read_path(data: Any, tokens: list[str | int]) -> Any:
    current = data
    for token in tokens:
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                raise ValueError("search parameter target path does not exist in model_data")
            current = current[token]
        else:
            if not isinstance(current, dict) or token not in current:
                raise ValueError("search parameter target path does not exist in model_data")
            current = current[token]
    return current


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def generate_candidates(
    artifact: CompilationArtifact,
    plan: OptimizationPlan,
) -> tuple[ParameterSet, ...]:
    """Generate baseline plus unique reproducible random candidates.

    Search parameters must be exact scalar M8 ``user_parameter`` bindings.
    Bounds preserve the model field's numeric type. Integer dimensions are
    sampled inclusively; floating-point dimensions are uniform on [lower, upper].
    """
    if not isinstance(artifact, CompilationArtifact):
        raise TypeError("artifact must be a CompilationArtifact")
    if not verify_artifact(artifact):
        raise ValueError("M8 artifact integrity verification failed; optimization blocked")
    if not isinstance(plan, OptimizationPlan):
        raise TypeError("plan must be an OptimizationPlan")

    paths = [item.target_path for item in plan.search_parameters]
    tokens_by_path = {path: _path_tokens(path) for path in paths}
    for index, left in enumerate(paths):
        for right in paths[index + 1:]:
            a, b = tokens_by_path[left], tokens_by_path[right]
            common = min(len(a), len(b))
            if a[:common] == b[:common]:
                raise ValueError(f"Search parameter paths {left!r} and {right!r} overlap")

    allowed = {
        binding.target_path for binding in artifact.bindings
        if binding.source is BindingSource.USER_PARAMETER
    }
    baseline: dict[str, int | float] = {}
    integer_capacities: list[int] = []
    has_float = False
    for parameter in plan.search_parameters:
        if parameter.target_path not in allowed:
            raise ValueError(
                f"Search path {parameter.target_path!r} is not an explicitly bound M8 user_parameter"
            )
        current = _read_path(artifact.model_data, tokens_by_path[parameter.target_path])
        if isinstance(current, bool) or not isinstance(current, (int, float)):
            raise ValueError(f"Search path {parameter.target_path!r} must point to a numeric scalar")
        if type(current) is not type(parameter.lower):
            raise ValueError(
                f"Search path {parameter.target_path!r} expects {type(current).__name__} bounds, "
                f"not {type(parameter.lower).__name__}"
            )
        if not math.isfinite(float(current)):
            raise ValueError(f"Search path {parameter.target_path!r} has a non-finite baseline")
        if not parameter.lower <= current <= parameter.upper and plan.include_baseline:
            raise ValueError(
                f"Baseline value for {parameter.target_path!r} lies outside the configured search bounds"
            )
        baseline[parameter.target_path] = current
        if isinstance(current, int):
            integer_capacities.append(parameter.upper - parameter.lower + 1)
        else:
            has_float = True

    baseline_key = _canonical(baseline)
    if not has_float:
        total_space = math.prod(integer_capacities)
        available = total_space - (1 if plan.include_baseline else 0)
        if plan.candidate_count > available:
            raise ValueError(
                f"Requested {plan.candidate_count} unique candidates, but only {available} non-baseline "
                "integer combinations are available"
            )

    rng = random.Random(plan.search_seed)
    candidates: list[ParameterSet] = []
    if plan.include_baseline:
        candidates.append(ParameterSet(
            "baseline",
            tuple(ParameterOverride(parameter.target_path, baseline[parameter.target_path]) for parameter in plan.search_parameters),
        ))

    seen = {baseline_key} if plan.include_baseline else set()
    generated: list[dict[str, int | float]] = []
    attempts = 0
    max_attempts = max(1000, plan.candidate_count * 500)
    while len(generated) < plan.candidate_count and attempts < max_attempts:
        attempts += 1
        values: dict[str, int | float] = {}
        for parameter in plan.search_parameters:
            if isinstance(parameter.lower, int):
                value = rng.randint(parameter.lower, parameter.upper)
            else:
                value = rng.uniform(parameter.lower, parameter.upper)
            values[parameter.target_path] = value
        key = _canonical(values)
        if key in seen:
            continue
        seen.add(key)
        generated.append(values)

    if len(generated) != plan.candidate_count:
        raise ValueError(
            f"Could generate only {len(generated)} unique candidates after {attempts} attempts; "
            "reduce candidate_count or widen the search bounds"
        )

    for index, values in enumerate(generated, start=1):
        candidates.append(ParameterSet(
            f"candidate_{index:03d}",
            tuple(ParameterOverride(parameter.target_path, values[parameter.target_path]) for parameter in plan.search_parameters),
        ))
    return tuple(candidates)


__all__ = ["generate_candidates"]
