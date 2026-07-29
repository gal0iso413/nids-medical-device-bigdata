"""Generate synthetic Class 3 cohort-dashboard meeting data."""
from __future__ import annotations

import json
import random
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "data" / "mock_data.json"
MONTHS = ["2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05"]
BUSINESS_TYPES = [
    "제조업",
    "수입업",
    "판매(임대)업",
    "의료기관",
    "기타",
]
REGIONS = ["수도권", "비수도권", "전국"]
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

# Facilitator-stable sparse demos (region × 업종), independent of scenario payload.
DATA_QUALITY_RULES = [
    {
        "businessType": "기타",
        "region": "비수도권",
        "dataStatus": "suppressed",
        "historyMonths": 0,
    },
    {
        "businessType": "기타",
        "region": "수도권",
        "dataStatus": "thinHistory",
        "historyMonths": 2,
    },
]

# top7-style 품목명 exemplars + coverage fillers (item name ≠ 품목군).
DEVICE_ITEM_SEEDS = [
    {
        "name": "국소 폼제 창상 피복재",
        "productGroup": "A2. 의료용품",
        "suggestTags": ["창상", "피복재", "폼제", "드레싱"],
    },
    {
        "name": "비가열식 흡입기",
        "productGroup": "A1. 기구/기계",
        "suggestTags": ["흡입기", "호흡", "기구"],
    },
    {
        "name": "비흡수성체내용스태플",
        "productGroup": "A1. 기구/기계",
        "suggestTags": ["스태플", "체내용", "수술"],
    },
    {
        "name": "생체재질인공심장판막",
        "productGroup": "A1. 기구/기계",
        "suggestTags": ["심장판막", "이식", "인공"],
    },
    {
        "name": "의료기구용 클립",
        "productGroup": "A1. 기구/기계",
        "suggestTags": ["클립", "기구", "지혈"],
    },
    {
        "name": "이식형의약품주입기",
        "productGroup": "A1. 기구/기계",
        "suggestTags": ["주입기", "이식형", "펌프"],
    },
    {
        "name": "체외형 범용 프로브",
        "productGroup": "B2. 임상화학검사기기",
        "suggestTags": ["프로브", "체외", "검사", "임상화학"],
    },
    {
        "name": "치과용 복합레진",
        "productGroup": "A3. 치과재료",
        "suggestTags": ["치과", "레진", "충전"],
    },
    {
        "name": "자동 검체분주기",
        "productGroup": "B1. 검체전처리기기",
        "suggestTags": ["검체", "분주", "전처리"],
    },
    {
        "name": "면역형광 분석시약 카트리지",
        "productGroup": "B3. 면역검사기기",
        "suggestTags": ["면역", "형광", "카트리지"],
    },
    {
        "name": "혈액형 판정 카드",
        "productGroup": "B4. 수혈의학검사기기",
        "suggestTags": ["혈액형", "수혈", "카드"],
    },
    {
        "name": "미생물 배양 모니터링 모듈",
        "productGroup": "B5. 임상미생물검사기기",
        "suggestTags": ["미생물", "배양", "모듈"],
    },
    {
        "name": "핵산증폭 검사 키트",
        "productGroup": "B6. 분자진단기기",
        "suggestTags": ["핵산", "증폭", "분자진단"],
    },
    {
        "name": "조직슬라이드 스캐너",
        "productGroup": "B7. 조직병리검사기기",
        "suggestTags": ["조직", "슬라이드", "병리"],
    },
    {
        "name": "원격 환자모니터링 소프트웨어",
        "productGroup": "C. 디지털 의료기기",
        "suggestTags": ["원격", "모니터링", "소프트웨어", "디지털"],
    },
]


def _series(
    rng: random.Random,
    start: int,
    monthly_growth: float,
    months: list[str] | None = None,
    value_key: str = "profileAverage",
    peer_key: str = "peerMedian",
) -> list[dict]:
    values = []
    current = float(start)
    for month in months or MONTHS:
        current *= 1 + monthly_growth + rng.uniform(-0.035, 0.035)
        peer = current * rng.uniform(0.91, 1.05)
        values.append(
            {
                "month": month,
                value_key: round(current),
                peer_key: round(peer),
            }
        )
    return values


def _item_series(rng: random.Random, start: int, monthly_growth: float) -> list[dict]:
    values = []
    current = float(start)
    for month in MONTHS:
        current *= 1 + monthly_growth + rng.uniform(-0.04, 0.04)
        group_avg = current * rng.uniform(0.85, 1.2)
        values.append(
            {
                "month": month,
                "itemAverage": round(current),
                "groupAverage": round(group_avg),
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
            }
        )
    return records


def _concentration_label(hhi: float) -> str:
    if hhi > 0.25:
        return "높음"
    if hhi > 0.15:
        return "보통"
    return "낮음"


