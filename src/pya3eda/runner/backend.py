"""Execution backends: *where* a generated script runs (local bash vs SLURM).

The :class:`ExecutionBackend` Protocol decouples submission/polling from *what*
runs (the :mod:`~pya3eda.runner.engine` run block) and from the orchestrator,
so a new scheduler (PBS, cloud, …) is a new backend with no executor changes
(OCP/DIP). Two impls ship:

* :class:`LocalBackend` — runs the script via ``bash`` in the background
  (``Popen``), so many jobs run at once under the core budget; polled via
  ``Popen.poll``. Job IDs are synthetic ``local-N``.
* :class:`SlurmBackend` — ``sbatch`` the script, poll with ``squeue``.

``sbatch_available()`` is the single SLURM-vs-local switch used by the ``auto``
selection. Tests patch ``subprocess``/``Popen`` to avoid a live cluster.
"""

from __future__ import annotations

import functools
import getpass
import itertools
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import IO, Protocol

log = logging.getLogger(__name__)

_JOB_ID_RE = re.compile(r"\b(\d+)\b")
_LOCAL_PREFIX = "local-"


class JobSubmissionError(RuntimeError):
    """Raised when a backend fails to submit a job."""


@functools.lru_cache(maxsize=1)
def _current_user() -> str:
    """Username for ``squeue -u`` (numeric UID fallback in passwd-less envs)."""
    try:
        return getpass.getuser()
    except (KeyError, OSError):
        return str(os.getuid())


def sbatch_available(*, sbatch_cmd: str = "sbatch") -> bool:
    """Return True when ``sbatch`` is on ``PATH`` (i.e. a real SLURM host)."""
    return shutil.which(sbatch_cmd) is not None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class ExecutionBackend(Protocol):
    """Submits a generated script and reports completion."""

    name: str

    def available(self) -> bool:
        """Whether this backend can run in the current environment."""
        ...

    def submit(self, script_path: Path, *, log_path: Path | None = None) -> str:
        """Submit *script_path*; return a job ID. Raise :class:`JobSubmissionError` on failure."""
        ...

    def is_finished(self, job_id: str) -> bool:
        """Return True once *job_id* is no longer running."""
        ...


# ---------------------------------------------------------------------------
# Local backend
# ---------------------------------------------------------------------------


class LocalBackend:
    """Run scripts via ``bash`` in the background; poll the child process."""

    name = "local"

    def __init__(self) -> None:
        """Initialise the background-process registry and id counter."""
        self._procs: dict[str, tuple[subprocess.Popen[bytes], IO[bytes]]] = {}
        self._counter = itertools.count(1)

    def available(self) -> bool:
        """Local execution is always possible."""
        return True

    def submit(self, script_path: Path, *, log_path: Path | None = None) -> str:
        """Launch ``bash script_path`` in the background; return a ``local-N`` id.

        The script's ``#SBATCH`` directives are inert to bash, so SLURM's
        stdout/stderr redirection does not fire; we send both streams to
        *log_path* (defaulting to ``<script>.err``) so on-disk artifacts match
        the SLURM run. A non-zero exit is surfaced via status parsing later, not
        raised here.
        """
        script_path = Path(script_path)
        log_path = Path(log_path) if log_path is not None else script_path.with_suffix(".err")
        handle = log_path.open("wb")
        try:
            proc = subprocess.Popen(
                ["bash", str(script_path)],
                stdout=handle,
                stderr=subprocess.STDOUT,
                cwd=script_path.parent,
            )
        except Exception:
            handle.close()
            raise
        job_id = f"{_LOCAL_PREFIX}{next(self._counter)}"
        self._procs[job_id] = (proc, handle)
        log.info("launched %s locally as %s (pid %s)", script_path, job_id, proc.pid)
        return job_id

    def is_finished(self, job_id: str) -> bool:
        """Poll the background job; close its log handle and reap it when done."""
        entry = self._procs.get(job_id)
        if entry is None:
            return True
        proc, handle = entry
        if proc.poll() is None:
            return False
        handle.close()
        self._procs.pop(job_id, None)
        if proc.returncode != 0:
            log.warning("local job %s exited %d", job_id, proc.returncode)
        return True


# ---------------------------------------------------------------------------
# SLURM backend
# ---------------------------------------------------------------------------


class SlurmBackend:
    """Submit scripts with ``sbatch``; poll completion with ``squeue``."""

    name = "slurm"

    def __init__(self, *, sbatch_cmd: str = "sbatch", squeue_cmd: str = "squeue") -> None:
        """Configure the ``sbatch`` / ``squeue`` commands (overridable for tests)."""
        self.sbatch_cmd = sbatch_cmd
        self.squeue_cmd = squeue_cmd

    def available(self) -> bool:
        """Whether ``sbatch`` is on ``PATH``."""
        return sbatch_available(sbatch_cmd=self.sbatch_cmd)

    def submit(self, script_path: Path, *, log_path: Path | None = None) -> str:
        """``sbatch`` the script and return the parsed job ID."""
        try:
            result = subprocess.run(
                [self.sbatch_cmd, str(script_path)],
                capture_output=True,
                text=True,
                check=True,
                cwd=Path(script_path).parent,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            raise JobSubmissionError(f"sbatch failed for {script_path}: {exc}") from exc
        m = _JOB_ID_RE.search(result.stdout)
        if not m:
            raise JobSubmissionError(
                f"could not parse job ID from sbatch output: {result.stdout!r}"
            )
        job_id = m.group(1)
        log.info("submitted %s as job %s", script_path, job_id)
        return job_id

    def is_finished(self, job_id: str) -> bool:
        """Return True if *job_id* is absent from the current user's ``squeue``."""
        try:
            result = subprocess.run(
                [self.squeue_cmd, "-u", _current_user(), "-o", "%i"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            # squeue is transient on busy clusters; treat as not-finished, retry later.
            return False
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        running = lines[1:] if lines else []  # drop the "JOBID" header
        return not any(line == job_id or line.startswith(f"{job_id}_") for line in running)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

BACKENDS: dict[str, type[ExecutionBackend]] = {
    "local": LocalBackend,
    "slurm": SlurmBackend,
}


def get_backend(name: str = "auto") -> ExecutionBackend:
    """Return an execution backend by name.

    ``"auto"`` (default) selects :class:`SlurmBackend` when ``sbatch`` is on
    ``PATH``, else :class:`LocalBackend`. Raise ``ValueError`` for unknown names.
    """
    if name == "auto":
        return SlurmBackend() if sbatch_available() else LocalBackend()
    cls = BACKENDS.get(name)
    if cls is None:
        available = ", ".join(["auto", *sorted(BACKENDS)])
        raise ValueError(f"Unknown backend '{name}'. Available: {available}")
    return cls()
