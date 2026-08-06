"""
Graph EDA orchestrator for Class 1 anomaly detection (Phase 1).

Runs the full Phase 1 Robust Statistical Filter sequence per spec:
  1. Load & validate top7 data
  2. Build supply network + print summary
  3. (Optional) Compute PDI per 3-key product composite
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

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from class_1_anomaly_detection.src.ingest.loader import REPO_ROOT
from class_1_anomaly_detection.src.ingest.keys import (
    ROLLING_WINDOW_MONTHS,
    COL_BASE_MONTH,
    COL_SUPPLY_DATE,
    COL_FIRST_RECEIPT_DATE,
    COL_SUPPLIER_SERIAL,
    COL_SUPPLIER_REG,
    COL_SUPPLIER_NAME,
    normalize_supply_entity_id,
)
from class_1_anomaly_detection.src.graph.build_network import (
    build_product_network,
    build_rolling_main_graph,
    build_monthly_network_stats,
    network_summary,
    select_rolling_window_supply,
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
from class_1_anomaly_detection.src.experiments.export_pyg_graph import (
    export_monthly_edge_attrs,
)
from class_1_anomaly_detection.src.experiments.pygod_common import rolling_pyg_dir

OUTPUT_DIR = REPO_ROOT / "class_1_anomaly_detection" / "output"
ROLLING_OUTPUT_DIR = OUTPUT_DIR / "rolling"


def _save_csv(df: pd.DataFrame, name: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  [saved] {path.relative_to(REPO_ROOT)}")
    return path


def _save_csv_to(df: pd.DataFrame, name: str, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{name}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"  [saved] {path.relative_to(REPO_ROOT)}")
    return path


def _validate_anchor_month(anchor_month: str) -> str:
    anchor = str(anchor_month).strip()
    if not re.fullmatch(r"\d{6}", anchor):
        raise ValueError(f"Invalid --anchor-month '{anchor_month}'. Expected YYYYMM.")
    return anchor


def _resolve_anchor_targets(
    supply: pd.DataFrame,
    *,
    anchor_month: str | None,
    all_anchors: bool,
    window: int,
) -> list[str]:
    if COL_BASE_MONTH not in supply.columns:
        return []
    months = sorted(supply[COL_BASE_MONTH].dropna().astype(str).str.strip().unique())
    if not months:
        return []

    if all_anchors:
        start_idx = max(int(window), 1) - 1
        if start_idx >= len(months):
            return [months[-1]]
        return months[start_idx:]

    if anchor_month is not None:
        anchor = _validate_anchor_month(anchor_month)
        if anchor not in months:
            raise ValueError(
                f"Anchor month {anchor} not found in supply data. "
                f"Available range: {months[0]} ~ {months[-1]}."
            )
        return [anchor]

    return [months[-1]]


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
    df["backdated"] = df["lag_days"] < 0
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
            median_lag_days=("lag_days", "median"),
            max_lag_days=("lag_days", "max"),
            min_lag_days=("lag_days", "min"),
            backdated_count=("backdated", "sum"),
            tx_count=("lag_days", "count"),
        )
        .reset_index()
        .sort_values("median_lag_days", ascending=False)
    )
    result["lag_days"] = result["median_lag_days"]
    return result


def _build_rolling_window_exports(
    supply: pd.DataFrame,
    *,
    window: int = ROLLING_WINDOW_MONTHS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build sliding-window (e.g., 3-month) snapshots for every anchor month.

    Returns
    -------
    edges_rolling, nodes_rolling, stats_rolling
    """
    if COL_BASE_MONTH not in supply.columns:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    months = sorted(supply[COL_BASE_MONTH].dropna().astype(str).str.strip().unique())
    if not months:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    edges_records: list[dict] = []
    nodes_records: list[dict] = []
    stats_records: list[dict] = []

    start_idx = max(int(window), 1) - 1
    for anchor in months[start_idx:]:
        supply_window, selected_months = select_rolling_window_supply(
            supply,
            anchor_month=anchor,
            window=window,
        )
        G = build_product_network(supply_window)
        stats = network_summary(G)
        stats_records.append({
            "anchor_month": anchor,
            "window_start": selected_months[0] if selected_months else anchor,
            "window_end": selected_months[-1] if selected_months else anchor,
            "window_month_count": len(selected_months),
            **stats,
        })

        for u, v, key, data in G.edges(keys=True, data=True):
            edges_records.append({
                "anchor_month": anchor,
                "window_start": selected_months[0] if selected_months else anchor,
                "window_end": selected_months[-1] if selected_months else anchor,
                "src": u,
                "dst": v,
                "product_key": data.get("product_key", key),
                "item_serial": data.get("item_serial", ""),
                "model_serial": data.get("model_serial", ""),
                "udi_serial": data.get("udi_serial", ""),
                "weight": data.get("weight", 0.0),
                "tx_count": data.get("tx_count", 1),
                "has_zero_price": data.get("has_zero_price", False),
                "unique_udi_count": data.get("unique_udi_count", 0),
                "has_traceable": data.get("has_traceable", False),
                "has_reimbursable": data.get("has_reimbursable", False),
                "max_device_class": data.get("max_device_class", 0),
                "first_month": data.get("first_month", ""),
                "last_month": data.get("last_month", ""),
                "active_month_count": data.get("active_month_count", 0),
            })

        for n in G.nodes():
            nodes_records.append({
                "anchor_month": anchor,
                "entity_id": n,
                "name": G.nodes[n].get("name", ""),
                "node_type": G.nodes[n].get(
                    "canonical_node_type",
                    G.nodes[n].get("node_type", "other"),
                ),
                "location": G.nodes[n].get("location", ""),
                "ever_supplier": G.nodes[n].get("ever_supplier", False),
                "ever_receiver": G.nodes[n].get("ever_receiver", False),
            })

    return (
        pd.DataFrame(edges_records),
        pd.DataFrame(nodes_records),
        pd.DataFrame(stats_records),
    )


