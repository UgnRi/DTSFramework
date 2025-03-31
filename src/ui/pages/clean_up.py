# clean_up.py
from .base_page import BasePage
from ...utils.logger import setup_logger

logger = setup_logger()


class CleanUp(BasePage):
    def __init__(self, page):
        super().__init__(page)

    async def delete_wifi_interface(self):
        """
        Delete all WiFi interfaces by clicking every delete button
        """
        try:
            await self.page.wait_for_timeout(5000)
            delete_buttons = self.page.locator('[test-id="button-delete"]')

            # Get total number of delete buttons
            total_buttons = await delete_buttons.count()

            # Track successful deletions
            successful_deletions = 0

            # Iterate through all delete buttons
            for _ in range(total_buttons - 1):
                try:
                    # Always select the first delete button (as list updates after each deletion)
                    first_delete_button = self.page.locator(
                        '[test-id="button-delete"]'
                    ).first

                    # Wait for the button to be visible and clickable
                    await first_delete_button.wait_for(state="visible")

                    # Click the delete button
                    await first_delete_button.click()

                    # Wait for and click confirmation dialog if it exists
                    try:
                        confirm_button = self.page.locator('[test-id="button-ok"]')
                        await confirm_button.click()
                        await self.page.wait_for_timeout(
                            2000
                        )  # Short wait between deletions
                        successful_deletions += 1
                    except:
                        # If no confirmation button, still count as successful
                        successful_deletions += 1

                except Exception as button_error:
                    logger.error(f"Error deleting interface: {button_error}")
                    break

            logger.info(f"Deleted {successful_deletions} DTS interfaces")
            return successful_deletions > 0

        except Exception as e:
            logger.error(f"Overall deletion process failed: {e}")
            return False
