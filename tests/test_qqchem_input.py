"""Tests for qqchem.qchem_input — input parsing and mem_total adjustment."""

from __future__ import annotations

from pathlib import Path

import pytest

from qqchem.qchem_input import adjust_mem_total, parse_mem_total, read_input_file


class TestReadInputFile:
    def test_reads_lines(self, tmp_path: Path) -> None:
        p = tmp_path / "job.in"
        p.write_text("line1\nline2\n")
        assert read_input_file(p) == ["line1\n", "line2\n"]

    def test_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_input_file(tmp_path / "nope.in")


class TestParseMemTotal:
    def test_single_value(self) -> None:
        lines = ["$rem\n", "   mem_total 4000\n", "$end\n"]
        assert parse_mem_total(lines) == [4000]

    def test_with_equals(self) -> None:
        lines = ["$rem\n", "mem_total = 8000\n", "$end\n"]
        assert parse_mem_total(lines) == [8000]

    def test_no_mem_total(self) -> None:
        lines = ["$rem\n", "method b3lyp\n", "$end\n"]
        assert parse_mem_total(lines) == []

    def test_multiple_blocks(self) -> None:
        lines = [
            "$rem\nmem_total 1000\n$end\n",
            "$rem\nmem_total 2000\n$end\n",
        ]
        assert parse_mem_total(lines) == [1000, 2000]


class TestAdjustMemTotal:
    def test_replaces_existing(self) -> None:
        lines = ["$rem\n", "   mem_total 4000\n", "$end\n"]
        new_lines, changed = adjust_mem_total(lines, 8000)
        assert changed is True
        assert "mem_total 8000" in "".join(new_lines)
        assert "4000" not in "".join(new_lines)

    def test_adds_when_absent(self) -> None:
        lines = ["$rem\n", "method b3lyp\n", "$end\n"]
        new_lines, changed = adjust_mem_total(lines, 6000)
        assert changed is True
        assert "mem_total 6000" in "".join(new_lines)

    def test_no_change_when_value_equal(self) -> None:
        lines = ["$rem\nmem_total 5000\n$end\n"]
        new_lines, changed = adjust_mem_total(lines, 5000)
        assert changed is False
        assert "".join(new_lines) == "".join(lines)  # content unchanged