def _export_anchor_bundle(
    supply: pd.DataFrame,
    *,
    anchor_month: str,
    window: int,
) -> dict[str, int | str | None]:
    """
    Export all rolling baseline outputs for a single anchor month.

    Outputs are written under:
      class_1_anomaly_detection/output/rolling/anchor_YYYYMM/
    """
    anchor = _validate_anchor_month(anchor_month)
    out_dir = ROLLING_OUTPUT_DIR / f"anchor_{anchor}"
    supply_window, selected_months = select_rolling_window_supply(
        supply,
        anchor_month=anchor,
        window=window,
    )

    G = build_product_network(supply_window)
    edge_rows = [
        {
            "src": u,
            "dst": v,
            "product_key": data.get("product_key", key),
            "item_serial": data.get("item_serial", ""),
            "model_serial": data.get("model_serial", ""),
            "udi_serial": data.get("udi_serial", ""),
            "weight": data.get("weight", 0.0),
            "tx_count": data.get("tx_count", 1),
            "has_zero_price": data.get("has_zero_price", False),
            "unique_udi_count": data.get("unique_udi_count", 0),
            "has_traceable": data.get("has_traceable", False),
            "has_reimbursable": data.get("has_reimbursable", False),
            "max_device_class": data.get("max_device_class", 0),
            "first_month": data.get("first_month", ""),
            "last_month": data.get("last_month", ""),
            "active_month_count": data.get("active_month_count", 0),
        }
        for u, v, key, data in G.edges(keys=True, data=True)
    ]
    edges_df = pd.DataFrame(edge_rows)
    node_rows = [
        {
            "entity_id": n,
            "name": G.nodes[n].get("name", ""),
            "node_type": G.nodes[n].get(
                "canonical_node_type", G.nodes[n].get("node_type", "other")
            ),
            "location": G.nodes[n].get("location", ""),
            "ever_supplier": G.nodes[n].get("ever_supplier", False),
            "ever_receiver": G.nodes[n].get("ever_receiver", False),
        }
        for n in G.nodes()
    ]
    nodes_df = pd.DataFrame(node_rows)

    bc_df = compute_betweenness_centrality(supply_window, verbose=False)
    hhi_df = compute_hhi(supply_window, verbose=False)
    price_tx_df, price_entity_df = compute_price_zscore(supply_window, verbose=False)
    timelag_df = _compute_timelag(supply_window)
    if timelag_df is None:
        timelag_df = pd.DataFrame(
            columns=[
                "supplier_id",
                "supplier_name",
                "median_lag_days",
                "max_lag_days",
                "min_lag_days",
                "backdated_count",
                "tx_count",
                "lag_days",
            ]
        )

    from class_1_anomaly_detection.src.graph.build_network import aggregate_firm_edges

    firm_edges_df = aggregate_firm_edges(edges_df, include_item_group=False)

    _save_csv_to(edges_df, "network_edges", out_dir)
    _save_csv_to(firm_edges_df, "network_edges_firm", out_dir)
    _save_csv_to(nodes_df, "network_nodes", out_dir)
    _save_csv_to(bc_df, "bc_per_entity", out_dir)
    _save_csv_to(hhi_df, "hhi_per_hospital_group", out_dir)
    _save_csv_to(price_tx_df, "price_zscore_per_transaction", out_dir)
    _save_csv_to(price_entity_df, "price_zscore_per_entity", out_dir)
    _save_csv_to(timelag_df, "timelag_per_entity", out_dir)

    # Export monthly edge_attr snapshots aligned to this anchor's graph skeleton.
    export_monthly_edge_attrs(
        supply_window,
        edges_df,
        months=selected_months,
        target_dir=rolling_pyg_dir(anchor),
        verbose=False,
    )

    manifest = {
        "anchor_month": anchor,
        "window_months": selected_months,
        "window_start": selected_months[0] if selected_months else anchor,
        "window_end": selected_months[-1] if selected_months else anchor,
        "window_size": len(selected_months),
        "rows_supply_window": int(len(supply_window)),
        "nodes": int(nodes_df.shape[0]),
        "edges": int(edges_df.shape[0]),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"  [saved] {(out_dir / 'manifest.json').relative_to(REPO_ROOT)}")
    return manifest


