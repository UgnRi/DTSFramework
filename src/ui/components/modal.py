from playwright.async_api import Page
from ...utils.logger import setup_logger

logger = setup_logger()

class Modal:
    def __init__(self, page: Page):
        self.page = page
        
    async def wait_for_modal(self):
        """Wait for modal to appear."""
        try:
            await self.page.wait_for_selector('[data-testid="modal"]', 
                                            state='visible', 
                                            timeout=5000)
        except Exception as e:
            logger.error(f"Modal did not appear: {str(e)}")
            raise
            
    async def close(self):
        """Close the modal."""
        try:
            await self.page.click('[data-testid="modal-close"]')
            await self.page.wait_for_selector('[data-testid="modal"]', 
                                            state='hidden', 
                                            timeout=5000)
        except Exception as e:
            logger.error(f"Failed to close modal: {str(e)}")
            raise