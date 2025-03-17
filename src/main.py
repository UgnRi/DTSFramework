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
    parser = argparse.ArgumentParser(description="Teltonika Router Test Framework")

    parser.add_argument(
        "--test-type",
        choices=["ssh", "api", "gui", "all"],
        default=None,
        help="Type of tests to run",
    )

    parser.add_argument(
        "--config",
        default="config/device_config.json",
        help="Path to device configuration file",
    )

    parser.add_argument(
        "--scenario-dir",
        default="config/test_scenarios",
        help="Directory containing scenario configuration files",
    )

    return parser.parse_args()


def load_scenario_file(scenario_dir: str, scenario_name: str) -> dict:
    """Load a scenario configuration file"""
    config_path = Path(scenario_dir) / f"{scenario_name}.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {config_path}")
    with open(config_path, "r") as f:
        data = json.load(f)

        # If scenario_name is not in the file, use the filename
        if "scenario_name" not in data:
            data["scenario_name"] = scenario_name

        # Ensure we return a dictionary with both scenario_name and config
        result = {
            "scenario_name": data.get("scenario_name", scenario_name),
            "config": data.get("config", {}),
        }
        return result


def get_test_class_name(test_dir: str, test_type: str) -> str:
    """Get the correct test class name based on directory and test type"""
    # Special handling for test types
    if test_type == "GUI":
        if test_dir == "mqtt_broker":
            return "MQTTBrokerGUITest"
        elif test_dir == "data_to_server":
            return "DataToServerGUITest"
    elif test_type == "SSH":
        if test_dir == "mqtt_broker":
            return "MQTTBrokerSSHTest"
        elif test_dir == "data_to_server":
            return "DataToServerSSHTest"
    elif test_type == "API":
        if test_dir == "mqtt_broker":
            return "MQTTBrokerAPITest"
        elif test_dir == "data_to_server":
            return "DataToServerAPITest"

    # Default format for other cases
    return f'{test_dir.title().replace("_", "")}{test_type}Test'


async def run_single_test(
    test_type: str, test_dir: str, device_config: dict, scenario_config: dict
):
    """Run a single test and return the test instance and result."""
    try:
        # Import the test module
        module = __import__(
            f"src.test_scenarios.{test_dir}.{test_type.lower()}_test", fromlist=[""]
        )
        class_name = get_test_class_name(test_dir, test_type.upper())
        test_class = getattr(module, class_name)

        # Create test instance
        test = test_class(device_config=device_config, scenario_config=scenario_config)

        # Run the test
        result = await test.run()

        # Extract scenario name safely
        scenario_name = ""
        if isinstance(scenario_config, dict):
            scenario_name = scenario_config.get("scenario_name", "")

        return {
            "test_instance": test,
            "result": {
                "scenario": f"{test_dir}_{test_type.lower()}_{scenario_name}",
                "status": "PASS" if result["success"] else "FAIL",
                "details": result["details"],
            },
            "success": result["success"],
        }
    except Exception as e:
        logger.error(f"Error in {test_dir} - {test_type} test: {str(e)}")

        # Extract scenario name safely
        scenario_name = ""
        if isinstance(scenario_config, dict):
            scenario_name = scenario_config.get("scenario_name", "")

        return {
            "test_instance": None,
            "result": {
                "scenario": f"{test_dir}_{test_type.lower()}_{scenario_name}",
                "status": "FAIL",
                "details": {"error": str(e)},
            },
            "success": False,
        }


