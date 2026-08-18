# PROGRESS — class_1_anomaly_detection

- Phase 1 EDA: **ACTIVE** (phase-gate locked; no auto-advance)
- Onsite Visit 1 (2026-06-18): profile imported → `notes/eda_profile_onsite_2026-06-18.md`
- Shared calibration: `shared_docs/structured/onsite_visit1_summary.md`
- 3-key join PASS (99.97%); UDI-only inflation FLAG (107.03%)
- Graph: 공급자 9.5k / 공급받은자 62k nodes; 요양기관기호 null 54.6% — hospital path coverage risk
- Price outliers FLAG — sanitize before Z-score; 제조원국가 99.6% null — no country proxy
- Awaiting PM direction on open FLAGs before Phase 2 unlock
- PyG adapter: `src/experiments/export_pyg_graph.py` → `output/pyg/` (14,304 nodes, 19,643 edges, 17-dim features)
- PyGOD DOMINANT smoke PASS → `output/ml/entity_anomaly_scores_dominant.csv` (1,431 flagged; 0/50 BC overlap)
- PyGOD compare PASS: DOMINANT + AnomalyDAE + GADNR → `output/ml/pygod_model_comparison.json`
- Step 4 eval PASS: GAD-NR recommended → `output/ml/step4_evaluation.md`
- Anomaly measures PASS: OCGNN + IsoForest (GAD-NR emb) → `output/ml/entity_anomaly_scores_{ocgnn,isoforest}.csv`
