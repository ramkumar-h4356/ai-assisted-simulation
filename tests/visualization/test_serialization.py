import json

import pytest

from execution import ExperimentConfig, execute_artifact
from tests.execution.helpers import abm_artifact
from visualization import (
    VisualizationSerializationError, build_visualization_bundle,
    load_bundle, loads_bundle, save_bundle, save_html,
)


def test_bundle_json_round_trip_and_html_persistence(tmp_path):
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=2, base_seed=50))
    bundle = build_visualization_bundle(result)
    json_path = save_bundle(bundle, tmp_path / "dashboard.json")
    html_path = save_html(bundle, tmp_path / "dashboard.html")
    loaded = load_bundle(json_path)
    assert loaded == bundle
    assert "Simulation dashboard" in html_path.read_text(encoding="utf-8")
    assert loads_bundle(json_path.read_text(encoding="utf-8")) == bundle


def test_bundle_loader_rejects_tampered_content():
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=1, base_seed=51))
    bundle = build_visualization_bundle(result)
    raw = json.loads(__import__("visualization").dumps_bundle(bundle))
    raw["project_title"] = "forged"
    with pytest.raises(VisualizationSerializationError, match="fingerprint"):
        loads_bundle(json.dumps(raw))


def test_bundle_loader_rejects_unknown_top_level_fields():
    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=1, base_seed=52))
    bundle = build_visualization_bundle(result)
    raw = json.loads(__import__("visualization").dumps_bundle(bundle))
    raw["unexpected"] = True
    with pytest.raises(VisualizationSerializationError, match="unknown field"):
        loads_bundle(json.dumps(raw))


def test_renderer_rejects_modified_bundle_after_creation():
    from dataclasses import replace
    from visualization import render_html

    result = execute_artifact(abm_artifact(), ExperimentConfig(runs=1, base_seed=53))
    bundle = build_visualization_bundle(result)
    modified = replace(bundle, project_title="tampered")
    with pytest.raises(VisualizationSerializationError, match="fingerprint"):
        render_html(modified)
