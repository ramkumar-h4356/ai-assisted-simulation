"""Safe Cartesian parameter-grid generation for verified M8 artifacts."""

from __future__ import annotations

from itertools import product
import json
import math
import re
from typing import Any

from compilation import BindingSource, CompilationArtifact, verify_artifact
from execution import ParameterOverride, ParameterSet
from experimentation.models import GridFactor


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
                raise ValueError("parameter target path does not exist in model_data")
            current = current[token]
        else:
            if not isinstance(current, dict) or token not in current:
                raise ValueError("parameter target path does not exist in model_data")
            current = current[token]
    return current


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _slug(value: Any) -> str:
    if value is None:
        raw = "null"
    elif isinstance(value, bool):
        raw = "true" if value else "false"
    else:
        raw = str(value)
    cleaned = re.sub(r"[^A-Za-z0-9.-]+", "-", raw).strip("-")
    return (cleaned or "value")[:24]


def generate_parameter_grid(
    artifact: CompilationArtifact,
    factors: tuple[GridFactor, ...],
    *,
    include_baseline: bool = True,
    max_variants: int = 100,
) -> tuple[ParameterSet, ...]:
    """Create a bounded Cartesian grid for explicit M8 user parameters only.

    When requested, the baseline contains the current values from the M8
    artifact. A Cartesian combination identical to baseline is omitted.
    """
    if not isinstance(artifact, CompilationArtifact):
        raise TypeError("artifact must be a CompilationArtifact")
    if not verify_artifact(artifact):
        raise ValueError("M8 artifact integrity verification failed; grid generation blocked")
    if not isinstance(factors, tuple) or not factors or any(not isinstance(item, GridFactor) for item in factors):
        raise ValueError("factors must be a non-empty tuple of GridFactor values")
    if not isinstance(include_baseline, bool):
        raise TypeError("include_baseline must be a boolean")
    if isinstance(max_variants, bool) or not isinstance(max_variants, int) or not 1 <= max_variants <= 100:
        raise ValueError("max_variants must be between 1 and 100")

    paths = [item.target_path for item in factors]
    if len(paths) != len(set(paths)):
        raise ValueError("each target_path may appear in only one grid factor")
    tokens_by_path = {factor.target_path: _path_tokens(factor.target_path) for factor in factors}
    for index, left in enumerate(factors):
        for right in factors[index + 1:]:
            left_tokens, right_tokens = tokens_by_path[left.target_path], tokens_by_path[right.target_path]
            common = min(len(left_tokens), len(right_tokens))
            if left_tokens[:common] == right_tokens[:common]:
                raise ValueError(f"Grid factor paths {left.target_path!r} and {right.target_path!r} overlap")

    allowed = {
        binding.target_path
        for binding in artifact.bindings
        if binding.source is BindingSource.USER_PARAMETER
    }
    baseline_values: dict[str, Any] = {}
    for factor in factors:
        if factor.target_path not in allowed:
            raise ValueError(
                f"Grid path {factor.target_path!r} is not an explicitly bound M8 user_parameter"
            )
        current = _read_path(artifact.model_data, tokens_by_path[factor.target_path])
        if not isinstance(current, (str, int, float, bool, type(None))):
            raise ValueError(f"Grid path {factor.target_path!r} must point to a scalar model value")
        if isinstance(current, float) and not math.isfinite(current):
            raise ValueError(f"Grid path {factor.target_path!r} has a non-finite baseline value")
        baseline_values[factor.target_path] = current
        for level in factor.levels:
            if type(level) is not type(current):
                raise ValueError(
                    f"Grid path {factor.target_path!r} expects {type(current).__name__} levels, "
                    f"not {type(level).__name__}"
                )

    baseline_key = tuple(_canonical(baseline_values[factor.target_path]) for factor in factors)
    product_count = math.prod(len(factor.levels) for factor in factors)
    baseline_in_grid = all(
        baseline_key[index] in {_canonical(value) for value in factor.levels}
        for index, factor in enumerate(factors)
    )
    skip_grid_baseline = include_baseline and baseline_in_grid
    expected_count = product_count - (1 if skip_grid_baseline else 0) + (1 if include_baseline else 0)
    if expected_count > max_variants:
        raise ValueError(
            f"Parameter grid contains {expected_count} variants, exceeding the configured limit of {max_variants}"
        )

    result: list[ParameterSet] = []
    if include_baseline:
        result.append(ParameterSet(
            "baseline",
            tuple(ParameterOverride(factor.target_path, baseline_values[factor.target_path]) for factor in factors),
        ))

    index = 0
    for combination in product(*(factor.levels for factor in factors)):
        if skip_grid_baseline and tuple(_canonical(value) for value in combination) == baseline_key:
            continue
        index += 1
        parts = []
        overrides = []
        for factor, value in zip(factors, combination):
            leaf = re.split(r"[.\[]", factor.target_path)[-1].rstrip("]")
            parts.append(f"{leaf}_{_slug(value)}")
            overrides.append(ParameterOverride(factor.target_path, value))
        name = f"variant_{index:03d}__" + "__".join(parts)
        result.append(ParameterSet(name, tuple(overrides)))

    if not result:
        raise ValueError("Grid generation produced no variants")
    return tuple(result)
