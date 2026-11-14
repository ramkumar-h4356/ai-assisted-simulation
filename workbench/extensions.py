"""Controlled extension contract for future simulation paradigms (M13)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ExtensionDescriptor:
    extension_id: str
    display_name: str
    version: str
    paradigm: str
    model_schema_versions: tuple[str, ...]
    capabilities: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("extension_id", "display_name", "version", "paradigm"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        for name in ("model_schema_versions", "capabilities"):
            value = getattr(self, name)
            if not isinstance(value, tuple) or any(not isinstance(item, str) or not item.strip() for item in value):
                raise TypeError(f"{name} must be a tuple of non-empty strings")
        if not self.model_schema_versions:
            raise ValueError("At least one model schema version must be declared")
        allowed = {"validate", "compile", "execute", "serialize_result", "validate_result", "visualize"}
        unknown = set(self.capabilities) - allowed
        if unknown:
            raise ValueError(f"Unsupported extension capability/capabilities: {', '.join(sorted(unknown))}")
        if not {"validate", "compile", "execute", "serialize_result", "validate_result"}.issubset(self.capabilities):
            raise ValueError("A simulation extension must support validate, compile, execute, serialize_result and validate_result")


@runtime_checkable
class SimulationParadigmExtension(Protocol):
    """Full lifecycle contract required for a new simulation-paradigm plugin.

    Implementations are responsible for paradigm-specific semantics. The
    workbench owns project lifecycle, provenance, artifact storage and UI.
    """

    @property
    def descriptor(self) -> ExtensionDescriptor: ...

    def validate(self, conceptual_project: Any, revision_id: str) -> Any: ...

    def compile(self, conceptual_project: Any, revision_id: str, profile: Any) -> Any: ...

    def execute(self, compiled_model: Any, config: Any) -> Any: ...

    def serialize_result(self, result: Any) -> bytes: ...

    def validate_result(self, serialized_result: bytes) -> Any: ...


class ExtensionRegistry:
    """Explicit registry for trusted, application-loaded paradigm extensions."""

    def __init__(self) -> None:
        self._extensions: dict[str, SimulationParadigmExtension] = {}

    def register(self, extension: SimulationParadigmExtension) -> None:
        descriptor = getattr(extension, "descriptor", None)
        if not isinstance(descriptor, ExtensionDescriptor):
            raise TypeError("extension must expose an ExtensionDescriptor as descriptor")
        required = ("validate", "compile", "execute", "serialize_result", "validate_result")
        missing = [name for name in required if not callable(getattr(extension, name, None))]
        if missing:
            raise TypeError(f"extension is missing required method(s): {', '.join(missing)}")
        if "visualize" in descriptor.capabilities and not callable(getattr(extension, "visualize", None)):
            raise TypeError("extension declares visualize capability but does not implement visualize()")
        if descriptor.extension_id in self._extensions:
            raise ValueError(f"Extension {descriptor.extension_id!r} is already registered")
        if any(item.descriptor.paradigm == descriptor.paradigm for item in self._extensions.values()):
            raise ValueError(f"A simulation extension is already registered for paradigm {descriptor.paradigm!r}")
        self._extensions[descriptor.extension_id] = extension

    def get(self, extension_id: str) -> SimulationParadigmExtension:
        try:
            return self._extensions[extension_id]
        except KeyError as error:
            raise LookupError(f"No simulation extension registered as {extension_id!r}") from error

    def for_paradigm(self, paradigm: str) -> SimulationParadigmExtension:
        for extension in self._extensions.values():
            if extension.descriptor.paradigm == paradigm:
                return extension
        raise LookupError(f"No simulation extension registered for paradigm {paradigm!r}")

    @property
    def descriptors(self) -> tuple[ExtensionDescriptor, ...]:
        return tuple(item.descriptor for item in self._extensions.values())


class BuiltInParadigmAdapter:
    """Adapt the existing M8/M9 lifecycle to the M13 extension contract."""

    def __init__(self, descriptor: ExtensionDescriptor, compilation_paradigm, readiness_paradigm) -> None:
        self._descriptor = descriptor
        self._compilation_paradigm = compilation_paradigm
        self._readiness_paradigm = readiness_paradigm

    @property
    def descriptor(self) -> ExtensionDescriptor:
        return self._descriptor

    def validate(self, conceptual_project, revision_id: str):
        from readiness import assess_readiness
        if conceptual_project.current_revision.id != revision_id:
            raise ValueError("M13 validation requires the selected project revision to be current")
        report = assess_readiness(conceptual_project, selected_paradigm=self._readiness_paradigm)
        return report.assessment_for(self._readiness_paradigm), report

    def compile(self, conceptual_project, revision_id: str, profile):
        from compilation import compile_profile
        if conceptual_project.current_revision.id != revision_id:
            raise ValueError("M13 compilation requires the selected project revision to be current")
        if profile.project_id != conceptual_project.id or profile.revision_id != revision_id:
            raise ValueError("Compilation profile does not target this project revision")
        if profile.paradigm is not self._compilation_paradigm:
            raise ValueError("Compilation profile targets a different simulation paradigm")
        return compile_profile(conceptual_project, profile)

    def execute(self, compiled_model, config=None):
        from execution import execute_artifact
        if compiled_model.paradigm is not self._compilation_paradigm:
            raise ValueError("Compiled artifact belongs to a different simulation paradigm")
        return execute_artifact(compiled_model, config)

    def serialize_result(self, result) -> bytes:
        from execution import dumps_result
        return dumps_result(result).encode("utf-8")

    def validate_result(self, serialized_result: bytes):
        from execution import loads_result
        if not isinstance(serialized_result, bytes):
            raise TypeError("serialized_result must be bytes")
        return loads_result(serialized_result.decode("utf-8"))


def create_builtin_registry() -> ExtensionRegistry:
    """Return a registry containing the existing, executable DES and ABM adapters."""
    from compilation import CompilationParadigm
    from readiness import Paradigm

    registry = ExtensionRegistry()
    registry.register(BuiltInParadigmAdapter(
        ExtensionDescriptor(
            extension_id="builtin.des.v1", display_name="Discrete-event simulation (DES)",
            version="1.0.0", paradigm="discrete_event",
            model_schema_versions=("m8-des-v1",),
            capabilities=("validate", "compile", "execute", "serialize_result", "validate_result"),
        ), CompilationParadigm.DISCRETE_EVENT, Paradigm.DISCRETE_EVENT,
    ))
    registry.register(BuiltInParadigmAdapter(
        ExtensionDescriptor(
            extension_id="builtin.abm.v1", display_name="Agent-based simulation (ABM)",
            version="1.0.0", paradigm="agent_based",
            model_schema_versions=("m8-abm-v1",),
            capabilities=("validate", "compile", "execute", "serialize_result", "validate_result"),
        ), CompilationParadigm.AGENT_BASED, Paradigm.AGENT_BASED,
    ))
    return registry
