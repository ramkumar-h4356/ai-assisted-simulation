
from asyncio import events
import unittest

from simulations.engine import SimulationEngine, SimulationEvent
from simulations.metrics import (
    calculate_entity_metrics,
    calculate_simulation_summary,
    calculate_stage_metrics,
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
        summary =calculate_simulation_summary([])

        self.assertEqual(summary.completed_entities, 0)
        self.assertEqual(summary.average_waiting_time, 0.0)
        self.assertEqual(summary.average_service_time, 0.0)
        self.assertEqual(summary.average_time_in_system, 0.0)
if __name__ == "__main__":
    unittest.main()
