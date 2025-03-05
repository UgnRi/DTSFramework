# src/test_scenarios/base_ssh_test.py
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
        """Close SSH connection"""
        try:
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
            await self.ssh_client.execute_command(command)
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
