# Class 1 GAD-NR 특징 계약

> 상태: 승인된 모델·특징 기준선
> 기준일: 2026-08-11
> 결정: GAD-NR를 Class 1 주 모델로 사용하되, 현재 구현은 아직 그 상태가 아니다.

## 결정 표기

이 문서는 **Confirmed fact**, **Locked decision**, **Proposed decision**, **Decision required**, **Implementation risk**를 구분한다.

## 코드 대조 결과

- **Confirmed fact** — [`class_1_anomaly_detection/README.md`](../../class_1_anomaly_detection/README.md)는 DOMINANT와 GAD-NR 실행을 함께 권장한다.
- **Confirmed fact** — [`run_pygod_compare.py`](../../class_1_anomaly_detection/src/experiments/run_pygod_compare.py)는 기본값으로 DOMINANT, AnomalyDAE, GAD-NR, OCGNN, IsoForest 다섯 모델을 실행한다.
- **Confirmed fact** — [`run_step4_evaluation.py`](../../class_1_anomaly_detection/src/experiments/run_step4_evaluation.py)는 BC와 약한 기준의 일치도를 합성해 앵커마다 `recommended_model`을 동적으로 선택한다.
- **Confirmed fact** — 기본 `contamination=0.1`이며, 점수 상위 10%를 라벨 1로 만드는 상대 라벨을 생성한다. 실제 이상 비율이 10%라는 근거는 저장소에 없다.
- **Confirmed fact** — [`export_pyg_graph.py`](../../class_1_anomaly_detection/src/experiments/export_pyg_graph.py)의 `data.x`에는 BC, 가격 flag/z-score, 시간 단차가 포함된다.
- **Confirmed fact** — `edge_attr`에는 정제 금액, 거래 건수, UDI 수, 규제 플래그 등이 저장되지만 현재 학습 호출은 PyGOD 모델에 `Data`를 전달할 뿐 edge-aware 사용자 모델이나 `edge_weight` 전달 계약은 없다. 현재 사용 중인 PyGOD GAD-NR 경로는 `x`와 `edge_index`를 forward에 전달하므로 `edge_attr`의 값은 GAD-NR 메시지 패싱에 직접 반영되지 않는다. 공식 소스: <https://docs.pygod.org/en/latest/_modules/pygod/detector/gadnr.html>.
- **Confirmed fact** — 저장소는 GAD-NR를 `num_layers=1`로 만들고 `batch_size`를 지정하지 않는다. PyGOD 1.1.0 기본값은 `batch_size=0`(full batch)이므로 선택 앵커의 전체 그래프를 학습 대상으로 사용하되 한 층의 직접 메시지 범위는 주로 1-hop이다. UI의 1-hop/2-hop 선택과 모델 학습 범위는 별개다.
- **Confirmed fact** — 현재 GNN `edge_index`는 `업체쌍×제품 3-key` 복수간선이다. BC만 별도 `collapse_to_digraph`에서 업체쌍으로 접는다.
- **Confirmed fact** — `in_degree`/`out_degree`도 제품 복수간선 행을 누적하므로 고유 거래처 수가 아니라 제품 간선 수에 가까워질 수 있다.
- **Confirmed fact** — 현재 Streamlit UI는 다섯 모델을 선택할 수 있고 원시 모델 점수·rank·상위 10% 라벨을 직접 노출한다.

## 주 모델과 평가 역할

- **Locked decision** — 주 모델은 GAD-NR다.
- **Locked decision** — DOMINANT는 오프라인 비교와 회귀 테스트에만 사용한다.
- **Locked decision** — AnomalyDAE, OCGNN, IsoForest는 연구용 후보이며 정식 UI 선택지에 노출하지 않는다.
- **Locked decision** — 고정 contamination 라벨을 `정상/이상` 판정으로 서비스하지 않는다.
- **Locked decision** — 모델 선택을 BC 일치도만으로 동적으로 바꾸지 않는다. GAD-NR 변경의 평가는 앵커 안정성, 합성 이상 주입, 수작업 검토 표본, 역할군 top-K 재현성, DOMINANT 회귀 비교로 구성한다.
- **Implementation risk** — BC가 GAD-NR 입력에도 있고 모델 추천 점수에도 들어가 현재 평가가 순환적이다.

