from playwright.async_api import Page
from src.test_scenarios.base_scenario import BaseTestScenario
from src.ui.pages.login_page import LoginPage
from typing import Dict, Any


class BaseGUITest(BaseTestScenario):
    def __init__(self, device_config: Dict[str, Any], scenario_name: str, page: Page):
        super().__init__(device_config=device_config, scenario_name=scenario_name)
        self.page = page
        self.login_page = LoginPage(page, device_config)

    async def setup(self):
        """Setup GUI test"""
        try:
            # Login to web interface
            await self.login_page.login(
                self.device_config["device"]["credentials"]["u      sername"],
                self.device_config["device"]["credentials"]["password"],
            )
            self.logger.info("Logged in to web interface")
        except Exception as e:
            self.logger.error(f"Failed to setup GUI test: {str(e)}")
            raise

    async def logout(self):
        """Logout from web interface with extensive debugging"""
        try:
            # Extensive logging of current page state
            current_url = self.page.url
            self.logger.info(f"Current URL before logout: {current_url}")

            # Capture and log all buttons
            try:
                all_buttons = await self.page.evaluate(
                    """() => {
                    return Array.from(document.querySelectorAll('button'))
                        .map(button => ({
                            text: button.textContent?.trim(),
                            testId: button.getAttribute('test-id'),
                            classes: button.className,
                            visible: button.offsetParent !== null
                        }));
                }"""
                )
            except Exception as btn_error:
                self.logger.error(
                    f"Failed to capture button information: {str(btn_error)}"
                )

            # Step 1: Try to find and click user dropdown
            dropdown_selectors = [
                '[test-id="header-main-expand-dropdown"]',
                'button[test-id="header-main-expand-dropdown"]',
                'div[test-id="header-main-expand-dropdown"] button',
            ]

            dropdown_clicked = False
            for selector in dropdown_selectors:
                try:
                    dropdown_button = self.page.locator(selector)
                    dropdown_count = await dropdown_button.count()

                    self.logger.info(f"Checking dropdown selector: {selector}")
                    self.logger.info(f"Dropdown button count: {dropdown_count}")

                    if dropdown_count > 0:
                        # Check if the button is actually clickable
                        first_button = dropdown_button.first

                        # Log button details
                        try:
                            is_visible = await first_button.is_visible()
                            is_enabled = await first_button.is_enabled()
                            self.logger.info(
                                f"Dropdown button - Visible: {is_visible}, Enabled: {is_enabled}"
                            )
                        except Exception as detail_error:
                            self.logger.error(
                                f"Failed to get button details: {str(detail_error)}"
                            )

                        try:
                            await first_button.click(timeout=5000)
                            self.logger.info(
                                f"Successfully clicked dropdown with selector: {selector}"
                            )
                            dropdown_clicked = True

                            # Short wait after clicking
                            await self.page.wait_for_timeout(1000)
                            break
                        except Exception as click_error:
                            self.logger.error(
                                f"Failed to click dropdown with {selector}: {str(click_error)}"
                            )

                except Exception as selector_error:
                    self.logger.error(
                        f"Error with selector {selector}: {str(selector_error)}"
                    )

            if not dropdown_clicked:
                self.logger.error("Could not click user dropdown")

                # Capture page content
                page_content = await self.page.content()

                raise Exception("Failed to open user dropdown")

            # Step 2: Try to find and click logout button
            logout_selectors = [
                '[test-id="header-logout"]',
                'button[test-id="header-logout"]',
                'a[test-id="header-logout"]',
            ]

            logout_clicked = False
            for selector in logout_selectors:
                try:
                    logout_button = self.page.locator(selector)
                    logout_count = await logout_button.count()

                    self.logger.info(f"Checking logout selector: {selector}")
                    self.logger.info(f"Logout button count: {logout_count}")

                    if logout_count > 0:
                        # Check if the button is actually clickable
                        first_button = logout_button.first

                        # Log button details
                        try:
                            is_visible = await first_button.is_visible()
                            is_enabled = await first_button.is_enabled()
                            self.logger.info(
                                f"Logout button - Visible: {is_visible}, Enabled: {is_enabled}"
                            )
                        except Exception as detail_error:
                            self.logger.error(
                                f"Failed to get logout button details: {str(detail_error)}"
                            )

                        try:
                            await first_button.click(timeout=5000)
                            self.logger.info(
                                f"Successfully clicked logout with selector: {selector}"
                            )
                            logout_clicked = True

                            # Wait for login page
                            await self.page.wait_for_selector(
                                'input[name="username"]', timeout=10000
                            )
                            break
                        except Exception as click_error:
                            self.logger.error(
                                f"Failed to click logout with {selector}: {str(click_error)}"
                            )

                except Exception as selector_error:
                    self.logger.error(
                        f"Error with selector {selector}: {str(selector_error)}"
                    )

            if not logout_clicked:
                self.logger.error("Could not click logout button")
                raise Exception("Failed to click logout button")

            self.logger.info("Logout process completed successfully")

        except Exception as e:
            self.logger.error(f"Overall logout process failed: {str(e)}")
            raise

    async def cleanup(self):
        """Cleanup after GUI test"""
        try:
            # Attempt to logout
            await self.logout()
        except Exception as e:
            self.logger.error(f"GUI cleanup failed: {str(e)}")
