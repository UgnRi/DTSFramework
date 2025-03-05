import asyncio
import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import List, Dict, Tuple
from src.backend.validators import WirelessValidator
from src.utils.logger import setup_logger
from src.utils.result_writer import ResultWriter

logger = setup_logger()

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Teltonika Router Test Framework')
    
    parser.add_argument(
        '--test-type',
        choices=['ssh', 'api', 'gui', 'all'],
        default='all',
        help='Type of tests to run'
    )
    
    parser.add_argument(
        '--mqtt-scenario',
        help='MQTT Broker scenario configuration file name (without extension)'
    )
    
    parser.add_argument(
        '--dts-scenario',
        help='Data to Server scenario configuration file name (without extension)'
    )
    
    parser.add_argument(
        '--config',
        default='config/device_config.json',
        help='Path to device configuration file'
    )
    
    parser.add_argument(
        '--scenario-dir',
        default='config/test_scenarios',
        help='Directory containing scenario configuration files'
    )
    
    return parser.parse_args()

def load_scenario_file(scenario_dir: str, scenario_name: str) -> dict:
    """Load a scenario configuration file"""
    config_path = Path(scenario_dir) / f"{scenario_name}.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {config_path}")
    with open(config_path, 'r') as f:
        data = json.load(f)
        
        # If scenario_name is not in the file, use the filename
        if 'scenario_name' not in data:
            data['scenario_name'] = scenario_name

        return {
            'scenario_name': data['scenario_name'],
            'config': data['config']
        }

def get_test_class_name(test_dir: str, test_type: str) -> str:
    """Get the correct test class name based on directory and test type"""
    # Special handling for test types
    if test_type == 'GUI':
        if test_dir == 'mqtt_broker':
            return 'MQTTBrokerGUITest'
        elif test_dir == 'data_to_server':
            return 'DataToServerGUITest'
    elif test_type == 'SSH':
        if test_dir == 'mqtt_broker':
            return 'MQTTBrokerSSHTest'
        elif test_dir == 'data_to_server':
            return 'DataToServerSSHTest'
    elif test_type == 'API':
        if test_dir == 'mqtt_broker':
            return 'MQTTBrokerAPITest'
        elif test_dir == 'data_to_server':
            return 'DataToServerAPITest'
            
    # Default format for other cases
    return f'{test_dir.title().replace("_", "")}{test_type}Test'

async def run_tests_for_scenario(test_type: str, test_dir: str, device_config: dict, scenario_config: dict):
    """Run specified test type for a given scenario"""
    results = []
    
    if test_type in ['ssh', 'all']:
        module = __import__(f'src.test_scenarios.{test_dir}.ssh_test', fromlist=[''])
        class_name = get_test_class_name(test_dir, 'SSH')
        test_class = getattr(module, class_name)
        
        # Pass the entire scenario_config, just like in GUI tests
        test = test_class(device_config=device_config, scenario_config=scenario_config)
        result = await test.run()
        results.append({
            'scenario': f'{test_dir}_ssh',
            'status': 'PASS' if result['success'] else 'FAIL',
            'details': result['details']
        })
    
    if test_type in ['api', 'all']:
        module = __import__(f'src.test_scenarios.{test_dir}.api_test', fromlist=[''])
        class_name = get_test_class_name(test_dir, 'API')
        test_class = getattr(module, class_name)
        
        # Pass the entire scenario_config, just like in GUI tests
        test = test_class(device_config=device_config, scenario_config=scenario_config)
        result = await test.run()
        results.append({
            'scenario': f'{test_dir}_api',
            'status': 'PASS' if result['success'] else 'FAIL',
            'details': result['details']
        })
    
    return results

async def run_gui_tests(device_config: dict, browser_context, scenarios: List[Tuple[str, dict]], validator: WirelessValidator):
    """Run GUI tests for specified scenarios"""
    results = []
    
    # Ensure MQTT broker test runs first
    sorted_scenarios = sorted(scenarios, key=lambda x: x[0] != 'mqtt_broker')
    
    for test_dir, config in sorted_scenarios:
        logger.info(f"Running {test_dir} GUI tests")
        page = await browser_context.new_page()
        test = None
        
        try:
            module = __import__(f'src.test_scenarios.{test_dir}.gui_test', fromlist=[''])
            class_name = get_test_class_name(test_dir, 'GUI')
            test_class = getattr(module, class_name)
            
            test = test_class(device_config, page, config)
            
            # Run setup and execute separately
            await test.setup()
            await test.execute()
            
            result = {'success': True, 'details': f'{test_dir} configuration successful'}
            
            # For MQTT test, call logout explicitly after execute
            if test_dir == 'mqtt_broker':
                try:
                    await test.logout()
                    logger.info("Successfully logged out after MQTT test")
                except Exception as logout_error:
                    logger.error(f"Failed to logout after MQTT test: {str(logout_error)}")
            
            # Run validation before cleanup on the last test
            if test_dir == scenarios[-1][0]:
                mqtt_config = next((cfg for td, cfg in scenarios if td == 'mqtt_broker'), {})
                dts_config = next((cfg for td, cfg in scenarios if td == 'data_to_server'), {})
                
                logger.info("Running validation checks...")
                validation_result = await validator.validate_ap_config(
                    mqtt_config=mqtt_config,
                    dts_config=dts_config
                )
                result['success'] = result['success'] and validation_result['success']
                logger.info(f"Validation completed with success: {validation_result['success']}")
            
            results.append({
                'scenario': f'{test_dir}_gui',
                'status': 'PASS' if result['success'] else 'FAIL',
                'details': result['details']
            })
            
            # Now perform cleanup after validation
            if test:
                try:
                    await test.cleanup()
                    logger.info(f"Cleanup completed for {test_dir}")
                except Exception as e:
                    logger.error(f"Failed to cleanup {test_dir} test: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error in {test_dir} GUI test: {str(e)}")
            results.append({
                'scenario': f'{test_dir}_gui',
                'status': 'FAIL',
                'details': {'error': str(e)}
            })
            
        finally:
            await page.close()
            await asyncio.sleep(2)
    
    return results


