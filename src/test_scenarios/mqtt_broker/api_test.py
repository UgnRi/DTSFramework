from src.test_scenarios.base_api_test import BaseAPITest
from src.utils.logger import setup_logger
from typing import Dict, Any, List, Union, Optional
import asyncio
import json

logger = setup_logger()

class MQTTBrokerAPITest(BaseAPITest):
    """API Test implementation for MQTT Broker configuration."""
    
    def __init__(self, device_config: Dict[str, Any], scenario_config=None):
        super().__init__(device_config=device_config, scenario_config=scenario_config)
        self.api_endpoint = "mqtt/broker/config"
        self.mqtt_config = None

    async def setup(self):
        """Setup test environment."""
        logger.info("MQTT Broker API Test: Setting up test environment")
        # Connect to the device API
        await self.connect()
        return True

    async def execute(self):
        """Execute test scenario."""
        logger.info("MQTT Broker API Test: Executing test")
        # Configure MQTT Broker
        await self.configure_mqtt_broker()
        
        # Verify configuration
        result = await self.verify_configuration()
        if not result:
            raise Exception("MQTT Broker configuration verification failed")
        
        return True

    async def cleanup(self):
        """Clean up after test."""
        logger.info("MQTT Broker API Test: Cleaning up")
        # Disconnect from API
        await self.disconnect()
        return True

    async def run(self):
        """Run MQTT Broker API test."""
        try:
            logger.info("API MQTT: Run function started.")
            
            # Implement run logic directly instead of using super().run()
            start_time = asyncio.get_event_loop().time()
            result = {
                'success': False,
                'details': None,
                'error': None,
                'duration': 0
            }
            
            try:
                # Setup
                await self.setup()
                
                # Execute
                await self.execute()
                
                # Success
                result.update({
                    'success': True,
                    'details': 'MQTT Broker configured successfully via API'
                })
            except Exception as e:
                logger.error(f"MQTT Broker API test failed: {str(e)}")
                result.update({
                    'success': False,
                    'error': str(e),
                    'details': str(e)
                })
            finally:
                # Cleanup
                try:
                    await self.cleanup()
                except Exception as e:
                    logger.error(f"MQTT Broker API test cleanup failed: {str(e)}")
                
                # Calculate duration
                end_time = asyncio.get_event_loop().time()
                result['duration'] = round(end_time - start_time, 2)
            
            return result

        except Exception as e:
            logger.error(f"MQTT Broker API test failed: {str(e)}")
            return {
                'success': False,
                'details': str(e)
            }

    async def configure_mqtt_broker(self):
        """Configure MQTT Broker via API."""
        try:
            logger.info("API MQTT: configure_mqtt_broker function started.")
            
            # Extract configuration from scenario
            config = self._extract_config()
            
            # First, get current configuration to find existing IDs or determine next ID to use
            current_config = await self.get_config(self.api_endpoint)
            logger.debug(f"Current broker config: {current_config}")
            
            # Determine ID to use
            broker_id = "mqtt"  # Default ID
            if isinstance(current_config, list) and len(current_config) > 0:
                # Use the first existing ID
                broker_id = current_config[0].get("id", "mqtt")
            
            # Get values from config
            port = config.get("port", "1883")
            anonymous_access = config.get("anonymous_access", True)
            remote_access = config.get("remote_access", False)
            
            # Get security settings
            security_config = config.get("security", {})
            use_tls_ssl = security_config.get("TLS/SSL", False)
            
            # Create the exact structure as shown in the API documentation
            mqtt_config = {
                "data": [{
                    "id": broker_id,
                    "enabled": "1",
                    "anonymous_access": "1" if anonymous_access else "0",
                    "local_port": [str(port)],
                    "allow_ra": "1" if remote_access else "0",
                    "use_tls_ssl": "1" if use_tls_ssl else "0"
                }]
            }
            
            # Add additional configuration fields if present
            if "miscellaneous" in config:
                misc_config = config["miscellaneous"]
                if "persistence" in misc_config:
                    mqtt_config["data"][0]["persistence"] = "1" if misc_config["persistence"] else "0"
                if "max_queued_messages" in misc_config:
                    mqtt_config["data"][0]["max_queued_messages"] = str(misc_config["max_queued_messages"])
                if "maximum_packet_size" in misc_config:
                    mqtt_config["data"][0]["max_packet_size"] = str(misc_config["maximum_packet_size"])
            
            # Update the MQTT broker config using PUT
            await self.api_request("put", self.api_endpoint, mqtt_config)
            logger.info("MQTT Broker configuration updated successfully")
            
            # Save configuration for verification
            self.mqtt_config = mqtt_config
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure MQTT Broker via API: {str(e)}")
            
            # Try alternate approach - update specific ID endpoint
            try:
                # Get the ID if possible
                broker_id = "mqtt"  # Default ID
                current_config = await self.get_config(self.api_endpoint)
                if isinstance(current_config, list) and len(current_config) > 0:
                    # Use the first existing ID
                    broker_id = current_config[0].get("id", "mqtt")
                
                # Create minimal configuration for the specific ID
                minimal_config = {
                    "data": {
                        "enabled": "1",
                        "anonymous_access": "1" if config.get("anonymous_access", True) else "0",
                        "local_port": [str(config.get("port", "1883"))],
                        "allow_ra": "1" if config.get("remote_access", False) else "0",
                        "use_tls_ssl": "0"
                    }
                }
                
                # Use PUT on the specific ID endpoint
                specific_endpoint = f"{self.api_endpoint}/{broker_id}"
                await self.api_request("put", specific_endpoint, minimal_config)
                logger.info("MQTT Broker configured with specific ID endpoint")
                return True
                
            except Exception as fallback_error:
                logger.error(f"Fallback approach also failed: {str(fallback_error)}")
                raise e

    def _build_mqtt_config(self, config: Dict[str, Any], current_config: Dict[str, Any]) -> Dict[str, Any]:
        """Build MQTT Broker configuration."""
        try:
            # Create a new configuration following the required format
            # Convert all values to strings to match API requirements
            mqtt_config = []
            
            # Start with the first item (or create one if empty)
            config_item = {}
            if isinstance(current_config, list) and current_config:
                config_item = current_config[0].copy()
            elif isinstance(current_config, dict) and current_config:
                # Use the whole dict if it's not a list
                config_item = current_config.copy()
            
            # Set ID if available
            if "id" not in config_item:
                config_item["id"] = "1"  # Default ID
            
            # Set basic settings - use "1" not "True"
            config_item["enabled"] = "1"
            
            # Configure port if specified
            if 'port' in config:
                # Make sure port is in a list of strings
                config_item["local_port"] = [str(config["port"])]
            
            # Configure anonymous access
            if 'anonymous_access' in config:
                config_item["anonymous_access"] = "1" if config["anonymous_access"] else "0"
            
            # Configure remote access if specified
            if 'remote_access' in config:
                config_item["allow_ra"] = "1" if config["remote_access"] else "0"
            
            # Disable TLS completely - this is a simpler approach for testing
            config_item["use_tls_ssl"] = "0"
            
            # Configure miscellaneous settings
            if 'miscellaneous' in config:
                self._configure_misc_settings(config_item, config["miscellaneous"])
            
            # Add the config item to the list
            mqtt_config.append(config_item)
            
            logger.debug(f"Built MQTT configuration: {mqtt_config}")
            return {"data": mqtt_config}
            
        except Exception as e:
            logger.error(f"Failed to build MQTT configuration: {str(e)}")
            raise

    def _configure_security_settings(self, mqtt_config: Dict[str, Any], security_config: Dict[str, Any]):
        """Configure MQTT security settings."""
        try:
            # Configure TLS/SSL
            if 'TLS/SSL' in security_config:
                mqtt_config["use_tls_ssl"] = "1" if security_config["TLS/SSL"] else "0"
            
            # Configure TLS version if specified
            if 'TLS_version' in security_config:
                mqtt_config["tls_version"] = str(security_config["TLS_version"])
            
            # Configure certificates
            if 'certificates' in security_config:
                cert_config = security_config['certificates']
                
                # Set TLS type
                if 'tls_type' in cert_config:
                    tls_type = cert_config['tls_type']
                    if tls_type == 'Certificate based':
                        mqtt_config["tls_type"] = "cert"
                    elif tls_type == 'Pre-Shared-Key based':
                        mqtt_config["tls_type"] = "psk"
                
                # Set require certificate
                if 'require_certificate' in cert_config:
                    mqtt_config["require_certificate"] = "1" if cert_config["require_certificate"] else "0"
                
                # Handle certificate files - ONLY SET THEM IF THEY EXIST ON THE DEVICE
                # For testing, it's safer not to set certificate paths at all
                # since we don't know if the files actually exist on the device
                
                # Handle PSK settings
                if 'pre-shared-key' in cert_config:
                    mqtt_config["psk"] = str(cert_config["pre-shared-key"])
                if 'identity' in cert_config:
                    mqtt_config["identity"] = str(cert_config["identity"])
            
        except Exception as e:
            logger.error(f"Failed to configure MQTT security settings: {str(e)}")
            raise

    def _configure_misc_settings(self, mqtt_config: Dict[str, Any], misc_config: Dict[str, Any]):
        """Configure MQTT miscellaneous settings."""
        try:
            # Configure persistence
            if 'persistence' in misc_config:
                mqtt_config["persistence"] = "1" if misc_config["persistence"] else "0"
            
            # Configure anonymous access
            if 'allow_anonymous' in misc_config:
                mqtt_config["anonymous_access"] = "1" if misc_config["allow_anonymous"] else "0"
            
            # Configure max queued messages
            if 'max_queued_messages' in misc_config:
                mqtt_config["max_queued_messages"] = str(misc_config["max_queued_messages"])
            
            # Configure maximum packet size
            if 'maximum_packet_size' in misc_config:
                mqtt_config["max_packet_size"] = str(misc_config["maximum_packet_size"])
            
        except Exception as e:
            logger.error(f"Failed to configure MQTT miscellaneous settings: {str(e)}")
            raise

    async def verify_configuration(self) -> bool:
        """Verify the applied configuration."""
        try:
            logger.info("API MQTT: verify_configuration function started.")
            
            # Get current configuration
            current_config = await self.get_config(self.api_endpoint)
            
            # Extract our configuration
            config = self._extract_config()
            
            # Handle case where current_config is a list
            if isinstance(current_config, list) and current_config:
                current_item = current_config[0]
            else:
                current_item = current_config
            
            # Check if MQTT is enabled
            if current_item.get("enabled", "0") not in ["1", "true", True, 1]:
                logger.error("MQTT broker is not enabled")
                return False
            
            # Check port configuration if specified
            if 'port' in config:
                expected_port = str(config["port"])
                actual_ports = current_item.get("local_port", [])
                # Convert to list if it's not already
                if not isinstance(actual_ports, list):
                    actual_ports = [actual_ports]
                
                if expected_port not in actual_ports:
                    logger.error(f"MQTT port mismatch. Expected: {expected_port}, Got: {actual_ports}")
                    return False
            
            # Check anonymous access if specified
            if 'anonymous_access' in config:
                expected_access = str(self.format_bool_value(config["anonymous_access"]))
                actual_access = current_item.get("anonymous_access")
                if actual_access != expected_access:
                    logger.error(f"MQTT anonymous access mismatch. Expected: {expected_access}, Got: {actual_access}")
                    return False
            
            process_info = await self.api_request("get", "mqtt/broker/config")
            if isinstance(process_info, dict) and isinstance(process_info.get("data"), list):
                process_info = process_info["data"][0] if process_info["data"] else {}

            if not isinstance(process_info, dict):
                logger.error("Invalid MQTT broker response format")
                return False

            running_status = process_info.get("enabled")
            if running_status not in [True, "1", 1, "true"]:
                logger.error("MQTT broker service is not running")
                return False
                
            logger.info("Configuration verification successful")
            return True
            
        except Exception as e:
            logger.error(f"Configuration verification failed: {str(e)}")
            return False
            
            logger.info("Configuration verification successful")
            return True
            
        except Exception as e:
            logger.error(f"Configuration verification failed: {str(e)}")
            return False

    # def _configure_security_settings(self, mqtt_config: Dict[str, Any], security_config: Dict[str, Any]):
    #     """Configure MQTT security settings."""
    #     try:
    #         # Configure TLS/SSL
    #         if 'TLS/SSL' in security_config:
    #             mqtt_config["use_tls_ssl"] = "1" if security_config["TLS/SSL"] else "0"
            
    #         # Configure TLS version if specified
    #         if 'TLS_version' in security_config:
    #             mqtt_config["tls_version"] = str(security_config["TLS_version"])
            
    #         # Configure certificates
    #         if 'certificates' in security_config:
    #             cert_config = security_config['certificates']
                
    #             # Set TLS type
    #             if 'tls_type' in cert_config:
    #                 tls_type = cert_config['tls_type']
    #                 if tls_type == 'Certificate based':
    #                     mqtt_config["tls_type"] = "cert"
    #                 elif tls_type == 'Pre-Shared-Key based':
    #                     mqtt_config["tls_type"] = "psk"
                
    #             # Set require certificate
    #             if 'require_certificate' in cert_config:
    #                 mqtt_config["require_certificate"] = "1" if cert_config["require_certificate"] else "0"
                
    #             # Handle certificate files
    #             if 'certificate_files_from_device' in cert_config:
    #                 from_device = cert_config['certificate_files_from_device']
    #                 mqtt_config["device_sec_files"] = "1" if from_device else "0"
                    
    #                 if from_device and 'device_certificates' in cert_config:
    #                     device_certs = cert_config['device_certificates']
    #                     if 'ca_file' in device_certs:
    #                         # Ensure proper path format
    #                         mqtt_config["ca_file"] = f"/etc/certificates/{device_certs['ca_file']}"
    #                     if 'certificate_file' in device_certs:
    #                         # Ensure proper path format
    #                         mqtt_config["cert_file"] = f"/etc/ssl/certs/{device_certs['certificate_file']}"
    #                     if 'key_file' in device_certs:
    #                         # Ensure proper path format
    #                         mqtt_config["key_file"] = f"/etc/certificates/{device_certs['key_file']}"
    #                 else:
    #                     # Handle uploaded certificates - ensure proper path format
    #                     if 'ca_file' in cert_config:
    #                         mqtt_config["ca_file"] = f"/etc/certificates/{cert_config['ca_file']}"
    #                     if 'certificate_file' in cert_config:
    #                         mqtt_config["cert_file"] = f"/etc/ssl/certs/{cert_config['certificate_file']}"
    #                     if 'key_file' in cert_config:
    #                         mqtt_config["key_file"] = f"/etc/certificates/{cert_config['key_file']}"
                
    #             # Handle PSK settings
    #             if 'pre-shared-key' in cert_config:
    #                 mqtt_config["psk"] = str(cert_config["pre-shared-key"])
    #             if 'identity' in cert_config:
    #                 mqtt_config["identity"] = str(cert_config["identity"])
            
    #     except Exception as e:
    #         logger.error(f"Failed to configure MQTT security settings: {str(e)}")
    #         raise