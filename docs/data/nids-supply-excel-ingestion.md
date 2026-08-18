# NIDS 공급내역 Excel 적재 계약

> 상태: PR-03A 구현 계약
> Adapter contract: `1.0.0`
> 다음 단계: PR-03B master 3-key join·월 집계·Parquet publication

## 범위와 생산 근거

이 adapter는 NIDS 공급내역 Excel을 `openpyxl`의 `read_only=True`, `data_only=True`로 순회해 PR-01의 정규화 전 source row 계약으로 변환한다. sheet 전체를 `pandas.read_excel`로 적재하지 않으며 호출자가 지정한 `batch_size` 이하의 `DataFrame`만 방출한다. 원본 master join, `aggregate_company_counterparty_product_month`, `write_monthly_fact_partitions`는 호출하지 않는다.

생산 규모의 우선 근거는 [`onsite_visit1_summary.md`](../../shared_docs/structured/onsite_visit1_summary.md)다. 확인된 공급 데이터는 12개 workbook, 4개월 12,000,000행, 71열이고 장기 보유 범위는 2020-08~2026-04다. 이번 PR은 synthetic workbook만 검증했으며 실제 production/top7 파일을 읽지 않았다.

검증 환경은 Python 3.13.12, pandas 3.0.3, openpyxl 3.1.5다. 지원 범위는 [`requirements-data-pipeline.txt`](../../requirements-data-pipeline.txt)에 기록한다.

## 공개 API

```python
create_source_lineage(workbook_paths) -> SourceLineage
discover_supply_sheets(workbook_path, header_scan_limit=12) -> tuple[DiscoveredSheet, ...]
stream_nids_supply_excel(workbook_paths, batch_size=10_000, header_scan_limit=12) -> SupplyExcelStream
```

`SupplyExcelStream`은 한 번만 순회할 수 있고 `close()`를 여러 번 호출해도 안전하다. `lineage`는 순회 전에도 사용할 수 있고 `report`는 순회하면서 누적된다. workbook은 정상·오류·generator 종료 경로에서 닫힌다. adapter는 batch를 반환할 뿐 전체 결과를 내부에 누적하지 않는다. 조기 종료가 가능한 호출자는 context manager를 사용한다.

```python
with stream_nids_supply_excel(paths) as stream:
    for batch in stream:
        consume(batch)
        if condition:
            break
```

context 종료는 활성 generator를 즉시 닫아 workbook의 `finally`를 실행한다. 닫힌 stream 또는 한 번 완료된 stream은 다시 순회할 수 없다.

## Content-based sheet discovery

sheet 이름과 위치는 계약이 아니다. 각 sheet의 처음 최대 12행에서 공급일자, 공급구분, 공급자 일련번호, 공식 행 식별 구성요소와 3-key anchor가 포함된 헤더를 찾는다. 일치 sheet는 이름 기준으로 정렬해 모두 읽는다. metadata sheet도 이름만으로 제외하지 않는다.

다음 상태는 `DataSheetDiscoveryError`다.

- 일치하는 data sheet 없음
- 같은 헤더 행의 중복 열 이름
- 제한 범위에 둘 이상의 후보 헤더 행
- 하나의 논리 필드에 복수 alias가 동시에 존재

data sheet 발견 직후 실제 행 순회 전에는 필수 논리 구조를 별도로 검증한다. `supply_date`, `src_company_id`, `transaction_type`, 공식 3-key, `raw_supply_qty`, 공식 행 식별 4개 필드가 모두 있어야 한다. 수령자는 `dst_company_id` 또는 `hospital_id` 원본 열 중 하나 이상이 있어야 한다. 누락 시 workbook 논리명, sheet명과 누락 논리 필드만 포함한 `DataSheetSchemaError`로 조기 차단한다. 금액·포장/낱개수량과 선택 dimension은 열 결측을 profile에 기록하되 streaming을 허용한다.

헤더 탐색 상한을 초과해 전체 sheet를 탐색하지 않는다. 필수 매핑 열 결측과 소비하지 않는 추가 열은 workbook/sheet profile에 기록한다.

## Source snapshot과 행 식별자

각 workbook의 논리 파일명, byte 크기, 전체 SHA-256과 adapter contract version을 정렬된 canonical UTF-8 JSON으로 직렬화하고 다시 SHA-256 해시해 `source_version`을 만든다. 절대 경로와 입력 순서는 포함하지 않는다. 같은 논리 파일명은 한 snapshot에서 중복될 수 없다. 파일 내용이나 구성 파일 집합이 바뀌면 `source_version`도 바뀐다.

`source_row_id`는 다음 공식 integer-code 구성요소를 공백·dtype 차이 없이 정규화한 canonical JSON SHA-256이다.

- 거래처 코드
- 공급내역기준연월
- 공급내역작업일련번호
- 공급내역일련번호

파일명, sheet명, 물리 행 번호는 정상 ID에 들어가지 않는다. 구성요소가 하나라도 불완전하면 `blocked:deduplication_unverified`로 report에 기록하고 정상 batch에서 제외한다. `공급내역보고자료복합Key`는 존재·결측 및 “복합키는 있지만 공식 구성요소 ID는 불완전”한 건수만 품질 비교한다. 형식을 추측하거나 ID fallback으로 사용하지 않는다. workbook checksum 목록은 별도 `SourceLineage`에만 있고 월 사실 행에 복제하지 않는다.

## 필드 매핑

