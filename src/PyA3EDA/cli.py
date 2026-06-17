"""
Command-Line Interface for PyA3EDA

Entry point for running PyA3EDA from the command line.
It parses command-line arguments and delegates to the WorkflowManager.
"""

import logging

from PyA3EDA.core.config.config_manager import ConfigManager
from PyA3EDA.core.utils.argument_parser import parse_arguments
from PyA3EDA.core.workflow.workflow_manager import WorkflowManager


def main() -> None:
    args = parse_arguments()
    numeric_level = getattr(logging, args.log.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    config_manager = ConfigManager(args.yaml_config)
    workflow = WorkflowManager(config_manager, args)

    if args.generate:
        workflow.generate_inputs()
        if args.run:
            workflow.run_calculations()
    elif args.run:
        workflow.run_calculations()
    elif args.extract:
        workflow.extract_data()
    else:
        workflow.check_status()


if __name__ == "__main__":
    main()
