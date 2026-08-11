# 구현 로드맵

> 상태: 작은 PR 실행 순서
> 기준일: 2026-08-11
> 이번 단계: 문서 PR만 수행하며 아래 구현은 수행하지 않는다.

## 순서 원칙

- 공통 월 사실 계약이 Class 1/3보다 먼저다.
- PR-01 직후 Class 3 mock 계약과 정적 웹을 먼저 검증하고, 그 화면 계약이 안정된 뒤 Parquet·실데이터·공개 보호를 연결한다.
- Class 3 실데이터 열과 Class 1 열은 공통 계약 이후 분리하되, 이 로드맵의 승인 순서를 따른다.
- 모델 입력 변경, API 변경, UI 변경, 기존 코드 삭제를 한 PR에 섞지 않는다.
- 각 PR은 synthetic fixture로 검증하고 생산 학습·대용량 실행은 별도 승인 작업으로 둔다.
- 패키지·프레임워크 설치는 해당 ADR/기술 선택 승인 후 별도 PR에서만 한다.

## PR 목록

### PR-00 — 결정 문서 기준선

범위:

- 이 `docs/` 문서 7개
- README·shared_docs에서 새 권한 문서로 연결
- 기존 Class 1/3 structured spec을 역사 기준선으로 표시

제외:

- Python/JS/CSS 변경
- 파일 삭제
- 패키지 설치
- 모델 실행·데이터 처리

테스트/완료:

- Markdown 링크·필수 상태 표기 검사
- `git diff --name-only`가 문서 파일만 포함
- 모든 Decision required가 후속 PR blocker와 연결

### PR-01 — 공통 월 사실 스키마와 순수 집계 함수

이것이 권장 첫 번째 구현 PR이다.

정확한 범위:

```text
data_pipeline/__init__.py
data_pipeline/contracts/__init__.py
data_pipeline/contracts/supply_monthly.py
data_pipeline/aggregates/__init__.py
data_pipeline/aggregates/company_counterparty_product_month.py
tests/contracts/test_supply_monthly_contract.py
tests/fixtures/supply_monthly_small.*
```

입력:

- synthetic pandas DataFrame fixture
- 공급자·수령자 ID, 원본 3-key, `source_version`, `source_row_id`, 품목군·품목명, 월, 거래 구분
- 공급금액·공급단가·공급수량·포장내 총 수량

출력:

- `fact_company_counterparty_product_month` DataFrame
- 스키마·dtype·nullable·quality flag 정의
- `tx_count`, `amount_sum_clean`, `raw_supply_qty_sum`, `piece_qty_sum` 분리
- `raw_supply_qty_valid_row_count`, `piece_qty_valid_row_count` 분리
- product-key·deduplication·forward-value 차단 상태

포함하지 않음:

- Excel 읽기
- Parquet 쓰기
- DB/API/UI
- Class 1 그래프·모델
- Class 3 억제
- 새 패키지

테스트:

- 행 순서를 바꿔도 같은 결과
- 같은 업체쌍·다른 제품은 별도 사실 행
- 금액/건수/수량 단위 분리
- 품목군 결측 시 품목명을 품목군으로 대체하지 않음
- 3-key의 공백과 공식 코드 dtype 차이가 달라도 같은 정규형과 `product_id`
- null·빈 값·불완전 3-key에서 정상 `product_id` 생성 차단
- 3-key가 같지 않으면 UDI가 같아도 합치지 않음
- 같은 `(source_version, source_row_id)`가 반복되어도 한 번만 집계
- 원천 식별자가 없고 승인 대체키도 없으면 `blocked:deduplication_unverified`
- 일반 공급의 음수 금액·수량 fixture는 명시적 오류 또는 품질 차단
- 반품·회수 fixture는 승인 전 `blocked:transaction_sign_policy_pending`

완료 조건:

- 스키마 snapshot이 문서 계약과 일치
- 기존 Class 1/3 코드를 호출하지 않는 독립 모듈
- 원천 식별·3-key·부호 차단을 통과한 행만 월 사실에 포함
- 생산 파일·모델을 실행하지 않고 테스트 통과

선행 결정:

- **Decision required** — `piece_qty_sum` 공식과 거래 구분별 부호. 해결되지 않으면 해당 필드는 nullable+quality flag로 구현하고 반품·회수 집계를 차단한다.

## Class 3 mock UI 선행 열

이 열은 PR-01 직후 시작한다. 목표 런타임 데이터 흐름을 대체하지 않으며, 화면·상호작용 계약을 실데이터 작업보다 먼저 검증하는 임시 개발 경계다.

### PR-C3-UI-01A — mock API 계약과 정적 웹 셸

범위: 버전된 mock 응답 스키마, 정적 진입점, 라우팅 없는 화면 셸, fixture loader.

제외: 실데이터, Parquet, 인증, 공개 정책 임계값, 기존 MCDM active route 격리, 런타임 mock fallback.

완료: fixture 스키마가 품목별 결과·포트폴리오·결측·억제 빈 상태를 구분하고, production API로 오인될 수 있는 endpoint가 없다.

