"""
Phase 1 exit notifier — Class 2 Supply Forecast & Early Warning.

Run AFTER reviewing output/ (monthly index, expiry profile, disruption candidates).
Posts notify_phase_completion to Slack, then HALTS.

Usage (from repo root with .venv active):
    python class_2_supply_forecast/scripts/notify_phase1_complete.py

PM must unlock Phase 2 Strategy in Cursor Composer before any further work.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(_REPO_ROOT / "class_2_supply_forecast" / ".env")

from shared_utils.slacker import AgentSlacker

INSIGHTS = (
    "Phase 1 EDA complete on top7 modeling tier (221 master / 704,315 supply rows). "
    "Key findings: (1) 3-key composite join achieves 100% supply coverage; .0 suffix stripping applied. "
    "(2) Monthly supply index built with rolling 3m/6m features; saved to output/. "
    "(3) 사용기한 (expiry date) is 92.97% populated — strong survival proxy for Phase 2. "
    "(4) 180-day silence disruption flag is exploratory; PM must validate threshold definition. "
    "(5) 공급단가 segmentation: hospital supply has 9.14% zero-price vs 82.59% B2B zero-price. "
    "(6) Price cap (50M KRW) applied; 8.8T KRW barcode outlier neutralised. "
    "Awaiting PM approval to advance to Phase 2 Strategy."
)


def main() -> None:
    slacker = AgentSlacker("class_2_supply_forecast")
    slacker.notify_phase_completion(
        phase_name="Phase 1 — Autonomous EDA",
        analytical_insights=INSIGHTS,
    )
    print("[notify] Phase 1 completion message sent to Slack.")
    print("[HALT] Class 2 agent stops here. Await PM directive in Cursor Composer.")
    sys.exit(0)


if __name__ == "__main__":
    main()
