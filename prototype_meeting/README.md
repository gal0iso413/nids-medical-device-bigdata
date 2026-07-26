# NIDS Expert Meeting Prototypes

This package contains synthetic, Korean-language prototypes for expert feedback
sessions. It is a presentation layer only and does not load operational NIDS
data or replace the Class 1/Class 3 analytical applications.

## Scope

- **Class 1:** Search a company, inspect its supply network, and understand why
  the system recommends review.
- **Class 3:** Define a non-identifying business profile (업종·권역·품목군),
  compare the matching cohort (거시·진단·반응), then optionally open 품목명
  market statistics (not a product index).
- **Shared:** One public-service visual system, glossary, privacy notices,
  meeting script, and feedback form.

All company, institution, product, score, and transaction values are generated
examples. They must not be used for operational or policy decisions.

## Run locally

From the repository root:

```bash
python -m http.server 8011
```

Open <http://localhost:8011/prototype_meeting/>.

The generated JSON files are committed so the demonstration works without a
build step. To regenerate them:

```bash
python prototype_meeting/class_1/build_mock_data.py
python prototype_meeting/class_3/build_mock_data.py
```

## Package map

- `index.html`: meeting landing page and model selector (혁신 시안 / 기존안)
- `innovation/`: bold redesign lab (`index.html` hub, `class1.html`, `class3.html`)
- `shared/`: common design tokens for control pages
- `class_1/`: distribution-network review control prototype
- `class_3/`: anonymous cohort dashboard control prototype
- `research/`: sourced platform and feasibility findings
- `specs/`: product, UX, analytics, and privacy specifications
- `meeting/`: facilitator guide and feedback form

## Governance

- `shared_data/` and `shared_docs/` remain read-only.
- Production model code remains in its class-specific folder.
- Class 3 clustering and publication controls described here are proposed
  future production requirements, not implemented production capabilities.