### PR-C3-UI-01B — 혁신 시안 시각 체계 이전

범위: 승인된 색상·타이포그래피·검색 영역·카드/비교표 위계·접근성 패턴만 정적 웹 셸에 이전.

제외: 기존 혁신 시안의 정보 구조, 생성 진단 문장, 단일 품목 흐름, 성장×HHI 중심 구조.

완료: 시각 토큰 출처가 문서화되고 기존 mock 정보 구조에 대한 런타임 의존이 없다.

### PR-C3-UI-01C — 핵심 비교 상호작용과 상태

범위: 다중 품목 검색, 기간 선택, 품목별 비교표, 월별 추세, 포트폴리오 요약, loading/error/empty/suppressed/missing 상태.

제외: 실제 검색 dimension, 실제 API, 인증 기업 기능, 승인 전 억제 임계값.

완료: mock fixture E2E와 접근성·responsive 테스트가 통과하며 품목별 결과와 포트폴리오가 혼합되지 않는다.

### PR-C3-UI-01D — Cursor 디자인 조정

범위: 사용자가 실제 화면을 확인하며 수행하는 레이아웃·간격·타이포그래피·responsive 세부 조정.

제외: 제품 계약, API 스키마, 데이터 의미, 공개 정책, 인증 경계 변경.

완료: 승인된 화면 상태별 시각 회귀 기준과 디자인 검토 기록이 남는다.

### PR-02 — 월별 Parquet writer와 manifest

범위:

- 승인된 Parquet 라이브러리 의존성
- 월 파티션 writer/reader
- schema/version/row-count/checksum manifest
- idempotency·partition overwrite guard 테스트

제외: 원본 Excel adapter, 서비스 DB, 모델.

완료: synthetic fixture를 두 월 Parquet으로 쓰고 projection/filter 검증 및 재실행 동일성 통과.

### PR-03 — 원본 적재 adapter와 3-key join 품질

범위:

- content-based sheet discovery
- 스키마 profile·drift 처리
- 3-key join, UDI-only inflation guard
- 금액 극단값·결측·수량 quality flag

제외: 전체 생산 적재 실행, 모델, 웹.

완료: 축소 fixture에서 적재→PR-02 파티션 end-to-end 통과. 생산 실행은 별도 운영 작업.

## Class 3 독립 열

### PR-C3-01 — 검색 dimension

범위: 품목군/품목명 분리 ID, 문자열 정규화, prefix/contains, 동의어 버전, synthetic 검색 테스트.

완료: 다중 유형 결과가 품목군과 품목명을 혼동하지 않는다.

### PR-C3-02 — 품목별 비교 집계

범위: 월 활동, 수량, 금액 유효률, 공급자·수령자 수, 업종·지역 구성, endpoint coverage, 품목별 HHI.

제외: 공개 억제, API, UI.

완료: 품목별 결과와 포트폴리오 요약이 별도 스키마이며 혼합 HHI가 없다.

### PR-C3-03 — 공개 보호 엔진

범위: allowlist, 최소 셀, 우세도, 보완 억제, 구간화·반올림, 차분 위험 fixture.

선행 결정: 개인정보·법무 승인 정책 값.

완료: 금지 필드와 역산 가능한 small-cell fixture가 공개 결과에 없다.

### PR-C3-04 — 공개 API 계약·fixture 구현

범위: 기술 ADR, OpenAPI, catalog/comparisons/methodology, 버전·coverage·release status.

제외: 인증 기업 API, UI.

완료: 공개 스키마 snapshot·rate limit·보안 테스트 통과.

### PR-C3-UI-02 — 확정 웹 화면과 실제 API 연결

범위: PR-C3-UI-01에서 확정한 화면 상태를 PR-C3-04 실제 API, 검색 dimension, 품목별 집계, 공개 보호 결과에 연결.

제외: 기존 Class 3 active route 격리, 기업 모드, production 응답 실패 시 mock fallback.

완료: 접근성·responsive·API E2E 통과, mock JSON 런타임 의존 없음, 억제·결측 응답이 확정된 빈 상태로 표시됨.

### PR-C3-06 — 인증 기업 경계

범위: 기업 인증·자사 소유권 검증, `/enterprise` API, 자사 vs 익명 cohort, 감사·캐시 격리.

완료: cross-tenant 접근 테스트와 suppression 테스트 통과.

### PR-C3-07 — 기존 MCDM active 경로 격리

범위:

- 배포·라우팅·CI의 `class_3_impact_evaluation/app.py` 진입점
- 배치 스케줄의 `src/eda/run_mcdm_eda.py` 진입점
- MCDM output 계약의 active 소비 경로
- 구형 prototype runtime 참조

선행 조건: C3-02~06 완료, 보존 사실 이전 검증.

완료: active runtime의 MCDM/Kraljic/Clinical Impact/Supply Risk 참조 0. 기존 소스는 역사 참조로 남기며, 삭제는 보존 사실 이전과 별도 승인을 거친 후속 PR에서만 수행한다.