async def run_gui_tests(
    device_config: dict,
    browser_context,
    scenarios: List[Tuple[str, dict]],
    validator: WirelessValidator,
):
    """Run GUI tests for specified scenarios with proper validation and cleanup sequence."""
    results = []

    # Ensure MQTT broker test runs first
    sorted_scenarios = sorted(scenarios, key=lambda x: x[0] != "mqtt_broker")

    # Track MQTT configuration for validation
    mqtt_config = None

    for test_dir, config in sorted_scenarios:
        logger.info(
            f"Running {test_dir} GUI test for scenario {config['scenario_name']}"
        )
        page = await browser_context.new_page()
        test = None

        try:
            # Import the test module
            module = __import__(
                f"src.test_scenarios.{test_dir}.gui_test", fromlist=[""]
            )
            class_name = get_test_class_name(test_dir, "GUI")
            test_class = getattr(module, class_name)

            # Create and run the test
            test = test_class(device_config, page, config)
            await test.setup()
            await test.execute()

            result = {
                "success": True,
                "details": f'{test_dir} configuration successful for {config["scenario_name"]}',
            }

            # For MQTT test, call logout explicitly after execute
            if test_dir == "mqtt_broker":
                try:
                    await test.logout()
                    logger.info("Successfully logged out after MQTT test")
                    # Store MQTT config for later validation
                    mqtt_config = config
                except Exception as logout_error:
                    logger.error(
                        f"Failed to logout after MQTT test: {str(logout_error)}"
                    )

            # Add result to results list
            results.append(
                {
                    "scenario": f'{test_dir}_gui_{config["scenario_name"]}',
                    "status": "PASS" if result["success"] else "FAIL",
                    "details": result["details"],
                }
            )

            # Run validation after DTS test
            if test_dir == "data_to_server" and mqtt_config:
                logger.info(
                    f"Running validation after GUI {config['scenario_name']} with MQTT config"
                )
                validation_result = await validator.validate_ap_config(
                    mqtt_config=mqtt_config, dts_config=config
                )

                # Add validation result
                results.append(
                    {
                        "scenario": f'validation_gui_{mqtt_config["scenario_name"]}_{config["scenario_name"]}',
                        "status": (
                            "PASS"
                            if validation_result.get("success", False)
                            else "FAIL"
                        ),
                        "details": validation_result,
                    }
                )

                logger.info(
                    f"GUI validation completed with success: {validation_result.get('success', False)}"
                )

            # Run cleanup after validation
            try:
                await test.cleanup()
                logger.info(
                    f"Cleanup completed for GUI test {test_dir} - {config['scenario_name']}"
                )
            except Exception as cleanup_error:
                logger.error(
                    f"Failed to cleanup GUI test {test_dir} - {config['scenario_name']}: {str(cleanup_error)}"
                )

        except Exception as e:
            logger.error(
                f"Error in {test_dir} - {config['scenario_name']} GUI test: {str(e)}"
            )
            results.append(
                {
                    "scenario": f'{test_dir}_gui_{config["scenario_name"]}',
                    "status": "FAIL",
                    "details": {"error": str(e)},
                }
            )

            # Attempt cleanup even if test failed
            if test:
                try:
                    await test.cleanup()
                    logger.info(
                        f"Cleanup completed for failed GUI test {test_dir} - {config['scenario_name']}"
                    )
                except Exception as cleanup_error:
                    logger.error(
                        f"Failed to cleanup failed GUI test {test_dir} - {config['scenario_name']}: {str(cleanup_error)}"
                    )
        finally:
            await page.close()
            await asyncio.sleep(2)  # Give time for browser operations to complete

    return results


