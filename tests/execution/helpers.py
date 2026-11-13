from dataclasses import replace

from compilation import CompilationParadigm, compile_profile
from tests.compilation.helpers import abm_profile, des_profile
from tests.readiness.helpers import abm_project, des_project


def abm_artifact(*, seed=7, probability=1.0):
    project = abm_project()
    profile = abm_profile(project)
    data = dict(profile.model_data)
    data["random_seed"] = seed
    behaviours = [dict(item) for item in data["behaviours"]]
    behaviours[0]["probability"] = probability
    data["behaviours"] = behaviours
    result = compile_profile(project, replace(profile, model_data=data))
    assert result.is_ready, result.issues
    return result.artifact


def des_artifact():
    project = des_project()
    result = compile_profile(project, des_profile(project))
    assert result.is_ready, result.issues
    return result.artifact
