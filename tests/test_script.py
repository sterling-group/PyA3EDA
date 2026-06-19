"""Tests for pya3eda.runner.script (header/local assembly + mem helpers).

Byte-for-byte SLURM fidelity is covered by ``test_slurm_golden.py``; this
covers the local variant, the header, and the absorbed input-memory helpers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pya3eda.runner import script
from pya3eda.runner.engine import JobSpec


def _spec(**overrides: Any) -> JobSpec:
    base: dict[str, Any] = {
        "input_path": "job.in",
        "output_file": "job.out",
        "error_file": "job.err",
        "job_name": "job",
        "partition": "sterling",
        "cpus": 1,
        "qchem_processors": 1,
        "mem_per_cpu": 4000,
        "walltime": "7-00:00:00",
        "parallel_type": "openmp",
        "scratch_base_dir": "/scratch/$USER",
        "cluster_name": "g2",
        "module_load_commands": ["module load qchem/6.2.1"],
    }
    base.update(overrides)
    return JobSpec(**base)


class TestHeaderAndAssembly:
    def test_sbatch_header_basic(self) -> None:
        header = script.sbatch_header(_spec())
        assert header.startswith("#!/bin/bash\n")
        assert "#SBATCH --job-name=job\n" in header
        assert "#SBATCH --nodelist" not in header

    def test_sbatch_header_nodelist_and_exclude(self) -> None:
        header = script.sbatch_header(_spec(nodename="n1", exclude_nodes="n2,n3"))
        assert "#SBATCH --nodelist=n1\n" in header
        assert "#SBATCH --exclude=n2,n3\n" in header

    def test_local_script_has_no_sbatch(self) -> None:
        text = script.local_script_text(_spec())
        assert text.startswith("#!/bin/bash\n")
        assert "#SBATCH" not in text
        assert "qchem job.in job.out $scrname" in text

    def test_slurm_equals_header_plus_runblock(self) -> None:
        spec = _spec()
        run_block = script.local_script_text(spec).removeprefix("#!/bin/bash\n")
        assert script.slurm_script_text(spec) == script.sbatch_header(spec) + run_block


class TestMemHelpers:
    def test_read_input_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            script.read_input_file(tmp_path / "nope.in")

    def test_read_input_file(self, tmp_path: Path) -> None:
        p = tmp_path / "job.in"
        p.write_text("$rem\n$end\n")
        assert script.read_input_file(p) == ["$rem\n", "$end\n"]

    def test_parse_mem_total(self) -> None:
        lines = ["$rem\n", "mem_total 8000\n", "$end\n"]
        assert script.parse_mem_total(lines) == [8000]

    def test_parse_mem_total_none(self) -> None:
        assert script.parse_mem_total(["$rem\n", "method b3lyp\n", "$end\n"]) == []

    def test_adjust_mem_total_replaces(self) -> None:
        lines = ["$rem\n", "mem_total 8000\n", "$end\n"]
        new, changed = script.adjust_mem_total(lines, 16000)
        assert changed is True
        assert "mem_total 16000" in "".join(new)

    def test_adjust_mem_total_inserts(self) -> None:
        lines = ["$rem\n", "method b3lyp\n", "$end\n"]
        new, changed = script.adjust_mem_total(lines, 16000)
        assert changed is True
        assert "mem_total 16000" in "".join(new)

    def test_adjust_mem_total_no_rem_block(self) -> None:
        lines = ["nothing here\n"]
        new, changed = script.adjust_mem_total(lines, 16000)
        assert changed is False
        assert new == lines
