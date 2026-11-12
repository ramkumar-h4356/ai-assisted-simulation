"""Register and resolve simulation execution backends."""

from simulations.core.backend import SimulationBackend
from simulations.core.specification import SimulationParadigm

class BackendRegistry:
    """Manage available simulation backends."""

    def __init__(self) -> None:
        self._backends: dict[SimulationParadigm, SimulationBackend] = {}

    def register(self, backend: SimulationBackend) -> None:
        """Register one backend for its supported paradigm."""

        if not isinstance(backend.name, str) or not backend.name.strip():
            raise ValueError("Backend name must be non-empty")

        if not isinstance(backend.paradigm, SimulationParadigm):
            raise TypeError(
                "Backend paradigm must be a SimulationParadigm"
            )

        if not callable(getattr(backend, "execute", None)):
            raise TypeError("Backend must implement execute()")

        if backend.paradigm in self._backends:
            raise ValueError(
                f"A backend is already registered for "
                f"{backend.paradigm.value}"
            )

        self._backends[backend.paradigm] = backend

    def get(self, paradigm: SimulationParadigm) -> SimulationBackend:
        """Retrieve the backend registered for a paradigm."""

        if not isinstance(paradigm, SimulationParadigm):
            raise TypeError("paradigm must be a SimulationParadigm")

        try:
            return self._backends[paradigm]
        except KeyError as error:
            raise LookupError(
                f"No backend registered for {paradigm.value}"
            ) from error

    @property
    def supported_paradigms(self) -> tuple[SimulationParadigm, ...]:
        """Return all paradigms with registered backends."""

        return tuple(self._backends.keys())