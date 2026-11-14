from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from compilation import save_profile
from conceptual import save_idea_project
from tests.compilation.helpers import abm_profile
from tests.readiness.helpers import abm_project
from webapp.app import create_app


def _upload(client: TestClient, workspace_id: str, artifact_type: str, path: Path):
    return client.post(
        f"/api/v1/workspaces/{workspace_id}/artifacts",
        params={"artifact_type": artifact_type},
        files={"file": (path.name, path.read_bytes(), "application/json")},
    )


def test_spatial_model_runs_through_browser_api_and_replay_uses_engine_positions(tmp_path):
    project = abm_project()
    profile = abm_profile(project)
    model_data = deepcopy(profile.model_data)
    model_data["space"] = {"width": 20, "height": 10, "boundary": "clamp"}
    model_data["agents"][0]["position"] = {"x": 2, "y": 3}
    model_data["agents"][1]["position"] = {"x": 18, "y": 7}
    model_data["behaviours"][0]["actions"].append(
        {"type": "move_by", "dx": 3, "dy": -1}
    )
    profile = replace(profile, model_data=model_data)

    idea_path = tmp_path / "idea.json"
    profile_path = tmp_path / "spatial_profile.json"
    save_idea_project(project, idea_path)
    save_profile(profile, profile_path)

    client = TestClient(create_app(tmp_path / "workspaces"))
    created = client.post("/api/v1/workspaces", json={
        "title": "Spatial API test",
        "original_idea": project.original_statement,
    })
    workspace_id = created.json()["overview"]["workspace_id"]
    assert _upload(client, workspace_id, "idea_project", idea_path).status_code == 201

    readiness = client.post(
        f"/api/v1/workspaces/{workspace_id}/readiness",
        json={"selected_paradigm": "agent_based"},
    )
    assert readiness.status_code == 200, readiness.text

    uploaded = _upload(client, workspace_id, "compilation_profile", profile_path)
    assert uploaded.status_code == 201, uploaded.text
    compiled = client.post(
        f"/api/v1/workspaces/{workspace_id}/compile",
        json={"profile_artifact_id": uploaded.json()["artifact"]["artifact_id"]},
    )
    assert compiled.status_code == 200, compiled.text

    executed = client.post(
        f"/api/v1/workspaces/{workspace_id}/execute",
        json={
            "compilation_artifact_id": compiled.json()["artifact"]["artifact_id"],
            "runs": 1,
            "base_seed": 23,
        },
    )
    assert executed.status_code == 200, executed.text
    execution_id = executed.json()["artifact"]["artifact_id"]

    replay = client.get(
        f"/api/v1/workspaces/{workspace_id}/executions/{execution_id}/replay"
    )
    assert replay.status_code == 200, replay.text
    scene = replay.json()
    assert scene["space"] == {"width": 20.0, "height": 10.0, "boundary": "clamp"}
    assert scene["frames"][0]["agents"][0]["position"] == {"x": 2.0, "y": 3.0}
    assert scene["frames"][1]["agents"][0]["position"] == {"x": 5.0, "y": 2.0}
