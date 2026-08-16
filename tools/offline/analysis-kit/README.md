# Complete offline analysis kit

This directory builds a separate, immutable kit for the existing local analysis
contracts. It does not alter the older pipeline-only field kit. The builder is
run on an internet-connected preparation PC; every install, verification,
analysis, and static-site serving action in the resulting kit is offline.

The runtime is CPython 3.13.12 Windows x64 and its single hash-locked
wheelhouse. `run-analysis.ps1` only delegates to the existing field runner,
Class 3 exporter, Class 1 anchor runner, and Class 1 safe handoff publisher.
It contains no pipeline or model implementation.