## 모델 입력 특징

### 포함

| 특징군 | 최소 특징 | 상태 |
|---|---|---|
| 구조 | 고유 in/out 거래처 수, 업체쌍 간선 수, 품목 다양성 | **Locked decision** |
| 역할 | 제조·수입·유통·의료기관·기타 one-hot/embedding | **Locked decision** |
| 지역 | 광역 공급자·수령자 지역, 결측 indicator | **Locked decision** |
| 거래 건수 | `in_tx_log`, `out_tx_log`, `tx_per_counterparty` | **Locked decision** |
| 금액 | `in_amount_clean_log`, `out_amount_clean_log`, 유효률 | **Locked decision** |
| 원본 수량 | `in_raw_supply_qty_log`, `out_raw_supply_qty_log` | **Locked decision** |
| 낱개 수량 | `in_piece_qty_log`, `out_piece_qty_log`, `piece_qty_per_tx_log` | **Locked decision**, 공식 검증 필요 |
| 상대 위치 | 품목군 내 수량 percentile 또는 robust z-score | **Proposed decision** |
| 지속성 | 활성 월 수, 신규/소실 거래처 수 | **Locked decision** |

### 제외하고 보조증거로 유지

- **Locked decision** — BC
- **Locked decision** — 가격 robust z-score와 가격 flag rate
- **Locked decision** — 공급일자와 최초접수일자의 시간 단차
- **Locked decision** — HHI와 PDI

이 네 계열은 GAD-NR의 독립 설명·검증 근거로 사용할 수 있도록 `data.x`에서 제거한다.

## 금액·건수·수량 계약

- **Locked decision** — 공급금액, 거래 건수, 공급 수량은 서로 다른 특징이다. 서로 더하거나 하나의 `weight`로 합치지 않는다.
- **Locked decision** — `amount_sum_clean`, `tx_count`, `raw_supply_qty_sum`, `piece_qty_sum`을 원 단위로 보존하고, 모델에는 로그·정규화 파생값을 별도로 넣는다.
- **Locked decision** — 가격 바코드형 극단값 대체 여부와 금액 유효률을 함께 저장한다.
- **Decision required** — 낱개 수량의 표준식과 예외 처리. 기본 후보는 `공급수량 × 포장내 총 수량`이나 반품·회수, 부분 낱개 회수, 결측 포장단위를 검토해야 한다.
- **Implementation risk** — 현재 `COL_SUPPLY_QTY`는 금액 대체 계산에만 사용되고 그래프·GNN 수량 특징으로 집계되지 않는다.

## 그래프 계약

### 모델 그래프

- **Locked decision** — 한 앵커의 기본 기간은 최근 3개월이다.
- **Locked decision** — 노드는 안정 업체 ID다.
- **Locked decision** — 방향성 간선은 `(src_company_id, dst_company_id)`당 1개다.
- **Locked decision** — 업체쌍 간선 속성은 금액·수량·건수·고유 품목 수를 분리 보존하지만, 1차 GAD-NR는 노드 집계 특징과 `edge_index`만 사용한다.
- **Locked decision** — 제품 수는 `unique_product_count`로 노드·업체쌍 특징에 보존한다.
- **Proposed decision** — edge-aware GAD-NR 변형은 별도 연구 PR에서만 검토한다. 주 모델 계약 변경으로 취급한다.

### UI 사실 데이터

- **Locked decision** — UI용 품목 세부는 모델 그래프와 분리된 `업체×거래처×품목×월` 사실 테이블에서 조회한다.
- **Locked decision** — 업체쌍의 주요 품목은 고정 문자열로 저장하지 않고 요청 기간·정렬 기준으로 상위 1~3개를 계산한다.
- **Locked decision** — 서로 다른 품목의 원시 수량을 의미 없이 합산하지 않는다. 품목별 비중 또는 정규화 수량으로 표현한다.

## 점수·표현 계약

