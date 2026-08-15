# Class 1 GAD-NR / PyG compatibility

`run_gadnr()` supplies a private, invocation-scoped PyG `GCN` subclass to
PyGOD 1.1.0.  The subclass consumes exactly one keyword, `tot_nodes`, then
passes every remaining positional and keyword argument to PyG unchanged.
Unknown arguments therefore continue to fail at the PyG constructor; it is
not a general argument filter or a site-package patch.

## Why this is needed

PyGOD 1.1.0's GAD-NR detector passes its internal `tot_nodes` bookkeeping
value into `GADNRBase`, which in turn passes it to the configured backbone.
PyG 2.7.0's `GCN` passes that keyword to `GCNConv` / `MessagePassing`, raising
`TypeError: MessagePassing.__init__() got an unexpected keyword argument
'tot_nodes'`.  The affected upstream source is visible in the
[PyGOD 1.1.0 GAD-NR implementation](https://docs.pygod.org/en/v1.1.0/_modules/pygod/detector/gadnr.html);
the upstream issue tracker is
[pygod-team/pygod issues](https://github.com/pygod-team/pygod/issues).

This repository neither modifies PyGOD/PyG site-packages nor vendors their
code.  The shim applies only when the Class 1 `run_gadnr()` optional-ML path
constructs GAD-NR; graph construction, features, hyperparameters, seeds,
scores, and service/UI serialization are unchanged.

## Offline Windows CPU lock

`class_1_anomaly_detection/requirements-ml-cp313-win-cpu.lock` records the
complete hash-locked CPython 3.13 Windows x64 CPU wheel set used to verify
this path.  `torch` is the official CPU build and `pyg-lib` is from the
official PyG wheel index; the remaining wheels are from PyPI.  Install only
from a pre-downloaded directory using:

```powershell
py -3.13 -m pip install --no-index --find-links <wheelhouse> --require-hashes `
  -r class_1_anomaly_detection/requirements-ml-cp313-win-cpu.lock
```

The lock is deliberately separate from the data-pipeline dependency lock and
does not include any wheel files.
