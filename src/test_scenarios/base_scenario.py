# src/test_scenarios/base_scenario.py
from abc import ABC, abstractmethod
from typing import Dict, Any
import asyncio
from src.utils.logger import setup_logger
from src.utils.config_loader import load_scenario_config

logger = setup_logger()

class BaseTestScenario(ABC):
    def __init__(self, device_config: Dict[str, Any], scenario_name: str):
        self.device_config = device_config
        self.scenario_name = scenario_name
        self.scenario_config = load_scenario_config(scenario_name)
        self.logger = logger

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
        result = {
            'success': False,
            'details': None,
            'error': None,
            'duration': 0
        }

        try:
            self.logger.info(f"Starting test scenario: {self.scenario_name}")
            await self.setup()
            await self.execute()
            result.update({
                'success': True,
                'details': None
            })

        except Exception as e:
            self.logger.error(f"Test scenario failed: {str(e)}")
            result.update({
                'success': False,
                'error': str(e)
            })
        finally:
            try:
                await self.cleanup()
            except Exception as e:
                self.logger.error(f"Cleanup failed: {str(e)}")

            end_time = asyncio.get_event_loop().time()
            result['duration'] = round(end_time - start_time, 2)

        return result