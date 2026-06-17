"""Pluggable submission backends.

Each backend implements ``submit(input_path, **extra) -> bool``.
Register new backends in ``BACKENDS``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Protocol

log = logging.getLogger(__name__)


class SubmissionBackend(Protocol):
    """Interface every submission backend must satisfy."""

    name: str

    def submit(self, input_path: Path, extra_argv: list[str] | None = None) -> bool:
        """Submit a single job. Return *True* on success."""
        ...


# ------------------------------------------------------------------
# qqchem (SLURM) backend
# ------------------------------------------------------------------


class QQChemBackend:
    """Submit via the ``qqchem`` package (SLURM)."""

    name = "qqchem"

    def submit(self, input_path: Path, extra_argv: list[str] | None = None) -> bool:
        """Submit *input_path* via qqchem to the detected SLURM cluster."""
        from qqchem.cli import build_parser, detect_cluster
        from qqchem.cli import run as qqchem_run

        cluster_name, cluster_config = detect_cluster()
        parser = build_parser(cluster_config)

        argv = [*(extra_argv or []), input_path.name]
        args = parser.parse_args(argv)

        orig = os.getcwd()
        try:
            os.chdir(input_path.parent)
            qqchem_run(args, cluster_name=cluster_name)
            return True
        except SystemExit:
            log.error("qqchem submission failed for %s", input_path)
            return False
        finally:
            os.chdir(orig)


# ------------------------------------------------------------------
# Backend registry
# ------------------------------------------------------------------

BACKENDS: dict[str, type[SubmissionBackend]] = {
    "qqchem": QQChemBackend,
}


def get_backend(name: str) -> SubmissionBackend:
    """Look up a backend by name, or raise ``ValueError``."""
    cls = BACKENDS.get(name)
    if cls is None:
        available = ", ".join(sorted(BACKENDS))
        raise ValueError(f"Unknown backend '{name}'. Available: {available}")
    return cls()
