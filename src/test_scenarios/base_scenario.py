from abc import ABC, abstractmethod
from typing import Dict, Any
import asyncio
from src.utils.logger import setup_logger
import json
from pathlib import Path

logger = setup_logger()


class BaseTestScenario(ABC):
    def __init__(
        self,
        device_config: Dict[str, Any],
        scenario_name: str = None,
        scenario_config: Dict[str, Any] = None,
    ):
        self.device_config = device_config
        self.scenario_name = scenario_name

        logger.info(
            f"BaseTestScenario.__init__ called with scenario_name={scenario_name}"
        )

        self.scenario_config = scenario_config or {}

        # If scenario_config is provided directly, use it
        # if scenario_config:
        #     self.scenario_config = scenario_config
        # Otherwise, try to load from scenario_name
        # elif scenario_name:
        #     try:
        #         self.scenario_config = self.load_scenario_config(scenario_name)
        #     except Exception as e:
        #         logger.error(
        #             f"Error loading config from config/test_scenarios/{scenario_name}.json: {str(e)}"
        #         )
        #         raise
        # else:
        #     self.scenario_config = {}

        self.logger = logger

    def load_scenario_config(self, scenario_name: str) -> Dict[str, Any]:
        """Load scenario configuration from a JSON file."""
        try:
            config_path = Path("config/test_scenarios") / f"{scenario_name}.json"
            with open(config_path, "r") as f:
                data = json.load(f)
                # Return the 'config' section if it exists, otherwise return the whole file
                return data.get("config", data)
        except Exception as e:
            logger.error(f"Failed to load scenario config: {str(e)}")
            raise

    @abstractmethod
    async def setup(self):
        """Setup test environment"""
        pass

    @abstractmethod
    async def execute(self):
        """Execute test scenario"""
        pass

    @abstractmethod
    async def cleanup(self):
        """Clean up after test"""
        pass

    async def run(self):
        """Run complete test scenario"""
        start_time = asyncio.get_event_loop().time()
        result = {"success": False, "details": None, "error": None, "duration": 0}
        try:
            self.logger.info(f"Starting test scenario: {self.scenario_name}")
            await self.setup()
            await self.execute()
            result.update({"success": True, "details": None})
        except Exception as e:
            self.logger.error(f"Test scenario failed: {str(e)}")
            result.update({"success": False, "error": str(e)})
        finally:
            try:
                await self.cleanup()
            except Exception as e:
                self.logger.error(f"Cleanup failed: {str(e)}")
            end_time = asyncio.get_event_loop().time()
            result["duration"] = round(end_time - start_time, 2)
        return result
