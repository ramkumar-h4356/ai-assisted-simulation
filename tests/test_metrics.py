import unittest

from simulations.engine import SimulationEngine, SimulationEvent
from simulations.metrics import (
    ResourceMetrics,
    calculate_entity_metrics,
    calculate_resource_metrics,
    calculate_simulation_summary,
    calculate_stage_metrics,
    identify_potential_bottlenecks,
)
from simulations.resource import Resource


class SimulationMetricsTests(unittest.TestCase):
    def test_calculates_waiting_service_and_system_times(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("checkout", capacity=1))
        engine.schedule_service("A", "checkout", 0, 4)
        engine.schedule_service("B", "checkout", 1, 2)

        metrics = calculate_entity_metrics(engine.run())

        customer_b = next(
            result for result in metrics if result.entity_id == "B"
        )

        self.assertEqual(customer_b.waiting_time, 3)
        self.assertEqual(customer_b.service_time, 2)
        self.assertEqual(customer_b.time_in_system, 5)

    def test_rejects_incomplete_event_history(self):
        events = [
            SimulationEvent(0, "A", "arrived", "checkout"),
        ]

        with self.assertRaises(ValueError):
            calculate_entity_metrics(events)

    def test_rejects_events_in_invalid_time_order(self):
        events = [
            SimulationEvent(3, "A", "arrived", "checkout"),
            SimulationEvent(2, "A", "service_started", "checkout"),
            SimulationEvent(4, "A", "service_completed", "checkout"),
        ]

        with self.assertRaises(ValueError):
            calculate_entity_metrics(events)

    def test_calculates_metrics_for_multi_stage_journey(self):
        events = [
            SimulationEvent(0, "A", "arrived", "registration"),
            SimulationEvent(0, "A", "service_started", "registration"),
            SimulationEvent(2, "A", "service_completed", "registration"),
            SimulationEvent(2, "A", "arrived", "consultation"),
            SimulationEvent(5, "A", "service_started", "consultation"),
            SimulationEvent(8, "A", "service_completed", "consultation"),
        ]

        entity = calculate_entity_metrics(events)[0]

        self.assertEqual(entity.arrival_time, 0)
        self.assertEqual(entity.completion_time, 8)
        self.assertEqual(entity.waiting_time, 3)
        self.assertEqual(entity.service_time, 5)
        self.assertEqual(entity.time_in_system, 8)

        stages = calculate_stage_metrics(events)

        self.assertEqual(len(stages), 2)

        self.assertEqual(stages[0].resource_name, "registration")
        self.assertEqual(stages[0].waiting_time, 0)
        self.assertEqual(stages[0].service_time, 2)

        self.assertEqual(stages[1].resource_name, "consultation")
        self.assertEqual(stages[1].waiting_time, 3)
        self.assertEqual(stages[1].service_time, 3)

    def test_calculates_simulation_summary(self):
        events = [
            SimulationEvent(0, "A", "arrived", "registration"),
            SimulationEvent(0, "A", "service_started", "registration"),
            SimulationEvent(2, "A", "service_completed", "registration"),
            SimulationEvent(2, "A", "arrived", "consultation"),
            SimulationEvent(5, "A", "service_started", "consultation"),
            SimulationEvent(8, "A", "service_completed", "consultation"),
        ]

        summary = calculate_simulation_summary(events)

        self.assertEqual(summary.completed_entities, 1)
        self.assertEqual(summary.average_waiting_time, 3)
        self.assertEqual(summary.average_service_time, 5)
        self.assertEqual(summary.average_time_in_system, 8)

    def test_empty_simulation_summary(self):
        summary = calculate_simulation_summary([])

        self.assertEqual(summary.completed_entities, 0)
        self.assertEqual(summary.average_waiting_time, 0.0)
        self.assertEqual(summary.average_service_time, 0.0)
        self.assertEqual(summary.average_time_in_system, 0.0)

    def test_calculates_resource_metrics(self):
        events = [
            SimulationEvent(0, "A", "arrived", "registration"),
            SimulationEvent(0, "A", "service_started", "registration"),
            SimulationEvent(2, "A", "service_completed", "registration"),
            SimulationEvent(2, "A", "arrived", "consultation"),
            SimulationEvent(5, "A", "service_started", "consultation"),
            SimulationEvent(8, "A", "service_completed", "consultation"),
        ]

        resources = calculate_resource_metrics(events)

        self.assertEqual(len(resources), 2)

        registration = resources[1]
        self.assertEqual(registration.resource_name, "registration")
        self.assertEqual(registration.completed_services, 1)
        self.assertEqual(registration.average_waiting_time, 0)
        self.assertEqual(registration.average_service_time, 2)

        consultation = resources[0]
        self.assertEqual(consultation.resource_name, "consultation")
        self.assertEqual(consultation.completed_services, 1)
        self.assertEqual(consultation.average_waiting_time, 3)
        self.assertEqual(consultation.average_service_time, 3)

    def test_identify_potential_bottlenecks(self):
        resource_metrics = [
            ResourceMetrics("registration", 1, 0, 2),
            ResourceMetrics("consultation", 1, 3, 3),
        ]

        bottlenecks = identify_potential_bottlenecks(resource_metrics)

        self.assertEqual(len(bottlenecks), 1)
        self.assertEqual(bottlenecks[0].resource_name, "consultation")

    def test_identifies_resource_with_highest_waiting_time(self):
        resources = [
            ResourceMetrics("registration", 10, 2.0, 3.0),
            ResourceMetrics("consultation", 8, 12.0, 8.0),
            ResourceMetrics("pharmacy", 10, 4.0, 2.0),
        ]

        result = identify_potential_bottlenecks(resources)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].resource_name, "consultation")

    def test_returns_all_resources_tied_for_highest_waiting_time(self):
        resources = [
            ResourceMetrics("registration", 10, 5.0, 3.0),
            ResourceMetrics("consultation", 8, 5.0, 8.0),
        ]

        result = identify_potential_bottlenecks(resources)

        self.assertEqual(
            [item.resource_name for item in result],
            ["consultation", "registration"],
        )

    def test_returns_empty_list_when_no_resource_has_waiting_time(self):
        resources = [
            ResourceMetrics("registration", 10, 0.0, 3.0),
            ResourceMetrics("consultation", 8, 0.0, 8.0),
        ]

        result = identify_potential_bottlenecks(resources)

        self.assertEqual(result, [])

    def test_calculates_resource_utilization(self):
        engine = SimulationEngine()
        engine.add_resource(Resource(name="Doctor", capacity=1))

        engine.schedule_service(
            entity_id="A",
            resource_name="Doctor",
            arrival_time=0,
            duration=4,
        )
        engine.schedule_service(
            entity_id="B",
            resource_name="Doctor",
            arrival_time=0,
            duration=2,
        )

        events = engine.run()
        resource_metrics = calculate_resource_metrics(events)

        doctor = resource_metrics[0]
        self.assertEqual(doctor.resource_name, "Doctor")
        self.assertAlmostEqual(doctor.utilization, 100.0)

    def test_utilization_accounts_for_resource_capacity(self):
        engine = SimulationEngine()
        engine.add_resource(Resource(name="Counter", capacity=2))

        engine.schedule_service(
            entity_id="A",
            resource_name="Counter",
            arrival_time=0,
            duration=4,
        )

        events = engine.run()
        resource_metrics = calculate_resource_metrics(
            events,
            resource_capacities=engine.resource_capacities,
        )

        counter = resource_metrics[0]
        self.assertAlmostEqual(counter.utilization, 50.0)

    def test_zero_duration_service_has_zero_utilization(self):
        engine = SimulationEngine()
        engine.add_resource(Resource(name="Machine", capacity=1))

        engine.schedule_service(
            entity_id="A",
            resource_name="Machine",
            arrival_time=0,
            duration=0,
        )

        events = engine.run()
        resource_metrics = calculate_resource_metrics(events)

        machine = resource_metrics[0]
        self.assertAlmostEqual(machine.utilization, 0.0)


if __name__ == "__main__":
    unittest.main()
