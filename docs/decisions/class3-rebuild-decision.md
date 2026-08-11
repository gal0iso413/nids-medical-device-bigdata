# Class 3 재구축 결정

> 상태: 승인된 제품 재정의(ADR)
> 기준일: 2026-08-11
> 결정: 기존 MCDM/영향평가 서비스를 폐기하고 **업체·품목군 비교분석** 서비스로 새로 구축한다.
> 주의: 이번 단계에서는 파일을 삭제하지 않는다.

## 결정 표기

이 문서는 **Confirmed fact**, **Locked decision**, **Proposed decision**, **Decision required**, **Implementation risk**를 구분한다.

## 맥락과 충돌

- **Confirmed fact** — [`shared_docs/structured/class_3_evaluation_spec.md`](../../shared_docs/structured/class_3_evaluation_spec.md)는 MCDM, 임상 영향, 공급 위험, Kraljic 4분면, 군집화를 활성 범위로 정의한다.
- **Confirmed fact** — [`class_3_impact_evaluation/app.py`](../../class_3_impact_evaluation/app.py)는 Kraljic Matrix, Supply Risk, Clinical Impact, MCDM Inputs의 네 Streamlit 탭을 제공한다.
- **Confirmed fact** — [`run_mcdm_eda.py`](../../class_3_impact_evaluation/src/eda/run_mcdm_eda.py)는 품목군별 HHI·Top-3 공급자 점유율과 고유 의료기관 수를 MCDM 입력으로 산출한다.
- **Confirmed fact** — HHI 0.15/0.25와 P50 4분면 기준이 코드에 하드코딩 또는 UI 조정값으로 존재한다.
- **Confirmed fact** — [`prototype_meeting/specs/class_3_public_dashboard_spec.md`](../../prototype_meeting/specs/class_3_public_dashboard_spec.md)는 이미 실명 업체 검색 없는 익명 동종집단 공개 대시보드로의 전환을 제안한다.
- **Confirmed fact** — 혁신 시안은 업종·권역·품목군 3단계 입력, 품목군 집중도×증감 버블, 단일 품목명 후속 검색, 진단 문장을 mock JSON으로 렌더링한다.
- **Implementation risk** — 기존 상위 문서는 MCDM을 “Active/supreme”로 두고 프로토타입 문서는 공개 비교 서비스로 전환한다. 명시적 supersession 없이는 구현자가 서로 다른 제품을 만들 수 있다.

## 결정

- **Locked decision** — 기존 Class 3 MCDM/영향평가 서비스 로직은 폐기한다.
- **Locked decision** — 최종 제품은 **업체·품목군 비교분석**이다.
- **Locked decision** — Class 3는 기존 기능 확장이 아니라 신규 서비스다.
- **Locked decision** — 혁신 시안에서는 색상, 타이포그래피, 큰 검색 영역, 단계 위계, 카드·비교표 위계, 접근성 방향만 계승한다.
- **Locked decision** — 혁신 시안의 정보 구조, mock 데이터 계약, 생성 진단 문장, 단일 품목 흐름, 성장×HHI 버블 중심 구조는 최종 계약으로 계승하지 않는다.
- **Locked decision** — 공개 업체 비교는 실명 업체 A와 B의 비교가 아니라 익명 동종집단 비교다.
- **Locked decision** — 일반 공개 사용자와 인증 기업 사용자의 기능·데이터 경계를 분리한다.

## 최종 서비스 범위

| 사용자 | 허용 기능 | 금지/제한 |
|---|---|---|
| 일반 공개 사용자 | 품목군·품목명 다중 검색, 품목별 공급 활동·수량·공급자/수령자 수, 업종·광역 지역 구성, 관측된 유통 도달 구조 | 실명 업체 간 비교, 업체별 정확 금액·순위, 원시 거래 경로 |
| 인증 기업 사용자 | 검증된 자사 취급 포트폴리오, 자사와 익명 동종업체군 비교 | 타사 식별값, 소수집단 역추론, 미검증 자사 ID |
| 내부 운영 사용자 | 공개 집계 검증, 억제 사유·품질·배치 상태 확인 | 공개 UI를 우회한 무감사 원시행 추출 |

- **Locked decision** — 품목군과 품목명을 모두 다중 검색할 수 있어야 한다.
- **Proposed decision** — 한 비교의 최대 선택 수는 5개다. 정확한 제한은 사용성·응답 크기 시험 후 확정한다.
- **Locked decision** — 품목별 개별 비교와 선택 포트폴리오 전체 요약을 별도 결과로 제공한다.
- **Locked decision** — HHI처럼 시장 정의가 필요한 값은 품목별/품목군별로만 계산하며 서로 다른 선택 품목을 합쳐 하나의 HHI로 만들지 않는다.

