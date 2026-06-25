"""CalcRegistry — the single source of truth for all calculations and profiles.

Built once from a ``Config`` and a base directory.  Pure derivation — no
filesystem access.  Every downstream module receives the registry and looks up
calculations by ``CalcID`` or profiles by ``ProfileID``.

The enumeration is split across :mod:`~pya3eda.registry.calcs` (calculations),
:mod:`~pya3eda.registry.profiles` (energy profiles), and
:mod:`~pya3eda.registry.paths` (the directory-tree layout); this module is the
thin ``CalcRegistry`` facade that owns the derived state and the lookup API.
"""

from __future__ import annotations

from pathlib import Path

from pya3eda.config import Config
from pya3eda.ids import CalcID, CalcSpec, ProfileID, ProfileSpec
from pya3eda.registry._common import build_method_key
from pya3eda.registry.calcs import enumerate_calcs
from pya3eda.registry.profiles import enumerate_profiles
from pya3eda.sanitize import sanitize

__all__ = ["CalcRegistry", "build_method_key"]


class CalcRegistry:
    """Enumerates every expected calculation and energy profile from config.

    Parameters
    ----------
    config : Config
        Validated configuration.
    base_dir : Path
        Root directory beneath which all method-key folders live.
    """

    def __init__(self, config: Config, base_dir: Path) -> None:
        """Initialise the registry by enumerating all calcs and profiles."""
        self._config = config
        self._base_dir = Path(base_dir)

        # Derived ordering helpers
        self._catalyst_order: list[str] = [c.name for c in config.catalysts]
        self._dimer_catalysts: set[str] = {sanitize(c.name) for c in config.catalysts if c.dimer}

        # Primary stores
        self._calcs, self._method_keys = enumerate_calcs(config, self._base_dir)
        self._profiles: dict[ProfileID, ProfileSpec] = enumerate_profiles(config)

    # -- public API ---------------------------------------------------------

    @property
    def config(self) -> Config:
        """The validated configuration this registry was built from."""
        return self._config

    @property
    def base_dir(self) -> Path:
        """Root directory beneath which all method-key folders live."""
        return self._base_dir

    @property
    def all_calcs(self) -> list[CalcSpec]:
        """All registered calculation specs."""
        return list(self._calcs.values())

    def get(self, calc_id: CalcID) -> CalcSpec:
        """Look up a CalcSpec by its CalcID."""
        return self._calcs[calc_id]

    def by_method(self, method_key: str) -> list[CalcSpec]:
        """Return all CalcSpecs matching the given method key."""
        return [c for c in self._calcs.values() if c.id.method_key == method_key]

    def by_mode(self, mode: str) -> list[CalcSpec]:
        """Return all CalcSpecs matching the given mode ('opt' or 'sp')."""
        return [c for c in self._calcs.values() if c.id.mode == mode]

    @property
    def all_profiles(self) -> list[ProfileSpec]:
        """All registered energy-profile specs."""
        return list(self._profiles.values())

    def get_profile(self, profile_id: ProfileID) -> ProfileSpec:
        """Look up a ProfileSpec by its ProfileID."""
        return self._profiles[profile_id]

    def profiles_for_method(self, method_key: str) -> list[ProfileSpec]:
        """Return all ProfileSpecs matching the given method key."""
        return [p for p in self._profiles.values() if p.id.method_key == method_key]

    @property
    def method_keys(self) -> list[str]:
        """Ordered list of method keys from config levels."""
        return list(self._method_keys)

    @property
    def catalyst_order(self) -> list[str]:
        """Ordered list of catalyst names from config."""
        return list(self._catalyst_order)

    @property
    def dimer_catalysts(self) -> set[str]:
        """Sanitised names of catalysts declared with ``dimer: true``."""
        return set(self._dimer_catalysts)
