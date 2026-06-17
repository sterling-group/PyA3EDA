"""
Q-Chem Status Parser

Parses the contents of Q-Chem status and error files to determine the calculation status.
"""

import re
from typing import Tuple


def parse_qchem_status(
    content: str, err_content: str, submission_exists: bool = False
) -> Tuple[str, str]:
    """
    Parses Q-Chem status and error text and returns a tuple (status, details).

    Args:
        content (str): The text content of the .out file.
        err_content (str): The text content of the .err file.

    Returns:
        Tuple[str, str]: Status and detailed message.
    """
    if "CANCELLED AT" in err_content:
        return "terminated", "Job cancelled by Queue"

    if "Error in Q-Chem run" in err_content or "Aborted" in err_content:
        status = "CRASH"
        error_msg = "Q-Chem execution crashed"
        if content:
            if "error occurred" in content:
                error_pattern = r"error occurred.*?\n\s*(.*?)(?:\n{2,}|\Z)"
                error_match = re.search(error_pattern, content, re.DOTALL)
                if error_match:
                    full_msg = error_match.group(1).strip()
                    error_msg = re.split(r"[.;]|\band\b", full_msg)[0].strip()
                else:
                    error_msg = "Unknown fatal error"
            elif "SGeom Failed" in content:
                error_msg = "Geometry optimization failed"
            elif "SCF failed to converge" in content:
                error_msg = "SCF convergence failure"
            elif "Insufficient memory" in content:
                error_msg = "Out of memory"
            else:
                error_msg = "Unknown failure"
        return status, error_msg

    # Check if job is still running based on submission file existence
    if submission_exists:
        return "running", "Job submission file exists"

    if not content:
        return "nofile", "Output file not found"

    # Check for running job in .out file
    if "Running on" in content and "Thank you very much" not in content:
        return "running", "Calculation in progress"

    if "Thank you very much" in content:
        time_pattern = r"Total job time:\s*(.*)"
        time_match = re.search(time_pattern, content)

        if time_match:
            time_str = time_match.group(1).strip()
            # Extract wall time in seconds
            wall_time_match = re.search(r"(\d+(?:\.\d+)?)s\(wall\)", time_str)

            if wall_time_match:
                wall_seconds = float(wall_time_match.group(1))
                # Convert to hours, minutes, seconds
                hours, remainder = divmod(wall_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                job_time = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
            else:
                job_time = time_str
        else:
            job_time = "unknown"

        return "SUCCESSFUL", f"Completed in {job_time}"

    if "Q-Chem fatal error occurred" in content:
        error_pattern = r"Q-Chem fatal error occurred.*?\n\s*(.*?)(?:\n\n|\Z)"
        error_match = re.search(error_pattern, content, re.DOTALL)
        if error_match:
            full_msg = error_match.group(1).strip()
            error_msg = re.split(r"[.;]", full_msg)[0].strip()
        else:
            error_msg = "Unknown fatal error"
        return "CRASH", error_msg

    if "SGeom Failed" in content:
        return "CRASH", "Geometry optimization failed"
    if "SCF failed to converge" in content:
        return "CRASH", "SCF convergence failure"
    if "Insufficient memory" in content:
        return "CRASH", "Out of memory"

    if "killed" in content.lower() or "terminating" in content.lower():
        return "terminated", "Job terminated unexpectedly"

    if content.strip():
        return "CRASH", "Unknown failure"

    return "empty", "Output file is empty"
