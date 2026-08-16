# Integrated offline analysis Python environment

The complete analysis kit uses the PR-24 verified CPython 3.13.12 Windows x64
CPU ML set as its baseline: NumPy 2.4.3, pandas 3.0.2, tzdata 2026.3, torch
2.11.0+cpu, torch-geometric 2.7.0, pyg-lib 0.8.0+pt211cpu, PyGOD 1.1.0, and
scikit-learn 1.8.0.  It does not adopt the data-only kit's newer NumPy/pandas
or older tzdata pins.

`tools/offline/analysis-kit/requirements-analysis-kit-win-py313.lock` contains
the 40 exact hash-pinned ML requirements and adds only pyarrow 24.0.0, openpyxl
3.1.5, and et-xmlfile 2.0.0 for the existing data pipeline. No version range,
CUDA wheel, index access, or resolver-selected dependency is permitted at
field installation time.

This is 43 unique distributions. The downloaded but unrequired
`setuptools-84.0.0` wheel is explicitly excluded: the lock pins only
`setuptools==78.1.0`, so a second setuptools distribution would violate the
one-requirement/one-wheel contract.