- **Locked decision** — 화면 명칭은 `이상 확률`이나 `AI 이상 점수`가 아니라 **검토 우선순위**다.
- **Locked decision** — 외부 표시값은 동일 앵커·동일 역할군 내 GAD-NR 백분위다.
- **Locked decision** — `최초 선택 업체`를 관계 탐색의 기준점 명칭으로 사용한다.
- **Locked decision** — 원시 GAD-NR 점수는 모델 QA 산출물에만 저장하고 일반 내부 화면 기본값으로 노출하지 않는다.
- **Locked decision** — 역할군 표본이 최소 기준을 충족하지 못하면 백분위 대신 `판단 유보`를 반환한다.
- **Decision required** — 역할군 정의와 최소 표본 수. 제조/수입을 합칠지, 다중 역할 업체를 어느 군에 둘지 확정해야 한다.

권장 출력 계약:

```json
{
  "entity_id": "internal-id",
  "anchor_month": "202605",
  "window_months": ["202603", "202604", "202605"],
  "model": "gadnr",
  "model_version": "required",
  "role_group": "distributor",
  "role_group_sample_size": 412,
  "review_priority_percentile": 98.2,
  "review_band": "priority",
  "insufficient_sample": false
}
```

## 보조지표 계약

### BC

- **Confirmed fact** — 현재 BC는 제조·수입(또는 in-degree 0)을 source, 의료기관을 target으로 하는 normalized subset BC이며, 거래 건수가 많을수록 짧아지는 `bc_distance`를 쓴다.
- **Confirmed fact** — 생산 의료기관 코드 결측률은 54.6%여서 target 경로가 불완전하다.
- **Confirmed fact** — 현재 저장 전에 8자리 반올림하고, 전체 노드 p95에 대해 `>=`를 적용한다. p95가 0이면 0인 노드까지 대량 high-risk가 된다.
- **Locked decision** — 원시 BC는 반올림하지 않고 저장하며 화면에서만 포맷한다.
- **Locked decision** — 기본 표시는 유통업체 역할군 내 BC 백분위·순위다. 낮은 원시 값 자체를 오류로 간주하지 않는다.
- **Locked decision** — `reachable_source_target_pairs`, `gateway_share`, `weak_component_size`, `reachable_target_count`를 함께 저장한다.
- **Locked decision** — 도달 경로가 없거나 표본이 작으면 `판단 유보`다.
- **Locked decision** — p95가 0이거나 비영(非零) 표본이 최소 기준 미만이면 high-risk band를 생성하지 않는다.
- **Proposed decision** — 전체 BC와 품목군별 BC, unweighted/거래건수 거리/정규화 수량 거리의 top-K 안정성을 오프라인에서 비교한다.

### 가격 z-score와 시간 단차

- **Locked decision** — 두 지표는 GAD-NR 입력에서 제외한 독립 보조증거다.
- **Locked decision** — 최소 유효 표본과 유효률을 통과할 때만 요약·확인 질문을 만든다.
- **Locked decision** — 가격은 동일 품목·공급형태 비교군과 정제 규칙 버전을 함께 표시한다.

### HHI와 PDI

- **Locked decision** — HHI는 Class 1 핵심 네트워크 지표에서 후순위화한다. 시장 단위가 명확한 Class 3 품목별 보조지표에서만 우선 검토한다.
- **Locked decision** — PDI는 의료기관 끝단 누락으로 경로가 잘릴 수 있으므로 Class 1 상세 보조지표로 둔다.
- **Locked decision** — `최종 경로`라는 표현을 금지하고 `관측된 경로`와 endpoint coverage를 함께 표시한다.

## 시간 비교 계약

서로 다른 두 비교를 API·UI에서 같은 `previous`로 부르지 않는다.

| 이름 | 현재 창 | 비교 창 | 용도 |
|---|---|---|---|
| `previous_anchor_diff` | 앵커 M의 `[M-2,M-1,M]` | 앵커 M-1의 `[M-3,M-2,M-1]` | 신규·소실 거래처, 새로 들어온 달/빠진 달 변화 |
| `prior_nonoverlap_3m_diff` | `[M-2,M-1,M]` | `[M-5,M-4,M-3]` | 거래 건수·금액·수량·품목 수·상대 업체 수 추세 |

