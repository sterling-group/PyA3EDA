"""
Executor Module

Handles the execution of Q-Chem calculations via subprocess.
"""

import logging
import subprocess
import time
from pathlib import Path


def execute_qchem(
    input_file: Path,
    cores: int = 32,
    time_limit: str = "7-00:00:00",
    node: str = "c-06-10,c-06-11,c-06-12",
) -> bool:
    """Execute a Q-Chem calculation using qqchem submission script."""
    logging.info(f"Executing qqchem for {input_file}")
    try:
        subprocess.run(
            # ['qqchem', '-c', str(cores), '-t', time_limit, '-M', '8000', '-m', '256000', input_file.name],
            # ['qqchem', '-c', str(cores), '-t', time_limit, input_file.name],
            # ['qqchem', '-c', str(cores), '-t', time_limit, '-M', '8000', '-m', '256000', '-v', 'modqchem', '--qcsetup', '/groups/sterling/software-tools/qchem/qcsetup6211', input_file.name],
            [
                "qqchem",
                "-c",
                str(cores),
                "-t",
                time_limit,
                "-v",
                "modqchem",
                "--qcsetup",
                "/groups/sterling/software-tools/qchem/qcsetup6211",
                input_file.name,
            ],
            # '-x', node,
            check=True,
            cwd=input_file.parent,
        )
        logging.info(f"Submission successful for {input_file}")
        time.sleep(5.2)  # Small delay to avoid overwhelming the scheduler
        return True
    except Exception as e:
        logging.error(f"Error executing qqchem for {input_file}: {e}")
        return False


def run_all_calculations(config_manager, system_dir, run_criteria=None):
    """
    Run calculations based on the specified run criteria.

    Args:
        config_manager: ConfigManager instance or raw config dict
        system_dir: Base system directory
        run_criteria: Criteria for which files to run
    """
    from PyA3EDA.core.builders.builder import iter_input_paths
    from PyA3EDA.core.status.status_checker import should_process_file

    if not run_criteria:
        logging.warning(
            "No run criteria specified. Use --run option with a valid criteria."
        )
        return

    logging.info(f"Running calculations with criteria: {run_criteria}")

    # Get all input paths and process them based on criteria
    count = 0
    for input_path in iter_input_paths(config_manager, system_dir):
        if not input_path.exists():
            continue

        should_run, reason = should_process_file(input_path, run_criteria)

        if should_run:
            logging.info(
                f"Submitting job ({reason}): {input_path.relative_to(system_dir)}"
            )
            if execute_qchem(input_path):
                count += 1

    logging.info(f"Total jobs submitted: {count}")
