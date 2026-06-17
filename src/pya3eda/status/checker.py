"""Status checking and reporting for Q-Chem calculations."""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path

from pya3eda.ids import CalcSpec
from pya3eda.parser.qchem import parse_imaginary_freq, parse_opt_converged, parse_status
from pya3eda.registry import CalcRegistry
from pya3eda.utils import read_text

log = logging.getLogger(__name__)

# Dedicated logger for the formatted status report (no prefix formatting).
_report = logging.getLogger("pya3eda.status.report")
if not _report.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _report.addHandler(_handler)
    _report.propagate = False
    _report.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class Status(StrEnum):
    """Possible states of a Q-Chem calculation."""

    SUCCESSFUL = "SUCCESSFUL"
    CRASH = "CRASH"
    RUNNING = "running"
    TERMINATED = "terminated"
    NOFILE = "nofile"
    EMPTY = "empty"
    ABSENT = "absent"
    VALIDATION = "VALIDATION"


# ---------------------------------------------------------------------------
# Per-file status detection
# ---------------------------------------------------------------------------


def get_status(spec: CalcSpec) -> tuple[Status, str]:
    """Determine the status of a single calculation.

    Reads ``.out`` / ``.err`` / submission-sentinel files and returns
    ``(Status, detail_message)``.
    """
    input_path = spec.input_path

    if not input_path.exists():
        return Status.ABSENT, "Input file not found"

    out_text = read_text(spec.output_path) or ""
    err_text = read_text(spec.output_path.with_suffix(".err")) or ""

    # Check for running job based on submission sentinel files
    stem = input_path.stem
    submission_exists = bool(
        list(input_path.parent.glob(f"{stem}.in_[0-9]*.[0-9]*"))
    ) or bool(list(input_path.parent.glob(f".{stem}.in.[0-9]*.qcin.[0-9]*")))

    raw_status, detail = parse_status(out_text, err_text, submission_exists)
    try:
        status = Status(raw_status)
    except ValueError:
        status = Status.CRASH

    # Enhanced OPT validation for successful calculations
    if status == Status.SUCCESSFUL and spec.id.mode == "opt" and out_text:
        v_status, v_detail = _validate_opt(out_text, spec)
        if v_status is not None:
            return v_status, v_detail

    return status, detail


def _validate_opt(out_text: str, spec: CalcSpec) -> tuple[Status | None, str]:
    """Extra validation for converged OPT calculations.

    Returns ``(None, "")`` if everything is fine, or ``(VALIDATION, msg)`` on
    mismatch.
    """
    converged = parse_opt_converged(out_text)
    imag = parse_imaginary_freq(out_text)

    if not converged and imag is None:
        return None, ""

    is_ts = spec.id.stage == "ts"

    if is_ts:
        if imag != 1:
            return Status.VALIDATION, f"Conv: ts, Imag: {imag}"
    else:
        if imag is not None and imag > 0:
            return Status.VALIDATION, f"Conv: opt, Imag: {imag}"

    return None, ""


# ---------------------------------------------------------------------------
# Filtering helper (shared by runner / builder)
# ---------------------------------------------------------------------------


def should_process(spec: CalcSpec, criteria: str) -> bool:
    """Return ``True`` if *spec* should be processed given *criteria*.

    *criteria* is one of ``"all"``, ``"nofile"``, or a status name like
    ``"CRASH"``.
    """
    if criteria.lower() == "all":
        return True
    if criteria.lower() == "nofile":
        return not spec.output_path.exists()
    status, _ = get_status(spec)
    return status.value.lower() == criteria.lower()


# ---------------------------------------------------------------------------
# Grouped report
# ---------------------------------------------------------------------------


def _rel_display(spec: CalcSpec, base_dir: Path) -> str:
    """Build a display path: relative to base_dir, parent/stem (no suffix)."""
    try:
        rel = spec.input_path.relative_to(base_dir)
    except ValueError:
        rel = spec.input_path
    return str(rel.parent / rel.stem)


def _interleave_opt_sp(specs: list[CalcSpec]) -> list[CalcSpec]:
    """Reorder so each OPT is immediately followed by its SP calcs.

    Preserves the natural insertion order from the registry (which mirrors
    the config: no_cat → catalysts in config order, full→pol→frz).
    """
    from collections import OrderedDict

    sp_by_key: OrderedDict[tuple, list[CalcSpec]] = OrderedDict()
    opt_list: list[CalcSpec] = []

    for s in specs:
        cid = s.id
        key = (cid.catalyst, cid.stage, cid.species, cid.calc_type or "")
        if cid.mode == "opt":
            opt_list.append(s)
        else:
            sp_by_key.setdefault(key, []).append(s)

    result: list[CalcSpec] = []
    for s in opt_list:
        result.append(s)
        key = (s.id.catalyst, s.id.stage, s.id.species, s.id.calc_type or "")
        result.extend(sp_by_key.pop(key, []))

    # Any SP calcs without a matching OPT (unlikely but safe)
    for remaining in sp_by_key.values():
        result.extend(remaining)

    return result


def check_all(registry: CalcRegistry) -> None:
    """Print a grouped status report, streaming each line as it is checked."""
    base_dir = registry.base_dir
    overall: dict[str, int] = {}
    divider = "-" * 60

    for mk in registry.method_keys:
        specs = _interleave_opt_sp(registry.by_method(mk))
        if not specs:
            continue

        # Compute column width from full relative paths
        max_len = max(
            (len(_rel_display(s, base_dir)) for s in specs),
            default=len("Input File (rel)"),
        )
        max_len = max(max_len, len("Input File (rel)"))
        fmt = f"{{:<{max_len}}} | {{:<6}} | {{:<12}} | {{}}"

        _report.info("")
        _report.info(divider)
        _report.info(f"        GROUP: {mk}")
        _report.info(divider)
        _report.info(fmt.format("Input File (rel)", "Mode", "Status", "Details"))
        _report.info(divider)

        group_counts: dict[str, int] = {}
        for spec in specs:
            status, detail = get_status(spec)
            mode = "SP" if spec.id.mode == "sp" else "OPT"
            display = _rel_display(spec, base_dir)

            # Print immediately
            _report.info(fmt.format(display, mode, status.value, detail))

            group_counts[status.value] = group_counts.get(status.value, 0) + 1
            overall[status.value] = overall.get(status.value, 0) + 1

        _report.info("")
        _report.info(f"    Summary for {mk}:")
        for s, c in group_counts.items():
            _report.info(f"    {s} : {c}")

    eq_line = "=" * 60
    _report.info("")
    _report.info(eq_line)
    _report.info("        OVERALL STATUS SUMMARY")
    _report.info(eq_line)
    for s, c in overall.items():
        _report.info(f"    {s} : {c}")
    _report.info(eq_line)
