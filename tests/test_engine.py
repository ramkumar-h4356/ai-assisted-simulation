
from asyncio import events
import unittest

from simulations import engine
from simulations.engine import SimulationEngine
from simulations.resource import Resource


class SimulationEngineTests(unittest.TestCase):
    def test_single_capacity_makes_second_customer_wait(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("checkout", capacity=1))

        engine.schedule_service("A", "checkout", 0, 4)
        engine.schedule_service("B", "checkout", 1, 2)

        events = engine.run()

        starts = [
            (event.entity_id, event.time)
            for event in events
            if event.event_type == "service_started"
        ]
        completions = [
            (event.entity_id, event.time)
            for event in events
            if event.event_type == "service_completed"
        ]

        self.assertEqual(starts, [("A", 0), ("B", 4)])
        self.assertEqual(completions, [("A", 4), ("B", 6)])

    def test_capacity_two_allows_simultaneous_service(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("doctors", capacity=2))

        engine.schedule_service("A", "doctors", 0, 3)
        engine.schedule_service("B", "doctors", 0, 2)

        events = engine.run()

        starts = [
            (event.entity_id, event.time)
            for event in events
            if event.event_type == "service_started"
        ]

        self.assertEqual(starts, [("A", 0), ("B", 0)])

    def test_unknown_resource_is_rejected(self):
        engine = SimulationEngine()

        with self.assertRaises(ValueError):
            engine.schedule_service("A", "missing", 0, 2)



    def test_second_job_waits_for_machine(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("machine", capacity=1))

        engine.schedule_service("A", "machine", 0, 6)
        engine.schedule_service("B", "machine", 2, 4)

        events = engine.run()

        start_times = {
            event.entity_id: event.time
            for event in events
            if event.event_type == "service_started"
        }

        self.assertEqual(start_times["A"], 0)
        self.assertEqual(start_times["B"], 6)

    
    def test_scheduling_after_run_is_rejected(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("machine", capacity=1))
        engine.schedule_service("A", "machine", 0, 2)

        engine.run()

        with self.assertRaises(RuntimeError):
            engine.schedule_service("B", "machine", 3, 1)

    def test_adding_resource_after_run_is_rejected(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("machine", capacity=1))
        engine.schedule_service("A", "machine", 0, 2)

        engine.run()

        with self.assertRaises(RuntimeError):
            engine.add_resource(Resource("another_machine", capacity=1))
    def test_running_engine_twice_is_rejected(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("machine", capacity=1))
        engine.schedule_service("A", "machine", 0, 2)

        engine.run()

        with self.assertRaises(RuntimeError):
            engine.run()


if __name__ == "__main__":
    unittest.main()