async def main():
    args = parse_arguments()
    logger.info(f"Starting tests with arguments: {args}")

    # Load device configuration
    with open(args.config, "r") as f:
        device_config = json.load(f)

    # Get the scenarios to run from the device config
    mqtt_scenarios = device_config.get("mqtt_scenarios", [])
    dts_scenarios = device_config.get("dts_scenarios", [])

    if not mqtt_scenarios and not dts_scenarios:
        logger.warning(
            "No scenarios defined in configuration. Please check your device_config.json."
        )
        return

    # Load all scenarios
    loaded_scenarios = []

    # Load all MQTT scenarios
    for mqtt_scenario in mqtt_scenarios:
        try:
            mqtt_config = load_scenario_file(args.scenario_dir, mqtt_scenario)
            loaded_scenarios.append(("mqtt_broker", mqtt_config))
            logger.info(f"Loaded MQTT scenario: {mqtt_scenario}")
        except Exception as e:
            logger.error(f"Error loading MQTT scenario {mqtt_scenario}: {str(e)}")

    # Load all DTS scenarios
    for dts_scenario in dts_scenarios:
        try:
            dts_config = load_scenario_file(args.scenario_dir, dts_scenario)
            loaded_scenarios.append(("data_to_server", dts_config))
            logger.info(f"Loaded DTS scenario: {dts_scenario}")
        except Exception as e:
            logger.error(f"Error loading DTS scenario {dts_scenario}: {str(e)}")

    if not loaded_scenarios:
        logger.error("No valid scenarios were loaded. Check your configuration files.")
        return

    # Generate result file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = (
        f"{device_config['device']['name']}_{timestamp}_"
        f"{device_config['device']['modem']}_{device_config['device']['firmware']}.csv"
    )

    # Store all test results
    results = []

    # Determine test type (default to "all" if not specified)
    effective_test_type = args.test_type if args.test_type is not None else "all"

    try:
        # Create validator instance
        validator = WirelessValidator(device_config, test_type=effective_test_type)

        # 1. Run GUI tests if requested (includes their own validation and cleanup)
        if effective_test_type in ["gui", "all"]:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.firefox.launch(
                    headless=False,
                    slow_mo=100,
                    args=["--ignore-certificate-errors", "--disable-web-security"],
                )

                browser_context = await browser.new_context(
                    ignore_https_errors=True,
                    viewport={"width": 1920, "height": 1080},
                    accept_downloads=True,
                )

                browser_context.set_default_timeout(5000)

                try:
                    gui_results = await run_gui_tests(
                        device_config, browser_context, loaded_scenarios, validator
                    )
                    results.extend(gui_results)
                finally:
                    await browser_context.close()
                    await browser.close()

        # 2. Run SSH tests if requested
        if effective_test_type in ["ssh", "all"]:
            # Group scenarios by type
            mqtt_loaded = [s for s in loaded_scenarios if s[0] == "mqtt_broker"]
            dts_loaded = [s for s in loaded_scenarios if s[0] == "data_to_server"]

            # Store MQTT config for validation
            mqtt_config = None
            if mqtt_loaded:
                mqtt_config = mqtt_loaded[-1][1]

            # Run MQTT broker SSH test first
            if mqtt_loaded:
                latest_mqtt_scenario = mqtt_loaded[-1][1]

                # Run the MQTT SSH test and get the result
                logger.info(
                    f"Running MQTT broker SSH test for scenario {latest_mqtt_scenario.get('scenario_name', '')}"
                )
                mqtt_ssh_result = await run_single_test(
                    "ssh", "mqtt_broker", device_config, latest_mqtt_scenario
                )

                # Add the result to results list
                results.append(mqtt_ssh_result["result"])

                # Store the test instance for cleanup after validation
                mqtt_ssh_test = mqtt_ssh_result["test_instance"]

                # Run DTS SSH test next
                if dts_loaded:
                    latest_dts_scenario = dts_loaded[-1][1]

                    # Run the DTS SSH test and get the result
                    logger.info(
                        f"Running Data to Server SSH test for scenario {latest_dts_scenario.get('scenario_name', '')}"
                    )
                    dts_ssh_result = await run_single_test(
                        "ssh", "data_to_server", device_config, latest_dts_scenario
                    )

                    # Add the result to results list
                    results.append(dts_ssh_result["result"])

                    # Store the test instance for cleanup after validation
                    dts_ssh_test = dts_ssh_result["test_instance"]

                    # Run validation after both SSH tests are complete
                    logger.info(
                        f"Running validation for SSH tests with MQTT and DTS configs"
                    )
                    validation_result = await validator.validate_ap_config(
                        mqtt_config=latest_mqtt_scenario, dts_config=latest_dts_scenario
                    )

                    # Add validation result
                    results.append(
                        {
                            "scenario": f'validation_ssh_{latest_mqtt_scenario.get("scenario_name", "")}_{latest_dts_scenario.get("scenario_name", "")}',
                            "status": (
                                "PASS"
                                if validation_result.get("success", False)
                                else "FAIL"
                            ),
                            "details": validation_result,
                        }
                    )

                    logger.info(
                        f"SSH validation completed with success: {validation_result.get('success', False)}"
                    )

                    # Clean up the tests after validation
                    if dts_ssh_test:
                        try:
                            await dts_ssh_test.cleanup()
                            logger.info("Cleanup completed for Data to Server SSH test")
                        except Exception as e:
                            logger.error(
                                f"Failed to cleanup Data to Server SSH test: {str(e)}"
                            )

                # Clean up MQTT test
                if mqtt_ssh_test:
                    try:
                        await mqtt_ssh_test.cleanup()
                        logger.info("Cleanup completed for MQTT broker SSH test")
                    except Exception as e:
                        logger.error(
                            f"Failed to cleanup MQTT broker SSH test: {str(e)}"
                        )

        # 3. Run API tests if requested
        if effective_test_type in ["api", "all"]:
            # Group scenarios by type
            mqtt_loaded = [s for s in loaded_scenarios if s[0] == "mqtt_broker"]
            dts_loaded = [s for s in loaded_scenarios if s[0] == "data_to_server"]

            # Store MQTT config for validation
            mqtt_config = None
            if mqtt_loaded:
                mqtt_config = mqtt_loaded[-1][1]

            # Run MQTT broker API test first
            if mqtt_loaded:
                latest_mqtt_scenario = mqtt_loaded[-1][1]

                # Run the MQTT API test and get the result
                logger.info(
                    f"Running MQTT broker API test for scenario {latest_mqtt_scenario.get('scenario_name', '')}"
                )
                mqtt_api_result = await run_single_test(
                    "api", "mqtt_broker", device_config, latest_mqtt_scenario
                )

                # Add the result to results list
                results.append(mqtt_api_result["result"])

                # Store the test instance for cleanup after validation
                mqtt_api_test = mqtt_api_result["test_instance"]

                # Run DTS API test next
                if dts_loaded:
                    latest_dts_scenario = dts_loaded[-1][1]

                    # Run the DTS API test and get the result
                    logger.info(
                        f"Running Data to Server API test for scenario {latest_dts_scenario.get('scenario_name', '')}"
                    )
                    dts_api_result = await run_single_test(
                        "api", "data_to_server", device_config, latest_dts_scenario
                    )

                    # Add the result to results list
                    results.append(dts_api_result["result"])

                    # Store the test instance for cleanup after validation
                    dts_api_test = dts_api_result["test_instance"]

                    # Run validation after both API tests are complete
                    logger.info(
                        f"Running validation for API tests with MQTT and DTS configs"
                    )
                    validation_result = await validator.validate_ap_config(
                        mqtt_config=latest_mqtt_scenario, dts_config=latest_dts_scenario
                    )

                    # Add validation result
                    results.append(
                        {
                            "scenario": f'validation_api_{latest_mqtt_scenario.get("scenario_name", "")}_{latest_dts_scenario.get("scenario_name", "")}',
                            "status": (
                                "PASS"
                                if validation_result.get("success", False)
                                else "FAIL"
                            ),
                            "details": validation_result,
                        }
                    )

                    logger.info(
                        f"API validation completed with success: {validation_result.get('success', False)}"
                    )

                    # Clean up the tests after validation
                    if dts_api_test:
                        try:
                            await dts_api_test.cleanup()
                            logger.info("Cleanup completed for Data to Server API test")
                        except Exception as e:
                            logger.error(
                                f"Failed to cleanup Data to Server API test: {str(e)}"
                            )

                # Clean up MQTT test
                if mqtt_api_test:
                    try:
                        await mqtt_api_test.cleanup()
                        logger.info("Cleanup completed for MQTT broker API test")
                    except Exception as e:
                        logger.error(
                            f"Failed to cleanup MQTT broker API test: {str(e)}"
                        )

        # Write results
        result_writer = ResultWriter(result_file)
        result_writer.write_results(results)

        # Log summary
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r["status"] == "PASS")
        logger.info(
            f"Test execution completed. "
            f"Total: {total_tests}, Passed: {passed_tests}, "
            f"Failed: {total_tests - passed_tests}"
        )

    except Exception as e:
        logger.error(f"Test execution failed: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
