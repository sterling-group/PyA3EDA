"""Cluster configuration: typed models, YAML discovery, and detection.

Absorbs ``qqchem/clusters.py`` (file discovery) and ``qqchem/cli.detect_cluster``.
The cluster schema is now a validated Pydantic model (was an untyped ``dict``),
so a malformed ``clusters.yaml`` fails loudly at load time with a clear message
instead of a late ``KeyError`` at submission.

Search order for the config file:
  1. ``$QQCHEM_CLUSTERS`` (path to a YAML file)
  2. ``~/.config/qqchem/clusters.yaml``
"""

from __future__ import annotations

import logging
import subprocess
from os import environ
from pathlib import Path

import yaml
from pydantic import BaseModel

from pya3eda.errors import PyA3EDAError

log = logging.getLogger(__name__)

_DEFAULT_PATH = Path.home() / ".config" / "qqchem" / "clusters.yaml"

EXAMPLE_YAML = """\
# ~/.config/qqchem/clusters.yaml
# One entry per cluster.  Cluster name is auto-detected via $CLUSTER_NAME or
# `scontrol show config`.

g2:
  default_partition: sterling
  mem_per_cpu: 4000            # MB
  default_time: "7-00:00:00"
  scratch_base_dir: "/scratch/ganymede2/$USER"
  exclude_nodes:
    sterling:
      - g-07-02
  qchem_versions:
    "6.2.1":
      module_loads: ["module load qchem/6.2.1"]
      qcsetup_file: ""
      environment: []
      mpi_support: true
      mpi_modules: ["gnu12/12.3.0", "openmpi4/4.1.6"]
"""


class QChemVersion(BaseModel, frozen=True):
    """A single Q-Chem version's module/environment setup on a cluster."""

    module_loads: list[str] = []
    qcsetup_file: str = ""
    environment: list[str] = []
    mpi_support: bool = False
    mpi_modules: list[str] = []


class ClusterConfig(BaseModel, frozen=True):
    """Validated configuration for one HPC cluster."""

    default_partition: str
    mem_per_cpu: int
    default_time: str
    scratch_base_dir: str
    exclude_nodes: dict[str, list[str]] = {}
    qchem_versions: dict[str, QChemVersion]


class ClusterConfigError(PyA3EDAError):
    """The cluster configuration is missing or invalid.

    Part of the :class:`~pya3eda.errors.PyA3EDAError` hierarchy so the CLI maps it
    to a deterministic exit code instead of surfacing it as an uncaught crash.
    """

    exit_code = 8


def _config_path() -> Path:
    """Return the path to the cluster config file."""
    env = environ.get("QQCHEM_CLUSTERS")
    if env:
        return Path(env).expanduser()
    return _DEFAULT_PATH


def load_cluster_configs() -> dict[str, ClusterConfig]:
    """Load, validate, and return the cluster configuration mapping.

    Raises :class:`ClusterConfigError` when the file is missing or malformed.
    """
    path = _config_path()
    if not path.is_file():
        raise ClusterConfigError(
            f"Cluster config not found at {path}\n"
            f"Create it, or set $QQCHEM_CLUSTERS to point to your file.\n\n"
            f"Example content:\n{EXAMPLE_YAML}"
        )

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ClusterConfigError(f"{path} must be a YAML mapping of cluster names.")

    try:
        return {name: ClusterConfig(**cfg) for name, cfg in data.items()}
    except Exception as exc:
        raise ClusterConfigError(f"Invalid cluster config in {path}: {exc}") from exc


def detect_cluster() -> tuple[str, ClusterConfig]:
    """Detect the current cluster and return ``(name, config)``.

    Detection order: ``$CLUSTER_NAME`` → SLURM ``ClusterName`` (``scontrol show
    config``) → first entry in the config file.
    """
    configs = load_cluster_configs()

    env_name = environ.get("CLUSTER_NAME", "").lower()
    if env_name:
        if env_name in configs:
            return env_name, configs[env_name]
        log.warning("CLUSTER_NAME=%r not in clusters.yaml", env_name)

    slurm_name = _scontrol_cluster_name()
    if slurm_name is not None:
        if slurm_name in configs:
            environ["CLUSTER_NAME"] = slurm_name
            log.info("Detected SLURM cluster: %s", slurm_name)
            return slurm_name, configs[slurm_name]
        log.warning("Detected SLURM cluster %r not in clusters.yaml", slurm_name)

    first = next(iter(configs))
    log.warning("Falling back to %r cluster settings", first)
    return first, configs[first]


def _scontrol_cluster_name() -> str | None:
    """Return the SLURM ClusterName from ``scontrol``, or ``None`` if unavailable."""
    try:
        result = subprocess.run(
            ["scontrol", "show", "config"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError, TimeoutError) as exc:
        log.warning("Could not detect cluster from SLURM: %s", exc)
        return None

    for line in result.stdout.split("\n"):
        if line.strip().startswith("ClusterName"):
            try:
                return line.split("=")[1].strip().lower()
            except IndexError:
                log.warning("Malformed ClusterName line from scontrol: %r", line)
                return None
    return None
