"""Build the ``$molecule`` section for Q-Chem input files.

Supports standard (single-fragment) and fragmented (EDA) molecule sections.
Coordinates come from template XYZ files (OPT mode) or from previous
optimization output (SP mode).
"""

from __future__ import annotations

import logging
from pathlib import Path

from pya3eda.parser.xyz import XYZData, parse_output_fragments, parse_output_xyz, parse_xyz
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


def _coords_from_output(output_text: str | None, template: XYZData) -> tuple[list[str], bool]:
    """Return optimised coordinates from output, falling back to template.

    The flag reports whether the coordinates actually came from the output, since only then
    is that output's echoed fragmentation relevant.
    """
    if output_text:
        data = parse_output_xyz(output_text)
        if data:
            return data.atoms, True
        log.warning("Failed to parse output; falling back to template coordinates")
    return template.atoms, False


def _load_xyz(templates_dir: Path, name: str, calc_type: str | None = None) -> str | None:
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

    atoms, _ = _coords_from_output(output_text, template)
    return _format_standard(template.charge, template.multiplicity, atoms)


def build_fragmented_molecule(
    composite_xyz_text: str,
    catalyst_xyz_text: str,
    substrate_xyz_text: str,
    output_text: str | None = None,
    label: str = "<templates>",
) -> str | None:
    """Build a fragmented (EDA) molecule section.

    In SP mode the atom count is dictated by the optimised geometry, not by the templates:
    an SP must describe the same molecule its OPT actually computed.  The fragmentation is
    therefore taken from the ``$molecule`` block echoed in *output_text* when that block
    accounts for every optimised atom, which lets a hand-extended OPT (explicit solvent
    molecules, say) carry through without editing any template.  Failing that, the template
    split is used and must match the geometry **exactly** — a template that disagrees is an
    error, never a silent trim.

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
    label : str
        Template name used in diagnostics.
    """
    composite = parse_xyz(composite_xyz_text)
    catalyst = parse_xyz(catalyst_xyz_text)
    substrate = parse_xyz(substrate_xyz_text)

    if composite is None or catalyst is None or substrate is None:
        log.error("Failed to parse one or more XYZ templates for fragmented molecule")
        return None

    total_expected = catalyst.n_atoms + substrate.n_atoms
    if composite.n_atoms != total_expected:
        log.warning(
            "Template %s declares %d atoms but its fragments sum to %d "
            "(catalyst %d + substrate %d) — the fragment files are what split the geometry",
            label,
            composite.n_atoms,
            total_expected,
            catalyst.n_atoms,
            substrate.n_atoms,
        )

    atoms, from_output = _coords_from_output(output_text, composite)

    # Prefer the fragmentation the optimisation itself ran with; fall back to the templates.
    layout = parse_output_fragments(output_text) if from_output and output_text else None
    if layout is not None and len(layout.fragments) == 2:
        cat_frag, sub_frag = layout.fragments
        if cat_frag.n_atoms + sub_frag.n_atoms == len(atoms):
            return _format_fragmented(
                layout.charge,
                layout.multiplicity,
                cat_frag.charge,
                cat_frag.multiplicity,
                atoms[: cat_frag.n_atoms],
                sub_frag.charge,
                sub_frag.multiplicity,
                atoms[cat_frag.n_atoms :],
            )

    if len(atoms) != total_expected:
        log.error(
            "Atom-count mismatch building %s: geometry has %d atoms but the templates "
            "declare %d (catalyst %d + substrate %d). Refusing to write a truncated "
            "$molecule — update the templates to cover every atom, or re-run the OPT so its "
            "output carries an explicit two-fragment $molecule to inherit the split from",
            label,
            len(atoms),
            total_expected,
            catalyst.n_atoms,
            substrate.n_atoms,
        )
        return None

    return _format_fragmented(
        composite.charge,
        composite.multiplicity,
        catalyst.charge,
        catalyst.multiplicity,
        atoms[: catalyst.n_atoms],
        substrate.charge,
        substrate.multiplicity,
        atoms[catalyst.n_atoms :],
    )
