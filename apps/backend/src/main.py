"""Demo entry point for the agent core (no API keys required).

Runs the full end-to-end flow against the in-process mock provider:

    .venv/bin/python apps/backend/src/main.py "Run the demo tool."

The same code path is reused once real model providers and real tools are
added (see ROADMAP.md). Exit code 0 only when the task COMPLETED.
"""

from __future__ import annotations

import argparse
import logging

from agent_core import Agent, Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one request through the agent core (mock provider)."
    )
    parser.add_argument(
        "request",
        nargs="?",
        default="Run the demo tool.",
        help="Natural-language request to run.",
    )
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    settings.configure_logging()
    log = logging.getLogger("apps.backend")
    log.info("agent=%s", settings.agent_name)

    agent = Agent.create_demo()
    task = agent.run(args.request)

    for event in agent.events.history:
        log.info("event: %s %s", event.type.value, event.data)

    print(f"task_id: {task.id}")
    print(f"state:   {task.state.value}")
    print(f"steps:   {len(task.steps)}")
    print(f"result:  {task.result!r}")
    if task.error:
        print(f"error:   {task.error}")
    return 0 if task.state.value == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
