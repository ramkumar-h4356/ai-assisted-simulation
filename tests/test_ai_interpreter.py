
"""Unit tests for the AI interpreter without real API calls."""

import json
import unittest
from unittest.mock import MagicMock, patch

from simulations.ai_interpreter import generate_model


class AIInterpreterTests(unittest.TestCase):
    @patch("simulations.ai_interpreter.Groq")
    def test_generates_model_from_valid_json(self, mock_groq):
        expected = {
            "name": "Test Hospital",
            "resources": [{"name": "Doctor", "capacity": 2}],
            "jobs": [
                {
                    "entity_id": "Patient-1",
                    "arrival_time": 0,
                    "stages": [
                        {
                            "resource_name": "Doctor",
                            "service_duration": 10,
                        }
                    ],
                }
            ],
        }

        client = mock_groq.return_value
        message = MagicMock()
        message.content = json.dumps(expected)
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=message)
        ]

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            result = generate_model("Simulate a small hospital")

        self.assertEqual(result, expected)
        client.chat.completions.create.assert_called_once()
        client.close.assert_called_once()

    def test_rejects_empty_request(self):
        with self.assertRaises(ValueError):
            generate_model("   ")

    def test_rejects_non_string_request(self):
        with self.assertRaises(TypeError):
            generate_model(123)

    @patch("simulations.ai_interpreter.Groq")
    def test_rejects_invalid_json(self, mock_groq):
        client = mock_groq.return_value
        message = MagicMock()
        message.content = "This is not JSON"
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=message)
        ]

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                generate_model("Simulate a hospital")

        client.close.assert_called_once()

    @patch("simulations.ai_interpreter.Groq")
    def test_rejects_non_object_json(self, mock_groq):
        client = mock_groq.return_value
        message = MagicMock()
        message.content = json.dumps(["not", "an", "object"])
        client.chat.completions.create.return_value.choices = [
            MagicMock(message=message)
        ]

        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            with self.assertRaisesRegex(ValueError, "JSON object"):
                generate_model("Simulate a hospital")

        client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
