# 현장 운영 가이드 (수 09:00–목 18:00)

인터넷이 없는 Windows PC에서, **이미 빌드된 offline analysis kit**로
월별 사실을 만들고 Class 2 비교 화면과 Class 1 GAD-NR을 돌리는 순서입니다.

이 문서는 방문 시점부터 **실제로 손을 대는 순서**입니다. 새 런타임을
만들지 않습니다. 기술 계약은 키트 안의
[analysis-kit README](../../tools/offline/analysis-kit/README.md)와
[local-analysis-turnkey-runbook](local-analysis-turnkey-runbook.md)을 따릅니다.

아래 경로·업체명·파일명은 **자리 표시**입니다. 현장 값을 그대로 넣지 않은 채
이 문서를 복사해 쓰지 마십시오.

현장 PC에는 VSCode 터미널과 Excel만 있다고 봅니다. npm, Cursor, 인터넷은
쓰지 않습니다. `.ps1`은 탐색기에서 더블클릭하지 말고, 항상 터미널에서
실행합니다.

---

## 이번 방문에서 하는 일 (한눈에)

창은 **수요일 09:00부터 목요일 18:00까지(약 33시간)** 입니다.
48시간 무중단을 전제하지 않습니다. 하룻밤에 파이프라인과 앵커 6개를
한 명령으로 묶지 않습니다.

| 언제 | 무엇을 끝내는가 |
| --- | --- |
| 수 09–10 | 키트 복사·검증, Python, 런타임, 설정, 마스터 헤더 확인, 입력 점검 |
| 수 10–18 | 월별 사실 파이프라인. 점심·자리 비움은 그 명령을 그대로 둔다 |
| 수 저녁 | 파이프라인이 안 끝났으면 **목 아침 같은 명령으로 재개**가 기본 |
| 목 오전 | 파이프라인 잔여를 끝낸 뒤 **Class 2 화면을 먼저** 연다 |
| 목 오후 | Class 1 scale gate 1회 → 앵커마다 GAD-NR → 조회 색인 → Class 1 화면 |

재개는 이미 있는 월별 checkpoint와 앵커 설정 단위로만 합니다.
작업을 1시간 미만으로 일부러 쪼개지 않습니다.

`keep-session.ps1`의 `-ArgumentList`에는 스위치 이름(`-Command` 등)을
넣지 않습니다. **값만 순서대로** 넣습니다.
`Command`, `Config`, `InstallDirectory`, `LogPath`.

---

## 1. 방문 직후: 키트를 로컬 디스크에 두고 폴더를 나눈다

키트 본체는 **USB 또는 망연계**로 들어옵니다. 메일에는 이 가이드와
`analysis-kit-manifest.json`의 SHA-256 목록만 보냅니다. torch 휠은 메일
용량에 들어가지 않습니다.

USB에서 바로 돌리지 마십시오. 키트 디렉터리 **전체**를 로컬 디스크의
짧은 경로로 복사합니다. Windows 경로 길이 제한에 걸리면
`D:\nids-analysis-kit`처럼 더 짧게 옮깁니다.

Excel, 마스터 lookup, checkpoint, Parquet, 모델 출력, 현장
`field-run.toml`은 **키트 안에 넣지 않습니다.** 키트·입력·실행 산출물은
서로 다른 폴더에 둡니다. 나중에 데이터를 키트 폴더 안으로 되넣지도
마십시오.

예시 배치:

```text
D:\nids-analysis-kit\          복사한 키트 (읽기 위주)
D:\nids-analysis-runtime\      설치기가 만드는 런타임. 지금은 만들지 말 것
D:\NIDS Input\                 공급내역 Excel, 마스터 Excel만
D:\NIDS Run\                   설정·로그·산출물 (하위 폴더는 실행이 만듦)
```

직접 만들 것은 키트를 푼 폴더, `D:\NIDS Input`, `D:\NIDS Run` 정도입니다.
`checkpoints`, `monthly-facts`, `class1-output` 같은 Run 하위 폴더는
미리 만들 필요 없습니다. `D:\NIDS Run\logs`만 있으면 이후 명령이 편합니다.

