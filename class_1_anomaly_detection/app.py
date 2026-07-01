"""
Class 1 — Supply Chain Anomaly Explorer (Phase 1 prototype)

Reads pre-computed output CSVs from class_1_anomaly_detection/output/.
Run run_graph_eda.py first (or again) to refresh them, then click
"Reload data" in the sidebar.

GNN Review tab reads per-model scores from output/ml/ (run_pygod_compare.py).

Launch:  streamlit run class_1_anomaly_detection/app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
import streamlit as st

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

OUTPUT = _HERE / "output"
ML_OUTPUT = OUTPUT / "ml"
ROLLING_OUTPUT_ROOT = OUTPUT / "rolling"
ANCHOR_PREFIX = "anchor_"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Class 1 · Supply Chain Anomaly Explorer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
_TYPE_COLOR = {
    "manufacturer": "#4c78a8",
    "importer":     "#9ecae9",
    "distributor":  "#f58518",
    "hospital":     "#54a24b",
    "other":        "#aec7e8",
    "unknown":      "#c7c7c7",
}
_RISK_COLOR  = "#e41a1c"
_WARN_COLOR  = "#f58518"
_GOOD_COLOR  = "#54a24b"
_FOCAL_RING_COLOR = "#6a1b9a"   # purple — selected / focal entity
_BC_HIGH_RING_COLOR = "#0b8f3d"  # green ring — BC p95 high-risk (non-focal); distinct from distributor orange

# slug -> (display name, score column, rank column, label column)
GNN_MODELS: dict[str, tuple[str, str, str, str]] = {
    "dominant": ("DOMINANT", "dominant_score", "dominant_rank", "dominant_label"),
    "anomalydae": ("AnomalyDAE", "anomalydae_score", "anomalydae_rank", "anomalydae_label"),
    "gadnr": ("GAD-NR", "gadnr_score", "gadnr_rank", "gadnr_label"),
    "ocgnn": ("OCGNN", "ocgnn_score", "ocgnn_rank", "ocgnn_label"),
    "isoforest": ("IsoForest (GAD-NR emb)", "isoforest_score", "isoforest_rank", "isoforest_label"),
}


def list_available_anchor_months() -> list[str]:
    if not ROLLING_OUTPUT_ROOT.exists():
        return []
    anchors: list[str] = []
    for p in ROLLING_OUTPUT_ROOT.iterdir():
        if p.is_dir() and p.name.startswith(ANCHOR_PREFIX):
            anchor = p.name.removeprefix(ANCHOR_PREFIX)
            if anchor.isdigit() and len(anchor) == 6:
                anchors.append(anchor)
    return sorted(set(anchors))


def _data_root(anchor_month: str | None) -> Path:
    if anchor_month:
        return ROLLING_OUTPUT_ROOT / f"{ANCHOR_PREFIX}{anchor_month}"
    return OUTPUT


def _ml_root(anchor_month: str | None) -> Path:
    if anchor_month:
        return ML_OUTPUT / f"{ANCHOR_PREFIX}{anchor_month}"
    return ML_OUTPUT


# ---------------------------------------------------------------------------
# CSV loader (cached; clear via sidebar button)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading output CSVs…")
def load_outputs(anchor_month: str | None) -> dict[str, pd.DataFrame]:
    base = _data_root(anchor_month)

    def _read(name: str) -> pd.DataFrame:
        p = base / f"{name}.csv"
        if p.exists():
            return pd.read_csv(p)
        return pd.DataFrame()

    return {
        "pdi":          _read("pdi_per_udi"),
        "bc":           _read("bc_per_entity"),
        "hhi":          _read("hhi_per_hospital_group"),
        "pz_entity":    _read("price_zscore_per_entity"),
        "pz_tx":        _read("price_zscore_per_transaction"),
        "timelag":      _read("timelag_per_entity"),
        "net_edges":    _read("network_edges"),
        "net_nodes":    _read("network_nodes"),
        "net_edges_roll": _read("network_edges_rolling"),
        "net_nodes_roll": _read("network_nodes_rolling"),
        "net_window_stats": _read("network_window_stats"),
    }


@st.cache_data(show_spinner="Loading GNN model scores…")
def load_gnn_scores(model_slug: str, anchor_month: str | None) -> pd.DataFrame:
    p = _ml_root(anchor_month) / f"entity_anomaly_scores_{model_slug}.csv"
    if p.exists():
        df = pd.read_csv(p)
        df["entity_id"] = df["entity_id"].astype(str)
        return df
    return pd.DataFrame()


@st.cache_data(show_spinner="Loading anchor window metadata…")
def load_anchor_manifest(anchor_month: str | None) -> dict:
    if not anchor_month:
        return {}
    p = _data_root(anchor_month) / "manifest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


@st.cache_data(show_spinner="Building full network from CSVs…")
def build_full_graph(anchor_month: str | None) -> nx.DiGraph:
    dfs = load_outputs(anchor_month)
    edges_df = dfs["net_edges"]
    nodes_df = dfs["net_nodes"]
    if edges_df.empty or nodes_df.empty:
        return nx.DiGraph()

    G = nx.DiGraph()
    for _, row in nodes_df.iterrows():
        G.add_node(
            row["entity_id"],
            name=row.get("name", ""),
            node_type=row.get("node_type", "unknown"),
        )
    for _, row in edges_df.iterrows():
        G.add_edge(
            row["src"],
            row["dst"],
            weight=row.get("weight", 0.0),
            tx_count=row.get("tx_count", 1),
        )
    return G


@st.cache_data(show_spinner="Building subgraph from CSVs…")
def build_subgraph(top_n: int, show_hospitals: bool, anchor_month: str | None) -> nx.DiGraph:
    """
    Build a DiGraph from the saved edge/node CSVs — no Excel loading.
    Returns a subgraph containing top-N BC nodes + their 1-hop neighbours.
    """
    dfs = load_outputs(anchor_month)
    nodes_df = dfs["net_nodes"]
    bc_df_ = dfs["bc"]
    G = build_full_graph(anchor_month)

    if G.number_of_nodes() == 0 or bc_df_.empty:
        return nx.DiGraph()

    top_ids: set[str] = set(bc_df_.nlargest(top_n, "bc_score")["entity_id"])
    neighbours: set[str] = set()
    for nid in top_ids:
        if nid in G:
            neighbours.update(G.predecessors(nid))
            neighbours.update(G.successors(nid))

    if not show_hospitals:
        hosp_ids = set(nodes_df.loc[nodes_df["node_type"] == "hospital", "entity_id"])
        neighbours -= hosp_ids

    return G.subgraph(top_ids | neighbours).copy()


def build_graph_from_frames(edges_df: pd.DataFrame, nodes_df: pd.DataFrame) -> nx.DiGraph:
    """Build graph from provided edge/node frames (for month-snapshot view)."""
    if edges_df.empty or nodes_df.empty:
        return nx.DiGraph()
    G = nx.DiGraph()
    for _, row in nodes_df.iterrows():
        G.add_node(
            row["entity_id"],
            name=row.get("name", ""),
            node_type=row.get("node_type", "unknown"),
        )
    for _, row in edges_df.iterrows():
        G.add_edge(
            row["src"],
            row["dst"],
            weight=row.get("weight", 0.0),
            tx_count=row.get("tx_count", 1),
        )
    return G


def build_subgraph_from_frames(
    *,
    edges_df: pd.DataFrame,
    nodes_df: pd.DataFrame,
    bc_df: pd.DataFrame,
    top_n: int,
    show_hospitals: bool,
) -> nx.DiGraph:
    """Build network subgraph for selected snapshot frames."""
    G = build_graph_from_frames(edges_df, nodes_df)
    if G.number_of_nodes() == 0 or bc_df.empty:
        return nx.DiGraph()

    top_ids: set[str] = set(bc_df.nlargest(top_n, "bc_score")["entity_id"])
    neighbours: set[str] = set()
    for nid in top_ids:
        if nid in G:
            neighbours.update(G.predecessors(nid))
            neighbours.update(G.successors(nid))

    if not show_hospitals and "node_type" in nodes_df.columns:
        hosp_ids = set(nodes_df.loc[nodes_df["node_type"] == "hospital", "entity_id"])
        neighbours -= hosp_ids

    return G.subgraph(top_ids | neighbours).copy()


@st.cache_data(show_spinner="Building ego subgraph…")
def build_ego_subgraph(
    focal_id: str,
    hops: int,
    show_hospitals: bool,
    anchor_month: str | None,
) -> nx.DiGraph:
    """BFS ego network around one entity (predecessors + successors)."""
    G = build_full_graph(anchor_month)
    if focal_id not in G:
        return nx.DiGraph()

    nodes: set[str] = {focal_id}
    frontier: set[str] = {focal_id}
    for _ in range(hops):
        nxt: set[str] = set()
        for nid in frontier:
            nxt.update(G.predecessors(nid))
            nxt.update(G.successors(nid))
        nodes |= nxt
        frontier = nxt

    if not show_hospitals:
        hosp_ids = {
            n for n in nodes if G.nodes[n].get("node_type") == "hospital"
        }
        nodes -= hosp_ids
        nodes.add(focal_id)

    return G.subgraph(nodes).copy()


@st.cache_data(show_spinner="Indexing network nodes…")
def load_node_catalog(anchor_month: str | None) -> pd.DataFrame:
    """Searchable entity list from network_nodes.csv."""
    nodes_df = load_outputs(anchor_month)["net_nodes"]
    if nodes_df.empty:
        return pd.DataFrame(columns=["entity_id", "name", "node_type"])
    catalog = nodes_df[["entity_id", "name", "node_type"]].copy()
    catalog["entity_id"] = catalog["entity_id"].astype(str)
    catalog["name"] = catalog["name"].fillna("").astype(str)
    catalog["node_type"] = catalog["node_type"].fillna("unknown").astype(str)
    return catalog.sort_values("name").reset_index(drop=True)


def _filter_node_catalog(
    catalog: pd.DataFrame,
    name_query: str,
    type_filter: list[str],
) -> pd.DataFrame:
    if catalog.empty:
        return catalog
    df = catalog
    q = name_query.strip()
    if q:
        df = df[df["name"].str.contains(q, case=False, na=False)]
    if type_filter:
        df = df[df["node_type"].isin(type_filter)]
    return df.reset_index(drop=True)


def _neighbor_tables(
    G_full: nx.DiGraph,
    G_ego: nx.DiGraph,
    focal_id: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    in_rows: list[dict] = []
    for pred in G_ego.predecessors(focal_id):
        in_rows.append(
            {
                "entity_id": pred,
                "name": G_ego.nodes[pred].get("name", ""),
                "type": G_ego.nodes[pred].get("node_type", ""),
                "tx_count": G_full[pred][focal_id].get("tx_count", 0)
                if G_full.has_edge(pred, focal_id)
                else 0,
            }
        )
    out_rows: list[dict] = []
    for succ in G_ego.successors(focal_id):
        out_rows.append(
            {
                "entity_id": succ,
                "name": G_ego.nodes[succ].get("name", ""),
                "type": G_ego.nodes[succ].get("node_type", ""),
                "tx_count": G_full[focal_id][succ].get("tx_count", 0)
                if G_full.has_edge(focal_id, succ)
                else 0,
            }
        )
    in_df = (
        pd.DataFrame(in_rows).sort_values("tx_count", ascending=False)
        if in_rows
        else pd.DataFrame(columns=["entity_id", "name", "type", "tx_count"])
    )
    out_df = (
        pd.DataFrame(out_rows).sort_values("tx_count", ascending=False)
        if out_rows
        else pd.DataFrame(columns=["entity_id", "name", "type", "tx_count"])
    )
    return in_df, out_df


def render_entity_ego_detail(
    focal_id: str,
    focal_name: str,
    *,
    selected_anchor: str | None,
    bc_df: pd.DataFrame,
    pz_ent_df: pd.DataFrame,
    timelag_df: pd.DataFrame,
    layout_seed: int,
    ego_hops: int,
    show_hospitals: bool,
    plot_caption_prefix: str,
    gnn_df: pd.DataFrame | None = None,
    gnn_score_col: str | None = None,
    gnn_score_label: str | None = None,
    gnn_rank_col: str | None = None,
) -> None:
    """Shared ego-network panel: metrics, plot, legend, inbound/outbound tables."""
    G_full = build_full_graph(selected_anchor)
    G_ego = build_ego_subgraph(focal_id, ego_hops, show_hospitals, selected_anchor)

    bc_row = (
        bc_df.loc[bc_df["entity_id"].astype(str) == focal_id]
        if not bc_df.empty and "entity_id" in bc_df.columns
        else pd.DataFrame()
    )
    pz_row = (
        pz_ent_df.loc[pz_ent_df["supplier_id"].astype(str) == focal_id]
        if not pz_ent_df.empty and "supplier_id" in pz_ent_df.columns
        else pd.DataFrame()
    )
    lag_row = (
        timelag_df.loc[timelag_df["supplier_id"].astype(str) == focal_id]
        if not timelag_df.empty and "supplier_id" in timelag_df.columns
        else pd.DataFrame()
    )
    gnn_row = (
        gnn_df.loc[gnn_df["entity_id"].astype(str) == focal_id]
        if gnn_df is not None
        and not gnn_df.empty
        and gnn_score_col
        and gnn_score_col in gnn_df.columns
        else pd.DataFrame()
    )

    met_cols = st.columns(5)
    if gnn_score_col and gnn_score_label and not gnn_row.empty:
        met_cols[0].metric(gnn_score_label, f"{float(gnn_row.iloc[0][gnn_score_col]):.4g}")
        rank_val = int(gnn_row.iloc[0].get(gnn_rank_col, 0)) if gnn_rank_col else 0
        met_cols[1].metric(f"{gnn_score_label} rank", rank_val)
        bc_metric_idx = 2
    else:
        met_cols[0].metric("Entity", focal_name[:24] + ("…" if len(focal_name) > 24 else ""))
        met_cols[1].metric("Type", G_full.nodes[focal_id].get("node_type", "unknown") if focal_id in G_full else "n/a")
        bc_metric_idx = 2

    bc_val = float(bc_row.iloc[0]["bc_score"]) if not bc_row.empty else 0.0
    met_cols[bc_metric_idx].metric("BC score", f"{bc_val:.2e}")
    met_cols[bc_metric_idx + 1].metric(
        "Price flag rate",
        f"{float(pz_row.iloc[0]['flag_rate']):.1%}"
        if not pz_row.empty and "flag_rate" in pz_row.columns
        else "n/a",
    )
    lag_col = (
        "median_lag_days"
        if not lag_row.empty and "median_lag_days" in lag_row.columns
        else "lag_days"
    )
    met_cols[bc_metric_idx + 2].metric(
        "Median time-lag (d)",
        f"{float(lag_row.iloc[0][lag_col]):.0f}"
        if not lag_row.empty and lag_col in lag_row.columns
        else "n/a",
    )

    plot_col, info_col = st.columns([3, 1])
    with plot_col:
        if G_ego.number_of_nodes() == 0:
            st.warning("Ego subgraph is empty for this entity.")
        else:
            with st.spinner("Rendering ego network…"):
                fig = render_network_figure(
                    G_ego,
                    layout_seed=int(layout_seed),
                    focal_id=focal_id,
                    bc_df=bc_df,
                    gnn_df=gnn_df if gnn_score_col else None,
                    gnn_score_col=gnn_score_col or "dominant_score",
                    gnn_score_label=gnn_score_label or "GNN",
                )
                st.plotly_chart(fig, use_container_width=True)
                st.caption(
                    f"{plot_caption_prefix}: {G_ego.number_of_nodes():,} nodes · "
                    f"{G_ego.number_of_edges():,} edges · {ego_hops}-hop"
                )

    with info_col:
        st.markdown("**Focal entity**")
        st.markdown(f"**{focal_name}**")
        st.caption(focal_id)
        if focal_id in G_full:
            st.markdown(
                f"In-degree: **{G_full.in_degree(focal_id)}**  \n"
                f"Out-degree: **{G_full.out_degree(focal_id)}**"
            )
        st.markdown("**Legend**")
        st.caption(
            "Colour = entity type · "
            "**Purple ring** = focal · "
            "**Green ring** = BC high-risk (p95)"
        )

    if focal_id in G_full and G_ego.number_of_nodes() > 0:
        in_df, out_df = _neighbor_tables(G_full, G_ego, focal_id)
        nb1, nb2 = st.columns(2)
        with nb1:
            st.markdown("**Inbound (suppliers → focal)**")
            st.dataframe(in_df, use_container_width=True, height=220)
        with nb2:
            st.markdown("**Outbound (focal → receivers)**")
            st.dataframe(out_df, use_container_width=True, height=220)


def render_network_figure(
    G_sub: nx.DiGraph,
    *,
    layout_seed: int,
    focal_id: str | None = None,
    bc_df: pd.DataFrame | None = None,
    gnn_df: pd.DataFrame | None = None,
    gnn_score_col: str = "dominant_score",
    gnn_score_label: str = "GNN",
) -> go.Figure:
    """Plotly network — purple ring = focal, green ring = BC high-risk (p95)."""
    bc_idx = bc_df.set_index("entity_id") if bc_df is not None and not bc_df.empty else None
    gnn_idx = (
        gnn_df.set_index("entity_id")
        if gnn_df is not None and not gnn_df.empty
        else None
    )

    pos = nx.spring_layout(G_sub, seed=int(layout_seed), k=1.5)

    ex, ey = [], []
    for u, v in G_sub.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        ex += [x0, x1, None]
        ey += [y0, y1, None]

    traces: list = [
        go.Scatter(
            x=ex,
            y=ey,
            mode="lines",
            line=dict(width=0.5, color="#dddddd"),
            hoverinfo="none",
            showlegend=False,
        )
    ]

    for ntype, base_color in _TYPE_COLOR.items():
        group = [
            n
            for n in G_sub.nodes()
            if G_sub.nodes[n].get("node_type", "unknown") == ntype
        ]
        if not group:
            continue
        xs, ys, sizes, texts = [], [], [], []
        line_widths, line_colors = [], []
        for n in group:
            xs.append(pos[n][0])
            ys.append(pos[n][1])
            is_focal = focal_id is not None and n == focal_id

            bc_val = 0.0
            high_bc = False
            if bc_idx is not None and n in bc_idx.index:
                row = bc_idx.loc[n]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                bc_val = float(row["bc_score"])
                high_bc = bool(row.get("high_risk", False))

            gnn_val = 0.0
            if gnn_idx is not None and n in gnn_idx.index:
                row = gnn_idx.loc[n]
                if isinstance(row, pd.DataFrame):
                    row = row.iloc[0]
                gnn_val = float(row.get(gnn_score_col, 0.0) or 0.0)

            if is_focal:
                sizes.append(30)
                line_widths.append(5.0)
                line_colors.append(_FOCAL_RING_COLOR)
            elif gnn_idx is not None and gnn_val > 0:
                sizes.append(max(7, np.log1p(gnn_val) * 2 + 7))
                line_widths.append(2.5 if high_bc else 1.0)
                line_colors.append(_BC_HIGH_RING_COLOR if high_bc else "white")
            else:
                sizes.append(max(7, np.log1p(bc_val * 1e7) * 3 + 7))
                line_widths.append(2.5 if high_bc else 1.0)
                line_colors.append(_BC_HIGH_RING_COLOR if high_bc else "white")

            label = G_sub.nodes[n].get("name") or str(n)
            bc_tag = "  [BC high]" if high_bc and not is_focal else ""
            hover = (
                f"<b>{label}</b>{'  [FOCAL]' if is_focal else ''}{bc_tag}<br>"
                f"Type: {ntype}<br>"
                f"In: {G_sub.in_degree(n)}  Out: {G_sub.out_degree(n)}"
            )
            if gnn_idx is not None:
                hover += f"<br>{gnn_score_label}: {gnn_val:.4g}"
            if bc_idx is not None:
                hover += f"<br>BC: {bc_val:.3e}"
            texts.append(hover)

        traces.append(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers",
                name=ntype,
                marker=dict(
                    size=sizes,
                    color=base_color,
                    line=dict(width=line_widths, color=line_colors),
                ),
                text=texts,
                hoverinfo="text",
            )
        )

    traces.append(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            name="Focal entity",
            marker=dict(
                size=14,
                color="#c7c7c7",
                line=dict(width=4, color=_FOCAL_RING_COLOR),
            ),
        )
    )
    traces.append(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            name="BC high-risk (p95)",
            marker=dict(
                size=12,
                color="#c7c7c7",
                line=dict(width=2.5, color=_BC_HIGH_RING_COLOR),
            ),
        )
    )

    return go.Figure(
        data=traces,
        layout=go.Layout(
            showlegend=True,
            hovermode="closest",
            height=580,
            margin=dict(b=20, l=5, r=5, t=10),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            plot_bgcolor="white",
            paper_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
        ),
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Controls")

if st.sidebar.button("🔄 Reload data", help="Clear cached CSVs and re-read output/"):
    st.cache_data.clear()
    st.rerun()

available_anchors = list_available_anchor_months()
selected_anchor: str | None = None
if available_anchors:
    selected_anchor = st.sidebar.selectbox(
        "Anchor month",
        available_anchors,
        index=len(available_anchors) - 1,
        help="All tabs read from this anchor's rolling window outputs.",
    )
    manifest = load_anchor_manifest(selected_anchor)
    months = manifest.get("window_months", [])
    if isinstance(months, list) and months:
        st.sidebar.caption(f"Window: `{months[0]}` ~ `{months[-1]}`")
else:
    st.sidebar.caption("Anchor outputs not found. Using legacy top-level outputs.")

dfs = load_outputs(selected_anchor)
pdi_df      = dfs["pdi"]
bc_df       = dfs["bc"]
hhi_df      = dfs["hhi"]
pz_ent_df   = dfs["pz_entity"]
pz_tx_df    = dfs["pz_tx"]
timelag_df  = dfs["timelag"]

missing = [k for k, v in dfs.items()
           if v.empty and k not in ("net_edges", "net_nodes", "net_edges_roll", "net_nodes_roll", "net_window_stats")]

if not bc_df.empty:
    top_n = st.sidebar.slider("Network: top-N by BC", 20, 200, 60, step=10)
    show_hospitals = st.sidebar.checkbox("Show hospital neighbours", value=True)
    layout_seed    = st.sidebar.number_input("Layout seed", 0, 999, value=42, step=1)
else:
    top_n, show_hospitals, layout_seed = 60, True, 42

# CSV freshness info
st.sidebar.markdown("---")
st.sidebar.caption("**Output files**")
data_root = _data_root(selected_anchor)
for name in ["pdi_per_udi", "bc_per_entity", "hhi_per_hospital_group",
             "price_zscore_per_entity", "price_zscore_per_transaction",
             "timelag_per_entity", "network_edges", "network_nodes",
             "network_edges_rolling", "network_nodes_rolling", "network_window_stats"]:
    p = data_root / f"{name}.csv"
    if p.exists():
        import datetime
        mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%m-%d %H:%M")
        st.sidebar.caption(f"✅ {name}  `{mtime}`")
    else:
        st.sidebar.caption(f"❌ {name} — missing")
st.sidebar.caption("**ML scores**")
ml_root = _ml_root(selected_anchor)
for slug in GNN_MODELS:
    name = f"{ml_root.relative_to(_HERE).as_posix()}/entity_anomaly_scores_{slug}"
    p = ml_root / f"entity_anomaly_scores_{slug}.csv"
    if p.exists():
        import datetime
        mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%m-%d %H:%M")
        st.sidebar.caption(f"✅ {name}  `{mtime}`")
    else:
        st.sidebar.caption(f"❌ {name} — missing")

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("🔍 Class 1 — Medical Device Supply Chain Anomaly Explorer")
if selected_anchor:
    manifest = load_anchor_manifest(selected_anchor)
    months = manifest.get("window_months", []) if isinstance(manifest, dict) else []
    if isinstance(months, list) and months:
        st.caption(
            f"Anchor `{selected_anchor}` · window `{months[0]}` ~ `{months[-1]}` · "
            "use **Reload data** after re-running anchor pipelines"
        )
    else:
        st.caption(f"Anchor `{selected_anchor}` · use **Reload data** after re-running pipelines")
else:
    st.caption("Phase 1 EDA prototype · legacy top-level outputs · use **Reload data** after re-running `run_graph_eda.py`")

if missing:
    st.warning(
        f"Missing CSVs: {missing}. Run `python class_1_anomaly_detection/src/eda/run_graph_eda.py` first.",
        icon="⚠️",
    )

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_net, tab_gnn, tab_pdi, tab_bc, tab_hhi, tab_pz, tab_lag = st.tabs([
    "🕸 Network", "🧠 GNN Review", "📏 PDI", "📊 BC", "📈 HHI", "💰 Price Z-Score", "⏱ Time-lag"
])


# ============================================================
# TAB 1 — NETWORK
# ============================================================
with tab_net:
    st.subheader("Supply Chain Network")

    net_edges_df = dfs["net_edges"]
    net_nodes_df = dfs["net_nodes"]
    net_edges_roll_df = dfs["net_edges_roll"]
    net_nodes_roll_df = dfs["net_nodes_roll"]
    net_window_stats_df = dfs["net_window_stats"]

    net_view = st.radio(
        "View mode",
        ["Top-N BC overview", "Search entity (ego network)"],
        horizontal=True,
        key="net_view_mode",
    )

    if net_view == "Top-N BC overview":
        st.caption(
            "Top-N entities by BC + 1-hop neighbours.  "
            "Colour = entity type · Size = BC score (log) · "
            "**Green ring** = BC high-risk (p95)."
        )
    else:
        st.caption(
            "Search any entity by name and explore its local supply chain.  "
            "**Purple ring** = focal · **Green ring** = BC high-risk (p95)."
        )

    snapshot_mode = "Latest window only"
    snapshot_anchor = None
    if net_view == "Top-N BC overview" and not net_edges_roll_df.empty and "anchor_month" in net_edges_roll_df.columns:
        snapshot_mode = st.selectbox(
            "Network snapshot mode",
            ["Latest window only", "Rolling snapshots (select anchor month)"],
            index=1,
            key="snapshot_mode",
        )
        if snapshot_mode.startswith("Rolling"):
            anchors = sorted(net_edges_roll_df["anchor_month"].astype(str).unique())
            snapshot_anchor = st.selectbox(
                "Anchor month (3-month merged network for this month)",
                anchors,
                index=len(anchors) - 1,
                key="snapshot_anchor_month",
            )
            net_edges_df = net_edges_roll_df[
                net_edges_roll_df["anchor_month"].astype(str) == str(snapshot_anchor)
            ].copy()
            net_nodes_df = net_nodes_roll_df[
                net_nodes_roll_df["anchor_month"].astype(str) == str(snapshot_anchor)
            ].copy()
            if not net_window_stats_df.empty and "anchor_month" in net_window_stats_df.columns:
                win_row = net_window_stats_df[
                    net_window_stats_df["anchor_month"].astype(str) == str(snapshot_anchor)
                ]
                if not win_row.empty:
                    r = win_row.iloc[0]
                    st.caption(
                        f"Window range: `{r.get('window_start', '')}` ~ `{r.get('window_end', '')}`"
                    )

    if dfs["net_edges"].empty or net_nodes_df.empty:
        st.info(
            "network_edges.csv / network_nodes.csv not found.  "
            "Re-run `run_graph_eda.py` to generate them (they are now saved in Step 2)."
        )
    elif net_view == "Search entity (ego network)":
        catalog = load_node_catalog(selected_anchor)
        if catalog.empty:
            st.warning("No nodes in network_nodes.csv.")
        else:
            type_options = sorted(catalog["node_type"].unique().tolist())
            search_col1, search_col2, search_col3 = st.columns([2, 1, 1])
            with search_col1:
                name_query = st.text_input(
                    "Search by name",
                    placeholder="e.g. 케어캠프",
                    key="net_search_query",
                )
            with search_col2:
                type_filter = st.multiselect(
                    "Filter by type",
                    type_options,
                    default=[],
                    key="net_search_types",
                )
            with search_col3:
                net_search_hops = st.slider("Hop depth", 1, 2, 1, key="net_search_hops")
            net_search_show_hosp = st.checkbox(
                "Show hospitals", value=True, key="net_search_show_hospitals"
            )

            filtered = _filter_node_catalog(catalog, name_query, type_filter)
            if filtered.empty:
                st.warning("No entities match your search — try a shorter or different name.")
            else:
                pick_options = {
                    f"{row['name']} ({row['node_type']}) · {row['entity_id']}": row["entity_id"]
                    for _, row in filtered.iterrows()
                }
                st.caption(f"{len(filtered):,} matching entities")
                pick_label = st.selectbox(
                    "Select entity",
                    list(pick_options.keys()),
                    key="net_search_pick",
                )
                search_focal_id = str(pick_options[pick_label])
                search_focal_name = filtered.loc[
                    filtered["entity_id"] == search_focal_id, "name"
                ].iloc[0]

                gnn_overlay_options = {"None": None}
                for slug, (display, *_rest) in GNN_MODELS.items():
                    if not load_gnn_scores(slug, selected_anchor).empty:
                        gnn_overlay_options[display] = slug
                gnn_overlay_label = st.selectbox(
                    "Overlay GNN scores (optional)",
                    list(gnn_overlay_options.keys()),
                    key="net_gnn_overlay",
                )
                gnn_overlay_slug = gnn_overlay_options[gnn_overlay_label]
                search_gnn_df = None
                search_score_col = None
                search_rank_col = None
                search_model_label = None
                if gnn_overlay_slug:
                    search_model_label, search_score_col, search_rank_col, _ = GNN_MODELS[
                        gnn_overlay_slug
                    ]
                    search_gnn_df = load_gnn_scores(gnn_overlay_slug, selected_anchor)

                render_entity_ego_detail(
                    search_focal_id,
                    search_focal_name,
                    selected_anchor=selected_anchor,
                    bc_df=bc_df,
                    pz_ent_df=pz_ent_df,
                    timelag_df=timelag_df,
                    layout_seed=int(layout_seed),
                    ego_hops=net_search_hops,
                    show_hospitals=net_search_show_hosp,
                    plot_caption_prefix="Entity ego network",
                    gnn_df=search_gnn_df,
                    gnn_score_col=search_score_col,
                    gnn_score_label=search_model_label,
                    gnn_rank_col=search_rank_col,
                )
    elif bc_df.empty or net_edges_df.empty:
        st.info(
            "BC metrics or network edges missing for Top-N overview.  "
            "Re-run `run_graph_eda.py`."
        )
    else:
        with st.spinner("Rendering network…"):
            try:
                if snapshot_anchor is None:
                    G_sub = build_subgraph(top_n, show_hospitals, selected_anchor)
                else:
                    G_sub = build_subgraph_from_frames(
                        edges_df=net_edges_df,
                        nodes_df=net_nodes_df,
                        bc_df=bc_df,
                        top_n=top_n,
                        show_hospitals=show_hospitals,
                    )

                if G_sub.number_of_nodes() == 0:
                    st.warning("Subgraph is empty — try increasing top-N.")
                else:
                    fig_net = render_network_figure(
                        G_sub,
                        layout_seed=int(layout_seed),
                        bc_df=bc_df,
                    )
                    st.plotly_chart(fig_net, width="stretch")
                    st.caption(
                        f"Rendered {G_sub.number_of_nodes():,} nodes · "
                        f"{G_sub.number_of_edges():,} edges  "
                        f"(top-{top_n} BC + 1-hop neighbours)"
                    )
            except Exception as exc:
                st.error(f"Network error: {exc}")
                st.info("Make sure run_graph_eda.py completed successfully.")


# ============================================================
# TAB — GNN REVIEW (PyGOD ego networks)
# ============================================================
with tab_gnn:
    st.subheader("GNN Review — Top Distributors by Model")
    st.caption(
        "Ego-network around each top-scored distributor per PyGOD model.  "
        "**Purple ring** = focal entity · **Green ring** = BC high-risk · Hover shows model score + BC."
    )

    available_models = {
        display: slug
        for slug, (display, *_rest) in GNN_MODELS.items()
        if not load_gnn_scores(slug, selected_anchor).empty
    }

    if not available_models:
        st.info(
            "No GNN score files found in `output/ml/`.  "
            "Run `python -m class_1_anomaly_detection.src.experiments.run_pygod_compare` first."
        )
    elif dfs["net_edges"].empty or dfs["net_nodes"].empty:
        st.info("Network CSVs missing — re-run `run_graph_eda.py`.")
    else:
        model_display = st.selectbox(
            "GNN model",
            list(available_models.keys()),
            key="gnn_model_select",
        )
        model_slug = available_models[model_display]
        model_label, score_col, rank_col, label_col = GNN_MODELS[model_slug]
        gnn_df = load_gnn_scores(model_slug, selected_anchor)

        top_dist = (
            gnn_df[gnn_df["node_type"] == "distributor"]
            .nlargest(10, score_col)
            .copy()
        )

        if top_dist.empty:
            st.warning(f"No distributors in {model_label} results.")
        else:
            table_cols = [
                c
                for c in [rank_col, "name", "entity_id", score_col, "bc_score", "bc_rank", label_col]
                if c in top_dist.columns
            ]
            st.dataframe(top_dist[table_cols], use_container_width=True, height=220)

            ctrl1, ctrl2, ctrl3 = st.columns(3)
            with ctrl1:
                options = {
                    f"{row['name']} ({row['entity_id']}) - score {row[score_col]:.4g}": row[
                        "entity_id"
                    ]
                    for _, row in top_dist.iterrows()
                }
                pick_label = st.selectbox("Focal distributor", list(options.keys()))
                focal_id = str(options[pick_label])
            with ctrl2:
                ego_hops = st.slider("Hop depth", 1, 2, 1, key="gnn_hops")
            with ctrl3:
                gnn_show_hosp = st.checkbox(
                    "Show hospitals", value=True, key="gnn_show_hospitals"
                )

            focal_row = top_dist.loc[top_dist["entity_id"] == focal_id].iloc[0]
            G_full = build_full_graph(selected_anchor)
            G_ego = build_ego_subgraph(focal_id, ego_hops, gnn_show_hosp, selected_anchor)

            pz_row = (
                pz_ent_df.loc[pz_ent_df["supplier_id"] == focal_id]
                if not pz_ent_df.empty and "supplier_id" in pz_ent_df.columns
                else pd.DataFrame()
            )
            lag_row = (
                timelag_df.loc[timelag_df["supplier_id"] == focal_id]
                if not timelag_df.empty and "supplier_id" in timelag_df.columns
                else pd.DataFrame()
            )

            met1, met2, met3, met4, met5 = st.columns(5)
            met1.metric(f"{model_label} score", f"{focal_row[score_col]:.4g}")
            met2.metric(f"{model_label} rank", int(focal_row.get(rank_col, 0)))
            met3.metric("BC score", f"{float(focal_row.get('bc_score', 0)):.2e}")
            met4.metric(
                "Price flag rate",
                f"{float(pz_row.iloc[0]['flag_rate']):.1%}"
                if not pz_row.empty and "flag_rate" in pz_row.columns
                else "n/a",
            )
            lag_col = (
                "median_lag_days"
                if not lag_row.empty and "median_lag_days" in lag_row.columns
                else "lag_days"
            )
            met5.metric(
                "Median time-lag (d)",
                f"{float(lag_row.iloc[0][lag_col]):.0f}"
                if not lag_row.empty and lag_col in lag_row.columns
                else "n/a",
            )

            plot_col, info_col = st.columns([3, 1])
            with plot_col:
                if G_ego.number_of_nodes() == 0:
                    st.warning("Ego subgraph is empty for this entity.")
                else:
                    with st.spinner("Rendering ego network…"):
                        fig_gnn = render_network_figure(
                            G_ego,
                            layout_seed=int(layout_seed),
                            focal_id=focal_id,
                            bc_df=bc_df,
                            gnn_df=gnn_df,
                            gnn_score_col=score_col,
                            gnn_score_label=model_label,
                        )
                        st.plotly_chart(fig_gnn, use_container_width=True)
                        st.caption(
                            f"{model_label} ego network: {G_ego.number_of_nodes():,} nodes · "
                            f"{G_ego.number_of_edges():,} edges · {ego_hops}-hop"
                        )

            with info_col:
                st.markdown("**Focal entity**")
                st.markdown(f"**{focal_row.get('name', focal_id)}**")
                st.caption(focal_id)
                if focal_id in G_full:
                    st.markdown(
                        f"In-degree: **{G_full.in_degree(focal_id)}**  \n"
                        f"Out-degree: **{G_full.out_degree(focal_id)}**"
                    )
                st.markdown("**Legend**")
                st.caption(
                    "Colour = entity type · "
                    "**Purple ring** = focal · "
                    "**Green ring** = BC high-risk (p95)"
                )

            if focal_id in G_full and G_ego.number_of_nodes() > 0:
                in_df, out_df = _neighbor_tables(G_full, G_ego, focal_id)
                nb1, nb2 = st.columns(2)
                with nb1:
                    st.markdown("**Inbound (suppliers → focal)**")
                    st.dataframe(in_df, use_container_width=True, height=220)
                with nb2:
                    st.markdown("**Outbound (focal → receivers)**")
                    st.dataframe(out_df, use_container_width=True, height=220)


# ============================================================
# TAB 2 — PDI
# ============================================================
with tab_pdi:
    st.subheader("Path Depth Index — Indirect Supply Detection")
    st.markdown(
        "**PDI_udi** = longest hop-count from manufacturer → hospital for a UDI-DI.  "
        "**PDI ≥ 3** → suspected indirect supply route (간납)."
    )

    if pdi_df.empty:
        st.info("pdi_per_udi.csv not found.")
    else:
        total = len(pdi_df)
        high  = int(pdi_df["high_risk"].sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("UDI-DIs total", total)
        c2.metric("High-risk (PDI ≥ 3)", high, f"{high/total:.0%}")
        c3.metric("Max PDI", int(pdi_df["pdi"].max()))
        c4.metric("Median PDI", float(pdi_df["pdi"].median()))

        dist = (
            pdi_df["pdi"].value_counts().sort_index().reset_index()
            .rename(columns={"pdi": "PDI", "count": "Count"})
        )
        dist["High-risk"] = dist["PDI"] >= 3
        fig_pdi = px.bar(dist, x="PDI", y="Count", color="High-risk",
                         color_discrete_map={True: _RISK_COLOR, False: "#4c78a8"},
                         title="PDI Distribution Across UDI-DIs")
        st.plotly_chart(fig_pdi, width="stretch")

        cols_show = [c for c in ["udi_di", "pdi", "device_class", "tx_count",
                                  "unique_suppliers", "unique_receivers"] if c in pdi_df.columns]
        st.subheader("High-risk UDI-DIs (PDI ≥ 3)")
        st.dataframe(
            pdi_df[pdi_df["high_risk"]][cols_show].sort_values("pdi", ascending=False)
            .style.background_gradient(subset=["pdi"], cmap="Reds"),
            width="stretch", height=300,
        )


# ============================================================
# TAB 3 — BC
# ============================================================
with tab_bc:
    st.subheader("Betweenness Centrality — Gatekeeper Broker Detection")
    st.markdown(
        "**BC(v)** = share of shortest supply paths passing through entity v.  "
        "**Top 5 %** → suspected 간납사 gatekeeper."
    )

    if bc_df.empty:
        st.info("bc_per_entity.csv not found.")
    else:
        total_bc = len(bc_df)
        high_bc  = int(bc_df["high_risk"].sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Entities total", f"{total_bc:,}")
        c2.metric("High-risk (p95)", f"{high_bc:,}", f"{high_bc/total_bc:.1%}")
        c3.metric("Max BC", f"{bc_df['bc_score'].max():.3e}")
        c4.metric("p95 threshold", f"{bc_df['bc_score'].quantile(0.95):.3e}")

        n_show = st.slider("Show top-N", 10, 100, 30, key="bc_top_slider")
        top_bc = bc_df.nlargest(n_show, "bc_score").copy()

        fig_bc = px.bar(
            top_bc, x="bc_score", y="name", orientation="h",
            color="node_type", color_discrete_map=_TYPE_COLOR,
            title=f"Top-{n_show} Entities by Betweenness Centrality",
            labels={"bc_score": "BC Score", "name": "Entity", "node_type": "Type"},
            height=max(420, n_show * 22),
        )
        fig_bc.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_bc, width="stretch")

        st.subheader("BC by Node Type")
        type_bc = (
            bc_df.groupby("node_type")["bc_score"]
            .agg(mean="mean", max="max", count="count")
            .reset_index().sort_values("mean", ascending=False).round(8)
        )
        st.dataframe(type_bc, width="stretch")


# ============================================================
# TAB 4 — HHI
# ============================================================
with tab_hhi:
    st.subheader("Herfindahl-Hirschman Index — Supply Monopoly Detection")
    st.markdown(
        "**HHI_item** = Σ(supplier share)² per (hospital × 품목명).  "
        "**HHI > 0.25** → monopoly risk."
    )

    if hhi_df.empty:
        st.info("hhi_per_hospital_group.csv not found.")
    else:
        total_h = len(hhi_df)
        high_h  = int((hhi_df["concentration"] == "high").sum())
        mod_h   = int((hhi_df["concentration"] == "moderate").sum())
        comp_h  = int((hhi_df["concentration"] == "competitive").sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Hospital × item pairs", f"{total_h:,}")
        c2.metric("High (>0.25)",         f"{high_h:,}",  f"{high_h/total_h:.0%}")
        c3.metric("Moderate (0.15–0.25)",  f"{mod_h:,}")
        c4.metric("Competitive (≤0.15)",   f"{comp_h:,}")

        conc_pie = pd.DataFrame({
            "Concentration": ["High", "Moderate", "Competitive"],
            "Count": [high_h, mod_h, comp_h],
        })
        fig_pie = px.pie(conc_pie, names="Concentration", values="Count",
                         color="Concentration",
                         color_discrete_map={"High": _RISK_COLOR, "Moderate": _WARN_COLOR,
                                             "Competitive": _GOOD_COLOR},
                         title="HHI Concentration Distribution")

        fig_hist = px.histogram(hhi_df, x="hhi", nbins=60, color="concentration",
                                color_discrete_map={"high": _RISK_COLOR,
                                                    "moderate": _WARN_COLOR,
                                                    "competitive": _GOOD_COLOR},
                                title="HHI Score Distribution",
                                labels={"hhi": "HHI Score"})
        fig_hist.add_vline(x=0.25, line_dash="dash",  line_color=_RISK_COLOR,
                           annotation_text="0.25 high")
        fig_hist.add_vline(x=0.15, line_dash="dot",   line_color=_WARN_COLOR,
                           annotation_text="0.15 mod")

        left, right = st.columns([1, 2])
        with left:
            st.plotly_chart(fig_pie,  width="stretch")
        with right:
            st.plotly_chart(fig_hist, width="stretch")

        st.subheader("High-concentration pairs (top 100)")
        cols_hhi = [c for c in ["hospital_name", "group", "hhi", "concentration",
                                 "dominant_supplier_id", "dominant_supplier_share",
                                 "supplier_count", "total_amount"] if c in hhi_df.columns]
        top_hhi = (
            hhi_df[hhi_df["concentration"] == "high"][cols_hhi]
            .sort_values("hhi", ascending=False).head(100)
        )
        grad_cols = [c for c in ["hhi", "dominant_supplier_share"] if c in top_hhi.columns]
        st.dataframe(
            top_hhi.style.background_gradient(subset=grad_cols, cmap="Reds"),
            width="stretch", height=350,
        )


# ============================================================
# TAB 5 — PRICE Z-SCORE
# ============================================================
with tab_pz:
    st.subheader("Price Margin Robust Z-Score — Abnormal Pricing Detection")
    st.markdown(
        "MAD-based Robust Z-score per (product × supply stage).  "
        "**|Z| > 2.0** → abnormal unit price vs peers in same product group.  "
        "Flagged entities = top-5 % by flag rate."
    )

    if pz_ent_df.empty:
        st.info("price_zscore_per_entity.csv not found.")
    else:
        total_ent  = len(pz_ent_df)
        high_ent   = int(pz_ent_df["high_risk"].sum()) if "high_risk" in pz_ent_df.columns else 0
        total_tx   = int(pz_tx_df["price_flag"].sum()) if not pz_tx_df.empty and "price_flag" in pz_tx_df.columns else 0
        total_tx_n = len(pz_tx_df) if not pz_tx_df.empty else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Suppliers evaluated", f"{total_ent:,}")
        c2.metric("High-risk suppliers (top-5%)", f"{high_ent:,}", f"{high_ent/max(total_ent,1):.1%}")
        c3.metric("Flagged transactions", f"{total_tx:,}")
        c4.metric("Flag rate",            f"{total_tx/max(total_tx_n,1):.1%}")

        n_show_pz = st.slider("Show top-N suppliers", 10, 100, 30, key="pz_top_slider")
        top_pz = pz_ent_df.nlargest(n_show_pz, "flag_rate").copy()

        fig_pz = px.bar(
            top_pz, x="flag_rate", y="supplier_name", orientation="h",
            color="high_risk",
            color_discrete_map={True: _RISK_COLOR, False: "#4c78a8"},
            title=f"Top-{n_show_pz} Suppliers by Price Flag Rate",
            labels={"flag_rate": "Flag Rate", "supplier_name": "Supplier",
                    "high_risk": "High-risk"},
            height=max(420, n_show_pz * 22),
        )
        fig_pz.update_layout(yaxis={"categoryorder": "total ascending"})
        fig_pz.add_vline(
            x=float(pz_ent_df["flag_rate"].quantile(0.95)),
            line_dash="dash", line_color=_RISK_COLOR,
            annotation_text="p95 threshold",
        )
        st.plotly_chart(fig_pz, width="stretch")

        # Z-score scatter (entity level)
        if "median_zscore" in pz_ent_df.columns and "max_zscore" in pz_ent_df.columns:
            fig_scatter = px.scatter(
                pz_ent_df, x="median_zscore", y="max_zscore",
                color="high_risk",
                color_discrete_map={True: _RISK_COLOR, False: "#4c78a8"},
                hover_data=["supplier_name", "flag_count", "total_tx"],
                title="Supplier Price Z-Score: Median vs Max",
                labels={"median_zscore": "Median |Z|", "max_zscore": "Max |Z|",
                        "high_risk": "High-risk"},
            )
            fig_scatter.add_vline(x=2.0, line_dash="dash", line_color=_RISK_COLOR)
            fig_scatter.add_hline(y=2.0, line_dash="dash", line_color=_RISK_COLOR)
            st.plotly_chart(fig_scatter, width="stretch")

        st.subheader("High-risk supplier table")
        ent_cols = [c for c in ["supplier_name", "flag_count", "total_tx", "flag_rate",
                                 "median_zscore", "max_zscore"] if c in pz_ent_df.columns]
        hr = pz_ent_df[pz_ent_df.get("high_risk", pd.Series(False, index=pz_ent_df.index))][ent_cols]
        grad_pz = [c for c in ["flag_rate", "max_zscore"] if c in hr.columns]
        st.dataframe(
            hr.sort_values("flag_rate", ascending=False)
            .style.background_gradient(subset=grad_pz, cmap="Reds"),
            width="stretch", height=300,
        )


# ============================================================
# TAB 6 — TIME-LAG
# ============================================================
with tab_lag:
    st.subheader("Time-lag (가납 의심) — Delayed Administrative Acceptance")
    st.markdown(
        "**Time-lag** = `최초접수일자` (admin receipt) − `공급일자` (physical supply date).  "
        "Long positive lags suggest consignment (가납/수탁) where invoicing is deliberately delayed.  "
        "Flag threshold: **> 30 days** (PM-adjustable)."
    )

    if timelag_df.empty:
        st.info("timelag_per_entity.csv not found.")
    else:
        lag_col = "median_lag_days" if "median_lag_days" in timelag_df.columns else "lag_days"
        flag_days = st.sidebar.number_input("Time-lag flag threshold (days)", 1, 365, 30, step=1)

        high_lag = int((timelag_df[lag_col] > flag_days).sum())
        total_lag = len(timelag_df)
        max_lag   = float(timelag_df[lag_col].max())
        med_lag   = float(timelag_df[lag_col].median())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Suppliers with lag data", f"{total_lag:,}")
        c2.metric(f"Lag > {flag_days} d (high-risk)", f"{high_lag:,}", f"{high_lag/max(total_lag,1):.0%}")
        c3.metric("Max lag (days)",    f"{max_lag:,.0f}")
        c4.metric("Median lag (days)", f"{med_lag:,.1f}")

        fig_lag_hist = px.histogram(
            timelag_df, x=lag_col, nbins=60,
            title="Distribution of Median Lag Days per Supplier",
            labels={lag_col: "Median Lag (days)"},
        )
        fig_lag_hist.add_vline(
            x=float(flag_days), line_dash="dash", line_color=_RISK_COLOR,
            annotation_text=f"{flag_days} d threshold",
        )
        st.plotly_chart(fig_lag_hist, width="stretch")

        n_show_lag = st.slider("Show top-N suppliers", 10, 100, 30, key="lag_top_slider")
        top_lag = timelag_df.nlargest(n_show_lag, lag_col).copy()
        top_lag["high_risk"] = top_lag[lag_col] > flag_days

        fig_lag_bar = px.bar(
            top_lag, x=lag_col, y="supplier_name", orientation="h",
            color="high_risk",
            color_discrete_map={True: _RISK_COLOR, False: "#4c78a8"},
            title=f"Top-{n_show_lag} Suppliers by Median Lag",
            labels={lag_col: "Median Lag (days)", "supplier_name": "Supplier"},
            height=max(420, n_show_lag * 22),
        )
        fig_lag_bar.update_layout(yaxis={"categoryorder": "total ascending"})
        fig_lag_bar.add_vline(
            x=float(flag_days), line_dash="dash", line_color=_RISK_COLOR,
        )
        st.plotly_chart(fig_lag_bar, width="stretch")

        st.subheader("Full supplier time-lag table")
        lag_cols_show = [c for c in ["supplier_name", lag_col, "max_lag_days", "tx_count"]
                         if c in timelag_df.columns]
        st.dataframe(
            timelag_df[lag_cols_show].sort_values(lag_col, ascending=False)
            .style.background_gradient(subset=[lag_col], cmap="Reds"),
            width="stretch", height=400,
        )
