import subprocess
import json
import re
import yaml
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any


class WebAuto:
    def __init__(self, project_id: str):
        self.project_id = project_id

    def search(self, name_keyword: str) -> List[str]:
        """Search for annotation datasets and return dataset IDs"""
        cmd = [
            "webauto", "data", "annotation-dataset", "search",
            "--project-id", self.project_id,
            "--name-keyword", name_keyword,
            "--unapproved"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            # Parse the output to extract dataset IDs
            lines = result.stdout.strip().split('\n')
            dataset_ids = []
            
            logging.debug(f"Raw output from webauto search: {result.stdout}")
            logging.debug(f"Number of lines: {len(lines)}")
            
            for line in lines:
                # Look for lines that start with "id" followed by whitespace and UUID
                if line.strip().startswith('id'):
                    # Extract the UUID part after "id"
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        potential_id = parts[1]
                        # Validate it's a UUID format
                        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        if re.match(uuid_pattern, potential_id):
                            dataset_ids.append(potential_id)
                            logging.debug(f"Found dataset ID: {potential_id}")
            
            logging.info(f"Found {len(dataset_ids)} datasets for keyword '{name_keyword}'")
            return dataset_ids
        except subprocess.CalledProcessError as e:
            logging.error(f"Error searching datasets: {e}")
            logging.debug(f"stdout: {e.stdout}")
            logging.debug(f"stderr: {e.stderr}")
            return []

    def describe(self, dataset_id: str) -> Dict[str, Any]:
        """Describe a dataset and return its details as JSON"""
        cmd = [
            "webauto", "data", "annotation-dataset", "describe",
            "--annotation-dataset-id", dataset_id,
            "--project-id", self.project_id,
            "--output", "json"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            logging.error(f"Error describing dataset {dataset_id}: {e}")
            logging.debug(f"stdout: {e.stdout}")
            logging.debug(f"stderr: {e.stderr}")
            return {}
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON for dataset {dataset_id}: {e}")
            return {}

    def update(self, dataset_id: str, new_name: str, dry_run: bool = False) -> bool:
        """Update dataset name"""
        cmd = [
            "webauto", "data", "annotation-dataset", "update",
            "--annotation-dataset-id", dataset_id,
            "--project-id", self.project_id,
            "--name", new_name
        ]
        
        try:
            if dry_run:
                logging.debug(f"DRY RUN: Would execute command: {' '.join(cmd)}")
                return True
            else:
                logging.info(f"Updating dataset {dataset_id} to name: {new_name}")
                logging.debug(f"Executing command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                print(f"Successfully updated dataset {dataset_id}")
                return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error updating dataset {dataset_id}: {e}")
            logging.debug(f"stdout: {e.stdout}")
            logging.debug(f"stderr: {e.stderr}")
            return False


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        return {}
    except yaml.YAMLError as e:
        print(f"Error parsing YAML config: {e}")
        return {}


def apply_name_rules(name: str, rules: List[Dict[str, str]]) -> str:
    """Apply regex-based name transformation rules"""
    new_name = name
    for rule in rules:
        pattern = rule.get('from', '')
        replacement = rule.get('to', '')
        if pattern:
            new_name = re.sub(pattern, replacement, new_name)
    return new_name


def rename_dataset(config: Dict[str, Any]):
    """Main function to rename datasets based on configuration"""
    project_id = config.get('project_id')
    name_keywords = config.get('name_keywords', [])
    rules = config.get('rules_regexp', [])
    dry_run = config.get('dry_run', False)
    
    if not project_id:
        print("Error: project_id not found in config")
        return
    
    if not name_keywords:
        print("Error: name_keywords not found in config")
        return
    
    if not rules:
        print("Error: rules_regexp not found in config")
        return
    
    webauto = WebAuto(project_id)
    
    # Step 1: Search for datasets
    all_dataset_ids = []
    for keyword in name_keywords:
        print(f"Searching for datasets with keyword: {keyword}")
        dataset_ids = webauto.search(keyword)
        all_dataset_ids.extend(dataset_ids)
        print(f"Found {len(dataset_ids)} datasets: {dataset_ids}")
    
    # Remove duplicates
    all_dataset_ids = list(set(all_dataset_ids))
    print(f"Total unique datasets found: {len(all_dataset_ids)}")
    
    # Step 2 & 3: Describe and update each dataset
    for dataset_id in all_dataset_ids:
        print(f"\nProcessing dataset: {dataset_id}")
        
        # Step 2: Get current name
        dataset_info = webauto.describe(dataset_id)
        if not dataset_info:
            print(f"Failed to get info for dataset {dataset_id}")
            continue
        
        current_name = dataset_info.get('name', '')
        if not current_name:
            print(f"No name found for dataset {dataset_id}")
            continue
        
        print(f"Current name: {current_name}")
        
        # Apply rules to get new name
        new_name = apply_name_rules(current_name, rules)
        
        if new_name == current_name:
            print(f"No change needed for dataset {dataset_id}")
            continue
        
        print(f"New name: {new_name}")
        
        # Step 3: Update the dataset
        success = webauto.update(dataset_id, new_name, dry_run)
        if not success:
            print(f"Failed to update dataset {dataset_id}")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Rename annotation datasets based on configuration rules")
    parser.add_argument(
        "--config", 
        "-c",
        type=str,
        default=str(Path(__file__).parent / "config" / "example.yaml"),
        help="Path to the configuration YAML file (default: config/example.yaml)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually updating datasets"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output with detailed logging"
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    
    # Configure logging based on verbose flag
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    config_path = args.config
    
    print(f"Loading config from: {config_path}")
    config = load_config(config_path)

    # Add dry-run flag to config
    config['dry_run'] = args.dry_run
    if args.dry_run:
        print("DRY RUN MODE: No actual updates will be performed")
    
    rename_dataset(config)

if __name__ == "__main__":
    main()