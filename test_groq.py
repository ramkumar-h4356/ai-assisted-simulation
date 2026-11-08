
"""Test Groq's GPT-OSS model with streaming output."""

import os

from dotenv import load_dotenv
from groq import Groq


def main():
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("GROQ_API_KEY was not found in .env")
        return

    try:
        client = Groq(api_key=api_key)

        print("Sending request to Groq...\n")

        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Explain discrete-event simulation in "
                        "two sentences."
                    ),
                }
            ],
            temperature=0.2,
            max_completion_tokens=512,
            top_p=1,
            reasoning_effort="medium",
            stream=True,
        )

        print("Groq response:\n")

        for chunk in completion:
            if not chunk.choices:
                continue

            content = chunk.choices[0].delta.content
            if content:
                print(content, end="", flush=True)

        print("\n\nGroq connection successful!")

    except Exception as error:
        print("\nGroq request failed.")
        print("Error type:", type(error).__name__)
        print("Details:", error)


if __name__ == "__main__":
    main()
