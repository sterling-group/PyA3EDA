"""
Configuration Manager

Loads and processes the YAML configuration file for PyA3EDA.
Every value is stored as a dictionary with its raw opt value, raw sp value (if any),
the sanitized versions for file naming, and a flag indicating whether an sp value was provided.
Consumers (like the builder) can then simply use configured keys for naming and substitution.
"""

from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

from PyA3EDA.core.utils.file_utils import sanitize_filename


class ConfigManager:
    def __init__(self, config_path: str) -> None:
        self.config_path = Path(config_path).resolve()  # Store as Path object
        self.config: Dict[str, Any] = self._load_config(config_path)
        self.processed_config: Dict[str, Any] = self._process_config()

    @property
    def config_dir(self) -> Path:
        """Return the directory containing the config file."""
        return self.config_path.parent

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        config_file = Path(config_path)
        if not config_file.is_file():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        try:
            with config_file.open(encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")

    @staticmethod
    def _create_value_entry(val: Any, default: Any = "false") -> Dict[str, Any]:
        """
        Converts a value (which can be given as a single value or a list of values)
        into a dictionary with:
          - "original_opt": The raw opt value.
          - "original_sp": The raw sp value if provided, else None.
          - "opt": The sanitized opt value.
          - "sp": The sanitized sp value if provided, otherwise an empty string.
          - "sp_enabled": True if an sp value was provided and it differs from opt.
        If val is absent, the default is used.
        """
        if not val:
            raw_opt = str(default)
            return {
                "original_opt": raw_opt,
                "original_sp": None,
                "opt": sanitize_filename(raw_opt),
                "sp": "",
                "sp_enabled": False,
            }
        # if list then two-element list means [opt, sp], one element means only opt provided.
        if isinstance(val, list):
            if len(val) == 2:
                raw_opt, raw_sp = val
            elif len(val) == 1:
                raw_opt, raw_sp = val[0], None
            else:
                raise ValueError("List value must have one or two elements.")
        else:
            raw_opt, raw_sp = val, None

        opt_sanitized = sanitize_filename(str(raw_opt))
        sp_sanitized = ""
        sp_enabled = False
        if raw_sp is not None:
            sp_sanitized = sanitize_filename(str(raw_sp))
            sp_enabled = True
        return {
            "original_opt": str(raw_opt),
            "original_sp": str(raw_sp) if raw_sp is not None else None,
            "opt": opt_sanitized,
            "sp": sp_sanitized,
            "sp_enabled": sp_enabled,
        }

    def _process_config(self) -> Dict[str, Any]:
        """
        Process (i.e., sanitize/normalize) the entire YAML configuration.
        """
        return {
            "methods": [
                self._process_method_config(m) for m in self.config.get("methods", [])
            ],
            "catalysts": [
                self._process_species_config(s, extra=True)
                for s in self.config.get("catalysts", [])
            ],
            "reactants": [
                self._process_species_config(s, include=True)
                for s in self.config.get("reactants", [])
            ],
            "products": [
                self._process_species_config(s, include=True)
                for s in self.config.get("products", [])
            ],
        }

    def _process_method_config(self, method: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a method entry. Each attribute is converted to a value entry.
        Also processes each basis set.
        """
        processed = {
            "name": self._create_value_entry(method.get("name", "")),
            "dispersion": self._create_value_entry(
                method.get("dispersion"), default="false"
            ),
            "solvent": self._create_value_entry(method.get("solvent"), default="false"),
            "basis_sets": [
                self._create_value_entry(bs, default="false")
                for bs in method.get("basis_sets", [])
            ],
            "eda2": method.get("eda2", 1),
        }
        return processed

    def _process_species_config(
        self, species: Dict[str, Any], include: bool = False, extra: bool = False
    ) -> Dict[str, Any]:
        """
        Processes a species entry (for catalysts, reactants, and products).
        Stores the species name as a value entry.
        If include is True, an include flag is added.
        If extra is True, additional information (like charge and multiplicity) is added.
        """
        processed = {"name": self._create_value_entry(species.get("name", ""))}
        if include:
            processed["include"] = species.get("include", True)
        if extra:
            processed["charge"] = species.get("charge")
            processed["multiplicity"] = species.get("multiplicity")
        return processed

    def get_builder_config(self) -> dict:
        """
        Returns unified configuration dictionary for builder functions.
        """
        return self.processed_config

    def get_common_values(
        self, method: Dict[str, Any], bs: Dict[str, Any], mode: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Returns two dictionaries (sanitized, original) that hold the naming values.
        For mode "opt", use the "opt" values.
        For mode "sp", use the "sp" values where available, falling back to "opt" values.

        Args:
            method: A processed method dictionary
            bs: A processed basis set dictionary
            mode: Either "opt" or "sp"

        Returns:
            Tuple of (sanitized, original) dictionaries with naming values
        """
        if mode not in ["opt", "sp"]:
            raise ValueError(f"Unknown mode: {mode}")

        # Define common fields to process
        fields = [
            ("method", method["name"]),
            ("basis", bs),
            ("dispersion", method["dispersion"]),
            ("solvent", method["solvent"]),
        ]

        sanitized = {}
        original = {}

        # Process fields based on mode
        for field_name, field_dict in fields:
            if mode == "opt":
                # For OPT mode, always use opt values
                sanitized[field_name] = field_dict["opt"]
                original[field_name] = field_dict["original_opt"]
            else:  # mode == "sp"
                # For SP mode, use sp values if sp_enabled, otherwise use opt values
                if field_dict.get("sp_enabled", False):
                    sanitized[field_name] = field_dict["sp"]
                    original[field_name] = field_dict["original_sp"]
                else:
                    sanitized[field_name] = field_dict["opt"]
                    original[field_name] = field_dict["original_opt"]

                # Always add opt values with opt_ prefix for SP mode (for file naming)
                sanitized[f"opt_{field_name}"] = field_dict["opt"]

        # Add eda2 to original dict for sp mode
        if mode == "sp":
            original["eda2"] = method.get("eda2")

        return sanitized, original

    def get_catalyst_order(self) -> list:
        """
        Returns list of catalyst names in the order they appear in the config file.

        Returns:
            List of catalyst name strings
        """
        catalysts = self.processed_config.get("catalysts", [])
        return [cat["name"]["opt"] for cat in catalysts]