| NIDS 원본 | PR-01 source | 처리 |
|---|---|---|
| 공급일자 | `supply_date` | `YYYYMMDD`/날짜를 일 단위 Timestamp로 검증 |
| 공급한자 업체일련번호 | `src_company_id` | 공식 integer code 정규화 후 `co:` |
| 공급받은자 업체일련번호 | `dst_company_id` | 유효하면 `co:` |
| 요양기관기호(의료기관) | `dst_company_id` | 업체일련번호가 없을 때만 `hosp:`; 품질 flag 추가 |
| 의료기기품목일련번호 | `item_serial` | 공식 integer code |
| 모델일련번호 | `model_serial` | 공식 integer code |
| UDI-DI 일련번호 | `udi_serial` | 공식 integer code |
| 품목군 | `item_group_id` | 공백 정리, 품목명으로 대체하지 않음 |
| 품목명 | `item_name_id` | 공백 정리 |
| UDI-DI | `udi` | 문자열, 선행 0 보존 |
| 업종 / 공급받은자업종 | `supplier_type` / `receiver_type` | 선택 문자열 |
| 공급한자 / 공급받은자 소재지 시도코드 | `supplier_region` / `receiver_region` | 문자열, 선행 0 보존 |
| 공급금액 | `amount_clean` | float를 거치지 않은 non-negative Decimal 또는 null |
| 공급수량 | `raw_supply_qty` | float를 거치지 않은 non-negative Decimal 또는 null |
| 낱개총수량 | `piece_qty` | 공식 값과 `공급수량 × 포장내 총 수량`이 모두 유효하고 일치할 때만 전달 |
| snapshot hash | `source_version` | `nids-supply-v1:<sha256>` |
| 공식 4개 구성요소 hash | `source_row_id` | `nids-row-v1:<sha256>` |

회사명·사업자등록번호는 ID fallback으로 사용하지 않는다. 수령 업체일련번호와 요양기관기호가 모두 없으면 행을 차단한다. 불완전 3-key도 정상 batch에서 제외한다.

선택 열 `공급자`와 `공급받은자`는 같은 순회에서 면허 ID별 한글 표시명으로만 누적한다. source batch·월 사실·GAD-NR 피처에는 넣지 않는다. 게시 위치와 사이트 한 패스 규칙은 [`company-display-name.md`](company-display-name.md)를 따른다.

## 거래·Decimal·품질 계약

거래 유형은 `출고→SUPPLY`, `반품→RETURN`, `회수→RECALL`, `폐기→DISCARD`, `임대→LEASE`만 표준화한다. 알 수 없는 값은 원문을 보존하고 `transaction_type_unknown`으로 표시하며 `SUPPLY`로 바꾸지 않는다. PR-01 집계 계약이 RETURN/RECALL과 지원하지 않는 유형을 승인 전 차단한다.

금액·수량은 문자열, 정수 또는 `Decimal`에서만 변환한다. Python float, non-finite, 비숫자와 음수는 정상값으로 인정하지 않고 null과 품질 flag로 반환한다. 낱개수량 불일치 또는 검증 불가는 null이다. adapter가 `공급수량 × 포장내 총 수량`을 계산해 공식 값을 대체하지 않는다. 금액과 수량을 합성 weight로 만들지 않는다.

공급금액은 삭제·cap·winsorize·반올림하지 않는다. 50,000,000원 초과는 `amount_high_value_review`, 1e12 초과는 `amount_barcode_entry_error_suspected`로 기록하고 건수와 최대값을 report에 남긴다. 생산 집계에 포함할 최종 정책은 승인 전이다.

`SupplyIngestionReport`는 sheet별 읽은/방출 행, 필수·추가 열, 거래 유형 수와 다음 bounded issue를 보유한다.

- source identity, 공급자/수령자, 3-key 불완전
- 날짜·금액·수량 변환 실패
- 낱개수량 불일치·검증 불가
- 알 수 없는 거래 유형
- high-value·barcode 의심
- 원본 복합키 존재·결측

각 issue는 전체 건수와 최대 20개 위치 또는 `source_row_id`, 나머지 omitted 건수만 보유한다. 회사명, 사업자등록번호, 전체 원시 행은 진단에 포함하지 않는다.

배제 행은 첫 번째로 확정된 사유 하나만 `rejected_by_reason`에 기록한다. 순서는 source identity → 공급자/수령자 identity → 3-key → 날짜 검증이다. Decimal 결측·극단값·낱개수량 불일치는 행을 배제하지 않으므로 exclusive reject 집계에 들어가지 않는다. 전체 순회 완료 시 report는 다음 불변식을 검증한다.

```text
rows_read == rows_emitted + rows_rejected
rows_rejected == sum(rejected_by_reason.values())
```

## PR-03B 연결점

PR-03B는 이 stream의 정상 batch를 받아 master의 정규화된 `의료기기품목일련번호 × 모델일련번호 × UDI-DI 일련번호`와 join한다. UDI-only join은 금지한다. join 품질과 lineage를 확인한 뒤에만 PR-01 월 집계를 호출하고, 검증된 fact를 PR-02 writer에 전달한다. PR-03A는 이 단계를 선행하거나 암묵적으로 실행하지 않는다.

## 남은 생산 리스크

- 12,000,000행에서 openpyxl XML 순회 속도와 CPU 비용 미측정
- batch DataFrame과 openpyxl 내부 buffer의 peak memory 미측정
- workbook별 sheet 수·헤더 위치·열 drift의 전체 분포 미확인
- Excel fractional numeric cell이 openpyxl에서 Python float로 노출되는 생산 빈도 미확인; PR-03A는 정밀도 계약상 이를 정상 Decimal로 추정 변환하지 않음
- Windows 장경로, 잠금, 손상 workbook 복구 정책 미확정
- 극단 공급금액의 최종 포함·차단·보정 정책 미승인
- PR-03B의 master snapshot 계보와 join 실패 격리 방식 미구현
