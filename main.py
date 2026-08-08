#!/usr/bin/env python3
"""
Verification Agent — CLI entrypoint

Usage:
    python main.py "URGENT: Click here to verify your account"
    python main.py "https://www.bbc.co.uk/news/some-article"
    python main.py   (interactive prompt)
"""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "WARNING"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from src.loop import run_verification
from src.formatter import render_cli
from shared.telemetry import TelemetryCallback


def _check_env():
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")
        sys.exit(1)


def main():
    _check_env()

    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        print("Verification Agent — paste a URL, message, or headline to check.")
        print("Type 'quit' to exit.\n")
        user_input = input("Input: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            sys.exit(0)

    if not user_input:
        print("No input provided.")
        sys.exit(1)

    print("\nChecking... (this may take a few seconds)\n")

    telemetry = TelemetryCallback()
    response = run_verification(user_input)
    print(render_cli(response))

    # Show phase log in debug mode
    if os.environ.get("LOG_LEVEL", "").upper() == "DEBUG":
        print("Phase log:")
        for step in response.get("phase_log", []):
            print(f"  → {step}")
        print()
        print("Telemetry:", telemetry.summary())


if __name__ == "__main__":
    main()