## 폐기할 서비스 로직

아래는 다음 구현 단계에서 active runtime과 기본 문서 경로에서 제거할 대상이다. 이번 문서 PR에서는 삭제하지 않는다.

| 대상 | 폐기 이유 | 처리 원칙 |
|---|---|---|
| `class_3_impact_evaluation/app.py` | Streamlit MCDM/Kraljic 서비스 | 신규 웹 전환 후 active route에서 먼저 격리; 소스 삭제는 별도 승인 PR |
| `class_3_impact_evaluation/src/eda/run_mcdm_eda.py` | 제품 목표와 다른 Supply Risk/Clinical Impact 입력 생성 | 결과 사실을 추출한 뒤 active job에서 격리; 소스 삭제는 별도 승인 PR |
| `supply_risk_per_group.csv` 계약 | 금액 HHI를 공급 위험으로 규정 | 새 품목별 비교 집계로 대체 |
| `clinical_impact_per_group.csv` 계약 | 고유 병원 수를 임상 영향으로 규정 | 수령자 수/구성 사실로 대체; “임상 영향” 금지 |
| `mcdm_inputs_combined.csv` 계약 | MCDM·4분면 전용 | 신규 public/enterprise DTO로 대체 |
| Supply Risk / Clinical Impact / MCDM Inputs / Kraljic 탭 | 폐기 제품 IA | 신규 다중 비교 IA로 대체 |
| HHI 0.15/0.25 위험 라벨 | 시장 정의·정책 승인 없는 위험 판정 | 집중도 사실과 품목별 비교 맥락만 유지 |
| `prototype_meeting/class_3/*` | 구형 mock 프로토타입 | 디자인 역사 자료로만 유지 후 정리 |
| `prototype_meeting/innovation/class3.html/js/css`의 런타임 사용 | mock·단일 선택·진단 문장 결합 | CSS 토큰·접근성 패턴만 참조 |
| 기존 Class 3 structured spec의 활성 MCDM 권한 | 새 결정과 충돌 | 이 ADR을 상위 제품 결정으로 명시 |

- **Locked decision** — Git 이력만을 보존 수단으로 삼기 전에 검증 사실과 마이그레이션 근거가 새 문서·테스트에 옮겨졌는지 확인한다.
- **Implementation risk** — 기존 app은 Excel을 직접 읽지 않지만 EDA job은 원시 Excel 전체를 읽는다. app 삭제만으로 대규모 데이터 문제가 해결되지 않는다.

## 보존할 데이터 사실

서비스 로직과 데이터 사실을 분리한다. 아래 사실은 공용 데이터 품질 문서와 회귀 fixture의 근거로 보존한다.

### 생산 방문 사실 — 우선 근거

출처: [`shared_docs/structured/onsite_visit1_summary.md`](../../shared_docs/structured/onsite_visit1_summary.md)

- **Confirmed fact** — 공급 12,000,000행/4개월, 71열.
- **Confirmed fact** — 마스터 약 2,625,652행, 93열.
- **Confirmed fact** — 3-key 조인 11,996,981/12,000,000, 99.97%.
- **Confirmed fact** — UDI 단독 조인은 107.03%로 팽창하므로 모델·집계 조인으로 부적합하다.
- **Confirmed fact** — 의료기관 코드 결측 54.6%로 최종단·병원 커버리지 해석이 불완전하다.
- **Confirmed fact** — 공급금액·단가에 극단값과 바코드형 값이 있어 정제가 필요하다.
- **Confirmed fact** — 제조원국가 결측 99.6%로 공개 세분화에 부적합하다.
- **Confirmed fact** — 기존 MCDM이 기대한 세 가지 마스터 필드는 생산 export에 없다.

### 로컬 EDA 사실 — 보조 근거

출처: [`prototype_meeting/research/platform_benchmark.md`](../../prototype_meeting/research/platform_benchmark.md)

- **Confirmed fact** — 공급수량 결측 약 0.01%, 공급금액 결측 17.16%, 단가 결측 21.51%.
- **Confirmed fact** — 공급자 serial/name/type은 결측이 없고, 수령자 serial 결측은 1.08%다.
- **Confirmed fact** — 광역 지역 구성, 품목/품목군, 공급자·수령자 업종, 월별 활동을 현 필드로 집계할 수 있다.
- **Confirmed fact** — 로컬 표본은 7개 품목 중심이므로 국가 시장 대표성을 주장할 수 없다.

### 보존하지 않을 주장

- **Confirmed fact** — 저장소에는 Class 3 EDA 결과 CSV, onsite 상세 profile, HHI 그룹 수 같은 산출값이 커밋되어 있지 않다.
- **Locked decision** — 코드가 계산할 수 있다는 사실을 검증된 생산 통계로 승격하지 않는다.
- **Locked decision** — “임상 영향”, “공급 위험”, “대체 불가능”, “최종 수요”, “시장 기회”를 현 데이터만으로 입증된 사실처럼 보존하지 않는다.

