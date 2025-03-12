import logging
from .base_page import BasePage
import os
from src.backend.certificate_generator import (
    generate_mqtt_certificates,
    prepare_mqtt_certificates,
)
from src.backend.file_generator import create_acl_file, create_password_file
from src.utils.logger import setup_logger

logger = setup_logger()


class BrokerPage(BasePage):
    def __init__(self, page, device_config):
        super().__init__(page)
        self.device_config = device_config

    async def navigate(self):
        """Navigate to MQTT Broker page"""
        try:
            url = f'https://{self.device_config["device"]["ip"]}/services/mqtt/broker'
            logger.info(f"Navigating to {url}")
            await self.page.goto(url)
            await self.page.wait_for_selector('[test-id="button-add"]')
            logger.info("MQTT Broker page loaded")
        except Exception as e:
            logger.error(f"Failed to navigate to MQTT Broker page: {str(e)}")
            raise

    async def configure_basic_settings(self, config):
        """Configure basic MQTT settings"""
        try:
            logger.info(config)
            # Enable MQTT Broker
            enable_switch = self.page.locator('[id="mosquitto.mqtt.mqtt.mqtt_enabled"]')
            await enable_switch.wait_for(state="visible", timeout=30000)
            switch_container = self.page.locator("div[aria-checked]").filter(
                has=enable_switch
            )
            is_enabled = await switch_container.get_attribute("aria-checked") == "true"
            if not is_enabled:
                logger.info("MQTT Broker not enabled, enabling it now")
                await enable_switch.click(force=True)

            # Configure port if specified
            if "port" in config:
                await self.page.click('[test-id="input-local_port_0"]')
                await self.page.keyboard.press("ControlOrMeta+A")
                await self.page.keyboard.press("Backspace")
                await self.page.keyboard.type(config["port"])

            # Configure remote access if specified
            if "remote_access" in config:
                remote_switch = self.page.locator(
                    '[id="mosquitto.mqtt.mqtt.mqtt_allow_ra"]'
                )
                await remote_switch.wait_for(state="visible", timeout=30000)
                switch_container = self.page.locator("div[aria-checked]").filter(
                    has=remote_switch
                )
                is_remote = (
                    await switch_container.get_attribute("aria-checked") == "true"
                )
                if is_remote != config["remote_access"]:
                    await remote_switch.click(force=True)

        except Exception as e:
            logger.error(f"Failed to configure basic settings: {str(e)}")
            raise

    async def handle_switch(
        self, id_selector, test_id_selector, desired_state, description
    ):
        """Helper function to handle switch toggling"""
        try:
            # Get the switch element
            switch = self.page.locator(id_selector)
            await switch.wait_for(state="visible", timeout=30000)

            # Get the container with test-id for checking state
            switch_container = self.page.locator(f'div[test-id="{test_id_selector}"]')
            is_enabled = await switch_container.get_attribute("aria-checked") == "true"

            if is_enabled != desired_state:
                logger.info(f"Setting {description} to {desired_state}")
                await switch.click(force=True)
                await self.page.wait_for_timeout(1000)  # Wait for switch action
            else:
                logger.info(f"{description} already in desired state: {desired_state}")

        except Exception as e:
            logger.error(f"Failed to handle {description} switch: {e}")
            raise

    async def configure_security(self, security_config):
        """Configure security settings with improved certificate handling"""
        try:
            if not security_config:
                logger.info(
                    "No security config provided, skipping security configuration"
                )
                return

            logger.info(f"Security config: {security_config}")

            # Navigate to Security tab
            logger.info("Clicking Security tab")
            await self.page.click('[test-id="selected-tab-security"]')
            await self.page.wait_for_timeout(1000)

            # Handle TLS/SSL switch
            if "TLS/SSL" in security_config:
                await self._configure_tls_ssl(security_config["TLS/SSL"])

            # Configure certificates if specified
            if (
                "certificates" in security_config
                and security_config["TLS/SSL"] != False
            ):
                await self._configure_certificates(security_config["certificates"])

            # Set TLS version if specified
            if "TLS_version" in security_config and security_config["TLS/SSL"] != False:
                await self._set_tls_version(security_config["TLS_version"])

            await self.page.wait_for_timeout(1000)  # Final wait for settings to apply
        except Exception as e:
            logger.error(f"Failed to configure security settings: {str(e)}")
            raise

    async def _configure_tls_ssl(self, enabled):
        """Configure TLS/SSL setting"""
        try:
            ssl_switch = self.page.locator(
                '[id="mosquitto.mqtt.mqtt.mqtt_use_tls_ssl"]'
            )
            await ssl_switch.wait_for(state="visible", timeout=30000)

            switch_container = self.page.locator('div[test-id="switch-use_tls_ssl"]')
            is_ssl_enabled = (
                await switch_container.get_attribute("aria-checked") == "true"
            )

            if is_ssl_enabled != enabled:
                logger.info(f"Setting TLS/SSL to {enabled}")
                await ssl_switch.click(force=True)
                await self.page.wait_for_timeout(1000)
            else:
                logger.info(f"TLS/SSL already in desired state: {enabled}")
        except Exception as e:
            logger.error(f"Failed to configure TLS/SSL: {str(e)}")
            raise

    async def _configure_certificates(self, cert_config):
        """Configure certificates with improved handling"""
        try:
            # Select TLS type
            if "tls_type" in cert_config:
                logger.info(f"Setting TLS type to {cert_config['tls_type']}")
                await self.page.click('[test-id="input-tls_type"]')
                await self.page.wait_for_timeout(500)

                if cert_config["tls_type"] == "Pre-Shared-Key based":
                    await self.page.locator('[test-id="selectoption-psk"]').click()
                    await self._configure_psk(cert_config)
                else:
                    await self.page.locator('[test-id="selectoption-cert"]').click()
                    await self._configure_cert_based(cert_config)

        except Exception as e:
            logger.error(f"Failed to configure certificates: {str(e)}")
            raise

    async def _configure_psk(self, cert_config):
        """Configure Pre-Shared-Key settings"""
        try:
            if "pre-shared-key" in cert_config:
                await self.page.fill(
                    '[test-id="input-psk"]', cert_config["pre-shared-key"]
                )
            if "identity" in cert_config:
                await self.page.fill(
                    '[test-id="input-identity"]', cert_config["identity"]
                )
            await self.page.wait_for_timeout(500)
        except Exception as e:
            logger.error(f"Failed to configure PSK settings: {str(e)}")
            raise

    async def _configure_cert_based(self, cert_config):
        """Configure certificate-based settings with generation and upload"""
        try:
            # Handle require certificate switch if specified
            if "require_certificate" in cert_config:
                await self._set_require_certificate(cert_config["require_certificate"])

            # Handle device certificate files switch
            if "certificate_files_from_device" in cert_config:
                await self._set_device_certificates(
                    cert_config["certificate_files_from_device"]
                )

                if cert_config["certificate_files_from_device"]:
                    # Handle device-based certificate selection
                    await self._handle_device_certificates(cert_config)
                else:
                    # Handle file-based certificates with generation
                    await self._handle_file_certificates(cert_config)

        except Exception as e:
            logger.error(f"Failed to configure certificate-based settings: {str(e)}")
            raise

    async def _handle_device_certificates(self, cert_config):
        """Handle selection of certificates from device dropdowns using role-based selection"""
        try:
            device_certs = cert_config.get("device_certificates", {})
            logger.info("Handling device-based certificate selection")

            # Map of certificate types to their dropdowns
            cert_types = {
                "ca_file": {
                    "dropdown": "input-ca_file",
                    "filename": device_certs.get("ca_file"),
                },
                "certificate_file": {
                    "dropdown": "input-cert_file",
                    "filename": device_certs.get("certificate_file"),
                },
                "key_file": {
                    "dropdown": "input-key_file",
                    "filename": device_certs.get("key_file"),
                },
            }

            for cert_type, selectors in cert_types.items():
                if not selectors["filename"]:
                    continue

                target_filename = os.path.basename(selectors["filename"])
                logger.info(f"Selecting {cert_type}: {target_filename}")

                try:
                    # Click dropdown to open it
                    dropdown = self.page.locator(f'[test-id="{selectors["dropdown"]}"]')
                    await dropdown.wait_for(state="visible", timeout=30000)
                    await dropdown.click()
                    logger.info(f"Clicked {cert_type} dropdown")

                    # Wait for dropdown list to be visible and stable
                    await self.page.wait_for_timeout(
                        1000
                    )  # Give UI time to fully render dropdown

                    # Use get_by_role to select the option
                    option = self.page.get_by_role(
                        "option", name=target_filename, exact=True
                    )
                    await option.wait_for(state="visible", timeout=30000)
                    await option.click()
                    logger.info(f"Selected {cert_type} option: {target_filename}")

                    # Verify the selection took effect
                    await self.page.wait_for_timeout(1000)

                except Exception as e:
                    # If selection fails, log available options for debugging
                    try:
                        options = self.page.get_by_role("option")
                        option_count = await options.count()
                        available_options = []
                        for i in range(option_count):
                            option = options.nth(i)
                            text = await option.inner_text()
                            available_options.append(text.strip())
                        logger.error(
                            f"Available options for {cert_type}: {available_options}"
                        )
                    except Exception as inner_e:
                        logger.error(f"Failed to get available options: {str(inner_e)}")

                    logger.error(f"Failed to select {cert_type}: {str(e)}")
                    raise

            await self.page.wait_for_timeout(1000)  # Final wait for all selections

        except Exception as e:
            logger.error(f"Failed to handle device certificates: {str(e)}")
            raise

    async def _select_from_dropdown(self, dropdown_id, target_value):
        """Helper method to select a value from a dropdown using role-based selection"""
        try:
            # Click dropdown to open it
            dropdown = self.page.locator(f'[test-id="{dropdown_id}"]')
            await dropdown.wait_for(state="visible", timeout=30000)
            await dropdown.click()
            logger.info(f"Clicked dropdown {dropdown_id}")

            # Wait for dropdown list to be visible and stable
            await self.page.wait_for_timeout(1000)

            # Select the option by role
            option = self.page.get_by_role("option", name=target_value, exact=True)
            await option.wait_for(state="visible", timeout=30000)
            await option.click()
            logger.info(f"Selected option: {target_value}")

            # Verify the selection took effect
            await self.page.wait_for_timeout(1000)
            return True

        except Exception as e:
            logger.error(
                f"Failed to select {target_value} from dropdown {dropdown_id}: {str(e)}"
            )
            return False

    async def _find_and_select_certificate(self, dropdown_id, target_filename):
        """Helper method to find and select a certificate from the dropdown"""
        try:
            # Click dropdown to open it
            dropdown = self.page.locator(f'[test-id="{dropdown_id}"]')
            await dropdown.wait_for(state="visible", timeout=5000)
            await dropdown.click()
            await self.page.wait_for_timeout(500)

            # Get all options
            options = self.page.locator('[test-id="options-wrapper"] li')
            option_count = await options.count()

            # Get just the filename part for comparison
            target_basename = os.path.basename(target_filename)
            found = False

            for i in range(option_count):
                option = options.nth(i)
                option_text = await option.locator("div.truncate").inner_text()

                if option_text.strip() == target_basename:
                    await option.click()
                    found = True
                    logger.info(f"Selected certificate: {option_text}")
                    break

            if not found:
                raise Exception(f"No matching option found for {target_basename}")

            await self.page.wait_for_timeout(500)
            return True

        except Exception as e:
            logger.error(f"Failed to select certificate {target_filename}: {str(e)}")
            return False

    async def _select_certificate_from_dropdown(self, dropdown_id, filename):
        """Helper method to select a certificate from a dropdown"""
        try:
            # Click dropdown to open it
            dropdown = self.page.locator(f'[test-id="{dropdown_id}"]')
            await dropdown.wait_for(state="visible", timeout=5000)
            await dropdown.click()
            await self.page.wait_for_timeout(500)

            # Try first with direct option selector
            try:
                option_name = filename.lower().replace(".", "_").replace("-", "_")
                option = self.page.locator(f'[test-id="selectoption-{option_name}"]')
                await option.wait_for(state="visible", timeout=2000)
                await option.click()
                return True
            except Exception:
                # If direct selection fails, try finding in list
                options = self.page.locator(f'[test-id="options-wrapper"] li')
                option_count = await options.count()

                for i in range(option_count):
                    option = options.nth(i)
                    option_text = await option.inner_text()

                    if option_text.strip() == filename:
                        await option.click()
                        return True

                # If we get here, no match was found
                raise Exception(f"No matching option found for {filename}")

        except Exception as e:
            logger.error(
                f"Failed to select certificate {filename} from dropdown: {str(e)}"
            )
            return False

    async def _set_require_certificate(self, enabled):
        """Set require certificate setting"""
        try:
            req_cert_switch = self.page.locator(
                '[id="mosquitto.mqtt.mqtt.mqtt_require_certificate"]'
            )
            await req_cert_switch.wait_for(state="visible", timeout=30000)

            req_cert_container = self.page.locator(
                'div[test-id="switch-require_certificate"]'
            )
            is_req_cert = (
                await req_cert_container.get_attribute("aria-checked") == "true"
            )

            if is_req_cert != enabled:
                logger.info(f"Setting require certificate to {enabled}")
                await req_cert_switch.click(force=True)
                await self.page.wait_for_timeout(1000)
        except Exception as e:
            logger.error(f"Failed to set require certificate: {str(e)}")
            raise

    async def _set_device_certificates(self, enabled):
        """Set device certificates setting"""
        try:
            device_cert_switch = self.page.locator(
                '[id="mosquitto.mqtt.mqtt.mqtt_device_sec_files"]'
            )
            await device_cert_switch.wait_for(state="visible", timeout=30000)

            device_cert_container = self.page.locator(
                'div[test-id="switch-device_sec_files"]'
            )
            is_device_cert = (
                await device_cert_container.get_attribute("aria-checked") == "true"
            )

            if is_device_cert != enabled:
                logger.info(f"Setting device certificates to {enabled}")
                await device_cert_switch.click(force=True)
                await self.page.wait_for_timeout(1000)
        except Exception as e:
            logger.error(f"Failed to set device certificates: {str(e)}")
            raise

    async def _handle_file_certificates(self, cert_config):
        """Handle file-based certificates with generation if needed"""
        try:
            if "device_certificates" not in cert_config:
                logger.warning("No device certificates specified in config")
                return

            device_certs = cert_config["device_certificates"]

            # Prepare the certificates (generate if needed)
            cert_paths = prepare_mqtt_certificates(device_certs)
            logger.info(f"Certificate paths: {cert_paths}")

            # Map of certificate types to their selectors
            cert_uploads = {
                "ca_file": {
                    "button": "button-ca_file",
                    "input": "upload-input-ca_file",
                    "label": "mqtt_ca_file-label",
                },
                "certificate_file": {
                    "button": "button-cert_file",
                    "input": "upload-input-cert_file",
                    "label": "mqtt_cert_file-label",
                },
                "key_file": {
                    "button": "button-key_file",
                    "input": "upload-input-key_file",
                    "label": "mqtt_key_file-label",
                },
            }

            # Upload each certificate
            for cert_type, selectors in cert_uploads.items():
                if cert_type in cert_paths and cert_paths[cert_type]:
                    path = cert_paths[cert_type]
                    logger.info(f"Uploading {cert_type}: {path}")

                    try:
                        if os.path.exists(path):
                            await self._upload_hidden_file(
                                file_path=path,
                                input_selector=selectors["input"],
                                button_selector=selectors["button"],
                                label_id=selectors["label"],
                            )
                            logger.info(f"Successfully uploaded {cert_type}")
                        else:
                            logger.error(f"Certificate file not found: {path}")
                    except Exception as e:
                        logger.error(f"Failed to upload {cert_type}: {str(e)}")
                        raise

        except Exception as e:
            logger.error(f"Failed to handle file certificates: {str(e)}")
            raise

    async def _upload_hidden_file(
        self, file_path, input_selector, button_selector, label_id=None
    ):
        """
        Helper method to handle file uploads with hidden input elements

        Args:
            file_path: Path to the file to upload
            input_selector: test-id of the hidden file input
            button_selector: test-id of the browse button
            label_id: ID of the label element (optional)
        """
        try:
            logger.info(f"Attempting to upload file: {file_path}")

            # 1. First ensure the browse button is present and wait for it
            browse_button = self.page.locator(f'[test-id="{button_selector}"]')
            await browse_button.wait_for(state="attached", timeout=5000)

            # 2. Find the associated label if provided
            if label_id:
                label = self.page.locator(f"#{label_id}")
                await label.wait_for(state="attached", timeout=5000)

            # 3. Find the hidden input element
            file_input = self.page.locator(f'[test-id="{input_selector}"]')

            # 4. Set the file using the input element directly
            # This works even with hidden elements in Playwright
            await file_input.set_input_files(file_path)

            # 5. Wait a moment for the upload to register
            await self.page.wait_for_timeout(1000)

            # 6. Verify upload by checking the file name display
            file_name = os.path.basename(file_path)
            file_name_display = self.page.locator(
                f'[test-id="upload-file-{input_selector.split("-")[-1]}"]'
            )
            await file_name_display.wait_for(state="attached", timeout=5000)

            display_text = await file_name_display.inner_text()
            if (
                file_name not in display_text
                and "or drag and drop your file here" in display_text
            ):
                raise Exception(f"File upload verification failed for {file_name}")

        except Exception as e:
            logger.error(f"Failed to upload file: {str(e)}")
            raise

    async def _set_tls_version(self, version):
        """Set TLS version"""
        try:
            logger.info(f"Setting TLS version to {version}")
            await self.page.click('[test-id="input-tls_version"]')
            await self.page.wait_for_timeout(500)
            version_lower = version.lower()
            await self.page.locator(f'[test-id="selectoption-{version_lower}"]').click()
            await self.page.wait_for_timeout(1000)
        except Exception as e:
            logger.error(f"Failed to set TLS version: {str(e)}")
            raise

    async def configure_miscellaneous(self, misc_config):
        """Configure miscellaneous settings"""
        try:
            if not misc_config:
                logger.info(
                    "No miscellaneous configuration provided, skipping configuration"
                )
                return

            logger.info(f"Miscellaneous config: {misc_config}")

            # Navigate to Miscellaneous tab
            logger.info("Clicking Miscellaneous tab")
            await self.page.click('[test-id="tab-miscellaneous"]')
            await self.page.wait_for_timeout(1000)

            # Handle files first
            if "acl_file" in misc_config:
                await self._handle_acl_file(misc_config["acl_file"])

            if "password_file" in misc_config:
                await self._handle_password_file(misc_config["password_file"])

            # Handle switches
            if "persistence" in misc_config:
                await self._set_persistence(misc_config["persistence"])

            if "allow_anonymous" in misc_config:
                await self._set_anonymous_access(misc_config["allow_anonymous"])

            # Handle numeric inputs
            if "max_queued_messages" in misc_config:
                await self._set_max_queued_messages(misc_config["max_queued_messages"])

            if "maximum_packet_size" in misc_config:
                await self._set_max_packet_size(misc_config["maximum_packet_size"])

            await self.page.wait_for_timeout(1000)  # Final wait for all settings

        except Exception as e:
            logger.error(f"Failed to configure miscellaneous settings: {str(e)}")
            raise

    async def _handle_acl_file(self, acl_config):
        """Handle ACL file configuration"""
        try:
            if (
                not acl_config
                or "acl_file_location" not in acl_config
                or "rules" not in acl_config
            ):
                logger.warning("Insufficient ACL configuration")
                return

            # Check if ACL file is already uploaded
            acl_file_label = self.page.locator('label[id="mqtt_acl_file_path-label"]')
            await acl_file_label.wait_for(state="visible", timeout=5000)

            # Get the text of the label
            label_text = await acl_file_label.inner_text()

            # Check if a file is already uploaded
            if "Browse or drag and drop your file here" not in label_text:
                logger.info("ACL file already uploaded. Skipping upload.")
                return

            # Create configuration for ACL file creation
            config = {
                "acl_file_location": acl_config["acl_file_location"],
                "rules": acl_config["rules"],
            }

            # Create the ACL file
            acl_file_path = create_acl_file(config)
            if acl_file_path and os.path.exists(acl_file_path):
                logger.info(f"ACL file created at: {acl_file_path}")
                await self._upload_hidden_file(
                    file_path=acl_file_path,
                    input_selector="upload-input-acl_file_path",
                    button_selector="button-acl_file_path",
                    label_id="mqtt_acl_file_path-label",
                )
                logger.info(f"Successfully uploaded ACL file: {acl_file_path}")
            else:
                raise Exception("Failed to create ACL file")
        except Exception as e:
            logger.error(f"Failed to configure ACL file: {str(e)}")
            raise

    async def _handle_password_file(self, password_config):
        """Handle password file configuration"""
        try:
            if (
                not password_config
                or "password_file_location" not in password_config
                or "users" not in password_config
            ):
                logger.warning("Insufficient password file configuration")
                return

            # Check if password file is already uploaded
            password_file_label = self.page.locator(
                'label[id="mqtt_password_file-label"]'
            )
            await password_file_label.wait_for(state="visible", timeout=5000)

            # Get the text of the label
            label_text = await password_file_label.inner_text()

            # Check if a file is already uploaded
            if "Browse or drag and drop your file here" not in label_text:
                logger.info("Password file already uploaded. Skipping upload.")
                return

            # Create configuration for password file creation
            config = {
                "password_file_location": password_config["password_file_location"],
                "users": password_config["users"],
            }

            # Create the password file
            password_file_path = create_password_file(config)
            if password_file_path and os.path.exists(password_file_path):
                logger.info(f"Password file created at: {password_file_path}")
                await self._upload_hidden_file(
                    file_path=password_file_path,
                    input_selector="upload-input-password_file",
                    button_selector="button-password_file",
                    label_id="mqtt_password_file-label",
                )
                logger.info(
                    f"Successfully uploaded password file: {password_file_path}"
                )
            else:
                raise Exception("Failed to create password file")
        except Exception as e:
            logger.error(f"Failed to configure password file: {str(e)}")
            raise

    async def _set_persistence(self, enabled):
        """Configure persistence setting"""
        try:
            persistence_switch = self.page.locator(
                '[id="mosquitto.mqtt.mqtt.mqtt_persistence"]'
            )
            await persistence_switch.wait_for(state="visible", timeout=30000)

            switch_container = self.page.locator('div[test-id="switch-persistence"]')
            is_persistent = (
                await switch_container.get_attribute("aria-checked") == "true"
            )

            if is_persistent != enabled:
                logger.info(f"Setting persistence to {enabled}")
                await persistence_switch.click(force=True)
                await self.page.wait_for_timeout(1000)
            else:
                logger.info(f"Persistence already in desired state: {enabled}")
        except Exception as e:
            logger.error(f"Failed to configure persistence: {str(e)}")
            raise

    async def _set_anonymous_access(self, enabled):
        """Configure anonymous access setting"""
        try:
            anonymous_switch = self.page.locator(
                '[id="mosquitto.mqtt.mqtt.mqtt_anonymous_access"]'
            )
            await anonymous_switch.wait_for(state="visible", timeout=30000)

            anonymous_container = self.page.locator(
                'div[test-id="switch-anonymous_access"]'
            )
            is_anonymous = (
                await anonymous_container.get_attribute("aria-checked") == "true"
            )

            if is_anonymous != enabled:
                logger.info(f"Setting anonymous access to {enabled}")
                await anonymous_switch.click(force=True)
                await self.page.wait_for_timeout(1000)
            else:
                logger.info(f"Anonymous access already in desired state: {enabled}")
        except Exception as e:
            logger.error(f"Failed to configure anonymous access: {str(e)}")
            raise

    async def _set_max_queued_messages(self, value):
        """Configure maximum queued messages"""
        try:
            input_field = self.page.locator('[test-id="input-max_queued_messages"]')
            await input_field.wait_for(state="visible", timeout=30000)
            await input_field.fill(str(value))
            logger.info(f"Set max queued messages to {value}")
        except Exception as e:
            logger.error(f"Failed to set max queued messages: {str(e)}")
            raise

    async def _set_max_packet_size(self, value):
        """Configure maximum packet size"""
        try:
            input_field = self.page.locator('[test-id="input-max_packet_size"]')
            await input_field.wait_for(state="visible", timeout=30000)
            await input_field.fill(str(value))
            logger.info(f"Set max packet size to {value}")
        except Exception as e:
            logger.error(f"Failed to set max packet size: {str(e)}")
            raise

    async def handle_certificate_uploads(self, cert_config):
        """Handle certificate file uploads with corrected mapping and paths"""
        try:
            if "device_certificates" not in cert_config:
                return

            device_certs = cert_config["device_certificates"]
            logger.info("Starting certificate uploads")

            # Map config keys to test IDs
            file_type_mapping = {
                "ca_file": "ca_file",
                "certificate_file": "cert_file",  # Maps 'certificate_file' from config to 'cert_file' test-id
                "key_file": "key_file",
            }

            for config_key, path in [
                ("ca_file", device_certs.get("ca_file")),
                ("certificate_file", device_certs.get("certificate_file")),
                ("key_file", device_certs.get("key_file")),
            ]:
                if path:
                    # Ensure path starts with /
                    if not path.startswith("/"):
                        path = "/" + path

                    # Get the corresponding test ID
                    test_id = f"upload-input-{file_type_mapping[config_key]}"
                    logger.info(
                        f"Uploading {config_key} using test-id {test_id}, path: {path}"
                    )

                    if os.path.exists(path):
                        # Wait for the input to be available
                        file_input = self.page.locator(f'[test-id="{test_id}"]')
                        await file_input.wait_for(state="visible", timeout=5000)

                        # Upload the file
                        await file_input.set_input_files(path)
                        await self.page.wait_for_timeout(1000)

                        logger.info(f"Successfully uploaded {config_key}")
                    else:
                        logger.error(f"Certificate file not found: {path}")
                        raise FileNotFoundError(f"Certificate file not found: {path}")

        except Exception as e:
            logger.error(f"Failed to upload certificates: {str(e)}")
            raise

    async def add_mqtt_broker(self, config):
        """Configure MQTT broker with all settings"""
        try:
            # Access port from the config
            port = config.get("port")  # Get port from config

            # Configure basic settings (pass the config)
            await self.configure_basic_settings(config)  # Pass the whole config

            # Configure security settings if present (pass the config)
            if "security" in config:
                await self.configure_security(config["security"])

            # Configure miscellaneous settings if present (pass the config)
            if "miscellaneous" in config:
                await self.configure_miscellaneous(config["miscellaneous"])

            # Save and Apply
            save_button = self.page.locator('[test-id="button-saveandapply"]')
            await save_button.click(force=True)
            await self.wait_for_spinner()

        except Exception as e:
            logger.error(f"Failed to configure MQTT Broker: {str(e)}")
            raise

    async def upload_certificate_files(self, cert_paths):
        """
        Upload a set of certificate files with proper error handling

        Args:
            cert_paths: Dictionary containing paths for 'ca_file', 'certificate_file', and 'key_file'
        """
        cert_selectors = {
            "ca_file": {
                "button": "button-ca_file",
                "input": "upload-input-ca_file",
                "label": "mqtt_ca_file-label",
            },
            "certificate_file": {
                "button": "button-cert_file",
                "input": "upload-input-cert_file",
                "label": "mqtt_cert_file-label",
            },
            "key_file": {
                "button": "button-key_file",
                "input": "upload-input-key_file",
                "label": "mqtt_key_file-label",
            },
        }

        for cert_type, path in cert_paths.items():
            if not path:
                continue

            if cert_type not in cert_selectors:
                logger.warning(f"Unknown certificate type: {cert_type}")
                continue

            selectors = cert_selectors[cert_type]

            try:
                await self._upload_hidden_file(
                    file_path=path,
                    input_selector=selectors["input"],
                    button_selector=selectors["button"],
                    label_id=selectors["label"],
                )
                logger.info(f"Successfully uploaded {cert_type}")
            except Exception as e:
                logger.error(f"Failed to upload {cert_type}: {str(e)}")
                raise

    async def upload_certificate(self, file_type: str, file_path: str):
        """Helper method to handle certificate file uploads"""
        try:
            logger.info(f"Starting upload for {file_type}: {file_path}")

            # Ensure the file exists before attempting to upload
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Certificate file not found: {file_path}")

            # Map of file types to their input test-ids
            input_selectors = {
                "ca_file": '[test-id="upload-input-ca_file"]',
                "cert_file": '[test-id="upload-input-cert_file"]',
                "key_file": '[test-id="upload-input-key_file"]',
            }

            # Get the input selector for the specific file type
            input_selector = input_selectors.get(file_type)
            if not input_selector:
                raise ValueError(f"Unknown file type: {file_type}")

            # Locate the file input element
            file_input = self.page.locator(input_selector)

            # Wait for the input to be visible and attached
            await file_input.wait_for(state="attached", timeout=5000)

            # Set the file path for upload
            await file_input.set_input_files(file_path)

            logger.info(f"Successfully uploaded {file_type}")

            # Optional: Add a small delay to ensure upload is processed
            await self.page.wait_for_timeout(1000)

        except Exception as e:
            logger.error(f"Failed to upload {file_type}: {str(e)}")

            # Optional: Take a screenshot for debugging
            raise

    async def handle_certificate_selection(self, cert_config):
        """Handle certificate selection from dropdowns when using device certificates"""
        try:
            if not cert_config.get("certificate_files_from_device"):
                return

            device_certs = cert_config["device_certificates"]
            logger.info("Selecting certificates from device")

            # Map of config keys to correct element IDs and expected filenames
            cert_mapping = {
                "ca_file": {
                    "wrapper": "selectwrapper-ca_file",
                    "input": "input-ca_file",
                    "filename": device_certs.get("ca_file"),
                },
                "certificate_file": {
                    "wrapper": "selectwrapper-cert_file",
                    "input": "input-cert_file",
                    "filename": device_certs.get("certificate_file"),
                },
                "key_file": {
                    "wrapper": "selectwrapper-key_file",
                    "input": "input-key_file",
                    "filename": device_certs.get("key_file"),
                },
            }

            for config_key, mapping in cert_mapping.items():
                filename = mapping["filename"]
                if not filename:
                    continue

                logger.info(f"Selecting {config_key}: {filename}")

                # Locate the wrapper and input elements
                wrapper = self.page.locator(f'[test-id="{mapping["wrapper"]}"]')
                input_element = self.page.locator(f'[test-id="{mapping["input"]}"]')
                # Ensure the wrapper is visible
                await wrapper.wait_for(state="visible", timeout=5000)
                # Try clicking the dropdown
                await wrapper.click(timeout=3000)
                await self.page.wait_for_timeout(1000)

                # Locate all options in the dropdown
                options = self.page.locator(
                    f'[test-id="{mapping["wrapper"]}-listbox"] [test-id="options-wrapper"] li div.truncate'
                )
                # Get the total number of options
                option_count = await options.count()

                # Log the number of options for debugging
                logger.info(f"Found {option_count} options for {config_key}")

                # Iterate through all options
                for i in range(option_count):
                    # Get the current option
                    option = options.nth(i)

                    # Get the text of the option
                    option_text = await option.inner_text()

                    # Check if the option text exactly matches the filename
                    if option_text.strip() == filename:
                        # Find the parent li element and click it
                        parent_li = option.locator("xpath=..")
                        await parent_li.click(timeout=2000)

                        logger.info(f"Selected {config_key} option: {option_text}")
                        break

                # Wait a moment after selection
                await self.page.wait_for_timeout(1000)

        except Exception as e:
            logger.error(f"Failed to select certificates: {str(e)}")
            raise