- **Locked decision** — 신규·소실 관계는 `previous_anchor_diff`를 기본으로 한다.
- **Locked decision** — 규모·구성 추세는 `prior_nonoverlap_3m_diff`를 기본으로 한다.
- **Locked decision** — GAD-NR 원시 점수 차이는 서비스하지 않는다.
- **Proposed decision** — 역할군 백분위 차이는 모델 버전·역할군 정의가 동일하고 안정성 시험을 통과한 경우에만 제공한다.

## 대상 파일과 구현 단계

| 단계 | 현재 대상 | 향후 대상(제안) | 입력 | 출력 |
|---|---|---|---|---|
| C1-1 공통 집계 | `src/ingest/keys.py`, `src/graph/build_network.py` | `data_pipeline/contracts`, `data_pipeline/aggregates` | 정제 월별 행 | 공통 월 사실 테이블 |
| C1-2 그래프 분리 | `build_network.py`, `export_pyg_graph.py` | `class_1.../src/graph/model_graph.py`, `ui_product_facts.py` | 월 사실 테이블 | 업체쌍 모델 그래프, UI 품목 사실 |
| C1-3 특징 계약 | `export_pyg_graph.py` | `features/gadnr_features.py` | 업체쌍 그래프 | BC/가격/시차 제외 `x`, 특징 manifest |
| C1-4 주 모델 | `run_pygod_compare.py`, `run_step4_evaluation.py` | `models/run_gadnr.py`, `evaluation/` | 버전된 그래프 | GAD-NR 원점수, 역할군 백분위, QA 비교 |
| C1-5 BC 개선 | `metrics_bc.py` | 동일 파일 또는 `metrics/bc_evidence.py` | 업체쌍 그래프 | BC 백분위·reachable 계약 |
| C1-6 diff | 없음 | `aggregates/anchor_diff.py` | 월 사실 테이블 | 두 종류 diff |

경로 신설은 **Proposed decision**이며 실제 PR에서 저장소 구조에 맞춰 확정한다.

## 테스트와 완료 조건

### 계약 테스트

- 같은 업체쌍에 여러 제품이 있어도 모델 `edge_index`는 방향당 1개다.
- 고유 거래처 수와 제품 간선 수가 별도 값으로 검증된다.
- 금액·거래 건수·원본 수량·낱개 수량이 합성되지 않는다.
- 특징 manifest에 BC, 가격 z-score, 시간 단차, HHI, PDI가 없다.
- `edge_attr`만 바꾼 기존 GAD-NR 결과가 바뀌지 않는 현재 동작을 회귀 증거로 남기고, 향후 edge-aware 모델은 별도 테스트로 구분한다.
- p95=0 fixture에서 모든 노드가 high-risk가 되지 않는다.
- 도달 가능한 source-target 쌍이 0인 fixture는 `판단 유보`다.
- 두 diff가 겹치는 창과 비중첩 창을 정확히 사용한다.

### 모델 완료 조건

- GAD-NR가 유일한 서비스 `primary_model`로 manifest에 기록된다.
- DOMINANT 비교 결과는 QA 보고서에만 존재한다.
- 역할군별 백분위가 동점·소표본 정책을 따른다.
- 금액-only, 수량-only, 금액+수량 ablation 결과와 앵커 top-K 안정성이 기록된다.
- 합성 이상 주입과 수작업 검토 표본 평가가 없으면 모델 계약을 production-ready로 표시하지 않는다.
- 기존 점수와 새 점수는 특징 버전이 달라 직접 비교하지 않으며, 마이그레이션 보고서로만 병렬 관찰한다.

## 남은 결정

1. **Decision required** — 역할군 정의, 다중 역할 업체 처리, 최소 표본 수.
2. **Decision required** — 낱개 수량 공식과 반품·회수 부호 규칙.
3. **Decision required** — 검토 우선순위 band 경계와 동점 처리.
4. **Decision required** — BC gateway share의 정확한 분모와 최소 reachable pair 수.
5. **Decision required** — GAD-NR 앵커 재학습 주기와 모델 승인 책임자.
