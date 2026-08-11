# Streamlit에서 일반 웹으로 전환 계획

> 상태: 마이그레이션 기준선
> 원칙: 기능 구현·삭제·패키지 설치는 후속 PR에서 수행한다.
> 관련: [목표 웹 아키텍처](../architecture/target-web-architecture.md)

## 현재와 목표

| 영역 | 현재 | 목표 |
|---|---|---|
| Class 1 UI | 단일 Python Streamlit 앱, 7개 탭 | GAD-NR 중심 내부 웹, 1-hop+가지형 2-hop |
| Class 3 UI | MCDM Streamlit + mock 정적 프로토타입 | 공개·인증 업체·품목군 다중 비교 웹 |
| 요청 데이터 | 사전 계산 CSV | 서비스 DB의 버전된 집계·모델 결과 |
| 원천 적재 | 배치가 Excel 전체 시트 로드 | 오프라인 증분 적재, 월별 Parquet |
| 모델·지표 | Python 배치/실험 산출 | 버전된 오프라인 배치, API는 조회만 |
| 인증 | 없음 | Class 1 내부 SSO/RBAC, Class 3 공개/기업 분리 |
| 공개 보호 | prototype 문서만 존재 | allowlist·억제·우세도·감사 서비스 |

- **Confirmed fact** — 현재 Streamlit 앱은 원시 Excel이 아니라 output CSV를 읽는다.
- **Confirmed fact** — 각 위젯 상호작용 시 Python 스크립트 재실행·세션 처리가 일어나는 Streamlit 구조는 내부 PoC에는 적합하지만 공개 서비스의 인증, API 분리, 다중 인스턴스 UX를 별도로 해결해야 한다. 공식 구조: <https://docs.streamlit.io/develop/concepts/architecture/architecture>.
- **Locked decision** — 정식 제품은 일반 웹으로 전환한다.
- **Locked decision** — Streamlit은 전환 기간의 내부 QA 도구로만 남길 수 있다.

## 마이그레이션 원칙

1. 데이터 계약을 UI보다 먼저 고정한다.
2. 원천 적재, 서비스 집계, 모델 산출, API, UI를 별도 PR로 나눈다.
3. Class 1 모델 변경과 Class 1 UI 변경을 같은 PR에 넣지 않는다.
4. Class 3 기존 코드 삭제와 신규 서비스 구축을 같은 PR에 넣지 않는다.
5. 새 계약과 회귀 증거가 준비되기 전 기존 파일을 삭제하지 않는다.
6. mock 값은 UI fixture로만 사용하고 생산 계약의 기본값으로 복사하지 않는다.
7. 생산 방문 수치가 로컬 top7 수치보다 우선한다.

## 단계별 계획

### M0. 결정·문서 기준선

대상:

- `docs/architecture/target-web-architecture.md`
- `docs/decisions/*`
- `docs/specs/*`
- `docs/migration/*`
- `README.md`, `shared_docs/README.md`, structured spec 상태 헤더

입력: 저장소 코드, README, shared_docs, onsite 문서, prototype/innovation, 두 참고 답변.

출력: 상태 표기가 있는 명세와 작은 PR 로드맵.

테스트:

- 상대 링크 유효성
- 필수 용어·금지 용어 정적 검사
- 코드 파일 변경·삭제 0건

완료 조건: 구현자가 채팅 원문 없이 범위·계약·미결정을 식별할 수 있다.

### M1. 공통 월 사실 계약

대상(제안):

- `data_pipeline/contracts/supply_monthly.py`
- `data_pipeline/aggregates/company_counterparty_product_month.py`
- `tests/contracts/test_supply_monthly_contract.py`

입력: 정제된 DataFrame fixture. 첫 PR에서는 생산 Excel을 실행하지 않는다.

출력: `fact_company_counterparty_product_month` 스키마와 결정적 집계 함수.

테스트:

- 금액·건수·원본 수량·낱개 수량 분리
- 3-key 제품 ID, 월, 업체쌍 중복 처리
- 결측·부호·금액 대체 quality flag
- 품목군과 품목명 분리

