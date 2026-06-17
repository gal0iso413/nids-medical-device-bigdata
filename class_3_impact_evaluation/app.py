"""
Class 3 — Impact Evaluation Explorer (Phase 1 prototype)

Reads pre-computed output CSVs from class_3_impact_evaluation/output/.
Run run_mcdm_eda.py first (or again) to refresh them, then click
"Reload data" in the sidebar.

Launch:  streamlit run class_3_impact_evaluation/app.py
"""
from __future__ import annotations

import sys
import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

OUTPUT = _HERE / "output"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Class 3 · Impact Evaluation Explorer",
    page_icon="🗺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
_HHI_COLOR = {
    "high":        "#e41a1c",
    "moderate":    "#f58518",
    "competitive": "#54a24b",
}

_QUADRANT_COLOR = {
    "Strategic":  "#e41a1c",
    "Bottleneck": "#f58518",
    "Leverage":   "#4c78a8",
    "Routine":    "#aec7e8",
}


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
        "supply_risk": _read("supply_risk_per_group"),
        "clinical":    _read("clinical_impact_per_group"),
        "combined":    _read("mcdm_inputs_combined"),
    }


def _quadrant_label(row: pd.Series, x_thresh: float, y_thresh: float) -> str:
    x_raw = row.get("hhi")
    y_raw = row.get("unique_hospital_count")
    x = 0.0 if (x_raw is None or pd.isna(x_raw)) else float(x_raw)
    y = 0.0 if (y_raw is None or pd.isna(y_raw)) else float(y_raw)
    if x >= x_thresh and y >= y_thresh:
        return "Strategic"
    if x < x_thresh and y >= y_thresh:
        return "Leverage"
    if x >= x_thresh and y < y_thresh:
        return "Bottleneck"
    return "Routine"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.header("Controls")

if st.sidebar.button("🔄 Reload data", help="Clear cached CSVs and re-read output/"):
    st.cache_data.clear()
    st.rerun()

dfs = load_outputs()
supply_risk_df = dfs["supply_risk"]
clinical_df    = dfs["clinical"]
combined_df    = dfs["combined"]

# Quadrant thresholds — Phase 1 provisional; PM locks in Phase 2
st.sidebar.markdown("---")
st.sidebar.markdown("**Quadrant thresholds** *(provisional — Phase 2 locks)*")

if not combined_df.empty and "hhi" in combined_df.columns:
    hhi_p50  = float(combined_df["hhi"].quantile(0.50))
    hosp_p50 = int(combined_df["unique_hospital_count"].dropna().quantile(0.50)) \
               if "unique_hospital_count" in combined_df.columns else 50
else:
    hhi_p50, hosp_p50 = 0.25, 50

x_thresh = st.sidebar.number_input(
    "Supply Risk (HHI) split", 0.0, 1.0, round(hhi_p50, 4), step=0.01, format="%.4f"
)
y_thresh = st.sidebar.number_input(
    "Clinical Impact (hospitals) split", 0, 10_000, hosp_p50, step=10
)

# Output file status
st.sidebar.markdown("---")
st.sidebar.caption("**Output files**")
for name in ["supply_risk_per_group", "clinical_impact_per_group", "mcdm_inputs_combined"]:
    p = OUTPUT / f"{name}.csv"
    if p.exists():
        mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%m-%d %H:%M")
        st.sidebar.caption(f"✅ {name}  `{mtime}`")
    else:
        st.sidebar.caption(f"❌ {name} — missing")

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.title("🗺 Class 3 — Medical Device Impact Evaluation Explorer")
st.caption(
    "Phase 1 EDA prototype · read from `output/` CSVs · "
    "use **Reload data** after re-running `run_mcdm_eda.py`"
)

