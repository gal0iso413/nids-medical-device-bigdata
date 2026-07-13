"""Generate synthetic Class 1 meeting data.

The output is intentionally generated from fictional entities and plausible
distributions. It does not transform or sample the operational workbooks.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "data" / "mock_data.json"
MONTHS = [
    "202510",
    "202511",
    "202512",
    "202601",
    "202602",
    "202603",
    "202604",
    "202605",
]
ITEMS = [
    "심혈관용 카테터",
    "일회용 주사기",
    "정형용 임플란트",
    "체외진단 시약",
    "환자감시장치",
    "창상피복재",
]


def _node(entity_id: str, name: str, entity_type: str) -> dict:
    return {
        "id": entity_id,
        "name": name,
        "type": entity_type,
    }


def build_payload(seed: int = 20260713) -> dict:
    rng = random.Random(seed)
    nodes = [
        *[_node(f"M{i:02d}", f"{chr(64 + i)} 제조", "제조사") for i in range(1, 9)],
        *[_node(f"I{i:02d}", f"{chr(72 + i)} 수입", "수입사") for i in range(1, 4)],
        *[_node(f"D{i:02d}", f"{chr(64 + i)} 유통", "유통사") for i in range(1, 15)],
        *[_node(f"H{i:02d}", f"{chr(64 + i)} 의료기관", "의료기관") for i in range(1, 21)],
    ]
    manufacturers = [node["id"] for node in nodes if node["type"] in {"제조사", "수입사"}]
    distributors = [node["id"] for node in nodes if node["type"] == "유통사"]
    hospitals = [node["id"] for node in nodes if node["type"] == "의료기관"]
    hub_id = "D03"
    edges: list[dict] = []

    def add_edge(src: str, dst: str, item: str, base_count: int, base_qty: int) -> None:
        monthly = {}
        for index, month in enumerate(MONTHS):
            drift = 1 + (index - 2) * rng.uniform(-0.04, 0.10)
            if src == hub_id or dst == hub_id:
                drift += index * 0.07
            monthly[month] = {
                "count": max(1, round(base_count * drift + rng.uniform(-2, 2))),
                "quantity": max(10, round(base_qty * drift + rng.uniform(-35, 35))),
            }
        edges.append(
            {
                "id": f"E{len(edges) + 1:03d}",
                "src": src,
                "dst": dst,
                "item": item,
                "monthly": monthly,
            }
        )

    for index, hospital in enumerate(hospitals):
        distributor = distributors[index % len(distributors)]
        source = manufacturers[index % len(manufacturers)]
        item = ITEMS[index % len(ITEMS)]
        add_edge(source, distributor, item, rng.randint(5, 14), rng.randint(180, 620))
        add_edge(distributor, hospital, item, rng.randint(6, 18), rng.randint(140, 550))

    for source in manufacturers:
        add_edge(source, hub_id, rng.choice(ITEMS), rng.randint(12, 24), rng.randint(450, 950))
    for hospital in hospitals[:14]:
        add_edge(hub_id, hospital, rng.choice(ITEMS), rng.randint(10, 23), rng.randint(350, 880))

    # Fictional multi-stage paths make the two-hop view and PDI explanation useful.
    for src, dst in [("D03", "D08"), ("D08", "D11"), ("D02", "D09"), ("D06", "D12")]:
        add_edge(src, dst, rng.choice(ITEMS), rng.randint(4, 9), rng.randint(90, 260))

    for _ in range(22):
        add_edge(
            rng.choice(manufacturers),
            rng.choice(distributors),
            rng.choice(ITEMS),
            rng.randint(3, 11),
            rng.randint(100, 480),
        )

    degree = Counter()
    for edge in edges:
        degree[edge["src"]] += 1
        degree[edge["dst"]] += 1

    for node in nodes:
        centrality = min(100, round(degree[node["id"]] / max(degree.values()) * 100))
        if node["type"] == "유통사":
            base_score = 22 + centrality * 0.55 + rng.uniform(-7, 8)
        else:
            base_score = 10 + centrality * 0.25 + rng.uniform(-4, 5)
        if node["id"] in {"D03", "D08", "D11"}:
            base_score += 12
        gnn_score = max(4, min(96, round(base_score)))
        node["degree"] = degree[node["id"]]
        node["gnnScore"] = gnn_score
        node["status"] = "우선 확인" if gnn_score >= 75 else ("관찰" if gnn_score >= 50 else "일반")
        node["observedFact"] = (
            f"최근 3개월 연결 {node['degree']}개, "
            f"{'다단계 유통 경로가 포함된' if node['id'] in {'D03', 'D08', 'D11'} else '직접·단일 단계 연결이 주를 이루는'} "
            f"거래 패턴입니다."
        )
        node["modelInterpretation"] = (
            "비슷한 역할의 유통업체와 비교해 연결 구조가 다르게 나타나 GNN 점수가 높게 산출된 예시입니다. "
            "속성별 기여도(XAI)는 제공되지 않습니다."
        )
        node["reviewQuestion"] = (
            "점수가 높은 연결 변화가 정상적인 계약·경로 변경인지, 추가 확인이 필요한 패턴인지 검토해 보시겠습니까?"
        )

    review_order = sorted(
        (node for node in nodes if node["type"] == "유통사"),
        key=lambda node: node["gnnScore"],
        reverse=True,
    )
    my_company_id = hub_id

    return {
        "meta": {
            "title": "Class 1 유통 관계 확인",
            "synthetic": True,
            "sourceLabel": "간담회용 생성 데이터",
            "myCompanyId": my_company_id,
            "myCompanyName": next(node["name"] for node in nodes if node["id"] == my_company_id),
            "anchors": [
                {"value": "202603", "label": "2026년 1~3월"},
                {"value": "202604", "label": "2026년 2~4월"},
                {"value": "202605", "label": "2026년 3~5월"},
            ],
            "availableMonths": MONTHS,
        },
        "nodes": nodes,
        "edges": edges,
        "reviewOrder": [node["id"] for node in review_order],
        "limitations": [
            "실제 데이터에서는 의료기관 식별코드가 비어 있는 거래가 있어 일부 경로가 완전하지 않을 수 있습니다.",
            "확인 필요 업체 순서는 GNN 점수만 사용하며, BC·가격·시차 등 개별 지표는 Model 1 화면에 표시하지 않습니다.",
            "GNN 점수는 위법 가능성이나 확률이 아니라 확인 우선순위이며, 속성별 근거 문장(XAI)은 제공되지 않습니다.",
        ],
    }


def main() -> None:
    payload = build_payload()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT}")
    print(f"  nodes: {len(payload['nodes'])}")
    print(f"  edges: {len(payload['edges'])}")


if __name__ == "__main__":
    main()
