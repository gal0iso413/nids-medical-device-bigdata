"""
Class 3 — Anonymous cohort dashboard (innovation wizard on Streamlit).

No firm search, no entity risk / GNN scores. Reads precomputed UI artifacts.

Run:
  streamlit run class_3_impact_evaluation/app.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
UI_DIR = ROOT / "output" / "ui"

st.set_page_config(
    page_title="Class 3 · 기업군 동향",
    page_icon="📊",
    layout="wide",
)


def _load(name: str) -> dict | list:
    path = UI_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


filters = _load("filter_options.json")
cohorts = _load("cohorts.json")
maps = _load("cohort_maps.json")
items = _load("item_stats.json")
manifest = _load("manifest.json")

st.sidebar.markdown("### 내부 모니터링")
st.sidebar.caption("Class 3 · 우리 기업군 동향")
st.sidebar.markdown("Class 1은 `streamlit run class_1_anomaly_detection/app.py`")

st.markdown(
    """
<div style="background:#003675;color:white;padding:14px 18px;border-radius:8px;margin-bottom:12px;">
  <strong>익명 집계 · 내부 참고</strong><br/>
  <span style="opacity:0.9;font-size:0.92rem;">
  회사명·순위·개체 위험점수는 제공하지 않습니다. 공급내역보고 기반이며 판매량이 아닙니다.
  </span>
</div>
""",
    unsafe_allow_html=True,
)

if not filters or not cohorts:
    st.error(
        "코호트 아티팩트가 없습니다. 실행:\n"
        "`python -m class_3_impact_evaluation.src.eda.run_cohort_pipeline`"
    )
    st.stop()

st.title("우리 기업군 동향")
st.info(filters.get("disclaimer_ko", ""))

# Wizard
st.markdown("#### 1 → 2 → 3 프로필")
c1, c2, c3 = st.columns(3)
biz_opts = filters.get("business_types") or ["제조업"]
region_opts = filters.get("regions") or ["수도권", "비수도권", "전국"]
group_opts = filters.get("product_groups") or []

with c1:
    biz = st.selectbox("업종", biz_opts)
with c2:
    region = st.selectbox("주 활동 권역", region_opts)
with c3:
    group = st.selectbox("관심 품목군", group_opts if group_opts else ["—"])

key = f"{biz}||{region}||{group}"
# Prefer exact; else best match same biz+region
cohort = cohorts.get(key)
if cohort is None:
    candidates = [k for k in cohorts if k.startswith(f"{biz}||{region}||")]
    if candidates:
        key = candidates[0]
        cohort = cohorts[key]
        st.caption(f"정확한 조합 집계가 없어 유사 조합을 표시합니다: `{key}`")

if cohort is None:
    st.warning("해당 조건의 집계가 없습니다. 조건을 바꿔 보세요.")
    st.stop()

st.markdown("### 기업군 리포트 · 거시")
m1, m2, m3, m4 = st.columns(4)
m1.metric("거래 건수(창)", f"{cohort['tx_count']:,}")
m2.metric("품목명 수", f"{cohort['item_name_count']:,}")
m3.metric("최근 증감률", f"{cohort['growth_pct']:.1f}%")
m4.metric("공급 집중도(HHI)", f"{cohort['hhi']:.3f}")
st.caption(
    f"보고대상 비중(추정): {cohort.get('in_report_scope_share', 0):.0%} · "
    f"공급자 수 프록시: {cohort.get('cohort_size_proxy', 0)}"
)

monthly = pd.DataFrame(cohort.get("monthly") or [])
if not monthly.empty:
    fig = px.line(monthly, x="month", y="tx_count", markers=True, title="월별 거래 활동")
    st.plotly_chart(fig, use_container_width=True)

st.markdown("### 진단")
for line in cohort.get("diagnosis", []):
    st.write(f"- {line}")

st.markdown("### 품목군 검토 지도")
map_key = f"{biz}||{region}"
map_rows = maps.get(map_key) or []
if map_rows:
    mdf = pd.DataFrame(map_rows)
    fig2 = px.scatter(
        mdf,
        x="hhi",
        y="growth_pct",
        size="supplier_count",
        color="selected",
        hover_name="product_group",
        title="집중도 × 증감 (거품=공급자 수)",
        labels={"hhi": "공급 집중도(HHI)", "growth_pct": "최근 증감(%)"},
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.write("지도 데이터 없음")

st.markdown("---")
st.markdown("### 관심 의료기기 · 품목명 (다중 선택)")
st.caption("품목 등록정보 색인이 아닙니다. 공급내역 집계 통계입니다.")
item_names = sorted(items.keys())
# Prefer items in selected group
preferred = [n for n, v in items.items() if v.get("product_group") == group]
default = preferred[:2] if preferred else item_names[:2]
selected_items = st.multiselect("품목명", item_names, default=default)

if selected_items:
    compare_rows = []
    for name in selected_items:
        meta = items[name]
        compare_rows.append(
            {
                "품목명": name,
                "품목군": meta.get("product_group"),
                "거래건수": meta.get("tx_count"),
                "수량합": meta.get("qty_sum"),
                "보고대상": "Y" if meta.get("in_report_scope") else "N/부분",
                "등급(최빈)": meta.get("device_class_mode"),
            }
        )
    st.dataframe(pd.DataFrame(compare_rows), use_container_width=True)

    # Overlay trends
    fig3 = go.Figure()
    for name in selected_items:
        m = pd.DataFrame(items[name].get("monthly") or [])
        if m.empty:
            continue
        fig3.add_trace(
            go.Scatter(x=m["month"], y=m["tx_count"], mode="lines+markers", name=name[:24])
        )
    fig3.update_layout(title="선택 품목명 월별 거래 활동 비교", height=360)
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("비교할 품목명을 하나 이상 선택하세요.")

if filters.get("my_company_mode_enabled"):
    st.warning("내 회사 모드 훅이 켜져 있으나 v1에서는 구현되지 않았습니다.")
else:
    st.caption("내 회사 인증 모드: 비활성 (설정 훅만 존재)")

st.caption(manifest.get("note", "Anonymous aggregates only."))
