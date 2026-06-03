import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from conductor.dispatch import run_conductor_turn


def run() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path, override=True)

    client = anthropic.Anthropic()

    print("Nake the Conductor is ready. Type your request (Ctrl+C to exit).\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        try:
            run_conductor_turn(client, user_input)
        except Exception as e:
            print(f"\n[error: {e}]")

        print()


if __name__ == "__main__":
    run()