완료 조건: 동일 fixture에서 행 순서와 무관하게 동일 집계가 생성된다.

### M2. 오프라인 월별 Parquet 적재

대상(제안):

- `data_pipeline/ingest/`
- `data_pipeline/jobs/load_month.py`
- `data_pipeline/manifests/`
- `tests/integration/test_monthly_parquet.py`

입력: 설정된 원본 파일/신규 보고 데이터, 스키마 profile, 3-key 마스터.

출력: 월 파티션 Parquet, 적재 manifest, 품질·조인 보고서.

테스트:

- content-based Excel sheet discovery
- 3-key join 및 UDI-only 팽창 guard
- idempotent 재실행
- schema drift fail/flag 정책
- 월 파티션만 다시 계산하는 증분성

완료 조건: API나 UI 없이 한 월을 재적재하고 manifest와 품질 결과를 재현한다.

**Decision required** — Parquet writer 라이브러리, 파일 저장 위치/암호화/보존 정책.

### M3. Class 3 신규 집계·공개 보호

Class 1과 독립 작업이다.

대상(제안):

- `data_pipeline/dimensions/product_search.py`
- `data_pipeline/aggregates/class3_product_month.py`
- `data_pipeline/publication/class3_policy.py`
- `tests/contracts/class3/`, `tests/security/class3/`

입력: 공통 월 사실.

출력: 검색 dimension, 품목별 비교, 포트폴리오 요약, 관측된 도달 구조, 억제된 공개 데이터 제품.

테스트: 다중 선택, 품목별 HHI 분리, 결측 coverage, small-cell/dominance/complementary suppression.

완료 조건: 공개 allowlist fixture에 직접 식별자와 원시 경로가 없다.

### M4. Class 3 API와 웹

대상(제안):

- `services/class3_public_api/`
- `services/class3_enterprise_api/`
- `web/class3_public/`
- `schemas/openapi/class3-*.yaml`

입력: M3 공개/기업 데이터 제품.

출력: 검색, 품목별 비교, 포트폴리오, 관측된 도달 구조, 억제·결측 안내.

테스트: OpenAPI snapshot, 공개/기업 권한 분리, 접근성, 캐시 격리, suppression UI.

완료 조건: 정적 mock 없이 승인 fixture로 end-to-end 사용자 여정을 수행한다.

### M5. Class 3 기존 서비스 active route 퇴역

대상 참조:

- `class_3_impact_evaluation/`
- `prototype_meeting/class_3/`
- `prototype_meeting/innovation/class3.*`
- 배포·README·CI의 기존 진입점

입력: M4 parity·보안 승인, 보존 사실 목록.

출력: 배포·라우팅·CI의 active runtime에서 MCDM 서비스 격리. 기존 소스 파일 삭제는 포함하지 않는다.

테스트:

- active 경로의 `MCDM|Kraljic|Clinical Impact|Supply Risk` 참조 0
- 신규 웹 회귀·보안 테스트
- 보존 사실 링크 확인

완료 조건: 신규 서비스와 공용 데이터 사실을 유지한 채 active route가 분리된다. 소스 삭제는 보존 사실 이전과 별도 승인을 거친 후속 PR에서만 수행한다.

### M6. Class 1 모델 계약 변경

Class 3와 독립 작업이다.

대상:

- `class_1_anomaly_detection/src/graph/build_network.py`
- `class_1_anomaly_detection/src/experiments/export_pyg_graph.py`
- `run_pygod_compare.py`, `run_step4_evaluation.py`
- `metrics_bc.py`
- 신규 diff·feature 모듈과 테스트

입력: 공통 월 사실.

출력: 업체쌍 그래프, 수량 특징, 보조지표 제외 GAD-NR, 역할군 백분위, 두 diff, BC reachability.

테스트: 그래프 단일 간선, 특징 allow/deny list, ablation, top-K 안정성, p95=0, reachable=0.

완료 조건: GAD-NR가 유일한 서비스 주 모델이고 기존 점수와 버전이 분리된다.

### M7. Class 1 API와 웹

대상(제안):