**`D:\nids-analysis-runtime`은 빈 폴더라도 만들지 마십시오.** 설치기는
그 경로가 없어야 통과하고, 자기가 폴더를 만듭니다.

`D:\NIDS Input`에는 원본 Excel만 미리 복사합니다.

- 공급내역 10일 파일: `공급내역보고자료(YYYYMMDD~YYYYMMDD).xlsx`
- 마스터를 Excel로 쓸 거면 통합정보 통합문서
  (예: `통합정보등록자료(~260531).xlsx`)

하위 폴더는 필수가 아닙니다. 한곳에 모아도 되고, 나중에 toml에 경로만
맞으면 됩니다. 키트 파일, checkpoint, Parquet, 모델 산출물은 Input에
넣지 않습니다. 예전에 만들어 둔 **게시된 마스터 lookup**을 재사용할
때만 `D:\NIDS Run\master-lookup`으로 가져옵니다.

PowerShell을 열고 키트 폴더로 들어갑니다. 이후 `.\...ps1` 명령은
모두 이 위치에서 실행합니다.

```powershell
cd D:\nids-analysis-kit
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

이 Bypass는 **지금 연 터미널에만** 적용됩니다. PC 전체 정책은 바꾸지
마십시오. 터미널을 새로 열면 다시 한 줄 실행합니다.

스크립트가 실행 정책에 막히면 파일마다
`powershell -ExecutionPolicy Bypass -File .\verify-analysis-kit.ps1`
처럼 우회해도 됩니다. 파일 이름을 철자까지 맞추십시오.

---

## 2. 키트가 온전한지 확인한다

```powershell
.\verify-analysis-kit.ps1
```

성공하면 JSON 한 줄에 `verified`가 보입니다. 실패하면 복사를 다시 하고,
현장에서 키트 파일을 고치지 마십시오.

---

## 3. Python을 설치한다

키트 안의 공식 설치기 `python\python-3.13.12-amd64.exe`로
**CPython 3.13.12 x64**만 설치합니다. Microsoft Store Python, 이미 있는
3.11/3.12, 인터넷에서 받은 설치기는 쓰지 않습니다. 현장 PC에 Python이
있어도 다음 단계에서는 **이번 설치기의 `python.exe` 전체 경로**를 씁니다.

1. 탐색기에서 위 `.exe`를 실행합니다. 관리자 권한이 있으면 관리자로
   실행합니다. 설치기는 **관리자 권한이 필요할 수 있습니다.**
2. 가능하면 Customize installation으로 가서 **Install for all users**를
   켜고 위치를 `C:\Python313\`로 둡니다. 실행 파일은
   `C:\Python313\python.exe`가 됩니다.
3. 관리자가 안 되면 현재 사용자 설치도 됩니다. 그때는 보통
   `C:\Users\<계정>\AppData\Local\Programs\Python\Python313\python.exe`
   입니다. 설치기가 알려 주는 경로를 메모합니다.
4. 온라인 업데이트 항목이 있으면 끕니다. `pip install`은 하지 않습니다.

설치 확인:

```powershell
& "C:\Python313\python.exe" -c "import platform,struct; print(platform.python_implementation(), platform.python_version(), struct.calcsize('P')*8)"
```

나와야 하는 한 줄은 `CPython 3.13.12 64` 입니다. `python`만 쳐서 다른
설치본이 잡히지 않게, 항상 전체 경로로 확인합니다.

이후 venv 작성은 관리자 없이 됩니다.

---

## 4. 분석 런타임을 만든다

런타임은 키트와 **다른 폴더**에 만듭니다. 그 경로가 이미 있으면
설치기가 `InstallDirectory must be clean`으로 거절합니다. 빈 폴더로
만들어 두었다면 지우고 시작합니다.

```powershell
.\install-analysis-env.ps1 -PythonExe "C:\Python313\python.exe" -InstallDirectory "D:\nids-analysis-runtime" -KitDirectory "D:\nids-analysis-kit"
```

Python 경로가 다르면 `-PythonExe`만 바꿉니다.

venv를 만들고 키트 휠을 깔고 소스와 화면 파일을 복사합니다. 백신의
휠 검사가 이 단계를 수십 분 늘릴 수 있습니다. 중단하지 마십시오.
끝나면 JSON에 `installed`가 보입니다.

이후 분석·화면 명령은 키트 폴더의 스크립트를 쓰되, 실제 Python은 이
런타임을 씁니다. 아래 명령마다 `-InstallDirectory "D:\nids-analysis-runtime"`을
빼먹지 마십시오. 빼먹으면 스크립트가 키트 옆의 기본 경로를 찾다가
실패합니다.

---

## 5. 현장 설정 파일을 키트 밖에 만든다

키트 예시를 직접 고치지 말고 복사합니다.

```powershell
Copy-Item "D:\nids-analysis-kit\field-run.example.toml" "D:\NIDS Run\field-run.toml"
```

`D:\NIDS Run\field-run.toml`을 열어 **경로만** 현장 값으로 바꿉니다.
상대 경로는 이 toml이 있는 폴더 기준입니다. 헷갈리면 절대 경로와
슬래시(`/`)를 씁니다. UTF-8로 저장합니다.

키트 예시 맨 아래 `[class2_export]`, `[class1]` 블록은 **지금 지웁니다.**
파이프라인용 TOML은 `config_version`, `[paths]`, `[master]`, `[run]`만
허용합니다. Class 1·Class 2 JSON은 목요일에 따로 둡니다.

Input에 뭐가 있는지는 이렇게 봅니다.

```powershell
Get-ChildItem "D:\NIDS Input" -File | Select-Object Name
```

공급내역 목록은 손으로 따옴표를 달지 말고, 터미널에서 만들어 붙여
넣습니다.

```powershell
Get-ChildItem "D:\NIDS Input" -File -Filter "공급내역보고자료*.xlsx" |
  Sort-Object Name |
  ForEach-Object { '  "{0}",' -f ($_.FullName -replace '\\','/') }
