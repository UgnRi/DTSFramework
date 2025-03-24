from .base_page import BasePage
from src.utils.logger import setup_logger

logger = setup_logger()


class DTSPage(BasePage):
    def __init__(self, page, device_config):
        super().__init__(page)
        self.device_config = device_config

    async def navigate(self):
        """Navigate to Services → Data to Server"""
        try:
            url = f'https://{self.device_config["device"]["ip"]}/services/data_sender'
            logger.info(f"Navigating to {url}")
            await self.page.goto(url)
            await self.page.wait_for_selector('[test-id="button-add"]', timeout=30000)
            logger.info("Successfully navigated to Data to Server page")
        except Exception as e:
            logger.error(f"Failed to navigate to Data to Server page: {str(e)}")
            raise

    async def configure_dts(self, config):
        """Configure Data to Server with full configuration"""
        try:
            # Check for and delete existing instance with same name
            await self._check_and_delete_existing_instance(config["instanceName"])

            # Set instance name
            await self._set_instance_name(config["instanceName"])
            await self.page.wait_for_timeout(500)

            # Add new instance
            await self._click_add_button()
            await self.page.wait_for_timeout(500)

            # Configure data collection
            if "data_config" in config:
                await self._configure_data_collection(config["data_config"])
                await self.page.wait_for_timeout(
                    1000
                )  # Increased wait after data collection

            # Handle both original and new configuration styles
            if "collection_config-scheduler" in config:
                logger.info("Detected scheduler configuration")
                await self._configure_scheduler(config["collection_config-scheduler"])
            elif "collection_config-period" in config:
                logger.info("Detected period configuration")
                await self._configure_period(config["collection_config-period"])
            elif "collection_config" in config:
                collection_config = config["collection_config"]

                # Original fallback detection
                if (
                    "timer" in collection_config
                    and collection_config["timer"] == "scheduler"
                ):
                    logger.info("Detected scheduler configuration (legacy)")
                    await self._configure_scheduler(
                        {
                            "timer": collection_config["timer"],
                            "day_time": collection_config["day_time"],
                            "interval_type": collection_config["interval_type"],
                            "month_day": collection_config["month_day"],
                            "weekdays": collection_config["weekdays"],
                            "force_last_day": collection_config.get(
                                "force_last_day", False
                            ),
                            "retry": collection_config.get("retry", False),
                            "retry_count": collection_config["retry_count"],
                            "timeout": collection_config["timeout"],
                        }
                    )
                elif "period" in collection_config:
                    logger.info("Detected period configuration (legacy)")
                    await self._configure_period(
                        {
                            "period": collection_config["period"],
                            "retry": collection_config.get("retry", False),
                        }
                    )

                await self.page.wait_for_timeout(
                    1000
                )  # Increased wait after collection timing

            # Configure server settings AFTER collection method
            if "server_config" in config:
                await self.page.wait_for_timeout(500)  # Extra wait before server config
                await self._configure_server(config["server_config"])

            # Save configuration
            await self._save_configuration()

        except Exception as e:
            logger.error(f"Failed to configure DTS: {str(e)}")
            raise

    async def _check_and_delete_existing_instance(self, instance_name):
        """Check if an instance with the same name exists and delete it if found"""
        try:
            logger.info(f"Checking for existing instance with name: {instance_name}")

            await self.page.wait_for_timeout(2000)

            name_spans = self.page.locator(
                "div.min-w-0.flex.lg\\:text-primary-300 span.truncate"
            )
            count = await name_spans.count()

            logger.info(f"Found {count} existing instances")

            # Check each span for matching name
            for i in range(count):
                span = name_spans.nth(i)

                if await span.is_visible():
                    name_text = await span.inner_text()

                    if name_text.strip() == instance_name:
                        logger.info(
                            f"Found existing instance with name '{instance_name}', deleting it"
                        )

                        try:
                            row = span.locator("xpath=../../../../../../../../..")

                            delete_button = row.locator(
                                'button[test-id="button-delete"]'
                            )

                            if await delete_button.count() > 0:
                                await delete_button.click()
                                await self.page.wait_for_timeout(1000)

                                confirm_button = self.page.locator(
                                    'button[test-id="button-ok"], button[test-id="button-confirm-delete"]'
                                )

                                if await confirm_button.count() > 0:
                                    await confirm_button.first.click()
                                    await self.page.wait_for_timeout(2000)
                                    logger.info(
                                        f"Successfully deleted existing instance '{instance_name}'"
                                    )
                                    return
                        except Exception as e:
                            logger.error(f"Error deleting from row: {str(e)}")

                        # Fallback approach - direct delete button search
                        try:
                            # Find all delete buttons on the page
                            delete_buttons = self.page.locator(
                                'button[test-id="button-delete"]:not([disabled])'
                            )
                            delete_count = await delete_buttons.count()

                            if delete_count > 0:
                                # Click the first enabled delete button
                                await delete_buttons.first.click()
                                await self.page.wait_for_timeout(1000)

                                # Try to find confirmation button with either selector
                                confirm_button = self.page.locator(
                                    'button[test-id="button-ok"], button[test-id="button-confirm-delete"]'
                                )

                                if await confirm_button.count() > 0:
                                    await confirm_button.first.click()
                                    await self.page.wait_for_timeout(2000)
                                    logger.info(
                                        f"Successfully deleted existing instance '{instance_name}' (fallback)"
                                    )
                                    return
                        except Exception as fallback_error:
                            logger.error(
                                f"Error with fallback delete: {str(fallback_error)}"
                            )

                        break

            logger.info(
                f"No instance with name '{instance_name}' found or unable to delete it"
            )

        except Exception as e:
            logger.error(f"Error checking/deleting existing instance: {str(e)}")
            # Don't raise the exception - continue with the rest of the configuration
            logger.info(
                "Continuing with configuration despite error checking for existing instance"
            )

        except Exception as e:
            logger.error(f"Error checking/deleting existing instance: {str(e)}")

            logger.info(
                "Continuing with configuration despite error checking for existing instance"
            )

    async def _set_instance_name(self, name):
        """Set instance name"""
        try:
            logger.info(f"Setting instance name: {name}")
            await self.page.click('[test-id="input-name"]')
            await self.page.keyboard.type(name)
        except Exception as e:
            logger.error(f"Failed to set instance name: {str(e)}")
            raise

    async def _click_add_button(self):
        """Click the add button with the solid background (not the '+ New data input' button)"""
        try:
            logger.info("Clicking solid background add button")

            add_button = self.page.locator(
                'button[test-id="button-add"].bg-primary-300'
            )
            await add_button.wait_for(state="visible", timeout=5000)
            await add_button.click()

            await self.page.wait_for_timeout(1000)
            logger.info("Successfully clicked solid background add button")
        except Exception as e:
            logger.error(f"Failed to click add button: {str(e)}")
            raise

    async def _configure_data_collection(self, data_config):
        """Configure data collection settings"""
        try:
            logger.info("Configuring data collection")

            # Set data input name
            await self._set_collection_name(data_config["name"])

            # Set data type
            data_type = data_config.get("type")
            if data_type:
                await self._set_data_type(data_type)

            # Configure type-specific settings if they exist
            type_settings = data_config.get("type_settings", {})

            await self._configure_type_settings(data_type, type_settings)

            # Handle format type
            if "format_type" in data_config:
                await self._set_format_type(data_config["format_type"])

                # Handle format-specific settings based on format type
                if data_config["format_type"] == "Custom":
                    if "format_string" in data_config:
                        await self._set_format_string(data_config["format_string"])
                    if "empty_value" in data_config:
                        await self._set_empty_value(data_config["empty_value"])
                    if "delimiter" in data_config:
                        await self._set_delimiter(data_config["delimiter"])
                elif data_config["format_type"] == "Lua script":
                    if "lua_format_script" in data_config:
                        await self._set_lua_format_script(
                            data_config["lua_format_script"]
                        )

            # Configure values if present
            if "values" in data_config:
                await self._configure_values(data_config["values"])

            await self._click_next()

        except Exception as e:
            logger.error(f"Failed to configure data collection: {str(e)}")
            raise

    async def _configure_type_settings(self, data_type, type_settings):
        """Configure type-specific settings for different data types"""
        try:
            logger.info(f"Configuring type-specific settings for {data_type}")

            if data_type == "Base":
                # Base type has no specific settings
                pass

            elif data_type == "Bluetooth":
                logger.info("BLOOTOOT")
                if "data_filtering" in type_settings:
                    filtering_selector = self.page.locator(
                        '[test-id="selectstate-bl_filter selectedid-all"]'
                    )
                    await filtering_selector.click()
                    filtering_option = self.page.get_by_role(
                        "option", name=type_settings["data_filtering"], exact=True
                    )
                    await filtering_option.wait_for(state="visible", timeout=30000)
                    await filtering_option.click()

                if "MAC_address" in type_settings:
                    mac_input = self.page.locator('[test-id="input-bl_filter_mac_0"]')
                    await mac_input.fill(type_settings["MAC_address"])

                if "device_name" in type_settings:
                    device_input = self.page.locator(
                        '[test-id="input-bl_filter_name_0"]'
                    )
                    await device_input.fill(type_settings["device_name"])

                if "segment_count" in type_settings:
                    segment_count = self.page.locator('[test-id="input-bl_segments"]')
                    await segment_count.fill(str(type_settings["segment_count"]))

                if "send_as_object" in type_settings:
                    send_as_object_switch = self.page.locator(
                        'div[test-id="switch-bl_object"] >> visible=true'
                    )
                    await send_as_object_switch.wait_for(state="visible")
                    toggle = send_as_object_switch.locator('div[tabindex="0"]')
                    await toggle.click()
                    await self.page.wait_for_timeout(500)

            elif data_type == "GSM":
                # GSM type has no specific settings in the config
                pass

            elif data_type == "Impulse_counter":
                if "data_filtering" in type_settings:
                    filtering_selector = self.page.locator(
                        '[test-id="input-impulse_counter_filter"]'
                    )
                    await filtering_selector.click()
                    filtering_option = self.page.get_by_role(
                        "option", name=type_settings["data_filtering"], exact=True
                    )
                    await filtering_option.wait_for(state="visible", timeout=30000)
                    await filtering_option.click()

                if "impulse_counter_pin" in type_settings:
                    pin_selector = self.page.locator(
                        '[test-id="multiselect-impulse_counter_filter_pin"]'
                    )
                    await pin_selector.click()
                    pin_option = self.page.get_by_role(
                        "option", name=type_settings["impulse_counter_pin"], exact=True
                    )
                    await pin_option.wait_for(state="visible", timeout=30000)
                    await pin_option.click()
                    await pin_selector.click()
                    await self.page.wait_for_timeout(500)  # Wait for dropdown to close

                if "invert_filter" in type_settings:
                    invert_switch = self.page.locator(
                        'div[test-id="switch-impulse_counter_filter_invert"] >> visible=true'
                    )
                    await invert_switch.wait_for(state="visible")
                    toggle = invert_switch.locator('div[tabindex="0"]')
                    await toggle.click()
                    await self.page.wait_for_timeout(500)

                if "max_segment_count" in type_settings:
                    segment_count = self.page.locator(
                        '[test-id="input-impulse_counter_segments"]'
                    )
                    await segment_count.fill(str(type_settings["max_segment_count"]))

                if (
                    "send_as_object" in type_settings
                    and type_settings.get("max_segment_count", 1) == 1
                ):
                    send_as_object_switch = self.page.locator(
                        'div[test-id="switch-impulse_counter_object"] >> visible=true'
                    )
                    await send_as_object_switch.wait_for(state="visible")
                    toggle = send_as_object_switch.locator('div[tabindex="0"]')
                    await toggle.click()
                    await self.page.wait_for_timeout(500)

            elif data_type == "Lua script":
                if "lua_script_location" in type_settings:
                    script_input = self.page.locator(
                        '[test-id="upload-input-lua_script"]'
                    )
                    await script_input.set_input_files(
                        type_settings["lua_script_location"]
                    )

            elif data_type == "Mobile usage":
                if "data_period" in type_settings:
                    period_selector = self.page.locator(
                        '[test-id="selectwrapper-mdc_period"]'
                    )
                    await period_selector.click()
                    period_option = self.page.get_by_role(
                        "option", name=type_settings["data_period"], exact=True
                    )
                    await period_option.wait_for(state="visible", timeout=30000)
                    await period_option.click()

                if "current" in type_settings:
                    current_switch = self.page.locator(
                        'div[test-id="switch-mdc_current"] >> visible=true'
                    )
                    await current_switch.wait_for(state="visible")
                    toggle = current_switch.locator('div[tabindex="0"]')
                    await toggle.click()
                    await self.page.wait_for_timeout(500)

                if "SIM_number" in type_settings:
                    sim_selector = self.page.locator(
                        '[test-id="selectwrapper-mdc_sim"]'
                    )
                    await sim_selector.click()
                    sim_option = self.page.get_by_role(
                        "option", name=type_settings["SIM_number"], exact=True
                    )
                    await sim_option.wait_for(state="visible", timeout=30000)
                    await sim_option.click()

            elif data_type == "MNF info":
                # MNF info type has no specific settings in the config
                pass

            elif data_type == "Modbus":
                if "data_filtering" in type_settings:
                    filtering_selector = self.page.locator(
                        '[test-id="input-modbus_filter"]'
                    )
                    await filtering_selector.click()
                    filtering_option = self.page.get_by_role(
                        "option", name=type_settings["data_filtering"], exact=True
                    )
                    await filtering_option.wait_for(state="visible", timeout=30000)
                    await filtering_option.click()

                if "server_ip" in type_settings:
                    ip_input = self.page.locator(
                        '[test-id="input-modbus_filter_server_ip_0"]'
                    )
                    await ip_input.fill(type_settings["server_ip"])

                if "server_id" in type_settings:
                    id_input = self.page.locator(
                        '[test-id="input-modbus_filter_server_id_0"]'
                    )
                    await id_input.fill(type_settings["server_id"])

                if "request_name" in type_settings:
                    request_name_input = self.page.locator(
                        '[test-id="input-modbus_filter_request_0"]'
                    )
                    await request_name_input.fill(type_settings["request_name"])

                if "segment_count" in type_settings:
                    segment_count = self.page.locator(
                        '[test-id="input-modbus_segments"]'
                    )
                    await segment_count.fill(str(type_settings["segment_count"]))

                if (
                    "send_as_object" in type_settings
                    and type_settings.get("segment_count", 1) == 1
                ):
                    send_as_object_switch = self.page.locator(
                        'div[test-id="switch-modbus_object" >> visible=true'
                    )
                    await send_as_object_switch.wait_for(state="visible")
                    toggle = send_as_object_switch.locator('div[tabindex="0"]')
                    await toggle.click()
                    await self.page.wait_for_timeout(500)

            elif data_type == "Modbus alarms":
                if "data_filtering" in type_settings:
                    filtering_selector = self.page.locator(
                        '[test-id="input-modbus_alarm_filter"]'
                    )
                    await filtering_selector.click()
                    filtering_option = self.page.get_by_role(
                        "option", name=type_settings["data_filtering"], exact=True
                    )
                    await filtering_option.wait_for(state="visible", timeout=30000)
                    await filtering_option.click()

                if "server_id" in type_settings:
                    server_id_input = self.page.locator(
                        '[test-id="input-modbus_alarm_filter_server_id_0"]'
                    )
                    await server_id_input.fill(str(type_settings["server_id"]))

                if "alarm_id" in type_settings:
                    alarm_id_input = self.page.locator(
                        '[test-id="input-modbus_alarm_filter_alarm_id_0"]'
                    )
                    await alarm_id_input.fill(str(type_settings["alarm_id"]))

                if "register_number" in type_settings:
                    register_number_input = self.page.locator(
                        '[test-id="input-modbus_alarm_filter_register_0"]'
                    )
                    await register_number_input.fill(
                        str(type_settings["register_number"])
                    )

            elif data_type == "MQTT":
                await self._configure_mqtt_input_settings(type_settings)

            elif data_type == "Wifi scanner":
                if "data_filtering" in type_settings:
                    type_mapping = {
                        "Name": "name",
                        "MAC address": "mac",
                        "Signal strength": "signal",
                    }
                    mapped_type = type_mapping.get(type_settings["data_filtering"])

                    # Click to open dropdown
                    filtering_selector = self.page.locator(
                        '[test-id="input-wifi_filter"]'
                    )
                    await filtering_selector.click()
                    await self.page.wait_for_timeout(500)  # Wait for dropdown to open

                    # More specific selector using the listbox context
                    option = self.page.locator(
                        f'[test-id="selectwrapper-wifi_filter-listbox"] [test-id="selectoption-{mapped_type}"]'
                    )
                    await option.wait_for(state="visible", timeout=5000)
                    await option.click()

                    if "hostname" in type_settings:
                        for i, hostname in enumerate(type_settings["hostname"]):
                            # Input the hostname
                            hostname_input = self.page.locator(
                                f'[test-id="input-wifi_filter_name_{i}"]'
                            )
                            await hostname_input.fill(str(hostname))

                            # If there are more entries to come, click the add button
                            if i < len(type_settings["hostname"]) - 1:
                                add_button = self.page.locator(
                                    f'[test-id="listadd-wifi_filter_signal_{i}"]'
                                )
                                await add_button.click()
                                await self.page.wait_for_timeout(
                                    500
                                )  # Wait for new field to appear

                    # Handle MAC address entries
                    if "mac_address" in type_settings:
                        for i, address in enumerate(type_settings["mac_address"]):
                            # Input the MAC address
                            address_input = self.page.locator(
                                f'[test-id="input-wifi_filter_mac_{i}"]'
                            )
                            await address_input.fill(str(address))

                            # If there are more entries to come, click the add button
                            if i < len(type_settings["mac_address"]) - 1:
                                add_button = self.page.locator(
                                    f'[test-id="listadd-wifi_filter_signal_{i}"]'
                                )
                                await add_button.click()
                                await self.page.wait_for_timeout(
                                    500
                                )  # Wait for new field to appear

                    # Handle signal strength entries
                    if "signal_strength" in type_settings:
                        for i, strength in enumerate(type_settings["signal_strength"]):
                            # Input the signal strength
                            strength_input = self.page.locator(
                                f'[test-id="input-wifi_filter_signal_{i}"]'
                            )
                            await strength_input.fill(str(strength))

                            # If there are more entries to come, click the add button
                            if i < len(type_settings["signal_strength"]) - 1:
                                add_button = self.page.locator(
                                    f'[test-id="listadd-wifi_filter_signal_{i}"]'
                                )
                                await add_button.click()
                                await self.page.wait_for_timeout(
                                    500
                                )  # Wait for new field to appear

                    if "segment_count" in type_settings:
                        segment_count = self.page.locator(
                            '[test-id="input-wifi_segments"]'
                        )
                        await segment_count.fill(str(type_settings["segment_count"]))

                    if "send_as_object" in type_settings and segment_count == 1:
                        send_object_switch = self.page.locator(
                            'div[test-id="switch-wifi_object"] >> visible=true'
                        )
                        await send_object_switch.wait_for(state="visible")
                        toggle = send_object_switch.locator('div[tabindex="0"]')
                        await toggle.click()

            logger.info(
                f"Successfully configured type-specific settings for {data_type}"
            )

        except Exception as e:
            logger.error(
                f"Failed to configure type-specific settings for {data_type}: {str(e)}"
            )
            raise

    async def _configure_mqtt_input_settings(self, mqtt_settings):
        """Configure MQTT input type settings"""
        try:
            logger.info("Configuring MQTT input settings")

            # Server address
            server_address = self.page.locator('[test-id="input-mqtt_in_host"]')
            await server_address.fill(mqtt_settings["server_address"])

            # Port
            port_input = self.page.locator('[test-id="input-mqtt_in_port"]')
            await port_input.fill(str(mqtt_settings["port"]))

            # Keepalive
            keepalive_input = self.page.locator('[test-id="input-mqtt_in_keepalive"]')
            await keepalive_input.fill(str(mqtt_settings["keepalive"]))

            # Topic
            topic_input = self.page.locator('[test-id="input-mqtt_in_topic"]')
            await topic_input.fill(mqtt_settings["topic"])

            # Client ID
            client_id_input = self.page.locator('[test-id="input-mqtt_in_client_id"]')
            await client_id_input.fill(str(mqtt_settings["client_id"]))

            # QoS
            qos_selector = self.page.locator('[test-id="input-mqtt_in_qos"]')
            await qos_selector.click()
            await self.page.locator(
                f'[test-id="selectoption-{mqtt_settings["QoS"]}"]'
            ).click()

            # Secure connection settings
            if mqtt_settings.get("enable_secure_connection"):
                secure_conn_switch = self.page.locator(
                    'div[test-id="switch-mqtt_in_tls"] >> visible=true'
                )
                await secure_conn_switch.wait_for(state="visible")
                toggle = secure_conn_switch.locator('div[tabindex="0"]')
                await toggle.click()
                await self.page.wait_for_timeout(500)

                secure_config = mqtt_settings["secure_connection"]

                # TLS settings
                tls_type_dropdown = self.page.locator(
                    '[test-id="input-mqtt_in_tls_type"]'
                )
                await tls_type_dropdown.click()
                await self.page.wait_for_timeout(500)

                cert_option = self.page.locator('[test-id="selectoption-cert"]')
                await cert_option.click()
                await self.page.wait_for_timeout(500)

                # Allow insecure connection
                if secure_config.get("allow_insecure_connection"):
                    insecure_switch = self.page.locator(
                        'div[test-id="switch-mqtt_in_insecure"]  >> visible=true'
                    )
                    await insecure_switch.wait_for(state="visible")
                    toggle = insecure_switch.locator('div[tabindex="0"]')
                    await toggle.click()
                    await self.page.wait_for_timeout(500)

                # Certificate files from device
                if secure_config.get("certificate_files_from_device"):
                    device_files_switch = self.page.locator(
                        'div[test-id="switch-mqtt_device_files"] >> visible=true'
                    )
                    await device_files_switch.wait_for(state="visible")
                    toggle = device_files_switch.locator('div[tabindex="0"]')
                    await toggle.click()
                    await self.page.wait_for_timeout(500)

                    # Select files from dropdowns
                    if secure_config.get("device_certificates", {}).get(
                        "certificate_authority_file"
                    ):
                        # Click CA file dropdown
                        ca_dropdown = self.page.locator(
                            '[test-id="input-mqtt_in_cafile"]'
                        )
                        await ca_dropdown.click()
                        await self.page.wait_for_timeout(500)

                        # Click the option within the visible dropdown list
                        dropdown_list = self.page.locator(
                            '[test-id="selectwrapper-mqtt_in_cafile-listbox"]'
                        )
                        ca_option = dropdown_list.get_by_text(
                            secure_config["device_certificates"][
                                "certificate_authority_file"
                            ]
                        )
                        await ca_option.click()
                        await self.page.wait_for_timeout(500)

                    if secure_config.get("device_certificates", {}).get(
                        "client_certificate"
                    ):
                        # Click client cert dropdown
                        cert_dropdown = self.page.locator(
                            '[test-id="input-mqtt_in_certfile"]'
                        )
                        await cert_dropdown.click()
                        await self.page.wait_for_timeout(500)

                        dropdown_list = self.page.locator(
                            '[test-id="selectwrapper-mqtt_in_certfile-listbox"]'
                        )
                        cert_option = dropdown_list.get_by_text(
                            secure_config["device_certificates"]["client_certificate"]
                        )
                        await cert_option.click()
                        await self.page.wait_for_timeout(500)

                    if secure_config.get("device_certificates", {}).get(
                        "client_private_keyfile"
                    ):
                        # Click private key dropdown
                        key_dropdown = self.page.locator(
                            '[test-id="input-mqtt_in_keyfile"]'
                        )
                        await key_dropdown.click()
                        await self.page.wait_for_timeout(500)

                        dropdown_list = self.page.locator(
                            '[test-id="selectwrapper-mqtt_in_keyfile-listbox"]'
                        )
                        key_option = dropdown_list.get_by_text(
                            secure_config["device_certificates"][
                                "client_private_keyfile"
                            ]
                        )
                        await key_option.click()
                        await self.page.wait_for_timeout(500)
                else:
                    # Upload certificate files
                    if secure_config.get("certificate_authority_file"):
                        ca_input = self.page.locator(
                            '[test-id="upload-input-mqtt_in_cafile"]'
                        )
                        await ca_input.set_input_files(
                            secure_config["certificate_authority_file"]
                        )

                    if secure_config.get("client_certificate"):
                        cert_input = self.page.locator(
                            '[test-id="upload-input-mqtt_in_certfile"]'
                        )
                        await cert_input.set_input_files(
                            secure_config["client_certificate"]
                        )

                    if secure_config.get("client_private_keyfile"):
                        key_input = self.page.locator(
                            '[test-id="upload-input-mqtt_in_keyfile"]'
                        )
                        await key_input.set_input_files(
                            secure_config["client_private_keyfile"]
                        )

            # Credentials
            if mqtt_settings.get("username") and mqtt_settings.get("password"):
                username_input = self.page.locator('[test-id="input-mqtt_in_username"]')
                await username_input.fill(mqtt_settings["username"])

                password_input = self.page.locator('[test-id="input-mqtt_in_password"]')
                await password_input.fill(mqtt_settings["password"])

            logger.info("Successfully configured MQTT input settings")

        except Exception as e:
            logger.error(f"Failed to configure MQTT input settings: {str(e)}")
            raise

    # Helper functions for format-specific settings (same as before)
    async def _set_format_string(self, format_string):
        """Set the format string for custom format type"""
        try:
            format_input = self.page.locator('[test-id="input-format_string"]')
            await format_input.fill(format_string)
        except Exception as e:
            logger.error(f"Failed to set format string: {str(e)}")
            raise

    async def _set_empty_value(self, empty_value):
        """Set the empty value for custom format type"""
        try:
            empty_value_input = self.page.locator('[test-id="input-empty_value"]')
            await empty_value_input.fill(empty_value)
        except Exception as e:
            logger.error(f"Failed to set empty value: {str(e)}")
            raise

    async def _set_delimiter(self, delimiter):
        """Set the delimiter for custom format type"""
        try:
            delimiter_input = self.page.locator('[test-id="input-delimiter"]')
            await delimiter_input.fill(delimiter)
        except Exception as e:
            logger.error(f"Failed to set delimiter: {str(e)}")
            raise

    async def _set_lua_format_script(self, script_path):
        """Set the Lua format script path"""
        try:
            script_input = self.page.locator(
                '[test-id="upload-input-lua_format_script"]'
            )
            await script_input.set_input_files(script_path)
        except Exception as e:
            logger.error(f"Failed to set Lua format script: {str(e)}")
            raise

    async def _set_collection_name(self, name):
        """Set the collection name for data collection"""
        try:
            logger.info(f"Setting data collection name to: {name}")

            # Use the specific ID we can see in the error logs
            # Look for the input within the data configuration section
            collection_name = self.page.locator(
                '#section-data-configuration input[test-id="input-name"]'
            )
            await collection_name.wait_for(state="visible", timeout=5000)

            # Clear existing text first
            await collection_name.click()
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")

            # Type the new name
            await collection_name.type(
                name, delay=50
            )  # Add slight delay between keystrokes
            await self.page.wait_for_timeout(500)  # Short wait after typing

            logger.info(f"Successfully set collection name to: {name}")
        except Exception as e:
            logger.error(f"Failed to set collection name: {str(e)}")
            raise

    async def _set_data_type(self, data_type):
        """Set the data type for data collection"""
        try:
            logger.info(f"Setting data type to: {data_type}")
            # Mapping of data types to their test-id values
            type_mapping = {
                "Base": "base",
                "Bluetooth": "bluetooth",
                "GSM": "gsm",
                "Impulse counter": "impulse_counter",
                "Impulse_counter": "impulse_counter",
                "Lua script": "lua",
                "Mobile usage": "mdcollect",
                "MNF info": "mnfinfo",
                "Modbus": "modbus",
                "Modbus alarms": "modbus_alarm",
                "MQTT": "mqtt",
                "Wifi scanner": "wifiscan",
            }

            # Get the mapped test-id value
            mapped_type = type_mapping.get(data_type, data_type.lower())
            logger.info(f"Mapped data type {data_type} to test-id: {mapped_type}")

            # Find the plugin dropdown wrapper
            dropdown_wrapper = self.page.locator(
                '#section-data-configuration [test-id="selectwrapper-plugin"]'
            )
            await dropdown_wrapper.wait_for(state="visible", timeout=10000)

            # Find and click the button within the wrapper
            dropdown_button = dropdown_wrapper.locator('div[role="button"]')
            await dropdown_button.wait_for(state="visible", timeout=5000)
            await dropdown_button.click()

            # Wait for animation
            await self.page.wait_for_timeout(1000)

            # First, try to find all matching options
            option_elements = await self.page.locator(
                f'[test-id="selectoption-{mapped_type}"]'
            ).all()

            if len(option_elements) == 0:
                raise Exception(f"No options found for {data_type}")

            # Try to find the visible option
            clicked = False
            for option in option_elements:
                try:
                    if await option.is_visible():
                        # Try clicking the inner truncate div first
                        try:
                            inner_div = option.locator("div.truncate")
                            await inner_div.click(timeout=2000)
                            clicked = True
                            break
                        except Exception:
                            # If inner div click fails, try clicking the option itself
                            await option.click(timeout=2000)
                            clicked = True
                            break
                except Exception as e:
                    logger.warning(f"Failed to click option: {str(e)}")
                    continue

            if not clicked:
                # If no visible option was found, try reopening the dropdown
                await dropdown_button.click()
                await self.page.wait_for_timeout(500)
                await dropdown_button.click()
                await self.page.wait_for_timeout(1000)

                # Try clicking the first option regardless of visibility
                try:
                    first_option = option_elements[0]
                    await first_option.click(timeout=5000)
                    clicked = True
                except Exception as e:
                    logger.error(f"Failed to click first option after reopen: {str(e)}")
                    raise

            if not clicked:
                raise Exception(f"Failed to click any option for {data_type}")

            # Wait for selection to take effect
            await self.page.wait_for_timeout(1000)

            # Verify selection
            dropdown_text = await dropdown_button.text_content()
            if data_type.lower() not in dropdown_text.lower():
                raise Exception(
                    f"Selection verification failed. Expected: {data_type}, Got: {dropdown_text}"
                )

            logger.info(f"Successfully set data type to: {data_type}")

        except Exception as e:
            logger.error(f"Failed to set data type: {str(e)}")
            # Add debugging information
            try:
                dropdown_state = await dropdown_wrapper.is_visible()
                logger.error(f"Dropdown wrapper visible: {dropdown_state}")

                # Log all matching options
                option_elements = await self.page.locator(
                    f'[test-id="selectoption-{mapped_type}"]'
                ).all()
                logger.error(f"Found {len(option_elements)} matching options")

                for i, opt in enumerate(option_elements):
                    try:
                        visible = await opt.is_visible()
                        text = await opt.text_content()
                        logger.error(f"Option {i}: visible={visible}, text={text}")
                    except Exception:
                        logger.error(f"Option {i}: Failed to get state")

            except Exception as debug_e:
                logger.error(f"Error during debug logging: {debug_e}")
            raise

    async def _set_format_type(self, format_type):
        """Set the format type for data collection using role-based selection"""
        try:
            logger.info(f"Setting format type to: {format_type}")

            # Click the format type dropdown to open it
            format_dropdown = self.page.locator(
                '#section-data-configuration [test-id="selectwrapper-format"]'
            )
            await format_dropdown.click()
            await self.page.wait_for_timeout(500)  # Wait for dropdown animation

            filter_params = {"has": self.page.get_by_text(format_type, exact=True)}
            option = self.page.get_by_role("option").filter(**filter_params)

            # Wait for and click the option
            await option.wait_for(state="visible", timeout=5000)
            await option.click()

            logger.info(f"Successfully set format type to: {format_type}")
            await self.page.wait_for_timeout(500)  # Wait for dropdown to close

        except Exception as e:
            logger.error(f"Failed to set format type: {str(e)}")
            raise

    async def _configure_values(self, values):
        """Configure which values to collect"""
        try:
            logger.info(f"Configuring values: {values}")

            # Click to open the values selection dropdown/list
            values_button = self.page.locator(
                '#section-data-configuration [test-id="multiselect-members"]'
            )
            await values_button.click()
            await self.page.wait_for_timeout(500)

            # For each value in the list, find and click its checkbox
            for value in values:
                # Convert value to lowercase and hyphenate for the test-id format
                value_id = f"checkbox-data_sender.input.3.edit.3_members-data_sender.input.3.edit.3_members-select-{value.lower()}-checkbox"
                checkbox = self.page.locator(f'[test-id="{value_id}"]')
                await checkbox.wait_for(state="visible", timeout=5000)
                await checkbox.click()
                await self.page.wait_for_timeout(300)  # Small wait between selections

            # Click outside to close the dropdown - we'll click on the main dropdown button again
            await values_button.click()
            await self.page.wait_for_timeout(500)  # Wait for dropdown to close

            logger.info("Successfully configured values")

        except Exception as e:
            logger.error(f"Failed to configure values: {str(e)}")
            raise

    async def _configure_server(self, server_config):
        """Configure server settings"""
        try:
            logger.info("Configuring server settings")

            # Set plugin type to MQTT using specific ID
            # plugin_dropdown = self.page.locator('#data_sender\\.output\\.2\\.edit\\.2_plugin')
            plugin_dropdown = self.page.locator(
                '#section-server-configuration [test-id="input-plugin"]'
            )
            await plugin_dropdown.click()
            await self.page.wait_for_timeout(500)

            mqtt_option = self.page.get_by_role("option", name="MQTT", exact=True)
            await mqtt_option.wait_for(state="visible", timeout=30000)
            await mqtt_option.click()

            # Set server address
            # server_address = self.page.locator('#data_sender\\.output\\.2\\.edit\\.2_mqtt_host')
            server_address = self.page.locator(
                '#section-server-configuration [test-id="input-mqtt_host"]'
            )
            await server_address.fill(server_config.get("server_address", ""))

            # Set port
            # port_field = self.page.locator('#data_sender\\.output\\.2\\.edit\\.2_mqtt_port')
            port_field = self.page.locator(
                '#section-server-configuration [test-id="input-mqtt_port"]'
            )
            await port_field.fill(str(server_config.get("port", "")))

            # Set keepalive
            # keepalive_field = self.page.locator('#data_sender\\.output\\.2\\.edit\\.2_mqtt_keepalive')
            keepalive_field = self.page.locator(
                '#section-server-configuration [test-id="input-mqtt_keepalive"]'
            )
            await keepalive_field.fill(str(server_config.get("keepalive", "")))

            # Set topic
            # topic_field = self.page.locator('#data_sender\\.output\\.2\\.edit\\.2_mqtt_topic')
            topic_field = self.page.locator(
                '#section-server-configuration [test-id="input-mqtt_topic"]'
            )
            await topic_field.fill(server_config.get("topic", ""))

            # Set client ID
            client_id_field = self.page.locator(
                '#section-server-configuration [test-id="input-mqtt_client_id"]'
            )
            await client_id_field.fill(server_config.get("client_id", ""))

            # Set QoS
            dropdown_button = self.page.locator(
                '#section-server-configuration [test-id="input-mqtt_qos"]'
            )
            await dropdown_button.wait_for(state="visible", timeout=30000)
            await dropdown_button.click()
            logger.info("Clicked QoS dropdown")

            # Wait for dropdown list to be visible and stable
            await self.page.wait_for_timeout(
                1000
            )  # Give UI time to fully render dropdown

            # Click MQTT option directly with improved locator
            mqtt_option = self.page.get_by_role(
                "option", name=str(server_config["QoS"]), exact=True
            )
            await mqtt_option.wait_for(state="visible", timeout=30000)
            await mqtt_option.click()

            # Verify the selection took effect
            await self.page.wait_for_timeout(1000)  # Wait for UI to update
            logger.info("Successfully set QoS")
            secure_config = server_config.get("secure_connection", {})
            # Configure secure connection if enabled
            if server_config.get("enable_secure_connection"):
                # Toggle secure connection switch if not already enabled
                logger.info("Turning on secure connection switch")
                secure_conn_switch = self.page.locator(
                    '#section-server-configuration div[test-id="switch-mqtt_tls"] >>visible=true'
                )
                await secure_conn_switch.wait_for(state="visible")
                toggle = secure_conn_switch.locator('div[tabindex="0"]')
                await toggle.click()
                await self.page.wait_for_timeout(500)

                # Select TLS type as Certificate based
                tls_type_dropdown = self.page.locator(
                    '[test-id="selectwrapper-mqtt_tls_type"]'
                )
                await tls_type_dropdown.click()
                await self.page.wait_for_timeout(500)

                cert_option = self.page.locator(
                    '[test-id="selectwrapper-mqtt_tls_type-listbox"] [test-id="selectoption-cert"]'
                )
                await cert_option.click()
                await self.page.wait_for_timeout(500)

                secure_config = server_config.get("secure_connection", {})

                insecure_switch = self.page.locator(
                    'div[test-id="switch-mqtt_insecure"] >> visible=true'
                )
                await insecure_switch.wait_for(
                    state="visible"
                )  # Make sure switch is visible

                if secure_config.get("allow_insecure_connection"):
                    if await insecure_switch.get_attribute("aria-checked") == "false":
                        # More specific selector targeting the clickable div that contains the toggle
                        toggle = insecure_switch.locator('div[tabindex="0"]')
                        await toggle.click()
                        await self.page.wait_for_timeout(500)
                else:
                    if await insecure_switch.get_attribute("aria-checked") == "true":
                        toggle = insecure_switch.locator('div[tabindex="0"]')
                        await toggle.click()
                        await self.page.wait_for_timeout(500)

                # Configure device files switch
                device_files_switch = self.page.locator(
                    'div[test-id="switch-mqtt_device_files"] >> visible=true'
                )
                await device_files_switch.wait_for(state="visible")

                if secure_config.get("certificate_files_from_device"):
                    if (
                        await device_files_switch.get_attribute("aria-checked")
                        == "false"
                    ):
                        toggle = device_files_switch.locator('div[tabindex="0"]')
                        await toggle.click()
                        await self.page.wait_for_timeout(500)

                    # Select files from dropdowns
                    if secure_config.get("device_certificates", {}).get(
                        "certificate_authority_file"
                    ):
                        # Click CA file dropdown
                        ca_dropdown = self.page.locator(
                            '[test-id="selectwrapper-mqtt_cafile"]'
                        )
                        await ca_dropdown.click()
                        await self.page.wait_for_timeout(500)

                        # Click the option within the visible dropdown list
                        dropdown_list = self.page.locator(
                            '[test-id="selectwrapper-mqtt_cafile-listbox"]'
                        )

                        ca_option = dropdown_list.get_by_text(
                            secure_config["device_certificates"][
                                "certificate_authority_file"
                            ]
                        )

                        await ca_option.click()
                        await self.page.wait_for_timeout(500)

                    if secure_config.get("device_certificates", {}).get(
                        "client_certificate"
                    ):
                        # Click client cert dropdown
                        cert_dropdown = self.page.locator(
                            '[test-id="selectwrapper-mqtt_certfile"]'
                        )
                        await cert_dropdown.click()
                        await self.page.wait_for_timeout(500)

                        dropdown_list = self.page.locator(
                            '[test-id="selectwrapper-mqtt_certfile-listbox"]'
                        )
                        cert_option = dropdown_list.get_by_text(
                            secure_config["device_certificates"]["client_certificate"]
                        )
                        await cert_option.click()
                        await self.page.wait_for_timeout(500)

                    if secure_config.get("device_certificates", {}).get(
                        "client_private_keyfile"
                    ):
                        # Click private key dropdown
                        key_dropdown = self.page.locator(
                            '[test-id="selectwrapper-mqtt_keyfile"]'
                        )
                        await key_dropdown.click()
                        await self.page.wait_for_timeout(500)

                        dropdown_list = self.page.locator(
                            '[test-id="selectwrapper-mqtt_keyfile-listbox"]'
                        )
                        key_option = dropdown_list.get_by_text(
                            secure_config["device_certificates"][
                                "client_private_keyfile"
                            ]
                        )
                        await key_option.click()
                        await self.page.wait_for_timeout(500)
                else:
                    if (
                        await device_files_switch.get_attribute("aria-checked")
                        == "true"
                    ):
                        toggle = device_files_switch.locator('div[tabindex="0"]')
                        await toggle.click()
                        await self.page.wait_for_timeout(500)

                # Only upload files if device_files is false
                if secure_config.get("certificate_authority_file"):
                    ca_file_input = self.page.locator(
                        '[test-id="upload-input-mqtt_cafile"]'
                    )
                    await ca_file_input.set_input_files(
                        secure_config["certificate_authority_file"]
                    )
                    await self.page.wait_for_timeout(500)

                if secure_config.get("client_certificate"):
                    cert_file_input = self.page.locator(
                        '[test-id="upload-input-mqtt_certfile"]'
                    )
                    await cert_file_input.set_input_files(
                        secure_config["client_certificate"]
                    )
                    await self.page.wait_for_timeout(500)

                if secure_config.get("client_private_keyfile"):
                    key_file_input = self.page.locator(
                        '[test-id="upload-input-mqtt_keyfile"]'
                    )
                    await key_file_input.set_input_files(
                        secure_config["client_private_keyfile"]
                    )
                    await self.page.wait_for_timeout(500)

            # Configure credentials if needed
            if server_config.get("use_credentials"):
                # Toggle credentials switch if not already enabled
                logger.info("use credentials is true in the config")
                credentials_switch = self.page.locator(
                    'div[test-id="switch-mqtt_use_credentials"] >> visible=true'
                )
                await credentials_switch.wait_for(state="visible")
                if await credentials_switch.get_attribute("aria-checked") == "false":
                    toggle = credentials_switch.locator('div[tabindex="0"]')
                    await toggle.click()
                    await self.page.wait_for_timeout(500)

                # Set username
                username_field = self.page.locator('[test-id="input-mqtt_username"]')
                await username_field.fill(server_config.get("username", ""))

                # Set password
                password_field = self.page.locator('[test-id="input-mqtt_password"]')
                await password_field.fill(server_config.get("password", ""))

        except Exception as e:
            logger.error(f"Failed to configure server settings: {str(e)}")
            raise

    async def _configure_period(self, period_config):
        """Configure period-based collection"""
        try:
            logger.info(f"Configuring period: {period_config['period']}")
            period_input = self.page.locator('[test-id="input-period"]')
            await period_input.click()
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            await period_input.type(str(period_config["period"]))

            if period_config.get("retry"):
                retry_switch = self.page.locator('[test-id="switch-retry"]')
                await retry_switch.click()

            await self._click_next()

        except Exception as e:
            logger.error(f"Failed to configure period: {str(e)}")
            raise

    async def _configure_scheduler(self, scheduler_config):
        """Configure scheduler-based collection"""
        try:
            logger.info("Configuring scheduler")

            # Set timer type to Scheduler
            timer_dropdown = self.page.locator(
                '#section-collection-configuration [test-id="selectwrapper-timer"]'
            )
            await timer_dropdown.click()
            await self.page.wait_for_timeout(500)  # Wait for dropdown animation

            scheduler_option = self.page.locator('[test-id="selectoption-scheduler"]')
            await scheduler_option.click()
            await self.page.wait_for_timeout(500)

            # Set day time
            time_input = self.page.locator(
                '#section-collection-configuration input[test-id="input-time_0"]'
            )
            await time_input.wait_for(state="visible", timeout=30000)
            await time_input.focus()
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            await time_input.fill(scheduler_config.get("day_time", ""))

            # Set interval type (day mode)
            interval_dropdown = self.page.locator(
                '#section-collection-configuration [test-id="selectwrapper-day_mode"]'
            )
            await interval_dropdown.click()
            await self.page.wait_for_timeout(500)
            logger.info(scheduler_config.get("interval_type", ""))
            interval_option = self.page.get_by_role("option").filter(
                has=self.page.get_by_text(
                    scheduler_config.get("interval_type", ""), exact=True
                )
            )
            await interval_option.click()
            await self.page.wait_for_timeout(500)

            # Configure weekdays
            if scheduler_config["timer"] == "period":
                weekdays = scheduler_config.get("weekdays", [])
                for day in weekdays:
                    day_checkbox = self.page.locator(
                        f'[test-id="checkbox-{day.lower()}"]'
                    )
                    await day_checkbox.click()
                    await self.page.wait_for_timeout(200)

            # Optional: Configure month days if applicable
            if "month_day" in scheduler_config:
                logger.info("Month days configuration found")

                # Open the dropdown
                month_days_button = self.page.locator(
                    '[test-id="multiselect-month_days"]'
                )
                await month_days_button.click()
                await self.page.wait_for_timeout(500)

                # Select the days
                for value in scheduler_config.get("month_day", []):
                    try:
                        list_item = self.page.locator(
                            f"#data_sender\\.collection\\.1\\.edit\\.1_month_days-select-{value}"
                        )
                        await list_item.wait_for(state="visible", timeout=5000)
                        label = list_item.locator("label")
                        await label.click()
                        await self.page.wait_for_timeout(200)
                    except Exception as value_error:
                        logger.warning(
                            f"Error selecting month day {value}: {value_error}"
                        )

                # Close the dropdown by clicking the dropdown arrow
                try:
                    dropdown_arrow = self.page.locator(
                        '[test-id="multiselect-month_days"] .tlt-input-icon-right'
                    )
                    await dropdown_arrow.click()
                    await self.page.wait_for_timeout(1000)
                except Exception as e:
                    logger.error(f"Failed to close month days dropdown: {e}")
                    raise

            try:

                # Configure force last day if applicable
                if scheduler_config.get("force_last_day"):
                    force_last_day_switch = self.page.locator(
                        '[id="data_sender.collection.1.edit.1_last_day"]'
                    )
                    await force_last_day_switch.wait_for(state="visible", timeout=10000)
                    # Use JavaScript click to avoid any potential intercepted clicks
                    await force_last_day_switch.evaluate("node => node.click()")
                    await self.page.wait_for_timeout(500)

                # Configure retry if applicable
                if scheduler_config.get("retry"):
                    retry_switch = self.page.locator(
                        '[id="data_sender.collection.1.edit.1_retry"]'
                    )
                    await retry_switch.wait_for(state="visible", timeout=10000)
                    # Use JavaScript click to avoid any potential intercepted clicks
                    await retry_switch.evaluate("node => node.click()")
                    await self.page.wait_for_timeout(500)

            except Exception as e:
                logger.error(f"Failed to configure switches: {str(e)}")
                raise

            # Configure retry count and timeout
            try:
                if scheduler_config.get("retry_count"):
                    retry_count_field = self.page.locator(
                        '[id="data_sender.collection.1.edit.1_retry_count"]'
                    )
                    await retry_count_field.click()

                    # Clear initial text
                    await self.page.keyboard.press("Control+A")
                    await self.page.keyboard.press("Backspace")

                    # Type the configured value
                    await self.page.keyboard.type(str(scheduler_config["retry_count"]))
                if scheduler_config.get("timeout"):
                    timeout_field = self.page.locator(
                        '[id="data_sender.collection.1.edit.1_retry_timeout"]'
                    )
                    await timeout_field.click()

                    # Clear initial text
                    await self.page.keyboard.press("Control+A")
                    await self.page.keyboard.press("Backspace")

                    # Type the configured value
                    await self.page.keyboard.type(str(scheduler_config["timeout"]))
            except Exception as e:
                logger.error(f"Failed to configure switches: {str(e)}")
                raise

            # Move to next step
            await self._click_next()

        except Exception as e:
            logger.error(f"Failed to configure scheduler: {str(e)}")
            raise

    async def _click_next(self):
        """Click the next button"""
        try:
            next_button = self.page.locator(
                'div[test-id="modal-container"] button[test-id="button-next"]'
            )
            await next_button.click()
            await self.page.wait_for_timeout(1000)
        except Exception as e:
            logger.error(f"Failed to click next button: {str(e)}")
            raise

    async def _save_configuration(self):
        """Save the configuration"""
        try:
            logger.info("Saving configuration")
            save_button = self.page.locator(
                'div[test-id="modal-container"] button[test-id="button-next"]'
            )
            await save_button.click()
            await self.page.wait_for_timeout(5000)
            logger.info("Successfully saved configuration")
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            raise