def _supplier_band(count: int) -> str:
    lower = (count // 10) * 10
    return f"{max(1, lower)}~{lower + 9}개"


def _device_items(seed: int) -> list[dict]:
    items = []
    for index, seed_row in enumerate(DEVICE_ITEM_SEEDS):
        rng = random.Random(seed + 1700 + index * 41)
        growth = round(rng.uniform(-8, 24), 1)
        hhi = round(rng.uniform(0.09, 0.42), 2)
        supplier_count = rng.randint(6, 48)
        share_of_group = rng.randint(8, 42)
        flags = {
            "traceableShare": rng.choice(["낮음", "중간", "높음"]),
            "implantableShare": rng.choice(["해당 없음", "낮음", "중간", "높음"]),
            "singleUseShare": rng.choice(["낮음", "중간", "높음"]),
            "reimbursementShare": rng.choice(["낮음", "중간", "높음"]),
            "classMode": rng.choice(["1·2등급 중심", "3등급 비중 큼", "4등급 비중 있음"]),
        }
        items.append(
            {
                "name": seed_row["name"],
                "productGroup": seed_row["productGroup"],
                "suggestTags": seed_row["suggestTags"],
                "stats": {
                    "growthPct": growth,
                    "hhi": hhi,
                    "concentrationBand": _concentration_label(hhi),
                    "supplierCount": supplier_count,
                    "supplierCountBand": _supplier_band(supplier_count),
                    "shareOfGroupPct": share_of_group,
                    "quantityDirection": rng.choice(["증가", "완만한 증가", "보합", "감소"]),
                    "receiverMix": {
                        "의료기관": rng.randint(40, 75),
                        "판매(임대)": rng.randint(10, 35),
                        "기타": rng.randint(5, 20),
                    },
                    "activitySeries": _item_series(
                        rng,
                        start=rng.randint(800, 3200),
                        monthly_growth=rng.uniform(-0.01, 0.05),
                    ),
                },
                "flagPrevalence": flags,
            }
        )
    return items


def build_payload(seed: int = 3032026) -> dict:
    scenarios = {}
    for index, business_type in enumerate(BUSINESS_TYPES):
        rng = random.Random(seed + index * 97)
        focus_index = index % len(PRODUCTS)
        scenarios[business_type] = {
            "baseCohortCount": rng.randint(42, 126),
            "dataStatus": "ok",
            "historyMonths": len(MONTHS),
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
                    "value": f"{rng.randint(28, 86)}개",
                    "position": rng.choice(["상위 25%", "중간 50%"]),
                    "definition": "기업군에서 활동이 확인된 고유 품목명 수",
                },
                {
                    "label": "거래처 폭",
                    "value": f"{rng.randint(18, 72)}개",
                    "position": rng.choice(["중간 50%", "상위 25%"]),
                    "definition": "기업군에서 거래가 확인된 고유 거래처(상대 업체) 수",
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
                    "traits": ["품목명 폭 넓음", "변동성 낮음", "거래처 수 많음"],
                },
                {
                    "name": "지역 거래처 집중형",
                    "share": rng.randint(15, 25),
                    "description": "선택 권역 내 거래처 비중이 상대적으로 높은 기업군",
                    "traits": ["권역 비중 높음", "거래처 폭 좁음", "수량 보합"],
                },
            ],
        }

    # Short series payload for thin-history demo (기타 + 수도권).
    thin_rng = random.Random(seed + 909)
    scenarios["기타"]["thinHistorySeries"] = _series(
        thin_rng,
        start=thin_rng.randint(2800, 4200),
        monthly_growth=thin_rng.uniform(-0.01, 0.02),
        months=MONTHS[-2:],
    )

    device_items = _device_items(seed)

    return {
        "meta": {
            "title": "Class 3 우리 기업군 동향",
            "synthetic": True,
            "period": "2025-12~2026-05",
            "sourceLabel": "간담회용 생성 데이터",
            "journey": "firm-first-then-device-sequel",
        },
        "profileOptions": {
            "businessTypes": BUSINESS_TYPES,
            "regions": REGIONS,
            "deviceTaxonomy": DEVICE_TAXONOMY,
            "productGroups": PRODUCTS,
        },
        "dataQualityRules": DATA_QUALITY_RULES,
        "scenarios": scenarios,
        "deviceItems": device_items,
        "privacy": {
            "cohortFloor": 5,
            "hiddenFields": [
                "업체명과 대표자명",
                "사업자·업허가번호",
                "정확한 업체별 거래금액과 순위",
                "개별 거래처와 유통 경로",
                "상세 주소와 의료기관 식별코드",
                "품목 허가·UDI·모델 목록(색인형 조회)",
            ],
            "message": "개별 업체를 찾는 대신 선택한 조건의 해당 기업군·품목명 집계 통계만 보여줍니다. 품목 색인(index) 조회가 아닙니다.",
        },
        "limitations": [
            "현재 화면은 생성된 예시 데이터로 기능과 이해도를 확인하기 위한 시안입니다.",
            "기업군 분석과 공개 기준은 실제 전체 데이터 검증과 개인정보·영업비밀 검토 후 확정해야 합니다.",
            "성장과 집중도는 확인할 시장을 찾는 지표이며 수요 예측이나 투자 권고가 아닙니다.",
            "품목군(분류)과 품목명(개별 품목)은 다릅니다. 기업군 단계에서는 품목군, 의료기기 이어보기에서는 품목명을 사용합니다.",
            "의료기기 화면은 집계 통계·진단이며 품목 등록정보 색인이 아닙니다.",
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
    print(f"  data quality rules: {len(payload['dataQualityRules'])}")
    print(f"  device items: {len(payload['deviceItems'])}")


if __name__ == "__main__":
    main()
