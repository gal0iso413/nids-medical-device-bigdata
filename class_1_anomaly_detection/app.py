"""
Class 1 — Supply-chain review explorer (innovation IA on Streamlit).

Reads precomputed UI artifacts only (no Excel, no full-graph render).
Production ranking: GAD-NR. Rule metrics are auxiliary evidence chips.

Run:
  streamlit run class_1_anomaly_detection/app.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
UI_ROOT = OUTPUT / "ui"
WATCHLIST_PATH = UI_ROOT / "watchlist_local.json"
PRODUCTION_SLUG = "gadnr"

st.set_page_config(
    page_title="Class 1 · 유통 관계 확인",
    page_icon="🔍",
    layout="wide",
)


def _list_anchors() -> list[str]:
    if not UI_ROOT.exists():
        return []
    return sorted(
        p.name.replace("anchor_", "")
        for p in UI_ROOT.glob("anchor_*")
        if p.is_dir() and (p / "review_list.csv").exists()
    )


def _ui_dir(anchor: str) -> Path:
    return UI_ROOT / f"anchor_{anchor}"


@st.cache_data(show_spinner=False)
def load_review(anchor: str) -> pd.DataFrame:
    path = _ui_dir(anchor) / "review_list.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def load_json(path_str: str) -> dict:
    path = Path(path_str)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_watchlist() -> list[dict]:
    if not WATCHLIST_PATH.exists():
        return []
    try:
        return json.loads(WATCHLIST_PATH.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []


def save_watchlist(items: list[dict]) -> None:
    UI_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    WATCHLIST_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def render_ego_figure(payload: dict, *, edge_mode: str = "tx_count") -> go.Figure:
    nodes = payload.get("nodes", [])
    edges = payload.get("edges", [])
    if not nodes:
        fig = go.Figure()
        fig.update_layout(title="연결망 없음")
        return fig

    # Simple circular layout around focal
    focal = next((n for n in nodes if n.get("is_focal")), nodes[0])
    others = [n for n in nodes if n["entity_id"] != focal["entity_id"]]
    pos = {focal["entity_id"]: (0.0, 0.0)}
    import math

    for i, n in enumerate(others):
        ang = 2 * math.pi * i / max(len(others), 1)
        pos[n["entity_id"]] = (math.cos(ang), math.sin(ang))

    edge_x, edge_y = [], []
    for e in edges:
        x0, y0 = pos.get(e["src"], (0, 0))
        x1, y1 = pos.get(e["dst"], (0, 0))
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line=dict(width=1, color="#9aa7b5"),
            hoverinfo="none",
            showlegend=False,
        )
    )
    xs, ys, texts, sizes, colors = [], [], [], [], []
    for n in nodes:
        x, y = pos[n["entity_id"]]
        xs.append(x)
        ys.append(y)
        texts.append(f"{n.get('name') or n['entity_id']}<br>{n.get('node_type')}")
        sizes.append(12 + min(int(n.get("degree", 1)) * 2, 24))
        colors.append("#003675" if n.get("is_focal") else "#2a9d8f")
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers+text",
            text=[(n.get("name") or n["entity_id"])[:12] for n in nodes],
            textposition="top center",
            marker=dict(size=sizes, color=colors, line=dict(width=2, color="#001a3a")),
            hovertext=texts,
            hoverinfo="text",
            showlegend=False,
        )
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=30, b=10),
        height=420,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        plot_bgcolor="#f7f9fc",
        title=f"선택 업체 중심 연결망 ({edge_mode})",
    )
    return fig


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.markdown("### 내부 모니터링")
st.sidebar.caption("Class 1 · 유통 관계 확인")
st.sidebar.markdown("[Class 3 기업군 동향](../class_3_impact_evaluation/)")

anchors = _list_anchors()
if not anchors:
    st.error(
        "UI 아티팩트가 없습니다. 다음을 순서대로 실행하세요:\n"
        "1. `python -m class_1_anomaly_detection.src.ingest.materialize_parquet`\n"
        "2. `python -m class_1_anomaly_detection.src.eda.run_graph_eda --anchor-month YYYYMM`\n"
        "3. `python -m class_1_anomaly_detection.src.experiments.export_pyg_graph --anchor-month YYYYMM`\n"
        "4. `python -m class_1_anomaly_detection.src.experiments.run_gadnr_production --anchor-month YYYYMM`\n"
        "5. `python -m class_1_anomaly_detection.src.experiments.build_ui_artifacts --anchor-month YYYYMM`"
    )
    st.stop()

anchor = st.sidebar.selectbox("기준월(앵커)", anchors, index=len(anchors) - 1)
if st.sidebar.button("캐시 새로고침"):
    st.cache_data.clear()
    st.rerun()

ui_dir = _ui_dir(anchor)
manifest = load_json(str(ui_dir / "manifest.json"))
events_payload = load_json(str(ui_dir / "events.json"))
overview = load_json(str(ui_dir / "top_n_overview.json"))
evidence_all = load_json(str(ui_dir / "entity_evidence.json"))
review = load_review(anchor)

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
st.markdown(
    """
