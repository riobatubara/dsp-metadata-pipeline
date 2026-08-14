from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.common.logging import logger


# How to use
# client = APIClient("https://api.example.com")

# data = client.get(
#     "/endpoint",
#     params={"limit": 50},
# )

class APIClient:
    """Reusable HTTP client with timeout and retry handling."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self.session = requests.Session()

        retry_strategy = Retry(
            total=retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send a GET request and return the JSON response."""

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        logger.debug("GET %s", url)

        response = self.session.get(
            url,
            params=params,
            headers=headers,
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send a POST request and return the JSON response."""

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        logger.debug("POST %s", url)

        response = self.session.post(
            url,
            json=data,
            headers=headers,
            timeout=self.timeout,
        )

        response.raise_for_status()

        return response.json()

    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self) -> "APIClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()