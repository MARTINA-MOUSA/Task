"""Command line entry point for the insurance agent."""

from __future__ import annotations

import argparse
import json
import uuid

from agentic_insurance.config import APP_NAME
from agentic_insurance.evaluation.harness import run_evaluation
from agentic_insurance.graph import build_graph
from agentic_insurance.state import build_initial_state


def run_request(user_request: str) -> dict:
    app = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = app.invoke(build_initial_state(user_request), config=config)
    return result.get("final_output", result)


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} recommendation system")
    parser.add_argument("user_request", nargs="?", help="Insurance recommendation request")
    parser.add_argument("--evaluate", action="store_true", help="Run the evaluation scenarios")
    args = parser.parse_args()

    if args.evaluate:
        run_evaluation()
        return

    user_request = args.user_request or input("Enter your insurance request: ").strip()
    result = run_request(user_request)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
