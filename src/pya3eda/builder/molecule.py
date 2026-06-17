"""Build the ``$molecule`` section for Q-Chem input files.

Supports standard (single-fragment) and fragmented (EDA) molecule sections.
Coordinates come from template XYZ files (OPT mode) or from previous
optimization output (SP mode).
"""

from __future__ import annotations

import logging
from pathlib import Path

from pya3eda.parser.xyz import XYZData, parse_output_xyz, parse_xyz
from pya3eda.utils import read_text

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _format_standard(charge: int, mult: int, atoms: list[str]) -> str:
    """Format a standard (non-fragmented) molecule section."""
    return f"{charge} {mult}\n" + "\n".join(atoms)


def _format_fragmented(
    total_charge: int,
    total_mult: int,
    cat_charge: int,
    cat_mult: int,
    cat_atoms: list[str],
    sub_charge: int,
    sub_mult: int,
    sub_atoms: list[str],
) -> str:
    """Format a fragmented molecule section for EDA calculations."""
    return (
        f"{total_charge} {total_mult}\n"
        f"---\n"
        f"{cat_charge} {cat_mult}\n" + "\n".join(cat_atoms) + "\n"
        f"---\n"
        f"{sub_charge} {sub_mult}\n" + "\n".join(sub_atoms)
    )


def _coords_from_output(output_text: str | None, template: XYZData) -> list[str]:
    """Return optimised coordinates from output, falling back to template."""
    if output_text:
        data = parse_output_xyz(output_text)
        if data:
            return data.atoms
        log.warning("Failed to parse output; falling back to template coordinates")
    return template.atoms


def _load_xyz(
    templates_dir: Path, name: str, calc_type: str | None = None
) -> str | None:
    """Load an XYZ template file, trying calc-type-specific variant first."""
    mol_dir = templates_dir / "molecule"
    if calc_type:
        path = mol_dir / f"{name}_{calc_type}.xyz"
        text = read_text(path)
        if text:
            return text
    text = read_text(mol_dir / f"{name}.xyz")
    if text is None:
        log.error("Missing molecule template: %s/%s.xyz", mol_dir, name)
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_standard_molecule(
    xyz_text: str,
    output_text: str | None = None,
) -> str | None:
    """Build a standard (single-fragment) molecule section.

    Parameters
    ----------
    xyz_text : str
        XYZ template content (n_atoms / charge mult / atoms).
    output_text : str | None
        If given, optimised coordinates are extracted from this Q-Chem output
        instead of the template (SP mode).
    """
    template = parse_xyz(xyz_text)
    if template is None:
        log.error("Failed to parse XYZ template")
        return None

    atoms = _coords_from_output(output_text, template)
    return _format_standard(template.charge, template.multiplicity, atoms)


def build_fragmented_molecule(
    composite_xyz_text: str,
    catalyst_xyz_text: str,
    substrate_xyz_text: str,
    output_text: str | None = None,
) -> str | None:
    """Build a fragmented (EDA) molecule section.

    Parameters
    ----------
    composite_xyz_text : str
        XYZ for the full complex (catalyst + substrate).
    catalyst_xyz_text : str
        XYZ for the catalyst fragment alone.
    substrate_xyz_text : str
        XYZ for the substrate fragment alone.
    output_text : str | None
        If given, optimised coordinates replace the template atoms (SP mode).
    """
    composite = parse_xyz(composite_xyz_text)
    catalyst = parse_xyz(catalyst_xyz_text)
    substrate = parse_xyz(substrate_xyz_text)

    if not all((composite, catalyst, substrate)):
        log.error("Failed to parse one or more XYZ templates for fragmented molecule")
        return None

    total_expected = catalyst.n_atoms + substrate.n_atoms
    atoms = _coords_from_output(output_text, composite)

    if len(atoms) < total_expected:
        log.error(
            "Insufficient atoms for fragmented molecule: expected %d, got %d",
            total_expected,
            len(atoms),
        )
        return None

    cat_atoms = atoms[: catalyst.n_atoms]
    sub_atoms = atoms[catalyst.n_atoms : catalyst.n_atoms + substrate.n_atoms]

    return _format_fragmented(
        composite.charge,
        composite.multiplicity,
        catalyst.charge,
        catalyst.multiplicity,
        cat_atoms,
        substrate.charge,
        substrate.multiplicity,
        sub_atoms,
    )
