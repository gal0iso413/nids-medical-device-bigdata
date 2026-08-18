# Class 2 웹 기술 스택 결정

> 상태: **Locked decision**
>
> 적용 대상: Class 2 공개 웹 `web/class2_public/`
>
> 적용 시작: PR-C3-UI-01A
>
> 범위: 프런트엔드 런타임·개발 도구·mock 경계
>
> 비범위: 제품 계약, 공개 정책 임계값, API 스키마, 인증 정책

## 결정 배경

- **Locked decision** — Class 2는 내부 분석 화면이 아니라 외부 공개가 가능한 업체·품목군 비교분석 서비스다.
- **Locked decision** — 목표 구조는 프런트엔드와 공개 API의 경계가 분리된 대시보드형 SPA다.
- **Locked decision** — 초기 정적 웹 셸에는 SSR, SEO, 서버 컴포넌트, 다중 route 요구가 없다.
- **Locked decision** — Historical innovation prototypes were visual reference only and are not a current web runtime; their code is available only through Git history.

## 확정 기술 선택

- **Locked decision** — Class 2 최종 웹은 React, Vite, TypeScript `strict` 모드로 구현한다.
- **Locked decision** — 패키지 관리자는 npm을 사용하고 lockfile은 `package-lock.json`으로 고정한다.
- **Locked decision** — 신규 웹의 대상 경로는 `web/class2_public/`이다.
- **Locked decision** — PR-C3-UI-01A에서는 라우터를 도입하지 않는다. 단일 정적 진입점에서 화면·상태 계약을 먼저 검증한다.
- **Locked decision** — 스타일은 CSS Custom Properties와 일반 CSS 또는 CSS Modules를 사용한다.
- **Locked decision** — Tailwind, UI component kit, 전역 상태관리, 차트 라이브러리는 실제 필요성과 수용 기준이 확인될 때까지 도입하지 않는다.
- **Locked decision** — mock fixture는 개발 전용 adapter를 통해서만 사용한다. production build 또는 production runtime은 API 실패나 설정 누락 시 mock 결과로 자동 fallback해서는 안 된다.
- **Locked decision** — 실제 공개 API 연결은 PR-C3-04와 PR-C3-UI-02에서 수행한다.

## Next.js를 채택하지 않는 이유

- **Locked decision** — 현재 Class 2 범위에는 Next.js를 채택하지 않는다.
- 현재 화면은 API 경계가 분리된 대시보드형 SPA이므로 React와 Vite만으로 요구사항을 충족한다.
- 초기 범위에는 SSR, SEO, 서버 컴포넌트, 다중 route가 필요하지 않다.
- 이 단계에서 Next.js 서버 runtime과 서버 캐시 운영을 추가하면 확인된 제품 요구 없이 배포·운영 경계만 늘어난다.
- 전체 데이터 규모는 프런트엔드 프레임워크가 아니라 오프라인 집계, 공개 API 응답 제한, 캐시, 페이지네이션으로 처리한다.
- 공개 SEO 또는 서버 렌더링 요구가 확정되면 별도 ADR에서 전환 비용과 운영 요건을 재평가한다.

## mock과 production 경계

PR-C3-UI-01A의 fixture loader는 개발 모드에서 명시적으로 선택되는 adapter다. production build는 실제 API adapter가 구성되지 않았으면 실패하거나 명시적 unavailable 상태를 보여야 하며, 개발 mock 데이터를 정상 서비스 데이터처럼 표시해서는 안 된다. 이 ADR은 mock 응답 필드나 실제 API 스키마를 확정하지 않는다.

## 시각 체계 이전 경계

혁신 시안에서는 색상, 타이포그래피, 큰 검색 영역, 카드·비교표 위계, 접근성 방향만 참고한다. 다음 정보 구조와 서비스 로직은 신규 웹으로 이전하지 않는다.

- 단일 품목 선택 흐름
- 기업군 프로필 3단계 wizard
- 생성형 진단 문장
- 성장×HHI 기회지도 중심 구조

시안 파일을 import, copy-on-build, iframe 또는 정적 자산 의존성으로 연결하지 않는다.

## 버전 정책

- **Confirmed fact** — 현재 저장소에는 등록된 GitHub Actions workflow가 없다.
- **Decision required** — 최소 지원 Node.js와 npm 버전은 PR-C3-UI-01A에서 실제 프로젝트를 생성할 때 Vite의 공식 지원 범위, 로컬 검증 환경, 배포 대상 환경을 함께 확인해 고정한다.
- **Locked decision** — 저장소 수준 GitHub Actions CI 신규 구축은 UI-01A 범위가 아니며 별도 PR에서 결정한다. UI-01A 구현 시 이미 사용할 수 있는 CI가 존재하는 경우에만 같은 검증 명령을 재사용한다.
- 이 ADR 단계에서는 Node.js/npm을 설치하거나 지원 버전을 추정해 확정하지 않는다.

## PR-C3-UI-01A 진입·완료 조건

진입 조건:

- 이 ADR의 Locked decision을 변경 없이 구현 범위에 반영한다.
- Node.js/npm 최소 지원 버전을 공식 지원 범위와 실행 환경으로 확인한다.
- mock adapter와 production adapter의 선택 방식 및 production mock fallback 금지를 테스트 가능한 계약으로 정의한다.

완료 조건:

- `web/class2_public/`에 React, Vite, TypeScript strict 기반의 라우팅 없는 정적 웹 셸이 존재한다.
- npm 외 패키지 관리자의 lockfile이 없고 `package-lock.json`이 재현 가능한 설치 기준이다.
- 불필요 도입 보류 대상 라이브러리가 dependency에 포함되지 않는다.
- production build에 mock 자동 fallback 경로가 없다.
- 혁신 시안 파일에 대한 runtime dependency가 없다.

필수 로컬 검증:

- `package.json`의 `engines`에 지원 Node.js와 npm 범위를 기록한다.
- 개발 문서에 실제 검증에 사용한 Node.js와 npm 버전을 기록한다.
- `npm install` 또는 `npm ci`의 재현성을 확인한다.
- typecheck, test, production build를 로컬에서 실행해 통과시킨다.

GitHub Actions workflow 신규 구축은 이 목록에 포함하지 않는다. UI-01A 구현 시 기존 CI가 있다면 위 명령을 재사용할 수 있지만, CI가 없다는 이유로 UI-01A에서 저장소 수준 CI를 함께 신설하지 않는다.

## 영향과 재평가 조건

이 결정은 초기 웹 셸의 의존성과 운영 복잡성을 제한한다. route, 공유 상태, 차트 상호작용이 실제 요구로 확인되면 각각 별도 근거와 테스트 범위를 갖는 후속 결정으로 추가할 수 있다. 다음 조건은 이 ADR의 재평가 사유다.

- 검색 유입을 위한 공개 SEO가 제품 요구로 승인됨
- 서버 렌더링이 성능 또는 접근성 SLO 달성에 필요함
- 다중 route와 서버 측 데이터 조합이 핵심 사용자 흐름이 됨
- 현재 SPA 배포 구조로 충족할 수 없는 보안·운영 요구가 확정됨

## 관련 문서와 참고 자료

- [Class 2 재구축 결정](class2-rebuild-decision.md)
- [Class 2 업체·품목군 비교분석 명세](../specs/class2-company-product-comparison.md)
- Historical prototype code is recoverable from Git history, not from the current runtime tree.
