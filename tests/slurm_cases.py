"""Characterization matrix for the generated SLURM script (byte-for-byte gate).

``CASES`` is a representative matrix of ``generate_slurm_script`` argument sets;
``render(case)`` produces the exact script text for one case.  The goldens in
``tests/data/golden/`` are captured from this once (``scripts/dump_slurm.py``)
and ``test_slurm_golden.py`` asserts the generator still reproduces them
byte-for-byte after the runner refactor.

To repoint at the absorbed generator after the refactor, change the single
import in :func:`_generate`.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# The one place that names the production generator. Repoint after the
# refactor: ``from pya3eda.runner.script import generate_slurm_script``.
# ---------------------------------------------------------------------------


def _generate(**kwargs: Any) -> str:
    """Render one SLURM script to text via the current production generator."""
    from pya3eda.runner.script import generate_slurm_script

    # generate_slurm_script writes ``{job_name}.slurm`` relative to CWD and
    # returns the filename; run it in a throwaway dir and read the bytes back.
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.chdir(tmp)
            script_name = generate_slurm_script(**kwargs)
            return Path(tmp, script_name).read_text(encoding="utf-8")
        finally:
            os.chdir(cwd)


# ---------------------------------------------------------------------------
# Matrix
# ---------------------------------------------------------------------------

_BASE: dict[str, Any] = {
    "input_path": Path("job.in"),
    "job_name": "job",
    "output_file": "job.out",
    "error_file": "job.err",
    "partition": "sterling",
    "cpus": 1,
    "qchem_processors": 1,
    "mem_per_cpu": 4000,
    "walltime": "7-00:00:00",
    "parallel_type": "openmp",
    "module_load_commands": ["module load qchem/6.2.1"],
    "environment_vars": [],
    "qcsetup_file": "",
    "mpi_support": True,
    "mpi_modules": ["gnu12/12.3.0", "openmpi4/4.1.6"],
    "scratch": None,
    "scratch_base_dir": "/scratch/ganymede2/$USER",
    "nodename": None,
    "exclude_nodes": None,
    "save": False,
    "save_all": False,
    "save_scratch": False,
    "force": False,
    "cluster_name": "g2",
}


def _case(**overrides: Any) -> dict[str, Any]:
    """A matrix case = the base kwargs with ``overrides`` applied."""
    return {**_BASE, **overrides}


CASES: dict[str, dict[str, Any]] = {
    "base_openmp": _case(),
    "openmp_cpus4": _case(cpus=4),
    "openmpi": _case(parallel_type="openmpi", qchem_processors=2, cpus=2),
    "openmpi_serial": _case(parallel_type="openmpi", qchem_processors=4, cpus=1),
    "scratch_set": _case(scratch="/tmp/myscratch"),
    "save": _case(save=True),
    "save_all": _case(save_all=True),
    "save_scratch": _case(save_scratch=True),
    "save_scratch_custom": _case(save_scratch=True, scratch="/tmp/myscratch"),
    "nodelist": _case(nodename="g-01-01"),
    "exclude": _case(exclude_nodes="g-07-02,g-07-03"),
    "qcsetup": _case(qcsetup_file="/home/u/qcsetup.sh", module_load_commands=[]),
    "envvars": _case(environment_vars=["export QC=1", "export FOO=bar"]),
    "cluster_juno": _case(
        partition="normal",
        mem_per_cpu=3000,
        walltime="2-00:00:00",
        scratch_base_dir="/scratch/juno/$USER",
        cluster_name="juno",
    ),
}


def render(name: str) -> str:
    """Render the named matrix case to its exact SLURM script text."""
    return _generate(**CASES[name])
