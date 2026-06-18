"""Tests for pya3eda.runner.engine — run-block branches not covered by the goldens.

The byte-for-byte golden matrix (``test_slurm_golden.py``) already exercises the
common run-block paths; these cover the MPI-availability branches the matrix
deliberately omits.
"""

from __future__ import annotations

from typing import Any

import pytest

from pya3eda.runner.engine import QChemEngine


def _spec(**overrides: Any):
    from pya3eda.runner.engine import JobSpec

    base: dict[str, Any] = {
        "input_path": "job.in",
        "output_file": "job.out",
        "error_file": "job.err",
        "job_name": "job",
        "partition": "p",
        "cpus": 1,
        "qchem_processors": 1,
        "mem_per_cpu": 1000,
        "walltime": "1:00:00",
        "parallel_type": "openmp",
        "scratch_base_dir": "/scratch/$USER",
        "cluster_name": "c",
    }
    base.update(overrides)
    return JobSpec(**base)


class TestQChemEngine:
    def test_metadata(self) -> None:
        eng = QChemEngine()
        assert eng.name == "qchem"
        assert eng.output_globs == ()

    def test_openmpi_without_mpi_support_exits(self) -> None:
        spec = _spec(parallel_type="openmpi", qchem_processors=2, mpi_support=False, force=False)
        with pytest.raises(SystemExit):
            QChemEngine().run_block(spec)

    def test_openmpi_force_proceeds_without_mpi_modules(self) -> None:
        spec = _spec(
            parallel_type="openmpi",
            qchem_processors=2,
            cpus=1,
            mpi_support=False,
            force=True,
            mpi_modules=[],
        )
        block = QChemEngine().run_block(spec)
        assert "-mpi -np 2 " in block
        assert "Load MPI modules" not in block  # no modules → block skipped
