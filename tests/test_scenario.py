
import unittest

from simulations.scenario import (
    Scenario,
    ScenarioResource,
    ServiceJob,
    ServiceStage,
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

    def test_rejects_empty_resource_name(self):
        with self.assertRaises(ValueError):
            Scenario("Test", " ", 1, self.jobs)

    def test_rejects_non_positive_resource_capacity(self):
        for capacity in (0, -1):
            with self.subTest(capacity=capacity):
                with self.assertRaises(ValueError):
                    Scenario("Test", "machine", capacity, self.jobs)

    def test_rejects_invalid_arrival_time(self):
        for arrival in (-1, float("inf"), float("nan")):
            with self.subTest(arrival=arrival):
                with self.assertRaises(ValueError):
                    ServiceJob("A", arrival, 2)

    def test_rejects_invalid_service_duration(self):
        for duration in (-1, float("inf"), float("nan")):
            with self.subTest(duration=duration):
                with self.assertRaises(ValueError):
                    ServiceJob("A", 0, duration)

    def test_scenario_reports_resource_utilization(self):
        scenario = Scenario(
            name="One machine",
            resource_name="machine",
            resource_capacity=1,
            jobs=self.jobs,
        )

        result = run_scenario(scenario)

        self.assertEqual(len(result.resource_metrics), 1)
        self.assertEqual(
            result.resource_metrics[0].resource_name,
            "machine",
        )
        self.assertAlmostEqual(
            result.resource_metrics[0].utilization,
            100.0,
        )

    def test_more_capacity_reduces_utilization_per_capacity_unit(self):
        scenario = Scenario(
            name="Two machines",
            resource_name="machine",
            resource_capacity=2,
            jobs=self.jobs,
        )

        result = run_scenario(scenario)

        self.assertAlmostEqual(
            result.resource_metrics[0].utilization,
            100.0 * 10 / 12,
        )

    def test_job_visits_multiple_resources_in_sequence(self):
        scenario = Scenario(
            name="Hospital workflow",
            resources=(
                ScenarioResource("registration", 2),
                ScenarioResource("doctor", 3),
                ScenarioResource("pharmacy", 1),
            ),
            jobs=(
                ServiceJob(
                    entity_id="Patient-1",
                    arrival_time=0,
                    stages=(
                        ServiceStage("registration", 5),
                        ServiceStage("doctor", 15),
                        ServiceStage("pharmacy", 3),
                    ),
                ),
            ),
        )

        result = run_scenario(scenario)

        self.assertEqual(result.completion_time, 23)
        self.assertEqual(len(result.resource_metrics), 3)
        self.assertEqual(
            {metric.resource_name for metric in result.resource_metrics},
            {"registration", "doctor", "pharmacy"},
        )



if __name__ == "__main__":
    unittest.main()

