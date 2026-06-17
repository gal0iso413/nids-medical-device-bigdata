"""
Class 1 — Supply Chain Anomaly Explorer (Phase 1 prototype)

Reads pre-computed output CSVs from class_1_anomaly_detection/output/.
Run run_graph_eda.py first (or again) to refresh them, then click
"Reload data" in the sidebar.

Launch:  streamlit run class_1_anomaly_detection/app.py
"""
from __future__ import annotations

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


# ---------------------------------------------------------------------------
# CSV loader (cached; clear via sidebar button)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading output CSVs…")
def load_outputs() -> dict[str, pd.DataFrame]:
    def _read(name: str) -> pd.DataFrame:
        p = OUTPUT / f"{name}.csv"
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
    }


@st.cache_data(show_spinner="Building subgraph from CSVs…")
def build_subgraph(top_n: int, show_hospitals: bool) -> nx.DiGraph:
    """
    Build a DiGraph from the saved edge/node CSVs — no Excel loading.
    Returns a subgraph containing top-N BC nodes + their 1-hop neighbours.
    """
    dfs = load_outputs()
    edges_df = dfs["net_edges"]
    nodes_df = dfs["net_nodes"]
    bc_df_   = dfs["bc"]

    if edges_df.empty or nodes_df.empty or bc_df_.empty:
        return nx.DiGraph()

    # Full graph from saved edge list
    G = nx.DiGraph()
    node_idx = nodes_df.set_index("entity_id")
    for _, row in nodes_df.iterrows():
        G.add_node(row["entity_id"], name=row.get("name", ""),
                   node_type=row.get("node_type", "unknown"))
    for _, row in edges_df.iterrows():
        G.add_edge(row["src"], row["dst"],
                   weight=row.get("weight", 0.0),
                   tx_count=row.get("tx_count", 1))

    # Subgraph: top-N by BC + 1-hop neighbours
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


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Controls")

if st.sidebar.button("🔄 Reload data", help="Clear cached CSVs and re-read output/"):
    st.cache_data.clear()
    st.rerun()

dfs = load_outputs()
pdi_df      = dfs["pdi"]
bc_df       = dfs["bc"]
hhi_df      = dfs["hhi"]
pz_ent_df   = dfs["pz_entity"]
pz_tx_df    = dfs["pz_tx"]
timelag_df  = dfs["timelag"]

missing = [k for k, v in dfs.items()
           if v.empty and k not in ("net_edges", "net_nodes")]

if not bc_df.empty:
    top_n = st.sidebar.slider("Network: top-N by BC", 20, 200, 60, step=10)
    show_hospitals = st.sidebar.checkbox("Show hospital neighbours", value=True)
    layout_seed    = st.sidebar.number_input("Layout seed", 0, 999, value=42, step=1)
else:
    top_n, show_hospitals, layout_seed = 60, True, 42

# CSV freshness info
st.sidebar.markdown("---")
st.sidebar.caption("**Output files**")
for name in ["pdi_per_udi", "bc_per_entity", "hhi_per_hospital_group",
             "price_zscore_per_entity", "price_zscore_per_transaction",
             "timelag_per_entity", "network_edges", "network_nodes"]:
    p = OUTPUT / f"{name}.csv"
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
st.caption("Phase 1 EDA prototype · read from `output/` CSVs · use **Reload data** after re-running `run_graph_eda.py`")

if missing:
    st.warning(
        f"Missing CSVs: {missing}. Run `python class_1_anomaly_detection/src/eda/run_graph_eda.py` first.",
        icon="⚠️",
    )

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_net, tab_pdi, tab_bc, tab_hhi, tab_pz, tab_lag = st.tabs([
    "🕸 Network", "📏 PDI", "📊 BC", "📈 HHI", "💰 Price Z-Score", "⏱ Time-lag"
])


