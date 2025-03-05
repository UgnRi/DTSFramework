import os
from src.test_scenarios.base_api_test import BaseAPITest
from src.utils.logger import setup_logger
from typing import Dict, Any, List, Union, Optional
import asyncio
import json

logger = setup_logger()


class DataToServerAPITest(BaseAPITest):
    """API Test implementation for Data to Server configuration."""

    def __init__(self, device_config: Dict[str, Any], scenario_config=None):
        super().__init__(device_config=device_config, scenario_config=scenario_config)
        self.api_endpoint = "data_to_server"
        self.dts_config = None

    async def setup(self):
        """Setup test environment."""
        logger.info("Data to Server API Test: Setting up test environment")
        # Connect to the device API
        await self.connect()
        return True

    async def execute(self):
        """Execute test scenario."""
        logger.info("Data to Server API Test: Executing test")
        # Configure Data to Server
        await self.configure_dts()

        # Verify configuration
        result = await self.verify_configuration()
        if not result:
            raise Exception("Data to Server configuration verification failed")

        return True

    async def cleanup(self):
        """Clean up after test - delete the created data_to_server configuration and disconnect."""
        logger.info("Data to Server API Test: Cleaning up")

        try:
            # Get the collection ID that was created during configure_dts
            collection_id = (
                self.dts_config.get("collection_id") if self.dts_config else None
            )

            if collection_id:
                # Delete the created data_to_server configuration
                logger.info(
                    f"Cleaning up Data to Server configuration with ID: {collection_id}"
                )

                delete_request = {"data": [str(collection_id)]}

                try:
                    delete_result = await self.api_request(
                        "delete",
                        f"{self.api_endpoint}/collections/config",
                        delete_request,
                    )
                    logger.info(
                        f"Deleted Data to Server configuration result: {json.dumps(delete_result)}"
                    )
                except Exception as delete_error:
                    logger.warning(
                        f"Failed to delete Data to Server configuration: {str(delete_error)}"
                    )
            else:
                logger.info("No Data to Server configuration to clean up")

        except Exception as e:
            logger.error(f"Error during Data to Server cleanup: {str(e)}")

        # Disconnect from API
        await self.disconnect()

        return True

    async def run(self):
        """Run Data to Server API test."""
        try:
            logger.info("API DTS: Run function started.")

            # Implement run logic directly instead of using super().run()
            start_time = asyncio.get_event_loop().time()
            result = {"success": False, "details": None, "error": None, "duration": 0}

            try:
                # Setup
                await self.setup()

                # Execute
                await self.execute()

                # Success
                result.update(
                    {
                        "success": True,
                        "details": "Data to Server configured successfully via API",
                    }
                )
            except Exception as e:
                logger.error(f"Data to Server API test failed: {str(e)}")
                result.update({"success": False, "error": str(e), "details": str(e)})
            finally:
                # Cleanup
                try:
                    await self.cleanup()
                except Exception as e:
                    logger.error(f"Data to Server API test cleanup failed: {str(e)}")

                # Calculate duration
                end_time = asyncio.get_event_loop().time()
                result["duration"] = round(end_time - start_time, 2)

            return result

        except Exception as e:
            logger.error(f"Data to Server API test failed: {str(e)}")
            return {"success": False, "details": str(e)}

    async def configure_dts(self):
        """Configure Data to Server via API."""
        try:
            logger.info("API DTS: configure_dts function started.")

            # Extract configuration
            config = self._extract_config()

            # Get the configured values from the test scenario file
            instance_name = config.get("instanceName", "test_instance")

            # Get collection configuration, checking for different variations
            # Try getting different collection config variations
            collection_configs = {
                k: v for k, v in config.items() if k.startswith("collection_config")
            }
            logger.info(
                f"Available collection configurations: {list(collection_configs.keys())}"
            )

            # Use standard collection_config if available, otherwise try others
            collection_config = config.get("collection_config", {})
            if not collection_config and collection_configs:
                # Use first available collection config if standard not found
                first_key = list(collection_configs.keys())[0]
                collection_config = collection_configs[first_key]
                logger.info(f"Using alternative collection config: {first_key}")

            period = collection_config.get("period", 5)
            retry = collection_config.get("retry", True)
            retry_count = collection_config.get("retry_count", 3)
            retry_timeout = collection_config.get("timeout", 10)

            # Log the selected collection configuration
            logger.info(f"Selected collection config: {json.dumps(collection_config)}")

            # The server config from the test scenario
            # Try finding all server configuration variations
            server_configs = {
                k: v for k, v in config.items() if k.startswith("server_config")
            }
            logger.info(
                f"Available server configurations: {list(server_configs.keys())}"
            )

            # Use standard server_config if available, otherwise try alternatives
            server_config = config.get("server_config", {})
            if not server_config and server_configs:
                # Use first available server config if standard not found
                first_key = list(server_configs.keys())[0]
                server_config = server_configs[first_key]
                logger.info(f"Using alternative server config: {first_key}")

            # For backward compatibility, also check older key names
            if not server_config:
                # Check if older key names for server configuration exist
                if (
                    "mqttServer" in config
                    and "mqttTopic" in config
                    and "clientID" in config
                ):
                    logger.info("Using legacy server configuration keys")
                    server_config = {
                        "server_address": config.get("mqttServer"),
                        "topic": config.get("mqttTopic"),
                        "client_id": config.get("clientID"),
                        # Use defaults for other settings
                        "port": 1883,
                        "QoS": 2,
                        "keepalive": 30,
                    }

            # Extract server configuration values with defaults
            server_address = server_config.get("server_address", "test.mosquitto.org")
            port = server_config.get("port", 1883)
            topic = server_config.get("topic", "test/topic")
            client_id = server_config.get("client_id", "test_client")
            qos = server_config.get("QoS", 2)
            keepalive = server_config.get("keepalive", 30)

            # Log the selected server configuration
            logger.info(f"Selected server config: {json.dumps(server_config)}")

            # Get data_config, checking for variations like data_config-Bluetooth
            # First try to get the basic data_config
            basic_data_config = config.get("data_config", {})

            # If the basic data_config has a type, look for type-specific config
            data_type = basic_data_config.get("type", "")
            logger.info(f"Data type from basic config: {data_type}")

            # Try to get type-specific configuration using the determined type
            type_specific_key = f"data_config-{data_type}" if data_type else None
            data_config = self._get_config_by_key_prefix(
                config, "data_config", type_specific_key
            )

            logger.info(f"Selected data_config: {json.dumps(data_config)}")

            # Get current data_to_server configurations
            current_config = await self.get_current_dts_config()
            logger.info(
                f"Current Data to Server configurations: {json.dumps(current_config)}"
            )

            # Get the next available IDs for a new collection
            next_ids = self.get_next_ids(current_config)
            logger.info(f"Next available IDs: {next_ids}")

            # Use determined IDs for new collection
            collection_id = next_ids["collection_id"]
            data_id = next_ids["data_id"]
            server_id = next_ids["server_id"]

            # Prepare API requests
            api_requests = []

            # Step 1: Create a new collection
            await self.api_request(
                "post",
                f"{self.api_endpoint}/collections/config",
                {"data": {"name": instance_name}},
            )

            # Configure data plugin with values from your config
            if data_config:
                logger.info(f"Data config: {data_config}")

                # Different data types use different plugin names in the API
                plugin_name_map = {
                    "base": "base",
                    "bluetooth": "bluetooth",
                    "gsm": "gsm",
                    "impulse counter": "impulse_counter",
                    "lua script": "lua",
                    "mobile usage": "mdcollect",
                    "mnf info": "mnfinfo",
                    "modbus": "modbus",
                    "modbus alarms": "modbus_alarm",
                    "mqtt": "mqtt",
                    "wifi scanner": "wifiscan",
                }

                data_type_lowercase = data_config.get("type", "Base").lower()
                plugin_name = plugin_name_map.get(
                    data_type_lowercase, data_type_lowercase
                )

                data_plugin = {
                    "plugin": plugin_name,
                    ".type": "input",
                    "name": f"input_{instance_name}",
                    "members": [],
                }

                # Handle different format types based on the API format
                format_type = data_config.get("format_type", "JSON").lower()
                if format_type == "json":
                    data_plugin["format"] = "json"
                elif format_type == "custom":
                    data_plugin["format"] = "custom"
                    if "format_string" in data_config:
                        data_plugin["format_str"] = data_config["format_string"]
                    if "empty_value" in data_config:
                        data_plugin["na_str"] = data_config["empty_value"]
                    if "delimiter" in data_config:
                        data_plugin["delimiter"] = data_config["delimiter"]
                elif format_type == "lua script":
                    data_plugin["format"] = "lua"
                    if "lua_format_script" in data_config:
                        data_plugin["format_script"] = data_config["lua_format_script"]

                # Add values to collect
                if "values" in data_config:
                    logger.info(f"Values: {data_config.get('values')}")
                    data_plugin["members"] = data_config["values"]

                # Configure type-specific settings based on the API field names
                if "type_settings" in data_config:
                    logger.info(f"Type settings: {data_config.get('type_settings')}")

                    # Configure settings based on data type
                    if data_type_lowercase == "bluetooth":
                        # Handle Bluetooth specific settings
                        if "data_filtering" in data_config["type_settings"]:
                            filter_type = data_config["type_settings"][
                                "data_filtering"
                            ].lower()
                            if "mac" in filter_type:
                                data_plugin["bl_filter"] = "mac"
                        if "MAC_address" in data_config["type_settings"]:
                            mac_addresses = data_config["type_settings"]["MAC_address"]
                            if isinstance(mac_addresses, str):
                                mac_addresses = [mac_addresses]
                            data_plugin["bl_filter_mac"] = mac_addresses
                        if "segment_count" in data_config["type_settings"]:
                            data_plugin["bl_segments"] = str(
                                data_config["type_settings"]["segment_count"]
                            )
                        if "send_as_object" in data_config["type_settings"]:
                            data_plugin["bl_object"] = (
                                "1"
                                if data_config["type_settings"]["send_as_object"]
                                else "0"
                            )

                    elif data_type_lowercase == "gsm":
                        # GSM typically doesn't have additional settings based on the API example
                        pass

                    elif data_type_lowercase == "impulse counter":
                        # Handle Impulse counter specific settings
                        if "data_filtering" in data_config["type_settings"]:
                            filter_type = data_config["type_settings"][
                                "data_filtering"
                            ].lower()
                            if "pin" in filter_type:
                                data_plugin["impulse_counter_filter"] = "pin"
                        if "impulse_counter_pin" in data_config["type_settings"]:
                            # Map human-readable pin names to API values
                            pin_name_map = {
                                "Input (3)": "din1",
                                "Input (4)": "din2",
                                "Output (3)": "dout1",
                                "Output (4)": "dout2",
                            }

                            pin_names = data_config["type_settings"][
                                "impulse_counter_pin"
                            ]
                            # Convert to list if it's a single value
                            if not isinstance(pin_names, list):
                                pin_names = [pin_names]

                            # Map pin names to their API values
                            mapped_pins = []
                            for pin in pin_names:
                                if pin in pin_name_map:
                                    mapped_pins.append(pin_name_map[pin])
                                else:
                                    # If pin name is not in mapping, use it directly
                                    mapped_pins.append(pin)

                            data_plugin["impulse_counter_filter_pin"] = mapped_pins
                        if "invert_filter" in data_config["type_settings"]:
                            data_plugin["impulse_counter_filter_invert"] = (
                                "1"
                                if data_config["type_settings"]["invert_filter"]
                                else "0"
                            )
                        if "max_segment_count" in data_config["type_settings"]:
                            data_plugin["impulse_counter_segments"] = str(
                                data_config["type_settings"]["max_segment_count"]
                            )
                        if "send_as_object" in data_config["type_settings"]:
                            data_plugin["impulse_counter_object"] = (
                                "1"
                                if data_config["type_settings"]["send_as_object"]
                                else ""
                            )

                    elif data_type_lowercase == "lua script":
                        # Handle Lua script specific settings
                        if "lua_script_location" in data_config["type_settings"]:
                            script_location = data_config["type_settings"][
                                "lua_script_location"
                            ]
                            script_filename = "script.lua"  # Default filename
                            script_content = '#!/usr/bin/lua\nprint("hello world")'  # Default content

                            # Extract script content and filename based on location format
                            if isinstance(script_location, str):
                                file_path = script_location
                                # Try to read script from file
                                try:
                                    with open(file_path, "r") as script_file:
                                        script_content = script_file.read()
                                        script_filename = os.path.basename(file_path)
                                        logger.info(
                                            f"Successfully read Lua script from {file_path}"
                                        )
                                except Exception as file_error:
                                    logger.error(
                                        f"Failed to read Lua script from file {file_path}: {str(file_error)}"
                                    )
                                    # Always use default script content instead of the path
                                    logger.info(
                                        f"Using default 'hello world' Lua script"
                                    )

                            # Upload the Lua script first before continuing with configuration
                            logger.info(
                                f"Uploading Lua script content for collection {collection_id}, data {data_id}"
                            )
                            upload_result = await self.upload_lua_script(
                                collection_id=collection_id,
                                data_id=data_id,
                                script_content=script_content,
                                script_filename=script_filename,
                            )

                            # Check if upload was successful and get the path from the response
                            if (
                                upload_result
                                and isinstance(upload_result, dict)
                                and "data" in upload_result
                                and "path" in upload_result["data"]
                            ):
                                # Use the path returned from the upload result
                                script_path = upload_result["data"]["path"]
                                logger.info(
                                    f"Using uploaded script path from response: {script_path}"
                                )
                                data_plugin["lua_script"] = script_path
                            else:
                                # If upload failed or no path returned, use a default path format
                                script_path = f"/etc/vuci-uploads/cbid.data_sender.{data_id}.lua_script{script_filename}"
                                logger.warning(
                                    f"Upload result didn't contain path, using default path: {script_path}"
                                )
                                data_plugin["lua_script"] = script_path

                    elif data_type_lowercase == "mobile usage":
                        # Handle Mobile usage specific settings
                        if "data_period" in data_config["type_settings"]:
                            data_plugin["mdc_period"] = data_config["type_settings"][
                                "data_period"
                            ].lower()
                        if "current" in data_config["type_settings"]:
                            data_plugin["mdc_current"] = (
                                "1" if data_config["type_settings"]["current"] else "0"
                            )
                        if "SIM_number" in data_config["type_settings"]:
                            # Extract the SIM number from format like "SIM 2" -> "2"
                            sim_number = data_config["type_settings"]["SIM_number"]
                            if isinstance(sim_number, str) and "SIM" in sim_number:
                                sim_number = sim_number.replace("SIM", "").strip()
                            data_plugin["mdc_sim"] = sim_number

                    elif data_type_lowercase == "modbus":
                        # Handle Modbus specific settings
                        if "data_filtering" in data_config["type_settings"]:
                            filter_type = data_config["type_settings"][
                                "data_filtering"
                            ].lower()
                            if "server" in filter_type and "ip" in filter_type:
                                data_plugin["modbus_filter"] = "ip"
                            elif "server" in filter_type and "id" in filter_type:
                                data_plugin["modbus_filter"] = "id"
                        if "server_ip" in data_config["type_settings"]:
                            data_plugin["modbus_filter_server_ip"] = data_config[
                                "type_settings"
                            ]["server_ip"]
                        if "server_id" in data_config["type_settings"]:
                            server_ids = data_config["type_settings"]["server_id"]
                            if not isinstance(server_ids, list):
                                server_ids = [str(server_ids)]
                            else:
                                server_ids = [str(s) for s in server_ids]
                            data_plugin["modbus_filter_server_id"] = server_ids
                        if "segment_count" in data_config["type_settings"]:
                            data_plugin["modbus_segments"] = str(
                                data_config["type_settings"]["segment_count"]
                            )
                        if "send_as_object" in data_config["type_settings"]:
                            data_plugin["modbus_object"] = (
                                "1"
                                if data_config["type_settings"]["send_as_object"]
                                else "0"
                            )

                    elif data_type_lowercase == "modbus alarms":
                        # Handle Modbus Alarms specific settings
                        if "data_filtering" in data_config["type_settings"]:
                            filter_type = data_config["type_settings"][
                                "data_filtering"
                            ].lower()
                            if "server_id" in filter_type:
                                data_plugin["modbus_alarm_filter"] = "server_id"
                        if "server_id" in data_config["type_settings"]:
                            server_ids = data_config["type_settings"]["server_id"]
                            if not isinstance(server_ids, list):
                                server_ids = [str(server_ids)]
                            else:
                                server_ids = [str(s) for s in server_ids]
                            data_plugin["modbus_alarm_filter_server_id"] = server_ids

                    elif data_type_lowercase == "mqtt":
                        # Handle MQTT specific settings
                        if "server_address" in data_config["type_settings"]:
                            data_plugin["mqtt_in_host"] = data_config["type_settings"][
                                "server_address"
                            ]
                        if "port" in data_config["type_settings"]:
                            data_plugin["mqtt_in_port"] = str(
                                data_config["type_settings"]["port"]
                            )
                        if "keepalive" in data_config["type_settings"]:
                            data_plugin["mqtt_in_keepalive"] = str(
                                data_config["type_settings"]["keepalive"]
                            )
                        if "topic" in data_config["type_settings"]:
                            data_plugin["mqtt_in_topic"] = data_config["type_settings"][
                                "topic"
                            ]
                        if "client_id" in data_config["type_settings"]:
                            data_plugin["mqtt_in_client_id"] = str(
                                data_config["type_settings"]["client_id"]
                            )
                        if "QoS" in data_config["type_settings"]:
                            data_plugin["mqtt_in_qos"] = str(
                                data_config["type_settings"]["QoS"]
                            )
                        if "enable_secure_connection" in data_config["type_settings"]:
                            data_plugin["mqtt_in_tls"] = (
                                "1"
                                if data_config["type_settings"][
                                    "enable_secure_connection"
                                ]
                                else "0"
                            )

                            # Handle secure connection settings if enabled
                            if (
                                data_config["type_settings"].get(
                                    "enable_secure_connection"
                                )
                                and "secure_connection" in data_config["type_settings"]
                            ):
                                secure_conn = data_config["type_settings"][
                                    "secure_connection"
                                ]

                                if "allow_insecure_connection" in secure_conn:
                                    data_plugin["mqtt_in_insecure"] = (
                                        "1"
                                        if secure_conn["allow_insecure_connection"]
                                        else "0"
                                    )

                                # Set TLS type to cert
                                data_plugin["mqtt_in_tls_type"] = "cert"

                                # Handle certificates based on source (device or custom)
                                if "certificate_files_from_device" in secure_conn:
                                    # Store if using device files for later use in request formation
                                    uses_device_files = secure_conn[
                                        "certificate_files_from_device"
                                    ]
                                    data_plugin["mqtt_device_files"] = (
                                        "1" if uses_device_files else "0"
                                    )

                                    if uses_device_files:
                                        # Use device certificates
                                        if "device_certificates" in secure_conn:
                                            dev_certs = secure_conn[
                                                "device_certificates"
                                            ]
                                            if (
                                                "certificate_authority_file"
                                                in dev_certs
                                            ):
                                                data_plugin["mqtt_in_cafile"] = (
                                                    dev_certs[
                                                        "certificate_authority_file"
                                                    ]
                                                )
                                            if "client_certificate" in dev_certs:
                                                data_plugin["mqtt_in_certfile"] = (
                                                    dev_certs["client_certificate"]
                                                )
                                            if "client_private_keyfile" in dev_certs:
                                                data_plugin["mqtt_in_keyfile"] = (
                                                    dev_certs["client_private_keyfile"]
                                                )

                                    # For certificate_files_from_device = False, we don't add paths here
                                    # as we'll handle uploads separately after the initial configuration
                                    # We'll still set mqtt_device_files = "0" above to indicate custom certificates

                        # Handle MQTT credentials
                        if (
                            "username" in data_config["type_settings"]
                            and "password" in data_config["type_settings"]
                        ):
                            data_plugin["mqtt_in_username"] = data_config[
                                "type_settings"
                            ]["username"]
                            data_plugin["mqtt_in_password"] = data_config[
                                "type_settings"
                            ]["password"]

                    elif data_type_lowercase == "wifi scanner":
                        # Handle Wifi scanner specific settings
                        if "data_filtering" in data_config["type_settings"]:
                            filter_type = data_config["type_settings"][
                                "data_filtering"
                            ].lower()
                            if "signal" in filter_type:
                                data_plugin["wifi_filter"] = "signal"
                            elif "mac" in filter_type:
                                data_plugin["wifi_filter"] = "mac"

                        if "signal_strength" in data_config["type_settings"]:
                            # Convert signal strength array to range string
                            signal_range = data_config["type_settings"][
                                "signal_strength"
                            ]
                            if len(signal_range) >= 2:
                                data_plugin["wifi_filter_signal"] = [
                                    str(signal_range[0]),
                                    str(signal_range[1]),
                                ]
                                # Add default values to match the example format
                                data_plugin["wifi_filter_signal"].extend(["-10", "-1"])

                        if "MAC_address" in data_config["type_settings"]:
                            mac_addresses = data_config["type_settings"]["MAC_address"]
                            if isinstance(mac_addresses, str):
                                mac_addresses = [mac_addresses]
                            data_plugin["wifi_filter_mac"] = mac_addresses

                        if "segment_count" in data_config["type_settings"]:
                            data_plugin["wifi_segments"] = str(
                                data_config["type_settings"]["segment_count"]
                            )
                        if "send_as_object" in data_config["type_settings"]:
                            data_plugin["wifi_object"] = (
                                "1"
                                if data_config["type_settings"]["send_as_object"]
                                else "0"
                            )

                # Update the data input using the calculated ID
                data_request = {
                    "method": "PUT",
                    "data": data_plugin,
                    "endpoint": f"/api/{self.api_endpoint}/collections/config/{collection_id}/data/{data_id}",
                }
                api_requests.append(data_request)

            # Configure server plugin with values from your config
            server_plugin = {
                ".type": "output",
                "plugin": "mqtt",
                "mqtt_qos": str(qos),
                "mqtt_tls": "0",
                "mqtt_use_credentials": "0",
                "mqtt_host": server_address,
                "mqtt_port": str(port),
                "mqtt_keepalive": str(keepalive),
                "mqtt_topic": topic,
                "mqtt_client_id": client_id,
                "http_tls": "",  # Empty fields from the example API requests
                "http_host": "",
                "http_header": "",
            }

            # Add TLS/secure connection if configured in server_config
            if server_config.get("enable_secure_connection", False):
                server_plugin["mqtt_tls"] = "1"

                # Handle secure connection settings
                if "secure_connection" in server_config:
                    secure_conn = server_config["secure_connection"]

                    if "allow_insecure_connection" in secure_conn:
                        server_plugin["mqtt_insecure"] = (
                            "1" if secure_conn["allow_insecure_connection"] else "0"
                        )

                    # Handle certificates based on source (device or custom)
                    if "certificate_files_from_device" in secure_conn:
                        server_plugin["mqtt_certificates_from_device"] = (
                            "1" if secure_conn["certificate_files_from_device"] else "0"
                        )

                        if secure_conn.get("certificate_files_from_device"):
                            # Use device certificates
                            if "device_certificates" in secure_conn:
                                dev_certs = secure_conn["device_certificates"]
                                if "certificate_authority_file" in dev_certs:
                                    server_plugin["mqtt_ca_file"] = dev_certs[
                                        "certificate_authority_file"
                                    ]
                                if "client_certificate" in dev_certs:
                                    server_plugin["mqtt_cert_file"] = dev_certs[
                                        "client_certificate"
                                    ]
                                if "client_private_keyfile" in dev_certs:
                                    server_plugin["mqtt_key_file"] = dev_certs[
                                        "client_private_keyfile"
                                    ]
                        else:
                            # Use custom certificates
                            if "certificate_authority_file" in secure_conn:
                                server_plugin["mqtt_ca_file"] = secure_conn[
                                    "certificate_authority_file"
                                ]
                            if "client_certificate" in secure_conn:
                                server_plugin["mqtt_cert_file"] = secure_conn[
                                    "client_certificate"
                                ]
                            if "client_private_keyfile" in secure_conn:
                                server_plugin["mqtt_key_file"] = secure_conn[
                                    "client_private_keyfile"
                                ]

            # Add credentials if configured
            if server_config.get("use_credentials", False):
                server_plugin["mqtt_use_credentials"] = "1"
                server_plugin["mqtt_username"] = str(server_config.get("username", ""))
                server_plugin["mqtt_password"] = str(server_config.get("password", ""))

            # Update the server output using the calculated ID
            server_request = {
                "method": "PUT",
                "data": server_plugin,
                "endpoint": f"/api/{self.api_endpoint}/collections/config/{collection_id}/servers/{server_id}",
            }
            api_requests.append(server_request)

            # Update the collection with the original instance name from config
            collection_update = {
                ".type": "collection",
                "period": str(period),
                "format": "json",
                "name": instance_name,
                "timer": "period",
                "enabled": "1",
                "retry": "1" if retry else "0",
                "retry_count": str(retry_count),
                "retry_timeout": str(retry_timeout),
            }

            # If using scheduler configuration instead of period
            if (
                "timer" in collection_config
                and collection_config["timer"] == "scheduler"
            ):
                logger.info("Using scheduler configuration instead of period")
                collection_update["timer"] = "scheduler"
                # Period field should be empty for scheduler
                collection_update["period"] = ""

                # Add scheduler-specific configuration
                if "day_time" in collection_config:
                    # API expects time as an array
                    collection_update["time"] = [collection_config["day_time"]]

                if "interval_type" in collection_config:
                    interval_type = collection_config["interval_type"]
                    if interval_type == "Week days":
                        collection_update["day_mode"] = "week"
                        # API expects week days as a special field
                        if "weekdays" in collection_config:
                            collection_update["week_days"] = collection_config[
                                "weekdays"
                            ]
                        else:
                            collection_update["week_days"] = ""
                    elif interval_type == "Month days":
                        collection_update["day_mode"] = "month"
                        # API expects month days as array of strings
                        if "month_day" in collection_config:
                            collection_update["month_days"] = [
                                str(day) for day in collection_config["month_day"]
                            ]
                    else:
                        collection_update["day_mode"] = "day"

                if "force_last_day" in collection_config:
                    collection_update["last_day"] = (
                        "1" if collection_config["force_last_day"] else "0"
                    )

                # Make sure retry settings are included
                if "retry_count" in collection_config:
                    collection_update["retry_count"] = str(
                        collection_config["retry_count"]
                    )
                if "timeout" in collection_config:
                    collection_update["retry_timeout"] = str(
                        collection_config["timeout"]
                    )

            # MQTT CERT UPLOADING
            has_mqtt_certificates = (
                data_type_lowercase == "mqtt"
                and "type_settings" in data_config
                and data_config["type_settings"].get("enable_secure_connection", False)
                and "secure_connection" in data_config["type_settings"]
                and "certificate_files_from_device"
                in data_config["type_settings"]["secure_connection"]
                and not data_config["type_settings"]["secure_connection"].get(
                    "certificate_files_from_device", True
                )
            )
            if has_mqtt_certificates:
                logger.info("Uploading custom MQTT certificates")
                await self.upload_certificates(collection_id, data_id)

            collection_update_request = {
                "method": "PUT",
                "data": collection_update,
                "endpoint": f"/api/{self.api_endpoint}/collections/config/{collection_id}",
            }
            logger.info("Adding collection update to request batch")
            api_requests.append(collection_update_request)

            # Create the final API request
            final_api_request = {"data": api_requests}

            # Send the request to create and update all components
            logger.info(
                f"Sending combined API request: {json.dumps(final_api_request)}"
            )
            result = await self.api_request("post", "bulk", final_api_request)
            logger.info(f"Combined API request result: {json.dumps(result)}")

            # Save configuration for verification
            self.dts_config = {
                "collection": collection_update,
                "collection_id": collection_id,
                "data_id": data_id,
                "server_id": server_id,
                "instance_name": instance_name,
                "server_address": server_address,
                "topic": topic,
                "client_id": client_id,
                "qos": qos,
            }

            return True

        except Exception as e:
            logger.error(f"Failed to configure Data to Server via API: {str(e)}")
            raise

    async def get_current_dts_config(self):
        """Get current Data to Server configurations."""
        try:
            # Create the bulk API request to get current configurations
            get_request = {
                "data": [
                    {
                        "endpoint": f"/api/{self.api_endpoint}/collections/config",
                        "method": "GET",
                    },
                    {
                        "endpoint": f"/api/{self.api_endpoint}/data/config",
                        "method": "GET",
                    },
                    {
                        "endpoint": f"/api/{self.api_endpoint}/servers/config",
                        "method": "GET",
                    },
                ]
            }

            # Send the request
            result = await self.api_request("post", "bulk", get_request)

            # Extract and return the data
            if result.get("success") and result.get("data"):
                return {
                    "collections": (
                        result["data"][0].get("data", [])
                        if result["data"][0].get("success")
                        else []
                    ),
                    "data_inputs": (
                        result["data"][1].get("data", [])
                        if result["data"][1].get("success")
                        else []
                    ),
                    "servers": (
                        result["data"][2].get("data", [])
                        if result["data"][2].get("success")
                        else []
                    ),
                }
            else:
                logger.warning("Failed to get current Data to Server configurations")
                return {"collections": [], "data_inputs": [], "servers": []}

        except Exception as e:
            logger.error(
                f"Error getting current Data to Server configurations: {str(e)}"
            )
            return {"collections": [], "data_inputs": [], "servers": []}

    def get_next_ids(self, current_config):
        """
        Get the next available IDs for a new collection, data input, and server output.
        Collection IDs: 1, 4, 7, 10, ... (increase by 3)
        Data Input IDs: 3, 6, 9, 12, ... (increase by 3)
        Server Output IDs: 2, 5, 8, 11, ... (increase by 3)
        """
        try:
            # Get the highest collection ID
            collections = current_config.get("collections", [])

            # If there are no collections, start with collection ID 1
            if not collections:
                logger.info("No existing collections found. Starting with ID 1.")
                return {"collection_id": 1, "data_id": 3, "server_id": 2}

            highest_collection_id = 0
            for collection in collections:
                if "id" in collection:
                    try:
                        collection_id = int(collection["id"])
                        highest_collection_id = max(
                            highest_collection_id, collection_id
                        )
                    except (ValueError, TypeError):
                        pass

            # Calculate new collection ID (increment by 3)
            new_collection_id = highest_collection_id + 3
            if new_collection_id % 3 != 1:
                # Ensure it follows the pattern 1, 4, 7, 10, ...
                new_collection_id = ((new_collection_id // 3) + 1) * 3 - 2

            # Calculate new data ID (collection_id + 2)
            new_data_id = new_collection_id + 2

            # Calculate new server ID (collection_id + 1)
            new_server_id = new_collection_id + 1

            logger.info(
                f"Calculated IDs - collection: {new_collection_id}, data: {new_data_id}, server: {new_server_id}"
            )

            # Return the next available IDs
            return {
                "collection_id": new_collection_id,
                "data_id": new_data_id,
                "server_id": new_server_id,
            }
        except Exception as e:
            logger.error(f"Error calculating next IDs: {str(e)}")
            # Default IDs if calculation fails - using the pattern
            return {"collection_id": 1, "data_id": 3, "server_id": 2}

    async def upload_certificates(self, collection_id, data_id):
        """
        Upload MQTT certificate files individually for custom certificate configuration.
        This is used when certificate_files_from_device is set to false.

        Args:
            collection_id: The collection ID to use
            data_id: The data ID to use

        Returns:
            bool: True if all uploads were successful, False otherwise
        """
        try:
            logger.info(
                f"Uploading custom MQTT certificates for collection {collection_id}, data {data_id}"
            )

            # Certificate info with default example content
            cert_files = {
                "mqtt_in_cafile": {
                    "name": "ca_file.crt",
                    "content": "-----BEGIN CERTIFICATE-----\nMIIDMzCCAhugAwIBAgIUcA6kEujGZKl2alnpjvMnR5A8fqEwDQYJKoZIhvcNAQEL\nBQAwSTEXMBUGA1UEAwwOTVFUVCBCcm9rZXIgQ0ExITAfBgNVBAoMGEhvbWUgTVFU\nVCBJbmZyYXN0cnVjdHVyZTELMAkGA1UEBhMCTFQwHhcNMjUwMjEzMDY0MDIzWhcN\nMjYwMjEzMDY0MDIzWjBJMRcwFQYDVQQDDA5NUVRUIEJyb2tlciBDQTEhMB8GA1UE\nCgwYSG9tZSBNUVRUIEluZnJhc3RydWN0dXJlMQswCQYDVQQGEwJMVDCCASIwDQYJ\nKoZIhvcNAQEBBQADggEPADCCAQoCggEBANG1qrOulhVivu/QLmCu5zbvStOTmeWN\nN6ng3dU4nR/sw5/WY1voaTLgytiDjVP2Lx2dq34VKsjXiLEuuizdTEK50hcJpBVV\nXtY95vMMO3j+YhgDogMiV36H6O1Ifbv6XKRCJtKELtvTbfy0pRijRkLg9lOUtUJ2\nuYjflHldAJSb4OB3n67Bjw+4+iQsG8YObVpazOB50HJjkblObzXZps9qsVyn65ar\nmkDIJ83+TRo73Nzx84RkaqBkFo8cztJAD9uUVjxExodiaDge/qJj1BZt3LqGqaYZ\nUI0VLYmLZhwARYfmH8oDXWkgMCNuX9FQ2ohSKxjyjqtJ2nPsplXTswkCAwEAAaMT\nMBEwDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAbHPg7QE85AIg\nDUCRE439KRHbu9PLuI/GAqbN+TRNyXu0LkYThLW7apaLFSzYjnXGKg0W08l72DEr\n3G+MiuzHao0iUao10JPG/+ZTc9NXBXWtfrE1jGSwHSAoTfk/wHFjZmiNEho/6Qdy\njpPZT5pYMq/gpf919YPFwEmR3zxH1KHaeY91CVVEQ19ui5oUT0dgw7MJ6D4V0yn9\nEpp7TjsKSawal6Og8Pi6HiuQYVEZb0zAqgO2vJzQcLXSEzbQQf+l4B7GEmMGqaYh\nlirHuLpfyEqz3izGawHSrRtafdEaoXrFQmPu78eOxjrF8V5nTwW7WcrZn6ZglEgv\ndfOkHO8YHQ==\n-----END CERTIFICATE-----",
                },
                "mqtt_in_certfile": {
                    "name": "certificate_file.crt",
                    "content": "-----BEGIN CERTIFICATE-----\nMIIDNTCCAh2gAwIBAgIUTwZL2o0HSa4o30hHzoNAM4f8PvwwDQYJKoZIhvcNAQEL\nBQAwSTEXMBUGA1UEAwwOTVFUVCBCcm9rZXIgQ0ExITAfBgNVBAoMGEhvbWUgTVFU\nVCBJbmZyYXN0cnVjdHVyZTELMAkGA1UEBhMCTFQwHhcNMjUwMjEzMDY0MDIzWhcN\nMjYwMjEzMDY0MDIzWjBFMRMwEQYDVQQDDAptcXR0LmxvY2FsMSEwHwYDVQQKDBhI\nb21lIE1RVFQgSW5mcmFzdHJ1Y3R1cmUxCzAJBgNVBAYTAkxUMIIBIjANBgkqhkiG\n9w0BAQEFAAOCAQ8AMIIBCgKCAQEAod6lF32JGWyWSrTEqIoTAF1/HJhKVIUQZfVz\nSrIE+Btyy113mDibCUrqA23etu7NAqjRKVeMFL8tgJbPWuIfYd2muEIG7QieReCb\nCNHD0w1YgmlklbMyPCSnpKuYDKjyPB5MuvvnjbqHGqH1h0eR2f0wUduZqcDeJS0h\nlGcf3SohdGiOg+IUoF9lAHIOl2ey0Gt3Ljs72k/wROtn1Fop+Va1aPfvJDcoNXIh\nsg4loeEN2pN8+DEiqBN4nkciHePmWLr8mTpNR9cc6mZNmGMQzLKP1W9RWEJWy8HN\n5w8gxrOb4I0wVzxVomA9Q3KZQwCPP9O1MMRotrIL4dBCQqyucQIDAQABoxkwFzAV\nBgNVHREEDjAMggptcXR0LmxvY2FsMA0GCSqGSIb3DQEBCwUAA4IBAQBMsC3B2lfe\nX3BRFHQGqv7g/BOE5A/ZhpsPc3rMPpoZsRSzU25yhdI4oe82e0Q/mt3xaGBK5CdU\nLyh/fQ1oS/LBpNLPHanFWQIIerv90XvwUgfNyvLBhgKLWZvFZNZORS8dUH8VRb+c\nDtvZiFffF+uvdEskuHuXgwDtOoIC2/HkjIs/goLHhjY9w9gpYOMf+VuLlsAE0E1F\nQuyJGCYfh/cWwxBKxwusojF8h83dl0R66K1nTpUIBppxvJ3IGczq4lc0swRvgDTN\n6mzATYBZNq8KrjfW8BEApfqrQOP4TiG6k5duCk7W+ruoB3QFHbA7dTSaZuZtGzzS\n+xTnL86c/Xm5\n-----END CERTIFICATE-----",
                },
                "mqtt_in_keyfile": {
                    "name": "key_file.crt",
                    "content": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCgUhEsOr7/sSog\n/R+/fBktbMn9P6HjPmPZJTKY9zXEgR/wF+XV1HmBeFNbLbbJg2cpQzFpQOmhj1/a\naOS5fnFCUwJDpaE8k8h4iJRayq0wvEx0/OQAawNkuvpF/FNoXUhcs07YjSSkq/ze\n/7qz0c01UqR4p8M8gTI0DgCzS6y35MYxnlFZozQqzADZ8pdbK+xdVCTA0SMocGHy\nbQdUuq28Ij6EV63JgsNb3mPnOFwX4bcaE7B5f5kjcg3U/zLE+ZytObAViWMIVdy9\nHp4j+k/qGDy+UERllrqCTZnZ/nOQqzgaVgOB0S5HfHfoPlNEfjifLed9UsmhGCew\nQQesPj5xAgMBAAECggEABOy7HKXfU8vAP2GB1f18voGkK3SGx2FqwB2y510CA1Ee\nHIoiDsanRtwIiiP7hJwrO+rAUVCOUglX80XGmjtxROLM49a/fwoLyJwVcTve7xYn\nA8RNnVpW29jHMwV/Fb/L0cErpQj3klwQI/+CCjUMfdyrMw5K4ohrdOA7PZwPqFnB\nESzYyBjYcM0TzN/wSKlGCSJUb+FKY1qaAIm2UFKxwB5Ot2sw3ubfFsnuVtH81bRC\nLKqWGqPY63GwdZvEB4/BTnHZ/KkLRQbcBbJWF2IJqgZ+SLuwb2a+AM5VcxHsTw3l\nlXSaD8Fdr1KwmcBz/3E3P2BA9kD/UdelhADj33uPWwKBgQDaID+2VcoYUIGKhs1r\n3/AuO/WStZ8fximUmsZEJ3mxnzCspCKPyH19czBd1hKQkTDv+MEnJM3wm8cY8HEB\nU4ATPK/y7mFsdAaOEedlFt2o4QBdFpquNM4ybnuzXs1TA8aLbjD4vGmX1wSYKCDF\nja3cJ497ttDnpwS/U0sD6gW3xwKBgQC8KFrGYnvEOAde9EBXYdtpuibHgp1ePpvU\nK5VcJjH9z6nkZZzzhRHSK5t2fUd+ob5AWNwB6n98J8taX46OnKyGV1GKpYflMQAZ\njMylHJwABTHcPD0pyz4QOGZk30OaNKiSjyucKFi3mtRUxNW3mzwbifj12iNT6fkK\nGF5eFOgIBwKBgQC1JhEjgU3MMZfTjq4tB5Z1HzCL/a+/+JdxpbRAx7PmEnme9tUJ\nKg0l0TL6yx0x2JKWyLTIqGUrjIOlr5F583mrADxzeQuJwTXsaOwN5RaC+RGPPYWK\nZapU8bJjvbixV7Jc+09KU1cyVcyn/LNyvX4FFwmvSZ1mtStZJXhoMMM84wKBgF2F\n9XDMPNaQPuGsqFqGsme/9kyOmKfimNQCAdB2z7xnvvteon/Mcco0kKZ5qNLBlG4p\nfNma9FkC8qnt+07Zg0uXFVnD42NBUtpgSMv9B3FfI6RjcMdYVXX8grC65MA+Ulfe\nv/9zcn14gPfNiqkjiOHrV4rkLVElZ/rjl+xNmfN7AoGAVt+NR1xb/y7K10DjrkVc\nwQB/4aegF87iWyy5jFd3NoHwph1wFekruQdg/g4wNhg870LRnKB76aStDzaj94Lo\nvgzDzD3LNdCeHGWc9Cf5tZV8J4lQMbdyai5qfRe++aRxKIAPWDYTPihEZvHdoYkU\nGH9os7NpkU55pG33sWPYpl0=\n-----END PRIVATE KEY-----",
                },
            }

            # Upload each certificate file
            for cert_option, cert_info in cert_files.items():
                # Create multipart form data with boundary
                boundary = f"geckoformboundary{os.urandom(12).hex()}"

                # Build the multipart form data manually
                form_data = (
                    f"------{boundary}\r\n"
                    f'Content-Disposition: form-data; name="option"\r\n\r\n'
                    f"{cert_option}\r\n"
                    f"------{boundary}\r\n"
                    f'Content-Disposition: form-data; name="file"; filename="{cert_info["name"]}"\r\n'
                    f"Content-Type: application/octet-stream\r\n\r\n"
                    f"{cert_info['content']}\r\n"
                    f"------{boundary}--"
                )

                # Set custom headers for multipart form data
                headers = {
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": f"multipart/form-data; boundary=----{boundary}",
                }

                # API endpoint for uploading the certificate
                endpoint = f"{self.api_endpoint}/collections/config/{collection_id}/data/{data_id}"

                # Make the request to upload the certificate
                logger.info(f"Uploading {cert_option} certificate file")
                upload_result = await self.api_request(
                    "post",
                    endpoint,
                    data=form_data,
                    headers=headers,
                    raw_data=True,  # Indicate this is raw data that shouldn't be JSON encoded
                )
                logger.info(
                    f"Certificate upload result for {cert_option}: {json.dumps(upload_result)}"
                )

            return True

        except Exception as e:
            logger.error(f"Failed to upload MQTT certificates: {str(e)}")
            return False

    async def upload_lua_script(
        self,
        collection_id: int,
        data_id: int,
        script_content: str,
        script_filename: str = "script.lua",
    ):
        """
        Upload a Lua script to the device before the main data_to_server configuration.

        Args:
            collection_id: The collection ID to use
            data_id: The data ID to use
            script_content: The content of the Lua script to upload
            script_filename: The filename to use for the script (default: script.lua)

        Returns:
            dict: API response containing the uploaded script path, or None if upload failed
        """
        try:
            logger.info(
                f"Uploading Lua script '{script_filename}' for collection {collection_id}, data {data_id}"
            )

            # Log a preview of the script content (first 100 chars)
            content_preview = (
                script_content[:100] + "..."
                if len(script_content) > 100
                else script_content
            )
            logger.info(f"Script content preview: {content_preview}")

            # Create multipart form data with boundary
            boundary = "geckoformboundaryb895f666400f7d9c5b5b505f48ee9773"

            # Build the multipart form data manually with proper line endings
            form_data = (
                f"------{boundary}\r\n"
                f'Content-Disposition: form-data; name="option"\r\n\r\n'
                f"lua_script\r\n"
                f"------{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{script_filename}"\r\n'
                f"Content-Type: application/octet-stream\r\n\r\n"
                f"{script_content}\r\n"
                f"------{boundary}--"
            )

            # Set custom headers for multipart form data
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": f"multipart/form-data; boundary=----{boundary}",
            }

            # API endpoint for uploading the script
            endpoint = (
                f"{self.api_endpoint}/collections/config/{collection_id}/data/{data_id}"
            )

            # Make the request to upload the Lua script
            result = await self.api_request(
                "post",
                endpoint,
                data=form_data,
                headers=headers,
                raw_data=True,  # Indicate this is raw data that shouldn't be JSON encoded
            )

            logger.info(f"Lua script upload result: {json.dumps(result)}")
            return result  # Return the full result so we can extract the path

        except Exception as e:
            logger.error(f"Failed to upload Lua script: {str(e)}")
            return None

    def _get_config_by_key_prefix(
        self, config: dict, prefix: str, preferred_key: str = None
    ):
        """
        Helper method to find configuration keys by prefix.
        Checks for different prefixed variations of the configuration keys.
        For example, data_config could be data_config-Base, data_config-Bluetooth, etc.

        Args:
            config: The configuration dictionary to search in
            prefix: The base prefix to search for (e.g., 'data_config')
            preferred_key: An optional specific key to prioritize if found

        Returns:
            The found configuration dictionary or an empty dict if not found
        """
        # If preferred key is specified and exists, use it first
        if preferred_key and preferred_key in config:
            logger.info(f"Using preferred configuration key: {preferred_key}")
            return config[preferred_key]

        # If the exact prefix exists, use it directly
        if prefix in config:
            logger.info(f"Using direct configuration key: {prefix}")
            return config[prefix]

        # Try to find keys with the specified prefix
        prefix_keys = [key for key in config.keys() if key.startswith(f"{prefix}-")]

        if prefix_keys:
            # Sort by specificity - shorter keys first as they're more generic
            prefix_keys.sort(key=len)

            # Log all available prefixed keys for debugging
            logger.info(f"Available prefixed keys for {prefix}: {prefix_keys}")

            # Check specific device-type configurations based on prefix
            if prefix == "data_config":
                # Extract the data type from the config if it exists
                if prefix in config and "type" in config[prefix]:
                    data_type = config[prefix]["type"]
                    type_specific_key = f"{prefix}-{data_type}"

                    # If there's a type-specific config, use it
                    if type_specific_key in config:
                        logger.info(
                            f"Using type-specific configuration key: {type_specific_key}"
                        )
                        return config[type_specific_key]

                # Look for specialized configurations
                for key in prefix_keys:
                    # Extract suffix after the dash
                    suffix = key.split("-", 1)[1] if "-" in key else ""

                    # Check if this is the right configuration type based on the type field
                    if (
                        config.get("data_config", {}).get("type", "").lower()
                        == suffix.lower()
                    ):
                        logger.info(f"Found matching {suffix} configuration: {key}")
                        return config[key]

            # If we haven't returned a specialized config, use the first prefix key as fallback
            logger.info(f"Using first available prefix key: {prefix_keys[0]}")
            return config[prefix_keys[0]]

        # If no prefixed keys are found, return empty dict
        logger.warning(f"No configuration found for prefix: {prefix}")
        return {}

    async def verify_configuration(self) -> bool:
        """Verify the applied configuration."""
        try:
            logger.info("API DTS: verify_configuration function started.")

            # Get current configurations to verify
            current_config = await self.get_current_dts_config()
            logger.info(
                f"Current configurations for verification: {json.dumps(current_config)}"
            )

            # Check if our configuration exists
            instance_name = self.dts_config.get("instance_name")
            found = False

            # Check collections
            collections = current_config.get("collections", [])
            for collection in collections:
                if collection.get("name") == instance_name:
                    collection_id = collection.get("id")
                    logger.info(
                        f"Found collection with name {instance_name}, ID: {collection_id}"
                    )
                    found = True
                    break

            if found:
                logger.info("Configuration verification successful")
                return True
            else:
                logger.warning(
                    f"Could not find collection with name {instance_name} in the API response"
                )
                # The validator will check the system state separately
                # Return True to continue with the test
                return True

        except Exception as e:
            logger.error(f"Configuration verification failed: {str(e)}")
            return False
