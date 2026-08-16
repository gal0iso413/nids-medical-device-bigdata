# Class 3 공개 웹 셸

PR-C3-UI-01A의 mock 화면 계약과 라우팅 없는 정적 웹 셸에 UI-01B의 시각 체계를 적용한 구현이다. 이 디렉터리는 기존 Class 3 Streamlit·MCDM 코드 및 `prototype_meeting/innovation/class3.*`를 runtime dependency로 사용하지 않는다.

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

UI-01C의 검색·다중 선택·기간 적용은 이 fixture 범위 안에서 디자인과 사용성을 확인하기 위한 로컬 화면 상태다. 검색 후보를 fixture 밖에서 생성하지 않으며, 기간 변경으로 mock 분석값을 재계산하지 않는다. 품목별 결과와 포트폴리오 구성도 선택된 기존 계약 항목만 필터링해 표시한다.

## production 경계

- production 모드에서는 mock 설정이 있어도 mock adapter를 선택하지 않는다.
- API 오류나 API 미연결 상태에서 mock으로 자동 fallback하지 않는다.
- 현재 production API는 연결되지 않았다. production build는 성공하지만 화면에는 `서비스 데이터 연결 전` unavailable 상태가 표시된다.
- 가짜 `/api` endpoint나 production 서버 패키지를 제공하지 않는다.

## 시각 체계

`src/design/tokens.css`는 `prototype_meeting/innovation` 시안에서 승인된 navy·blue·teal·amber·danger 색상 계열, canvas와 surface, 선, radius, shadow, 1180px 콘텐츠 폭 및 타이포그래피 스케일을 신규 웹 전용 `--c3-*` 변수로 옮긴다. 슬림한 서비스 바, editorial hero, 큰 검색 패널, 상태 notice, 서로 다른 밀도의 결과·포트폴리오·관측 도달·coverage 표면, skip link와 focus-visible 패턴도 시각 언어로 계승한다.

기존 시안의 기업군 3단계 wizard, 단일 품목 흐름, 진단 문장, 기회지도, 성장×HHI 정보 구조는 가져오지 않는다. 기존 CSS·HTML·JS를 import하거나 정적 asset으로 연결하지 않으며, 현재 mock 계약과 섹션 순서를 유지한다.

외부 Pretendard CDN `@import`는 배포 보안·가용성·개인정보 정책이 확정되지 않아 사용하지 않는다. 현재는 `"Pretendard GOV"`, Pretendard, `"Apple SD Gothic Neo"`, `"Malgun Gothic"`, system-ui, sans-serif의 로컬 fallback stack만 사용한다. 폰트 self-hosting은 배포 정책 확정 후 별도 작업이다.

Cursor를 이용한 세부 시각 조정은 PR-C3-UI-01D의 후속 범위다. 실제 검색 dimension과 공개 API 연결은 PR-C3-04와 PR-C3-UI-02에서 수행한다.

## Local analysis adapter

## Local API mode

`VITE_CLASS3_DATA_SOURCE=api` selects the local Class 3 query API with the
same-origin `/api` base path. API mode verifies `/v1/status` first and does not
fall back to mock fixtures or local JSON when the API is unavailable or rejects
a request. The UI displays `local_internal_only` and
`public_release_policy=not_approved`; it is not a public service or release.

For local development only, Vite proxies `/api` to `127.0.0.1:8013`. The proxy
is development-server configuration and is not included in the production
bundle. Production API use requires a separately approved same-origin reverse
proxy and deployment configuration; no fixed localhost URL is embedded.

For the localhost integrated production host (React build plus `/api` on one
origin), see [`docs/service/class3-local-integrated-host.md`](../../docs/service/class3-local-integrated-host.md).

Terminal 1:

```powershell
python -m services.class3_local_api `
  --mart-root "D:\NIDS Local Run\class3-serving-marts" `
  --host 127.0.0.1 `
  --port 8013
```

Terminal 2:

```powershell
cd web/class3_public
$env:VITE_CLASS3_DATA_SOURCE = "api"
npm run dev
```

For the full offline execution and read-only artifact verification sequence,
see [`docs/data/local-analysis-turnkey-runbook.md`](../../docs/data/local-analysis-turnkey-runbook.md).

PR #15의 Python `serialize_class3_analysis()`가 생성한 JSON payload를 명시적으로 연결한다.
JSON 생성은 Python serializer의 책임이며, 브라우저는 Excel, Parquet, SQLite를 직접 읽지 않는다.
실제 생성 파일은 `web/class3_public/public/generated/class3-analysis.json`에 둘 수 있으며 커밋하지 않는다.

```powershell
$env:VITE_CLASS3_DATA_SOURCE = "local"
$env:VITE_CLASS3_ANALYSIS_URL = "/generated/class3-analysis.json" # local mode에서는 선택 사항
npm run dev
```

`VITE_CLASS3_DATA_SOURCE=local`일 때만 URL 미설정 시 위 기본 경로를 사용한다. payload schema나
필수 필드가 맞지 않거나 load가 실패하면 오류 상태를 보이며 mock으로 fallback하지 않는다. 화면은
`로컬 분석 데이터 · 공개 정책 미적용`으로 표시되며, 공개 서비스 승인·공개 억제·비식별 정책 적용 상태가 아니다.