<div style="background:#003675;color:white;padding:14px 18px;border-radius:8px;margin-bottom:12px;">
  <strong>내부 참고용 · 정책 모니터링</strong><br/>
  <span style="opacity:0.9;font-size:0.92rem;">
  본 화면의 관계 AI 점수와 보조 지표는 적발·제재 목적이 아닙니다.
  특정 품목의 공급망 이상을 내부에서 참고하기 위한 자료입니다.
  </span>
</div>
""",
    unsafe_allow_html=True,
)

st.title("유통 관계 확인")
st.caption(
    f"기준월 `{anchor}` · 창 "
    f"`{', '.join(manifest.get('window_months', events_payload.get('window_months', []))) or '—'}` · "
    f"생산 모형 **GAD-NR** (허브 BC 순위 ≠ AI 검토 순위)"
)

ev_list = events_payload.get("events", [])
if ev_list:
    with st.expander("외부 이슈 캘린더 (창 중첩)", expanded=True):
        for ev in ev_list:
            st.warning(f"**{ev.get('label')}** ({ev.get('start_month')}–{ev.get('end_month')}): {ev.get('note', '')}")

# ---------------------------------------------------------------------------
# Search + hero
# ---------------------------------------------------------------------------
name_map = {}
if not review.empty and "name" in review.columns:
    name_map = {
        f"{r.get('name') or ''} ({r['entity_id']})": str(r["entity_id"])
        for _, r in review.iterrows()
    }
# Also allow raw id search from overview
for ent in overview.get("entities", []):
    label = f"{ent.get('name') or ''} ({ent['entity_id']})"
    name_map.setdefault(label, str(ent["entity_id"]))

search_options = ["— 업체 선택 —"] + sorted(name_map.keys())
col_s, col_h = st.columns([2, 1])
with col_s:
    pick = st.selectbox("업체 검색", search_options)
with col_h:
    hops = st.radio("연결 깊이", [1, 2], horizontal=True, index=0)
    edge_mode = st.selectbox("연결 굵기", ["tx_count", "weight"], format_func=lambda x: "보고 건수" if x == "tx_count" else "공급 금액")

focal_id = name_map.get(pick) if pick in name_map else None

# Watchlist
wl = load_watchlist()
with st.sidebar.expander("북마크 / 저장 검색", expanded=False):
    st.caption("알림 없음 · 로컬 저장만")
    if focal_id and st.button("현재 업체 북마크"):
        if not any(i.get("entity_id") == focal_id for i in wl):
            wl.append(
                {
                    "entity_id": focal_id,
                    "label": pick,
                    "anchor_month": anchor,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                    "notes": "",
                }
            )
            save_watchlist(wl)
            st.success("저장됨")
    for item in wl:
        st.write(f"- `{item.get('entity_id')}` {item.get('label', '')}")

# Hero brief
if focal_id:
    row = review[review["entity_id"].astype(str) == focal_id]
    ev = evidence_all.get(focal_id, {})
    st.subheader("한눈에 보기")
    m1, m2, m3, m4 = st.columns(4)
    if not row.empty:
        r0 = row.iloc[0]
        m1.metric("관계 AI 점수", f"{float(r0.get(f'{PRODUCTION_SLUG}_score', 0) or 0):.4g}")
        m2.metric("관계 AI 순위", int(r0.get(f"{PRODUCTION_SLUG}_rank", 0) or 0))
        m3.metric("BC (보조)", f"{float(r0.get('bc_score', 0) or 0):.2e}")
        m4.metric("BC 순위 (허브)", int(r0.get("bc_rank", 0) or 0))
    else:
        st.info("선택 업체가 검토 목록 상위권 밖일 수 있습니다. 연결망만 표시합니다.")

    # Progressive disclosure: evidence first
    st.markdown("### 확인 근거")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**관찰된 사실**")
        for t in ev.get("observed_facts", ["—"]):
            st.write(f"- {t}")
    with c2:
        st.markdown("**모형의 해석**")
        for t in ev.get("interpretations", ["—"]):
            st.write(f"- {t}")
    with c3:
        st.markdown("**확인할 질문**")
        for t in ev.get("next_questions", ["—"]):
            st.write(f"- {t}")

    aux = ev.get("auxiliary", {})
    chips = [
        f"가격이상비율 {aux.get('price_flag_rate', 0):.2f}",
        f"지연일 중앙값 {aux.get('median_lag_days', 0):.0f}",
        f"BC순위 {aux.get('bc_rank', '—')}",
    ]
    st.caption("보조 지표 · " + " · ".join(chips))

    show_net = st.checkbox("연결망 보기", value=False)
    if show_net:
        ego_path = ui_dir / "ego" / f"{focal_id}_h{hops}.json"
        payload = load_json(str(ego_path))
        if not payload:
            st.warning("해당 업체의 ego 아티팩트가 없습니다. build_ui_artifacts를 다시 실행하세요.")
        else:
            if payload.get("truncated"):
                st.caption("표시 한도로 일부 연결이 생략되었습니다.")
            st.plotly_chart(render_ego_figure(payload, edge_mode=edge_mode), use_container_width=True)
else:
    st.info("업체를 검색하거나 아래 확인 필요 목록에서 선택하세요.")

st.markdown("---")
st.markdown("### 확인 필요 업체 (관계 AI = GAD-NR 순위)")
st.caption("BC 허브 목록과 다릅니다. 규칙 지표는 보조 칩으로만 사용합니다.")

if review.empty:
    st.warning("review_list.csv 가 비어 있습니다.")
else:
    show_cols = [
        c
        for c in [
            "entity_id",
            "name",
            "node_type",
            f"{PRODUCTION_SLUG}_score",
            f"{PRODUCTION_SLUG}_rank",
            "bc_score",
            "bc_rank",
            "price_flag_rate",
            "median_lag_days",
        ]
        if c in review.columns
    ]
    st.dataframe(review[show_cols], use_container_width=True, height=360)

    # Review deck cards (top 5)
    st.markdown("#### 검토 카드")
    for _, r in review.head(5).iterrows():
        eid = str(r["entity_id"])
        with st.container(border=True):
            st.markdown(
                f"**{r.get('name') or eid}** · AI순위 {int(r.get(f'{PRODUCTION_SLUG}_rank', 0) or 0)} · "
                f"BC순위 {int(r.get('bc_rank', 0) or 0)}"
            )
            ev = evidence_all.get(eid, {})
            if ev.get("next_questions"):
                st.write(ev["next_questions"][0])
            if st.button("이 업체 열기", key=f"open_{eid}"):
                st.session_state["force_pick"] = eid
                st.info(f"사이드바/검색에서 `{eid}` 를 선택하세요.")

st.markdown("---")
with st.expander("허브 탐색 (BC Top-N) — AI 검토 순위 아님", expanded=False):
    ents = overview.get("entities", [])
    if not ents:
        st.write("overview 없음")
    else:
        st.dataframe(pd.DataFrame(ents), use_container_width=True)

st.caption(manifest.get("disclaimer", "Internal reference only."))
