"""Run the bundled M20 SIR ODE example."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.mathematical.backend import MathematicalBackend
from simulations.mathematical.model import mathematical_model_from_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an M20 mathematical simulation example")
    parser.add_argument(
        "model", nargs="?",
        default=str(Path(__file__).resolve().parents[2] / "scenarios" / "mathematical" / "sir_rk4.json"),
        help="Path to an M20 mathematical model JSON file",
    )
    arguments = parser.parse_args()
    raw = json.loads(Path(arguments.model).read_text(encoding="utf-8"))
    model = mathematical_model_from_dict(raw)
    result = MathematicalBackend().execute(
        SimulationSpecification(model.name, SimulationParadigm.MATHEMATICAL, model)
    )
    final = result.native_result.snapshots[-1]
    print(f"Model: {result.specification_name}")
    print(f"Solver: {result.native_result.solver}; steps: {result.native_result.steps}")
    print(f"Final time: {final.time:g} {result.native_result.time_unit or ''}".rstrip())
    print("Final state:")
    for name, value in final.values.items():
        print(f"  {name}: {value:.6f}")
    print("Population conservation (S + I + R):", f"{sum(final.values.values()):.6f}")


if __name__ == "__main__":
    main()
