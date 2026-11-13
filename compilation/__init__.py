"""Traceable compilation from conceptual idea revisions to supported model specs."""

from compilation.compiler import compile_profile, create_profile_template, fingerprint_artifact, fingerprint_model, verify_artifact
from compilation.models import (
    BindingSource, CompilationArtifact, CompilationIssue, CompilationParadigm,
    CompilationProfile, CompilationResult, ElementBinding, IssueSeverity,
)
from compilation.serialization import (
    CompilationSerializationError, artifact_to_dict, dumps_artifact, dumps_profile,
    load_artifact, load_profile, loads_artifact, loads_profile, profile_to_dict,
    save_artifact, save_profile,
)

__all__ = [
    "BindingSource", "CompilationArtifact", "CompilationIssue", "CompilationParadigm",
    "CompilationProfile", "CompilationResult", "CompilationSerializationError",
    "ElementBinding", "IssueSeverity", "artifact_to_dict", "compile_profile",
    "create_profile_template", "dumps_artifact", "dumps_profile", "fingerprint_artifact", "fingerprint_model",
    "load_artifact", "load_profile", "loads_artifact", "loads_profile",
    "profile_to_dict", "save_artifact", "save_profile", "verify_artifact",
]
