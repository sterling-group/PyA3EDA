#!/home/dal063121/.conda/envs/extrplt/bin/python3

import argparse
import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import yaml
import pandas as pd

class Constants:
    """Class holding program constants."""
    HARTREE_TO_KCALMOL = 627.5096080305927
    CAL_TO_KCAL = 1e-3
    ESCAPE_MAP = {
        ' ': '-space-', '(': '-paren-', ')': '-paren-',
        '[': '-bracket-', ']': '-bracket-',
        '{': '-brace-', '}': '-brace-',
        ',': '-comma-', ';': '-semicolon-',
        '*': '-asterisk-', '?': '-qmark-',
        '&': '-and-', '|': '-pipe-',
        '<': '-lt-', '>': '-gt-',
        '"': '-dq-', "'": '-sq-',
        '\\': '-backslash-', ':': '-colon-',
        '$': '-dollar-', '~': '-tilde-',
        '!': '-exclamation-', '=': '-equal-',
        '\t': '-tab-', '\n': '-newline-',
    }

class Utilities:
    """Static utility functions used across classes."""
    @staticmethod
    def get_energy_value(content: str, patterns: dict) -> Optional[float]:
        """Extract energy value from content."""
        for pattern_name in ["final_energy", "final_energy_fallback"]:
            match = patterns[pattern_name].search(content)
            if match:
                return float(match.group(1))
        return None

    @staticmethod
    def get_value_with_fallback(content: str, primary_pattern: re.Pattern,
                               fallback_pattern: re.Pattern) -> Tuple[Optional[float], Optional[str], bool]:
        """Extract value and unit using primary pattern, fallback to secondary if needed."""
        primary_match = primary_pattern.search(content)
        if primary_match:
            return float(primary_match.group(1)), primary_match.group(2), False
        fallback_match = fallback_pattern.search(content)
        if fallback_match:
            return float(fallback_match.group(1)), fallback_match.group(2), True
        return None, None, False

    @staticmethod
    def get_calculation_label(relative_path: Path) -> str:
        """Generate a calculation label based on the directory structure."""
        parts = relative_path.parts[:-1]
        return "/".join(parts)

    @staticmethod
    def count_atoms(molecule_section: str) -> int:
        """Count the number of atoms in the molecule section."""
        lines = [line.strip() for line in molecule_section.splitlines() if line.strip()]
        if not lines:
            logging.error("Empty molecule section")
            return 0
        return len(lines[1:])  # First line is charge/multiplicity

class FileOperations:
    """Base class for file operations."""
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def read_file(self, file_path: Path) -> Optional[str]:
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore").rstrip()
        except Exception as e:
            logging.error(f"Error reading file '{file_path}': {e}")
            return None

    def write_file(self, file_path: Path, content: str) -> bool:
        try:
            file_path.write_text(content)
            return True
        except Exception as e:
            logging.error(f"Error writing file '{file_path}': {e}")
            return False

class FileHandler(FileOperations):
    """Class for handling file operations with path sanitization."""
    @staticmethod
    def sanitize_filename(name: str) -> str:
        sanitized = name
        for char, replacement in Constants.ESCAPE_MAP.items():
            sanitized = sanitized.replace(char, replacement)
        return sanitized

    def verify_templates(self, required_templates: List[Path]) -> None:
        """Ensure all required template files exist."""
        missing_templates = [t for t in required_templates if not t.is_file()]
        if missing_templates:
            for tmpl in missing_templates:
                logging.error(f'Missing template file: {tmpl}')
            sys.exit(1)

    def create_directory_structure(self, base_dir: Path, paths: List[str]) -> None:
        """Create directory structures with sanitized path names."""
        for path in paths:
            # Split path and sanitize each component
            components = [self.sanitize_filename(p) for p in path.split('/')]
            dir_path = base_dir / Path(*components)
            dir_path.mkdir(parents=True, exist_ok=True)

class ConfigManager:
    """Class for managing configuration."""
    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        self.sanitized_config = self._sanitize_config()

    def load_config(self, config_path: str) -> dict:
        config_file = Path(config_path)
        if not config_file.is_file():
            raise FileNotFoundError(f'Configuration file not found: {config_path}')
        try:
            with config_file.open() as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as err:
            raise ValueError(f'Error parsing YAML configuration: {err}')

    def _sanitize_config(self) -> dict:
        """Create sanitized version of config values for paths."""
        return {
            'methods': [FileHandler.sanitize_filename(m) for m in self.config['methods']],
            'bases': [FileHandler.sanitize_filename(b) for b in self.config['bases']],
            'catalysts': [FileHandler.sanitize_filename(c) for c in self.config['catalysts']],
            'reactant1': FileHandler.sanitize_filename(self.config['reactant1']),
            'reactant2': FileHandler.sanitize_filename(self.config['reactant2'])
        }

    def get_calculation_paths(self, system_dir: Path) -> List[Path]:
        """Get all possible calculation paths with sanitized names."""
        paths = []
        for method in self.sanitized_config['methods']:
            for basis in self.sanitized_config['bases']:
                method_basis_dir = system_dir / f'{method}_{basis}'
                
                # Add no_cat paths
                no_cat_dir = method_basis_dir / 'no_cat'
                for path in self._get_no_cat_paths(no_cat_dir):
                    paths.append(path)
                
                # Add catalyst paths
                for catalyst in self.sanitized_config['catalysts']:
                    for path in self._get_catalyst_paths(method_basis_dir, catalyst):
                        paths.append(path)
        return paths

    def _get_no_cat_paths(self, no_cat_dir: Path) -> List[Path]:
        """Helper method to generate no_cat paths."""
        return [
            no_cat_dir / f'reactants/{self.sanitized_config["reactant1"]}/{self.sanitized_config["reactant1"]}_opt.in',
            no_cat_dir / f'reactants/{self.sanitized_config["reactant2"]}/{self.sanitized_config["reactant2"]}_opt.in',
            no_cat_dir / 'product/no_cat_product_opt.in',
            no_cat_dir / 'ts/no_cat_ts_opt.in'
        ]

    def _get_catalyst_paths(self, method_basis_dir: Path, catalyst: str) -> List[Path]:
        """Helper method to generate catalyst paths."""
        paths = []
        cat_dir = method_basis_dir / catalyst
        calc_types = ['full_cat', 'pol_cat', 'frz_cat']
        
        paths.append(cat_dir / f'reactants/{catalyst}/{catalyst}_opt.in')
        
        for calc_type in calc_types:
            paths.extend([
                cat_dir / f'reactants/{self.sanitized_config["reactant1"]}/{calc_type}/{self.sanitized_config["reactant1"]}_{calc_type}_opt.in',
                cat_dir / f'product/{calc_type}_product/product_{calc_type}_opt.in',
                cat_dir / f'ts/{calc_type}_ts/ts_{calc_type}_opt.in'
            ])
        return paths

