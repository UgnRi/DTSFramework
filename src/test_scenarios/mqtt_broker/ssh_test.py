# src/test_scenarios/mqtt_broker/ssh_test.py

from src.test_scenarios.base_scenario import BaseTestScenario
from src.backend.ssh_client import SSHClient
from src.utils.logger import setup_logger
from src.test_scenarios.base_ssh_test import BaseSSHTest
from typing import Dict, Any

logger = setup_logger()


class MQTTBrokerSSHTest(BaseSSHTest):
    def __init__(self, device_config: Dict[str, Any], scenario_config=None):
        super().__init__(device_config=device_config, scenario_config=scenario_config)
        self.logger.info(
            f"MQTTBrokerSSHTest initialized with scenario: {self.scenario_name}"
        )

    async def execute(self):
        """Execute MQTT broker configuration via SSH commands"""
        try:
            self.logger.info(
                f"Executing MQTT Broker SSH test for scenario: {self.scenario_name}"
            )
            # Log the scenario config for debugging
            self.logger.info(
                f"Scenario config keys: {list(self.scenario_config.keys())}"
            )

            # Configure the MQTT broker
            await self._configure_basic_settings()

            # Security settings if present
            if "security" in self.scenario_config:
                await self._configure_security_settings()

            # Miscellaneous settings if present
            if "miscellaneous" in self.scenario_config:
                await self._configure_misc_settings()

            # Apply the changes
            await self.apply_uci_changes("mosquitto")

            # Check MQTT broker status
            status = await self.ssh_client.execute_command(
                "/etc/init.d/mosquitto status"
            )
            if "running" in status.lower():
                self.logger.info("MQTT broker is running after configuration")
                return {
                    "success": True,
                    "details": "MQTT broker configured successfully",
                }
            else:
                self.logger.error("MQTT broker is not running after configuration")
                return {
                    "success": False,
                    "details": "MQTT broker is not running after configuration",
                }

        except Exception as e:
            self.logger.error(f"Error executing MQTT broker SSH test: {str(e)}")
            return {"success": False, "details": {"error": str(e)}}

    async def _configure_basic_settings(self):
        """Configure basic MQTT settings via UCI"""
        try:
            # Enable MQTT Broker
            await self.execute_uci_command("uci set mosquitto.mqtt.enabled=1")

            # Configure port if specified
            if "port" in self.scenario_config:
                await self.execute_uci_command(
                    f'uci set mosquitto.mqtt.local_port={self.scenario_config["port"]}'
                )

            # Configure remote access if specified
            if "remote_access" in self.scenario_config:
                await self.execute_uci_command(
                    f'uci set mosquitto.mqtt.allow_ra={self.format_bool_value(self.scenario_config["remote_access"])}'
                )

            self.logger.info("Configured basic MQTT settings")
        except Exception as e:
            self.logger.error(f"Failed to configure basic MQTT settings: {str(e)}")
            raise

    async def _configure_security_settings(self):
        """Configure MQTT security settings via UCI"""
        try:
            security_config = self.scenario_config["security"]

            # Configure TLS/SSL
            if "TLS/SSL" in security_config:
                await self.execute_uci_command(
                    f'uci set mosquitto.mqtt.use_tls_ssl={self.format_bool_value(security_config["TLS/SSL"])}'
                )

            # Configure certificates
            if "certificates" in security_config:
                cert_config = security_config["certificates"]

                if "require_certificate" in cert_config:
                    await self.execute_uci_command(
                        f'uci set mosquitto.mqtt.require_certificate={self.format_bool_value(cert_config["require_certificate"])}'
                    )

                if "device_certificates" in cert_config:
                    device_certs = cert_config["device_certificates"]
                    for cert_type, cert_path in {
                        "ca_file": "ca_file",
                        "certificate_file": "cert_file",
                        "client_private_keyfile": "key_file",
                    }.items():
                        if cert_type in device_certs:
                            await self.execute_uci_command(
                                f"uci set mosquitto.mqtt.{cert_path}={device_certs[cert_type]}"
                            )

            self.logger.info("Configured MQTT security settings")
        except Exception as e:
            self.logger.error(f"Failed to configure MQTT security settings: {str(e)}")
            raise

    async def _configure_misc_settings(self):
        """Configure MQTT miscellaneous settings via UCI"""
        try:
            misc_config = self.scenario_config["miscellaneous"]

            settings_map = {
                "persistence": ("persistence", bool),
                "allow_anonymous": ("anonymous_access", bool),
                "max_queued_messages": ("max_queued_messages", str),
                "maximum_packet_size": ("max_packet_size", str),
            }

            for config_key, (uci_key, value_type) in settings_map.items():
                if config_key in misc_config:
                    value = misc_config[config_key]
                    formatted_value = (
                        self.format_bool_value(value)
                        if value_type is bool
                        else str(value)
                    )
                    await self.execute_uci_command(
                        f"uci set mosquitto.mqtt.{uci_key}={formatted_value}"
                    )

            self.logger.info("Configured MQTT miscellaneous settings")
        except Exception as e:
            self.logger.error(
                f"Failed to configure MQTT miscellaneous settings: {str(e)}"
            )
            raise

    async def run(self):
        """Run MQTT Broker SSH test"""
        try:
            # Connect to device via SSH
            await self.ssh_client.connect()

            # Configure MQTT broker
            await self.configure_mqtt_broker()

            # Return success result
            return {
                "success": True,
                "details": "MQTT broker configured successfully via SSH",
            }

        except Exception as e:
            logger.error(f"MQTT Broker SSH test failed: {str(e)}")
            return {"success": False, "details": str(e)}
        finally:
            await self.ssh_client.close()

    async def configure_mqtt_broker(self):
        """Configure MQTT broker via SSH/UCI"""
        try:
            # Basic settings
            await self._configure_basic_settings()

            # Security settings if present
            if "security" in self.scenario_config:
                await self._configure_security_settings()

            # Miscellaneous settings if present
            if "miscellaneous" in self.scenario_config:
                await self._configure_misc_settings()

            # Apply changes
            await self._apply_changes()

        except Exception as e:
            logger.error(f"Failed to configure MQTT broker via SSH: {str(e)}")
            raise

    async def _configure_basic_settings(self):
        """Configure basic MQTT settings via UCI"""
        try:
            # Enable MQTT Broker
            await self.ssh_client.execute_command("uci set mosquitto.mqtt.enabled=1")

            # Configure port if specified
            if "port" in self.scenario_config:
                await self.ssh_client.execute_command(
                    f'uci set mosquitto.mqtt.local_port={self.scenario_config["port"]}'
                )

            # Configure remote access if specified
            if "remote_access" in self.scenario_config:
                await self.ssh_client.execute_command(
                    f'uci set mosquitto.mqtt.allow_ra={1 if self.scenario_config["remote_access"] else 0}'
                )

            logger.info("Configured basic MQTT settings via SSH")

        except Exception as e:
            logger.error(f"Failed to configure basic MQTT settings via SSH: {str(e)}")
            raise

    async def _configure_security_settings(self):
        """Configure MQTT security settings via UCI"""
        try:
            security_config = self.scenario_config["security"]

            # Configure TLS/SSL
            if "TLS/SSL" in security_config:
                await self.ssh_client.execute_command(
                    f'uci set mosquitto.mqtt.use_tls_ssl={1 if security_config["TLS/SSL"] else 0}'
                )

            # Configure certificates
            if "certificates" in security_config:
                cert_config = security_config["certificates"]

                # Set require certificate
                if "require_certificate" in cert_config:
                    await self.ssh_client.execute_command(
                        f'uci set mosquitto.mqtt.require_certificate={1 if cert_config["require_certificate"] else 0}'
                    )

                # Handle certificate files
                if "device_certificates" in cert_config:
                    device_certs = cert_config["device_certificates"]
                    await self.ssh_client.execute_command(
                        f'uci set mosquitto.mqtt.ca_file={device_certs.get("ca_file", "")}'
                    )
                    await self.ssh_client.execute_command(
                        f'uci set mosquitto.mqtt.cert_file={device_certs.get("certificate_file", "")}'
                    )
                    await self.ssh_client.execute_command(
                        f'uci set mosquitto.mqtt.key_file={device_certs.get("client_private_keyfile", "")}'
                    )

            # Set TLS version if specified
            if "TLS_version" in security_config:
                await self.ssh_client.execute_command(
                    f'uci set mosquitto.mqtt.tls_version="{security_config["TLS_version"]}"'
                )

            logger.info("Configured MQTT security settings via SSH")

        except Exception as e:
            logger.error(
                f"Failed to configure MQTT security settings via SSH: {str(e)}"
            )
            raise

    async def _configure_misc_settings(self):
        """Configure MQTT miscellaneous settings via UCI"""
        try:
            misc_config = self.scenario_config["miscellaneous"]

            # Configure persistence
            if "persistence" in misc_config:
                await self.ssh_client.execute_command(
                    f'uci set mosquitto.mqtt.persistence={1 if misc_config["persistence"] else 0}'
                )

            # Configure anonymous access
            if "allow_anonymous" in misc_config:
                await self.ssh_client.execute_command(
                    f'uci set mosquitto.mqtt.anonymous_access={1 if misc_config["allow_anonymous"] else 0}'
                )

            # Configure max queued messages
            if "max_queued_messages" in misc_config:
                await self.ssh_client.execute_command(
                    f'uci set mosquitto.mqtt.max_queued_messages={misc_config["max_queued_messages"]}'
                )

            # Configure maximum packet size
            if "maximum_packet_size" in misc_config:
                await self.ssh_client.execute_command(
                    f'uci set mosquitto.mqtt.max_packet_size={misc_config["maximum_packet_size"]}'
                )

            logger.info("Configured MQTT miscellaneous settings via SSH")

        except Exception as e:
            logger.error(
                f"Failed to configure MQTT miscellaneous settings via SSH: {str(e)}"
            )
            raise

    async def _apply_changes(self):
        """Apply UCI changes and restart MQTT service"""
        try:
            # Commit UCI changes
            await self.ssh_client.execute_command("uci commit mosquitto")

            # Restart MQTT service
            await self.ssh_client.execute_command("/etc/init.d/mosquitto restart")

            logger.info("Applied MQTT configuration changes via SSH")

        except Exception as e:
            logger.error(f"Failed to apply MQTT changes via SSH: {str(e)}")
            raise