## 용어와 출력 원칙

- **Locked decision** — `자사 제품 최종단 추적`과 `최종 유통 경로`를 사용하지 않는다.
- **Locked decision** — 화면 용어는 **관측된 유통 도달 구조**다.
- **Locked decision** — 제공 가능한 내용은 관측된 다음 단계의 역할 비중, 수령자 업종 구성, 광역 지역 구성, 월별 수령 업체 수, endpoint 미확인 비율이다.
- **Locked decision** — 거래 건수는 **보고된 거래 활동**으로 표현한다. 실제 수요·매출·시장규모와 동일시하지 않는다.
- **Locked decision** — 수량, 공급금액, 건수는 별도 지표로 표시하고 유효률을 함께 제공한다.

## 공개 보호 계약

- **Locked decision** — 서버 집계 후 공개하며 원시행·식별자를 브라우저로 보내지 않는다.
- **Locked decision** — 소수 셀 억제, 보완 억제, 우세도 검사, 차분 공격 방지, 구간화/반올림, 필드 allowlist, 감사 로그가 필요하다.
- **Locked decision** — 억제 시 빈 화면이 아니라 억제 사유, 조건을 넓히는 방법, 데이터 범위·결측 안내를 반환한다.
- **Locked decision** — 결과마다 기간, 갱신일, 보고 데이터임을 알리는 문구, 주요 결측률, 억제 상태를 포함한다.
- **Decision required** — 최소 셀 크기, 우세도 임계값, 보완 억제 알고리즘, 금액 공개 단위, 쿼리 예산은 NIDS 개인정보·법무 승인이 필요하다.

## 결과와 후속 영향

### 긍정적 결과

- MCDM 점수의 근거 부족과 생산 결측을 서비스 가치와 분리한다.
- 공개 사용자, 인증 기업, 내부 운영자의 데이터 노출 경계가 명확해진다.
- 품목별 비교와 포트폴리오 요약을 독립적으로 검증할 수 있다.

### 비용과 리스크

- **Implementation risk** — 기존 Class 3 코드는 대부분 재사용 대상이 아니어서 신규 데이터 제품·API·UI 작업량이 크다.
- **Implementation risk** — 익명 동종집단은 entity resolution, 코호트 정의, 소수집단·우세도 통제가 없으면 제공할 수 없다.
- **Implementation risk** — 의료기관 코드 결측 때문에 `최종단` 또는 완전한 의료기관 도달률을 산출할 수 없다.
- **Implementation risk** — 품목명·품목군 검색 사전과 동의어·정규화가 아직 없다.

## 대상 파일과 완료 조건

### 향후 대상

- 공통 집계: `data_pipeline/contracts/`, `data_pipeline/aggregates/`
- 신규 Class 3: `services/class3_public_api/`, `services/class3_enterprise_api/`, `web/class3_public/`
- 공개 스키마: `schemas/openapi/class3-public.yaml`, `schemas/openapi/class3-enterprise.yaml`
- 사실 보존: `docs/data/production-calibration.md` 또는 기존 onsite 요약의 승인된 후속 문서
- 역사 참조: 기존 `class_3_impact_evaluation/`, `prototype_meeting/class_3/`, `prototype_meeting/innovation/`

경로는 **Proposed decision**이며 구현 PR에서 확정한다.

### 폐기 완료 조건

- 신규 서비스가 MCDM/Kraljic/Clinical Impact/Supply Risk DTO나 화면 문구를 참조하지 않는다.
- 기존 Class 3 진입점이 정식 배포 manifest·라우팅·CI에서 제거된다.
- 보존 사실의 출처와 날짜가 새 데이터 문서에 남는다.
- `git grep`에서 active runtime의 `mcdm`, `kraljic`, `clinical_impact`, 고정 HHI 위험 라벨 참조가 0건이다.
- 삭제는 신규 계약 테스트와 데이터 사실 이전이 완료된 별도 PR에서만 수행한다.

## 남은 결정

1. **Decision required** — 공개 비교의 정확한 동종집단 차원(업종, 지역, 규모, 품목군 조합)과 최소 표본.
2. **Decision required** — 인증 기업의 자사 소유권 검증·로그인 방식.
3. **Decision required** — 품목군/품목명 최대 선택 수와 비교 기간 기본값.
4. **Decision required** — 공개 억제·우세도·구간화 정책.
5. **Decision required** — 기존 Class 3 폴더를 언제 삭제할지, 역사 archive를 저장소 내부에 둘지 Git 이력만 사용할지.
