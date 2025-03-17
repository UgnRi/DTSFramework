from src.test_scenarios.base_scenario import BaseTestScenario
from src.backend.ssh_client import SSHClient
from src.utils.logger import setup_logger
from typing import Dict, Any

logger = setup_logger()


class BaseSSHTest(BaseTestScenario):
    """Base class for SSH-based test scenarios"""

    def __init__(self, device_config: Dict[str, Any], scenario_config: Dict[str, Any]):
        """
        Initialize SSH test base class

        Args:
            device_config: Device configuration dictionary
            scenario_config: Scenario-specific configuration
        """
        # Extract scenario name from scenario_config
        scenario_name = scenario_config.get("scenario_name")

        # Call parent constructor with scenario name
        super().__init__(device_config=device_config, scenario_name=scenario_name)

        # Store full scenario configuration
        self.full_scenario_config = scenario_config

        # Use config from scenario_config
        self.scenario_config = scenario_config.get("config", {})

        # Initialize SSH client
        self.ssh_client = SSHClient(device_config)

        # Flag to track whether configuration changes were made
        self.config_changes_made = False

    async def setup(self):
        """Setup SSH connection"""
        try:
            await self.ssh_client.connect()
            self.logger.info(
                f"SSH connection established for {self.__class__.__name__}"
            )
        except Exception as e:
            self.logger.error(f"Failed to setup SSH connection: {str(e)}")
            raise

    async def cleanup(self):
        """Close SSH connection and perform configuration cleanup if needed"""
        try:
            # Check if this is a Data to Server test that needs cleanup
            if "data_to_server" in self.__class__.__name__.lower():
                self.logger.info(
                    f"Performing configuration cleanup for {self.__class__.__name__}"
                )

                try:
                    # Import here to avoid circular imports
                    from src.backend.validators import WirelessValidator

                    # Create validator with EXPLICITLY set 'ssh' test type to force cleanup
                    # This is the key fix - we're forcing the test_type to be 'ssh'
                    validator = WirelessValidator(self.device_config, test_type="ssh")

                    # Connect with a new connection to ensure it works
                    await validator.ssh_client.connect()

                    # Manually force the _cleanup_configuration method to run
                    # Use full path to call the method to ensure it's found
                    self.logger.info(
                        "Forcing cleanup with validator._cleanup_configuration"
                    )
                    await validator._cleanup_configuration(
                        self.full_scenario_config, clean_all=True
                    )

                    self.logger.info(
                        "Successfully cleaned up Data to Server configuration"
                    )

                    # Close validator's SSH connection
                    await validator.ssh_client.close()

                except Exception as cleanup_error:
                    self.logger.error(
                        f"Error during configuration cleanup: {str(cleanup_error)}"
                    )

            # Close main SSH connection
            await self.ssh_client.close()
            self.logger.info(f"SSH connection closed for {self.__class__.__name__}")

        except Exception as e:
            self.logger.error(f"Failed to close SSH connection: {str(e)}")
            raise

    async def execute_uci_command(self, command: str, silent: bool = False):
        """
        Execute a UCI command with proper error handling

        Args:
            command: UCI command to execute
            silent: If True, don't log the command (useful for password commands)
        """
        try:
            if not silent:
                self.logger.debug(f"Executing UCI command: {command}")
            result = await self.ssh_client.execute_command(command)

            # If this is a configuration change command, set the flag
            if "uci set" in command or "uci add" in command or "uci delete" in command:
                self.config_changes_made = True

            return result

        except Exception as e:
            self.logger.error(f"Failed to execute UCI command: {str(e)}")
            raise

    async def apply_uci_changes(self, config_name: str):
        """
        Apply UCI changes and restart service if needed

        Args:
            config_name: Name of the UCI configuration to commit
        """
        try:
            # Commit changes
            await self.execute_uci_command(f"uci commit {config_name}")

            # Restart service
            await self.execute_uci_command(f"/etc/init.d/{config_name} restart")

            # Mark that configuration changes were made
            self.config_changes_made = True

            self.logger.info(f"Applied {config_name} configuration changes")

        except Exception as e:
            self.logger.error(f"Failed to apply {config_name} changes: {str(e)}")
            raise

    @staticmethod
    def format_bool_value(value: bool) -> str:
        """Convert boolean to UCI-compatible string"""
        return "1" if value else "0"

    @staticmethod
    def format_list_value(values: list) -> str:
        """Convert list to UCI-compatible string"""
        return " ".join(map(str, values))

    async def execute(self):
        """Execute method must be implemented by child classes"""
        raise NotImplementedError("Execute method must be implemented by child classes")

    async def run(self):
        """
        Override the run method from BaseTestScenario to ensure cleanup happens

        Returns:
            Dictionary with test results
        """
        import asyncio

        start_time = asyncio.get_event_loop().time()
        result = {"success": False, "details": None, "error": None, "duration": 0}

        try:
            self.logger.info(f"Starting SSH test scenario: {self.scenario_name}")
            await self.setup()

            # Execute test method
            execute_result = await self.execute()

            # Handle different result formats
            if isinstance(execute_result, dict):
                if "success" in execute_result:
                    result["success"] = execute_result["success"]
                if "details" in execute_result:
                    result["details"] = execute_result["details"]
            else:
                result.update(
                    {
                        "success": bool(execute_result),
                        "details": (
                            "Test executed successfully"
                            if execute_result
                            else "Test execution failed"
                        ),
                    }
                )

        except Exception as e:
            self.logger.error(f"Test scenario failed: {str(e)}")
            result.update({"success": False, "error": str(e)})

        finally:
            # Ensure cleanup is always called
            try:
                self.logger.info(
                    f"Running cleanup for SSH test {self.__class__.__name__}"
                )
                await self.cleanup()
            except Exception as e:
                self.logger.error(f"Cleanup failed: {str(e)}")

            # Calculate duration
            end_time = asyncio.get_event_loop().time()
            result["duration"] = round(end_time - start_time, 2)

        return result