# ============================================================
# TAB 1 — NETWORK
# ============================================================
with tab_net:
    st.subheader("Supply Chain Network")
    st.caption(
        "Top-N entities by BC + 1-hop neighbours.  "
        "Colour = entity type · Size = BC score (log) · **Red** = high-risk."
    )

    net_edges_df = dfs["net_edges"]
    net_nodes_df = dfs["net_nodes"]

    if bc_df.empty or net_edges_df.empty or net_nodes_df.empty:
        st.info(
            "network_edges.csv / network_nodes.csv not found.  "
            "Re-run `run_graph_eda.py` to generate them (they are now saved in Step 2)."
        )
    else:
        with st.spinner("Rendering network…"):
            try:
                G_sub = build_subgraph(top_n, show_hospitals)

                if G_sub.number_of_nodes() == 0:
                    st.warning("Subgraph is empty — try increasing top-N.")
                else:
                    bc_idx = bc_df.set_index("entity_id")
                    pos = nx.spring_layout(G_sub, seed=int(layout_seed), k=1.5)

                    ex, ey = [], []
                    for u, v in G_sub.edges():
                        x0, y0 = pos[u]; x1, y1 = pos[v]
                        ex += [x0, x1, None]; ey += [y0, y1, None]

                    traces: list = [go.Scatter(
                        x=ex, y=ey, mode="lines",
                        line=dict(width=0.5, color="#dddddd"),
                        hoverinfo="none", showlegend=False,
                    )]

                    for ntype, base_color in _TYPE_COLOR.items():
                        group = [n for n in G_sub.nodes()
                                 if G_sub.nodes[n].get("node_type", "unknown") == ntype]
                        if not group:
                            continue
                        xs, ys, sizes, texts, colours = [], [], [], [], []
                        for n in group:
                            xs.append(pos[n][0]); ys.append(pos[n][1])
                            if n in bc_idx.index:
                                row = bc_idx.loc[n]
                                # loc returns DataFrame when index has duplicates
                                if isinstance(row, pd.DataFrame):
                                    row = row.iloc[0]
                                bc_val = float(row["bc_score"])
                                high   = bool(row.get("high_risk", False))
                            else:
                                bc_val, high = 0.0, False
                            sizes.append(max(7, np.log1p(bc_val * 1e7) * 3 + 7))
                            colours.append(_RISK_COLOR if high else base_color)
                            label = G_sub.nodes[n].get("name") or str(n)
                            texts.append(
                                f"<b>{label}</b>{'  ⚠️' if high else ''}<br>"
                                f"Type: {ntype}<br>BC: {bc_val:.3e}<br>"
                                f"In: {G_sub.in_degree(n)}  Out: {G_sub.out_degree(n)}"
                            )
                        traces.append(go.Scatter(
                            x=xs, y=ys, mode="markers", name=ntype,
                            marker=dict(size=sizes, color=colours,
                                        line=dict(width=1.5, color="white")),
                            text=texts, hoverinfo="text",
                        ))

                    fig_net = go.Figure(
                        data=traces,
                        layout=go.Layout(
                            showlegend=True, hovermode="closest", height=580,
                            margin=dict(b=20, l=5, r=5, t=10),
                            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            plot_bgcolor="white", paper_bgcolor="white",
                            legend=dict(orientation="h", yanchor="bottom",
                                        y=1.01, xanchor="left", x=0),
                        ),
                    )
                    st.plotly_chart(fig_net, use_container_width=True)
                    st.caption(
                        f"Rendered {G_sub.number_of_nodes():,} nodes · "
                        f"{G_sub.number_of_edges():,} edges  "
                        f"(top-{top_n} BC + 1-hop neighbours)"
                    )
            except Exception as exc:
                st.error(f"Network error: {exc}")
                st.info("Make sure run_graph_eda.py completed successfully.")


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
        st.plotly_chart(fig_pdi, use_container_width=True)

        cols_show = [c for c in ["udi_di", "pdi", "device_class", "tx_count",
                                  "unique_suppliers", "unique_receivers"] if c in pdi_df.columns]
        st.subheader("High-risk UDI-DIs (PDI ≥ 3)")
        st.dataframe(
            pdi_df[pdi_df["high_risk"]][cols_show].sort_values("pdi", ascending=False)
            .style.background_gradient(subset=["pdi"], cmap="Reds"),
            use_container_width=True, height=300,
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
        st.plotly_chart(fig_bc, use_container_width=True)

        st.subheader("BC by Node Type")
        type_bc = (
            bc_df.groupby("node_type")["bc_score"]
            .agg(mean="mean", max="max", count="count")
            .reset_index().sort_values("mean", ascending=False).round(8)
        )
        st.dataframe(type_bc, use_container_width=True)


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
            st.plotly_chart(fig_pie,  use_container_width=True)
        with right:
            st.plotly_chart(fig_hist, use_container_width=True)

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
            use_container_width=True, height=350,
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
        st.plotly_chart(fig_pz, use_container_width=True)

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
            st.plotly_chart(fig_scatter, use_container_width=True)

        st.subheader("High-risk supplier table")
        ent_cols = [c for c in ["supplier_name", "flag_count", "total_tx", "flag_rate",
                                 "median_zscore", "max_zscore"] if c in pz_ent_df.columns]
        hr = pz_ent_df[pz_ent_df.get("high_risk", pd.Series(False, index=pz_ent_df.index))][ent_cols]
        grad_pz = [c for c in ["flag_rate", "max_zscore"] if c in hr.columns]
        st.dataframe(
            hr.sort_values("flag_rate", ascending=False)
            .style.background_gradient(subset=grad_pz, cmap="Reds"),
            use_container_width=True, height=300,
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
        st.plotly_chart(fig_lag_hist, use_container_width=True)

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
        st.plotly_chart(fig_lag_bar, use_container_width=True)

        st.subheader("Full supplier time-lag table")
        lag_cols_show = [c for c in ["supplier_name", lag_col, "max_lag_days", "tx_count"]
                         if c in timelag_df.columns]
        st.dataframe(
            timelag_df[lag_cols_show].sort_values(lag_col, ascending=False)
            .style.background_gradient(subset=[lag_col], cmap="Reds"),
            use_container_width=True, height=400,
        )
