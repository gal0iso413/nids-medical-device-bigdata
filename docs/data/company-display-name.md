# Company display-name directory

Korean trade names from supply Excel (`공급자`, `공급받은자`) are published as a
side-channel next to monthly facts. They are not identifiers, not monthly-fact
columns, and not GAD-NR features.

```text
<output_root>/company_display_name/schema_version=1.0.0/names.parquet
```

Each license ID (`co:…` / `hosp:…`) keeps the most frequent observed name.
A tie uses the sorted name. `name_conflict` is true when more than one distinct
name was seen. Missing names stay missing; the directory does not invent labels.

## One ingest pass

Site ingest must capture names in the **same** Excel stream that emits source
rows. `run_supply_monthly_orchestration` writes this directory when it seals a
checkpoint. Do not schedule a second full workbook scan to obtain names.

The standalone catch-up builder is only for facts that were published before
this side-channel existed:

```powershell
python -m data_pipeline.ingest.company_display_name `
  --supply-workbooks C:/secure/inputs/supply.xlsx `
  --output-root D:/nids/monthly-fact
```

Class 1 lookup index schema `1.1.0` joins the directory and exposes bounded
name catalog search. Exact ID lookup remains available to the API; the internal
screen searches and displays Korean names.
