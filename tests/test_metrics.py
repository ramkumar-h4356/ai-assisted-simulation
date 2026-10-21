
import unittest

from simulations.engine import SimulationEngine, SimulationEvent
from simulations.metrics import calculate_entity_metrics
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


if __name__ == "__main__":
    unittest.main()
