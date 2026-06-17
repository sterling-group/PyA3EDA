"""Load cluster configurations from a user-maintained YAML file.

Search order:
  1. ``$QQCHEM_CLUSTERS`` environment variable (path to YAML)
  2. ``~/.config/qqchem/clusters.yaml``

If neither exists, qqchem exits with an error and prints a template.
"""

from __future__ import annotations

import sys
from os import environ
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

_DEFAULT_PATH = Path.home() / ".config" / "qqchem" / "clusters.yaml"

EXAMPLE_YAML = """\
# ~/.config/qqchem/clusters.yaml
# One entry per cluster.  qqchem auto-detects the cluster name via
# $CLUSTER_NAME or `scontrol show config`.

g2:
  default_partition: sterling
  mem_per_cpu: 4000            # MB
  default_time: "7-00:00:00"
  scratch_base_dir: "/scratch/ganymede2/$USER"
  exclude_nodes:
    sterling:
      - g-07-02
  qchem_versions:
    "6.3.0":
      module_loads: ["module load qchem/6.3"]
      qcsetup_file: ""
      environment: []
      mpi_support: true
      mpi_modules: ["gnu12/12.3.0", "openmpi4/4.1.6"]
    "6.2.1":
      module_loads: ["module load qchem/6.2.1"]
      qcsetup_file: ""
      environment: []
      mpi_support: true
      mpi_modules: ["gnu12/12.3.0", "openmpi4/4.1.6"]

juno:
  default_partition: normal
  mem_per_cpu: 3000
  default_time: "2-00:00:00"
  scratch_base_dir: "/scratch/juno/$USER"
  exclude_nodes: {}
  qchem_versions:
    "6.3.0":
      module_loads: ["module load qchem/6.3"]
      qcsetup_file: ""
      environment: []
      mpi_support: true
      mpi_modules: ["gnu12/12.3.0", "openmpi4/4.1.6"]
"""


def _config_path() -> Path:
    """Return the path to the cluster config file."""
    env = environ.get("QQCHEM_CLUSTERS")
    if env:
        return Path(env).expanduser()
    return _DEFAULT_PATH


def load_cluster_configs() -> dict[str, dict]:
    """Load and return the cluster configuration dictionary.

    Raises ``SystemExit`` with a helpful message when the file is missing
    or pyyaml is not installed.
    """
    if yaml is None:
        print(
            "Error: pyyaml is required by qqchem.  Install it with:\n"
            "  pip install pyyaml",
            file=sys.stderr,
        )
        sys.exit(1)

    path = _config_path()
    if not path.is_file():
        print(
            f"Error: Cluster config not found at {path}\n"
            f"Create it, or set $QQCHEM_CLUSTERS to point to your file.\n\n"
            f"Example content:\n{EXAMPLE_YAML}",
            file=sys.stderr,
        )
        sys.exit(1)

    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or not data:
        print(
            f"Error: {path} must be a YAML mapping of cluster names.", file=sys.stderr
        )
        sys.exit(1)

    return data