```

나온 줄을 `supply_workbooks = [`와 `]` 사이에 넣습니다. 파이프라인은
월별로 묶어 **파일이 정확히 3개인 달만** 게시합니다.
`통합정보등록자료`는 이 목록에 넣지 말고 `[master]`의 `workbooks`에만
둡니다.

이번이 첫 방문이고 마스터 Excel이 있으면, 예시의
`source_hash = "0000..."`는 **지우고** `workbooks`를 씁니다. 가짜 해시로
두면 게시된 lookup을 찾다가 실패합니다. 둘 다 넣거나 둘 다 빼면
실패합니다. 마스터 lookup을 바꿔도 **이미 닫힌 월은 다시 조인하지
않습니다.**

```toml
config_version = "1.1.0"

[paths]
supply_workbooks = [
  "D:/NIDS Input/공급내역보고자료(20210701~20210710).xlsx",
  "D:/NIDS Input/공급내역보고자료(20210711~20210720).xlsx",
  "D:/NIDS Input/공급내역보고자료(20210721~20210731).xlsx",
]
checkpoint_root = "D:/NIDS Run/checkpoints"
output_root = "D:/NIDS Run/monthly-facts"

[master]
lookup_root = "D:/NIDS Run/master-lookup"
workbooks = ["D:/NIDS Input/통합정보등록자료(~260531).xlsx"]

