"""
Create synthetic sample Excel files under shared_data/ (sample_ prefix).
Run from project root: python scripts/generate_sample_data.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "shared_data"

MASTER_NAME = "sample_master_registration_data.xlsx"
TX_NAME = "sample_transaction_supply_data.xlsx"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    master = pd.DataFrame(
        {
            "entity_id": [f"E{i:04d}" for i in range(1, 51)],
            "entity_name": [f"Site-{i}" for i in range(1, 51)],
            "region": ["North", "South", "East", "West"] * 12 + ["North", "South"],
            "supplier_id": [f"S{(i % 10) + 1:03d}" for i in range(1, 51)],
            "registration_date": pd.date_range("2020-01-01", periods=50, freq="W"),
            "capacity_units": (pd.Series(range(50)) * 17 + 100).astype(float),
        }
    )
    master.loc[5:7, "capacity_units"] = None

    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    rows = []
    for eid in master["entity_id"].head(20):
        for d in dates:
            rows.append(
                {
                    "entity_id": eid,
                    "transaction_date": d,
                    "supply_qty": max(0, 50 + (hash((eid, d)) % 40) - 20),
                    "demand_qty": max(0, 48 + (hash((d, eid)) % 35) - 15),
                }
            )
    transactions = pd.DataFrame(rows)

    master_path = OUT / MASTER_NAME
    tx_path = OUT / TX_NAME
    master.to_excel(master_path, index=False)
    transactions.to_excel(tx_path, index=False)
    print(f"Wrote {master_path} ({len(master)} rows)")
    print(f"Wrote {tx_path} ({len(transactions)} rows)")


if __name__ == "__main__":
    main()
