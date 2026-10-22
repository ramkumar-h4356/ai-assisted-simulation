
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


    def test_events_are_recorded_in_chronological_order(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("machine", capacity=1))

        engine.schedule_service("A", "machine", 3, 2)
        engine.schedule_service("B", "machine", 0, 1)

        events = engine.run()
        event_times = [event.time for event in events]

        self.assertEqual(event_times, sorted(event_times))



    def test_simultaneous_arrivals_are_both_recorded(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("machine", capacity=1))

        engine.schedule_service("A", "machine", 0, 2)
        engine.schedule_service("B", "machine", 0, 1)

        events = engine.run()
        arrivals = [
            event for event in events
            if event.event_type == "arrived"
        ]

        self.assertEqual(len(arrivals), 2)
        self.assertEqual(
            {event.entity_id for event in arrivals},
            {"A", "B"},
        )
        self.assertEqual([event.time for event in arrivals], [0, 0])


    def test_entity_can_pass_through_two_service_stages(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("registration", capacity=1))
        engine.add_resource(Resource("consultation", capacity=1))

        engine.schedule_route(
            entity_id="A",
            arrival_time=0,
            stages=[
                ("registration", 2),
                ("consultation", 5),
            ],
        )

        events = engine.run()
        actual = [
            (event.event_type, event.resource_name, event.time)
            for event in events
        ]

        self.assertEqual(
            actual,
                [
                    ("arrived", "registration", 0),
                    ("service_started", "registration", 0),
                    ("service_completed", "registration", 2),
                    ("arrived", "consultation", 2),
                    ("service_started", "consultation", 2),
                    ("service_completed", "consultation", 7),
                ],
        ) 

    def test_empty_route_is_rejected(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("registration", capacity=1))

        with self.assertRaises(ValueError):
            engine.schedule_route(
                entity_id="A",
                arrival_time=0,
                stages=[],
            ) 
    def test_route_rejects_unknown_resource(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("registration", capacity=1))

        with self.assertRaises(ValueError):
            engine.schedule_route(
                entity_id="A",
                arrival_time=0,
                stages=[
                    ("doctor", 5),
                ],
            )
    def test_route_rejects_negative_stage_duration(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("registration", capacity=1))

        with self.assertRaises(ValueError):
            engine.schedule_route(
                entity_id="A",
                arrival_time=0,
                stages=[
                    ("registration", -2),
                ],
            )
    def test_duplicate_entity_ids_in_routes_are_rejected(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("registration", capacity=1))

        engine.schedule_route(
            entity_id="A",
            arrival_time=0,
            stages=[("registration", 2)],
        )

        with self.assertRaises(ValueError):
            engine.schedule_route(
                entity_id="A",
                arrival_time=1,
                stages=[("registration", 3)],
            )
    def test_entity_cannot_be_scheduled_as_service_and_route(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("registration", capacity=1))

        engine.schedule_service("A", "registration", 0, 2)

        with self.assertRaises(ValueError):
            engine.schedule_route(
                entity_id="A",
                arrival_time=1,
                stages=[("registration", 3)],
            )
    def test_route_waits_when_next_resource_is_busy(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("registration", capacity=1))
        engine.add_resource(Resource("consultation", capacity=1))

        # A occupies consultation from time 0 to 5.
        engine.schedule_route(
            entity_id="A",
            arrival_time=0,
            stages=[("consultation", 5)],
        )

        # B finishes registration at time 2, then must wait for consultation.
        engine.schedule_route(
            entity_id="B",
            arrival_time=0,
            stages=[
                ("registration", 2),
                ("consultation", 1),
            ],
        )

        events = engine.run()
        b_consultation_start = next(
            event.time
            for event in events
            if event.entity_id == "B"
            and event.event_type == "service_started"
            and event.resource_name == "consultation"
        )

        self.assertEqual(b_consultation_start, 5)

    def test_resource_capacities_returns_configured_capacities(self):
        engine = SimulationEngine()
        engine.add_resource(Resource("Doctor", capacity=1))
        engine.add_resource(Resource("Counter", capacity=2))

        self.assertEqual(
            engine.resource_capacities,
            {"Doctor": 1, "Counter": 2},
        )


if __name__ == "__main__":
    unittest.main()
