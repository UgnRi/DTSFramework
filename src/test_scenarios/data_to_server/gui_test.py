from src.utils.logger import setup_logger
from src.test_scenarios.base_gui_test import BaseGUITest
from src.ui.pages.data_to_server_page import DTSPage
from src.ui.pages.login_page import LoginPage
from src.ui.pages.clean_up import CleanUp
from typing import Dict, Any

logger = setup_logger()


class DataToServerGUITest(BaseGUITest):
    def __init__(self, device_config: Dict[str, Any], page, scenario_config=None):
        super().__init__(
            device_config=device_config, 
            scenario_name='data_to_server', 
            page=page
        )
        self.scenario_config = scenario_config or {}
        self.dts_page = DTSPage(page, device_config)
        self.login_page = LoginPage(page, device_config)
        self.cleanup_handler = CleanUp(page)
        
    async def run(self, perform_cleanup=True):
        """
        Run the Data to Server GUI test
        
        :param perform_cleanup: Flag to control whether cleanup is performed
        :return: Test result dictionary
        """
        try:
            # Setup test environment
            await self.setup()
            
            # Execute configuration
            await self.execute()
            
            # Return success result
            result = {
                'success': True, 
                'details': 'Data to Server configuration successful'
            }
            
            # Only perform cleanup if explicitly requested
            if perform_cleanup:
                await self.cleanup()
            
            return result
        
        except Exception as e:
            # Log and return failure result
            self.logger.error(f"Data to Server GUI test failed: {str(e)}")
            return {
                'success': False, 
                'details': str(e)
            }

    async def setup(self):
        """Setup test environment"""
        try:
            # Login first
            await self.login_page.login(
                self.device_config['device']['credentials']['username'],
                self.device_config['device']['credentials']['password']
            )
            
            # Navigate to DTS page with retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await self.dts_page.navigate()
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    self.logger.warning(f"Navigation attempt {attempt + 1} failed: {str(e)}")
                    await self.page.wait_for_timeout(5000)  # Wait 5 seconds before retry
                
        except Exception as e:
            self.logger.error(f"Failed to setup Data to Server test: {str(e)}")
            raise
            
    async def execute(self):
        """Configure Data to Server via GUI"""
        try:
            # Prepare the configuration dictionary

            scenario_config = self.scenario_config.get('config', {})

            config = {
                'instanceName': scenario_config['instanceName'],
                'data_config': {
                    'name': scenario_config['data_config']['name'],
                    'type': scenario_config['data_config']['type'],
                    'type_settings': scenario_config['data_config']['type_settings'],
                    'format_type': scenario_config['data_config']['format_type'],
                    'values': scenario_config['data_config']['values']
                },
                'server_config': {
                    'server_address': scenario_config['server_config']['server_address'],
                    'port': scenario_config['server_config']['port'],
                    'keepalive': scenario_config['server_config']['keepalive'],
                    'topic': scenario_config['server_config']['topic'],
                    'client_id': scenario_config['server_config']['client_id'],
                    'QoS': scenario_config['server_config']['QoS'],
                    'enable_secure_connection': scenario_config['server_config'].get('enable_secure_connection', False),
                    'use_credentials': scenario_config['server_config'].get('use_credentials', False),
                    'username': scenario_config['server_config'].get('username'),
                    'password': scenario_config['server_config'].get('password')
                }
            }

            # Add collection configuration based on the timer type
            if 'collection_config' in scenario_config:
                if 'day_time' in scenario_config['collection_config']:
                    # Scheduler-based configuration
                    config['collection_config-scheduler'] = {
                        'timer': scenario_config['collection_config']['timer'],
                        'day_time': scenario_config['collection_config']['day_time'],
                        'interval_type': scenario_config['collection_config']['interval_type'],
                        'month_day': scenario_config['collection_config']['month_day'],
                        'weekdays': scenario_config['collection_config']['weekdays'],
                        'force_last_day': scenario_config['collection_config'].get('force_last_day', False),
                        'retry': scenario_config['collection_config'].get('retry', False),
                        'retry_count': scenario_config['collection_config']['retry_count'],
                        'timeout': scenario_config['collection_config']['timeout']
                    }
                elif 'period' in scenario_config['collection_config']:
                    # Period-based configuration
                    config['collection_config-period'] = {
                        'period': scenario_config['collection_config']['period'],
                        'retry': scenario_config['collection_config'].get('retry', False)
                    }

            # Optional: Add secure connection details if enabled
            if config['server_config']['enable_secure_connection']:
                secure_connection = {
                    'allow_insecure_connection': scenario_config['server_config']['secure_connection'].get('allow_insecure_connection', False),
                    'certificate_files_from_device': scenario_config['server_config']['secure_connection'].get('certificate_files_from_device', False)
                }

                # Add device certificate paths
                if 'device_certificates' in scenario_config['server_config']['secure_connection']:
                    secure_connection['device_certificates'] = {
                        'certificate_authority_file': scenario_config['server_config']['secure_connection']['device_certificates']['certificate_authority_file'],
                        'client_certificate': scenario_config['server_config']['secure_connection']['device_certificates']['client_certificate'],
                        'client_private_keyfile': scenario_config['server_config']['secure_connection']['device_certificates']['client_private_keyfile']
                    }
                
                # Add upload certificate paths
                secure_connection['upload_certificates'] = {
                    'certificate_authority_file': scenario_config['server_config']['secure_connection']['certificate_authority_file'],
                    'client_certificate': scenario_config['server_config']['secure_connection']['client_certificate'],
                    'client_private_keyfile': scenario_config['server_config']['secure_connection']['client_private_keyfile']
                }

                config['server_config']['secure_connection'] = secure_connection
            # Navigate to the page and configure
            await self.dts_page.navigate()
            await self.dts_page.configure_dts(config)

            self.logger.info("Data to Server configured via GUI")
        except Exception as e:
            self.logger.error(f"Failed to configure Data to Server via GUI: {str(e)}")
            raise
        

    async def cleanup(self):
        """
        Perform cleanup using CleanUp class
        """
        try:
            deleted = await self.cleanup_handler.delete_wifi_interface()
            if deleted:
                logger.info("Cleanup successful: Deleted all WiFi interfaces.")
            else:
                logger.warning("Cleanup completed: No interfaces deleted or encountered issues.")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")