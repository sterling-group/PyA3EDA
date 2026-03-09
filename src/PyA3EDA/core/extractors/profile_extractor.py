"""
Energy Profile Extractor for Quantum Chemistry Calculations.

Processes quantum chemistry calculation data to construct reaction energy profiles
for both catalyzed and uncatalyzed pathways. Uses metadata-driven approach to 
identify reaction components and build comprehensive energy profiles.

Example:
     extractor = ProfileExtractor(calculation_data)
     profiles = extractor.extract_profiles()
"""
import logging
from typing import Dict, List, Any, Optional

from PyA3EDA.core.constants import Constants


class ProfileExtractor:
    """
    Extracts energy profiles from quantum chemistry calculation data.
    
    This class processes raw quantum chemistry calculation results to generate
    comprehensive energy profiles for chemical reactions. It handles both 
    catalyzed and uncatalyzed reaction pathways, supporting various calculation
    types including EDA (Energy Decomposition Analysis) methods.
    
    Attributes:
        raw_data (List[Dict[str, Any]]): Raw calculation data containing energies and metadata.
        components (Dict[str, List[str]]): Identified reaction components (reactants, products, catalysts).
        energy_lookup (Dict[str, Dict[str, float]]): Optimized lookup table for species energies.
    """
    
    def __init__(self, raw_data_list: List[Dict[str, Any]]):
        """
        Initialize the ProfileExtractor with calculation data.
        
        Args:
            raw_data_list (List[Dict[str, Any]]): List of calculation data dictionaries.
                Each dictionary must contain:
                - 'Species': Species identifier string
                - 'Branch': Calculation branch ('reactants', 'products', 'ts', 'preTS', 'postTS', 'cat')
                - 'Category': Calculation category ('no_cat', 'cat')
                - 'E (kcal/mol)' or 'SP_E (kcal/mol)': Electronic energy in kcal/mol
                - 'G (kcal/mol)': Gibbs free energy in kcal/mol
                - 'all_reactants': List of reactant species names
                - 'all_products': List of product species names
                - 'all_catalysts': List of catalyst species names
                - 'Calc_Type' (optional): EDA calculation type ('frz_cat', 'pol_cat', 'full_cat')
        
        Raises:
            ValueError: If raw_data_list is empty or contains invalid data.
        """
        self.raw_data = raw_data_list
        self.components = self._get_components()
        self.energy_lookup = self._build_energy_lookup()
    
    def _get_components(self) -> Dict[str, List[str]]:
        """Extract reaction components from calculation metadata."""
        if not self.raw_data:
            return {"all_reactants": [], "all_products": [], "all_catalysts": []}
        
        # Get first entry's component data (all entries should have same reaction setup)
        first_entry = self.raw_data[0]
        return {
            "all_reactants": first_entry.get("all_reactants", []),
            "all_products": first_entry.get("all_products", []),  
            "all_catalysts": first_entry.get("all_catalysts", [])
        }
    
    def _build_energy_lookup(self) -> Dict[str, Dict[str, float]]:
        """Build energy lookup table with support for calculation-specific keys."""
        energy_lookup = {}
        
        for data in self.raw_data:
            species = data.get("Species", "")
            if not species:
                continue
            
            # Get energy values
            e_val = data.get("E (kcal/mol)") or data.get("SP_E (kcal/mol)")
            g_val = data.get("G (kcal/mol)")
            g_no_trans_val = data.get("G_no_trans (kcal/mol)")
            
            if e_val is not None and g_val is not None:
                calc_type = data.get("Calc_Type", "")
                
                entry = {"E": e_val, "G": g_val}
                if g_no_trans_val is not None:
                    entry["G_no_trans"] = g_no_trans_val
                
                # Create calc_type-specific key if calc_type exists
                if calc_type and calc_type != "unknown":
                    energy_lookup[f"{species}_{calc_type}"] = entry.copy()
                
                # Always create base species key
                energy_lookup[species] = entry
        
        return energy_lookup
    
    def _get_energy(self, species: str, calc_type: str = None) -> Optional[Dict[str, float]]:
        """Get energy for species, trying calc_type-specific key first if provided."""
        if calc_type:
            calc_type_key = f"{species}_{calc_type}"
            if calc_type_key in self.energy_lookup:
                return self.energy_lookup[calc_type_key]
        
        return self.energy_lookup.get(species)
    
    def _find_entries(self, branch: str = None, category: str = None, catalyst: str = None) -> List[Dict[str, Any]]:
        """Find calculation entries matching specified metadata criteria."""
        matches = []
        for entry in self.raw_data:
            if branch and entry.get("Branch") != branch:
                continue
            if category and entry.get("Category") != category:
                continue
            if catalyst and entry.get("Catalyst") != catalyst:
                continue
            matches.append(entry)
        return matches
    
    def _create_stage(self, stage_name: str, species_list: List[str], calc_types: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create an energy profile stage by combining species energies.
        
        Constructs a single stage in the energy profile by summing the energies
        of the specified species list.
        
        Args:
            stage_name (str): Name identifier for the profile stage.
            species_list (List[str]): List of species identifiers to combine.
            calc_types (List[str], optional): List of calculation types corresponding
                to each species. Must match length of species_list if provided.
                
        Returns:
            Optional[Dict[str, Any]]: Dictionary containing stage data with keys:
                - 'Stage': Stage name identifier
                - 'Species': Combined species string (space + separated)
                - 'E (kcal/mol)': Total electronic energy
                - 'G (kcal/mol)': Total Gibbs free energy
                - 'G_no_trans (kcal/mol)': Total G without translational entropy (if available)
                - 'Source': Energy source description
                Returns None if any required energies are unavailable.
        """
        """Create stage by summing energies of species list."""
        if not species_list:
            return None
        
        total_e = total_g = 0.0
        total_g_no_trans = 0.0
        has_g_no_trans = False
        calc_types = calc_types or [None] * len(species_list)
        
        # Sum energies for all species
        for species, calc_type in zip(species_list, calc_types):
            energy = self._get_energy(species, calc_type)
            if not energy:
                return None
            total_e += energy["E"]
            total_g += energy["G"]
            # Sum G_no_trans if available
            if "G_no_trans" in energy:
                total_g_no_trans += energy["G_no_trans"]
                has_g_no_trans = True
        
        # Get primary calc_type with sanity check
        non_empty_calc_types = [ct for ct in calc_types if ct]
        if len(set(non_empty_calc_types)) > 1:
            logging.warning(f"Mixed calc_types in '{stage_name}': {set(non_empty_calc_types)}")
        primary_calc_type = non_empty_calc_types[0] if non_empty_calc_types else None
        
        # Simple source description
        if len(species_list) == 1 and calc_types[0]:
            source = f"Direct ({calc_types[0]})"
        elif len(species_list) == 1:
            source = "Direct"
        else:
            source = "Addition"
        
        result = {
            "Stage": stage_name,
            "Calc_Type": primary_calc_type,
            "Species": " + ".join(species_list),
            "E (kcal/mol)": total_e,
            "G (kcal/mol)": total_g,
            "Source": source
        }
        
        # Add G_no_trans if available for this stage
        if has_g_no_trans:
            result["G_no_trans (kcal/mol)"] = total_g_no_trans
        
        return result
    
    # def _process_entries(self, entries: List[Dict[str, Any]], stage_prefix: str, 
    #                     missing_logic: callable = None, category: str = "no_cat") -> List[Dict[str, Any]]:
    #     """Process calculation entries to generate energy profile stages with customizable logic."""
    #     stages = []
    #     seen_combinations = set() if category == "no_cat" else None
        
    #     for entry in entries:
    #         # Get basic entry info
    #         species = entry["Species"]
    #         calc_type = entry.get("Calc_Type") if entry.get("Category") == "cat" else None
    #         stage_name = f"{stage_prefix}_{calc_type}" if calc_type else stage_prefix
            
    #         # Determine species list and calc_types
    #         if missing_logic:
    #             species_list, calc_types = missing_logic(entry)
    #         else:
    #             species_list, calc_types = [species], [calc_type] if calc_type else None
            
    #         # Create stage
    #         stage = self._create_stage(stage_name, species_list, calc_types)
    #         if not stage:
    #             continue
                
    #         # Handle duplicates for no_cat
    #         if seen_combinations is not None:
    #             species_set = frozenset(stage["Species"].split(" + "))
    #             if species_set in seen_combinations:
    #                 continue
    #             seen_combinations.add(species_set)
            
    #         stages.append(stage)
        
    #     return stages
    
    def _generate_stages(self, stage_type: str, catalyst: str) -> List[Dict[str, Any]]:
        """Universal stage generator for all stage types using configuration-driven approach."""
        
        # Stage type configurations
        stage_configurations = {
            "reactants": {
                "branch": "reactants", "category": "no_cat", "stage_name": "Reactants",
                "needs_missing_components": True, "needs_catalyst": True, "components_key": "all_reactants"
            },
            "products": {
                "branch": "products", "category": "no_cat", "stage_name": "Products", 
                "needs_missing_components": True, "needs_catalyst": True, "components_key": "all_products"
            },
            "preTS": {
                "branch": "preTS", "category": "cat", "stage_name": "preTS",
                "needs_missing_components": True, "needs_calc_type": True, "components_key": "all_reactants"
            },
            "postTS": {
                "branch": "postTS", "category": "cat", "stage_name": "postTS",
                "needs_missing_components": True, "needs_calc_type": True, "components_key": "all_products"
            },
            "ts_cat": {
                "branch": "ts", "category": "cat", "stage_name": "TS",
                "needs_calc_type": True, "catalyst_present": True
            },
            "ts_nocat": {
                "branch": "ts", "category": "no_cat", "stage_name": "TS",
                "needs_catalyst": True
            }
        }
        
        stage_config = stage_configurations.get(stage_type)
        if not stage_config:
            return []
            
        # Find entries based on configuration
        entries = self._find_entries(
            branch=stage_config["branch"], 
            category=stage_config["category"],
            catalyst=catalyst if stage_config["category"] == "cat" else None
        )
        
        if not entries:
            return []
            
        stages = []
        seen_combinations = set() if stage_config["category"] == "no_cat" else None
        
        for entry in entries:
            calc_type = entry.get("Calc_Type", "")
            
            # Build stage name - keep stage separate from calc_type
            stage_name = stage_config["stage_name"]  # Just use base stage name
            
            # Build species list based on configuration
            species_list = [entry["Species"]]
            calc_types = [calc_type] if calc_type else [None]
            
            # Add missing components if needed
            if stage_config.get("needs_missing_components") and stage_config.get("components_key"):
                components = self.components[stage_config["components_key"]]
                present_components = entry.get(stage_config["components_key"].replace("all_", ""), [])
                missing_components = [c for c in components if c not in present_components]
                
                if missing_components:
                    species_list.extend(missing_components)
                    calc_types.extend([None] * len(missing_components))
            
            # Add catalyst if needed (and not already present)
            if stage_config.get("needs_catalyst") and not stage_config.get("catalyst_present"):
                species_list.append(catalyst)
                calc_types.append(None)
            
            # Handle duplicates for no_cat
            if seen_combinations is not None:
                species_set = frozenset(species_list)
                if species_set in seen_combinations:
                    continue
                seen_combinations.add(species_set)
            
            # Create stage
            stage = self._create_stage(stage_name, species_list, calc_types)
            if stage:
                stages.append(stage)
                
        return stages
    
    def _generate_catalyst_profile(self, catalyst: str) -> List[Dict[str, Any]]:
        """Generate a complete profile for a single catalyst using unified stage generation."""
        profile = []
        
        # Add stages in order: reactants -> preTS -> TS -> postTS -> products
        profile.extend(self._generate_stages("reactants", catalyst))
        profile.extend(self._generate_stages("preTS", catalyst))
        profile.extend(self._generate_stages("ts_cat", catalyst))
        profile.extend(self._generate_stages("ts_nocat", catalyst))
        profile.extend(self._generate_stages("postTS", catalyst))
        profile.extend(self._generate_stages("products", catalyst))
        
        return profile

    def _filter_profile(self, profile: List[Dict[str, Any]], energy_type: str) -> List[Dict[str, Any]]:
        """Smart filtering: Group by stage, find min full_cat, keep same species for pol/frz_cat."""
        energy_key = f"{energy_type} (kcal/mol)"
        stage_groups = {}
        
        # Group by stage name (e.g., "Reactants", "preTS", "TS", etc.)
        for stage in profile:
            stage_name = stage.get("Stage", "")
            if stage_name not in stage_groups:
                stage_groups[stage_name] = []
            stage_groups[stage_name].append(stage)
        
        filtered = []
        for stage_name, stages in stage_groups.items():
            # Subgroup stages: those with calc_types vs those without
            calc_type_stages = [s for s in stages if s.get("Calc_Type") and s.get("Calc_Type") not in [None, "", "unknown"]]
            no_calc_type_stages = [s for s in stages if not s.get("Calc_Type") or s.get("Calc_Type") in [None, "", "unknown"]]
            
            # Handle calc_type subgroup: smart filtering via full_cat
            if calc_type_stages:
                full_cat_stages = [s for s in calc_type_stages if s.get("Calc_Type") == "full_cat"]
                if full_cat_stages:
                    # Find min full_cat, keep same species for pol/frz_cat  
                    min_full_cat = min(full_cat_stages, key=lambda x: x.get(energy_key, float('inf')))
                    min_species = min_full_cat.get("Species", "")
                    
                    filtered.append(min_full_cat)
                    for calc_type in ["pol_cat", "frz_cat"]:
                        matching_stages = [
                            s for s in calc_type_stages 
                            if s.get("Calc_Type") == calc_type and s.get("Species") == min_species
                        ]
                        if matching_stages:
                            filtered.append(matching_stages[0])
                else:
                    # Has calc_types but no full_cat: find lowest energy stage, then keep all calc_types for that species
                    min_stage = min(calc_type_stages, key=lambda x: x.get(energy_key, float('inf')))
                    min_species = min_stage.get("Species", "")
                    
                    # Keep all calc_types that match the minimum species
                    for stage in calc_type_stages:
                        if stage.get("Species") == min_species:
                            filtered.append(stage)
            
            # Handle no-calc_type subgroup: simple minimum energy
            if no_calc_type_stages:
                min_no_calc = min(no_calc_type_stages, key=lambda x: x.get(energy_key, float('inf')))
                filtered.append(min_no_calc)
        
        return sorted(filtered, key=lambda s: profile.index(s))  # Keep original order

    def extract_profiles(self, filter_duplicates: bool = False) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Extract energy profiles for all catalyst pathways."""
        if not self.raw_data:
            return {}
        
        profiles = {}
        for catalyst in self.components["all_catalysts"]:
            raw_profile = self._generate_catalyst_profile(catalyst)
            if raw_profile:  # Only include non-empty profiles
                catalyst_profiles = {
                    "raw": raw_profile, 
                    "unit": Constants.ENERGY_UNIT
                }
                
                if filter_duplicates:
                    catalyst_profiles["E"] = self._filter_profile(raw_profile, "E")
                    catalyst_profiles["G"] = self._filter_profile(raw_profile, "G")
                
                profiles[catalyst] = catalyst_profiles
        
        return profiles

    @classmethod
    def process_all_profiles(cls, raw_data: Dict[str, Dict[str, List[Dict[str, Any]]]]) -> Dict[str, Dict[str, Any]]:
        """
        Process all raw extracted data into profiles for all method combos.
        
        Args:
            raw_data: Dictionary mapping method combo names to their extracted data
            
        Returns:
            Dictionary with raw data + processed profiles for each combo
        """
        if not raw_data:
            return {}
        
        processed_data = {}
        for combo_name, combo_data in raw_data.items():
            processed_data[combo_name] = {
                **combo_data,  # Keep all original data
                "profiles": {}  # Add profiles
            }
            
            # Process profiles for each data type (opt/sp)
            for data_key in ["opt_data", "sp_data"]:
                if combo_data.get(data_key):
                    extractor = cls(combo_data[data_key])
                    processed_data[combo_name]["profiles"][data_key] = extractor.extract_profiles(filter_duplicates=True)
        
        return processed_data