missing = [k for k, v in dfs.items() if v.empty]
if missing:
    st.warning(
        f"Missing CSVs: {missing}. "
        "Run `python class_3_impact_evaluation/src/eda/run_mcdm_eda.py` first.",
        icon="⚠️",
    )

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_matrix, tab_risk, tab_impact, tab_combined = st.tabs([
    "🗺 Kraljic Matrix",
    "⚠️ Supply Risk (HHI)",
    "🏥 Clinical Impact",
    "📋 MCDM Inputs",
])


# ============================================================
# TAB 1 — KRALJIC MATRIX
# ============================================================
with tab_matrix:
    st.subheader("Kraljic-Style Portfolio Matrix")
    st.markdown(
        "**X-axis** (Supply Risk) = HHI per product group.  "
        "**Y-axis** (Clinical Impact) = unique hospital count.  "
        "**Bubble size** ∝ log(total supply amount KRW).  \n"
        "> Quadrant thresholds use P50 as provisional split (adjust in sidebar). "
        "PM locks P50/P75 thresholds in Phase 2 Framework."
    )

    if combined_df.empty:
        st.info("mcdm_inputs_combined.csv not found.")
    else:
        df = combined_df.copy()
        df["quadrant"] = df.apply(_quadrant_label, axis=1, x_thresh=x_thresh, y_thresh=y_thresh)

        # Bubble size: log-scale supply amount, normalised for readability
        df["_size"] = df["total_supply_amount_krw"].clip(lower=1).apply(np.log1p)
        df["_size"] = (df["_size"] / df["_size"].max() * 55 + 8).round(1)

        # Detect Korean clinical flag columns
        _COL_CLASS   = next((c for c in df.columns if "등급" in c and len(c) <= 4), None)
        _COL_IMPLANT = next((c for c in df.columns if "이식" in c), None)
        _COL_TRACE   = next((c for c in df.columns if "추적" in c), None)
        _COL_ORPHAN  = next((c for c in df.columns if "희귀" in c), None)

        extra_hover: dict = {}
        if _COL_CLASS:   extra_hover["Device class (등급)"] = _COL_CLASS
        if _COL_IMPLANT: extra_hover["Implantable"]          = _COL_IMPLANT
        if _COL_TRACE:   extra_hover["Traceable"]            = _COL_TRACE
        if _COL_ORPHAN:  extra_hover["Orphan device"]        = _COL_ORPHAN

        fig_matrix = px.scatter(
            df,
            x="hhi",
            y="unique_hospital_count",
            size="_size",
            size_max=55,
            color="quadrant",
            color_discrete_map=_QUADRANT_COLOR,
            hover_name="product_group",
            hover_data={
                "hhi": ":.4f",
                "top3_supplier_share": ":.2%",
                "supplier_count": True,
                "unique_hospital_count": True,
                "total_supply_amount_krw": ":,.0f",
                "_size": False,
                "quadrant": False,
                **{k: True for k in extra_hover.values()},
            },
            title="Kraljic Portfolio Matrix — Product Groups",
            labels={
                "hhi": "Supply Risk (HHI)",
                "unique_hospital_count": "Clinical Impact (Unique Hospitals)",
            },
            height=580,
        )

        # Quadrant dividers
        fig_matrix.add_vline(
            x=x_thresh, line_dash="dash", line_color="#777777",
            annotation_text=f"HHI = {x_thresh:.4f} (provisional P50)",
            annotation_position="top right",
        )
        fig_matrix.add_hline(
            y=y_thresh, line_dash="dash", line_color="#777777",
            annotation_text=f"Hospitals = {y_thresh} (provisional P50)",
            annotation_position="top right",
        )

        # Quadrant corner labels
        y_max = float(df["unique_hospital_count"].dropna().max()) if not df.empty else 1000.0
        x_max = float(df["hhi"].dropna().max()) if not df.empty else 1.0
        for label, xpos, ypos in [
            ("Strategic",  x_max * 0.80, y_max * 0.90),
            ("Bottleneck", x_max * 0.80, y_max * 0.06),
            ("Leverage",   x_max * 0.04, y_max * 0.90),
            ("Routine",    x_max * 0.04, y_max * 0.06),
        ]:
            fig_matrix.add_annotation(
                x=xpos, y=ypos,
                text=f"<b>{label}</b>",
                showarrow=False,
                font=dict(size=13, color=_QUADRANT_COLOR[label]),
                opacity=0.45,
            )

        fig_matrix.update_layout(plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_matrix, use_container_width=True)

        # Quadrant counts
        q_counts = df["quadrant"].value_counts()
        c1, c2, c3, c4 = st.columns(4)
        for col, q in zip([c1, c2, c3, c4], ["Strategic", "Bottleneck", "Leverage", "Routine"]):
            col.metric(q, int(q_counts.get(q, 0)))

        st.markdown("---")
        q_filter = st.selectbox(
            "Filter table by quadrant",
            ["All", "Strategic", "Bottleneck", "Leverage", "Routine"],
        )
        display_df = df if q_filter == "All" else df[df["quadrant"] == q_filter]

        show_cols = ["product_group", "quadrant", "hhi", "hhi_label",
                     "top3_supplier_share", "supplier_count",
                     "unique_hospital_count", "total_supply_amount_krw"]
        show_cols = [c for c in show_cols if c in display_df.columns]
        st.dataframe(
            display_df[show_cols]
            .sort_values("hhi", ascending=False)
            .style.background_gradient(subset=["hhi"], cmap="Reds"),
            use_container_width=True,
            height=320,
        )


