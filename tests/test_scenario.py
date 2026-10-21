
import unittest

from simulations.scenario import (
    Scenario,
    ServiceJob,
    compare_scenarios,
    run_scenario,
)


class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.jobs = (
            ServiceJob("A", arrival_time=0, service_duration=6),
            ServiceJob("B", arrival_time=2, service_duration=4),
        )

    def test_one_machine_causes_waiting(self):
        scenario = Scenario(
            name="One machine",
            resource_name="machine",
            resource_capacity=1,
            jobs=self.jobs,
        )

        result = run_scenario(scenario)

        self.assertEqual(result.average_waiting_time, 2.0)
        self.assertEqual(result.completion_time, 10.0)

    def test_two_machines_reduce_waiting(self):
        scenario = Scenario(
            name="Two machines",
            resource_name="machine",
            resource_capacity=2,
            jobs=self.jobs,
        )

        result = run_scenario(scenario)

        self.assertEqual(result.average_waiting_time, 0.0)
        self.assertEqual(result.completion_time, 6.0)

    def test_comparison_runs_both_scenarios(self):
        scenarios = (
            Scenario("One machine", "machine", 1, self.jobs),
            Scenario("Two machines", "machine", 2, self.jobs),
        )

        results = compare_scenarios(scenarios)

        self.assertEqual(len(results), 2)
        self.assertLess(
            results[1].average_waiting_time,
            results[0].average_waiting_time,
        )

    def test_empty_scenario_list_is_rejected(self):
        with self.assertRaises(ValueError):
            compare_scenarios(())

    def test_duplicate_job_ids_are_rejected(self):
        jobs = (
            ServiceJob("A", 0, 3),
            ServiceJob("A", 1, 2),
        )

        with self.assertRaises(ValueError):
            Scenario("Invalid", "machine", 1, jobs)


if __name__ == "__main__":
    unittest.main()

