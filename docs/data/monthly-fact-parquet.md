# 월 사실 Parquet 저장 계약

> 상태: PR-02 구현 계약
> 논리 계약: `fact_company_counterparty_product_month` 1.0.0
> 저장 계약: 1.0.0

## 범위

이 저장 계층은 PR-01이 검증한 업체×거래처×품목×월 `DataFrame`만 입력받는다. 원본 Excel 적재, `source_row_id` 생성, 실데이터 위치, API·DB·UI·모델 연결은 수행하지 않는다. 호출자가 `pathlib.Path`로 `output_root`를 전달하며 코드에는 기관 또는 사용자 경로가 없다.

검증 환경은 Python 3.13.12, pandas 3.0.3, pyarrow 24.0.0이다. 의존성 범위는 [`requirements-data-pipeline.txt`](../../requirements-data-pipeline.txt)에 별도로 고정한다. 다른 Parquet 엔진은 사용하지 않는다.

## 파티션 배치

```text
<output_root>/
  fact_company_counterparty_product_month/
    schema_version=1.0.0/
      month=202601/
        part-00000.parquet
        _manifest.json
```

월은 검증된 `YYYYMM`만 허용한다. Parquet와 manifest는 같은 임시 월 디렉터리에 완성한 후 최종 월 디렉터리로 이동한다. 기존 파티션은 삭제하거나 덮어쓰지 않는다. 동일 내용은 no-op이고 다른 내용, 불완전 manifest, 손상된 파일은 명시적 오류다. `force` 우회는 없다.

## 논리 스키마와 물리 스키마

컬럼 순서는 PR-01의 `MONTHLY_FACT_COLUMNS`와 같다.

- pandas `string` 계약 필드 → Arrow `string`
- pandas nullable `Int64` 계약 필드 → Arrow nullable `int64`
- `amount_sum_clean`, `raw_supply_qty_sum`, `piece_qty_sum` → Arrow `decimal128(38,6)`

논리 계약의 Decimal은 가변 정밀 Python 객체지만 저장 물리는 precision 38, scale 6으로 제한된다. writer는 반올림하지 않으며 scale 6 또는 전체 precision 38을 초과하면 `DecimalEncodingError`로 차단한다. null은 유지하고 reader는 Decimal 컬럼을 Python `Decimal`/null이 담긴 pandas `object`로, count 컬럼을 `Int64`로, 문자열을 `string`으로 복원한다. 유효한 입력을 float로 변환하지 않는다.

## 공개 함수

```python
write_monthly_fact_partitions(fact, output_root) -> WriteResult
read_monthly_fact_partitions(output_root, months=None, columns=None) -> pd.DataFrame
verify_monthly_fact_partition(output_root, month) -> PartitionVerification
monthly_fact_arrow_schema() -> pyarrow.Schema
```

`read_monthly_fact_partitions`는 요청 월만 열고 요청 컬럼만 읽는다. 일반 읽기에서는 전체 파일 SHA-256을 계산하지 않는다. 전체 컬럼은 PR-01 논리 검증을 다시 통과해야 하며 projection은 요청한 Arrow 필드와 manifest를 검증한다. 명시적 `verify_monthly_fact_partition`만 파일 크기와 전체 SHA-256을 확인한다.

## manifest

manifest는 UTF-8, key 정렬, 고정 separator의 canonical JSON이며 실행시각이나 절대·임시 경로, PC·사용자명, 원천 식별값 표본을 포함하지 않는다.

```json
{"column_order":["month","src_company_id","..."],"compression":"zstd","dataset_name":"fact_company_counterparty_product_month","decimal_encoding":{"amount_sum_clean":"decimal128(38,6)","piece_qty_sum":"decimal128(38,6)","raw_supply_qty_sum":"decimal128(38,6)"},"logical_schema_fingerprint":"<sha256>","logical_schema_name":"fact_company_counterparty_product_month","logical_schema_version":"1.0.0","parquet_file_size":1234,"parquet_sha256":"<sha256>","partition_column":"month","partition_value":"202601","relative_parquet_path":"fact_company_counterparty_product_month/schema_version=1.0.0/month=202601/part-00000.parquet","row_count":3,"source_versions":["fixture-v1"],"storage_contract_version":"1.0.0"}
```

`logical_schema_fingerprint`는 논리 스키마 이름·버전과 순서 있는 컬럼/타입 계약의 canonical JSON SHA-256이다. Parquet checksum은 물리 파일 바이트의 SHA-256이다.

## 아직 확정하지 않은 운영 정책

- 실제 기관 저장 위치와 파일시스템·object storage 선택
- 저장 암호화, 키 관리, 접근권한과 감사
- 보존기간, 파기, 백업·복구 및 재처리 승인 절차
- 생산 1,200만 행 규모의 row-group·메모리·병렬화 정책
- 원본 adapter와 manifest 계보 연결 방식

이 PR의 synthetic 검증 결과는 위 운영 정책을 확정하지 않는다.