class QChemCalculation(FileOperations):
    """Class for handling Q-Chem calculations."""
    def __init__(self, input_file: Path, overwrite: bool = False):
        super().__init__(input_file.parent)
        self.input_file = input_file
        self.output_file = input_file.with_suffix('.out')
        self.error_file = input_file.with_suffix('.err')
        self.overwrite = overwrite

    def execute(self):
        """Execute the Q-Chem calculation."""
        logging.info(f'Executing qqchem for {self.input_file}')
        try:
            subprocess.run(
                ['qqchem', '-c', '16', '-t', '4-00:00:00', self.input_file.name],
                check=True,
                cwd=self.input_file.parent
            )
            logging.info(f'Submission successful for {self.input_file}')
            time.sleep(0.2)
            return True
        except Exception as e:
            logging.error(f'Error executing qqchem for {self.input_file}: {e}')
            return False

    def check_status(self) -> Tuple[str, str]:
        """Check calculation status and return detailed information."""
        # ... existing status checking logic from check_calculation_status ...
        # This would be the same logic as in your original check_calculation_status function
        """
        Check calculation status and return detailed information.
        Returns tuple of (status, details)
        """
        try:
            # Check if .out file exists
            if self.output_file.exists():
                # Read .out file content
                content = self.read_file(self.output_file)
            else:
                content = None  # Indicates .out file does not exist
    
            # Read .err file content if it exists
            err_content = self.read_file(self.error_file) if self.error_file.exists() else ''
    
            # Check if job was cancelled manually in .err file
            if 'CANCELLED AT' in err_content:
                return 'terminated', 'Job cancelled by Queue'
    
            # Check for Q-Chem crash in .err file
            if 'Error in Q-Chem run' in err_content or 'Aborted' in err_content:
                # Job crashed, extract error message from .out file
                status = 'CRASH'
                error_msg = 'Q-Chem execution crashed'
    
                # Attempt to get detailed error message from .out file
                if content:
                    if 'error occurred' in content:
                    #if 'Q-Chem fatal error occurred' in content:
                        error_pattern = r'error occurred.*?\n\s*(.*?)(?:\n{2,}|\Z)'
                        #error_pattern = r'Q-Chem fatal error occurred.*?\n\s*(.*?)(?:\n{2,}|\Z)'
                        error_match = re.search(error_pattern, content, re.DOTALL)
                        if error_match:
                            full_msg = error_match.group(1).strip()
                            # Extract message up to the first '.' or ';'
                            error_msg = re.split(r'[.;]|\band\b', full_msg)[0].strip()
                        else:
                            error_msg = 'Unknown fatal error'
                    elif 'SGeom Failed' in content:
                        error_msg = 'Geometry optimization failed'
                    elif 'SCF failed to converge' in content:
                        error_msg = 'SCF convergence failure'
                    elif 'Insufficient memory' in content:
                        error_msg = 'Out of memory'
                    else:
                        error_msg = 'Unknown failure'
                return status, error_msg
    
            # Check if job is still running based on submission file
            input_stem = self.output_file.with_suffix('').stem
            submission_pattern = f"{input_stem}.in_[0-9]*.[0-9]*"
            submission_files = list(self.output_file.parent.glob(submission_pattern))
            if submission_files:
                return 'running', 'Job submission file exists'
    
            # If .out file does not exist
            if content is None:
                return 'nofile', 'Output file not found'
    
            # Check for running job in .out file
            if 'Running on' in content and 'Thank you very much' not in content:
                return 'running', 'Calculation in progress'
    
            # Check for successful completion
            if 'Thank you very much' in content:
                time_pattern = r'Total job time:\s*(.*)'
                time_match = re.search(time_pattern, content)
                job_time = time_match.group(1).strip() if time_match else 'unknown'
                return 'SUCCESSFUL', f'Completed in {job_time}'
    
            # Check for Q-Chem fatal error in .out file
            if 'Q-Chem fatal error occurred' in content:
                error_pattern = r'Q-Chem fatal error occurred.*?\n\s*(.*?)(?:\n\n|\Z)'
                error_match = re.search(error_pattern, content, re.DOTALL)
                if error_match:
                    full_msg = error_match.group(1).strip()
                    # Extract message up to the first '.' or ';'
                    error_msg = re.split(r'[.;]', full_msg)[0].strip()
                else:
                    error_msg = 'Unknown fatal error'
                return 'CRASH', error_msg
    
            # Check for specific errors in .out file
            if 'SGeom Failed' in content:
                return 'CRASH', 'Geometry optimization failed'
            if 'SCF failed to converge' in content:
                return 'CRASH', 'SCF convergence failure'
            if 'Insufficient memory' in content:
                return 'CRASH', 'Out of memory'
    
            # Check for job termination messages in .out file
            if 'killed' in content.lower() or 'terminating' in content.lower():
                return 'terminated', 'Job terminated unexpectedly'
    
            # If .out file exists but contains unknown content
            if content.strip():
                return 'CRASH', 'Unknown failure'
    
            # If .out file exists but is empty
            return 'empty', 'Output file is empty'
    
        except Exception as e:
            return 'error', f'Error reading output: {str(e)}'
    
    def write_input_file(self, molecule_section: str, rem_section: str, 
                        base_template_content: str, calc_type: str) -> bool:
        """Generate the input file by filling in placeholders."""
        if self.input_file.exists() and not self.overwrite:
            logging.info(f'File exists and will not be overwritten: {self.input_file}')
            return False

        num_atoms = Utilities.count_atoms(molecule_section)
        jobtype = 'ts' if calc_type == 'ts' else ('sp' if num_atoms == 1 else 'opt')
        
        rem_section_filled = rem_section.format(jobtype=jobtype)
        input_content = base_template_content.format(
            molecule_section=molecule_section.strip(),
            rem_section=rem_section_filled.rstrip())

        return self.write_file(self.input_file, input_content)