# src/test_scenarios/data_to_server/ssh_test.py

from src.test_scenarios.base_scenario import BaseTestScenario
from src.backend.ssh_client import SSHClient
from src.utils.logger import setup_logger
from typing import Dict, Any

logger = setup_logger()


class DataToServerSSHTest(BaseTestScenario):
    def __init__(self, device_config: Dict[str, Any], scenario_config=None):
        super().__init__(device_config=device_config, scenario_name="data_to_server")
        self.scenario_config = scenario_config or {}
        self.ssh_client = SSHClient(
            host=self.device_config["device"]["ip"],
            username=self.device_config["device"]["credentials"]["username"],
            password=self.device_config["device"]["credentials"]["password"],
        )

    async def run(self):
        """Run Data to Server SSH test"""
        try:
            # Connect to device via SSH
            await self.ssh_client.connect()

            # Configure Data to Server
            await self.configure_dts()

            # Return success result
            return {
                "success": True,
                "details": "Data to Server configured successfully via SSH",
            }

        except Exception as e:
            logger.error(f"Data to Server SSH test failed: {str(e)}")
            return {"success": False, "details": str(e)}
        finally:
            await self.ssh_client.close()

    async def configure_dts(self):
        """Configure Data to Server via SSH/UCI"""
        try:
            # Set instance name
            instance_name = self.scenario_config.get("instanceName", "test_instance")
            await self.ssh_client.execute_command(
                f'uci set data_sender.1.name="{instance_name}"'
            )
            await self.ssh_client.execute_command("uci set data_sender.1.enabled=1")

            # Configure data collection
            if "data_config" in self.scenario_config:
                await self._configure_data_collection()

            # Configure collection method (period or scheduler)
            if "collection_config-scheduler" in self.scenario_config:
                await self._configure_scheduler()
            elif "collection_config-period" in self.scenario_config:
                await self._configure_period()

            # Configure server settings
            if "server_config" in self.scenario_config:
                await self._configure_server()

            # Apply changes
            await self._apply_changes()

        except Exception as e:
            logger.error(f"Failed to configure Data to Server via SSH: {str(e)}")
            raise

    async def _configure_data_collection(self):
        """Configure data collection settings via UCI"""
        try:
            data_config = self.scenario_config["data_config"]

            # Set data source type
            await self.ssh_client.execute_command(
                f'uci set data_sender.1.type="{data_config["type"]}"'
            )

            # Configure type-specific settings
            if "type_settings" in data_config:
                type_settings = data_config["type_settings"]
                for key, value in type_settings.items():
                    if isinstance(value, bool):
                        value = 1 if value else 0
                    await self.ssh_client.execute_command(
                        f'uci set data_sender.1.{key}="{value}"'
                    )

            # Set format type
            await self.ssh_client.execute_command(
                f'uci set data_sender.1.format_type="{data_config["format_type"]}"'
            )

            # Configure values to collect
            if "values" in data_config:
                values_str = " ".join(data_config["values"])
                await self.ssh_client.execute_command(
                    f'uci set data_sender.1.values="{values_str}"'
                )

            logger.info("Configured data collection settings via SSH")

        except Exception as e:
            logger.error(
                f"Failed to configure data collection settings via SSH: {str(e)}"
            )
            raise

    async def _configure_scheduler(self):
        """Configure scheduler-based collection via UCI"""
        try:
            scheduler_config = self.scenario_config["collection_config-scheduler"]

            # Set basic scheduler settings
            await self.ssh_client.execute_command(
                'uci set data_sender.1.timer="scheduler"'
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.1.day_time="{scheduler_config["day_time"]}"'
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.1.interval_type="{scheduler_config["interval_type"]}"'
            )

            # Set month days
            if "month_day" in scheduler_config:
                month_days = " ".join(map(str, scheduler_config["month_day"]))
                await self.ssh_client.execute_command(
                    f'uci set data_sender.1.month_day="{month_days}"'
                )

            # Set weekdays
            if "weekdays" in scheduler_config:
                weekdays = " ".join(scheduler_config["weekdays"])
                await self.ssh_client.execute_command(
                    f'uci set data_sender.1.weekdays="{weekdays}"'
                )

            # Set additional options
            if scheduler_config.get("force_last_day"):
                await self.ssh_client.execute_command(
                    "uci set data_sender.1.force_last_day=1"
                )

            if scheduler_config.get("retry"):
                await self.ssh_client.execute_command("uci set data_sender.1.retry=1")
                await self.ssh_client.execute_command(
                    f'uci set data_sender.1.retry_count={scheduler_config["retry_count"]}'
                )
                await self.ssh_client.execute_command(
                    f'uci set data_sender.1.timeout={scheduler_config["timeout"]}'
                )

            logger.info("Configured scheduler settings via SSH")

        except Exception as e:
            logger.error(f"Failed to configure scheduler settings via SSH: {str(e)}")
            raise

    async def _configure_period(self):
        """Configure period-based collection via UCI"""
        try:
            period_config = self.scenario_config["collection_config-period"]

            # Set period
            await self.ssh_client.execute_command(
                f'uci set data_sender.1.period={period_config["period"]}'
            )

            # Set retry if enabled
            if period_config.get("retry"):
                await self.ssh_client.execute_command("uci set data_sender.1.retry=1")

            logger.info("Configured period settings via SSH")

        except Exception as e:
            logger.error(f"Failed to configure period settings via SSH: {str(e)}")
            raise

    async def _configure_server(self):
        """Configure server settings via UCI"""
        try:
            server_config = self.scenario_config["server_config"]

            # Set basic server settings
            await self.ssh_client.execute_command(
                f'uci set data_sender.2.mqtt_host="{server_config["server_address"]}"'
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.2.mqtt_port={server_config["port"]}'
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.2.mqtt_keepalive={server_config["keepalive"]}'
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.2.mqtt_topic="{server_config["topic"]}"'
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.2.mqtt_client_id="{server_config["client_id"]}"'
            )
            await self.ssh_client.execute_command(
                f'uci set data_sender.2.mqtt_qos={server_config["QoS"]}'
            )

            # Configure secure connection if enabled
            if server_config.get("enable_secure_connection"):
                await self.ssh_client.execute_command(
                    "uci set data_sender.2.mqtt_tls=1"
                )

                secure_config = server_config["secure_connection"]

                if secure_config.get("allow_insecure_connection"):
                    await self.ssh_client.execute_command(
                        "uci set data_sender.2.mqtt_insecure=1"
                    )

                if secure_config.get("certificate_files_from_device"):
                    await self.ssh_client.execute_command(
                        "uci set data_sender.2.mqtt_device_files=1"
                    )

                    # Set certificate paths
                    if "device_certificates" in secure_config:
                        certs = secure_config["device_certificates"]
                        if "certificate_authority_file" in certs:
                            await self.ssh_client.execute_command(
                                f'uci set data_sender.2.mqtt_cafile="{certs["certificate_authority_file"]}"'
                            )
                        if "certificate_authority_file" in certs:
                            await self.ssh_client.execute_command(
                                f'uci set data_sender.2.mqtt_cafile="{certs["certificate_authority_file"]}"'
                            )
                        if "client_certificate" in certs:
                            await self.ssh_client.execute_command(
                                f'uci set data_sender.2.mqtt_certfile="{certs["client_certificate"]}"'
                            )
                        if "client_private_keyfile" in certs:
                            await self.ssh_client.execute_command(
                                f'uci set data_sender.2.mqtt_keyfile="{certs["client_private_keyfile"]}"'
                            )
                else:
                    # Handle uploaded certificates
                    if "certificate_authority_file" in secure_config:
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.2.mqtt_cafile="{secure_config["certificate_authority_file"]}"'
                        )
                    if "client_certificate" in secure_config:
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.2.mqtt_certfile="{secure_config["client_certificate"]}"'
                        )
                    if "client_private_keyfile" in secure_config:
                        await self.ssh_client.execute_command(
                            f'uci set data_sender.2.mqtt_keyfile="{secure_config["client_private_keyfile"]}"'
                        )

            # Configure credentials if needed
            if server_config.get("use_credentials"):
                await self.ssh_client.execute_command(
                    "uci set data_sender.2.mqtt_use_credentials=1"
                )
                await self.ssh_client.execute_command(
                    f'uci set data_sender.2.mqtt_username="{server_config["username"]}"'
                )
                await self.ssh_client.execute_command(
                    f'uci set data_sender.2.mqtt_password="{server_config["password"]}"'
                )

            logger.info("Configured server settings via SSH")

        except Exception as e:
            logger.error(f"Failed to configure server settings via SSH: {str(e)}")
            raise

    async def _apply_changes(self):
        """Apply UCI changes and restart Data to Server service"""
        try:
            # Commit UCI changes
            await self.ssh_client.execute_command("uci commit data_sender")

            # Restart Data to Server service
            await self.ssh_client.execute_command("/etc/init.d/data_sender restart")

            logger.info("Applied Data to Server configuration changes via SSH")

        except Exception as e:
            logger.error(f"Failed to apply Data to Server changes via SSH: {str(e)}")
            raise
