"""Canonical registry dump + a branch-covering config, for parity checks.

``dump_registry`` serialises a built :class:`~pya3eda.registry.CalcRegistry` to a
deterministic, base-dir-relative text blob covering every value the enumeration
produces — each ``CalcSpec`` (id fields, relative paths, fragment flag, eda2,
present species) and each ``ProfileSpec`` (id, leader/ref, and per stage the
label, summed ``CalcID``s, NI reference, and alternatives). It reads only the
public ``CalcRegistry`` API, so it is a stable oracle across the registry
refactor. ``snapshot_config`` exercises every branch (dimer catalyst, ≥2 included
reactants/products → combinations + alternatives, a free spectator, solvent +
gas levels, opt + sp modes) so the snapshot locks the full enumeration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pya3eda.config import (
    CatalystConfig,
    Config,
    LevelConfig,
    SpeciesConfig,
    TheoryConfig,
)

if TYPE_CHECKING:
    from pya3eda.ids import CalcID, ProfileID
    from pya3eda.registry import CalcRegistry


def _cid(c: CalcID) -> str:
    """Compact, total CalcID string."""
    return (
        f"{c.method_key}/{c.catalyst or '-'}/{c.stage}/{c.species}/"
        f"{c.calc_type or '-'}/{c.mode}/{c.sp_subfolder or '-'}"
    )


def _pid(p: ProfileID) -> str:
    """Compact ProfileID string."""
    return (
        f"{p.method_key}/{p.catalyst or '-'}/{p.calc_type or '-'}/{p.mode}/{p.sp_subfolder or '-'}"
    )


def dump_registry(reg: CalcRegistry) -> str:
    """Serialise *reg* to a deterministic, base-dir-relative text blob."""
    base = reg.base_dir
    out: list[str] = ["== CALCS =="]
    for s in reg.all_calcs:
        out.append(
            f"{_cid(s.id)} :: {s.input_path.relative_to(base)} frag={int(s.is_fragmented)} "
            f"eda2={s.eda2} pr=[{','.join(s.present_reactants)}] "
            f"pp=[{','.join(s.present_products)}] pc=[{','.join(s.present_catalysts)}]"
        )
    out.append("== PROFILES ==")
    for p in reg.all_profiles:
        out.append(f"PID {_pid(p.id)} leader={int(p.selection_leader)} ref={p.ref_stage}")
        for st in p.stages:
            ni = "-"
            if st.ni_ref is not None:
                ni = (
                    f"R[{'|'.join(_cid(c) for c in st.ni_ref.ref_cids)}]"
                    f"T[{'|'.join(_cid(c) for c in st.ni_ref.trans_cids)}]"
                    f"ssc={int(st.ni_ref.apply_ssc_to_g_ni)}"
                )
            alts = " ;; ".join(
                f"{a.label}=[{'|'.join(_cid(c) for c in a.calc_ids)}]ni={1 if a.ni_ref else 0}"
                for a in st.alternatives
            )
            ids = "|".join(_cid(c) for c in st.calc_ids)
            out.append(f"  {st.name} | {st.label} | [{ids}] | ni={ni} | alts={alts}")
    out.append("MK=" + ",".join(reg.method_keys))
    out.append("CO=" + ",".join(reg.catalyst_order))
    out.append("DC=" + ",".join(sorted(reg.dimer_catalysts)))
    return "\n".join(out) + "\n"


def snapshot_config() -> Config:
    """A configuration that exercises every enumeration branch."""
    return Config(
        levels=[
            LevelConfig(
                opt=TheoryConfig(method="m1", basis="b1", solvent="smd"),
                sp=[TheoryConfig(method="m2", basis="b2", solvent="smd", eda2=1)],
            ),
            LevelConfig(opt=TheoryConfig(method="m1", basis="b4", dispersion="d3")),
        ],
        catalysts=[CatalystConfig(name="c1", dimer=True)],
        reactants=[
            SpeciesConfig(name="r1"),
            SpeciesConfig(name="r2"),
            SpeciesConfig(name="r3", include=False),
        ],
        products=[SpeciesConfig(name="p1"), SpeciesConfig(name="p2")],
    )
