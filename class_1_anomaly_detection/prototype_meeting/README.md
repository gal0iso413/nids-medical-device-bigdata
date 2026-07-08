# Class 1 Meeting Prototype Guide

## Purpose

HTML prototype for stakeholder meetings. Focuses on:

- **Network map** (SVG graph, similar flow to Streamlit `app.py`)
- **Company search** (name search + ego-network drill-down)
- **AI review** (GNN priority list; click row to open network)

All names are masked sample data. Not for operational decisions.

## Files

| File | Role |
|------|------|
| `index.html` | Layout: network map + AI review tabs |
| `app.js` | Graph rendering, search, scenario switching |
| `styles.css` | UI styles |
| `data/mock_data.json` | Sample network (~70+ nodes, ~180+ edges per scenario) |
| `build_mock_data.py` | Regenerate mock data |

## Run locally

```bash
cd class_1_anomaly_detection/prototype_meeting
python -m http.server 8011
```

Open [http://localhost:8011](http://localhost:8011)

## Regenerate sample data

```bash
python class_1_anomaly_detection/prototype_meeting/build_mock_data.py
```

## Demo flow (3–5 min)

1. Select anchor month and scenario
2. **Network map** → `AI 상위 유통사 개요` to see hub pattern
3. Switch to **업체 검색** → search e.g. `C 유통` → view ego network
4. **AI 검토** tab → click a row to jump to that entity's network

## Notes

- Metrics tabs (PDI, BC, price, timelag) removed — GNN + network only
- Graph uses subgraph/ego rendering for performance (not full graph at once)
