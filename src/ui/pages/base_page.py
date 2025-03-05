# src/ui/pages/base_page.py
from playwright.async_api import Page
from src.utils.logger import setup_logger

logger = setup_logger()

class BasePage:
    def __init__(self, page: Page):
        self.page = page
        self.logger = logger
        
    async def wait_for_spinner(self):
        """Wait for loading spinner to disappear"""
        try:
            await self.page.wait_for_selector('.loading-spinner', state='attached', timeout=1000)
            await self.page.wait_for_selector('.loading-spinner', state='detached', timeout=30000)
        except Exception:
            # Spinner might not appear at all, which is fine
            pass
            
    async def wait_for_element(self, selector: str, timeout: int = 30000):
        """Wait for element to be visible"""
        try:
            await self.page.wait_for_selector(selector, state='visible', timeout=timeout)
        except Exception as e:
            self.logger.error(f"Element {selector} not found: {str(e)}")
            await self.page.screenshot(path='element_not_found.png')
            raise
            
    async def fill_input(self, selector: str, value: str):
        """Fill input field"""
        try:
            await self.wait_for_element(selector)
            await self.page.fill(selector, value)
        except Exception as e:
            self.logger.error(f"Failed to fill input {selector}: {str(e)}")
            raise
            
    async def click_element(self, selector: str, force: bool = False):
        """Click element"""
        try:
            await self.wait_for_element(selector)
            await self.page.click(selector, force=force)
        except Exception as e:
            self.logger.error(f"Failed to click element {selector}: {str(e)}")
            raise