- `services/class1_internal_api/`
- `web/class1_internal/`
- `schemas/openapi/class1-internal.yaml`

입력: M6 버전된 모델·지표 결과와 공통 월 사실.

출력: 업체 검색, 검토 요약, 1-hop, 가지형 2-hop, 관계표, 보조지표.

테스트: SSO/RBAC, 원시 점수 미노출, 전체 네트워크 부재, 접근성, 성능 한도.

완료 조건: 정식 내부 사용자 여정이 Streamlit 없이 동작한다.

### M8. Streamlit QA 격리

대상:

- 기존 `class_1_anomaly_detection/app.py`
- 필요한 경우 제한된 QA 전용 앱
- 배포 manifest·README

입력: 승인된 QA 산출물.

출력: 운영 트래픽과 분리된 내부 QA 도구 또는 완전 제거.

테스트: 정식 서비스 라우팅·가용성이 Streamlit 프로세스에 의존하지 않는다.

완료 조건: Streamlit이 공개 DNS, 정식 내부 사용자 진입점, 운영 DB 쓰기 권한을 갖지 않는다.

## 병행·의존 관계

```mermaid
flowchart LR
    M0["M0 문서"] --> M1["M1 공통 집계 계약"] --> M2["M2 월별 Parquet"]
    M2 --> M3["M3 Class 3 집계·보호"] --> M4["M4 Class 3 웹"] --> M5["M5 Class 3 퇴역"]
    M2 --> M6["M6 Class 1 모델"] --> M7["M7 Class 1 웹"] --> M8["M8 Streamlit 격리"]
```

M3~M5와 M6~M8은 M2 이후 독립 브랜치·PR 열로 진행한다. 한쪽의 모델·UI 변경이 다른 쪽의 승인을 막아서는 안 된다.

## 데이터 전환과 검증

- shadow 기간 동안 CSV 기반 기존 결과와 새 Parquet/DB 결과를 병렬 산출한다.
- 비교 대상은 원시 모델 점수가 아니라 입력 행 수, 집계 합계, 고유 키 수, 품질 플래그, 역할군 top-K다.
- 특징 버전이 바뀌는 Class 1 점수는 숫자 동등성을 완료 조건으로 삼지 않는다.
- Class 3는 MCDM 결과 parity가 아니라 새 데이터 계약의 집계 정확성과 공개 보호를 검증한다.

## 롤백 원칙

- 데이터 파티션과 모델·정책 버전은 불변으로 보존한다.
- API가 지원하는 `data_version`/`model_version`/`policy_version`만 라우팅으로 전환한다.
- 새 웹 장애 시 이전 Streamlit을 공개 서비스로 승격하지 않는다. 마지막 승인된 웹·API 버전으로 되돌린다.
- 기존 파일 삭제 PR은 신규 경로 안정화 후 별도로 수행해 되돌리기 쉽게 한다.

## 전환 리스크

- **Implementation risk** — 현 저장소에는 웹 프레임워크·API·DB 운영 표준이 없어 기술 선택이 먼저 이뤄지면 조직 환경과 충돌할 수 있다.
- **Implementation risk** — 생산 파일 크기에서 pandas/openpyxl 전체 로딩은 메모리·시간 병목이다.
- **Implementation risk** — 공개 보호가 UI 뒤에서 추가되면 API·캐시에서 식별값이 새어 나갈 수 있다. 데이터 제품 단계에서 적용해야 한다.
- **Implementation risk** — Class 1 특징 변경과 UI 변경을 섞으면 점수 변동 원인을 추적하기 어렵다.
- **Implementation risk** — 기존 Class 3 삭제를 먼저 하면 보존해야 할 join/결측 근거를 잃을 수 있다.

## 전환 전 결정 필요

1. 프런트엔드·API 조직 표준과 배포 플랫폼.
2. Parquet writer, 서비스 DB, 객체/파일 저장 위치.
3. 내부 SSO와 기업 인증·소유권 검증.
4. 공개 보호 정책.
5. 생산 갱신 주기, 동시접속, SLO, 보존기간.
