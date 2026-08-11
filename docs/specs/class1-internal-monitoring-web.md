# Class 1 내부 모니터링 웹 명세

> 상태: 구현 가능한 제품 명세
> 사용자: 승인된 NIDS 내부 검토자
> 전제: [GAD-NR 특징 계약](../decisions/class1-gadnr-feature-contract.md)과 [목표 웹 아키텍처](../architecture/target-web-architecture.md)를 따른다.

## 제품 목적

내부 검토자가 업체를 검색하고, 직접 공급·수령 관계를 읽고, GAD-NR 역할군 백분위와 독립 보조증거를 근거로 다음 확인 대상을 정한다. 이 서비스는 위법·이상 여부를 자동 판정하지 않는다.

## 상태별 기준

- **Confirmed fact** — 현재 Streamlit과 혁신 프로토타입은 업체 검색, 3개월 앵커, 1/2-hop, 다중 모델 점수, BC/PDI/HHI/가격/시차를 표시할 수 있다.
- **Locked decision** — 정식 웹은 GAD-NR만 주 모델로 사용하고, 모델 원시 점수 대신 역할군 백분위 **검토 우선순위**를 표시한다.
- **Locked decision** — BC, 가격 z-score, 시간 단차는 GAD-NR 입력에서 분리된 보조지표다.
- **Locked decision** — HHI/PDI는 기본 화면에서 제거하고 상세 근거로 후순위화한다.
- **Implementation risk** — 현재 UI의 원시 점수, 5개 모델 선택, BC p95 green ring은 새 명세와 충돌한다.

## 권한과 감사

- 조직 SSO 인증이 필요하다.
- 역할: `reviewer`(조회), `analyst`(QA 상세), `admin`(모델·배치 상태).
- 모든 업체 검색, 상세 조회, 내보내기 시도, 권한 거부를 감사 로그에 남긴다.
- 원시 거래행과 전체 업체 목록의 무제한 다운로드는 제공하지 않는다.
- **Decision required** — 실제 SSO와 역할 매핑, 감사 로그 보존기간.

## 기본 사용자 여정

1. 업체명 또는 승인된 내부 ID로 검색한다.
2. 결과에서 기준점을 선택한다. UI 명칭은 **최초 선택 업체**다.
3. 최근 완료 앵커의 3개월 기간과 데이터 품질을 확인한다.
4. `공급 업체 → 최초 선택 업체 → 공급받은 업체` 1-hop 관계를 본다.
5. 거래 건수/낱개 수량/정제 금액 중 간선 두께 기준을 바꾼다.
6. 특정 거래처를 선택한 경우 그 가지의 2-hop만 확장한다.
7. GAD-NR 역할군 백분위와 독립 보조지표를 읽고 확인 포인트를 연다.
8. 직전 앵커 관계 diff와 비중첩 이전 3개월 규모 diff를 구분해 본다.

## 화면 정보 구조

### 1. 검색·기간 헤더

- 자동완성 업체 검색
- 결과의 업체 역할, 광역 지역, 내부 구분자 표시
- 앵커 월과 포함 3개월을 명시
- 모델 버전, 데이터 갱신일, 품질 상태 표시
- 검색 결과가 없거나 권한이 없을 때 상태를 구분

### 2. 탐지 요약

- `검토 우선순위: 유통업체군 상위 2%` 형식
- 동일 역할군 표본 수
- 직접 공급업체 수, 직접 수령업체 수
- 보고 거래 건수, 낱개 수량, 정제 금액과 각 유효률
- 최근 신규·소실 거래처 수
- 판단 유보 사유

### 3. 1-hop 관계 화면

