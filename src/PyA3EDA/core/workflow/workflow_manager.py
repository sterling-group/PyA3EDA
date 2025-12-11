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
        self.system_dir = config_manager.config_dir
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
            self.config_manager,
            self.system_dir,
            run_criteria
        )

    def check_status(self) -> None:
        """
        Uses the status checker to iterate over expected input paths and
        prints a formatted status report and summary.
        """
        from PyA3EDA.core.status.status_checker import check_all_statuses
        check_all_statuses(self.config_manager, self.system_dir)

    def extract_data(self) -> None:
        """
        Extracts all relevant calculation data based on the extraction criteria (default: "SUCCESSFUL"), 
        transforms and processes the data, exports the processed results, and generates profile plots 
        and barplots unless the --no-plots or --no-barplots flags are specified in the arguments.
        """
        from PyA3EDA.core.extractors.data_extractor import extract_all_data
        from PyA3EDA.core.extractors.profile_extractor_functional import process_all_profiles
        from PyA3EDA.core.extractors.delta_delta_extractor import extract_all_delta_delta
        from PyA3EDA.core.exporters.data_exporter import export_all_data
        from PyA3EDA.core.plotters.profile_plotter import plot_all_profiles
        from PyA3EDA.core.plotters.barplot_plotter import plot_delta_delta_barplots
        
        criteria = getattr(self.args, 'extract', None) if self.args else "SUCCESSFUL"
        catalyst_order = self.config_manager.get_catalyst_order()
        
        # Extract-Transform-Load pipeline
        raw_data = extract_all_data(self.config_manager, self.system_dir, criteria)
        processed_data = process_all_profiles(raw_data)
        delta_delta_data = extract_all_delta_delta(processed_data, catalyst_order)
        
        # Single unified export call
        export_all_data(processed_data, self.system_dir, delta_delta_data, catalyst_order)
        
        # Generate profile plots by default (can be disabled with --no-plots)
        generate_plots = not getattr(self.args, 'no_plots', False) if self.args else True
        if generate_plots:
            plot_all_profiles(processed_data, self.system_dir)
        
        # Generate delta-delta barplots by default (can be disabled with --no-barplots)
        generate_barplots = not getattr(self.args, 'no_barplots', False) if self.args else True
        if generate_barplots and delta_delta_data:
            plot_delta_delta_barplots(delta_delta_data, self.system_dir, catalyst_order)
