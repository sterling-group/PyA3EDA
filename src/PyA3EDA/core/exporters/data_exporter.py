"""
Data Exporter Module

Unified export functions for all data types:
- Raw calculation data (OPT/SP)
- Energy profiles (raw and filtered)
- Delta-delta barrier contributions
- XYZ coordinate files
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from PyA3EDA.core.utils.file_utils import write_text


def _write_csv(
    data: List[Dict[str, Any]], file_path: Path, data_type: str = "data"
) -> bool:
    """Write list of dicts to CSV. Returns True on success."""
    if not data:
        return False
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(data).to_csv(file_path, index=False)
        logging.info(f"Saved {len(data)} {data_type} rows to {file_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to write {data_type} CSV {file_path}: {e}")
        return False


def _write_xyz(data_list: List[Dict[str, Any]], output_dir: Path) -> int:
    """Write XYZ coordinate files. Returns count of files written."""
    if not data_list:
        return 0

    from PyA3EDA.core.utils.xyz_format_utils import format_xyz_content

    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for data in data_list:
        coords = data.get("coordinates")
        if not coords:
            continue

        xyz_content = format_xyz_content(
            coords.get("n_atoms", 0),
            coords.get("Charge", 0),
            coords.get("Multiplicity", 1),
            coords.get("atoms", []),
        )
        if not xyz_content:
            continue

        file_stem = data.get("output_file_stem", data.get("Species", "unknown"))
        if file_stem.endswith("_opt"):
            file_stem = file_stem[:-4]

        if write_text(output_dir / f"{file_stem}.xyz", xyz_content):
            count += 1

    logging.info(f"Written {count} XYZ files to {output_dir}")
    return count


def _build_delta_delta_rows(
    catalyst_data: Dict[str, Dict[str, Any]],
    catalyst_order: List[str],
    energy_type: str,
) -> List[Dict[str, Any]]:
    """Build CSV rows for delta-delta data, respecting catalyst order."""
    rows = []
    for catalyst in catalyst_order:
        if catalyst not in catalyst_data:
            continue
        data = catalyst_data[catalyst]
        barriers = data.get("barriers", {})
        contribs = data.get("contributions", {})
        rows.append(
            {
                "Catalyst": catalyst,
                f"Barrier_uncat ({energy_type})": barriers.get("uncat"),
                f"Barrier_frz ({energy_type})": barriers.get("frz"),
                f"Barrier_pol ({energy_type})": barriers.get("pol"),
                f"Barrier_full ({energy_type})": barriers.get("full"),
                f"ΔΔ{energy_type}‡_frz": contribs.get("frz"),
                f"ΔΔ{energy_type}‡_pol": contribs.get("pol"),
                f"ΔΔ{energy_type}‡_ct": contribs.get("ct"),
                f"ΔΔ{energy_type}‡_complete": contribs.get("complete"),
            }
        )
    return rows


def export_all_data(
    processed_data: Dict[str, Dict[str, Any]],
    base_dir: Path,
    delta_delta_data: Dict[str, Dict[str, Any]] = None,
    catalyst_order: List[str] = None,
) -> None:
    """
    Export all processed data to organized file structure.

    Args:
        processed_data: Method combo data with raw data + profiles
        base_dir: Base directory for results
        delta_delta_data: Optional pre-extracted delta-delta contributions
        catalyst_order: Optional catalyst order for delta-delta export

    Directory structure:
        results/{method_combo}/
        ├── raw_data/      - Raw OPT/SP data + raw profiles
        ├── profiles/      - Filtered profiles (E and G)
        ├── delta_delta/   - Barrier contributions
        └── xyz_files/     - Coordinate files
    """
    if not processed_data:
        logging.warning("No processed data provided for export")
        return

    results_dir = base_dir / "results"
    total_files = 0

    for combo_name, combo_data in processed_data.items():
        try:
            dirs = {
                "raw": results_dir / combo_name / "raw_data",
                "profiles": results_dir / combo_name / "profiles",
                "delta_delta": results_dir / combo_name / "delta_delta",
                "xyz": results_dir / combo_name / "xyz_files",
            }
            combo_files = 0

            # Export OPT and SP data
            for calc_mode in ["opt", "sp"]:
                data_key = f"{calc_mode}_data"
                raw_data = combo_data.get(data_key)
                if not raw_data:
                    continue

                method_combo = (
                    combo_name
                    if calc_mode == "opt"
                    else raw_data[0].get("SP_Method_Combo", combo_name)
                )

                # Raw calculation data
                if _write_csv(
                    raw_data,
                    dirs["raw"] / f"{calc_mode}_{method_combo}.csv",
                    calc_mode.upper(),
                ):
                    combo_files += 1

                # Profiles per catalyst
                profiles = combo_data.get("profiles", {}).get(data_key, {})
                for catalyst, cat_profiles in profiles.items():
                    # Raw profile
                    if _write_csv(
                        cat_profiles.get("raw"),
                        dirs["raw"]
                        / f"raw_{calc_mode}_profile_{method_combo}_{catalyst}.csv",
                        "raw profile",
                    ):
                        combo_files += 1
                    # Filtered profiles
                    for energy_type in ["E", "G"]:
                        if _write_csv(
                            cat_profiles.get(energy_type),
                            dirs["profiles"]
                            / f"{calc_mode}_profile_{energy_type}_{method_combo}_{catalyst}.csv",
                            f"{energy_type} profile",
                        ):
                            combo_files += 1

                # Delta-delta data
                if delta_delta_data and catalyst_order:
                    dd_combo = delta_delta_data.get(combo_name, {}).get(data_key, {})
                    for energy_type in ["E", "G"]:
                        rows = _build_delta_delta_rows(
                            dd_combo.get(energy_type, {}), catalyst_order, energy_type
                        )
                        filename = (
                            f"delta_delta_{combo_name}_{energy_type}.csv"
                            if calc_mode == "opt"
                            else f"delta_delta_{calc_mode}_{combo_name}_{energy_type}.csv"
                        )
                        if _write_csv(
                            rows, dirs["delta_delta"] / filename, "delta-delta"
                        ):
                            combo_files += 1

            # XYZ files
            combo_files += _write_xyz(combo_data.get("xyz_data", []), dirs["xyz"])

            total_files += combo_files
            logging.info(f"Exported {combo_name}: {combo_files} files")

        except Exception as e:
            logging.error(f"Failed to export {combo_name}: {e}")

    logging.info(f"Export completed: {len(processed_data)} combos, {total_files} files")