## Class 1 독립 열

### PR-C1-01 — 업체쌍 모델 그래프와 UI 품목 사실 분리

범위: 업체쌍당 방향 간선 1개, 고유 거래처 수·제품 간선 수 분리, UI 품목 세부 조회 계약.

완료: 복수 제품 fixture에서 모델 간선 1개, UI 품목 N개.

### PR-C1-02 — 수량 특징과 보조지표 입력 분리

범위: 원본/낱개 수량 노드 특징, `data.x`에서 BC·가격·시차 제거, 특징 manifest denylist.

제외: 학습 실행, 웹.

완료: 특징 계약 테스트 통과, 모델 버전 증가.

### PR-C1-03 — GAD-NR 주 모델·역할군 백분위

범위: 서비스 주 모델 고정, DOMINANT QA 경로, contamination 서비스 라벨 제거, 역할군 백분위 산출.

완료: 서비스 DTO에 원시 점수·타 모델 선택·정상/이상 라벨 없음.

### PR-C1-04 — BC reachability와 p95=0 guard

범위: 원값 저장, 역할군 백분위, reachable pairs, gateway share, component size, 판단 유보.

완료: disconnected/p95=0/small-sample fixture 통과.

### PR-C1-05 — 두 종류 앵커 diff

범위: `previous_anchor_diff`와 `prior_nonoverlap_3m_diff`, 분모 0·부분 월 정책.

완료: 포함 월과 신규·소실·추세 fixture 통과.

### PR-C1-06 — 오프라인 평가·ablation

범위: 금액-only/수량-only/결합, DOMINANT 회귀, 앵커 top-K 안정성, 합성 이상 주입 harness.

주의: 실제 학습 실행은 승인된 환경·데이터로 별도 운영한다.

완료: 평가 산출물 스키마와 승인 gate가 자동화되고 모델 선택이 BC 단일 일치도에 의존하지 않는다.

### PR-C1-07 — 내부 API

범위: SSO/RBAC 이후 업체 검색, review summary, 1-hop, branch 2-hop, changes, OpenAPI.

완료: 권한·한도·버전·원시 점수 미노출 계약 통과.

### PR-C1-08 — 내부 웹

범위: 3단 1-hop, 최초 선택 업체, 가지형 2-hop, 검토 우선순위, 보조지표, 두 diff.

완료: 전체 네트워크·다중 모델·원시 점수·HHI/PDI 기본 탭이 없고 접근성 E2E 통과.

### PR-C1-09 — Streamlit QA 격리

범위: 운영 진입점 제거, QA 전용 권한·데이터 제한 또는 앱 제거.

완료: Streamlit 중단이 Class 1 정식 웹에 영향 없음.

## 교차 작업 금지표

| PR | 포함 금지 |
|---|---|
| 공통 데이터 PR | React/FastAPI, GAD-NR, MCDM 삭제, 공개 정책 임계값 |
| Class 3 집계 PR | Class 1 특징·모델 파일 |
| Class 3 mock UI PR | 실데이터, 인증, 공개 정책 임계값, 기존 MCDM 격리, production mock fallback |
| Class 3 실제 API 연결 PR | 공개 억제 우회 mock fallback, Class 1 UI |
| Class 1 모델 PR | Class 3 코드, 웹 프레임워크 |
| Class 1 UI PR | 모델 재학습·특징 변경 |
| 삭제 PR | 신규 기능, 의존성 업그레이드, 대규모 포맷 변경 |

## PR 공통 체크리스트

- [ ] 관련 Decision required가 해결되었거나 명시적으로 차단된다.
- [ ] 입력·출력 스키마와 버전이 문서에 연결된다.
- [ ] synthetic fixture로 경계·결측·빈 상태를 검증한다.
- [ ] 생산 파일·대용량 학습이 CI에서 실행되지 않는다.
- [ ] 공개 응답은 allowlist를 통과한다.
- [ ] 마이그레이션 중 기존 사용자 경로와 롤백을 설명한다.
- [ ] unrelated Class의 파일을 변경하지 않는다.

## 구현 전 사용자 결정 목록

### 첫 PR 전 필수

1. `piece_qty_sum` 공식과 반품·회수 부호 규칙.
2. 새 공통 모듈 경로(`data_pipeline/`) 승인.

### Parquet/API 전 필수

3. Parquet writer·저장 위치·암호화·보존.
4. 프런트엔드/API/DB 조직 표준과 배포 플랫폼.
5. 내부 SSO·역할, 기업 인증·자사 검증.

### 공개 전 필수

6. 소수 셀, 우세도, 보완 억제, 반올림, 차분 방지 정책.
7. 동종집단 정의와 최소 표본.
8. 공개 금액 제공 여부.

### Class 1 서비스 전 필수

9. 역할군·최소 표본·백분위 band.
10. BC gateway share 분모와 판단 유보 기준.
11. 모델 승인·재학습 주기와 수작업 검토 책임자.
