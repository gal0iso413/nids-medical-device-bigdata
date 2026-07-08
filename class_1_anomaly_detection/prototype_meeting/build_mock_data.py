"""Generate expanded mock_data.json for the meeting prototype.

Run from repo root:
  python class_1_anomaly_detection/prototype_meeting/build_mock_data.py
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent / "data" / "mock_data.json"
TYPE_LABEL = {"manufacturer": "제조사", "distributor": "유통사", "hospital": "병원"}
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def risk_from_score(score: int) -> str:
    if score >= 75:
        return "경고"
    if score >= 50:
        return "관찰"
    return "낮음"


def build_graph(m_count: int, d_count: int, h_count: int, hub_idx: int, hub_boost: float, seed: int) -> dict:
    rng = random.Random(seed)
    nodes: list[dict] = []
    edges: list[dict] = []

    for i in range(m_count):
        nodes.append(
            {
                "id": f"M{i + 1:03d}",
                "name": f"{LETTERS[i % len(LETTERS)]} 제조",
                "type": TYPE_LABEL["manufacturer"],
                "gnnScore": round(10 + rng.random() * 25),
                "risk": "낮음",
            }
        )
    for i in range(d_count):
        score = round(20 + rng.random() * 40)
        if i == hub_idx:
            score = round(70 + rng.random() * 25 + hub_boost)
        nodes.append(
            {
                "id": f"D{i + 1:03d}",
                "name": f"{LETTERS[i % len(LETTERS)]} 유통",
                "type": TYPE_LABEL["distributor"],
                "gnnScore": score,
                "risk": risk_from_score(score),
            }
        )
    for i in range(h_count):
        score = round(8 + rng.random() * 35)
        nodes.append(
            {
                "id": f"H{i + 1:03d}",
                "name": f"{LETTERS[i % len(LETTERS)]} 병원",
                "type": TYPE_LABEL["hospital"],
                "gnnScore": score,
                "risk": risk_from_score(score),
            }
        )

    m_ids = [n["id"] for n in nodes if n["type"] == TYPE_LABEL["manufacturer"]]
    d_ids = [n["id"] for n in nodes if n["type"] == TYPE_LABEL["distributor"]]
    h_ids = [n["id"] for n in nodes if n["type"] == TYPE_LABEL["hospital"]]
    hub_id = d_ids[hub_idx]

    def add_edge(src: str, dst: str, item: str) -> None:
        edges.append({"src": src, "dst": dst, "item": item, "weight": round(1 + rng.random() * 40)})

    for idx, hid in enumerate(h_ids):
        add_edge(m_ids[idx % len(m_ids)], d_ids[idx % len(d_ids)], f"품목 {(idx % 20) + 1}")
        add_edge(d_ids[idx % len(d_ids)], hid, f"품목 {(idx % 20) + 1}")

    for mid in m_ids:
        if rng.random() < 0.5:
            add_edge(mid, hub_id, f"품목 H{rng.randint(1, 12)}")
    for hid in h_ids[: int(h_count * 0.7)]:
        if rng.random() < 0.45:
            add_edge(hub_id, hid, f"품목 H{rng.randint(1, 12)}")

    for _ in range(int((m_count + d_count + h_count) * 1.2)):
        mid, did, hid = rng.choice(m_ids), rng.choice(d_ids), rng.choice(h_ids)
        if rng.random() < 0.5:
            add_edge(mid, did, f"품목 X{rng.randint(1, 30)}")
        if rng.random() < 0.55:
            add_edge(did, hid, f"품목 X{rng.randint(1, 30)}")

    node_by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        n["risk"] = risk_from_score(n["gnnScore"])
    watch = sum(
        1
        for e in edges
        if node_by_id[e["src"]]["risk"] != "낮음" or node_by_id[e["dst"]]["risk"] != "낮음"
    )
    return {"nodes": nodes, "edges": edges, "watchEdges": watch}


def scenario(id_: str, name: str, anchor: str, desc: str, graph: dict, hub_name: str) -> dict:
    top = sorted(
        [n for n in graph["nodes"] if n["type"] == TYPE_LABEL["distributor"]],
        key=lambda n: n["gnnScore"],
        reverse=True,
    )[:8]
    gnn_rows = [
        {
            "entity": n["name"],
            "entityId": n["id"],
            "score": str(n["gnnScore"]),
            "status": n["risk"],
            "reason": (
                "다수 제조사·병원 연결을 동시에 중개하는 허브 패턴"
                if n["name"] == hub_name
                else "AI 모델이 동종 업체 대비 비정상 거래 패턴을 감지"
            ),
        }
        for n in top
    ]
    node_by_id = {n["id"]: n for n in graph["nodes"]}
    table = []
    for e in graph["edges"][:40]:
        src, dst = node_by_id[e["src"]], node_by_id[e["dst"]]
        note = (
            "우선 확인"
            if src["risk"] == "경고" or dst["risk"] == "경고"
            else "관찰 필요"
            if src["risk"] == "관찰" or dst["risk"] == "관찰"
            else "일반 유통"
        )
        table.append({"supplier": src["name"], "receiver": dst["name"], "item": e["item"], "note": note})

    warn = sum(1 for n in graph["nodes"] if n["risk"] == "경고")
    avg = round(sum(n["gnnScore"] for n in graph["nodes"]) / len(graph["nodes"]))
    hub_id = next((n["id"] for n in graph["nodes"] if n["name"] == hub_name), top[0]["id"])

    return {
        "id": id_,
        "name": name,
        "anchorMonth": anchor,
        "description": desc,
        "network": {
            "cards": [
                {"label": "전체 참여 기관", "value": str(len(graph["nodes"])), "note": "제조사/유통사/병원 포함"},
                {"label": "주요 연결 수", "value": str(len(graph["edges"])), "note": "3개월 누적 거래 연결"},
                {"label": "관찰 대상 연결", "value": str(graph["watchEdges"]), "note": "AI·위험 등급과 연계된 연결"},
            ],
            "graph": graph,
            "table": table,
            "hubEntityId": hub_id,
        },
        "gnn": {
            "cards": [
                {"label": "AI 관찰 대상 수", "value": str(len(top)), "note": "유통사 상위 점수 대상"},
                {"label": "즉시 확인 권고", "value": str(warn), "note": "경고 등급 기관"},
                {"label": "평균 주의 점수", "value": str(avg), "note": "100점에 가까울수록 우선 확인"},
            ],
            "rows": gnn_rows,
        },
    }


def main() -> None:
    g1 = build_graph(12, 22, 38, 2, 5, 42)
    g2 = build_graph(12, 24, 40, 1, 12, 99)
    g3 = build_graph(10, 20, 35, 4, 8, 7)
    payload = {
        "meta": {
            "title": "Class 1 Meeting UI Prototype",
            "anchors": ["202605", "202606"],
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        },
        "scenarios": [
            scenario(
                "normal_flow",
                "정상 흐름 중심",
                "202605",
                "정상 흐름 중심 시나리오입니다. 대부분 연결이 안정 범위이며 일부 허브 유통사만 관찰 대상으로 표시됩니다.",
                g1,
                "C 유통",
            ),
            scenario(
                "delay_focus",
                "지연·허브 집중",
                "202605",
                "유통 허브 집중이 강화된 시나리오입니다. AI 점수 상위 유통사를 중심으로 연결망을 탐색할 수 있습니다.",
                g2,
                "B 유통",
            ),
            scenario(
                "price_focus",
                "가격·연결 이상",
                "202606",
                "연결 구조는 유지되지만 AI 점수가 높은 유통사가 늘어난 시나리오입니다.",
                g3,
                "E 유통",
            ),
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    for s in payload["scenarios"]:
        g = s["network"]["graph"]
        print(f"  {s['id']}: {len(g['nodes'])} nodes, {len(g['edges'])} edges")


if __name__ == "__main__":
    main()
