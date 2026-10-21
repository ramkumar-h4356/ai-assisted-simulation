
from simulations.engine import SimulationEngine
from simulations.resource import Resource
from simulations.metrics import calculate_entity_metrics


def main():
    # 1. Create the simulation engine.
    engine = SimulationEngine()

    # 2. Add one machine.
    engine.add_resource(Resource("machine", capacity=1))

    # 3. Schedule two jobs.
    engine.schedule_service("A", "machine", arrival_time=0, duration=6)
    engine.schedule_service("B", "machine", arrival_time=2, duration=4)

    # 4. Run the simulation.
    events = engine.run()

    # 5. Display the event log.
    print("\n--- Simulation Event Log ---")
    for event in events:
        print(
            f"Time: {event.time:>4} | "
            f"Job: {event.entity_id} | "
            f"Event: {event.event_type}"
        )

    # 6. Calculate and display metrics.
    metrics = calculate_entity_metrics(events)

    print("\n--- Job Metrics ---")
    for item in metrics:
        print(
            f"Job {item.entity_id}: "
            f"Waiting={item.waiting_time}, "
            f"Service={item.service_time}, "
            f"Time in system={item.time_in_system}"
        )


if __name__ == "__main__":
    main()
