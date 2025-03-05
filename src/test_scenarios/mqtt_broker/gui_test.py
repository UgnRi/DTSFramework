from src.test_scenarios.base_gui_test import BaseGUITest
from src.ui.pages.broker_page import BrokerPage
from src.ui.pages.login_page import LoginPage
from src.utils.logger import setup_logger
from typing import Dict, Any

logger = setup_logger()

class MQTTBrokerGUITest(BaseGUITest):
    def __init__(self, device_config, page, scenario_config=None):
        super().__init__(
            device_config=device_config,
            scenario_name='mqtt_broker',
            page=page
        )
        self.scenario_config = scenario_config or {}
        self.broker_page = BrokerPage(page, device_config)

    async def setup(self):
        """Setup test environment"""
        try:
            await self.login_page.login(
                self.device_config['device']['credentials']['username'],
                self.device_config['device']['credentials']['password']
            )
            await self.broker_page.navigate()
        except Exception as e:
            self.logger.error(f"Failed to setup MQTT broker test: {str(e)}")
            raise

    async def execute(self):
        """Configure MQTT broker via GUI"""
        try:
            # Extract the nested config
            mqtt_config = self.scenario_config.get('config', {})
            
            # Pass the extracted config
            await self.broker_page.add_mqtt_broker(config=mqtt_config)
            
            self.logger.info("MQTT broker configured via GUI")
        except Exception as e:
            self.logger.error(f"Failed to configure MQTT broker via GUI: {str(e)}")
            raise

    async def cleanup(self):
        """No specific cleanup needed for MQTT broker"""
        pass