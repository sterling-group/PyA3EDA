"""Configuration models and YAML loading.

The configuration file is the single source of truth for the entire system.
It is validated on load via Pydantic and never mutated afterwards.
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, field_validator, model_validator

# ---------------------------------------------------------------------------
# Theory level
# ---------------------------------------------------------------------------


class TheoryConfig(BaseModel, frozen=True):
    """A single level of theory (method + basis + optional modifiers)."""

    method: str
    basis: str
    dispersion: str | None = None  # None → no dispersion
    solvent: str | None = None  # None → gas phase
    eda2: int | None = None  # Only meaningful for SP; 0, 1, or 2

    @field_validator("dispersion", "solvent", mode="before")
    @classmethod
    def _coerce_bool_to_str(cls, v: str | bool | None) -> str | None:
        """Accept YAML bare ``false`` / ``true`` and coerce to string."""
        if isinstance(v, bool):
            return str(v).lower()
        return v

    @field_validator("eda2")
    @classmethod
    def _validate_eda2(cls, v: int | None) -> int | None:
        """Ensure *eda2* is 0, 1, or 2 when set."""
        if v is not None and v not in (0, 1, 2):
            raise ValueError(f"eda2 must be 0, 1, or 2, got {v}")
        return v


# ---------------------------------------------------------------------------
# Level = OPT (always) + optional list of SPs
# ---------------------------------------------------------------------------


class LevelConfig(BaseModel, frozen=True):
    """One optimisation level with zero or more single-point levels beneath."""

    opt: TheoryConfig
    sp: list[TheoryConfig] = []


# ---------------------------------------------------------------------------
# Species & catalysts
# ---------------------------------------------------------------------------


class SpeciesConfig(BaseModel, frozen=True):
    """A reactant or product species."""

    name: str
    include: bool = True  # False → free spectator, not part of catalyst complexes


class CatalystConfig(BaseModel, frozen=True):
    """A catalyst."""

    name: str
    dimer: bool = False  # True → also run a `dimer` stage and add a DISS dissociation bar


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class Config(BaseModel, frozen=True):
    """Top-level validated configuration. Immutable after construction."""

    levels: list[LevelConfig]
    catalysts: list[CatalystConfig] = []
    reactants: list[SpeciesConfig]
    products: list[SpeciesConfig]

    @field_validator("levels")
    @classmethod
    def _at_least_one_level(cls, v: list[LevelConfig]) -> list[LevelConfig]:
        """Reject configurations with no theory levels."""
        if not v:
            raise ValueError("At least one level is required")
        return v

    @field_validator("reactants")
    @classmethod
    def _at_least_one_reactant(cls, v: list[SpeciesConfig]) -> list[SpeciesConfig]:
        """Reject configurations with no reactant species."""
        if not v:
            raise ValueError("At least one reactant is required")
        return v

    @field_validator("products")
    @classmethod
    def _at_least_one_product(cls, v: list[SpeciesConfig]) -> list[SpeciesConfig]:
        """Reject configurations with no product species."""
        if not v:
            raise ValueError("At least one product is required")
        return v

    @model_validator(mode="after")
    def _merge_duplicate_opts(self) -> Self:
        """Auto-merge levels that share the same OPT theory.

        If two level entries specify the same ``opt`` TheoryConfig, their SP
        lists are merged into a single ``LevelConfig``.  Duplicate SP entries
        within the merged list are rejected.
        """
        seen: dict[TheoryConfig, list[TheoryConfig]] = {}
        order: list[TheoryConfig] = []

        for level in self.levels:
            if level.opt not in seen:
                seen[level.opt] = list(level.sp)
                order.append(level.opt)
            else:
                for sp in level.sp:
                    if sp in seen[level.opt]:
                        raise ValueError(f"Duplicate SP entry {sp!r} under OPT {level.opt!r}")
                    seen[level.opt].append(sp)

        merged = [LevelConfig(opt=opt_theory, sp=seen[opt_theory]) for opt_theory in order]

        # Pydantic frozen models need object.__setattr__ to mutate
        object.__setattr__(self, "levels", merged)
        return self


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_config(path: str | Path) -> Config:
    """Load and validate a YAML configuration file.

    Returns a fully validated, immutable ``Config`` instance. Every failure mode
    (missing file, non-mapping YAML, schema violation) surfaces as
    :class:`~pya3eda.errors.ConfigError` so the CLI maps it to one exit code.
    """
    from pydantic import ValidationError

    from pya3eda.errors import ConfigError

    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ConfigError(f"Expected a YAML mapping, got {type(raw).__name__}")
    try:
        return Config(**raw)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration in {path}:\n{exc}") from exc
