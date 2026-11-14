from __future__ import annotations

import json
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


def test_local_web_shell_and_workspace_crud(tmp_path):
    client = TestClient(create_app(tmp_path / "workspaces"))

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["version"] == "18.0.0"

    home = client.get("/")
    assert home.status_code == 200
    assert "Simulation Workbench" in home.text
    assert "Content-Security-Policy" in home.headers

    created = client.post("/api/v1/workspaces", json={
        "title": "Cooperation study",
        "original_idea": "People cooperate to manage a shared resource.",
    })
    assert created.status_code == 201
    workspace_id = created.json()["overview"]["workspace_id"]
    assert created.json()["original_idea"] == "People cooperate to manage a shared resource."

    listed = client.get("/api/v1/workspaces")
    assert listed.status_code == 200
    assert [item["workspace_id"] for item in listed.json()["workspaces"]] == [workspace_id]

    detail = client.get(f"/api/v1/workspaces/{workspace_id}")
    assert detail.status_code == 200
    assert detail.json()["overview"]["artifact_count"] == 0


def test_browser_api_runs_abm_workflow_through_m12(tmp_path):
    project = abm_project()
    profile = abm_profile(project)
    idea_path = tmp_path / "idea_project.json"
    profile_path = tmp_path / "abm_profile.json"
    plan_path = tmp_path / "uncertainty_plan.json"
    save_idea_project(project, idea_path)
    save_profile(profile, profile_path)
    plan_path.write_text(json.dumps({
        "sample_count": 5,
        "sampling_seed": 19,
        "parameters": [{
            "target_path": "agents[0].attributes.trust",
            "distribution": "uniform",
            "lower": 0.0,
            "upper": 1.0,
        }],
    }), encoding="utf-8")

    client = TestClient(create_app(tmp_path / "workspaces"))
    created = client.post("/api/v1/workspaces", json={
        "title": "ABM API workflow",
        "original_idea": project.original_statement,
    })
    workspace_id = created.json()["overview"]["workspace_id"]

    idea_upload = _upload(client, workspace_id, "idea_project", idea_path)
    assert idea_upload.status_code == 201, idea_upload.text

    readiness = client.post(
        f"/api/v1/workspaces/{workspace_id}/readiness",
        json={"selected_paradigm": "agent_based"},
    )
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["report"]["status"] == "ready_for_implementation_planning"

    profile_upload = _upload(client, workspace_id, "compilation_profile", profile_path)
    assert profile_upload.status_code == 201, profile_upload.text
    profile_id = profile_upload.json()["artifact"]["artifact_id"]

    compilation = client.post(
        f"/api/v1/workspaces/{workspace_id}/compile",
        json={"profile_artifact_id": profile_id},
    )
    assert compilation.status_code == 200, compilation.text
    compilation_id = compilation.json()["artifact"]["artifact_id"]

    execution = client.post(
        f"/api/v1/workspaces/{workspace_id}/execute",
        json={"compilation_artifact_id": compilation_id, "runs": 1, "base_seed": 23},
    )
    assert execution.status_code == 200, execution.text
    assert execution.json()["result"]["status"] == "completed"
    execution_id = execution.json()["artifact"]["artifact_id"]

    replay = client.get(f"/api/v1/workspaces/{workspace_id}/executions/{execution_id}/replay")
    assert replay.status_code == 200, replay.text
    replay_payload = replay.json()
    assert replay_payload["schema_version"] == 1
    assert replay_payload["agent_count"] == 2
    assert replay_payload["relationship_count"] == 1
    assert len(replay_payload["frames"]) == 11
    assert replay_payload["frames"][0]["step"] == 0
    assert replay_payload["frames"][-1]["step"] == 10
    assert replay_payload["display_semantics"]["positions_are_physical"] is False

    missing_run = client.get(
        f"/api/v1/workspaces/{workspace_id}/executions/{execution_id}/replay?run_index=2"
    )
    assert missing_run.status_code == 422

    sweep = client.post(
        f"/api/v1/workspaces/{workspace_id}/parameter-sweep",
        json={
            "compilation_artifact_id": compilation_id,
            "factors": [{"target_path": "agents[0].attributes.trust", "levels": [0.2, 0.8]}],
            "runs": 1,
            "base_seed": 31,
        },
    )
    assert sweep.status_code == 200, sweep.text
    assert sweep.json()["analysis_artifact"]["artifact_type"] == "analysis_report"

    analysis = client.post(
        f"/api/v1/workspaces/{workspace_id}/analysis",
        json={"execution_artifact_id": execution_id},
    )
    assert analysis.status_code == 200, analysis.text
    analysis_id = analysis.json()["artifact"]["artifact_id"]

    plan_upload = _upload(client, workspace_id, "uncertainty_plan", plan_path)
    assert plan_upload.status_code == 201, plan_upload.text
    uncertainty = client.post(
        f"/api/v1/workspaces/{workspace_id}/uncertainty",
        json={
            "compilation_artifact_id": compilation_id,
            "plan_artifact_id": plan_upload.json()["artifact"]["artifact_id"],
            "execution_base_seed": 47,
        },
    )
    assert uncertainty.status_code == 200, uncertainty.text
    assert uncertainty.json()["report"]["sample_count"] == 5

    # M11 creates its own M9 execution result. The M10 analysis attached to
    # an M12 bundle must reference that exact same execution result.
    uncertainty_execution_id = uncertainty.json()["execution_artifact"]["artifact_id"]
    uncertainty_analysis = client.post(
        f"/api/v1/workspaces/{workspace_id}/analysis",
        json={"execution_artifact_id": uncertainty_execution_id},
    )
    assert uncertainty_analysis.status_code == 200, uncertainty_analysis.text

    visualization = client.post(
        f"/api/v1/workspaces/{workspace_id}/visualization",
        json={
            "execution_artifact_id": uncertainty_execution_id,
            "analysis_artifact_id": uncertainty_analysis.json()["artifact"]["artifact_id"],
            "uncertainty_artifact_id": uncertainty.json()["uncertainty_artifact"]["artifact_id"],
        },
    )
    assert visualization.status_code == 200, visualization.text
    assert visualization.json()["html_download_url"].endswith("/download")
    dashboard_download = client.get(visualization.json()["html_download_url"])
    assert dashboard_download.status_code == 200
    assert dashboard_download.headers.get("content-type") == "application/octet-stream"
    dashboard_preview = client.get(visualization.json()["html_preview_url"])
    assert dashboard_preview.status_code == 200
    assert "text/html" in dashboard_preview.headers.get("content-type", "")
    assert "sandbox allow-scripts" in dashboard_preview.headers.get("content-security-policy", "")

    verification = client.get(f"/api/v1/workspaces/{workspace_id}/verification")
    assert verification.status_code == 200
    assert verification.json()["valid"] is True

    export = client.post(f"/api/v1/workspaces/{workspace_id}/export")
    assert export.status_code == 200, export.text
    archive = client.get(export.json()["download_url"])
    assert archive.status_code == 200
    assert archive.content[:2] == b"PK"


def test_upload_limits_and_unknown_workspace_are_handled(tmp_path):
    client = TestClient(create_app(tmp_path / "workspaces", max_upload_bytes=8))
    missing = client.get("/api/v1/workspaces/ws-000000000000")
    assert missing.status_code == 404

    created = client.post("/api/v1/workspaces", json={"title": "Upload", "original_idea": "Test upload limit."})
    workspace_id = created.json()["overview"]["workspace_id"]
    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/artifacts",
        params={"artifact_type": "other"},
        files={"file": ("large.txt", b"0123456789abcdef", "text/plain")},
    )
    assert response.status_code == 413