- **Locked decision** — 기본은 3열 고정 레이아웃: 공급 업체 / 최초 선택 업체 / 공급받은 업체.
- **Locked decision** — 좌우 각각 기본 10개, 최대 20개를 표시하고 나머지는 `기타 N개`로 묶는다.
- **Locked decision** — 전체 force-directed 네트워크 기본 렌더링을 제거한다.
- **Locked decision** — 색만으로 역할·상태를 전달하지 않고 텍스트·아이콘을 병행한다.
- **Locked decision** — 간선 두께 기준은 거래 건수, 낱개 수량, 정제 금액 중 하나이며 범례에 단위를 표시한다.
- **Locked decision** — 품목군 필터와 업체쌍 주요 품목 1~3개를 제공한다.
- **Proposed decision** — `기타 N개`의 정렬은 선택 지표 내림차순이고 표시 경계 동점은 모두 포함한다.

### 4. 선택 가지형 2-hop

- 전체 2-hop 자동 펼치기를 제공하지 않는다.
- 사용자가 직접 거래처 하나를 선택할 때만 그 거래처의 다음 한 단계가 열린다.
- 확장 전 예상 노드 수를 반환하고, 한도 초과 시 숫자 요약만 표시한다.
- 2-hop은 모델 학습 범위가 아니라 UI 탐색 범위임을 안내한다.
- **Proposed decision** — 한 가지 확장 최대 20개 노드, 화면 전체 최대 60개 노드.

### 5. 관계·품목 표

필수 열:

- 방향
- 거래처 명칭·역할
- 보고 거래 건수
- 원본 공급 수량
- 낱개 수량과 유효률
- 정제 금액과 유효률
- 주요 품목 `A 외 N개`
- `previous_anchor_diff`의 신규/유지/소실 상태
- `prior_nonoverlap_3m_diff`의 건수·수량·금액 변화

### 6. 보조지표와 확인 포인트

기본 칩:

- BC 역할군 백분위
- reachable 경로 수와 gateway share
- 가격 이례 거래 수/유효 거래 수
- 접수 시차 중앙값/유효 표본 수
- 신규·소실 관계 수

확인 포인트는 규칙이 성립하고 최소 표본을 통과할 때만 생성한다.

- BC 상위 + 충분한 reachable 경로: `다수의 관측된 유통 경로가 이 업체를 통과하는지 확인`
- 가격 이례율 상위 + 최소 표본: `동일 품목·공급형태 기준 단가 확인`
- 시차 상위 + 최소 표본: `공급일과 최초접수일 차이 확인`
- 신규·소실 급증: `최근 거래 관계 변경 확인`

**Locked decision** — 기존 `관찰된 사실 → 관계 AI 해석 → 확인할 질문` 3단 구조는 `탐지 요약 → 확인 포인트` 2단 구조로 축소한다. GNN attribution이 없으므로 관계 AI가 이유를 설명했다는 문장을 만들지 않는다.

## API 계약

기본 prefix 제안: `/internal/v1/class1`

### 업체 검색

`GET /entities?query=&role=&limit=`

출력:

```json
{
  "items": [
    {"entity_id":"...","display_name":"...","role_group":"distributor","region":"11"}
  ],
  "next_cursor": null
}
```

### 탐지 요약

`GET /entities/{entity_id}/review-summary?anchor=YYYYMM`

출력 필수 필드:

- 앵커·포함 월
- 모델·특징·데이터 버전
- 역할군·표본 수·검토 우선순위 백분위
- 직접 상대 업체 수와 품질 상태
- 보조지표 요약과 판단 유보 사유

### 1-hop

`GET /entities/{entity_id}/relationships?anchor=&direction=&item_group=&measure=&limit=`

- 모델 그래프가 아니라 UI 사실 테이블에서 품목 세부를 조립한다.
- 응답은 `nodes`, `edges`, `other_count`, `measure_unit`, `truncated`를 포함한다.

### 선택 가지 2-hop

`GET /entities/{entity_id}/branches/{counterparty_id}?anchor=&measure=&limit=`

- `counterparty_id`는 1-hop 응답에 존재해야 한다.
- 전역 2-hop 요청은 400으로 거부한다.

### 변화

`GET /entities/{entity_id}/changes?anchor=`

- `previous_anchor_diff`와 `prior_nonoverlap_3m_diff`를 별도 객체로 반환한다.
- 비교 월 목록과 분모 0 처리 상태를 포함한다.

## 오류·빈 상태 계약

