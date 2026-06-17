"""Tests for qqchem.clusters — cluster config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

import qqchem.clusters as clusters
from qqchem.clusters import _config_path, load_cluster_configs

SAMPLE = """\
juno:
  default_partition: normal
  mem_per_cpu: 3000
  default_time: "2-00:00:00"
  scratch_base_dir: "/scratch/juno/$USER"
  exclude_nodes: {}
  qchem_versions:
    "6.2.1":
      module_loads: ["module load qchem/6.2.1"]
"""


class TestConfigPath:
    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QQCHEM_CLUSTERS", "/tmp/custom.yaml")
        assert _config_path() == Path("/tmp/custom.yaml")

    def test_default_when_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("QQCHEM_CLUSTERS", raising=False)
        assert _config_path() == Path.home() / ".config" / "qqchem" / "clusters.yaml"


class TestLoadClusterConfigs:
    def test_loads_valid(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = tmp_path / "clusters.yaml"
        cfg.write_text(SAMPLE)
        monkeypatch.setenv("QQCHEM_CLUSTERS", str(cfg))
        data = load_cluster_configs()
        assert "juno" in data
        assert data["juno"]["mem_per_cpu"] == 3000

    def test_missing_file_exits(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QQCHEM_CLUSTERS", str(tmp_path / "absent.yaml"))
        with pytest.raises(SystemExit):
            load_cluster_configs()

    def test_non_mapping_exits(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = tmp_path / "clusters.yaml"
        cfg.write_text("- just\n- a\n- list\n")
        monkeypatch.setenv("QQCHEM_CLUSTERS", str(cfg))
        with pytest.raises(SystemExit):
            load_cluster_configs()

    def test_empty_mapping_exits(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = tmp_path / "clusters.yaml"
        cfg.write_text("")  # yaml.safe_load -> None
        monkeypatch.setenv("QQCHEM_CLUSTERS", str(cfg))
        with pytest.raises(SystemExit):
            load_cluster_configs()

    def test_missing_yaml_dependency_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Simulate pyyaml not being installed.
        monkeypatch.setattr(clusters, "yaml", None)
        with pytest.raises(SystemExit):
            load_cluster_configs()
