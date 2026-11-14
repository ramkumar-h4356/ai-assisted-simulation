"""Run the bundled synthetic M21 forecasting example."""

from __future__ import annotations

import json
from pathlib import Path

from simulations.core.specification import SimulationParadigm, SimulationSpecification
from simulations.data_driven.backend import DataDrivenBackend


def main() -> None:
    scenario_path = Path(__file__).resolve().parents[2] / "scenarios" / "data_driven" / "synthetic_coupled_series.json"
    model_data = json.loads(scenario_path.read_text(encoding="utf-8"))
    result = DataDrivenBackend().execute(SimulationSpecification(
        model_data["name"], SimulationParadigm.DATA_DRIVEN, model_data,
    ))
    execution = result.native_result
    print(f"Model: {execution.model_name}")
    print(f"Method: {execution.method} VAR({execution.lag_order})")
    print(f"Training samples: {execution.training_samples}; holdout samples: {execution.holdout_samples}")
    for variable, metrics in execution.evaluation_metrics.items():
        print(f"{variable}: RMSE={metrics['rmse']:.6f}; MAE={metrics['mae']:.6f}; R²={metrics['r_squared']:.6f}")
    print("Forecast:")
    for point in execution.forecast:
        print(f"  t={point.time:g}: {point.values}")


if __name__ == "__main__":
    main()