async def main():
    args = parse_arguments()
    logger.info(f"Starting tests with arguments: {args}")
    
    # Load device configuration
    with open(args.config, 'r') as f:
        device_config = json.load(f)
    
    # Create list of scenarios to run
    scenarios = []
    
    # Load MQTT scenario if specified
    if args.mqtt_scenario:
        try:
            mqtt_config = load_scenario_file(args.scenario_dir, args.mqtt_scenario)
            scenarios.append(('mqtt_broker', mqtt_config))
        except Exception as e:
            logger.error(f"Error loading MQTT scenario: {str(e)}")
            raise
    
    # Load DTS scenario if specified
    if args.dts_scenario:
        try:
            dts_config = load_scenario_file(args.scenario_dir, args.dts_scenario)
            scenarios.append(('data_to_server', dts_config))
        except Exception as e:
            logger.error(f"Error loading DTS scenario: {str(e)}")
            raise
    
    if not scenarios:
        raise ValueError("No scenarios specified. Please provide --mqtt-scenario and/or --dts-scenario")
    
    # Generate result file name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = f"{device_config['device']['name']}_{timestamp}_" \
                 f"{device_config['device']['modem']}_{device_config['device']['firmware']}.csv"
    
    results = []
    
    try:
        # Create validator instance
        validator = WirelessValidator(device_config)
        
        # Run GUI tests if requested
        if args.test_type in ['gui', 'all']:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.firefox.launch(
                    headless=False,
                    slow_mo=100,
                    args=['--ignore-certificate-errors', '--disable-web-security']
                )
                
                browser_context = await browser.new_context(
                    ignore_https_errors=True,
                    viewport={'width': 1920, 'height': 1080},
                    accept_downloads=True
                )
                
                browser_context.set_default_timeout(5000)
                
                try:
                    gui_results = await run_gui_tests(
                        device_config,
                        browser_context,
                        scenarios,
                        validator
                    )
                    results.extend(gui_results)
                finally:
                    await browser_context.close()
                    await browser.close()
        
        # Run SSH and API tests if requested
        for test_dir, config in scenarios:
            if args.test_type in ['ssh', 'api', 'all']:
                scenario_results = await run_tests_for_scenario(
                    args.test_type,
                    test_dir,
                    device_config,
                    config
                )
                results.extend(scenario_results)
                # Add validation for the last scenario, similar to GUI tests
                if test_dir == scenarios[-1][0]:
                    mqtt_config = next((cfg for td, cfg in scenarios if td == 'mqtt_broker'), {})
                    dts_config = next((cfg for td, cfg in scenarios if td == 'data_to_server'), {})
                    
                    logger.info("Running validation checks...")
                    validation_result = await validator.validate_ap_config(
                        mqtt_config=mqtt_config,
                        dts_config=dts_config
                    )
                    
                    # Update the last test result based on validation
                    if results:
                        last_result = results[-1]
                        
                        # Ensure validation_result is a dictionary
                        if not isinstance(validation_result, dict):
                            validation_result = {
                                'success': False,
                                'details': str(validation_result)
                            }
                        
                        last_result['status'] = 'PASS' if validation_result.get('success', False) else 'FAIL'
                        last_result['details'] = validation_result
                    
                    logger.info(f"Validation completed with success: {validation_result.get('success', False)}")
        
        # Write results
        result_writer = ResultWriter(result_file)
        result_writer.write_results(results)
        
        # Log summary
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r['status'] == 'PASS')
        logger.info(f"Test execution completed. "
                   f"Total: {total_tests}, Passed: {passed_tests}, "
                   f"Failed: {total_tests - passed_tests}")
        
    except Exception as e:
        logger.error(f"Test execution failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())