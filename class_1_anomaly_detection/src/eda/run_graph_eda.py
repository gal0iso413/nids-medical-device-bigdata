"""
Graph EDA orchestrator for Class 1 anomaly detection (Phase 1).

Runs the full Phase 1 Robust Statistical Filter sequence per spec:
  1. Load & validate top7 data
  2. Build supply network + print summary
  3. Compute PDI per UDI-DI (enriched with device class from master)
  4. Compute Betweenness Centrality
  5. Compute HHI per (hospital, item) — 품목명-level per spec HHI_item
  6. Compute Price Margin Robust Z-Score (spec Phase 1 Robust Statistical Filter)
  7. Compute Time-lag (가납 의심) — 공급일자 vs 최초접수일자
  8. Save output CSVs under class_1_anomaly_detection/output/
  9. Print consolidated anomaly summary

Phase 1 scope:
  - All five spec indicators computed and saved.
  - No composite scoring (weights = PM decision for Phase 2).
  - No graph ML (Isolation Forest deferred to Phase 2 Strategy).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from class_1_anomaly_detection.src.ingest.loader import load_top7, REPO_ROOT
from class_1_anomaly_detection.src.ingest.keys import (
    join_master_supply,
    COL_SUPPLY_DATE,
    COL_FIRST_RECEIPT_DATE,
    COL_SUPPLIER_SERIAL,
    COL_SUPPLIER_REG,
    COL_SUPPLIER_NAME,
    normalize_supply_entity_id,
)
from class_1_anomaly_detection.src.graph.build_network import (
    build_supply_network,
    network_summary,
)
from class_1_anomaly_detection.src.graph.metrics_pdi import compute_pdi, pdi_summary
from class_1_anomaly_detection.src.graph.metrics_bc import (
    compute_betweenness_centrality,
    bc_summary,
)
from class_1_anomaly_detection.src.graph.metrics_hhi import compute_hhi, hhi_summary
from class_1_anomaly_detection.src.graph.metrics_price_zscore import (
    compute_price_zscore,
    price_zscore_summary,
)

OUTPUT_DIR = REPO_ROOT / "class_1_anomaly_detection" / "output"


def _save_csv(df: pd.DataFrame, name: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  [saved] {path.relative_to(REPO_ROOT)}")
    return path


def _compute_timelag(supply: pd.DataFrame) -> pd.DataFrame | None:
    """
    Compute 가납(수탁) 의심 지연일수 (spec §2 착수보고서 Engineered Features).

    Time-lag = 최초접수일자 (admin receipt date) - 공급일자 (physical supply date).
    Positive values indicate delayed administrative acceptance — a 가납 risk signal.
    """
    if COL_SUPPLY_DATE not in supply.columns or COL_FIRST_RECEIPT_DATE not in supply.columns:
        return None

    df = supply[[COL_SUPPLIER_SERIAL, COL_SUPPLIER_REG, COL_SUPPLIER_NAME,
                 COL_SUPPLY_DATE, COL_FIRST_RECEIPT_DATE]].copy()

    # Date columns may arrive as int YYMMDD (Korean format) or datetime objects
    for col in [COL_SUPPLY_DATE, COL_FIRST_RECEIPT_DATE]:
        if not pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = pd.to_datetime(
                df[col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True),
                format="%Y%m%d",
                errors="coerce",
            )

    df = df.dropna(subset=[COL_SUPPLY_DATE, COL_FIRST_RECEIPT_DATE])
    if df.empty:
        return None

    df["lag_days"] = (df[COL_FIRST_RECEIPT_DATE] - df[COL_SUPPLY_DATE]).dt.days
    df["supplier_id"] = df.apply(
        lambda r: normalize_supply_entity_id(
            r.get(COL_SUPPLIER_SERIAL),
            r.get(COL_SUPPLIER_REG),
            r.get(COL_SUPPLIER_NAME),
        ),
        axis=1,
    )

    result = (
        df.groupby("supplier_id")
        .agg(
            supplier_name=(COL_SUPPLIER_NAME, "first"),
            lag_days=("lag_days", "median"),
            max_lag_days=("lag_days", "max"),
            tx_count=("lag_days", "count"),
        )
        .reset_index()
        .rename(columns={"lag_days": "median_lag_days", "max_lag_days": "max_lag_days"})
        .sort_values("median_lag_days", ascending=False)
    )
    result["lag_days"] = result["median_lag_days"]
    return result


def run_graph_eda() -> None:
    print("\n" + "=" * 70)
    print("  Class 1 — Phase 1 Graph EDA")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # Step 1: Load
    # -----------------------------------------------------------------------
    print("\n[Step 1] Loading top7 workbooks...")
    master, supply = load_top7(verbose=True)

    # -----------------------------------------------------------------------
    # Step 2: Network summary + save edge/node lists for the Streamlit app
    # -----------------------------------------------------------------------
    print("\n[Step 2] Building supply network (all edges, including zero-price B2B)...")
    G_full = build_supply_network(supply, include_zero_price=True, hospital_only=False)
    stats = network_summary(G_full)
    print(f"  Nodes         : {stats['nodes']:,}")
    print(f"  Edges         : {stats['edges']:,}")
    print(f"  Density       : {stats['density']}")
    print(f"  WCC           : {stats['weakly_connected_components']}")
    print(f"  Node types    : {stats['node_types']}")

    # Save edge list so the Streamlit app can render the network from CSV alone
    # (avoids loading the 700k-row Excel file inside the UI process on Windows)
    edge_rows = [
        {"src": u, "dst": v,
         "weight": G_full[u][v].get("weight", 0.0),
         "tx_count": G_full[u][v].get("tx_count", 1)}
        for u, v in G_full.edges()
    ]
    _save_csv(pd.DataFrame(edge_rows), "network_edges")
    node_rows = [
        {"entity_id": n,
         "name": G_full.nodes[n].get("name", ""),
         "node_type": G_full.nodes[n].get("node_type", "unknown")}
        for n in G_full.nodes()
    ]
    _save_csv(pd.DataFrame(node_rows), "network_nodes")

    # -----------------------------------------------------------------------
    # Step 3: PDI — pass master for device-class enrichment (spec Phase 1)
    # -----------------------------------------------------------------------
    print("\n[Step 3] Computing Path Depth Index (PDI) per UDI-DI...")
    pdi_df = compute_pdi(supply, master=master, verbose=True)
    _save_csv(pdi_df, "pdi_per_udi")

    pdi_stats = pdi_summary(pdi_df)
    print(f"\n  PDI Summary:")
    for k, v in pdi_stats.items():
        if k != "distribution":
            print(f"    {k}: {v}")
    print(f"    distribution: {pdi_stats['distribution']}")

    # -----------------------------------------------------------------------
    # Step 4: Betweenness Centrality
    # -----------------------------------------------------------------------
    print("\n[Step 4] Computing Betweenness Centrality (BC)...")
    bc_df = compute_betweenness_centrality(supply, verbose=True)
    _save_csv(bc_df, "bc_per_entity")

    bc_stats = bc_summary(bc_df)
    print(f"\n  BC Summary:")
    for k, v in bc_stats.items():
        if k != "by_node_type":
            print(f"    {k}: {v}")

    # -----------------------------------------------------------------------
    # Step 5: HHI — 품목명 level (spec HHI_item)
    # -----------------------------------------------------------------------
    print("\n[Step 5] Computing HHI per (hospital, item name — 품목명)...")
    hhi_df = compute_hhi(supply, verbose=True)
    _save_csv(hhi_df, "hhi_per_hospital_group")

    hhi_stats = hhi_summary(hhi_df)
    print(f"\n  HHI Summary:")
    for k, v in hhi_stats.items():
        print(f"    {k}: {v}")

    # -----------------------------------------------------------------------
    # Step 6: Price Margin Robust Z-Score (spec Phase 1 Robust Statistical Filter)
    # -----------------------------------------------------------------------
    print("\n[Step 6] Computing Price Margin Robust Z-Score (MAD-based, spec Phase 1)...")
    price_tx_df, price_entity_df = compute_price_zscore(supply, verbose=True)
    _save_csv(price_tx_df, "price_zscore_per_transaction")
    _save_csv(price_entity_df, "price_zscore_per_entity")

    price_stats = price_zscore_summary(price_tx_df, price_entity_df)
    print(f"\n  Price Z-Score Summary:")
    for k, v in price_stats.items():
        print(f"    {k}: {v}")

    # -----------------------------------------------------------------------
    # Step 7: Time-lag (가납 의심 — spec Engineered Feature)
    # -----------------------------------------------------------------------
    print("\n[Step 7] Computing time-lag (가납 의심 지연일수)...")
    timelag_df = _compute_timelag(supply)
    if timelag_df is not None:
        _save_csv(timelag_df, "timelag_per_entity")
        hi = int((timelag_df["lag_days"] > 30).sum())
        print(f"  Rows with time-lag > 30 days: {hi:,}/{len(timelag_df):,}")
        print(timelag_df[["supplier_name", "lag_days"]].head(20).to_string(index=False))
    else:
        print("  [SKIP] One or both date columns absent — time-lag not computed.")

    # -----------------------------------------------------------------------
    # Step 8: Consolidated anomaly flag summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  Consolidated Phase 1 Anomaly Indicator Summary (all 5 spec metrics)")
    print("=" * 70)
    print(f"  PDI       — High-risk UDIs (PDI≥3)         : "
          f"{pdi_stats['high_risk_count']}/{pdi_stats['total_udis']} "
          f"({pdi_stats['high_risk_pct']:.1%})")
    print(f"  BC        — High-risk gatekeepers (p95)     : "
          f"{bc_stats['high_risk_count']}/{bc_stats['total_nodes']} "
          f"({bc_stats['high_risk_pct']:.1%})")
    print(f"  HHI       — High-concentration pairs        : "
          f"{hhi_stats['high_concentration']}/{hhi_stats['total_pairs']} "
          f"({hhi_stats['high_concentration']/max(hhi_stats['total_pairs'],1):.1%})")
    print(f"  PriceZ    — Flagged transactions (|Z|>2.0)  : "
          f"{price_stats['flagged_tx']}/{price_stats['total_tx_evaluated']} "
          f"({price_stats['flagged_tx_pct']:.1%})")
    if timelag_df is not None:
        hi_lag = int((timelag_df["lag_days"] > 30).sum())
        print(f"  Time-lag  — Rows >30 days lag               : "
              f"{hi_lag:,}/{len(timelag_df):,}")
    print("\n  NOTE: Composite scoring deferred to Phase 2 (weights = PM decision).")
    print("=" * 70)

    print("\n[Phase 1 EDA complete] Outputs saved to class_1_anomaly_detection/output/")
    print("Next step: PM reviews findings → notify_phase_completion → HALT")


if __name__ == "__main__":
    run_graph_eda()
