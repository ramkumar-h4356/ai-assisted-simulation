from pathlib import Path
import tempfile

from workbench import ArtifactType, WorkspaceManager


def test_artifact_copy_uses_short_temporary_filename(tmp_path, monkeypatch):
    workspace = WorkspaceManager(tmp_path / "workspaces").create("Long path regression", "Source idea.")
    source = tmp_path / "document.txt"
    source.write_text("An auxiliary artifact.", encoding="utf-8")

    original_mkstemp = tempfile.mkstemp
    captured = {}

    def capture_mkstemp(*args, **kwargs):
        descriptor, name = original_mkstemp(*args, **kwargs)
        captured["name"] = Path(name).name
        return descriptor, name

    monkeypatch.setattr(tempfile, "mkstemp", capture_mkstemp)
    record = workspace.add_artifact(source, ArtifactType.OTHER)

    assert captured["name"].startswith(".a-")
    assert len(captured["name"]) < 32
    assert workspace.artifact_path(record.artifact_id).read_text(encoding="utf-8") == "An auxiliary artifact."
