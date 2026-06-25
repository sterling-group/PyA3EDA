"""Startup-cost guards: lazy ``__version__`` and a lean ``--help`` import graph."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest


def test_version_attr_is_lazy_string() -> None:
    """``pya3eda.__version__`` resolves to a string via the PEP 562 __getattr__."""
    import pya3eda

    assert isinstance(pya3eda.__version__, str)


def test_unknown_attribute_raises() -> None:
    """Accessing a non-existent module attribute raises (the __getattr__ fallback)."""
    import pya3eda

    with pytest.raises(AttributeError, match="does_not_exist"):
        _ = pya3eda.does_not_exist


def test_version_falls_back_when_distribution_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the package metadata is absent (run from a bare source tree),
    ``__version__`` falls back to ``"0+unknown"`` instead of raising."""
    import importlib.metadata

    import pya3eda

    def _raise(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(_name)

    monkeypatch.setattr(importlib.metadata, "version", _raise)
    assert pya3eda.__version__ == "0+unknown"


def test_help_does_not_import_heavy_deps() -> None:
    """``--help`` must not pull pandas / matplotlib / pydantic / yaml.

    These are only needed once a config is loaded or results are produced;
    importing them at CLI startup would regress ``--help``/``--version`` latency.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(["src", env.get("PYTHONPATH", "")])
    proc = subprocess.run(
        [sys.executable, "-X", "importtime", "-m", "pya3eda", "--help"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    imported = proc.stderr
    for mod in ("pandas", "matplotlib", "pydantic", "yaml"):
        assert mod not in imported, f"{mod} was imported on `--help` (startup regression)"