class DataProcessor(FileOperations):
    """Class for processing chemical calculation data."""
    def __init__(self, config: dict, base_dir: Path):
        super().__init__(base_dir)
        self.config = config
        self.patterns = self._compile_patterns()

    def _compile_patterns(self) -> dict:
        """Compile and return regex patterns."""
        patterns = {
            "final_energy": re.compile(r"Final energy is\s+([-+]?\d+\.\d+)"),
            "final_energy_fallback": re.compile(r"Total energy =\s+([-+]?\d+\.\d+)"),
            "optimization_status": re.compile(
                r"(OPTIMIZATION CONVERGED|TRANSITION STATE CONVERGED)"
            ),
            "thermodynamics": re.compile(
                r"STANDARD THERMODYNAMIC QUANTITIES AT\s+([-+]?\d+\.\d+)\s*K\s+AND\s+([-+]?\d+\.\d+)\s*ATM"
            ),
            "imaginary_frequencies": re.compile(
                r"This Molecule has\s+(\d+)\s+Imaginary Frequencies"
            ),
            "zero_point_energy": re.compile(
                r"Zero point vibrational energy:\s+([-+]?\d+\.\d+)\s+(\S+)"
            ),
            "qrrho_parameters": re.compile(
                r"Quasi-RRHO corrections using alpha\s*=\s*(\d+),\s*and omega\s*=\s*(\d+)\s*cm\^-1"
            ),
            # Patterns with priority logic for Enthalpy and Entropy
            "qrrho_total_enthalpy": re.compile(
                r"QRRHO-Total Enthalpy:\s+([-+]?\d+\.\d+)\s+(\S+)"
            ),
            "total_enthalpy_fallback": re.compile(
                r"Total Enthalpy:\s+([-+]?\d+\.\d+)\s+(\S+)"
            ),
            "qrrho_total_entropy": re.compile(
                r"QRRHO-Total Entropy:\s+([-+]?\d+\.\d+)\s+(\S+)"
            ),
            "total_entropy_fallback": re.compile(
                r"Total Entropy:\s+([-+]?\d+\.\d+)\s+(\S+)"
            ),
        }
        return patterns

    def process_files(self, root_dir: Path, method_basis: str, target_catalyst: str) -> list:
        """Process files for a given method-basis combination and catalyst."""
        data_list = []
        catalysts = [c.lower() for c in self.config.get('catalysts', [])]
        reactant1 = self.config.get('reactant1', '').lower()
        reactant2 = self.config.get('reactant2', '').lower()
        target_catalyst = target_catalyst.lower()

        for file_path in root_dir.rglob("*.out"):
            relative_path = file_path.relative_to(root_dir)
            path_str = str(relative_path).lower()
            
            # Include file if it's either nocat or matches the target catalyst
            if ('no_cat' in path_str or 'nocat' in path_str or target_catalyst in path_str):
                if self._is_valid_path(relative_path, catalysts, reactant1, reactant2):
                    content = self.read_file(file_path)
                    if content:
                        data = self._extract_data(content)
                        if data:
                            calculation_label = Utilities.get_calculation_label(relative_path)
                            #data["Method_Basis"] = method_basis
                            data[f"{method_basis}"] = calculation_label
                            data_list.append(data)
        return data_list

    def _is_valid_path(self, relative_path: Path, catalysts: list,
                      reactant1: str, reactant2: str) -> bool:
        """Check if the relative path contains any of the desired paths."""
        path_str = str(relative_path).lower()
        parts = [part.lower() for part in relative_path.parts]
        
        # Check for standard calculation paths
        if any('no_cat' in part or 'nocat' in part for part in parts):
            return True
        if any(part in ['product', 'ts'] for part in parts):
            return True
        if any('frz_cat' in part or 'frz' in part or
               'pol_cat' in part or 'pol' in part or 
               'full_cat' in part or 'full' in part for part in parts):
            return True
            
        # Check for catalysts
        if any(cat in parts for cat in catalysts):
            return True
            
        # Check for reactants
        if reactant1 in path_str or reactant2 in path_str:
            return True
            
        # Exclude unwanted directories (e.g., 'templates')
        if 'templates' in parts:
            return False
            
        return False

    def _extract_data(self, content: str) -> Optional[dict]:
        """Extract data from output file content."""
        data = {}
        fallback_used = False

        # Energy Extraction (No unit to extract; assume Hartrees)
        energy_value = Utilities.get_energy_value(content, self.patterns)
        if energy_value is not None:
            data["E (Ha)"] = energy_value
            # Convert energy from Hartrees to kcal/mol
            energy_value_converted = energy_value * Constants.HARTREE_TO_KCALMOL
            # Store in data with unit in column name
            data["E (kcal/mol)"] = energy_value_converted
        else:
            logging.warning("Final energy value not found.")
            return None  # Can't proceed without energy value

        # Enthalpy Extraction
        enthalpy_value, enthalpy_unit, enthalpy_fallback = Utilities.get_value_with_fallback(
            content,
            self.patterns["qrrho_total_enthalpy"],
            self.patterns["total_enthalpy_fallback"],
        )
        if enthalpy_value is not None:
            # Convert enthalpy to kcal/mol
            if enthalpy_unit in ["kcal/mol"]:
                enthalpy_value_converted = enthalpy_value
                enthalpy_unit_converted = "kcal/mol"
            elif enthalpy_unit in ["Hartree", "Ha", "a.u."]:
                enthalpy_value_converted = enthalpy_value * Constants.HARTREE_TO_KCALMOL
                enthalpy_unit_converted = "kcal/mol"
            else:
                logging.warning(
                    f"Unrecognized enthalpy unit: {enthalpy_unit}. Assuming kcal/mol."
                )
                enthalpy_value_converted = enthalpy_value
                enthalpy_unit_converted = "kcal/mol"

            # Store in data with unit in column name
            enthalpy_column_name = f"Total Enthalpy Corr. ({enthalpy_unit_converted})"
            data[enthalpy_column_name] = enthalpy_value_converted

            if enthalpy_fallback:
                fallback_used = True

        # Entropy Extraction
        entropy_value, entropy_unit, entropy_fallback = Utilities.get_value_with_fallback(
            content,
            self.patterns["qrrho_total_entropy"],
            self.patterns["total_entropy_fallback"],
        )
        if entropy_value is not None:
            # Convert entropy to kcal/mol·K
            if entropy_unit in ["cal/mol.K", "cal/mol·K"]:
                entropy_value_converted = entropy_value * Constants.CAL_TO_KCAL
                entropy_unit_converted = "kcal/mol.K"
            elif entropy_unit in ["kcal/mol.K", "kcal/mol·K"]:
                entropy_value_converted = entropy_value
                entropy_unit_converted = "kcal/mol.K"
            else:
                logging.warning(
                    f"Unrecognized entropy unit: {entropy_unit}. Assuming kcal/mol.K."
                )
                entropy_value_converted = entropy_value
                entropy_unit_converted = "kcal/mol.K"

            # Store in data with unit in column name
            entropy_column_name = f"Total Entropy Corr. ({entropy_unit_converted})"
            data[entropy_column_name] = entropy_value_converted

            if entropy_fallback:
                fallback_used = True

        # Extract other data as before
        for key, pattern in self.patterns.items():
            if key in [
                "final_energy",
                "final_energy_fallback",
                "qrrho_total_enthalpy",
                "total_enthalpy_fallback",
                "qrrho_total_entropy",
                "total_entropy_fallback",
            ]:
                continue  # Already handled
            match = pattern.search(content)
            if match:
                if key == "optimization_status":
                    data["Optimization Status"] = match.group(1)
                elif key == "thermodynamics":
                    data["Temperature (K)"] = float(match.group(1))
                    data["Pressure (atm)"] = float(match.group(2))
                elif key == "qrrho_parameters":
                    data["Alpha"] = int(match.group(1))
                    data["Omega (cm^-1)"] = int(match.group(2))
                elif key == "imaginary_frequencies":
                    data["Imaginary Frequencies"] = int(match.group(1))
                elif key == "zero_point_energy":
                    value = float(match.group(1))
                    unit = match.group(2)
                    column_name = f"Zero Point Energy ({unit})"
                    data[column_name] = value
                else:
                    value = float(match.group(1))
                    unit = match.group(2) if match.lastindex >= 2 else ""
                    column_name = (
                        f"{key.replace('_', ' ').title()} ({unit})"
                        if unit
                        else key.replace("_", " ").title()
                    )
                    data[column_name] = value

        # Calculate H (kcal/mol)
        energy_col = "E (kcal/mol)"
        enthalpy_col = f"Total Enthalpy Corr. (kcal/mol)"
        if energy_col in data and enthalpy_col in data:
            data["H (kcal/mol)"] = data[energy_col] + data[enthalpy_col]

        # Calculate G (kcal/mol)
        entropy_col = f"Total Entropy Corr. (kcal/mol.K)"
        if (
            "H (kcal/mol)" in data
            and "Temperature (K)" in data
            and entropy_col in data
        ):
            data["G (kcal/mol)"] = (
                data["H (kcal/mol)"] - data["Temperature (K)"] * data[entropy_col]
            )

        # Add 'Fallback Used' column if any fallback was used
        if data:
            data["Fallback Used"] = "Yes" if fallback_used else "No"
            return data
        else:
            return None

