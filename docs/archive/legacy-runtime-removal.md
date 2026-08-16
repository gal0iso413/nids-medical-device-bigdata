# Legacy runtime removal

> Status: historical cleanup record
> Base SHA: `d2a3e87fcba1e5236556657402168a49c70fa9f5`

## Scope

This cleanup removed superseded Class 1 Streamlit/graph/Excel/model-comparison
entrypoints, the former Class 3 MCDM/Streamlit implementation, meeting
prototypes, and the prior multi-agent workspace rule.

## Reason

Those paths conflicted with the supported offline route: verified monthly
Parquet, the Class 1 GAD-NR anchor runner or Class 3 local exporter, and the
Class 1/3 React interfaces.

## Recovery

The removed code is preserved only in Git history. This record intentionally
does not reproduce an executable legacy command.
