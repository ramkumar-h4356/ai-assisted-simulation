from dataclasses import replace

import pytest

from compilation.compiler import fingerprint_artifact
from experimentation import GridFactor, generate_parameter_grid
from tests.execution.helpers import abm_artifact


def test_grid_includes_compiled_baseline_and_cartesian_variants():
    artifact = abm_artifact()
    factors = (
        GridFactor("agents[0].attributes.trust", (0.2, 0.8)),
        GridFactor("termination.value", (3, 5)),
    )

    parameter_sets = generate_parameter_grid(artifact, factors)

    assert len(parameter_sets) == 5  # baseline plus three non-baseline combinations
    assert parameter_sets[0].name == "baseline"
    baseline = {item.target_path: item.value for item in parameter_sets[0].overrides}
    assert baseline == {
        "agents[0].attributes.trust": 0.8,
        "termination.value": 10,
    }
    assert all(len(item.overrides) == 2 for item in parameter_sets)
    assert len({item.name for item in parameter_sets}) == len(parameter_sets)


def test_grid_rejects_non_user_parameter_bindings():
    with pytest.raises(ValueError, match="not an explicitly bound M8 user_parameter"):
        generate_parameter_grid(abm_artifact(), (GridFactor("agents[0].state", ("active",)),))


def test_grid_rejects_type_changes_and_overlapping_paths():
    artifact = abm_artifact()
    with pytest.raises(ValueError, match="expects float levels"):
        generate_parameter_grid(artifact, (GridFactor("agents[0].attributes.trust", (1,)),))
    with pytest.raises(ValueError, match="overlap"):
        generate_parameter_grid(artifact, (
            GridFactor("agents[0]", ("not-valid",)),
            GridFactor("agents[0].attributes.trust", (0.3,)),
        ))


def test_grid_rejects_tampered_artifact_and_variant_limit():
    artifact = abm_artifact()
    changed = replace(artifact, project_title="tampered title")
    with pytest.raises(ValueError, match="integrity verification failed"):
        generate_parameter_grid(changed, (GridFactor("termination.value", (3,)),))
    with pytest.raises(ValueError, match="exceeding the configured limit"):
        generate_parameter_grid(
            artifact,
            (GridFactor("termination.value", (1, 2, 3)),),
            include_baseline=True,
            max_variants=2,
        )


def test_grid_rejects_duplicate_paths_and_duplicate_level_values():
    artifact = abm_artifact()
    with pytest.raises(ValueError, match="unique"):
        GridFactor("termination.value", (2, 2))
    with pytest.raises(ValueError, match="only one grid factor"):
        generate_parameter_grid(artifact, (
            GridFactor("termination.value", (3,)),
            GridFactor("termination.value", (5,)),
        ))


def test_grid_without_baseline_keeps_the_current_value_if_it_is_a_requested_level():
    artifact = abm_artifact()
    variants = generate_parameter_grid(
        artifact,
        (GridFactor("termination.value", (3, 10)),),
        include_baseline=False,
    )
    assert len(variants) == 2
    assert {item.overrides[0].value for item in variants} == {3, 10}


def test_grid_rejects_malformed_paths_and_large_products_before_materializing():
    artifact = abm_artifact()
    with pytest.raises(ValueError, match="Invalid parameter path"):
        generate_parameter_grid(artifact, (GridFactor("termination..value", (3,)),))
    levels = tuple(range(1, 1001))
    with pytest.raises(ValueError, match="exceeding the configured limit"):
        generate_parameter_grid(
            artifact,
            (GridFactor("termination.value", levels),),
            max_variants=100,
        )
