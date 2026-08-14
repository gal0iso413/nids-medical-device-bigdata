# Class 3 public web

React/Vite 화면입니다. 로컬 분석 모드는 PR #15의 Python
`serialize_class3_analysis()`가 만든 JSON payload만 읽습니다. 브라우저가 Excel,
Parquet, SQLite를 직접 읽거나 HTTP/FastAPI 백엔드에 연결하지 않습니다.

## Install and verify

```powershell
npm ci
npm run typecheck
npm test
npm run build
```

## Local analysis mode

먼저 Python serializer로 JSON을 생성하고, 생성 파일은 커밋하지 않습니다. 기본 위치는
`web/class3_public/public/generated/class3-analysis.json`이며 이 디렉터리는 ignore됩니다.

```powershell
$env:VITE_CLASS3_DATA_SOURCE = "local"
$env:VITE_CLASS3_ANALYSIS_URL = "/generated/class3-analysis.json" # optional in local mode
npm run dev
```

`VITE_CLASS3_ANALYSIS_URL`이 없더라도 `VITE_CLASS3_DATA_SOURCE=local`일 때만 위 기본
경로를 사용합니다. 로컬 JSON의 schema version 또는 필수 필드가 맞지 않거나 불러오기에
실패하면 명시적인 오류 상태를 표시하며 mock으로 fallback하지 않습니다.

로컬 모드는 화면에 `로컬 분석 데이터 · 공개 정책 미적용`으로 표시됩니다. 이는 공개
서비스 승인, 공개 억제, 비식별 정책 적용 상태가 아닙니다.

## Development mock mode

합성 fixture는 development에서 명시적으로만 사용할 수 있습니다.

```powershell
$env:VITE_CLASS3_DATA_SOURCE = "mock"
$env:VITE_CLASS3_MOCK_FIXTURE = "released"
npm run dev
```

Production에서 source를 지정하지 않으면 기존 unavailable 상태를 유지합니다. mock fixture와
Ajv 검증기는 development mock 경로에서만 동적으로 가져오며 production bundle에 포함하지
않습니다.
