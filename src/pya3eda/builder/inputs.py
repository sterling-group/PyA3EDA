"""Build all Q-Chem input files from a CalcRegistry.

This is the **only** module that creates files and directories.  It iterates
every ``CalcSpec`` in the registry, assembles the ``$rem`` and ``$molecule``
sections, and writes the final ``.in`` file to disk.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pya3eda.builder.molecule import (
    _load_xyz,
    build_fragmented_molecule,
    build_standard_molecule,
)
from pya3eda.builder.rem import build_opt_rem, build_sp_rem
from pya3eda.errors import TemplateNotFoundError
from pya3eda.ids import CalcSpec
from pya3eda.parser.qchem import parse_status
from pya3eda.parser.xyz import parse_xyz
from pya3eda.registry import CalcRegistry
from pya3eda.utils import read_text, write_text

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_all(
    registry: CalcRegistry,
    template_dir: Path,
    *,
    overwrite: str | None = None,
    sp_strategy: str = "smart",
) -> None:
    """Create ``.in`` files for every calculation in *registry*.

    Parameters
    ----------
    registry : CalcRegistry
        The registry enumerating all expected calculations.
    template_dir : Path
        Root directory that contains ``templates/rem/``, ``templates/molecule/``
        and ``templates/base_template.in``.
    overwrite : str | None
        ``None`` → skip existing; ``"all"`` → overwrite everything;
        ``"CRASH"`` / ``"terminated"`` → overwrite only matching status.
    sp_strategy : str
        ``"always"`` — always generate SP files.
        ``"smart"``  — only if the OPT converged successfully (status + validation check).
        ``"never"``  — skip SP files entirely.
    """
    base_template_path = template_dir / "base_template.in"
    base_template = read_text(base_template_path)
    if base_template is None:
        raise TemplateNotFoundError(f"Base template not found: {base_template_path}")

    for spec in registry.all_calcs:
        _build_one(spec, registry, template_dir, base_template, overwrite, sp_strategy)


def build_calc(
    spec: CalcSpec,
    registry: CalcRegistry,
    template_dir: Path,
    *,
    overwrite: str | None = None,
    sp_strategy: str = "smart",
) -> None:
    """Build the input file for a single calculation (e.g. an SP once its OPT is done)."""
    base_template = read_text(template_dir / "base_template.in")
    if base_template is None:
        raise TemplateNotFoundError(f"Base template not found: {template_dir / 'base_template.in'}")
    _build_one(spec, registry, template_dir, base_template, overwrite, sp_strategy)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _build_one(
    spec: CalcSpec,
    registry: CalcRegistry,
    template_dir: Path,
    base_template: str,
    overwrite: str | None,
    sp_strategy: str,
) -> None:
    """Assemble and write a single Q-Chem input file."""
    cid = spec.id
    file_path = spec.input_path

    # SP strategy gate
    if cid.mode == "sp":
        if sp_strategy == "never":
            return
        if sp_strategy == "smart" and not _opt_successful(spec, registry):
            log.info("Skipping SP (OPT not successful): %s", file_path)
            return

    # Overwrite gate
    if file_path.exists():
        if not _should_overwrite(file_path, overwrite):
            log.info("Skipping (exists): %s", file_path)
            return
        log.info("Overwriting: %s", file_path)

    # Molecule section
    result = _build_molecule_section(spec, registry, template_dir)
    if result is None:
        log.error("Failed to build molecule section: %s", file_path)
        return
    molecule_section, n_atoms = result

    # REM section
    rem_section = _build_rem_section(spec, template_dir, n_atoms=n_atoms)

    # Geom opt section
    geom_block = ""
    if cid.mode == "opt":
        geom_text = read_text(template_dir / "rem" / "geom_opt.rem")
        if geom_text:
            geom_block = "\n\n" + geom_text.strip("\n")

    # Solvent block
    solvent_block = ""
    if spec.solvent and spec.solvent.lower() != "false":
        solvent_path = template_dir / "rem" / f"solvent_{spec.solvent}.rem"
        solvent_text = read_text(solvent_path)
        if solvent_text:
            solvent_block = "\n\n" + solvent_text.strip("\n")

    template_text = base_template.strip("\n") + geom_block + solvent_block + "\n"
    content = template_text.format(
        molecule_section=molecule_section.rstrip(),
        rem_section=rem_section.rstrip(),
    )

    if not content.strip():
        log.error("Empty content for %s — skipping", file_path)
        return

    write_text(file_path, content)
    log.info("Written: %s", file_path)


def _opt_successful(sp_spec: CalcSpec, registry: CalcRegistry) -> bool:
    """Check whether the corresponding OPT calculation completed successfully."""
    try:
        opt_spec = registry.get(sp_spec.id.to_opt())
    except KeyError:
        return False

    from pya3eda.status.checker import Status, get_status

    status, _ = get_status(opt_spec)
    return status == Status.SUCCESSFUL


def _should_overwrite(file_path: Path, overwrite: str | None) -> bool:
    """Return *True* if *file_path* should be overwritten given the policy."""
    if overwrite == "all":
        return True
    if overwrite is None:
        return False
    # Check current file status
    out_path = file_path.with_suffix(".out")
    err_path = file_path.with_suffix(".err")
    out_text = read_text(out_path) or ""
    err_text = read_text(err_path) or ""
    status, _ = parse_status(out_text, err_text)
    return status.upper() == overwrite.upper()


def _build_molecule_section(
    spec: CalcSpec,
    registry: CalcRegistry,
    template_dir: Path,
) -> tuple[str, int] | None:
    """Load XYZ templates and build the molecule section.

    Returns ``(molecule_text, n_atoms)`` or ``None`` on failure.
    """
    cid = spec.id

    # For SP: read the OPT output to use optimised coordinates
    opt_output_text: str | None = None
    if cid.mode == "sp":
        try:
            opt_spec = registry.get(cid.to_opt())
            opt_output_text = read_text(opt_spec.output_path)
        except KeyError:
            pass

    # Determine template name
    if cid.stage == "ts" and cid.catalyst is None:
        template_name = "tscomplex"
    elif cid.stage in ("preTS", "postTS", "ts"):
        # Catalyzed stages: prefix from stage, species is clean
        template_name = f"{cid.stage}_{cid.species}"
    else:
        template_name = cid.species

    if spec.is_fragmented:
        return _build_fragmented(
            template_dir,
            template_name,
            cid.catalyst,
            cid.species,
            cid.calc_type,
            opt_output_text,
        )
    return _build_standard(template_dir, template_name, opt_output_text)


def _build_standard(
    template_dir: Path,
    template_name: str,
    opt_output_text: str | None,
) -> tuple[str, int] | None:
    """Build molecule section from a standard (non-fragmented) XYZ file."""
    xyz_text = _load_xyz(template_dir, template_name)
    if xyz_text is None:
        return None
    data = parse_xyz(xyz_text)
    if data is None:
        return None
    mol = build_standard_molecule(xyz_text, opt_output_text)
    if mol is None:
        return None
    return mol, data.n_atoms


def _build_fragmented(
    template_dir: Path,
    template_name: str,
    catalyst: str | None,
    species: str,
    calc_type: str | None,
    opt_output_text: str | None,
) -> tuple[str, int] | None:
    """Build molecule section from fragmented (catalyst + substrate) XYZ files."""
    composite_text = _load_xyz(template_dir, template_name, calc_type)
    if composite_text is None:
        return None
    data = parse_xyz(composite_text)
    if data is None:
        return None

    # Derive catalyst / substrate identifiers
    parts = species.split("-", 1)
    cat_id = catalyst if catalyst else parts[0]
    substrate_id = parts[1] if len(parts) >= 2 else species

    cat_text = _load_xyz(template_dir, cat_id)
    sub_text = _load_xyz(template_dir, substrate_id)
    if cat_text is None or sub_text is None:
        return None

    mol = build_fragmented_molecule(composite_text, cat_text, sub_text, opt_output_text)
    if mol is None:
        return None
    return mol, data.n_atoms


def _build_rem_section(
    spec: CalcSpec,
    template_dir: Path,
    *,
    n_atoms: int = 2,
) -> str:
    """Build the REM section from spec metadata."""
    cid = spec.id

    if cid.mode == "opt":
        # Determine jobtype — single atoms cannot be optimised
        if n_atoms <= 1:
            jobtype = "sp"
        elif cid.stage == "ts":
            jobtype = "ts"
        else:
            jobtype = "opt"

        return build_opt_rem(
            template_dir,
            method=spec.method_name,
            basis=spec.basis_set,
            dispersion=spec.dispersion,
            solvent=spec.solvent,
            jobtype=jobtype,
            calc_type=cid.calc_type,
        )
    # SP mode — EDA parameters key off calc_type. A calc is an EDA fragment
    # calculation iff it carries a calc_type (full/pol/frz); standalone molecules
    # (uncatalyzed species, the catalyst ``cat``, and the ``dimer``) have
    # calc_type None and must not request EDA — emitting eda2 != 0 on a
    # single-fragment $molecule makes Q-Chem run a fragment-EDA with no fragments.
    eda2 = str(spec.eda2 or 0) if cid.calc_type is not None else "0"

    scfmi_freeze = "1" if cid.calc_type == "frz_cat" else "0"
    eda_bsse = "true" if cid.calc_type == "full_cat" else "false"

    return build_sp_rem(
        template_dir,
        method=spec.method_name,
        basis=spec.basis_set,
        dispersion=spec.dispersion,
        solvent=spec.solvent,
        eda2=eda2,
        scfmi_freeze_ss=scfmi_freeze,
        eda_bsse=eda_bsse,
    )
