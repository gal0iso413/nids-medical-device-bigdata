"""Tests for multi-sheet Excel header detection (first-only vs all sheets)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from class_1_anomaly_detection.src.ingest.loader import (
    _align_to_reference_columns,
    _header_overlap_ratio,
    _read_workbook_all_data_sheets,
    _sheet_has_header_row,
)


def _write_workbook(path: Path, sheets: dict[str, pd.DataFrame], *, header: dict[str, bool]) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False, header=header[name])


def test_header_overlap_ratio_basic() -> None:
    ref = ["공급자", "공급수량", "품목명"]
    assert _header_overlap_ratio(ref, ref) == 1.0
    assert _header_overlap_ratio(["a", "b", "c"], ref) == 0.0
    assert _header_overlap_ratio(["공급자", "x", "품목명"], ref) >= 0.5


def test_align_positional_and_named() -> None:
    ref = ["A", "B", "C"]
    positional = pd.DataFrame([[1, 2, 3], [4, 5, 6]])
    aligned = _align_to_reference_columns(positional, ref)
    assert list(aligned.columns) == ref

    named = pd.DataFrame({"C": [3], "A": [1], "B": [2]})
    aligned2 = _align_to_reference_columns(named, ref)
    assert list(aligned2.columns) == ref
    assert aligned2.iloc[0].tolist() == [1, 2, 3]


def test_workbook_header_only_on_first_sheet(tmp_path: Path) -> None:
    path = tmp_path / "supply_split.xlsx"
    cols = ["공급자", "공급수량", "품목명"]
    s1 = pd.DataFrame([["A사", 10, "품목1"], ["B사", 20, "품목2"]], columns=cols)
    s2 = pd.DataFrame([["C사", 30, "품목3"], ["D사", 40, "품목4"]])  # no header when written
    _write_workbook(
        path,
        {"data1": s1, "data2": s2},
        header={"data1": True, "data2": False},
    )

    assert _sheet_has_header_row(path, "data1", cols) is True
    assert _sheet_has_header_row(path, "data2", cols) is False

    out, sheets = _read_workbook_all_data_sheets(path, verbose=False)
    assert sheets == ["data1", "data2"]
    assert list(out.columns) == cols
    assert len(out) == 4
    assert out.iloc[2]["공급자"] == "C사"


def test_workbook_header_on_every_sheet(tmp_path: Path) -> None:
    path = tmp_path / "supply_headed.xlsx"
    cols = ["공급자", "공급수량", "품목명"]
    s1 = pd.DataFrame([["A사", 10, "품목1"]], columns=cols)
    s2 = pd.DataFrame([["C사", 30, "품목3"]], columns=cols)
    _write_workbook(
        path,
        {"data1": s1, "data2": s2},
        header={"data1": True, "data2": True},
    )

    assert _sheet_has_header_row(path, "data2", cols) is True
    out, _ = _read_workbook_all_data_sheets(path, verbose=False)
    assert list(out.columns) == cols
    assert len(out) == 2
    assert set(out["공급자"]) == {"A사", "C사"}
