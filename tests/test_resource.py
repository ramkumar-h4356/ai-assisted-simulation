"""Unit tests for the simulation Resource domain object."""

import unittest

from simulations.resource import Resource


class ResourceTests(unittest.TestCase):
    def test_resource_keeps_name_and_capacity(self) -> None:
        resource = Resource("checkout", capacity=3)

        self.assertEqual(resource.name, "checkout")
        self.assertEqual(resource.capacity, 3)

    def test_capacity_defaults_to_one(self) -> None:
        resource = Resource("single_server")

        self.assertEqual(resource.capacity, 1)

    def test_name_must_be_a_non_empty_string(self) -> None:
        for name in ("", "   ", None, 7):
            with self.subTest(name=name):
                with self.assertRaises((TypeError, ValueError)):
                    Resource(name)  # type: ignore[arg-type]

    def test_capacity_must_be_a_positive_integer(self) -> None:
        for capacity in (0, -1):
            with self.subTest(capacity=capacity):
                with self.assertRaises(ValueError):
                    Resource("server", capacity=capacity)

        for capacity in (1.5, "2", True):
            with self.subTest(capacity=capacity):
                with self.assertRaises(TypeError):
                    Resource("server", capacity=capacity)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()