class DataExporter(FileOperations):
    """Class for exporting processed data."""
    def __init__(self, output_dir: Path):
        super().__init__(output_dir)

    def save_method_basis_data(self, data_list: list, filename: str):
        """Save the extracted data to CSV."""
        if not data_list:
            logging.info(f"No data to save for '{filename}'")
            return

        df = pd.DataFrame(data_list)
        
        method_basis = "_".join(filename.split("_")[:-1])
        # Ensure Method_Basis and Label are first columns
        expected_columns = [f"{method_basis}"]#, 'Label']
        
        # Check if expected columns exist
        for col in expected_columns:
            if col not in df.columns:
                logging.warning(f"Missing required column: {col}")
                return
                
        # Reorder columns to put Method_Basis and Label first
        other_cols = [col for col in df.columns if col not in expected_columns]
        df = df[expected_columns + other_cols]
        
        # Create output file directly in raw_data_dir
        csv_file = self.base_dir / f"{filename}.csv"
        
        try:
            df.to_csv(csv_file, index=False)
            logging.info(f"Data saved to '{csv_file}'")
        except Exception as e:
            logging.error(f"Failed to save data to '{csv_file}': {e}")

class EnergyProfileGenerator(FileOperations):
    """Class for generating energy profiles."""
    def __init__(self, input_dir: Path, profiles_dir: Path, config: dict, catalyst: str):
        super().__init__(input_dir)
        self.config = config
        self.profiles_dir = profiles_dir
        self.profiles_dir.mkdir(exist_ok=True)
        self.catalyst = catalyst

    def _get_energy_values(self, df: pd.DataFrame, path: str, stage: str) -> Tuple[Optional[float], Optional[float]]:
        """Get E and G values for a specific path and stage."""
        matching_rows = df[(df['Path'] == path) & (df['Stage'] == stage)]
        if not matching_rows.empty:
            return (matching_rows['E (kcal/mol)'].iloc[0], 
                   matching_rows['G (kcal/mol)'].iloc[0])
        return None, None

    def _create_combined_profile(self, df: pd.DataFrame, method_basis: str) -> List[dict]:
        """Create profile with combined energies."""
        combined_data = []
        cat = self.config['catalysts'][0].lower()  # Assuming single catalyst
        r1 = self.config['reactant1'].lower()
        r2 = self.config['reactant2'].lower()

        # Define combinations and their components
        combinations = [
            {
                'name': f"{cat}+{r1}+{r2}",
                'components': [
                    {'path': cat, 'stage': 'Reactants'},
                    {'path': r1, 'stage': 'Reactants'},
                    {'path': r2, 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"Frz-{cat}-{r1}+{r2}",
                'components': [
                    {'path': 'frz', 'stage': 'Reactants'},
                    {'path': r2, 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"Pol-{cat}-{r1}+{r2}",
                'components': [
                    {'path': 'pol', 'stage': 'Reactants'},
                    {'path': r2, 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"Full-{cat}-{r1}+{r2}",
                'components': [
                    {'path': 'full', 'stage': 'Reactants'},
                    {'path': r2, 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"ts-{r1}-{r2}+{cat}",
                'components': [
                    {'path': 'nocat', 'stage': 'TS'},
                    {'path': cat, 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"Ts-{cat}-frz-{r1}-{r2}",
                'components': [
                    {'path': 'frz', 'stage': 'TS'}
                ]
            },
            {
                'name': f"Ts-{cat}-pol-{r1}-{r2}",
                'components': [
                    {'path': 'pol', 'stage': 'TS'}
                ]
            },
            {
                'name': f"Ts-{cat}-full-{r1}-{r2}",
                'components': [
                    {'path': 'full', 'stage': 'TS'}
                ]
            },
            {
                'name': f"product+{cat}",
                'components': [
                    {'path': 'nocat', 'stage': 'Product'},
                    {'path': cat, 'stage': 'Reactants'}
                ]
            },
            {
                'name': f"{cat}-frz-product",
                'components': [
                    {'path': 'frz', 'stage': 'Product'}
                ]
            },
            {
                'name': f"{cat}-pol-product",
                'components': [
                    {'path': 'pol', 'stage': 'Product'}
                ]
            },
            {
                'name': f"{cat}-full-product",
                'components': [
                    {'path': 'full', 'stage': 'Product'}
                ]
            }
        ]

        # Calculate combined energies
        for combo in combinations:
            e_sum = 0.0
            g_sum = 0.0
            all_components_found = True
            
            for component in combo['components']:
                e_val, g_val = self._get_energy_values(df, component['path'], component['stage'])
                if e_val is None or g_val is None:
                    logging.warning(f"Missing energy values for {combo['name']}: {component}")
                    all_components_found = False
                    break
                e_sum += e_val
                g_sum += g_val
            
            if all_components_found:
                combined_data.append({
                    'Structure': combo['name'],
                    'E (kcal/mol)': e_sum,
                    'G (kcal/mol)': g_sum
                })

        return combined_data

    def _generate_raw_profile(self, df: pd.DataFrame, method_basis: str) -> pd.DataFrame:
        """Generate raw profile data."""
        raw_data = []
        catalysts = [c.lower() for c in self.config.get('catalysts', [])]
        reactant1 = self.config.get('reactant1', '').lower()
        reactant2 = self.config.get('reactant2', '').lower()

        for _, row in df.iterrows():
            label = row.get('Label') or row.get(f"{method_basis}")
            if not label:
                continue

            # Initialize path and stage
            path = 'unknown'
            stage = 'Unknown'

            label_parts = label.lower().split('/')
            label_parts = [part.strip() for part in label_parts]

            # First determine stage
            if any('reactants' in part for part in label_parts):
                stage = 'Reactants'
            elif any(part == 'ts' or 'ts' in part for part in label_parts):
                stage = 'TS'
            elif any('product' in part for part in label_parts):
                stage = 'Product'


            # Then determine path with precedence order
            if any('frz_cat' in part or 'frz' in part for part in label_parts):
                path = 'frz'
            elif any('pol_cat' in part or 'pol' in part for part in label_parts):
                path = 'pol'
            elif any('full_cat' in part or 'full' in part for part in label_parts):
                path = 'full'
            elif any(reactant1 in part for part in label_parts):
                path = reactant1
            elif any(reactant2 in part for part in label_parts):
                path = reactant2
            elif any('no_cat' in part or 'nocat' in part for part in label_parts):
                path = 'nocat'

            elif any(cat in label_parts for cat in catalysts):
                for cat in catalysts:
                    if cat in label_parts:
                        path = cat
                        break
            # elif reactant1 in label_parts:
            #     path = reactant1
            # elif reactant2 in label_parts:
            #     path = reactant2

            if path != 'unknown' and stage != 'Unknown':
                raw_data.append({
                    f"{method_basis}": label,
                    'Path': path,
                    'Stage': stage,
                    'E (kcal/mol)': row.get('E (kcal/mol)'),
                    'G (kcal/mol)': row.get('G (kcal/mol)')
                })

        return pd.DataFrame(raw_data)

    def generate_profiles(self):
        """Generate both raw and combined energy profiles."""
        for csv_file in self.base_dir.glob("*.csv"):
            if self.catalyst.lower() in csv_file.stem.lower():
                method_basis = "_".join(csv_file.stem.split("_")[:-1])  # Remove catalyst from name
                df = pd.read_csv(csv_file)

                # Generate raw profile
                raw_profile = self._generate_raw_profile(df, method_basis)
                raw_output = self.profiles_dir / f"{csv_file.stem}_raw_profile.csv"
                raw_profile.to_csv(raw_output, index=False)
                logging.info(f"Raw energy profile saved to {raw_output}")

                # Generate combined profile
                combined_data = self._create_combined_profile(raw_profile, method_basis)
                if combined_data:
                    combined_df = pd.DataFrame(combined_data)
                    combined_output = self.profiles_dir / f"{csv_file.stem}_combined_profile.csv"
                    combined_df.to_csv(combined_output, index=False)
                    logging.info(f"Combined energy profile saved to {combined_output}")
                else:
                    logging.warning(f"No combined profile data generated for {method_basis}")

class InputGenerator(FileOperations):
    """Class for generating input files."""
    def __init__(self, config: dict, template_dir: Path):
        super().__init__(template_dir)
        self.config = config
        self.system_dir = Path.cwd()
        self.file_handler = FileHandler(template_dir)

    def generate_inputs(self, overwrite_option: str, run_option: str):
        """Generate input files and execute if run_option is specified."""
        # Get original names from config
        methods = self.config['methods']
        bases = self.config['bases']
        catalysts = self.config['catalysts']
        reactant1 = self.config['reactant1']
        reactant2 = self.config['reactant2']
        
        # Get sanitized names for paths 
        san_methods = [FileHandler.sanitize_filename(m) for m in methods]
        san_bases = [FileHandler.sanitize_filename(b) for b in bases]
        san_catalysts = [FileHandler.sanitize_filename(c) for c in catalysts]
        san_reactant1 = FileHandler.sanitize_filename(reactant1)
        san_reactant2 = FileHandler.sanitize_filename(reactant2)
        
        # Process each method-basis combination
        for method, san_method in zip(methods, san_methods):
            for basis, san_basis in zip(bases, san_bases):
                method_basis_dir = self.system_dir / f'{san_method}_{san_basis}'
                method_basis_dir.mkdir(exist_ok=True)
                
                # Create no_cat directories
                no_cat_dir = method_basis_dir / 'no_cat'
                no_cat_paths = [
                    f'reactants/{san_reactant1}',
                    f'reactants/{san_reactant2}',
                    'product',
                    'ts'
                ]
                self.file_handler.create_directory_structure(no_cat_dir, no_cat_paths)
                
                # Create catalyst directories
                for catalyst, san_catalyst in zip(catalysts, san_catalysts):
                    cat_dir = method_basis_dir / san_catalyst
                    catalyst_paths = []
                    for calc_type in ['full_cat', 'pol_cat', 'frz_cat']:
                        catalyst_paths.extend([
                            f'reactants/{san_reactant1}/{calc_type}',
                            f'product/{calc_type}_product',
                            f'ts/{calc_type}_ts'
                        ])
                    catalyst_paths.append(f'reactants/{san_catalyst}')
                    self.file_handler.create_directory_structure(cat_dir, catalyst_paths)

                self._generate_calculation_inputs(
                    method_basis_dir=method_basis_dir,
                    method=method,
                    basis=basis,
                    catalysts=catalysts,
                    reactant1=reactant1,
                    reactant2=reactant2,
                    overwrite_option=overwrite_option,
                    run_option=run_option
                )

    def _generate_calculation_inputs(self, method_basis_dir: Path, method: str, basis: str,
                                   catalysts: List[str], reactant1: str, reactant2: str,
                                   overwrite_option: str, run_option: str):
        """Generate the actual input files."""
        # Read templates
        template_dir = self.system_dir / 'templates'
        rem_base = self.read_file(template_dir / 'rem/rem_base.rem')
        rem_additions = {
            'full_cat': self.read_file(template_dir / 'rem/rem_full_cat.rem'),
            'pol_cat': self.read_file(template_dir / 'rem/rem_pol_cat.rem'),
            'frz_cat': self.read_file(template_dir / 'rem/rem_frz_cat.rem')
        }
        base_template_content = self.read_file(template_dir / 'base_template.in')

        # Format base REM section
        rem_base_formatted = rem_base.format(method=method, basis=basis, jobtype='{jobtype}')

        # Generate no_cat inputs
        self._generate_no_cat_inputs(
            method_basis_dir=method_basis_dir,
            reactant1=reactant1,
            reactant2=reactant2,
            rem_base=rem_base_formatted,
            base_template_content=base_template_content,  # Changed from base_template
            template_dir=template_dir,
            overwrite_option=overwrite_option,
            run_option=run_option
        )

        # Generate catalyst inputs
        for catalyst in catalysts:
            self._generate_catalyst_inputs(
                method_basis_dir=method_basis_dir,
                catalyst=catalyst,
                reactant1=reactant1,
                rem_base=rem_base_formatted,
                rem_additions=rem_additions,
                base_template_content=base_template_content,  # Changed from base_template
                template_dir=template_dir,
                overwrite_option=overwrite_option,
                run_option=run_option
            )

    def _generate_no_cat_inputs(self, method_basis_dir: Path, reactant1: str, reactant2: str, 
                               rem_base: str, base_template_content: str, template_dir: Path, 
                               overwrite_option: str, run_option: str):
        """Generate no-catalyst input files."""
        no_cat_dir = method_basis_dir / 'no_cat'
        no_cat_calcs = [
            (reactant1, no_cat_dir / f'reactants/{reactant1}/{reactant1}_opt.in', 'reactants'),
            (reactant2, no_cat_dir / f'reactants/{reactant2}/{reactant2}_opt.in', 'reactants'),
            ('no_cat_product', no_cat_dir / 'product/no_cat_product_opt.in', 'product'),
            ('no_cat_ts', no_cat_dir / 'ts/no_cat_ts_opt.in', 'ts'),
        ]
        for mol_name, input_file, calc_type in no_cat_calcs:
            mol_section = self.read_file(template_dir / 'molecule' / f'{mol_name}.mol')
            
            # Determine overwrite decision
            out_file = input_file.with_suffix('.out')
            qchem = QChemCalculation(input_file)
            status, details = qchem.check_status()
            
            # Create new QChemCalculation instance with proper overwrite flag
            qchem = QChemCalculation(
                input_file, 
                overwrite=(overwrite_option == 'all' or overwrite_option == status)
            )
            
            qchem.write_input_file(
                mol_section, rem_base, base_template_content, calc_type)
            if run_option:
                qchem.execute()

    def _generate_catalyst_inputs(self, method_basis_dir: Path, catalyst: str, reactant1: str, rem_base: str, rem_additions: dict, base_template_content: str, template_dir: Path, overwrite_option: str, run_option: str):
        """Generate catalyst-specific input files."""
        cat_dir = method_basis_dir / catalyst
        calc_types = ['full_cat', 'pol_cat', 'frz_cat']
        stages = ['reactants', 'product', 'ts']

        # Prepare molecule sections
        mol_sections = {}
        # Reactants
        catal_mol_react = self.read_file(template_dir / 'molecule' / f'{catalyst}_reactant.mol')
        reactant1_mol = self.read_file(template_dir / 'molecule' / f'{reactant1}.mol')
        mol_sections['reactants'] = f"{catal_mol_react}\n{reactant1_mol}"
        # Product
        catal_mol_prod = self.read_file(template_dir / 'molecule' / f'{catalyst}_product.mol')
        no_cat_prod_mol = self.read_file(template_dir / 'molecule' / 'no_cat_product.mol')
        mol_sections['product'] = f"{catal_mol_prod}\n{no_cat_prod_mol}"
        # TS
        catal_mol_ts = self.read_file(template_dir / 'molecule' / f'{catalyst}_ts.mol')
        no_cat_ts_mol = self.read_file(template_dir / 'molecule' / 'no_cat_ts.mol')
        mol_sections['ts'] = f"{catal_mol_ts}\n{no_cat_ts_mol}"
        # Catalyst optimization
        mol_sections['catalyst_opt'] = self.read_file(template_dir / 'molecule' / f'{catalyst}.mol')

        # Generate and optionally execute input files for each stage and calc_type
        for stage in stages:
            for calc_type in calc_types:
                rem_section = f"{rem_base}\n{rem_additions[calc_type]}"
                if stage == 'reactants':
                    input_file = cat_dir / f'reactants/{reactant1}/{calc_type}/{reactant1}_{calc_type}_opt.in'
                else:
                    input_file = cat_dir / f'{stage}/{calc_type}_{stage}/{stage}_{calc_type}_opt.in'
                mol_section = mol_sections[stage]
                
                # Determine overwrite decision
                out_file = input_file.with_suffix('.out')
                qchem = QChemCalculation(input_file)
                status, details = qchem.check_status()
                
                qchem = QChemCalculation(
                    input_file,
                    overwrite=(overwrite_option == 'all' or overwrite_option == status)
                )
                
                qchem.write_input_file(
                    mol_section, rem_section, base_template_content, stage)
                if run_option:
                    qchem.execute()
        # Catalyst optimization input
        catalyst_opt_file = cat_dir / f'reactants/{catalyst}/{catalyst}_opt.in'
        # Determine overwrite decision
        out_file = catalyst_opt_file.with_suffix('.out')
        qchem = QChemCalculation(catalyst_opt_file)
        status, details = qchem.check_status()
        qchem = QChemCalculation(
            catalyst_opt_file,
            overwrite=(overwrite_option == 'all' or overwrite_option == status)
        )
        qchem.write_input_file(
            mol_sections['catalyst_opt'], rem_base, base_template_content, 'reactants')
        if run_option:
            qchem.execute()

class StatusChecker(FileOperations):
    """Class for checking calculation statuses."""
    def __init__(self, paths: List[Path], base_dir: Path):
        super().__init__(base_dir)
        self.paths = paths
        self.status_counts = {}

    def check_all_statuses(self):
        """Check and report status for all calculation paths."""
        system_dir = Path.cwd()
        max_path_length = max(len(str(path.relative_to(system_dir).parent / path.stem)) 
                            for path in self.paths)
        format_str = f"{{:<{max_path_length}}} | {{:<10}} | {{}}"
        
        for path in self.paths:
            relative_path = path.relative_to(system_dir).parent / path.stem
            if path.exists():
                qchem = QChemCalculation(path)
                status, details = qchem.check_status()
                self.status_counts[status] = self.status_counts.get(status, 0) + 1
                logging.info(format_str.format(str(relative_path), status, details))
            else:
                status = 'absent'
                self.status_counts[status] = self.status_counts.get(status, 0) + 1
                logging.info(format_str.format(str(relative_path), status, 'Input file not found'))
        
        self._print_summary()

    def _print_summary(self):
        """Print summary of calculation statuses."""
        logging.info("\nStatus Summary:")
        max_status_length = max(len(status) for status in self.status_counts.keys())
        summary_format = f"{{:<{max_status_length}}} : {{:>4}} calculations"
        for status, count in self.status_counts.items():
            logging.info(summary_format.format(status, count))

class A3EDA:
    """Main class coordinating the entire process."""
    def __init__(self, args):
        self.setup_logging(args.log)
        self.config_manager = ConfigManager(args.yaml_config)
        self.system_dir = Path.cwd()
        self.file_handler = FileHandler(self.system_dir)
        self.args = args
        
        # Only set up data directories as attributes, don't create them yet
        self.data_dir = self.system_dir / 'data'
        self.raw_data_dir = self.data_dir / 'raw'
        self.profiles_dir = self.data_dir / 'profiles'

    def _create_data_directories(self):
        """Create data directories if they don't exist."""
        self.data_dir.mkdir(exist_ok=True)
        self.raw_data_dir.mkdir(exist_ok=True)
        self.profiles_dir.mkdir(exist_ok=True)

    @staticmethod
    def setup_logging(level: str):
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            stream=sys.stdout
        )

    def run(self):
        if self.args.generate:
            self._handle_generation()
        elif self.args.run:
            self._handle_running()
        elif self.args.extract:
            self._handle_extraction()
        else:
            self._handle_status_check()

    def _handle_generation(self):
        """Handle input generation."""
        generator = InputGenerator(self.config_manager.config, self.system_dir / 'templates')
        generator.generate_inputs(self.args.overwrite, self.args.run)

    def _handle_running(self):
        """Handle calculation running."""
        paths = self.config_manager.get_calculation_paths(self.system_dir)
        self._run_existing_inputs(paths)

    def _handle_extraction(self):
        """Handle data extraction."""
        # Create directories only when extraction is requested
        self._create_data_directories()
        
        processor = DataProcessor(self.config_manager.config, self.system_dir)
        exporter = DataExporter(self.raw_data_dir)

        # Process each catalyst separately
        for catalyst in self.config_manager.config['catalysts']:
            for method in self.config_manager.config['methods']:
                for basis in self.config_manager.config['bases']:
                    method_basis = f"{method}_{basis}"
                    method_basis_dir = self.system_dir / FileHandler.sanitize_filename(method_basis)
                    
                    if method_basis_dir.is_dir():
                        logging.info(f"Processing method_basis: {method_basis} for catalyst: {catalyst}")
                        data_list = processor.process_files(method_basis_dir, method_basis, catalyst)
                        if data_list:
                            # Include catalyst in filename
                            filename = f"{method_basis}_{FileHandler.sanitize_filename(catalyst)}"
                            exporter.save_method_basis_data(data_list, filename)
                        else:
                            logging.info(f"No data was extracted for '{method_basis}' with catalyst '{catalyst}'")
                    else:
                        logging.warning(f"Directory '{method_basis_dir}' does not exist. Skipping.")

            # Generate energy profiles for this catalyst
            profile_generator = EnergyProfileGenerator(
                self.raw_data_dir,
                self.profiles_dir,
                self.config_manager.config,
                catalyst
            )
            profile_generator.generate_profiles()

    def _handle_status_check(self):
        """Handle status checking."""
        paths = self.config_manager.get_calculation_paths(self.system_dir)
        StatusChecker(paths, self.system_dir).check_all_statuses()

    def _run_existing_inputs(self, paths: List[Path]):
        """Execute existing input files based on their status."""
        for input_file in paths:
            if input_file.exists():
                calc = QChemCalculation(input_file)
                status, details = calc.check_status()
                if self.args.run == 'all' or self.args.run == status:
                    logging.info(f'Executing input file: {input_file} (current: {status} - {details})')
                    calc.execute()
                else:
                    logging.info(f'Skipping {input_file} (current: {status} - {details})')
            else:
                logging.warning(f'Input file does not exist: {input_file}')

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='A3EDA: Automated Analysis of Electronic Structure Data',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('yaml_config', type=str, help='Path to the configuration YAML file')
    parser.add_argument(
        '-l', '--log', type=str, default='info',
        choices=['debug', 'info', 'warning', 'error', 'critical'],
        help='Logging level'
    )
    parser.add_argument(
        '-o', '--overwrite', type=str,
        choices=['all', 'nofile', 'CRASH', 'terminated', 'SUCCESSFUL', 'running'],
        help='Overwrite input files based on their status'
    )
    parser.add_argument(
        '-g', '--generate', action='store_true',
        help='Generate input files and optionally execute calculations'
    )
    parser.add_argument(
        '-r', '--run', type=str,
        choices=['all', 'nofile', 'CRASH', 'terminated', 'SUCCESSFUL', 'running'],
        help='Execute input files based on their status'
    )
    parser.add_argument(
        '-e', '--extract', action='store_true',
        help='Extract data from output files and generate energy profiles'
    )
    return parser.parse_args()

def main():
    args = parse_arguments()
    try:
        a3eda = A3EDA(args)
        a3eda.run()
    except Exception as e:
        logging.error(f"Error during execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
