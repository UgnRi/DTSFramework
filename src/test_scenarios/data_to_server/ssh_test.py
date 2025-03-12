from src.test_scenarios.base_scenario import BaseTestScenario
from src.backend.ssh_client import SSHClient
from src.test_scenarios.base_ssh_test import BaseSSHTest
from src.test_scenarios.data_to_server.api_test import DataToServerAPITest
from src.utils.logger import setup_logger
from typing import Dict, Any, List, Union, Optional
import re

logger = setup_logger()


class DataToServerSSHTest(BaseSSHTest):
    """SSH Test implementation for Data to Server configuration."""

    def __init__(self, device_config: Dict[str, Any], scenario_config=None):
        super().__init__(device_config=device_config, scenario_config=scenario_config)
        self.section_ids = {
            "collection": None,  # Will be dynamically assigned
            "output": None,  # Will be dynamically assigned
            "input": None,  # Will be dynamically assigned
        }

    async def run(self):
        """Run Data to Server SSH test with dynamic section detection."""
        try:
            logger.info("SSH DTS: Run function started.")
            # Connect to device via SSH
            await self.ssh_client.connect()

            # Identify existing sections or create new ones
            await self._identify_sections()

            # Configure Data to Server
            await self.configure_dts()

            # Verify configuration
            verification_result = await self._verify_configuration()

            # Cleanup configuration after successful validation
            # if verification_result:
            #   await self._cleanup_configuration()

            # Return success result
            return {
                "success": True,
                "details": "Data to Server configured successfully via SSH",
                "verification": verification_result,
            }

        except Exception as e:
            logger.error(f"Data to Server SSH test failed: {str(e)}")
            return {"success": False, "details": str(e)}
        finally:
            await self.ssh_client.close()

    async def _identify_sections(self):
        """Identify existing sections or determine the next available section IDs."""
        try:
            # Get all existing sections
            result = await self.ssh_client.execute_command("uci show data_sender")
            lines = result.strip().split("\n")

            # Extract section IDs
            collection_ids = []
            output_ids = []
            input_ids = []

            for line in lines:
                if "=collection" in line:
                    section_id = line.split("=")[0].split(".")[1]
                    collection_ids.append(int(section_id))
                elif "=output" in line:
                    section_id = line.split("=")[0].split(".")[1]
                    output_ids.append(int(section_id))
                elif "=input" in line:
                    section_id = line.split("=")[0].split(".")[1]
                    input_ids.append(int(section_id))

            # Use existing instance or get next available ID
            config = self._extract_config()
            instance_name = config.get("instanceName", "test_instance")

            # Try to find existing sections with matching name
            for line in lines:
                if f"data_sender.*.name='{instance_name}'" in line:
                    # Extract the ID and type from the line
                    parts = line.split("=")[0].split(".")
                    if len(parts) >= 2:
                        section_id = parts[1]
                        section_type = await self.ssh_client.execute_command(
                            f"uci get data_sender.{section_id}"
                        )
                        section_type = section_type.strip()

                        if section_type == "collection":
                            self.section_ids["collection"] = section_id
                        elif section_type == "output":
                            self.section_ids["output"] = section_id
                        elif section_type == "input":
                            self.section_ids["input"] = section_id

            # If no existing sections found, use the next available IDs
            if self.section_ids["collection"] is None:
                next_id = 1 if not collection_ids else max(collection_ids) + 1
                self.section_ids["collection"] = str(next_id)

            if self.section_ids["output"] is None:
                next_id = 2 if not output_ids else max(output_ids) + 1
                self.section_ids["output"] = str(next_id)

            if self.section_ids["input"] is None:
                next_id = 3 if not input_ids else max(input_ids) + 1
                self.section_ids["input"] = str(next_id)

            # Create sections if they don't exist
            for section_type, section_id in self.section_ids.items():
                result = await self.ssh_client.execute_command(
                    f'uci get data_sender.{section_id} 2>/dev/null || echo "not_found"'
                )
                if "not_found" in result:
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{section_id}={section_type}"
                    )

            logger.info(
                f"Using section IDs: collection={self.section_ids['collection']}, output={self.section_ids['output']}, input={self.section_ids['input']}"
            )

        except Exception as e:
            logger.error(f"Failed to identify sections: {str(e)}")
            # Use default values if identification fails
            self.section_ids = {"collection": "1", "output": "2", "input": "3"}
            logger.info(f"Using default section IDs: {self.section_ids}")

    def _extract_config(self) -> Dict[str, Any]:
        """Extract configuration with support for both nested and flat structures."""
        if not self.scenario_config:
            return {}

        # Check if the config is nested under 'config' key
        if "config" in self.scenario_config and isinstance(
            self.scenario_config["config"], dict
        ):
            return self.scenario_config["config"]

        # If not nested, use the scenario_config directly
        return self.scenario_config

    async def _get_next_sender_id(self):
        """Determine the next available sender_id for new Data to Server clients."""
        try:
            # Get all existing collection sections
            result = await self.ssh_client.execute_command(
                'uci show data_sender | grep "=collection"'
            )
            lines = result.strip().split("\n")

            # Find the highest existing sender_id
            highest_id = 0
            for line in lines:
                section_id = line.split("=")[0].split(".")[1]
                # Get sender_id for this collection if it exists
                sender_id_result = await self.ssh_client.execute_command(
                    f'uci get data_sender.{section_id}.sender_id 2>/dev/null || echo "0"'
                )
                try:
                    sender_id = int(sender_id_result.strip("'\""))
                    highest_id = max(highest_id, sender_id)
                except ValueError:
                    # Skip if not a valid integer
                    pass

            # Return the next available ID (highest + 1)
            return highest_id + 1

        except Exception as e:
            logger.error(f"Failed to determine next sender_id: {str(e)}")
            # Fallback to section ID based approach
            try:
                return int(self.section_ids["collection"])
            except ValueError:
                # Last resort fallback
                return 1

    async def configure_dts(self):
        """Configure Data to Server via SSH/UCI with dynamic section handling."""
        try:
            logger.info("SSH DTS: configure_dts function started.")

            # Extract configuration
            config = self._extract_config()

            # Set instance name
            instance_name = config.get("instanceName", "test_instance")
            logger.info(f"Instance name: {instance_name}")

            # Configure the main sections
            # For input, use 'input' as name to match WebUI configuration
            await self.ssh_client.execute_command(
                f'uci set data_sender.{self.section_ids["input"]}.name="input{self.section_ids["input"]}"'
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.{self.section_ids["output"]}.name="{instance_name}_output"'
            )

            # Enable the data collection
            await self.ssh_client.execute_command(
                f'uci set data_sender.{self.section_ids["collection"]}.enabled="1"'
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.{self.section_ids["collection"]}.name="{instance_name}"'
            )

            # Set collection format to json
            await self.ssh_client.execute_command(
                f'uci set data_sender.{self.section_ids["collection"]}.format="json"'
            )

            # Set up the collection->input->output chain
            await self.ssh_client.execute_command(
                f'uci set data_sender.{self.section_ids["collection"]}.input="{self.section_ids["input"]}"'
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.{self.section_ids["collection"]}.output="{self.section_ids["output"]}"'
            )

            # Configure collection method
            collection_config_scheduler = config.get("collection_config-scheduler", {})
            collection_config_period = config.get("collection_config-period", {})
            collection_config = config.get("collection_config", {})

            if (
                collection_config_scheduler
                and "day_time" in collection_config_scheduler
            ):
                logger.info("Using dedicated scheduler configuration...")
                await self._configure_scheduler(collection_config_scheduler)
            elif collection_config_period and "period" in collection_config_period:
                logger.info("Using dedicated period configuration...")
                await self._configure_period(collection_config_period)
            elif collection_config:
                if collection_config.get("timer") == "scheduler":
                    logger.info("Using legacy scheduler configuration...")
                    await self._configure_scheduler(collection_config)
                elif "period" in collection_config:
                    logger.info("Using legacy period configuration...")
                    await self._configure_period(collection_config)
                else:
                    logger.warning(
                        "No valid collection timing found in config, using defaults"
                    )
                    await self._configure_period({"period": 60, "retry": False})

            # Configure data collection
            data_config = config.get("data_config", {})
            if data_config:
                logger.info(
                    f"Configuring data collection with type: {data_config.get('type', 'unknown')}"
                )
                await self._configure_data_collection(data_config)
            else:
                logger.warning("No data_config found, using defaults")
                await self._configure_data_collection(
                    {
                        "type": "Base",
                        "format_type": "JSON",
                        "values": ["time", "local_time", "fw", "name", "id"],
                    }
                )

            next_sender_id = await self._get_next_sender_id()
            await self.ssh_client.execute_command(
                f'uci set data_sender.{self.section_ids["collection"]}.sender_id="{next_sender_id}"'
            )
            logger.info(
                f"Assigned sender_id {next_sender_id} to collection {self.section_ids['collection']}"
            )

            # Configure server settings
            server_config = config.get("server_config", {})
            if server_config:
                logger.info(
                    f"Configuring server with address: {server_config.get('server_address', 'unknown')}"
                )
                await self._configure_server(server_config)
            else:
                logger.warning("No server_config found in configuration")

            # Apply changes
            await self._apply_changes()

        except Exception as e:
            logger.error(f"Failed to configure Data to Server via SSH: {str(e)}")
            raise

    async def _configure_data_collection(self, data_config):
        """Configure data collection settings via UCI with dynamic section ID."""
        try:
            logger.info("SSH DTS: _configure_data_collection function started.")
            input_id = self.section_ids["input"]

            # Set data source type for input - always use lowercase for plugin name
            data_type = data_config.get("type", "Base").lower()
            if data_type == "wifi scanner":
                await self.ssh_client.execute_command(
                    f"uci set data_sender.{input_id}.plugin='wifiscan'"
                )
            if data_type == "modbus alarms":
                await self.ssh_client.execute_command(
                    f"uci set data_sender.{input_id}.plugin='modbus_alarm'"
                )
            if data_type == "mnf info":
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{input_id}.plugin="mnfinfo"'
                )
            elif data_type == "impulse counter":
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{input_id}.plugin="impulse_counter"'
                )
            elif data_type == "mobile usage":
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{input_id}.plugin="mdcollect"'
                )
            else:
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{input_id}.plugin="{data_type}"'
                )

            # Configure type-specific settings
            type_settings = data_config.get("type_settings", {})
            for key, value in type_settings.items():
                # Skip impulse_counter_pin for impulse counter plugin - we'll handle it separately
                if (
                    data_type.lower() == "impulse counter"
                    or "mobile usage"
                    or "mnf info"
                    or "modbus"
                    or "wifi scanner"
                ):
                    continue

                # Handle boolean values
                if isinstance(value, bool):
                    value = 1 if value else 0
                # Handle list values
                elif isinstance(value, list):
                    value = " ".join(map(str, value))

                await self.ssh_client.execute_command(
                    f'uci set data_sender.{input_id}.{key}="{value}"'
                )

            # Set format type for input (always lowercase)
            format_type = data_config.get("format_type", "JSON").lower()
            await self.ssh_client.execute_command(
                f'uci set data_sender.{input_id}.format="{format_type}"'
            )

            # Configure values to collect using add_list for WebUI compatibility
            values = data_config.get("values", [])
            logger.info(f" VALUES: {values}")
            if values:
                # Delete existing members if any
                await self.ssh_client.execute_command(
                    f"uci del data_sender.{input_id}.members"
                )
                # Add each value as a separate list item (quoted)
                for value in values:
                    await self.ssh_client.execute_command(
                        f"uci add_list data_sender.{input_id}.members='{value}'"
                    )

            # Handle MQTT-specific configuration if type is MQTT
            if data_type.lower() == "mqtt":
                mqtt_settings = type_settings
                if mqtt_settings:
                    # Basic MQTT settings
                    await self.ssh_client.execute_command(
                        f'uci set data_sender.{input_id}.mqtt_in_host="{mqtt_settings.get("server_address", "localhost")}"'
                    )
                    await self.ssh_client.execute_command(
                        f'uci set data_sender.{input_id}.mqtt_in_port="{mqtt_settings.get("port", 1338)}"'
                    )  # 1338 to match WebUI
                    await self.ssh_client.execute_command(
                        f'uci set data_sender.{input_id}.mqtt_in_topic="{mqtt_settings.get("topic", "test")}"'
                    )
                    await self.ssh_client.execute_command(
                        f'uci set data_sender.{input_id}.mqtt_in_client_id="{mqtt_settings.get("client_id", "client")}"'
                    )
                    await self.ssh_client.execute_command(
                        f'uci set data_sender.{input_id}.mqtt_in_qos="{mqtt_settings.get("QoS", 0)}"'
                    )
                    await self.ssh_client.execute_command(
                        f'uci set data_sender.{input_id}.mqtt_in_keepalive="{mqtt_settings.get("keepalive", 60)}"'
                    )

                    # Credentials
                    if "username" in mqtt_settings and "password" in mqtt_settings:
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.{input_id}.mqtt_in_username="{mqtt_settings["username"]}"'
                        )
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.{input_id}.mqtt_in_password="{mqtt_settings["password"]}"'
                        )

                    # TLS/SSL settings
                    if mqtt_settings.get("enable_secure_connection"):
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.{input_id}.mqtt_in_tls="1"'
                        )
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.{input_id}.mqtt_in_tls_type="cert"'
                        )

                        secure_conn = mqtt_settings.get("secure_connection", {})
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.{input_id}.mqtt_in_insecure="{1 if secure_conn.get("allow_insecure_connection") else 0}"'
                        )

                        # Certificate files
                        cert_from_device = secure_conn.get(
                            "certificate_files_from_device", False
                        )
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.{input_id}.mqtt_device_files="{1 if cert_from_device else 0}"'
                        )

                        # Use full paths for certificates as in WebUI
                        if cert_from_device and "device_certificates" in secure_conn:
                            certs = secure_conn["device_certificates"]
                            if "certificate_authority_file" in certs:
                                await self.ssh_client.execute_command(
                                    f'uci set data_sender.{input_id}.mqtt_in_cafile="/etc/certificates/{certs["certificate_authority_file"]}"'
                                )
                            if "client_certificate" in certs:
                                await self.ssh_client.execute_command(
                                    f'uci set data_sender.{input_id}.mqtt_in_certfile="/etc/ssl/certs/{certs["client_certificate"]}"'
                                )
                            if "client_private_keyfile" in certs:
                                await self.ssh_client.execute_command(
                                    f'uci set data_sender.{input_id}.mqtt_in_keyfile="/etc/certificates/{certs["client_private_keyfile"]}"'
                                )
                        else:
                            # Upload certificates with full paths
                            if "certificate_authority_file" in secure_conn:
                                await self.ssh_client.execute_command(
                                    f'uci set data_sender.{input_id}.mqtt_in_cafile="/etc/certificates/{secure_conn["certificate_authority_file"]}"'
                                )
                            if "client_certificate" in secure_conn:
                                await self.ssh_client.execute_command(
                                    f'uci set data_sender.{input_id}.mqtt_in_certfile="/etc/ssl/certs/{secure_conn["client_certificate"]}"'
                                )
                            if "client_private_keyfile" in secure_conn:
                                await self.ssh_client.execute_command(
                                    f'uci set data_sender.{input_id}.mqtt_in_keyfile="/etc/certificates/{secure_conn["client_private_keyfile"]}"'
                                )

            # Handle impulse counter specific configuration if type is impulse counter
            if data_type.lower() == "impulse counter":
                impulse_settings = type_settings or {}
                logger.info(
                    f"Configuring impulse counter specific settings for input {input_id}"
                )

                # Set the plugin name
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{input_id}.plugin="impulse_counter"'
                )

                # Set the impulse counter object (required)
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{input_id}.impulse_counter_object="1"'
                )

                # Set the number of segments/pins to collect data from
                segments = impulse_settings.get("segments", 3)
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{input_id}.impulse_counter_segments="{segments}"'
                )

                if impulse_settings.get("invert_filter") == True:
                    await self.ssh_client.execute_command(
                        f'uci set data_sender.{input_id}.impulse_counter_filter_invert="1"'
                    )
                # Configure filter type (pin, name, etc.)
                filter_type = impulse_settings.get("filter", "pin")
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{input_id}.impulse_counter_filter="{filter_type}"'
                )
                pin_mapping = {
                    "Input (3)": "1",
                    "Input (4)": "2",
                    "Output (3)": "3",
                    "Output (4)": "4",
                    "din1": "1",
                    "din2": "2",
                    "dout1": "3",
                    "dout2": "4",
                }

                # Configure pin filter value (e.g., din1)
                if filter_type == "pin":
                    # Get the pin from settings
                    pin_name = impulse_settings.get("impulse_counter_pin", "Input (3)")
                    # Convert to pin filter value (e.g., "din1")
                    pin_filter = pin_name.lower()
                    if "input (3)" in pin_filter:
                        pin_filter = "din1"
                    elif "input (4)" in pin_filter:
                        pin_filter = "din2"
                    elif "output (3)" in pin_filter:
                        pin_filter = "dout1"
                    elif "output (4)" in pin_filter:
                        pin_filter = "dout2"

                    await self.ssh_client.execute_command(
                        f'uci set data_sender.{input_id}.impulse_counter_filter_pin="{pin_filter}"'
                    )

                    # Get pin number from mapping
                    pin_num = pin_mapping.get(
                        pin_name, "1"
                    )  # Default to 1 if not found

                    # Add to filter list with the correct pin number
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.filter_list_impulse_counter_filter_pin='{pin_num}'"
                    )

                # Configure the values to collect - default to common impulse counter values
                if not values:
                    values = ["pin_name", "timestamp", "count"]

                # Delete existing members if any
                await self.ssh_client.execute_command(
                    f"uci del data_sender.{input_id}.members"
                )
                # Add each value as a separate list item (quoted)
                for value in values:
                    await self.ssh_client.execute_command(
                        f"uci add_list data_sender.{input_id}.members='{value}'"
                    )
            if data_type.lower() == "mobile usage":
                mobile_settings = type_settings or {}
                logger.info(
                    f"Configuring impulse counter specific settings for input {input_id}"
                )

                # Set the plugin name
                await self.ssh_client.execute_command(
                    f"uci set data_sender.{input_id}.plugin='mdcollect'"
                )
                sim_no = mobile_settings.get("SIM_number")
                if sim_no:
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.mdc_sim='{self.strip_letters_regex(sim_no)}'"
                    )

                period = mobile_settings.get("data_period")
                period = period.lower()
                if period:
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.mdc_period='{period}'"
                    )

                current = mobile_settings.get("current")
                if current == True:

                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.mdc_current='1'"
                    )
                elif current == False:
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.mdc_current='0'"
                    )

                # Delete existing members if any
                await self.ssh_client.execute_command(
                    f"uci del data_sender.{input_id}.members"
                )
                # Add each value as a separate list item (quoted)
                for value in values:
                    await self.ssh_client.execute_command(
                        f"uci add_list data_sender.{input_id}.members='{value}'"
                    )
            if data_type.lower() == "modbus":
                modbus_settings = type_settings or {}
                logger.info(
                    f"Configuring impulse counter specific settings for input {input_id}"
                )
                data_filtering = modbus_settings.get("data_filtering")
                if data_filtering == "Server IP address":
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.modbus_filter='ip'"
                    )
                    server_ip = modbus_settings.get("server_ip")
                    if server_ip:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_filter_server_ip='{server_ip}'"
                        )
                    if len(server_ip) > 1:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_modbus_filter_server_ip='0'"
                        )
                    modbus_segments = modbus_settings.get("segment_count")
                    if modbus_segments:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_segments='{str(modbus_segments)}'"
                        )
                    modbus_object = modbus_segments.get("send_as_object")
                    if modbus_object:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_object='1'"
                        )
                    else:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_object='0'"
                        )
                elif data_filtering == "Server ID":
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.modbus_filter='id'"
                    )
                    server_id = modbus_settings.get("server_id")
                    if server_id:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_filter_server_id='{server_id}'"
                        )
                    if len(server_id) > 1:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_modbus_filter_server_id='1'"
                        )
                    else:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_modbus_filter_server_id='0'"
                        )
                    modbus_segments = modbus_settings.get("segment_count")
                    if modbus_segments:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_segments='{str(modbus_segments)}'"
                        )
                    modbus_object = modbus_segments.get("send_as_object")
                    if modbus_object:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_object='1'"
                        )
                    else:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_object='0'"
                        )
                elif data_filtering == "Request name":
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.modbus_filter='name'"
                    )
                    request_name = modbus_settings.get("request_name")
                    if request_name:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_filter_request='{request_name}'"
                        )
                    if len(request_name) > 1:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_modbus_filter_request='1'"
                        )
                    else:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_modbus_filter_request='0'"
                        )
                    modbus_segments = modbus_settings.get("segment_count")
                    if modbus_segments:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_segments='{str(modbus_segments)}'"
                        )
                    modbus_object = modbus_segments.get("send_as_object")
                    if modbus_object:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_object='1'"
                        )
                    else:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_object='0'"
                        )
                # Delete existing members if any
                await self.ssh_client.execute_command(
                    f"uci del data_sender.{input_id}.members"
                )
                # Add each value as a separate list item (quoted)
                for value in values:
                    await self.ssh_client.execute_command(
                        f"uci add_list data_sender.{input_id}.members='{value}'"
                    )

            if data_type.lower() == "modbus alarms":
                modbus_alarm_settings = type_settings or {}
                logger.info(
                    f"Configuring impulse counter specific settings for input {input_id}"
                )
                data_filtering = modbus_settings.get("data_filtering")
                if data_filtering == "Server ID":
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.modbus_alarm_filter='server_id'"
                    )
                    server_id = modbus_alarm_settings.get("server_id")
                    if server_id:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_alarm_filter_server_id='{str(server_id)}'"
                        )
                    if len(server_id) > 1:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_modbus_alarm_filter_server_id='1'"
                        )
                    else:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_modbus_alarm_filter_server_id='0'"
                        )

                elif data_filtering == "Alarm ID":
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.modbus_alarm_filter='alarm_id'"
                    )
                    alarm_id = modbus_alarm_settings.get("alarm_id")
                    if alarm_id:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_alarm_filter_alarm_id='{alarm_id}'"
                        )
                    if len(alarm_id) > 1:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_modbus_alarm_filter_alarm_id='1'"
                        )
                    else:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_modbus_alarm_filter_alarm_id='0'"
                        )
                elif data_filtering == "Register number":
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.modbus_alarm_filter='register'"
                    )
                    register_number = modbus_alarm_settings.get("register_number")
                    if register_number:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.modbus_alarm_filter_register='{register_number}'"
                        )
                    if len(register_number) > 1:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_modbus_alarm_filter_register='1'"
                        )
                    else:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_modbus_alarm_filter_register='0'"
                        )
                # Delete existing members if any
                await self.ssh_client.execute_command(
                    f"uci del data_sender.{input_id}.members"
                )
                # Add each value as a separate list item (quoted)
                for value in values:
                    await self.ssh_client.execute_command(
                        f"uci add_list data_sender.{input_id}.members='{value}'"
                    )
            if data_type == "wifi scanner":
                wifi_scanner_settings = type_settings or {}
                logger.info(
                    f"Configuring impulse counter specific settings for input {input_id}"
                )
                data_filtering = wifi_scanner_settings.get("data_filtering")
                if data_filtering == "Signal strength":
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.wifi_filter='signal'"
                    )
                    signal_strength = wifi_scanner_settings.get("signal_strength")
                    if len(signal_strength) > 1:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_wifi_filter_signal='1'"
                        )
                    else:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_wifi_filter_signal='0'"
                        )
                    if signal_strength:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.wifi_filter_signal='{signal_strength}'"
                        )
                elif data_filtering == "Name":
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.wifi_filter='name'"
                    )
                    device_hostname = wifi_scanner_settings.get("device_hostname")
                    if len(device_hostname) > 1:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_wifi_filter_name='1'"
                        )
                    else:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_wifi_filter_name='0'"
                        )
                    if device_hostname:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.wifi_filter_name='{device_hostname}'"
                        )
                    segment_count = wifi_scanner_settings.get("segment_count")
                    if segment_count:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.wifi_segments='{str(segment_count)}'"
                        )
                elif data_filtering == "MAC address":
                    await self.ssh_client.execute_command(
                        f"uci set data_sender.{input_id}.wifi_filter='mac'"
                    )
                    mac_address = wifi_scanner_settings.get("mac_address")
                    if len(mac_address) > 1:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_wifi_filter_mac='1'"
                        )
                    else:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.filter_list_wifi_filter_mac='0'"
                        )
                    if mac_address:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.wifi_filter_mac='{mac_address}'"
                        )
                    segment_count = wifi_scanner_settings.get("segment_count")
                    if segment_count:
                        await self.ssh_client.execute_command(
                            f"uci set data_sender.{input_id}.wifi_segments='{str(segment_count)}'"
                        )
                # Delete existing members if any
                await self.ssh_client.execute_command(
                    f"uci del data_sender.{input_id}.members"
                )
                # Add each value as a separate list item (quoted)
                for value in values:
                    await self.ssh_client.execute_command(
                        f"uci add_list data_sender.{input_id}.members='{value}'"
                    )
            logger.info(
                f"Configured data collection settings via SSH for section {input_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to configure data collection settings via SSH: {str(e)}"
            )
            raise

    async def _configure_scheduler(self, scheduler_config):
        """Configure scheduler-based collection via UCI with dynamic section ID."""
        try:
            logger.info("SSH DTS: _configure_scheduler function started.")
            collection_id = self.section_ids["collection"]

            # Set timer type
            await self.ssh_client.execute_command(
                f'uci set data_sender.{collection_id}.timer="scheduler"'
            )

            # Day time
            day_time = scheduler_config.get("day_time")
            if day_time:
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{collection_id}.day_time="{day_time}"'
                )

            # Interval type
            interval_type = scheduler_config.get("interval_type", "Day")
            day_mode = "day"
            if interval_type == "Week days":
                day_mode = "week"
            elif interval_type == "Month days":
                day_mode = "month"

            await self.ssh_client.execute_command(
                f'uci set data_sender.{collection_id}.day_mode="{day_mode}"'
            )

            # Month days - use add_list for WebUI compatibility
            month_days = scheduler_config.get("month_day", [])
            if month_days:
                # First delete any existing month_days
                await self.ssh_client.execute_command(
                    f"uci del data_sender.{collection_id}.month_days"
                )
                # Add each day as a separate list item (quoted)
                for day in month_days:
                    await self.ssh_client.execute_command(
                        f"uci add_list data_sender.{collection_id}.month_days='{day}'"
                    )

            # Weekdays
            weekdays = scheduler_config.get("weekdays", [])
            if weekdays:
                weekdays_str = " ".join(weekdays)
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{collection_id}.weekdays="{weekdays_str}"'
                )

            # Force last day
            force_last_day = scheduler_config.get("force_last_day", False)
            await self.ssh_client.execute_command(
                f'uci set data_sender.{collection_id}.last_day="{1 if force_last_day else 0}"'
            )

            # Additional options
            await self.ssh_client.execute_command(
                f'uci set data_sender.{collection_id}.retry="{1 if scheduler_config.get("retry") else 0}"'
            )

            # Construct time string (combines day_time and month_days for 'time' field)
            # Without the trailing asterisk to match WebUI format
            time_str = (
                f"{day_time}:{','.join(map(str, month_days)) if month_days else ''}:"
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.{collection_id}.time="{time_str}"'
            )

            # Retry count and timeout
            retry_count = scheduler_config.get("retry_count", 0)
            timeout = scheduler_config.get("timeout", 0)
            await self.ssh_client.execute_command(
                f'uci set data_sender.{collection_id}.retry_count="{retry_count}"'
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.{collection_id}.retry_timeout="{timeout}"'
            )

            logger.info(
                f"Configured scheduler settings via SSH for section {collection_id}"
            )

        except Exception as e:
            logger.error(f"Failed to configure scheduler settings via SSH: {str(e)}")
            raise

    def strip_letters_regex(self, input_string):
        return re.sub(r"[^0-9]", "", input_string)

    async def _configure_period(self, period_config):
        """Configure period-based collection via UCI with dynamic section ID."""
        try:
            logger.info("SSH DTS: _configure_period function started.")
            collection_id = self.section_ids["collection"]

            # Set timer type to period
            await self.ssh_client.execute_command(
                f'uci set data_sender.{collection_id}.timer="period"'
            )

            # Set period
            period = period_config.get("period", 60)
            await self.ssh_client.execute_command(
                f'uci set data_sender.{collection_id}.period="{period}"'
            )

            # Set retry
            retry = 1 if period_config.get("retry") else 0
            await self.ssh_client.execute_command(
                f'uci set data_sender.{collection_id}.retry="{retry}"'
            )

            logger.info(
                f"Configured period settings via SSH for section {collection_id}"
            )

        except Exception as e:
            logger.error(f"Failed to configure period settings via SSH: {str(e)}")
            raise

    async def _configure_server(self, server_config):
        """Configure server settings via UCI with dynamic section ID."""
        try:
            logger.info("SSH DTS: _configure_server function started.")
            output_id = self.section_ids["output"]

            # Set server plugin
            await self.ssh_client.execute_command(
                f'uci set data_sender.{output_id}.plugin="mqtt"'
            )

            # Set basic server settings
            server_address = server_config.get("server_address", "localhost")
            await self.ssh_client.execute_command(
                f'uci set data_sender.{output_id}.mqtt_host="{server_address}"'
            )

            port = server_config.get("port", 1883)
            await self.ssh_client.execute_command(
                f'uci set data_sender.{output_id}.mqtt_port="{port}"'
            )

            keepalive = server_config.get(
                "keepalive", 30
            )  # Default to 30 to match WebUI
            await self.ssh_client.execute_command(
                f'uci set data_sender.{output_id}.mqtt_keepalive="{keepalive}"'
            )

            topic = server_config.get("topic", "test/topic")
            await self.ssh_client.execute_command(
                f'uci set data_sender.{output_id}.mqtt_topic="{topic}"'
            )

            client_id = server_config.get(
                "client_id", "test_client"
            )  # Default to 'test_client' to match WebUI
            await self.ssh_client.execute_command(
                f'uci set data_sender.{output_id}.mqtt_client_id="{client_id}"'
            )

            qos = server_config.get("QoS", 2)  # Default to 2 to match WebUI
            await self.ssh_client.execute_command(
                f'uci set data_sender.{output_id}.mqtt_qos="{qos}"'
            )

            # Configure secure connection if enabled
            if server_config.get("enable_secure_connection"):
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{output_id}.mqtt_tls="1"'
                )

                secure_config = server_config.get("secure_connection", {})

                # Insecure connection setting
                insecure = 1 if secure_config.get("allow_insecure_connection") else 0
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{output_id}.mqtt_insecure="{insecure}"'
                )

                # Determine certificate source
                is_device_certs = secure_config.get(
                    "certificate_files_from_device", False
                )
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{output_id}.mqtt_device_files="{1 if is_device_certs else 0}"'
                )

                # Set TLS type
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{output_id}.mqtt_tls_type="cert"'
                )

                # Process certificates based on source - use full paths
                if is_device_certs and "device_certificates" in secure_config:
                    # Using device certificates
                    cert_source = secure_config["device_certificates"]
                    # Set certificate paths with full paths
                    if "certificate_authority_file" in cert_source:
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.{output_id}.mqtt_cafile="/etc/certificates/{cert_source["certificate_authority_file"]}"'
                        )
                    if "client_certificate" in cert_source:
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.{output_id}.mqtt_certfile="/etc/ssl/certs/{cert_source["client_certificate"]}"'
                        )
                    if "client_private_keyfile" in cert_source:
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.{output_id}.mqtt_keyfile="/etc/certificates/{cert_source["client_private_keyfile"]}"'
                        )
                else:

                    collection_id = self.section_ids["collection"]
                    data_id = self.section_ids["output"]
                    try:
                        uploaded_paths = await DataToServerAPITest.upload_certificates(
                            collection_id, data_id, secure_config
                        )

                        if "mqtt_in_cafile" in uploaded_paths:
                            await self.ssh_client.execute_command(
                                f'uci set data_sender.{output_id}.mqtt_cafile="{uploaded_paths["mqtt_in_cafile"]}"'
                            )
                        if "mqtt_in_certfile" in uploaded_paths:
                            await self.ssh_client.execute_command(
                                f'uci set data_sender.{output_id}.mqtt_certfile="{uploaded_paths["mqtt_in_certfile"]}"'
                            )
                        if "mqtt_in_keyfile" in uploaded_paths:
                            await self.ssh_client.execute_command(
                                f'uci set data_sender.{output_id}.mqtt_keyfile="{uploaded_paths["mqtt_in_keyfile"]}"'
                            )
                    except Exception as upload_error:
                        logger.error(
                            f"Failed to upload certificates: {str(upload_error)}"
                        )

            # Configure credentials if needed
            use_credentials = 1 if server_config.get("use_credentials") else 0
            await self.ssh_client.execute_command(
                f'uci set data_sender.{output_id}.mqtt_use_credentials="{use_credentials}"'
            )

            if use_credentials:
                username = server_config.get("username", "")
                password = server_config.get("password", "")
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{output_id}.mqtt_username="{username}"'
                )
                await self.ssh_client.execute_command(
                    f'uci set data_sender.{output_id}.mqtt_password="{password}"'
                )

            logger.info(f"Configured server settings via SSH for section {output_id}")

        except Exception as e:
            logger.error(f"Failed to configure server settings via SSH: {str(e)}")
            raise

    async def _apply_changes(self):
        """Apply UCI changes and restart Data to Server service."""
        try:
            logger.info("SSH DTS: _apply_changes function started.")
            # Commit UCI changes
            await self.ssh_client.execute_command("uci commit data_sender")

            # Restart Data to Server service
            await self.ssh_client.execute_command("/etc/init.d/data_sender restart")

            # Wait for service to start properly
            await self.ssh_client.execute_command("sleep 2")

            logger.info("Applied Data to Server configuration changes via SSH")

        except Exception as e:
            logger.error(f"Failed to apply Data to Server changes via SSH: {str(e)}")
            raise

    async def _verify_configuration(self):
        """Verify the applied configuration with dynamically determined section IDs."""
        try:
            logger.info("SSH DTS: _verify_configuration function started.")

            # Get full configuration
            config = self._extract_config()

            # Check if data sender is enabled
            collection_id = self.section_ids["collection"]
            result = await self.ssh_client.execute_command(
                f"uci get data_sender.{collection_id}.enabled"
            )
            if result.strip() != "1":
                logger.error(f"Data sender is not enabled in section {collection_id}")
                return False

            # Check instance name
            expected_name = config.get("instanceName", "test_instance")
            name_result = await self.ssh_client.execute_command(
                f"uci get data_sender.{collection_id}.name"
            )
            if name_result.strip() != expected_name:
                logger.error(
                    f"Instance name mismatch in section {collection_id}. Expected: {expected_name}, Got: {name_result.strip()}"
                )
                return False

            # Check server configuration
            server_config = config.get("server_config", {})
            output_id = self.section_ids["output"]
            if server_config:
                # Verify MQTT host
                host_cmd = f"uci get data_sender.{output_id}.mqtt_host"
                host = await self.ssh_client.execute_command(host_cmd)
                if host.strip() != server_config.get("server_address", ""):
                    logger.error(
                        f"MQTT host mismatch in section {output_id}. Expected: {server_config.get('server_address')}, Got: {host.strip()}"
                    )
                    return False

                # Verify MQTT port
                port_cmd = f"uci get data_sender.{output_id}.mqtt_port"
                port = await self.ssh_client.execute_command(port_cmd)
                if port.strip() != str(server_config.get("port", "")):
                    logger.error(
                        f"MQTT port mismatch in section {output_id}. Expected: {server_config.get('port')}, Got: {port.strip()}"
                    )
                    return False

            logger.info("Configuration verification successful")
            return True

        except Exception as e:
            logger.error(f"Configuration verification failed: {str(e)}")
            return False
