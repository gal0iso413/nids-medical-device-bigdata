# Company display-name directory

Korean trade names from supply Excel (`공급자`, `공급받은자`) are published as a
side-channel next to monthly facts. They are not identifiers, not monthly-fact
columns, and not GAD-NR features.

```text
<output_root>/company_display_name/schema_version=1.1.0/
  names.parquet
  month=YYYYMM/names.parquet
```

Each license ID (`co:…` / `hosp:…`) keeps the name from the **earliest logical
month** (`first_name_order=logical_month_ascending`). Later months that disagree
set `name_conflict` and do not replace the earlier name. Missing names stay
missing; the directory does not invent labels. Wall-clock ingest order is not
the merge key.

## One ingest pass

Site ingest must capture names in the **same** Excel stream that emits source
rows. `run_supply_monthly_orchestration` writes this directory when it seals a
checkpoint. Do not schedule a second full workbook scan to obtain names.

The standalone catch-up builder is only for facts that were published before
this side-channel existed:

```powershell
python -m data_pipeline.ingest.company_display_name `
  --supply-workbooks C:/secure/inputs/공급내역보고자료(20240301~20240310).xlsx `
  --output-root D:/nids/monthly-fact
```

Class 1 lookup index schema `1.2.0` joins the directory and exposes bounded
name catalog search per `anchor_month` partition. Exact ID lookup remains available to the API; the internal
screen searches and displays Korean names.
