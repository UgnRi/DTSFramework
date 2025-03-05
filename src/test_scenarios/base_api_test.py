from src.test_scenarios.base_scenario import BaseTestScenario
from src.utils.logger import setup_logger
import aiohttp
import json
import asyncio
from typing import Dict, Any, List, Union, Optional

logger = setup_logger()


class BaseAPITest(BaseTestScenario):
    """Base class for API tests."""

    def __init__(self, device_config: Dict[str, Any], scenario_config=None):
        # Don't use the scenario loading mechanism from BaseTestScenario
        # We'll just initialize the necessary attributes directly
        self.device_config = device_config
        self.scenario_config = scenario_config or {}
        # Skip calling super().__init__ to avoid loading scenario_name.json
        self.logger = logger

        self.device_ip = self.device_config["device"]["ip"]
        self.username = self.device_config["device"]["credentials"]["username"]
        self.password = self.device_config["device"]["credentials"]["password"]
        self.session = None
        self.token = None
        self.base_url = f"https://{self.device_ip}/api"

    async def setup(self):
        """Setup test environment - establish API connection."""
        logger.info("BaseAPITest: Setting up API connection")
        await self.connect()
        return True

    async def execute(self):
        """Execute test scenario - this should be implemented by child classes."""
        logger.warning(
            "BaseAPITest: execute() method called on base class, should be overridden by child class"
        )
        return True

    async def cleanup(self):
        """Clean up after test - close API connection."""
        logger.info("BaseAPITest: Cleaning up API connection")
        await self.disconnect()
        return True

    async def connect(self):
        """Establish API connection and authenticate."""
        try:
            # Create aiohttp session with SSL verification disabled
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False)
            )

            # Authenticate with credentials
            auth_payload = {"username": self.username, "password": self.password}

            # Use the correct login endpoint
            login_url = f"{self.base_url}/login"
            logger.info(f"Authenticating to API: {login_url}")
            response = await self.session.post(login_url, json=auth_payload)

            if response.status != 200:
                error_text = await response.text()
                raise Exception(
                    f"Authentication failed: {response.status} - {error_text}"
                )

            # Extract authentication token from the response data
            auth_data = await response.json()
            self.token = auth_data.get("data", {}).get("token")

            if not self.token:
                raise Exception("Authentication succeeded but no token was received")

            logger.info("API authentication successful")
            return True

        except Exception as e:
            logger.error(f"API connection failed: {str(e)}")
            await self.disconnect()
            raise

    async def disconnect(self):
        """Close API connection."""
        if self.session:
            await self.session.close()
            self.session = None
            self.token = None
            logger.info("API connection closed")

    async def api_request(
        self,
        method: str,
        endpoint: str,
        data: dict = None,
        headers=None,
        raw_data=False,
    ) -> dict:
        """Send an API request with the authenticated session."""
        if not self.session or not self.token:
            raise Exception("Not connected to API, call connect() first")

        url = f"{self.base_url}/{endpoint}"

        # Use custom headers if provided, otherwise use default headers
        if headers is None:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
        else:
            # Ensure authorization header is included
            if "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {self.token}"

        try:
            logger.debug(f"API {method} request to {url}")

            if method.lower() == "get":
                response = await self.session.get(url, headers=headers)
            elif method.lower() == "post":
                if raw_data:
                    # Use raw data as is without JSON encoding
                    response = await self.session.post(url, headers=headers, data=data)
                else:
                    # Use JSON encoding
                    response = await self.session.post(url, headers=headers, json=data)
            elif method.lower() == "put":
                if raw_data:
                    response = await self.session.put(url, headers=headers, data=data)
                else:
                    response = await self.session.put(url, headers=headers, json=data)
            elif method.lower() == "delete":
                response = await self.session.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status < 200 or response.status >= 300:
                error_text = await response.text()
                raise Exception(f"API request failed: {response.status} - {error_text}")

            # Try to parse JSON, if it fails return raw text
            try:
                return await response.json()
            except:
                return {"text": await response.text()}
        except Exception as e:
            logger.error(f"API request failed for {url}: {str(e)}")
            raise

    # async def api_request(self, method: str, endpoint: str, data: dict = None) -> dict:
    #     """Send an API request with the authenticated session."""
    #     if not self.session or not self.token:
    #         raise Exception("Not connected to API, call connect() first")

    #     url = f"{self.base_url}/{endpoint}"
    #     headers = {
    #         "Authorization": f"Bearer {self.token}",
    #         "Content-Type": "application/json"
    #     }

    #     try:
    #         logger.debug(f"API {method} request to {url}")
    #         if method.lower() == "get":
    #             response = await self.session.get(url, headers=headers)
    #         elif method.lower() == "post":
    #             response = await self.session.post(url, headers=headers, json=data)
    #         elif method.lower() == "put":
    #             response = await self.session.put(url, headers=headers, json=data)
    #         elif method.lower() == "delete":
    #             response = await self.session.delete(url, headers=headers)
    #         else:
    #             raise ValueError(f"Unsupported HTTP method: {method}")

    #         if response.status < 200 or response.status >= 300:
    #             error_text = await response.text()
    #             raise Exception(f"API request failed: {response.status} - {error_text}")

    #         # Try to parse JSON, if it fails return raw text
    #         try:
    #             return await response.json()
    #         except:
    #             return {"text": await response.text()}

    #     except Exception as e:
    #         logger.error(f"API request failed for {url}: {str(e)}")
    #         raise

    async def get_config(self, endpoint: str) -> dict:
        """Get configuration from API."""
        response = await self.api_request("get", endpoint)
        # API might return data within a 'data' field
        if "data" in response:
            return response["data"]
        return response

    async def set_config(self, endpoint: str, config: dict) -> dict:
        """Set configuration via API."""
        # Wrap config in data field if not already wrapped
        if "data" not in config:
            wrapped_config = {"data": config}
        else:
            wrapped_config = config
        return await self.api_request("put", endpoint, wrapped_config)

    async def restart_service(self, service_name: str) -> bool:
        """Restart a service via API."""
        try:
            endpoint = f"services/{service_name}/restart"
            result = await self.api_request("post", endpoint)
            logger.info(f"Service {service_name} restart requested: {result}")
            # Wait for service to initialize
            await asyncio.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Failed to restart service {service_name}: {str(e)}")
            return False

    def format_bool_value(self, value: bool) -> int:
        """Format Boolean value as Integer for API compatibility."""
        return 1 if value else 0

    def _extract_config(self) -> Dict[str, Any]:
        """Extract configuration with support for both nested and flat structures."""
        if not self.scenario_config:
            return {}

        # Check if the config is nested under 'config' key
        if "config" in self.scenario_config and isinstance(
            self.scenario_config["config"], dict
        ):
            return self.scenario_config["config"]

        # If not nested, use the scenario_config directly
        return self.scenario_config
