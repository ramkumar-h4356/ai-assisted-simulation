"""Run the illustrative SIR stock-flow model from the M22 scenario file."""
from __future__ import annotations

import json
from pathlib import Path

from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.system_dynamics import SystemDynamicsBackend, system_dynamics_model_from_dict


def main() -> None:
    path = Path(__file__).resolve().parents[2] / "scenarios" / "system_dynamics" / "sir_stock_flow.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    model = system_dynamics_model_from_dict(raw)
    result = SystemDynamicsBackend().execute(
        SimulationSpecification(model.name, SimulationParadigm.SYSTEM_DYNAMICS, model)
    )
    native = result.native_result
    print(f"Model: {native.model_name}")
    print(f"Solver: {native.solver}; steps: {native.steps}; duration: {native.end_time - native.start_time:g} {native.time_unit or ''}")
    print("Final stocks:")
    for name, summary in native.summaries.items():
        print(f"  {name}: {summary['final']:.6f}")
    print("Cumulative flows:")
    for name, value in native.total_flow.items():
        print(f"  {name}: {value:.6f}")
    print(f"Population conservation: {sum(native.snapshots[-1].stocks.values()):.9f}")


if __name__ == "__main__":
    main()
