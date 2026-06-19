"""Assemble the SLURM/bash script: ``#SBATCH`` header + an engine run block.

Absorbs the original ``qqchem`` ``slurm.py`` script assembly and
``qchem_input.py`` memory helpers.  The header is generic SLURM; the run block
comes from an :class:`~pya3eda.runner.engine.Engine`.  ``generate_slurm_script``
is kept as a byte-for-byte-compatible entry point (locked by
``tests/test_slurm_golden.py``); ``local_script_text`` is the same script with
the ``#SBATCH`` directives omitted, for the local (no-SLURM) backend.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pya3eda.runner.engine import ENGINES, Engine, JobSpec

# ---------------------------------------------------------------------------
# Script assembly
# ---------------------------------------------------------------------------


def sbatch_header(spec: JobSpec) -> str:
    """Return ``#!/bin/bash`` + the ``#SBATCH`` directive block for *spec*."""
    lines = [
        "#!/bin/bash",
        "#SBATCH --export=ALL",
        f"#SBATCH --job-name={spec.job_name}",
        f"#SBATCH --output={spec.error_file}",
        f"#SBATCH --error={spec.error_file}",
        f"#SBATCH --partition={spec.partition}",
        "#SBATCH --nodes=1",
        f"#SBATCH --ntasks={spec.qchem_processors}",
        f"#SBATCH --cpus-per-task={spec.cpus}",
        f"#SBATCH --mem-per-cpu={spec.mem_per_cpu}",
        f"#SBATCH --time={spec.walltime}",
    ]
    if spec.nodename:
        lines.append(f"#SBATCH --nodelist={spec.nodename}")
    if spec.exclude_nodes:
        lines.append(f"#SBATCH --exclude={spec.exclude_nodes}")
    return "".join(f"{line}\n" for line in lines)


def slurm_script_text(spec: JobSpec, engine: Engine | None = None) -> str:
    """Full SLURM script: ``#SBATCH`` header + the engine run block."""
    engine = engine or ENGINES["qchem"]
    return sbatch_header(spec) + engine.run_block(spec)


def local_script_text(spec: JobSpec, engine: Engine | None = None) -> str:
    """Local bash script: shebang + the engine run block (no ``#SBATCH``)."""
    engine = engine or ENGINES["qchem"]
    return "#!/bin/bash\n" + engine.run_block(spec)


def generate_slurm_script(**kwargs: Any) -> str:
    """Write ``{job_name}.slurm`` in the CWD and return its filename.

    Byte-for-byte compatible with the original ``qqchem.slurm`` entry point;
    accepts the same keyword arguments (they map directly onto :class:`JobSpec`).
    """
    spec = JobSpec(**kwargs)
    slurm_script = f"{spec.job_name}.slurm"
    Path(slurm_script).write_text(slurm_script_text(spec), encoding="utf-8")
    return slurm_script


# ---------------------------------------------------------------------------
# Q-Chem input memory helpers (absorbed from qqchem/qchem_input.py)
# ---------------------------------------------------------------------------


def read_input_file(input_path: Path) -> list[str]:
    """Read a Q-Chem input file and return its lines."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file '{input_path}' does not exist.")
    return input_path.read_text().splitlines(keepends=True)


def parse_mem_total(lines: list[str]) -> list[int]:
    """Return all ``mem_total`` values found in ``$rem`` blocks."""
    text = "".join(lines)
    values: list[int] = []
    for block in re.findall(r"\$rem(.*?)\$end", text, re.DOTALL | re.IGNORECASE):
        values.extend(int(v) for v in re.findall(r"\bmem_total\s*=?\s*(\d+)", block, re.IGNORECASE))
    return values


def adjust_mem_total(lines: list[str], mem_total_value: int) -> tuple[list[str], bool]:
    """Set ``mem_total`` in every ``$rem`` block, adding it if absent.

    Returns the (possibly modified) lines and whether any change was made.
    """
    text = "".join(lines)
    original = text

    def _adjust(match: re.Match[str]) -> str:
        """Replace or insert ``mem_total`` within a single ``$rem`` block."""
        block = match.group(0)
        if re.search(r"\bmem_total\s*=?\s*\d+", block, re.IGNORECASE):
            return re.sub(
                r"(\bmem_total\s*=?\s*)(\d+)",
                rf"\g<1>{mem_total_value}",
                block,
                flags=re.IGNORECASE,
            )
        return block.replace("$rem", f"$rem\n   mem_total {mem_total_value}", 1)

    adjusted = re.sub(r"\$rem(.*?)\$end", _adjust, text, flags=re.DOTALL | re.IGNORECASE)
    return adjusted.splitlines(keepends=True), adjusted != original
