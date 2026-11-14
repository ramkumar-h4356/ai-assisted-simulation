from __future__ import annotations

import pytest

pytest.importorskip("simpy")

from compilation import compile_profile, save_artifact
from tests.compilation.helpers import des_profile
from tests.readiness.helpers import des_project
from validation import InvariantSpec, ValidationPlan, validate_model


def test_des_validation_checks_event_order_and_repeatability(tmp_path):
    project = des_project()
    compiled = compile_profile(project, des_profile(project))
    assert compiled.is_ready, compiled.issues
    save_artifact(compiled.artifact, tmp_path / "des.json")
    plan = ValidationPlan(
        1, "DES event verification", "des.json", repeatability_check=True,
        invariants=(InvariantSpec("event-time", "monotonic", "events[].time", direction="nondecreasing"),),
    )
    report = validate_model(plan, artifact_root=tmp_path, output_dir=tmp_path / "outputs")
    assert report.overall_status == "passed"
    assert next(item for item in report.checks if item.check_id == "repeatability").status == "passed"
