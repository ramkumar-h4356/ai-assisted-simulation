"""Unit tests for the simulation Entity domain object."""

import math
import unittest

from simulations.entity import Entity


class EntityTests(unittest.TestCase):
    def test_entity_keeps_identity_creation_time_and_attributes(self) -> None:
        entity = Entity("customer-17", created_at=3.5, attributes={"priority": 2})

        self.assertEqual(entity.identifier, "customer-17")
        self.assertEqual(entity.created_at, 3.5)
        self.assertEqual(entity.get("priority"), 2)

    def test_default_creation_time_and_missing_attribute(self) -> None:
        entity = Entity("job-1")

        self.assertEqual(entity.created_at, 0.0)
        self.assertIsNone(entity.get("missing"))
        self.assertEqual(entity.get("missing", "fallback"), "fallback")

    def test_attributes_are_not_shared_with_the_callers_mapping(self) -> None:
        supplied_attributes = {"destination": "dock-a"}
        entity = Entity("parcel-1", attributes=supplied_attributes)
        supplied_attributes["destination"] = "dock-b"

        self.assertEqual(entity.get("destination"), "dock-a")

    def test_attributes_can_be_set_and_updated(self) -> None:
        entity = Entity("patient-1")
        entity.set("triage_level", 1)
        entity.update({"room": "A3", "urgent": True})

        self.assertEqual(
            entity.attributes,
            {"triage_level": 1, "room": "A3", "urgent": True},
        )

    def test_identifier_must_be_a_non_empty_string(self) -> None:
        for identifier in ("", "   ", None, 7):
            with self.subTest(identifier=identifier):
                with self.assertRaises((TypeError, ValueError)):
                    Entity(identifier)  # type: ignore[arg-type]

    def test_creation_time_must_be_finite_and_non_negative(self) -> None:
        for created_at in (-0.1, math.inf, math.nan):
            with self.subTest(created_at=created_at):
                with self.assertRaises(ValueError):
                    Entity("event", created_at=created_at)

        with self.assertRaises(TypeError):
            Entity("event", created_at="now")  # type: ignore[arg-type]

    def test_attribute_names_and_updates_are_validated(self) -> None:
        entity = Entity("worker-1")

        for name in ("", "  ", None):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    entity.set(name, "value")  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            entity.update([("shift", "night")])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
