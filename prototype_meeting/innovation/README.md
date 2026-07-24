# Innovation Lab

Bold redesign of the meeting prototypes: NIDS navy/teal trust + modern B2B layout.

## Open

From repo root:

```bash
python -m http.server 8011
```

- Hub: http://localhost:8011/prototype_meeting/innovation/
- Class 1: http://localhost:8011/prototype_meeting/innovation/class1.html
- Class 3: http://localhost:8011/prototype_meeting/innovation/class3.html

Control (기존안) pages remain at `../class_1/` and `../class_3/`.

## Demo scripts

**Class 1 (3–4 min):** default `C 유통` → read hero brief → 최근 변화 → spotlight 1-hop → review deck → open a case.

**Class 3 (3–4 min):** keep defaults → 리포트 생성 → peer portrait → report → 품목 검토 지도.

## Data

Fetches existing mock JSON:

- `../class_1/data/mock_data.json`
- `../class_3/data/mock_data.json`