[run]
batch_size = 10000
max_month_fact_bytes = 536870912
minimum_free_bytes = 0
```

`checkpoint_root`와 `output_root`는 서로 다른 폴더여야 합니다. 폴더는
아직 없어도 됩니다. `minimum_free_bytes`를 `0`으로 두면 preflight가
경고만 하고 통과할 수 있습니다. 현장 하한이 있으면 바이트 숫자로
넣습니다.

### 마스터 헤더를 파이프라인 전에 본다

마스터 Excel의 데이터 시트 **1행**에 아래 세 이름이 글자 그대로 있어야
합니다. 열 글자(`BK`/`BL`/`BM`)는 보통 이 세 칸입니다.

- `의료기기품목일련번호`
- `모델일련번호`
- `UDIDI일련번호` (공급내역의 `UDI-DI 일련번호`와 철자가 다릅니다)

같은 1행에 **`업종`이 두 번** 있으면 파이프라인이
`Duplicate headers`로 거절합니다. 마스터 lookup은 업종을 쓰지 않습니다.
데이터 칸은 건드리지 말고, **뒤쪽 `업종` 헤더 글자만** `업종2`로
바꿉니다. 첫 번째 `업종`은 그대로 둡니다. 시트가 여러 개면 같은 중복이
있는 시트도 같이 고칩니다. 저장한 뒤 Excel을 닫습니다.

Class 1 앵커 JSON은 **앵커 월마다 하나**입니다. 최신 완료 앵커 6개에
설정 파일을 따로 두고, 각각을 가리키는 `field-run-YYYYMM.toml`도 키트
밖에 둡니다. 그 파일에는 `[class1] config`가 있어도 됩니다. 파이프라인용
`field-run.toml`과는 분리합니다.

Class 1 완료는 최신 완료 앵커 6개입니다. 앵커 `M`은 Parquet `M-5`부터
`M`까지를 읽으므로, 그 여섯 앵커를 돌리려면 디스크에 최근 닫힌 월이
**11개월** 있어야 합니다. Class 1 JSON에서 `region_vocabulary`는 비우지
않습니다. 정렬되고 중복 없는 값이어야 합니다. Class 1 출력 폴더는 월별
사실 폴더와 겹치거나 그 안에 두면 안 됩니다.

---

## 6. 입력과 디스크를 점검한다 (수 09–10의 마지막)

preflight는 Excel을 한 줄씩 읽지 않습니다. 파일이 있는지, 쓸 수 있는지,
공간이 충분한지만 봅니다. 통과가 데이터 무결성 확인은 아닙니다.

공급내역·마스터 Excel을 Excel에서 **닫습니다.** 파이프라인이 길어지므로
처음부터 `keep-session.ps1`로 감쌉니다. 이 스크립트는 **시스템 절전만**
막습니다. 화면이 꺼져도 CPU가 살아 있으면 됩니다. 노트북 **덮개를 닫으면
절전될 수 있으므로**, 전원 옵션에서 덮개 닫기를 “아무 것도 안 함”으로
두거나, 덮개를 연 채로 둡니다.

```powershell
.\keep-session.ps1 -LogPath "D:\NIDS Run\logs\preflight.log" -File .\run-analysis.ps1 -ArgumentList @("preflight","D:\NIDS Run\field-run.toml","D:\nids-analysis-runtime","D:\NIDS Run\logs\preflight.cmd.log")
```

성공하면 JSON에 `"ok": true`가 보입니다. `minimum_free_bytes`를 0으로 둔
경우 `warn`이 섞여도 **`fail`만 없으면** 통과입니다.

실패하면 설정 경로, Excel 위치, 마스터 `workbooks`/`source_hash`, 디스크
여유를 고친 뒤 같은 명령을 다시 실행합니다.

---

## 7. 수요일 오전부터: 월별 사실 파이프라인을 돌린다

입력이 준비되면 바로 파이프라인을 시작합니다. GAD-NR이나 Class 2 화면은
아직 하지 않습니다. **파이프라인과 GAD-NR을 동시에 돌리지 않습니다**
(메모리). 진행 확인만 다른 터미널에서 합니다.

파이프라인이 Excel을 읽는 동안 **같은 통합문서를 Excel에서 열지 마십시오.**
파일 잠금으로 실패합니다.

```powershell
.\keep-session.ps1 -LogPath "D:\NIDS Run\logs\pipeline.log" -File .\run-analysis.ps1 -ArgumentList @("pipeline","D:\NIDS Run\field-run.toml","D:\nids-analysis-runtime","D:\NIDS Run\logs\pipeline.cmd.log")
```

처음 두 줄만 보이고 오래 조용한 것이 정상입니다.

```text
keep-session log=D:\NIDS Run\logs\pipeline.log
keep-session system sleep is blocked; the display may still turn off.
```

마스터 lookup(수백만 행)을 만든 뒤, 닫힌 달마다 공급내역 3개 파일을
읽어 checkpoint와 Parquet를 만듭니다. 공급내역이 많으면 수 시간 갈 수
있습니다. 진행률 숫자는 거의 안 나옵니다. `Workbook contains no default
style` 경고는 오류가 아닙니다.

점심이거나 자리를 비울 때도 이 창을 끄지 않습니다. 화면만 꺼져도 됩니다.
작업 관리자에서 `python.exe`가 CPU·디스크를 쓰면 돌아가고 있는 것입니다.

| 위치 | 무엇을 보나 |
| --- | --- |
| `D:\NIDS Run\logs\pipeline.log` | keep-session이 화면 출력을 저장 |
| `D:\NIDS Run\logs\pipeline.cmd.log` | 파이프라인 명령 기록 |
| `D:\NIDS Run\master-lookup\` | 마스터 lookup이 생기면 그 단계가 지난 것 |
| `D:\NIDS Run\checkpoints\` | 월별 checkpoint가 생기는지 |
| `D:\NIDS Run\monthly-facts\` | 게시된 Parquet |

진행만 보려면 **다른** PowerShell에서:

```powershell
cd D:\nids-analysis-kit
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\status-analysis.ps1 -Config "D:\NIDS Run\field-run.toml" -MartRoot "D:\NIDS Run\class2-mart" -InstallDirectory "D:\nids-analysis-runtime"
```

이 명령은 checkpoint 봉인/완료 매니페스트, 월 사실 `_manifest.json`,
Class 1 `run-manifest.json`, Class 2 mart `_manifest.json`만 읽습니다.
Excel과 Parquet는 다시 열지 않습니다.

끝나면 JSON이 나오고 프롬프트가 돌아옵니다. 끊기면 checkpoint를 지우거나
고치지 마십시오. **같은 config로 같은 명령을 다시** 실행합니다. 이미
봉인·게시된 월은 다시 쓰지 않습니다. 한 달에서 행 ID 충돌 같은 데이터
오류가 나면 그달은 게시하지 않고 다음 닫힌 달로 넘어갑니다. 로그에
`skipped_source_error`와 월이 남습니다. 디스크 잠금이나 메모리 한도는
그달에서 멈추므로 같은 명령을 다시 치면 됩니다.

고객 직원에게 밤새 전원 유지를 부탁하는 것은 **최후 수단**입니다.
기본은 수요일 저녁에 PC를 정상 종료해도 되고, 목요일 아침에 같은
파이프라인 명령을 다시 치는 것입니다.

---

## 8. 목요일 오전: 파이프라인을 끝낸 뒤 Class 2를 먼저 연다

자리에 앉으면 먼저 상태부터 봅니다 (`status-analysis.ps1`, 7절과 동일).
파이프라인이 안 끝났으면 7절과 **같은** keep-session + pipeline 명령을
다시 실행해 잔여 월만 이어 갑니다.

파이프라인이 끝나면 GAD-NR을 기다리지 말고 Class 2 serving mart를
만듭니다. `-PeriodStart`/`-PeriodEnd`는 넣지 않습니다. 검증된 사실 월
전체를 담습니다.

```powershell
.\build-class2-serving-marts.ps1 -FieldRunConfig "D:\NIDS Run\field-run.toml" -FactRoot "D:\NIDS Run\monthly-facts" -OutputRoot "D:\NIDS Run\class2-mart" -InstallDirectory "D:\nids-analysis-runtime"
.\serve-class2-site.ps1 -MartRoot "D:\NIDS Run\class2-mart" -InstallDirectory "D:\nids-analysis-runtime"
```

브라우저에서 `http://127.0.0.1:8012` 를 엽니다. 이 PC의 localhost이며
공개 서비스가 아닙니다. 이 화면이 목요일 오전에 보여줄 결과입니다.

