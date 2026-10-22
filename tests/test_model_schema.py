
"""Tests for structured simulation model parsing."""

import unittest

from simulations.scenario import run_scenario

from simulations.model_schema import (
    scenario_from_dict,
    scenario_from_json,
)


class ModelSchemaTests(unittest.TestCase):
    def setUp(self):
        self.model = {
            "name": "Hospital workflow",
            "resources": [
                {"name": "registration", "capacity": 2},
                {"name": "doctor", "capacity": 3},
                {"name": "pharmacy", "capacity": 1},
            ],
            "jobs": [
                {
                    "entity_id": "Patient-1",
                    "arrival_time": 0,
                    "stages": [
                        {
                            "resource_name": "registration",
                            "service_duration": 5,
                        },
                        {
                            "resource_name": "doctor",
                            "service_duration": 15,
                        },
                        {
                            "resource_name": "pharmacy",
                            "service_duration": 3,
                        },
                    ],
                }
            ],
        }

    def test_valid_dictionary_creates_scenario(self):
        from simulations.scenario import Scenario

        scenario = scenario_from_dict(self.model)

        self.assertIsInstance(scenario, Scenario)
        self.assertEqual(scenario.name, "Hospital workflow")
        self.assertEqual(len(scenario.resources), 3)
        self.assertEqual(len(scenario.jobs), 1)
        self.assertEqual(len(scenario.jobs[0].stages), 3)

    def test_valid_json_creates_scenario(self):
        import json

        scenario = scenario_from_json(json.dumps(self.model))

        self.assertEqual(scenario.name, "Hospital workflow")
        self.assertEqual(scenario.jobs[0].entity_id, "Patient-1")

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(ValueError):
            scenario_from_json('{"name": ')

    def test_non_object_model_is_rejected(self):
        with self.assertRaises(TypeError):
            scenario_from_dict(["not", "an", "object"])

    def test_missing_top_level_field_is_rejected(self):
        model = dict(self.model)
        del model["jobs"]

        with self.assertRaises(ValueError):
            scenario_from_dict(model)

    def test_unexpected_top_level_field_is_rejected(self):
        model = {**self.model, "extra": "not allowed"}

        with self.assertRaises(ValueError):
            scenario_from_dict(model)

    def test_invalid_resource_reference_is_rejected(self):
        import copy

        model = copy.deepcopy(self.model)
        model["jobs"][0]["stages"][0]["resource_name"] = "unknown"

        with self.assertRaises(ValueError):
            scenario_from_dict(model)

    def test_non_positive_resource_capacity_is_rejected(self):
        import copy

        model = copy.deepcopy(self.model)
        model["resources"][0]["capacity"] = 0

        with self.assertRaises(ValueError):
            scenario_from_dict(model)

    def test_negative_service_duration_is_rejected(self):
        import copy

        model = copy.deepcopy(self.model)
        model["jobs"][0]["stages"][0]["service_duration"] = -1

        with self.assertRaises(ValueError):
            scenario_from_dict(model)

    def test_parsed_model_runs_in_simulation_engine(self):
        scenario = scenario_from_dict(self.model)

        result = run_scenario(scenario)

        self.assertEqual(result.scenario_name, "Hospital workflow")
        self.assertEqual(result.completion_time, 23)
        self.assertEqual(len(result.resource_metrics), 3)
        self.assertEqual(
            {metric.resource_name for metric in result.resource_metrics},
            {"registration", "doctor", "pharmacy"},
        )


if __name__ == "__main__":
    unittest.main()
