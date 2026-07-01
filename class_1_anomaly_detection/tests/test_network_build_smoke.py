"""Smoke tests for rolling product network and monthly edge export."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from class_1_anomaly_detection.src.graph.build_network import (
    build_rolling_main_graph,
    build_month_edge_aggregates,
    collapse_to_digraph,
    network_summary,
)
from class_1_anomaly_detection.src.experiments.export_pyg_graph import export_monthly_edge_attrs
from class_1_anomaly_detection.src.ingest.keys import (
    COL_AMOUNT,
    COL_BASE_MONTH,
    COL_DEVICE_CLASS,
    COL_HOSPITAL_CODE,
    COL_ITEM_SERIAL,
    COL_MODEL_SERIAL,
    COL_RECEIVER_NAME,
    COL_RECEIVER_REG,
    COL_RECEIVER_SERIAL,
    COL_RECEIVER_TYPE,
    COL_REIMBURSABLE,
    COL_SUPPLY_CLASS,
    COL_SUPPLIER_NAME,
    COL_SUPPLIER_REG,
    COL_SUPPLIER_SERIAL,
    COL_SUPPLIER_TYPE,
    COL_TRACEABLE,
    COL_UDI_SERIAL,
    COL_UNIT_PRICE,
    COL_SUPPLY_QTY,
)


def _synthetic_supply(n: int = 200) -> pd.DataFrame:
    rows = []
    for i in range(n):
        month = "202601" if i % 3 == 0 else ("202602" if i % 3 == 1 else "202603")
        rows.append({
            COL_SUPPLY_CLASS: "출고",
            COL_BASE_MONTH: month,
            COL_SUPPLIER_SERIAL: 100 + (i % 5),
            COL_SUPPLIER_REG: f"111{i % 5}",
            COL_SUPPLIER_NAME: f"Supplier{i % 5}",
            COL_SUPPLIER_TYPE: "제조업",
            COL_RECEIVER_SERIAL: 200 + (i % 7),
            COL_RECEIVER_REG: f"222{i % 7}",
            COL_RECEIVER_NAME: f"Receiver{i % 7}",
            COL_RECEIVER_TYPE: "의료기관",
            COL_HOSPITAL_CODE: f"H{i % 7}",
            COL_ITEM_SERIAL: 10 + (i % 3),
            COL_MODEL_SERIAL: 20 + (i % 2),
            COL_UDI_SERIAL: 30 + (i % 4),
            COL_AMOUNT: 1000 + i,
            COL_UNIT_PRICE: 100,
            COL_SUPPLY_QTY: 10,
            COL_DEVICE_CLASS: 2,
            COL_TRACEABLE: "Y",
            COL_REIMBURSABLE: "N",
        })
    return pd.DataFrame(rows)


def test_rolling_graph_and_monthly_export(tmp_path: Path, monkeypatch) -> None:
    supply = _synthetic_supply()
    G = build_rolling_main_graph(supply)
    stats = network_summary(G)
    assert stats["nodes"] > 0
    assert stats["edges"] > 0

    collapsed = collapse_to_digraph(G)
    assert collapsed.number_of_edges() <= G.number_of_edges()

    edge_rows = [
        {
            "src": u,
            "dst": v,
            "product_key": d.get("product_key", k),
            "weight": d.get("weight", 0),
            "tx_count": d.get("tx_count", 1),
            "has_zero_price": d.get("has_zero_price", False),
            "unique_udi_count": d.get("unique_udi_count", 1),
            "has_traceable": d.get("has_traceable", False),
            "has_reimbursable": d.get("has_reimbursable", False),
            "max_device_class": d.get("max_device_class", 0),
        }
        for u, v, k, d in G.edges(keys=True, data=True)
    ]
    edges_df = pd.DataFrame(edge_rows)

    out_pyg = tmp_path / "pyg"
    monkeypatch.setattr(
        "class_1_anomaly_detection.src.experiments.export_pyg_graph.PYG_DIR",
        out_pyg,
    )
    monkeypatch.setattr(
        "class_1_anomaly_detection.src.experiments.export_pyg_graph._REPO_ROOT",
        tmp_path,
    )

    manifest = export_monthly_edge_attrs(supply, edges_df, verbose=False)
    assert len(manifest) == 3
    assert (out_pyg / "monthly_manifest.json").exists()

    m = build_month_edge_aggregates(supply, "202601")
    assert not m.empty

    npz = np.load(out_pyg / "pyg_monthly_202601.npz")
    assert npz["edge_attr_month"].shape == (len(edges_df), 7)

    with open(out_pyg / "monthly_manifest.json", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded[0]["month"] == "202601"
