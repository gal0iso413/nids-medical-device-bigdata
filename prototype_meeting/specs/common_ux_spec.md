# Common Meeting UX Specification

## Audience

Primary participants are Korean medical-device-domain experts, typically aged
35–50, who may not have computer-science or machine-learning expertise.

They primarily want to know:

- Where is my organization or peer group now?
- What changed recently?
- Which connected organizations or market changes may affect me?
- What should I verify or discuss next?

## Shared service promise

**내 위치 확인 → 변화 이해 → 확인할 사항 발견**

The interface must answer those questions before exposing technical methods.

## Information architecture

The root meeting page introduces the two systems:

- **Class 1 유통 관계 확인:** regulator-oriented network review.
- **Class 3 우리 기업군 동향:** public, firm-oriented anonymous comparison.

Every model page includes:

1. NIDS meeting header and model switcher
2. visible “synthetic example” status
3. task-oriented primary interaction
4. result summary before detailed charts
5. “분석 기준” explanation
6. data period, source scope, and limitation text
7. glossary access

## Language rules

- Use Korean domain language first.
- Expand or avoid acronyms in primary UI.
- Replace “GNN” with “관계 구조를 학습하는 AI” in task copy.
- Replace “ego network” with “선택 업체 중심 연결망.”
- Replace “cluster” with “비슷한 기업군.”
- Use “확인 필요” rather than “불법,” “사기,” or “확정 이상.”
- Distinguish **observed value**, **model interpretation**, and **recommended
  review question**.

## Visual rules

- Base body text: at least 16 px.
- Supporting text: at least 14 px; never use it for essential instructions.
- Interactive targets: at least 44 by 44 px.
- Text contrast: at least 4.5:1.
- Use a restrained blue/teal public-service palette aligned with the NIDS
  institutional site (navy `#003675`, corporate blue, restrained green accent).
- Load **Pretendard GOV** (or equivalent) for Korean UI; do not rely on system
  fallback alone.
- Red is reserved for warnings and must be paired with text/icons.
- Avoid gradients, animation, dense decorative cards, and chart-only meaning.
- Use NIDS official assets only after brand-owner confirmation.
- Prefer conclusion-first result blocks and a compact three-step flow strip
  (`위치 확인 → 변화 이해 → 확인할 사항`) on model pages.

## Interaction rules

- One obvious primary action per page.
- Preserve selections when switching result tabs.
- Provide defaults suitable for the facilitator script.
- Never require hover to discover essential information.
- Every chart has a title, units, legend where necessary, period, and source.
- Tables remain available for people who do not read charts comfortably.
- Keyboard order follows visual order; focus is always visible.
- Errors explain what happened and how to recover.

## Meeting-data rules

- All prototype data is synthetic and generated from documented scenarios.
- No source workbook is loaded by the browser.
- No real organization name, registration number, hospital code, UDI, address,
  transaction value, or contact information is included.
- Numbers are plausible examples, not transformed real records.
- Every result page displays “간담회용 예시 데이터.”

## Shared components

- `service-header`: model title, model switcher, prototype badge
- `scope-banner`: data status, period, and limitation
- `stepper`: small guided sequence for multi-step tasks (profile picker on Class 3;
  page-level flow strip on Class 1/3)
- `conclusion-card`: plain-language summary before detailed charts
- `metric`: label, value, comparison, and definition
- `insight`: observed fact, interpretation, next question
- `method-panel`: plain explanation plus optional technical detail
- `privacy-note`: publication boundary and suppressed information
- `feedback-link`: opens the meeting feedback document/instruction

## Acceptance criteria

- A participant can identify the model purpose within 10 seconds.
- A participant can complete the primary task without facilitator intervention.
- No primary task requires understanding GNN, BC, HHI, percentile, or K-Means.
- Technical participants can still locate definitions and limitations.
- The page remains usable at 200% browser zoom and by keyboard.
- Color removal does not remove status meaning.
