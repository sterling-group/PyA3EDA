"""Tests for pya3eda.runner.clusters (typed config, discovery, detection)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pya3eda.runner import clusters
from pya3eda.runner.clusters import (
    ClusterConfig,
    ClusterConfigError,
    QChemVersion,
    detect_cluster,
    load_cluster_configs,
)

_VALID_YAML = """\
g2:
  default_partition: sterling
  mem_per_cpu: 4000
  default_time: "7-00:00:00"
  scratch_base_dir: "/scratch/g2/$USER"
  exclude_nodes:
    sterling: [g-07-02]
  qchem_versions:
    "6.2.1":
      module_loads: ["module load qchem/6.2.1"]
      mpi_support: true
      mpi_modules: ["openmpi4"]
juno:
  default_partition: normal
  mem_per_cpu: 3000
  default_time: "2-00:00:00"
  scratch_base_dir: "/scratch/juno/$USER"
  qchem_versions:
    "6.3.0":
      module_loads: ["module load qchem/6.3"]
"""


@pytest.fixture
def cfg_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Write a valid clusters.yaml and point $QQCHEM_CLUSTERS at it."""
    p = tmp_path / "clusters.yaml"
    p.write_text(_VALID_YAML)
    monkeypatch.setenv("QQCHEM_CLUSTERS", str(p))
    monkeypatch.delenv("CLUSTER_NAME", raising=False)
    return p


# ===================================================================
# Models
# ===================================================================


class TestModels:
    def test_defaults(self) -> None:
        v = QChemVersion()
        assert v.module_loads == [] and v.mpi_support is False
        c = ClusterConfig(
            default_partition="p",
            mem_per_cpu=1000,
            default_time="1:00:00",
            scratch_base_dir="/s",
            qchem_versions={"x": QChemVersion()},
        )
        assert c.exclude_nodes == {}


# ===================================================================
# load_cluster_configs
# ===================================================================


class TestLoad:
    def test_success(self, cfg_file: Path) -> None:
        configs = load_cluster_configs()
        assert set(configs) == {"g2", "juno"}
        assert configs["g2"].default_partition == "sterling"

    def test_missing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QQCHEM_CLUSTERS", str(tmp_path / "absent.yaml"))
        with pytest.raises(ClusterConfigError, match="not found"):
            load_cluster_configs()

    def test_default_path_used_when_env_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("QQCHEM_CLUSTERS", raising=False)
        monkeypatch.setattr(clusters, "_DEFAULT_PATH", tmp_path / "none.yaml")
        with pytest.raises(ClusterConfigError, match="not found"):
            load_cluster_configs()

    def test_not_a_mapping(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        p = tmp_path / "c.yaml"
        p.write_text("- a\n- b\n")
        monkeypatch.setenv("QQCHEM_CLUSTERS", str(p))
        with pytest.raises(ClusterConfigError, match="must be a YAML mapping"):
            load_cluster_configs()

    def test_invalid_schema(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        p = tmp_path / "c.yaml"
        p.write_text("g2:\n  default_partition: sterling\n")  # missing required fields
        monkeypatch.setenv("QQCHEM_CLUSTERS", str(p))
        with pytest.raises(ClusterConfigError, match="Invalid cluster config"):
            load_cluster_configs()


# ===================================================================
# detect_cluster
# ===================================================================


class TestDetect:
    def test_env_match(self, cfg_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLUSTER_NAME", "juno")
        name, cfg = detect_cluster()
        assert name == "juno"
        assert cfg.default_partition == "normal"

    def test_env_no_match_falls_through(
        self, cfg_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLUSTER_NAME", "ghost")
        with patch("pya3eda.runner.clusters._scontrol_cluster_name", return_value=None):
            name, _ = detect_cluster()
        assert name == "g2"  # first entry

    def test_scontrol_match(self, cfg_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        with patch("pya3eda.runner.clusters._scontrol_cluster_name", return_value="juno"):
            name, _ = detect_cluster()
        assert name == "juno"

    def test_scontrol_unknown_falls_back(
        self, cfg_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with patch("pya3eda.runner.clusters._scontrol_cluster_name", return_value="mystery"):
            name, _ = detect_cluster()
        assert name == "g2"

    def test_scontrol_none_falls_back(self, cfg_file: Path) -> None:
        with patch("pya3eda.runner.clusters._scontrol_cluster_name", return_value=None):
            name, _ = detect_cluster()
        assert name == "g2"


# ===================================================================
# _scontrol_cluster_name
# ===================================================================


class TestScontrol:
    def test_success(self) -> None:
        result = MagicMock(stdout="ClusterName    = JUNO\nFoo = bar\n")
        with patch("pya3eda.runner.clusters.subprocess.run", return_value=result):
            assert clusters._scontrol_cluster_name() == "juno"

    def test_no_clustername_line(self) -> None:
        result = MagicMock(stdout="Foo = bar\nBaz = qux\n")
        with patch("pya3eda.runner.clusters.subprocess.run", return_value=result):
            assert clusters._scontrol_cluster_name() is None

    def test_malformed_line(self) -> None:
        result = MagicMock(stdout="ClusterName\n")  # no '='
        with patch("pya3eda.runner.clusters.subprocess.run", return_value=result):
            assert clusters._scontrol_cluster_name() is None

    def test_subprocess_unavailable(self) -> None:
        with patch("pya3eda.runner.clusters.subprocess.run", side_effect=FileNotFoundError):
            assert clusters._scontrol_cluster_name() is None