# ============================================================
# TAB 2 — SUPPLY RISK (HHI)
# ============================================================
with tab_risk:
    st.subheader("Supply Risk — HHI & Top-3 Supplier Concentration")
    st.markdown(
        "**HHI** = Σ(supplier share of supply amount)² per product group (0–1 scale).  \n"
        "**HHI > 0.25** → high · **0.15–0.25** → moderate · **≤ 0.15** → competitive.  \n"
        "**Top-3 share** = combined fraction of the three largest suppliers."
    )

    if supply_risk_df.empty:
        st.info("supply_risk_per_group.csv not found.")
    else:
        total  = len(supply_risk_df)
        high_n = int((supply_risk_df["hhi_label"] == "high").sum())
        mod_n  = int((supply_risk_df["hhi_label"] == "moderate").sum())
        comp_n = int((supply_risk_df["hhi_label"] == "competitive").sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Product groups", total)
        c2.metric("High (HHI > 0.25)",    f"{high_n}",  f"{high_n / max(total, 1):.0%}")
        c3.metric("Moderate (0.15–0.25)", f"{mod_n}")
        c4.metric("Competitive (≤ 0.15)", f"{comp_n}")

        left, right = st.columns([1, 2])
        with left:
            pie_df = pd.DataFrame({
                "Concentration": ["High", "Moderate", "Competitive"],
                "Count":         [high_n, mod_n, comp_n],
            })
            fig_pie = px.pie(
                pie_df, names="Concentration", values="Count",
                color="Concentration",
                color_discrete_map={
                    "High": "#e41a1c", "Moderate": "#f58518", "Competitive": "#54a24b"
                },
                title="HHI Concentration Breakdown",
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with right:
            fig_hist = px.histogram(
                supply_risk_df, x="hhi", nbins=50,
                color="hhi_label",
                color_discrete_map=_HHI_COLOR,
                title="HHI Score Distribution",
                labels={"hhi": "HHI Score"},
            )
            fig_hist.add_vline(x=0.25, line_dash="dash",  line_color="#e41a1c",
                               annotation_text="0.25 high")
            fig_hist.add_vline(x=0.15, line_dash="dot",   line_color="#f58518",
                               annotation_text="0.15 mod")
            st.plotly_chart(fig_hist, use_container_width=True)

        n_show = st.slider("Show top-N groups by HHI", 10, 80, 25, key="risk_top_n")
        top_risk = supply_risk_df.nlargest(n_show, "hhi").copy()

        fig_bar = px.bar(
            top_risk, x="hhi", y="product_group", orientation="h",
            color="hhi_label",
            color_discrete_map=_HHI_COLOR,
            title=f"Top-{n_show} Product Groups by HHI",
            labels={"hhi": "HHI", "product_group": "Product Group", "hhi_label": "Concentration"},
            height=max(420, n_show * 22),
        )
        fig_bar.update_layout(yaxis={"categoryorder": "total ascending"})
        fig_bar.add_vline(x=0.25, line_dash="dash", line_color="#e41a1c")
        st.plotly_chart(fig_bar, use_container_width=True)

        # HHI vs Top-3 scatter
        fig_scatter = px.scatter(
            supply_risk_df,
            x="hhi",
            y="top3_supplier_share",
            color="hhi_label",
            color_discrete_map=_HHI_COLOR,
            hover_name="product_group",
            hover_data={"supplier_count": True, "total_supply_amount_krw": ":,.0f"},
            title="HHI vs Top-3 Supplier Share",
            labels={
                "hhi": "HHI",
                "top3_supplier_share": "Top-3 Share",
                "hhi_label": "Concentration",
            },
        )
        fig_scatter.add_vline(x=0.25, line_dash="dash", line_color="#e41a1c")
        fig_scatter.add_hline(y=0.80, line_dash="dot",  line_color="#777777",
                              annotation_text="top-3 share 80 %")
        st.plotly_chart(fig_scatter, use_container_width=True)

        st.subheader("High-concentration groups")
        high_df = supply_risk_df[supply_risk_df["hhi_label"] == "high"].sort_values("hhi", ascending=False)
        show_cols_h = [c for c in ["product_group", "hhi", "hhi_label",
                                   "top3_supplier_share", "supplier_count",
                                   "total_supply_amount_krw"] if c in high_df.columns]
        st.dataframe(
            high_df[show_cols_h]
            .style.background_gradient(
                subset=[c for c in ["hhi", "top3_supplier_share"] if c in high_df.columns],
                cmap="Reds",
            ),
            use_container_width=True, height=340,
        )


# ============================================================
# TAB 3 — CLINICAL IMPACT
# ============================================================
with tab_impact:
    st.subheader("Clinical Impact — Hospital Coverage per Product Group")
    st.markdown(
        "**Unique hospital count** = distinct `요양기관기호` values supplied per product group.  \n"
        "High breadth → broad systemic dependency. "
        "Low breadth → specialised niche. "
        "P50/P75 thresholds are provisional; PM locks them in Phase 2."
    )

    if clinical_df.empty:
        st.info("clinical_impact_per_group.csv not found.")
    else:
        max_hosp = int(clinical_df["unique_hospital_count"].max())
        med_hosp = float(clinical_df["unique_hospital_count"].median())
        p75_hosp = float(clinical_df["unique_hospital_count"].quantile(0.75))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Product groups", len(clinical_df))
        c2.metric("Max hospital coverage",    f"{max_hosp:,}")
        c3.metric("Median (P50) coverage",    f"{med_hosp:.0f}")
        c4.metric("Groups above P75",
                  int((clinical_df["unique_hospital_count"] > p75_hosp).sum()))

        fig_dist = px.histogram(
            clinical_df, x="unique_hospital_count", nbins=50,
            title="Distribution of Hospital Coverage per Product Group",
            labels={"unique_hospital_count": "Unique Hospitals"},
            color_discrete_sequence=["#4c78a8"],
        )
        fig_dist.add_vline(x=med_hosp, line_dash="dot",  line_color="#f58518",
                           annotation_text="P50")
        fig_dist.add_vline(x=p75_hosp, line_dash="dash", line_color="#e41a1c",
                           annotation_text="P75")
        st.plotly_chart(fig_dist, use_container_width=True)

        n_show_c = st.slider("Show top-N groups by hospital coverage", 10, 80, 25, key="clin_top_n")
        top_clin = clinical_df.nlargest(n_show_c, "unique_hospital_count")

        fig_clin = px.bar(
            top_clin, x="unique_hospital_count", y="product_group", orientation="h",
            title=f"Top-{n_show_c} Product Groups by Hospital Coverage",
            labels={
                "unique_hospital_count": "Unique Hospitals",
                "product_group": "Product Group",
            },
            color_discrete_sequence=["#4c78a8"],
            height=max(420, n_show_c * 22),
        )
        fig_clin.update_layout(yaxis={"categoryorder": "total ascending"})
        fig_clin.add_vline(x=p75_hosp, line_dash="dash", line_color="#e41a1c",
                           annotation_text=f"P75 = {p75_hosp:.0f}")
        st.plotly_chart(fig_clin, use_container_width=True)


# ============================================================
# TAB 4 — MCDM COMBINED
# ============================================================
with tab_combined:
    st.subheader("MCDM Inputs — Combined Table")
    st.markdown(
        "Raw input vectors per product group: Supply Risk (X) + Clinical Impact (Y) + device severity flags.  \n"
        "> **Composite MCDM weights and quadrant thresholds are deferred to Phase 2 Framework.**"
    )

    if combined_df.empty:
        st.info("mcdm_inputs_combined.csv not found.")
    else:
        df_c = combined_df.copy()
        df_c["quadrant"] = df_c.apply(
            _quadrant_label, axis=1, x_thresh=x_thresh, y_thresh=y_thresh
        )

        # Detect clinical flag columns
        _COL_CLASS   = next((c for c in df_c.columns if "등급" in c and len(c) <= 4), None)
        _COL_IMPLANT = next((c for c in df_c.columns if "이식" in c), None)
        _COL_TRACE   = next((c for c in df_c.columns if "추적" in c), None)
        _COL_ORPHAN  = next((c for c in df_c.columns if "희귀" in c), None)

        with st.expander("Filters", expanded=True):
            filt1, filt2, filt3 = st.columns(3)

            with filt1:
                hhi_opts = sorted(df_c["hhi_label"].dropna().unique().tolist())
                sel_hhi  = st.multiselect("HHI label", hhi_opts, default=hhi_opts, key="filt_hhi")

            with filt2:
                q_opts = ["Strategic", "Bottleneck", "Leverage", "Routine"]
                sel_q  = st.multiselect("Quadrant", q_opts, default=q_opts, key="filt_quad")

            with filt3:
                if _COL_CLASS:
                    class_opts = sorted(df_c[_COL_CLASS].dropna().unique().tolist())
                    sel_class  = st.multiselect(
                        "Device class (등급)", class_opts, default=class_opts, key="filt_class"
                    )
                else:
                    sel_class = []

        mask = df_c["hhi_label"].isin(sel_hhi) & df_c["quadrant"].isin(sel_q)
        if _COL_CLASS and sel_class:
            mask &= df_c[_COL_CLASS].isin(sel_class)
        df_show = df_c[mask]

        st.caption(f"Showing {len(df_show):,} / {len(df_c):,} product groups")

        display_cols = [
            "product_group", "quadrant", "hhi", "hhi_label",
            "top3_supplier_share", "supplier_count",
            "unique_hospital_count", "total_supply_amount_krw",
        ]
        for extra in [_COL_CLASS, _COL_IMPLANT, _COL_TRACE, _COL_ORPHAN]:
            if extra:
                display_cols.append(extra)
        display_cols = [c for c in display_cols if c in df_show.columns]

        grad_cols = [c for c in ["hhi", "unique_hospital_count"] if c in df_show.columns]
        st.dataframe(
            df_show[display_cols]
            .sort_values("hhi", ascending=False)
            .style.background_gradient(subset=grad_cols, cmap="RdYlGn_r"),
            use_container_width=True,
            height=520,
        )