---

## 9. 목요일 오후: Class 1을 돌리고 화면을 연다

Class 2 화면을 띄운 뒤에 Class 1을 시작합니다. 파이프라인이 아직
돌고 있으면 Class 1을 겹쳐 실행하지 마십시오.

scale gate는 **한 번** 측정합니다. 그래프를 지역/품목으로 자르지 않습니다.
실패하면 GAD-NR을 시작하지 않고 중단합니다.

```powershell
.\run-class1-graph-scale-gate.ps1 -Config "D:\NIDS Run\class1-graph-scale-gate.json" -Report "D:\NIDS Run\reports\class1-graph-scale-gate.json" -InstallDirectory "D:\nids-analysis-runtime"
```

통과하면 최신 완료 앵커마다, 그 앵커용 `field-run-YYYYMM.toml`로
하나씩 돌립니다. 한 명령에 여섯 앵커를 묶지 않습니다. 앵커 하나가
실패해도 다음 앵커 설정만 다시 돌립니다.

```powershell
.\keep-session.ps1 -LogPath "D:\NIDS Run\logs\class1-202403.log" -File .\run-analysis.ps1 -ArgumentList @("class1-run","D:\NIDS Run\field-run-202403.toml","D:\nids-analysis-runtime")
```

각 앵커가 끝나면 그 월의 조회 색인을 만듭니다.

