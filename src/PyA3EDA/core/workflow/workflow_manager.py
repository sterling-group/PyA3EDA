"""
WorkflowManager

Orchestrates the workflow for PyA3EDA.
"""

import logging
from pathlib import Path
from PyA3EDA.core.config.config_manager import ConfigManager

class WorkflowManager:
    def __init__(self, config_manager: ConfigManager, args=None) -> None:
        self.config_manager = config_manager
        self.system_dir = Path.cwd()
        self.args = args

    def generate_inputs(self) -> None:
        """
        Delegate input file generation to the builder.
        """
        from PyA3EDA.core.builders import builder
        
        # Extract arguments with safe defaults
        overwrite = getattr(self.args, 'overwrite', None) if self.args else None
        sp_strategy = getattr(self.args, 'sp_strategy', 'smart') if self.args else 'smart'
        
        builder.generate_all_inputs(self.config_manager, self.system_dir, overwrite, sp_strategy)

    def run_calculations(self) -> None:
        """
        Run calculations based on the specified run criteria.
        """
        from PyA3EDA.core.runners.executor import run_all_calculations
        
        # Extract run criteria from args with safe defaults
        run_criteria = getattr(self.args, 'run', None) if self.args else None
        
        run_all_calculations(
            self.config_manager.processed_config,
            self.system_dir,
            run_criteria
        )

    def check_status(self) -> None:
        """
        Uses the status checker to iterate over expected input paths and
        prints a formatted status report and summary.
        """
        from PyA3EDA.core.status.status_checker import check_all_statuses
        check_all_statuses(self.config_manager.processed_config, self.system_dir)

    def extract_data(self) -> None:
        """
        Extract data from output files and save to CSV.
        """
        from PyA3EDA.core.exporters.data_exporter import extract_and_save
        
        # Get extraction criteria
        # If extract is a boolean flag, convert to string criteria
        if hasattr(self.args, 'extract'):
            if self.args.extract is True:
                criteria = "SUCCESSFUL"  # Default when -e flag is used
            else:
                criteria = self.args.extract  # If it's a string value
        else:
            criteria = "SUCCESSFUL"  # Default if not specified
        
        # Let data_exporter handle the results directory creation
        extract_and_save(
            self.config_manager.processed_config,
            self.system_dir,
            criteria=criteria
        )
