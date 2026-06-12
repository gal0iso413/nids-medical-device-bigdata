#!/usr/bin/env python3
"""
Post Hermes role deliverable completion to Slack.

Usage (from repo root, with venv active):

  python scripts/notify_hermes_deliverable.py \\
    --agent class_1_anomaly_detection \\
    --role methods-researcher \\
    --path class_1_anomaly_detection/research/2025-06-network-methods.md \\
    --summary "Compared PDI/BC/HHI vs graph outlier methods; recommends hybrid."
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

from shared_utils.slacker import AgentSlacker  # noqa: E402

AGENT_CHOICES = (
    "class_1_anomaly_detection",
    "class_2_supply_forecast",
    "class_3_impact_evaluation",
)

ROLE_CHOICES = (
    "methods-researcher",
    "data-profiler",
    "spec-auditor",
)


def _load_env(agent: str) -> None:
    load_dotenv(REPO_ROOT / ".env")
    agent_env = REPO_ROOT / agent / ".env"
    if agent_env.exists():
        load_dotenv(agent_env)


def main() -> int:
    parser = argparse.ArgumentParser(description="Notify Slack of a Hermes role deliverable.")
    parser.add_argument("--agent", required=True, choices=AGENT_CHOICES)
    parser.add_argument("--role", required=True, choices=ROLE_CHOICES)
    parser.add_argument(
        "--path",
        required=True,
        help="Repo-relative path to the deliverable markdown file.",
    )
    parser.add_argument(
        "--summary",
        required=True,
        help="Short summary for Slack (keep under ~500 characters).",
    )
    parser.add_argument(
        "--broadcast-global",
        action="store_true",
        help="Mirror to SLACK_GENERAL_WEBHOOK_URL (#general-pm-board).",
    )
    args = parser.parse_args()

    deliverable = REPO_ROOT / args.path
    if not deliverable.is_file():
        print(f"Warning: deliverable not found at {deliverable}", file=sys.stderr)

    _load_env(args.agent)
    slacker = AgentSlacker(args.agent)
    slacker.notify_hermes_deliverable(
        args.role,
        args.path,
        args.summary,
        broadcast_global=args.broadcast_global,
    )
    print(f"Slack notification sent for {args.agent} ({args.role}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
