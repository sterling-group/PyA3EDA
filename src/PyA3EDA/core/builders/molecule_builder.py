"""
Molecule Builder Module

This module provides functions to build the molecule section for Q-Chem input files.
For OPT calculations, coordinates come from template XYZ files.
For SP calculations, coordinates come from previous optimization output files.
"""

import logging

from PyA3EDA.core.parsers.output_xyz_parser import parse_qchem_output_xyz
from PyA3EDA.core.parsers.xyz_parser import parse_xyz


def _build_standard_section(charge: int, multiplicity: int, atoms: list[str]) -> str:
    """Return a standard molecule section string."""
    return f"{charge} {multiplicity}\n" + "\n".join(atoms)


def _build_fragmented_section(
    overall_charge: int,
    overall_mult: int,
    catalyst_charge: int,
    catalyst_mult: int,
    catalyst_atoms: list[str],
    substrate_charge: int,
    substrate_mult: int,
    substrate_atoms: list[str],
) -> str:
    """Return a fragmented molecule section string."""
    return (
        f"{overall_charge} {overall_mult}\n"
        f"---\n"
        f"{catalyst_charge} {catalyst_mult}\n"
        f"{'\n'.join(catalyst_atoms)}\n"
        f"---\n"
        f"{substrate_charge} {substrate_mult}\n"
        f"{'\n'.join(substrate_atoms)}"
    )


def _get_coordinates(
    template_data: dict, output_text: str = None, identifier: str = None
) -> list[str]:
    """Get coordinates from either template or output file with fallback."""
    if output_text and identifier:
        # SP mode - get coordinates from output file
        output_data = parse_qchem_output_xyz(output_text, identifier)
        if output_data:
            return output_data["atoms"]
        else:
            # Fall back to template if output parsing fails
            logging.warning(
                f"Failed to parse output for '{identifier}', falling back to template"
            )
    elif output_text and not identifier:
        logging.warning(
            "Cannot parse output text without identifier, using template coordinates"
        )

    # Return template coordinates
    return template_data["atoms"]


def _parse_composite_id(
    composite_id: str, catalyst_id: str = None, substrate_id: str = None
) -> tuple:
    """Parse composite identifier into catalyst and substrate IDs."""
    if catalyst_id is None or substrate_id is None:
        parts = composite_id.split("-")
        if len(parts) < 2:
            logging.error(
                f"Composite identifier '{composite_id}' does not contain both catalyst and substrate parts"
            )
            return None, None

        derived_catalyst_id = parts[0]
        derived_substrate_id = "-".join(parts[1:])

        catalyst_id = catalyst_id or derived_catalyst_id
        substrate_id = substrate_id or derived_substrate_id

    return catalyst_id, substrate_id


def build_standard_molecule_section(
    xyz_text: str, identifier: str, output_text: str = None
) -> str:
    """
    Build a standard molecule section for either OPT or SP calculation.

    Args:
        xyz_text: XYZ template text
        identifier: Molecule identifier
        output_text: If provided, coordinates will be parsed from this output file (SP mode)

    Returns:
        Molecule section string
    """
    # Parse the template
    template_data = parse_xyz(xyz_text, identifier)
    if template_data is None:
        logging.error(f"Failed to parse XYZ template for '{identifier}'")
        return ""

    # Get coordinates from template or output
    atoms = _get_coordinates(template_data, output_text, identifier)

    return _build_standard_section(
        template_data["charge"], template_data["multiplicity"], atoms
    )


def build_fragmented_molecule_section(
    composite_xyz_text: str,
    composite_id: str,
    catalyst_xyz_text: str = None,
    substrate_xyz_text: str = None,
    catalyst_id: str = None,
    substrate_id: str = None,
    output_text: str = None,
) -> str:
    """
    Build a fragmented molecule section for either OPT or SP calculation.

    Args:
        composite_xyz_text: Composite XYZ template text
        composite_id: Composite molecule identifier (catalyst-substrate)
        catalyst_xyz_text: XYZ text for the catalyst component
        substrate_xyz_text: XYZ text for the substrate component
        catalyst_id: Catalyst identifier (derived from composite_id if not provided)
        substrate_id: Substrate identifier (derived from composite_id if not provided)
        output_text: If provided, coordinates will be parsed from this output file (SP mode)

    Returns:
        Molecule section string
    """
    # Parse the composite ID
    catalyst_id, substrate_id = _parse_composite_id(
        composite_id, catalyst_id, substrate_id
    )
    if catalyst_id is None or substrate_id is None:
        return ""

    # Parse the composite template
    composite_data = parse_xyz(composite_xyz_text, composite_id)
    if composite_data is None:
        logging.error(f"Failed to parse composite XYZ for '{composite_id}'")
        return ""

    # Parse catalyst template
    if catalyst_xyz_text is None:
        logging.error(f"No catalyst XYZ text provided for '{catalyst_id}'")
        return ""

    catalyst_data = parse_xyz(catalyst_xyz_text, catalyst_id)
    if catalyst_data is None:
        logging.error(f"Failed to parse catalyst XYZ for '{catalyst_id}'")
        return ""

    # Parse substrate template
    if substrate_xyz_text is None:
        logging.error(f"No substrate XYZ text provided for '{substrate_id}'")
        return ""

    substrate_data = parse_xyz(substrate_xyz_text, substrate_id)
    if substrate_data is None:
        logging.error(f"Failed to parse substrate XYZ for '{substrate_id}'")
        return ""

    # Get fragment sizes
    catalyst_atom_count = catalyst_data["n_atoms"]
    substrate_atom_count = substrate_data["n_atoms"]
    total_atoms = catalyst_atom_count + substrate_atom_count

    # Get coordinates from template or output
    atoms = _get_coordinates(composite_data, output_text, composite_id)

    # Ensure we have enough atoms
    if len(atoms) < total_atoms:
        logging.error(
            f"Insufficient atom lines for '{composite_id}'. Expected {total_atoms}, got {len(atoms)}."
        )
        return ""

    # Split atoms between catalyst and substrate
    catalyst_atoms = atoms[:catalyst_atom_count]
    substrate_atoms = atoms[
        catalyst_atom_count : catalyst_atom_count + substrate_atom_count
    ]

    return _build_fragmented_section(
        composite_data["charge"],
        composite_data["multiplicity"],
        catalyst_data["charge"],
        catalyst_data["multiplicity"],
        catalyst_atoms,
        substrate_data["charge"],
        substrate_data["multiplicity"],
        substrate_atoms,
    )
