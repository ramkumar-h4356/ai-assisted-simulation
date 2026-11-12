
"""Tests for the AI-to-simulation pipeline."""

import unittest
from unittest.mock import patch

from simulations.des.pipeline import run_prompt


VALID_MODEL = {
    "name": "Test Hospital",
    "resources": [
        {"name": "Doctor", "capacity": 1}
    ],
    "jobs": [
        {
            "entity_id": "Patient-1",
            "arrival_time": 0,
            "stages": [
                {
                    "resource_name": "Doctor",
                    "service_duration": 10,
                }
            ],
        }
    ],
}


class PipelineTests(unittest.TestCase):
    @patch("simulations.des.pipeline.generate_model")
    def test_valid_model_runs_simulation(self, mock_generate):
        mock_generate.return_value = VALID_MODEL

        result = run_prompt("Simulate a hospital")

        mock_generate.assert_called_once_with("Simulate a hospital")
        self.assertEqual(
            result.model_data,
            VALID_MODEL,
        )
        self.assertEqual(
            result.simulation_result.scenario_name,
            "Test Hospital",
        )
        self.assertEqual(
            len(result.simulation_result.entity_metrics),
            1,
        )

    @patch("simulations.des.pipeline.run_scenario")
    @patch("simulations.des.pipeline.generate_model")
    def test_invalid_model_is_rejected_before_execution(
        self, mock_generate, mock_run
    ):
        mock_generate.return_value = {
            "name": "Invalid Hospital",
            "resources": [],
            "jobs": [],
        }

        with self.assertRaises(ValueError):
            run_prompt("Simulate an invalid hospital")

        mock_run.assert_not_called()

    @patch("simulations.des.pipeline.generate_model")
    def test_empty_prompt_does_not_call_ai(self, mock_generate):
        with self.assertRaises(ValueError):
            run_prompt("   ")

        mock_generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
