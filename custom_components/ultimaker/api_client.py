"""API client for Ultimaker printers."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import aiohttp
import async_timeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import Throttle

from .const import (
    LOCAL_API_URL,
    CLOUD_API_URL,
    DEFAULT_SCAN_INTERVAL_LOCAL,
    DEFAULT_SCAN_INTERVAL_CLOUD,
    USER_INFO_URL,
)

_LOGGER = logging.getLogger(__name__)


class UltimakerApiClientBase:
    """Base class for Ultimaker API clients."""

    def __init__(self, session: aiohttp.ClientSession):
        """Initialize the API client."""
        self._session = session
        self._data = None

    @property
    def latest_data(self) -> Dict[str, Any]:
        """Return the latest data."""
        return self._data or {}

    async def async_update(self) -> None:
        """Update data from the API."""
        raise NotImplementedError("Subclasses must implement this method")


class UltimakerLocalApiClient(UltimakerApiClientBase):
    """Client for interacting with the local Ultimaker API."""

    def __init__(self, session: aiohttp.ClientSession, host: str):
        """Initialize the API client."""
        super().__init__(session)
        self._host = host
        self._url_printer = LOCAL_API_URL.format(host) + "/printer"
        self._url_print_job = LOCAL_API_URL.format(host) + "/print_job"
        self._url_system = LOCAL_API_URL.format(host) + "/system"

    @Throttle(timedelta(seconds=DEFAULT_SCAN_INTERVAL_LOCAL))
    async def async_update(self) -> None:
        """Update data from the API."""
        if not self._host:
            _LOGGER.error("No host configured for Ultimaker printer")
            raise UpdateFailed("No host configured")

        try:
            # Fetch printer data - this contains all the information we need
            _LOGGER.debug("Fetching printer data from %s", self._url_printer)
            printer_data = await self._fetch_data(self._url_printer)
            if not printer_data:
                _LOGGER.error("Failed to fetch printer data from %s", self._url_printer)
                self._data = {"status": "not connected"}
                raise UpdateFailed("Failed to fetch printer data")

            # Use the printer data directly
            self._data = printer_data

            # Ensure status is always present
            if "status" not in self._data:
                self._data["status"] = "idle"

            # Try to fetch print job data for additional information
            _LOGGER.debug("Fetching print job data from %s", self._url_print_job)
            try:
                print_job_data = await self._fetch_data(self._url_print_job)
                if print_job_data:
                    # Add print job data fields
                    for key, value in print_job_data.items():
                        self._data[key] = value
            except Exception as err:
                _LOGGER.warning("Error fetching print job data (this is normal if no print job is active): %s", err)
                # Ensure essential print job fields are present even if no job is active
                self._data.setdefault("state", "idle")
                self._data.setdefault("progress", 0)

            # Log the structured data for debugging
            _LOGGER.debug("Structured data: %s", self._data)

            _LOGGER.debug("Successfully updated data from Ultimaker printer at %s", self._host)
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error fetching data from Ultimaker printer at %s: %s", self._host, err)
            self._data = {"status": "not connected"}
            raise UpdateFailed(f"Connection error: {err}")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error fetching data from Ultimaker printer at %s", self._host)
            self._data = {"status": "timeout"}
            raise UpdateFailed("Connection timed out")
        except Exception as err:
            _LOGGER.error("Unknown error fetching data from Ultimaker printer at %s: %s", self._host, err)
            self._data = {"status": "error"}
            raise UpdateFailed(f"Unknown error: {err}")

        self._data["sampleTime"] = datetime.now()

    async def _fetch_data(self, url: str) -> Dict[str, Any]:
        """Fetch data from the API."""
        try:
            with async_timeout.timeout(5):
                _LOGGER.debug("Making GET request to %s", url)
                response = await self._session.get(url)

                if response.status >= 400:
                    error_text = await response.text()
                    _LOGGER.error(
                        "Error response from Ultimaker printer at %s: HTTP %s - %s",
                        self._host,
                        response.status,
                        error_text
                    )
                    return {}

                data = await response.json()
                _LOGGER.debug("Received data from %s: %s", url, data)

                # Check if data is empty or None
                if not data:
                    _LOGGER.warning(
                        "Empty data received from Ultimaker printer at %s using url %s",
                        self._host,
                        url,
                    )

                return data

        except aiohttp.ClientError as err:
            _LOGGER.warning("Printer %s is offline or unreachable: %s", self._host, err)
            raise
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Timeout error occurred while polling Ultimaker printer at %s using url %s",
                self._host,
                url,
            )
            raise
        except ValueError as err:
            _LOGGER.error(
                "Invalid JSON response from Ultimaker printer at %s using url %s: %s",
                self._host,
                url,
                err,
            )
            return {}
        except Exception as err:
            _LOGGER.error(
                "Unknown error occurred while polling Ultimaker printer at %s using url %s: %s",
                self._host,
                url,
                err,
            )
            return {}


class UltimakerCloudApiClient(UltimakerApiClientBase):
    """Client for interacting with the Ultimaker Connect API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str,
        token_expiry: datetime,
        cluster_id: Optional[str] = None,
    ):
        """Initialize the API client."""
        super().__init__(session)
        self._token = token
        self._token_expiry = token_expiry
        self._cluster_id = cluster_id
        self._headers = {"Authorization": f"Bearer {self._token}"}
        self.oauth_session = None  # Will be set by __init__.py

    @Throttle(timedelta(seconds=DEFAULT_SCAN_INTERVAL_CLOUD))
    async def async_update(self) -> None:
        """Update data from the API."""
        if not self._token or not self._cluster_id:
            _LOGGER.error("Missing token or cluster_id for Ultimaker Cloud API")
            self._data = {"status": "not configured"}
            return

        if self._token_expiry and self._token_expiry < datetime.now():
            _LOGGER.warning("Token expired for Ultimaker Cloud API, attempting refresh")
            if not await self._refresh_token():
                raise UpdateFailed("Token expired and refresh failed")

        try:
            # Get cluster status
            cluster_status = await self._api_request(
                "GET", f"/clusters/{self._cluster_id}/status"
            )

            # Get cluster details
            cluster_details = await self._api_request(
                "GET", f"/clusters/{self._cluster_id}"
            )

            # Combine data
            self._data = {
                "status": "connected",
                "cluster_status": cluster_status.get("status", "unknown"),
                "printer_count": len(cluster_status.get("printers", [])),
                "cluster_name": cluster_details.get("name", "Unknown Cluster"),
            }

            # Add printer data
            printers = cluster_status.get("printers", [])
            if printers:
                # Use the first printer for compatibility with local API
                printer = printers[0]
                self._data.update({
                    "status": printer.get("status", "unknown"),
                    "state": printer.get("state", "unknown"),
                    "progress": printer.get("progress", 0),
                })

                # Add bed data if available
                bed = printer.get("bed", {})
                if bed:
                    self._data["bed"] = bed

                # Add head data if available
                heads = printer.get("heads", [])
                if heads:
                    self._data["heads"] = heads

        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching data from Ultimaker Cloud API: %s", err)
            self._data = {"status": "not connected"}
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error fetching data from Ultimaker Cloud API")
            self._data = {"status": "timeout"}
        except Exception as err:
            _LOGGER.error("Unknown error fetching data from Ultimaker Cloud API: %s", err)
            self._data = {"status": "error"}

        self._data["sampleTime"] = datetime.now()

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the API."""
        url = f"{CLOUD_API_URL}{endpoint}"

        try:
            with async_timeout.timeout(10):
                async with self._session.request(
                    method, url, json=data, params=params, headers=self._headers
                ) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        _LOGGER.error(
                            "Error response from Ultimaker Cloud API: %s - %s",
                            response.status,
                            error_text,
                        )
                        return {}
                    return await response.json()
        except aiohttp.ClientError as err:
            _LOGGER.error("Error making request to Ultimaker Cloud API: %s", err)
            raise
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Timeout error making request to Ultimaker Cloud API: %s", url
            )
            raise
        except Exception as err:
            _LOGGER.error(
                "Unknown error making request to Ultimaker Cloud API: %s - %s",
                url,
                err,
            )
            return {}

    async def get_clusters(self) -> List[Dict[str, Any]]:
        """Get all available clusters."""
        response = await self._api_request("GET", "/clusters")
        return response.get("data", [])

    async def select_cluster(self, cluster_id: str) -> None:
        """Select a cluster to use."""
        self._cluster_id = cluster_id

    async def get_user_info(self) -> Dict[str, Any]:
        """Get information about the current user."""
        try:
            # Make a direct request to the user info endpoint
            with async_timeout.timeout(10):
                async with self._session.get(
                    USER_INFO_URL, headers=self._headers
                ) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        _LOGGER.error(
                            "Error getting user info: %s - %s",
                            response.status,
                            error_text,
                        )
                        return {}
                    return await response.json()
        except Exception as err:
            _LOGGER.error("Error getting user info: %s", err)
            return {}

    async def get_workspaces(self) -> List[Dict[str, Any]]:
        """Get available workspaces (organizations) for the user."""
        try:
            user_info = await self.get_user_info()
            # Extract organization memberships from user info
            memberships = user_info.get("organization_memberships", [])
            return [
                {
                    "id": org.get("id"),
                    "name": org.get("name"),
                    "role": org.get("role"),
                }
                for org in memberships
            ]
        except Exception as err:
            _LOGGER.error("Error getting workspaces: %s", err)
            return []

    async def _refresh_token(self) -> bool:
        """Refresh the OAuth2 token.

        Returns:
            bool: True if the token was refreshed successfully, False otherwise.
        """
        if not self.oauth_session:
            _LOGGER.error("No OAuth session available for token refresh")
            return False

        try:
            # Refresh the token
            await self.oauth_session.async_ensure_token_valid()

            # Update our token and expiry
            token = self.oauth_session.token
            self._token = token["access_token"]
            self._token_expiry = datetime.now() + timedelta(seconds=token.get("expires_in", 3600))
            self._headers = {"Authorization": f"Bearer {self._token}"}

            _LOGGER.info("Successfully refreshed OAuth token")
            return True
        except Exception as err:
            _LOGGER.error("Error refreshing OAuth token: %s", err)
            return False

    async def switch_workspace(self, organization_id: str) -> bool:
        """Switch to a different workspace (organization).

        This requires re-authentication with the new organization_id.
        The caller should handle the re-authentication process.

        Returns:
            bool: True if the switch was successful, False otherwise.
        """
        # Just store the organization ID - actual switching happens during re-auth
        try:
            # Verify the organization exists
            workspaces = await self.get_workspaces()
            for workspace in workspaces:
                if workspace.get("id") == organization_id:
                    return True
            _LOGGER.error("Organization ID %s not found in user's workspaces", organization_id)
            return False
        except Exception as err:
            _LOGGER.error("Error switching workspace: %s", err)
            return False
