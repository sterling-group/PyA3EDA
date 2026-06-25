"""Input-file path construction for the registry (the directory tree layout)."""

from __future__ import annotations

from pathlib import Path

from pya3eda.registry._common import _TS_SPECIES
from pya3eda.vocab import Mode, Stage

_NO_CAT_DIR = "no_cat"


def build_input_path(
    base_dir: Path,
    method_key: str,
    catalyst: str | None,
    stage: str,
    species: str,
    calc_type: str | None,
    mode: str,
    sp_subfolder: str | None,
) -> Path:
    """Build the input-file path (beneath ``base_dir``).

    Mirrors the directory tree documented in the old builder module.
    """
    suffix = f"_{mode}.in"
    base = base_dir / method_key

    # Filesystem directory: None → _NO_CAT_DIR, else the catalyst name
    cat_dir = catalyst or _NO_CAT_DIR

    if catalyst is None:
        if stage in (Stage.REACTANTS, Stage.PRODUCTS):
            parts = Path(cat_dir) / stage / species
            filename = f"{species}{suffix}"
        elif stage == Stage.TS:
            parts = Path(cat_dir) / Stage.TS
            filename = f"{_TS_SPECIES}{suffix}"
        else:
            raise ValueError(f"Unknown uncatalyzed stage: {stage}")

        if mode == Mode.SP and sp_subfolder:
            parts = parts / sp_subfolder
        return base / parts / filename

    # Catalyzed — cat_dir is the catalyst name
    if stage == Stage.CAT:
        parts = Path(cat_dir) / Stage.CAT
        filename = f"{cat_dir}{suffix}"
        if mode == Mode.SP and sp_subfolder:
            parts = parts / sp_subfolder
        return base / parts / filename

    if stage == Stage.DIMER:
        parts = Path(cat_dir) / Stage.DIMER
        filename = f"{cat_dir}-dimer{suffix}"
        if mode == Mode.SP and sp_subfolder:
            parts = parts / sp_subfolder
        return base / parts / filename

    if stage in (Stage.PRETS, Stage.POSTTS):
        assert calc_type is not None  # preTS/postTS calcs always carry a calc_type
        prefix = stage  # "preTS" or "postTS"
        parts = Path(cat_dir) / stage / species / calc_type
        filename = f"{prefix}_{species}_{calc_type}{suffix}"
        if mode == Mode.SP and sp_subfolder:
            parts = parts / sp_subfolder
        return base / parts / filename

    if stage == Stage.TS:
        assert calc_type is not None  # TS calcs always carry a calc_type
        parts = Path(cat_dir) / Stage.TS / calc_type
        filename = f"{Stage.TS}_{species}_{calc_type}{suffix}"
        if mode == Mode.SP and sp_subfolder:
            parts = parts / sp_subfolder
        return base / parts / filename

    raise ValueError(f"Unknown stage: {stage}")
