# src/utils/config_loader.py
import json
from pathlib import Path
from typing import Dict, Any
from src.utils.logger import setup_logger

logger = setup_logger()

class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    pass

class ConfigLoader:
    @staticmethod
    def load_config(file_path: str) -> Dict[str, Any]:
        """Load and validate configuration from JSON file"""
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)
            
            ConfigLoader._validate_config(config, file_path)
            return config
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config file {file_path}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error loading config from {file_path}: {str(e)}")
            raise
            
    @staticmethod
    def load_scenario_config(scenario_name: str) -> Dict[str, Any]:
        """Load scenario-specific configuration"""
        scenario_path = Path('config/test_scenarios') / f"{scenario_name}.json"
        return ConfigLoader.load_config(str(scenario_path))
        
    @staticmethod
    def _validate_config(config: Dict[str, Any], file_path: str):
        """Validate configuration structure"""
        if 'device_config.json' in file_path:
            required_fields = {
                'device': {
                    'name': str,
                    'ip': str,
                    'credentials': {
                        'username': str,
                        'password': str
                    },
                    'ssh': {
                        'username': str,
                        'password': str
                    }
                }
            }
            
        elif 'mqtt_broker.json' in file_path:
            required_fields = {
                'scenario_name': str,
                'config': {
                    'port': str,
                    'validation': {
                        'timeout': int,
                        'retry_interval': int,
                        'max_retries': int
                    }
                }
            }
            
        elif 'data_to_server.json' in file_path:
            required_fields = {
                'scenario_name': str,
                'config': {
                    'instanceName': str,
                    'period': str,
                    'mqttServer': str,
                    'mqttTopic': str,
                    'clientID': str,
                    'validation': {
                        'timeout': int,
                        'retry_interval': int,
                        'max_retries': int
                    }
                }
            }
            
        ConfigLoader._validate_structure(config, required_fields, [])
            
    @staticmethod
    def _validate_structure(config: Dict[str, Any], required: Dict[str, Any], path: list):
        """Recursively validate configuration structure"""
        for key, value_type in required.items():
            current_path = path + [key]
            
            if key not in config:
                raise ConfigValidationError(
                    f"Missing required field: {'.'.join(current_path)}"
                )
                
            if isinstance(value_type, dict):
                if not isinstance(config[key], dict):
                    raise ConfigValidationError(
                        f"Field {'.'.join(current_path)} must be an object"
                    )
                ConfigLoader._validate_structure(
                    config[key], value_type, current_path
                )
            else:
                if not isinstance(config[key], value_type):
                    raise ConfigValidationError(
                        f"Field {'.'.join(current_path)} must be of type {value_type.__name__}"
                    )

# Function to expose for direct import
def load_config(file_path: str) -> Dict[str, Any]:
    """Load configuration file"""
    return ConfigLoader.load_config(file_path)

def load_scenario_config(scenario_name: str) -> Dict[str, Any]:
    """Load scenario configuration"""
    return ConfigLoader.load_scenario_config(scenario_name)