def run_graph_eda(
    *,
    enable_pdi: bool = False,
    anchor_month: str | None = None,
    all_anchors: bool = False,
    window: int = ROLLING_WINDOW_MONTHS,
) -> None:
    print("\n" + "=" * 70)
    print("  Class 1 — Phase 1 Graph EDA")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # Step 1: Load
    # -----------------------------------------------------------------------
    print("\n[Step 1] Loading top7 via Parquet working store (Excel only if missing)...")
    from class_1_anomaly_detection.src.ingest.materialize_parquet import (
        load_top7_prefer_parquet,
    )

    master, supply = load_top7_prefer_parquet(verbose=True)
    anchor_targets = _resolve_anchor_targets(
        supply,
        anchor_month=anchor_month,
        all_anchors=all_anchors,
        window=window,
    )
    if anchor_targets:
        print(
            f"  Anchors to export: {len(anchor_targets)} "
            f"({anchor_targets[0]} ~ {anchor_targets[-1]})"
        )
        primary_anchor = anchor_targets[-1]
    else:
        print("  [warn] No anchor-month column found; anchor exports disabled.")
        primary_anchor = None

    # -----------------------------------------------------------------------
    # Step 2: Network summary + save edge/node lists for the Streamlit app
    # -----------------------------------------------------------------------
    print("\n[Step 2] Building rolling supply network (출고 only, 3-month window)...")
    supply_rolling, rolling_months = select_rolling_window_supply(
        supply,
        anchor_month=primary_anchor,
        window=window,
    )
    G_full = build_rolling_main_graph(
        supply,
        anchor_month=primary_anchor,
        window=window,
    )
    stats = network_summary(G_full)
    print(f"  Nodes         : {stats['nodes']:,}")
    print(f"  Edges         : {stats['edges']:,}")
    print(f"  Density       : {stats['density']}")
    print(f"  WCC           : {stats['weakly_connected_components']}")
    print(f"  Node types    : {stats['node_types']}")

    edge_rows = [
        {
            "src": u,
            "dst": v,
            "product_key": data.get("product_key", key),
            "item_serial": data.get("item_serial", ""),
            "model_serial": data.get("model_serial", ""),
            "udi_serial": data.get("udi_serial", ""),
            "weight": data.get("weight", 0.0),
            "tx_count": data.get("tx_count", 1),
            "has_zero_price": data.get("has_zero_price", False),
            "unique_udi_count": data.get("unique_udi_count", 0),
            "has_traceable": data.get("has_traceable", False),
            "has_reimbursable": data.get("has_reimbursable", False),
            "max_device_class": data.get("max_device_class", 0),
            "first_month": data.get("first_month", ""),
            "last_month": data.get("last_month", ""),
            "active_month_count": data.get("active_month_count", 0),
        }
        for u, v, key, data in G_full.edges(keys=True, data=True)
    ]
    edges_df = pd.DataFrame(edge_rows)
    _save_csv(edges_df, "network_edges")
    node_rows = [
        {
            "entity_id": n,
            "name": G_full.nodes[n].get("name", ""),
            "node_type": G_full.nodes[n].get(
                "canonical_node_type", G_full.nodes[n].get("node_type", "other")
            ),
            "location": G_full.nodes[n].get("location", ""),
            "ever_supplier": G_full.nodes[n].get("ever_supplier", False),
            "ever_receiver": G_full.nodes[n].get("ever_receiver", False),
        }
        for n in G_full.nodes()
    ]
    _save_csv(pd.DataFrame(node_rows), "network_nodes")

    print("\n[Step 2b] Building monthly network summaries...")
    monthly_stats = build_monthly_network_stats(supply)
    if not monthly_stats.empty:
        _save_csv(monthly_stats, "network_monthly_stats")
        print(f"  Months covered: {len(monthly_stats)}")
        print(
            monthly_stats[
                ["month", "nodes", "edges", "weakly_connected_components"]
            ].to_string(index=False)
        )
    else:
        print("  [SKIP] 공급내역기준연월 column absent — monthly stats not computed.")

    if all_anchors:
        print("\n[Step 2c] Building rolling-window snapshots for all anchor months...")
        edges_roll_df, nodes_roll_df, stats_roll_df = _build_rolling_window_exports(
            supply,
            window=window,
        )
        if not stats_roll_df.empty:
            _save_csv(edges_roll_df, "network_edges_rolling")
            _save_csv(nodes_roll_df, "network_nodes_rolling")
            _save_csv(stats_roll_df, "network_window_stats")
            print(f"  Rolling snapshots: {len(stats_roll_df)} anchor months")
            print(
                stats_roll_df[
                    ["anchor_month", "window_start", "window_end", "nodes", "edges"]
                ].to_string(index=False)
            )
        else:
            print("  [SKIP] Rolling-window snapshots not generated.")
    else:
        print("\n[Step 2c] Skipped global rolling snapshots (use --all-anchors to generate).")

    # -----------------------------------------------------------------------
    # Step 3: PDI (optional; disabled by default for Class 1 runtime efficiency)
    # -----------------------------------------------------------------------
    pdi_df = pd.DataFrame()
    pdi_stats = {
        "total_udis": 0,
        "high_risk_count": 0,
        "high_risk_pct": 0.0,
        "distribution": {},
    }
    if enable_pdi:
        print("\n[Step 3] Computing Path Depth Index (PDI) per 3-key product composite...")
        pdi_df = compute_pdi(supply_rolling, master=master, verbose=True)
        _save_csv(pdi_df, "pdi_per_udi")

        pdi_stats = pdi_summary(pdi_df)
        print(f"\n  PDI Summary:")
        for k, v in pdi_stats.items():
            if k != "distribution":
                print(f"    {k}: {v}")
        print(f"    distribution: {pdi_stats['distribution']}")
    else:
        print("\n[Step 3] PDI disabled (Class 1 default).")

    # -----------------------------------------------------------------------
    # Step 4: Betweenness Centrality
    # -----------------------------------------------------------------------
    print("\n[Step 4] Computing Betweenness Centrality (BC)...")
    bc_df = compute_betweenness_centrality(supply_rolling, verbose=True)
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
    hhi_df = compute_hhi(supply_rolling, verbose=True)
    _save_csv(hhi_df, "hhi_per_hospital_group")

    hhi_stats = hhi_summary(hhi_df)
    print(f"\n  HHI Summary:")
    for k, v in hhi_stats.items():
        print(f"    {k}: {v}")

    # -----------------------------------------------------------------------
    # Step 6: Price Margin Robust Z-Score (spec Phase 1 Robust Statistical Filter)
    # -----------------------------------------------------------------------
    print("\n[Step 6] Computing Price Margin Robust Z-Score (MAD-based, spec Phase 1)...")
    price_tx_df, price_entity_df = compute_price_zscore(supply_rolling, verbose=True)
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
    timelag_df = _compute_timelag(supply_rolling)
    if timelag_df is not None:
        _save_csv(timelag_df, "timelag_per_entity")
        hi = int((timelag_df["lag_days"] > 30).sum())
        print(f"  Rows with time-lag > 30 days: {hi:,}/{len(timelag_df):,}")
        print(timelag_df[["supplier_name", "lag_days"]].head(20).to_string(index=False))
    else:
        print("  [SKIP] One or both date columns absent — time-lag not computed.")

    # -----------------------------------------------------------------------
    # Step 8b: Monthly edge_attr tensors (GNN temporal snapshots)
    # -----------------------------------------------------------------------
    print("\n[Step 8b] Exporting monthly edge_attr tensors for GNN snapshots...")
    monthly_manifest = export_monthly_edge_attrs(
        supply_rolling,
        edges_df,
        months=rolling_months,
        verbose=True,
    )
    if monthly_manifest:
        manifest_path = OUTPUT_DIR / "pyg" / "monthly_manifest.json"
        print(f"  Months exported: {len(monthly_manifest)}")
        print(f"  Manifest: {manifest_path.relative_to(REPO_ROOT)}")

    # -----------------------------------------------------------------------
    # Step 8: Consolidated anomaly flag summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  Consolidated Phase 1 Anomaly Indicator Summary (all 5 spec metrics)")
    print("=" * 70)
    if enable_pdi:
        print(f"  PDI       — High-risk products (PDI≥3)       : "
              f"{pdi_stats['high_risk_count']}/{pdi_stats['total_udis']} "
              f"({pdi_stats['high_risk_pct']:.1%})")
    else:
        print("  PDI       — Disabled in Class 1 (moved to Class 3 plan)")
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

    # -----------------------------------------------------------------------
    # Step 9: Anchor-scoped exports (rolling/anchor_YYYYMM)
    # -----------------------------------------------------------------------
    if anchor_targets:
        print("\n[Step 9] Exporting anchor-scoped rolling outputs...")
        for anchor in anchor_targets:
            print(f"\n  - Anchor {anchor}")
            manifest = _export_anchor_bundle(
                supply,
                anchor_month=anchor,
                window=window,
            )
            print(
                "    window: "
                f"{manifest['window_start']} ~ {manifest['window_end']}  "
                f"nodes={manifest['nodes']:,} edges={manifest['edges']:,}"
            )
    else:
        print("\n[Step 9] Skipped (no anchor targets resolved).")

    print("\n[Phase 1 EDA complete] Outputs saved to class_1_anomaly_detection/output/")
    print("Next step: PM reviews findings → notify_phase_completion → HALT")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Class 1 graph EDA")
    parser.add_argument(
        "--anchor-month",
        type=str,
        default=None,
        help="Anchor month YYYYMM for rolling-window outputs (default: latest month).",
    )
    parser.add_argument(
        "--all-anchors",
        action="store_true",
        help="Generate anchor-scoped rolling outputs for all valid anchor months.",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=ROLLING_WINDOW_MONTHS,
        help=f"Rolling window size in months (default: {ROLLING_WINDOW_MONTHS}).",
    )
    parser.add_argument(
        "--enable-pdi",
        action="store_true",
        help="Enable PDI computation (disabled by default).",
    )
    args = parser.parse_args()
    run_graph_eda(
        enable_pdi=args.enable_pdi,
        anchor_month=args.anchor_month,
        all_anchors=args.all_anchors,
        window=args.window,
    )


if __name__ == "__main__":
    main()