```powershell
.\build-class1-lookup-index.ps1 -FactRoot "D:\NIDS Run\monthly-facts" -RunRoot "D:\NIDS Run\class1-output" -OutputRoot "D:\NIDS Run\class1-index" -AnchorMonth 202403 -InstallDirectory "D:\nids-analysis-runtime"
```

여섯 앵커의 색인이 있으면 Class 1 화면을 엽니다.

```powershell
.\serve-class1-site.ps1 -IndexRoot "D:\NIDS Run\class1-index" -InstallDirectory "D:\nids-analysis-runtime"
```

브라우저는 `http://127.0.0.1:8011` 입니다. Class 2와 같이 띄울 때는
이미 연 serve 창을 끄고 아래를 씁니다.

```powershell
.\serve-analysis-sites.ps1 -IndexRoot "D:\NIDS Run\class1-index" -MartRoot "D:\NIDS Run\class2-mart" -InstallDirectory "D:\nids-analysis-runtime"
```

Class 1은 `8011`, Class 2는 `8012`입니다. 둘 다 이 PC의 localhost입니다.

---

## 10. 목요일 18:00 전: 자리를 정리한다

화면 확인이 끝나면 serve 창을 종료합니다. 산출물은 Run 폴더에 남겨 두고,
반출 승인이 없는 파일은 USB로 가져가지 않습니다. 키트 폴더의
`sites/*/generated`에 분석 JSON을 넣지 않습니다.

상태 표기는 `local_internal_only`, `public_release_policy=not_approved`
입니다. 현장 검증은 생산·공개 승인이 아닙니다.

---

## 하지 말 것

- 인터넷, npm, 현장 Node, Streamlit
- `.ps1`을 탐색기에서 더블클릭하기
- 키트 `sites/*/generated`에 분석 JSON 넣기
- 파이프라인용 `field-run.toml`에 `[class1]` / `[class2_export]` 남기기
- `keep-session`의 `-ArgumentList`에 `-Command` 같은 스위치 이름을 넣기
- 파이프라인과 GAD-NR 병렬 실행
- 사용량 때문에 인위적으로 작업을 잘게 쪼개거나 그래프를 슬라이스하기
- 데이터를 USB 키트 폴더 안으로 되넣거나 반출 승인이 없는 산출물을 반출하기
- 고객 직원 상주 모니터링을 기본 경로로 삼기
- checkpoint·게시된 월 사실·완료된 앵커 출력을 지워서 “처음부터 다시”
- 마스터 1행의 뒤쪽 `업종` 헤더를 고치지 않은 채 파이프라인만 반복하기
