import json
from dataclasses import replace

import pytest

from compilation import (
    CompilationSerializationError, dumps_artifact, dumps_profile,
    load_artifact, loads_artifact, loads_profile, save_artifact,
)
from tests.compilation.helpers import des_profile
from tests.readiness.helpers import des_project
from compilation import compile_profile


def test_profile_json_round_trip_is_strict():
    profile = des_profile()
    restored = loads_profile(dumps_profile(profile))
    assert restored == profile


def test_profile_rejects_unknown_fields():
    raw = json.loads(dumps_profile(des_profile()))
    raw["untrusted_extra"] = True
    with pytest.raises(CompilationSerializationError, match="unknown field"):
        loads_profile(json.dumps(raw))


def test_artifact_save_load_round_trip_and_integrity(tmp_path):
    result = compile_profile(des_project(), des_profile())
    path = tmp_path / "compiled.json"
    save_artifact(result.artifact, path)
    restored = load_artifact(path)
    assert restored == result.artifact


def test_artifact_loader_rejects_tampered_model_payload(tmp_path):
    result = compile_profile(des_project(), des_profile())
    raw = json.loads(dumps_artifact(result.artifact))
    raw["model_data"]["resources"][0]["capacity"] = 99
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(CompilationSerializationError, match="fingerprint"):
        load_artifact(path)


def test_artifact_rejects_unknown_fields():
    result = compile_profile(des_project(), des_profile())
    raw = json.loads(dumps_artifact(result.artifact))
    raw["untrusted"] = "x"
    with pytest.raises(CompilationSerializationError, match="unknown field"):
        loads_artifact(json.dumps(raw))


def test_artifact_loader_rejects_tampered_provenance_bindings(tmp_path):
    result = compile_profile(des_project(), des_profile())
    raw = json.loads(dumps_artifact(result.artifact))
    raw["bindings"][0]["element_ids"] = ["not-the-original-element"]
    path = tmp_path / "tampered-provenance.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(CompilationSerializationError, match="integrity fingerprint"):
        load_artifact(path)
