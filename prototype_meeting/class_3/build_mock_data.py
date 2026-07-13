"""Generate synthetic Class 3 cohort-dashboard meeting data."""
from __future__ import annotations

import json
import random
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "data" / "mock_data.json"
MONTHS = ["2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05"]
BUSINESS_TYPES = [
    "제조업체",
    "수입업체",
    "판매·임대업체",
    "의료기관",
    "약국·의약품도매상",
    "기타 관련기관",
]
REGIONS = ["수도권", "충청권", "호남권", "영남권", "강원권", "제주권"]
DEVICE_TAXONOMY = [
    {
        "group": "A. 일반 의료기기",
        "items": [
            "A1. 기구/기계",
            "A2. 의료용품",
            "A3. 치과재료",
        ],
    },
    {
        "group": "B. 체외진단",
        "items": [
            "B1. 검체전처리기기",
            "B2. 임상화학검사기기",
            "B3. 면역검사기기",
            "B4. 수혈의학검사기기",
            "B5. 임상미생물검사기기",
            "B6. 분자진단기기",
            "B7. 조직병리검사기기",
        ],
    },
    {
        "group": "C. 디지털 의료기기",
        "items": ["C. 디지털 의료기기"],
    },
]
PRODUCTS = [item for group in DEVICE_TAXONOMY for item in group["items"]]


def _series(rng: random.Random, start: int, monthly_growth: float) -> list[dict]:
    values = []
    current = float(start)
    for month in MONTHS:
        current *= 1 + monthly_growth + rng.uniform(-0.035, 0.035)
        peer = current * rng.uniform(0.91, 1.05)
        values.append(
            {
                "month": month,
                "profileAverage": round(current),
                "peerMedian": round(peer),
            }
        )
    return values


def _opportunities(rng: random.Random, focus_index: int) -> list[dict]:
    records = []
    for index, product in enumerate(PRODUCTS):
        growth = rng.uniform(-9, 22)
        if index == focus_index:
            growth += 8
        hhi = rng.uniform(0.08, 0.43)
        records.append(
            {
                "product": product,
                "growthPct": round(growth, 1),
                "hhi": round(hhi, 2),
                "supplierCount": rng.randint(8, 62),
                "scaleBand": rng.choice(["중", "중", "대", "소"]),
            }
        )
    return records


def build_payload(seed: int = 3032026) -> dict:
    scenarios = {}
    for index, business_type in enumerate(BUSINESS_TYPES):
        rng = random.Random(seed + index * 97)
        focus_index = index % len(PRODUCTS)
        scenarios[business_type] = {
            "baseCohortCount": rng.randint(42, 126),
            "transactionSeries": _series(
                rng,
                start=rng.randint(4200, 9800),
                monthly_growth=rng.uniform(-0.005, 0.045),
            ),
            "metrics": [
                {
                    "label": "거래 활동 변화",
                    "value": f"{rng.uniform(3, 18):+.1f}%",
                    "position": rng.choice(["상위 25%", "중간 50%", "중간 50%"]),
                    "definition": "최근 3개월 거래 보고 횟수의 이전 기간 대비 변화",
                },
                {
                    "label": "취급 품목 폭",
                    "value": f"{rng.randint(4, 12)}개 군",
                    "position": rng.choice(["상위 25%", "중간 50%"]),
                    "definition": "기업군에서 활동이 확인된 품목군 수",
                },
                {
                    "label": "거래처 유형 폭",
                    "value": f"{rng.randint(2, 5)}개 유형",
                    "position": rng.choice(["중간 50%", "상위 25%"]),
                    "definition": "제조·유통·의료기관 등 거래처 유형 수",
                },
                {
                    "label": "공급 수량 방향",
                    "value": rng.choice(["증가", "완만한 증가", "보합"]),
                    "position": rng.choice(["상위 25%", "중간 50%"]),
                    "definition": "최근 3개월 총 공급 수량 방향",
                },
            ],
            "opportunities": _opportunities(rng, focus_index),
            "similarGroups": [
                {
                    "name": f"{PRODUCTS[focus_index]} 중심 성장형",
                    "share": rng.randint(24, 38),
                    "description": "선택 품목 비중과 최근 거래 활동이 함께 증가한 기업군",
                    "traits": ["품목 집중도 높음", "거래 활동 증가", "의료기관 공급 비중 중간"],
                },
                {
                    "name": "다품목 안정 거래형",
                    "share": rng.randint(20, 31),
                    "description": "여러 품목군을 취급하며 월별 변화가 크지 않은 기업군",
                    "traits": ["품목 폭 넓음", "변동성 낮음", "거래처 유형 다양"],
                },
                {
                    "name": "지역 거래처 집중형",
                    "share": rng.randint(15, 25),
                    "description": "선택 권역 내 거래처 비중이 상대적으로 높은 기업군",
                    "traits": ["권역 비중 높음", "거래처 폭 좁음", "수량 보합"],
                },
            ],
        }

    return {
        "meta": {
            "title": "Class 3 우리 기업군 동향",
            "synthetic": True,
            "period": "2025-12~2026-05",
            "sourceLabel": "간담회용 생성 데이터",
        },
        "profileOptions": {
            "businessTypes": BUSINESS_TYPES,
            "regions": REGIONS,
            "deviceTaxonomy": DEVICE_TAXONOMY,
            "productGroups": PRODUCTS,
        },
        "scenarios": scenarios,
        "privacy": {
            "cohortFloor": 5,
            "hiddenFields": [
                "업체명과 대표자명",
                "사업자·업허가번호",
                "정확한 업체별 거래금액과 순위",
                "개별 거래처와 유통 경로",
                "상세 주소와 의료기관 식별코드",
            ],
            "message": "개별 업체를 찾는 대신 조건이 비슷한 기업군의 집계 결과만 보여줍니다.",
        },
        "limitations": [
            "현재 화면은 생성된 예시 데이터로 기능과 이해도를 확인하기 위한 시안입니다.",
            "기업군 분석과 공개 기준은 실제 전체 데이터 검증과 개인정보·영업비밀 검토 후 확정해야 합니다.",
            "성장과 집중도는 확인할 시장을 찾는 지표이며 수요 예측이나 투자 권고가 아닙니다.",
            "비슷한 기업군 유형은 실제 구현에서 군집 분석 결과를 검증한 뒤 이름과 설명을 부여합니다.",
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
    print(f"  business scenarios: {len(payload['scenarios'])}")


if __name__ == "__main__":
    main()
