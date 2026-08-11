# Class 3 공개 웹 셸

PR-C3-UI-01A의 mock 화면 계약과 라우팅 없는 정적 웹 셸이다. 이 디렉터리는 기존 Class 3 Streamlit·MCDM 코드 및 `prototype_meeting/innovation/class3.*`를 runtime dependency로 사용하지 않는다.

## 기술 스택과 지원 환경

- React 19.2.8
- Vite 8.2.1
- TypeScript 7.0.2 (`strict`)
- npm과 `package-lock.json`
- Vitest, jsdom, React Testing Library, Ajv는 개발·검증 전용

설치된 Vite·Vitest·jsdom의 engine 교집합에 맞춰 `package.json`의 `engines.node`를 `^20.19.0 || ^22.12.0 || >=24.0.0`으로 설정했다. Vite 자체의 범위는 [공식 Node.js 지원 문서](https://vite.dev/guide/)에서 확인할 수 있다. npm 지원 범위는 `>=10.0.0`이다.

이 PR에서 실제 검증한 환경:

- Node.js 24.18.0
- npm 11.16.0

## 설치와 검증

```powershell
npm install
npm run typecheck
npm test
npm run build
```

lockfile 기준 재현은 깨끗한 의존성 디렉터리에서 다음 명령으로 확인한다.

```powershell
npm ci
```

개발 서버는 기본적으로 서비스 데이터 미연결 상태를 표시한다.

```powershell
npm run dev
```

## 개발 mock 실행

mock은 development 모드에서 명시적으로 선택해야 한다. 기본 fixture는 `released`이며 `released`, `suppressed_small_cell`, `suppressed_dominance`, `suppressed_differencing`, `insufficient_coverage`, `not_available`, `empty` 중 하나를 선택할 수 있다.

```powershell
$env:VITE_CLASS3_DATA_SOURCE = "mock"
$env:VITE_CLASS3_MOCK_FIXTURE = "released"
npm run dev
```

mock JSON Schema와 fixture는 개발 전용 화면 계약이다. 후속 production OpenAPI 또는 공개 정책 임계값을 확정하지 않는다. 모든 fixture는 합성 데이터이며 실제 의료기기명, 업체·병원 식별자, 실제 수치를 포함하지 않는다.

## production 경계

- production 모드에서는 mock 설정이 있어도 mock adapter를 선택하지 않는다.
- API 오류나 API 미연결 상태에서 mock으로 자동 fallback하지 않는다.
- 현재 production API는 연결되지 않았다. production build는 성공하지만 화면에는 `서비스 데이터 연결 전` unavailable 상태가 표시된다.
- 가짜 `/api` endpoint나 production 서버 패키지를 제공하지 않는다.

혁신 시안의 세부 디자인 이전은 PR-C3-UI-01B에서 수행한다. 실제 공개 API 연결은 PR-C3-04와 PR-C3-UI-02의 후속 범위다.
