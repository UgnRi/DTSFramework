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


async def run_gui_test_pair(
    device_config: dict,
    browser_context,
    mqtt_scenario: dict,
    dts_scenario: dict,
    validator: WirelessValidator,
):
    """Run a pair of GUI tests (MQTT and DTS), followed by validation and cleanup"""
    results = []
    mqtt_test = None
    dts_test = None
    mqtt_page = None
    dts_page = None

    try:
        # Run MQTT Broker GUI test first
        logger.info(
            f"Running mqtt_broker GUI test for scenario {mqtt_scenario['scenario_name']}"
        )
        mqtt_page = await browser_context.new_page()

        try:
            # Import and create MQTT test
            mqtt_module = __import__(
                f"src.test_scenarios.mqtt_broker.gui_test", fromlist=[""]
            )
            mqtt_class_name = get_test_class_name("mqtt_broker", "GUI")
            mqtt_test_class = getattr(mqtt_module, mqtt_class_name)
            mqtt_test = mqtt_test_class(device_config, mqtt_page, mqtt_scenario)

            # Run MQTT test
            await mqtt_test.setup()
            await mqtt_test.execute()

            # Logout from MQTT test
            await mqtt_test.logout()
            logger.info("Successfully logged out after MQTT test")

            # Add MQTT result
            results.append(
                {
                    "scenario": f"mqtt_broker_gui_{mqtt_scenario['scenario_name']}",
                    "status": "PASS",
                    "details": f"mqtt_broker configuration successful for {mqtt_scenario['scenario_name']}",
                }
            )

            # Run DTS test next
            logger.info(
                f"Running data_to_server GUI test for scenario {dts_scenario['scenario_name']}"
            )
            dts_page = await browser_context.new_page()

            try:
                # Import and create DTS test
                dts_module = __import__(
                    f"src.test_scenarios.data_to_server.gui_test", fromlist=[""]
                )
                dts_class_name = get_test_class_name("data_to_server", "GUI")
                dts_test_class = getattr(dts_module, dts_class_name)
                dts_test = dts_test_class(device_config, dts_page, dts_scenario)

                # Run DTS test
                await dts_test.setup()
                await dts_test.execute()

                # Add DTS result
                results.append(
                    {
                        "scenario": f"data_to_server_gui_{dts_scenario['scenario_name']}",
                        "status": "PASS",
                        "details": f"data_to_server configuration successful for {dts_scenario['scenario_name']}",
                    }
                )

                # Run validation after both tests complete
                logger.info(
                    f"Running validation after GUI tests for {mqtt_scenario['scenario_name']} and {dts_scenario['scenario_name']}"
                )
                validation_result = await validator.validate_ap_config(
                    mqtt_config=mqtt_scenario, dts_config=dts_scenario
                )

                # Add validation result
                results.append(
                    {
                        "scenario": f"validation_gui_{mqtt_scenario['scenario_name']}_{dts_scenario['scenario_name']}",
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

            except Exception as dts_error:
                logger.error(f"Error in data_to_server GUI test: {str(dts_error)}")
                results.append(
                    {
                        "scenario": f"data_to_server_gui_{dts_scenario['scenario_name']}",
                        "status": "FAIL",
                        "details": {"error": str(dts_error)},
                    }
                )
            finally:
                # Skip DTS cleanup - clients were already removed
                # Instead, just log that we're skipping it
                logger.info(
                    f"Skipping DTS test cleanup to avoid errors with already removed clients"
                )

                # Close DTS page
                if dts_page:
                    try:
                        logger.info("Closing data_to_server page")
                        await dts_page.close()
                        dts_page = None
                        logger.info("Closed data_to_server page successfully")
                    except Exception as e:
                        logger.error(f"Error closing data_to_server page: {str(e)}")

        except Exception as mqtt_error:
            logger.error(f"Error in mqtt_broker GUI test: {str(mqtt_error)}")
            results.append(
                {
                    "scenario": f"mqtt_broker_gui_{mqtt_scenario['scenario_name']}",
                    "status": "FAIL",
                    "details": {"error": str(mqtt_error)},
                }
            )
        finally:
            # Skip MQTT cleanup as well - just close the page
            logger.info(
                f"Skipping MQTT test cleanup to avoid errors with already removed clients"
            )

            # Close MQTT page
            if mqtt_page:
                try:
                    logger.info("Closing mqtt_broker page")
                    await mqtt_page.close()
                    mqtt_page = None
                    logger.info("Closed mqtt_broker page successfully")
                except Exception as e:
                    logger.error(f"Error closing mqtt_broker page: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error in GUI test pair: {str(e)}")
        # Make sure to close any pages that might be open
        if dts_page:
            try:
                await dts_page.close()
                logger.info("Closed data_to_server page in exception handler")
            except:
                pass
        if mqtt_page:
            try:
                await mqtt_page.close()
                logger.info("Closed mqtt_broker page in exception handler")
            except:
                pass

    # Give a little time to ensure all browser operations are completed
    await asyncio.sleep(1)

    return results


async def run_test_pair(
    test_type: str,
    device_config: dict,
    mqtt_scenario: dict,
    dts_scenario: dict,
    validator: WirelessValidator,
):
    """Run a pair of tests (MQTT + DTS) of specified type, followed by validation and cleanup"""
    results = []
    mqtt_test = None
    dts_test = None

    # Run MQTT test
    logger.info(
        f"Running MQTT broker {test_type} test for scenario {mqtt_scenario['scenario_name']}"
    )
    mqtt_result = await run_single_test(
        test_type, "mqtt_broker", device_config, mqtt_scenario
    )
    results.append(mqtt_result["result"])
    mqtt_test = mqtt_result["test_instance"]

    # Run DTS test
    logger.info(
        f"Running Data to Server {test_type} test for scenario {dts_scenario['scenario_name']}"
    )
    dts_result = await run_single_test(
        test_type, "data_to_server", device_config, dts_scenario
    )
    results.append(dts_result["result"])
    dts_test = dts_result["test_instance"]

    # Run validation if both tests were successful
    if mqtt_test and dts_test:
        logger.info(
            f"Running validation for {test_type} tests with {mqtt_scenario['scenario_name']} and {dts_scenario['scenario_name']}"
        )
        try:
            validation_result = await validator.validate_ap_config(
                mqtt_config=mqtt_scenario, dts_config=dts_scenario
            )

            # Add validation result
            results.append(
                {
                    "scenario": f"validation_{test_type}_{mqtt_scenario['scenario_name']}_{dts_scenario['scenario_name']}",
                    "status": (
                        "PASS" if validation_result.get("success", False) else "FAIL"
                    ),
                    "details": validation_result,
                }
            )

            logger.info(
                f"{test_type.upper()} validation completed with success: {validation_result.get('success', False)}"
            )
        except Exception as validation_error:
            logger.error(
                f"Validation failed for {test_type} tests: {str(validation_error)}"
            )
            results.append(
                {
                    "scenario": f"validation_{test_type}_{mqtt_scenario['scenario_name']}_{dts_scenario['scenario_name']}",
                    "status": "FAIL",
                    "details": {"error": str(validation_error)},
                }
            )

    # Cleanup tests
    if dts_test:
        try:
            await dts_test.cleanup()
            logger.info(
                f"Cleanup completed for Data to Server {test_type} test - {dts_scenario['scenario_name']}"
            )
        except Exception as e:
            logger.error(f"Failed to cleanup Data to Server {test_type} test: {str(e)}")

    if mqtt_test:
        try:
            await mqtt_test.cleanup()
            logger.info(
                f"Cleanup completed for MQTT broker {test_type} test - {mqtt_scenario['scenario_name']}"
            )
        except Exception as e:
            logger.error(f"Failed to cleanup MQTT broker {test_type} test: {str(e)}")

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
    mqtt_configs = []
    dts_configs = []

    # Load all MQTT scenarios
    for mqtt_scenario in mqtt_scenarios:
        try:
            mqtt_config = load_scenario_file(args.scenario_dir, mqtt_scenario)
            mqtt_configs.append(mqtt_config)
            logger.info(f"Loaded MQTT scenario: {mqtt_scenario}")
        except Exception as e:
            logger.error(f"Error loading MQTT scenario {mqtt_scenario}: {str(e)}")

    # Load all DTS scenarios
    for dts_scenario in dts_scenarios:
        try:
            dts_config = load_scenario_file(args.scenario_dir, dts_scenario)
            dts_configs.append(dts_config)
            logger.info(f"Loaded DTS scenario: {dts_scenario}")
        except Exception as e:
            logger.error(f"Error loading DTS scenario {dts_scenario}: {str(e)}")

    if not mqtt_configs or not dts_configs:
        logger.error(
            "Both MQTT and DTS scenarios are required. Check your configuration files."
        )
        return

    # Make sure we have equal numbers of scenario pairs, or warn about mismatched counts
    if len(mqtt_configs) != len(dts_configs):
        logger.warning(
            f"Mismatched scenario counts: {len(mqtt_configs)} MQTT scenarios and {len(dts_configs)} DTS scenarios. "
            f"Will run pairs until one type runs out."
        )

    # Determine how many pairs we have
    num_pairs = min(len(mqtt_configs), len(dts_configs))
    logger.info(f"Will run {num_pairs} scenario pairs")

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

        # Run tests for each pair of scenarios
        for pair_index in range(num_pairs):
            mqtt_scenario = mqtt_configs[pair_index]
            dts_scenario = dts_configs[pair_index]

            logger.info(
                f"Running tests for scenario pair {pair_index+1}/{num_pairs}: "
                f"MQTT={mqtt_scenario['scenario_name']}, DTS={dts_scenario['scenario_name']}"
            )

            # 1. Run GUI tests if requested
            if effective_test_type in ["gui", "all"]:
                from playwright.async_api import async_playwright

                async with async_playwright() as p:
                    browser = None
                    browser_context = None

                    try:
                        # Launch browser with explicit cleanup handling
                        logger.info("Launching browser for GUI tests")
                        browser = await p.firefox.launch(
                            headless=False,
                            slow_mo=100,
                            args=[
                                "--ignore-certificate-errors",
                                "--disable-web-security",
                            ],
                        )

                        browser_context = await browser.new_context(
                            ignore_https_errors=True,
                            viewport={"width": 1920, "height": 1080},
                            accept_downloads=True,
                        )

                        browser_context.set_default_timeout(5000)

                        gui_results = await run_gui_test_pair(
                            device_config,
                            browser_context,
                            mqtt_scenario,
                            dts_scenario,
                            validator,
                        )
                        results.extend(gui_results)

                    except Exception as browser_error:
                        logger.error(
                            f"Error during GUI test execution: {str(browser_error)}"
                        )

                    finally:
                        # Ensure proper browser context and browser cleanup
                        logger.info("Cleaning up browser resources...")

                        # Close all pages first
                        if browser_context:
                            try:
                                pages = await browser_context.pages()
                                logger.info(f"Found {len(pages)} pages to close")
                                for idx, page in enumerate(pages):
                                    try:
                                        logger.info(
                                            f"Closing page {idx+1}/{len(pages)}"
                                        )
                                        await page.close(timeout=5000)
                                    except Exception as page_close_error:
                                        logger.error(
                                            f"Error closing page {idx+1}: {str(page_close_error)}"
                                        )
                            except Exception as e:
                                logger.error(f"Error accessing pages: {str(e)}")

                        # Then close the context
                        if browser_context:
                            try:
                                logger.info("Closing browser context")
                                await browser_context.close(timeout=5000)
                                browser_context = None
                                logger.info("Browser context closed successfully")
                            except Exception as context_error:
                                logger.error(
                                    f"Error closing browser context: {str(context_error)}"
                                )

                        # Finally close the browser
                        if browser:
                            try:
                                logger.info("Closing browser")
                                await browser.close()
                                browser = None
                                logger.info("Browser closed successfully")
                            except Exception as browser_close_error:
                                logger.error(
                                    f"Error closing browser: {str(browser_close_error)}"
                                )

                        # Force garbage collection and wait longer to ensure resources are released
                        import gc

                        gc.collect()

                        # Additional delay to ensure all browser processes terminate
                        await asyncio.sleep(3)
                        logger.info("Browser cleanup completed")

            # 2. Run SSH tests if requested
            if effective_test_type in ["ssh", "all"]:
                ssh_results = await run_test_pair(
                    "ssh", device_config, mqtt_scenario, dts_scenario, validator
                )
                results.extend(ssh_results)

            # 3. Run API tests if requested
            if effective_test_type in ["api", "all"]:
                api_results = await run_test_pair(
                    "api", device_config, mqtt_scenario, dts_scenario, validator
                )
                results.extend(api_results)

            # Add a separator line in logs between test pairs
            logger.info("-" * 80)

        # Organize results by test type
        organized_results = {
            "GUI Tests": [],
            "SSH Tests": [],
            "API Tests": [],
            "Validations": [],
        }

        # Categorize each result
        for result in results:
            scenario = result["scenario"]
            if "_gui_" in scenario:
                organized_results["GUI Tests"].append(result)
            elif "_ssh_" in scenario:
                organized_results["SSH Tests"].append(result)
            elif "_api_" in scenario:
                organized_results["API Tests"].append(result)
            elif "validation_" in scenario:
                organized_results["Validations"].append(result)

        # Write organized results to file
        result_writer = ResultWriter(result_file)
        result_writer.write_organized_results(organized_results)

        # Log summary
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r["status"] == "PASS")
        failed_tests = total_tests - passed_tests

        logger.info(
            f"Test execution completed. "
            f"Total: {total_tests}, Passed: {passed_tests}, "
            f"Failed: {failed_tests}"
        )

        # Add detailed failure information if there were any failures
        if failed_tests > 0:
            logger.info("\n" + "=" * 40)
            logger.info("FAILED TESTS SUMMARY:")
            logger.info("=" * 40)

            for idx, result in enumerate(results):
                if result["status"] == "FAIL":
                    scenario_name = result["scenario"]
                    # Extract error details in a readable format
                    if isinstance(result["details"], dict):
                        if "error" in result["details"]:
                            error_msg = result["details"]["error"]
                        elif (
                            "success" in result["details"]
                            and not result["details"]["success"]
                        ):
                            # For validation results that have detailed "details" field
                            validation_details = result["details"].get("details", {})
                            if (
                                isinstance(validation_details, dict)
                                and "failures" in validation_details
                            ):
                                error_msg = ", ".join(validation_details["failures"])
                            else:
                                error_msg = "Validation failed"
                        else:
                            error_msg = str(result["details"])
                    else:
                        error_msg = str(result["details"])

                    logger.info(f"{idx+1}. {scenario_name}: {error_msg}")

            logger.info("=" * 40)

    except Exception as e:
        logger.error(f"Test execution failed: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