| 상태 | API | UI |
|---|---|---|
| 업체 없음 | 404 | 검색 조건 변경 안내 |
| 권한 없음 | 403 | 데이터 존재 여부를 노출하지 않는 안내 |
| 앵커 미완료 | 409/422 | 사용 가능한 최신 앵커 제안 |
| 역할군 소표본 | 200 + `insufficient_sample` | 백분위 대신 판단 유보 |
| 가격/시차 결측 | 200 + coverage | 지표 숨김이 아니라 결측률 안내 |
| 가지 한도 초과 | 200 + `truncated` | 숫자 요약·필터 제안 |
| 버전 불일치 | 503 | 결과 미서비스, 재계산 상태 안내 |

## 대상 파일

현재 파일은 대조·회귀 근거이며 신규 웹에 직접 복사하지 않는다.

| 구현 묶음 | 현재 대조 파일 | 향후 대상(제안) |
|---|---|---|
| 점수 DTO | `run_pygod_compare.py`, `run_step4_evaluation.py` | `services/class1_internal_api/schemas/review.py` |
| 관계 조회 | `build_network.py`, `app.py` | `services/class1_internal_api/routes/relationships.py` |
| diff 조회 | 없음 | `data_pipeline/aggregates/class1_anchor_diff.py` |
| BC 보조증거 | `metrics_bc.py` | `services/class1_internal_api/schemas/evidence.py` |
| 웹 | `app.py`, `prototype_meeting/innovation/class1.*` | `web/class1_internal/` |
| 계약 | 없음 | `schemas/openapi/class1-internal.yaml` |
| 테스트 | `tests/test_network_build_smoke.py` | `tests/contracts/class1/`, `tests/e2e/class1/` |

## 테스트

### API 계약

- 공개 자격으로 모든 endpoint가 401/403이다.
- 업체 검색은 마스킹·권한 정책과 페이지 한도를 지킨다.
- 응답에 GAD-NR 원시 점수, contamination 라벨, 타 모델 선택지가 없다.
- 역할군 백분위가 0~100 범위이며 역할군·표본 수를 포함한다.
- 1-hop에 없는 거래처의 branch 요청은 거부한다.
- 전역 2-hop·전체 네트워크 endpoint가 존재하지 않는다.

### 계산 계약

- 금액/건수/수량 선택이 간선 순서만 바꾸고 단위를 합성하지 않는다.
- 주요 품목은 선택 기간에 따라 다시 계산된다.
- 직전 앵커 diff와 비중첩 3개월 diff의 월 집합이 정확하다.
- BC p95=0, reachable=0, 가격·시차 소표본 fixture가 판단 유보를 만든다.

### UI·접근성

- 키보드만으로 검색, 1-hop 읽기, 가지 확장, 표 이동이 가능하다.
- 방향과 역할이 색 없이도 식별된다.
- 기본 최초 렌더에 전체 네트워크가 없다.
- 좌우 20개 초과 관계가 `기타 N개`로 묶인다.
- `최초 선택 업체`, `검토 우선순위`, `관측된 경로` 문구를 사용한다.

## 완료 조건

- GAD-NR 역할군 백분위와 버전이 없는 앵커는 서비스되지 않는다.
- 1-hop 기본과 선택 가지형 2-hop만 제공된다.
- 전체 네트워크, 5개 모델 선택, 원시 점수, 고정 정상/이상 라벨이 정식 웹에서 제거된다.
- BC·가격·시차가 독립 보조증거로 표시되고 각 coverage가 보인다.
- HHI/PDI는 기본 화면에 없고 상세 한계와 함께만 접근 가능하다.
- 원시 Excel과 모델 학습이 HTTP 요청 경로에서 호출되지 않는다.

## 결정 필요 사항

1. 역할군·최소 표본·백분위 band.
2. 1-hop/가지형 2-hop의 정확한 노드 한도.
3. 검색 가능한 업체 식별자와 마스킹 정책.
4. SSO, 역할, 감사·내보내기 정책.
5. 내부 화면에서 정제 금액을 어느 권한까지 보여줄지.
