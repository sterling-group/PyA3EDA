"""
Argument Parser Module

Parses command-line arguments for PyA3EDA.
"""

import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="PyA3EDA: Python Automatization of Electronic Structure Data Analysis",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("yaml_config", type=str, help="Path to the configuration YAML file")
    parser.add_argument("-l", "--log", type=str, default="info",
                        choices=["debug", "info", "warning", "error", "critical"],
                        help="Logging level")
    parser.add_argument("-o", "--overwrite", type=str,
                        choices=["all", "nofile", "CRASH", "terminated", "SUCCESSFUL", "running", "VALIDATION"],
                        help="Overwrite input files based on their status")
    parser.add_argument("-g", "--generate", action="store_true",
                        help="Generate input files and optionally execute calculations")
    parser.add_argument("-r", "--run", type=str,
                        choices=["all", "nofile", "CRASH", "terminated", "SUCCESSFUL", "running", "VALIDATION"],
                        help="Execute input files based on their status")
    parser.add_argument("-e", "--extract", type=str, nargs='?', const="SUCCESSFUL", default=None,
                        choices=["all", "nofile", "CRASH", "terminated", "SUCCESSFUL", "running", "VALIDATION"],
                        help="Extract data from output files and generate energy profiles (defaults to SUCCESSFUL)")
    parser.add_argument("--sp-strategy", type=str, default="smart",
                        choices=["always", "smart", "never"],
                        help="Control SP file generation: 'always' (always generate), 'smart' (only when opt output exists), 'never' (skip SP files)")
    parser.add_argument("--no-plots", action="store_true",
                        help="Disable automatic plot generation during data extraction")
    parser.add_argument("--no-barplots", action="store_true",
                        help="Disable automatic barplot generation during data extraction")
    return parser.parse_args()
