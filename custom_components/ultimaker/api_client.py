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
_LOGGER.info("Initializing Ultimaker API client module")


class UltimakerApiClientBase:
    """Base class for Ultimaker API clients."""

    def __init__(self, session: aiohttp.ClientSession):
        """Initialize the API client."""
        _LOGGER.debug("Initializing UltimakerApiClientBase")
        self._session = session
        self._data = None
        _LOGGER.debug("UltimakerApiClientBase initialized")

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
        _LOGGER.info("Initializing UltimakerLocalApiClient for host: %s", host)
        super().__init__(session)
        self._host = host
        self._url_printer = LOCAL_API_URL.format(host) + "/printer"
        self._url_print_job = LOCAL_API_URL.format(host) + "/print_job"
        self._url_system = LOCAL_API_URL.format(host) + "/system"
        _LOGGER.debug("Local API URLs configured: printer=%s, print_job=%s, system=%s", 
                     self._url_printer, self._url_print_job, self._url_system)
        _LOGGER.info("UltimakerLocalApiClient initialized successfully")

    @Throttle(timedelta(seconds=DEFAULT_SCAN_INTERVAL_LOCAL))
    async def async_update(self) -> None:
        """Update data from the API."""
        _LOGGER.info("Starting update cycle for Ultimaker printer at %s", self._host)

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

            _LOGGER.debug("Received printer data: %s", printer_data)

            # Use the printer data directly
            self._data = printer_data
            _LOGGER.debug("Stored printer data in self._data")

            # Ensure status is always present
            if "status" not in self._data:
                _LOGGER.debug("Status field not found in printer data, defaulting to 'idle'")
                self._data["status"] = "idle"
            else:
                _LOGGER.info("Printer status: %s", self._data["status"])

            # Try to fetch print job data for additional information
            _LOGGER.debug("Fetching print job data from %s", self._url_print_job)
            try:
                print_job_data = await self._fetch_data(self._url_print_job)
                if print_job_data:
                    _LOGGER.debug("Received print job data: %s", print_job_data)
                    # Add print job data fields
                    _LOGGER.debug("Merging print job data into self._data")
                    for key, value in print_job_data.items():
                        _LOGGER.debug("Adding print job field: %s = %s", key, value)
                        self._data[key] = value
                else:
                    _LOGGER.debug("No print job data received (printer may be idle)")
            except Exception as err:
                _LOGGER.warning("Error fetching print job data (this is normal if no print job is active): %s", err)
                # Ensure essential print job fields are present even if no job is active
                _LOGGER.debug("Setting default print job fields")
                self._data.setdefault("state", "idle")
                self._data.setdefault("progress", 0)

            # Log the structured data for debugging
            _LOGGER.debug("Final structured data: %s", self._data)

            _LOGGER.info("Successfully updated data from Ultimaker printer at %s", self._host)
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error fetching data from Ultimaker printer at %s: %s", self._host, err)
            self._data = {"status": "not connected"}
            _LOGGER.warning("Setting status to 'not connected' due to connection error")
            raise UpdateFailed(f"Connection error: {err}")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error fetching data from Ultimaker printer at %s", self._host)
            self._data = {"status": "timeout"}
            _LOGGER.warning("Setting status to 'timeout' due to timeout error")
            raise UpdateFailed("Connection timed out")
        except Exception as err:
            _LOGGER.error("Unknown error fetching data from Ultimaker printer at %s: %s", self._host, err)
            self._data = {"status": "error"}
            _LOGGER.warning("Setting status to 'error' due to unknown error")
            raise UpdateFailed(f"Unknown error: {err}")

        # Add sample time to data
        current_time = datetime.now()
        self._data["sampleTime"] = current_time
        _LOGGER.debug("Added sample time to data: %s", current_time)
        _LOGGER.info("Update cycle completed for Ultimaker printer at %s", self._host)

    async def _fetch_data(self, url: str) -> Dict[str, Any]:
        """Fetch data from the API."""
        _LOGGER.debug("Starting _fetch_data for URL: %s", url)
        start_time = datetime.now()

        try:
            with async_timeout.timeout(5):
                _LOGGER.debug("Making GET request to %s", url)
                response = await self._session.get(url)
                _LOGGER.debug("Received response from %s with status code: %s", url, response.status)

                if response.status >= 400:
                    error_text = await response.text()
                    _LOGGER.error(
                        "Error response from Ultimaker printer at %s: HTTP %s - %s",
                        self._host,
                        response.status,
                        error_text
                    )
                    _LOGGER.warning("Request to %s failed with status code %s", url, response.status)
                    return {}

                _LOGGER.debug("Parsing JSON response from %s", url)
                data = await response.json()
                _LOGGER.debug("Received data from %s: %s", url, data)

                # Check if data is empty or None
                if not data:
                    _LOGGER.warning(
                        "Empty data received from Ultimaker printer at %s using url %s",
                        self._host,
                        url,
                    )
                else:
                    _LOGGER.info("Successfully fetched data from %s (%s keys in response)", 
                                url, len(data) if isinstance(data, dict) else "non-dict response")

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                _LOGGER.debug("_fetch_data completed for %s in %.3f seconds", url, duration)

                return data

        except aiohttp.ClientError as err:
            _LOGGER.warning("Printer %s is offline or unreachable: %s", self._host, err)
            _LOGGER.debug("ClientError details: %s", str(err))
            raise
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Timeout error occurred while polling Ultimaker printer at %s using url %s",
                self._host,
                url,
            )
            _LOGGER.debug("Request timed out after 5 seconds")
            raise
        except ValueError as err:
            _LOGGER.error(
                "Invalid JSON response from Ultimaker printer at %s using url %s: %s",
                self._host,
                url,
                err,
            )
            _LOGGER.debug("JSON parsing error details: %s", str(err))
            return {}
        except Exception as err:
            _LOGGER.error(
                "Unknown error occurred while polling Ultimaker printer at %s using url %s: %s",
                self._host,
                url,
                err,
            )
            _LOGGER.critical("Unexpected exception in _fetch_data: %s - %s", type(err).__name__, str(err))
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
        _LOGGER.info("Initializing UltimakerCloudApiClient")
        super().__init__(session)

        # Mask token for logging (show only first 10 chars)
        masked_token = token[:10] + "..." if token and len(token) > 10 else "[empty token]"
        _LOGGER.debug("Using token: %s", masked_token)

        self._token = token
        self._token_expiry = token_expiry

        if token_expiry:
            time_until_expiry = token_expiry - datetime.now()
            _LOGGER.debug("Token expires in: %s", time_until_expiry)
        else:
            _LOGGER.warning("No token expiry time provided")

        self._cluster_id = cluster_id
        if cluster_id:
            _LOGGER.info("Using cluster ID: %s", cluster_id)
        else:
            _LOGGER.debug("No cluster ID provided, will need to be set later")

        self._headers = {"Authorization": f"Bearer {self._token}"}
        self.oauth_session = None  # Will be set by __init__.py
        _LOGGER.debug("Authorization headers configured")
        _LOGGER.info("UltimakerCloudApiClient initialized successfully")

    @Throttle(timedelta(seconds=DEFAULT_SCAN_INTERVAL_CLOUD))
    async def async_update(self) -> None:
        """Update data from the API."""
        _LOGGER.info("Starting update cycle for Ultimaker Cloud API")

        if not self._token or not self._cluster_id:
            _LOGGER.error("Missing token or cluster_id for Ultimaker Cloud API")
            if not self._token:
                _LOGGER.debug("Token is missing or empty")
            if not self._cluster_id:
                _LOGGER.debug("Cluster ID is missing or empty")
            self._data = {"status": "not configured"}
            _LOGGER.warning("Setting status to 'not configured' due to missing configuration")
            return

        # Check token expiry
        if self._token_expiry:
            time_until_expiry = self._token_expiry - datetime.now()
            _LOGGER.debug("Time until token expiry: %s", time_until_expiry)

            if self._token_expiry < datetime.now():
                _LOGGER.warning("Token expired for Ultimaker Cloud API, attempting refresh")
                refresh_result = await self._refresh_token()
                if not refresh_result:
                    _LOGGER.error("Token refresh failed, cannot continue with update")
                    raise UpdateFailed("Token expired and refresh failed")
                _LOGGER.info("Token refreshed successfully")
        else:
            _LOGGER.debug("No token expiry information available")

        try:
            # Get cluster status
            _LOGGER.debug("Requesting cluster status for cluster ID: %s", self._cluster_id)
            cluster_status = await self._api_request(
                "GET", f"/clusters/{self._cluster_id}/status"
            )
            _LOGGER.debug("Received cluster status: %s", cluster_status)

            # Get cluster details
            _LOGGER.debug("Requesting cluster details for cluster ID: %s", self._cluster_id)
            cluster_details = await self._api_request(
                "GET", f"/clusters/{self._cluster_id}"
            )
            _LOGGER.debug("Received cluster details: %s", cluster_details)

            # Combine data
            _LOGGER.debug("Combining cluster data into structured format")
            self._data = {
                "status": "connected",
                "cluster_status": cluster_status.get("status", "unknown"),
                "printer_count": len(cluster_status.get("printers", [])),
                "cluster_name": cluster_details.get("name", "Unknown Cluster"),
            }
            _LOGGER.info(
                "Cluster '%s' status: %s with %d printers", 
                self._data["cluster_name"], 
                self._data["cluster_status"], 
                self._data["printer_count"]
            )

            # Add printer data
            printers = cluster_status.get("printers", [])
            if printers:
                _LOGGER.debug("Found %d printers in cluster, using first printer for compatibility", len(printers))
                # Use the first printer for compatibility with local API
                printer = printers[0]
                printer_status = printer.get("status", "unknown")
                printer_state = printer.get("state", "unknown")
                printer_progress = printer.get("progress", 0)

                _LOGGER.info("Printer status: %s, state: %s, progress: %s", 
                            printer_status, printer_state, printer_progress)

                self._data.update({
                    "status": printer_status,
                    "state": printer_state,
                    "progress": printer_progress,
                })

                # Add bed data if available
                bed = printer.get("bed", {})
                if bed:
                    _LOGGER.debug("Adding bed data: %s", bed)
                    self._data["bed"] = bed
                    if "temperature" in bed:
                        temp = bed["temperature"]
                        _LOGGER.info("Bed temperature: current=%s, target=%s", 
                                    temp.get("current"), temp.get("target"))

                # Add head data if available
                heads = printer.get("heads", [])
                if heads:
                    _LOGGER.debug("Adding head data: %s", heads)
                    self._data["heads"] = heads
                    _LOGGER.info("Found %d print heads", len(heads))
            else:
                _LOGGER.warning("No printers found in cluster")

            _LOGGER.debug("Final structured data: %s", self._data)
            _LOGGER.info("Successfully updated data from Ultimaker Cloud API")

        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error fetching data from Ultimaker Cloud API: %s", err)
            _LOGGER.debug("ClientError details: %s", str(err))
            self._data = {"status": "not connected"}
            _LOGGER.warning("Setting status to 'not connected' due to connection error")
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout error fetching data from Ultimaker Cloud API")
            self._data = {"status": "timeout"}
            _LOGGER.warning("Setting status to 'timeout' due to timeout error")
        except Exception as err:
            _LOGGER.error("Unknown error fetching data from Ultimaker Cloud API: %s", err)
            _LOGGER.critical("Unexpected exception in async_update: %s - %s", type(err).__name__, str(err))
            self._data = {"status": "error"}
            _LOGGER.warning("Setting status to 'error' due to unknown error")

        # Add sample time to data
        current_time = datetime.now()
        self._data["sampleTime"] = current_time
        _LOGGER.debug("Added sample time to data: %s", current_time)
        _LOGGER.info("Update cycle completed for Ultimaker Cloud API")

    async def _api_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the API."""
        url = f"{CLOUD_API_URL}{endpoint}"
        _LOGGER.debug("Starting API request: %s %s", method, url)

        if params:
            _LOGGER.debug("Request params: %s", params)
        if data:
            _LOGGER.debug("Request data: %s", data)

        start_time = datetime.now()

        try:
            with async_timeout.timeout(10):
                _LOGGER.debug("Making %s request to %s with timeout of 10 seconds", method, url)
                async with self._session.request(
                    method, url, json=data, params=params, headers=self._headers
                ) as response:
                    _LOGGER.debug("Received response with status code: %s", response.status)

                    if response.status >= 400:
                        error_text = await response.text()
                        _LOGGER.error(
                            "Error response from Ultimaker Cloud API: %s - %s",
                            response.status,
                            error_text,
                        )
                        _LOGGER.warning("Request to %s failed with status code %s", url, response.status)
                        return {}

                    _LOGGER.debug("Parsing JSON response")
                    response_data = await response.json()

                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    _LOGGER.debug("API request completed in %.3f seconds", duration)

                    if isinstance(response_data, dict):
                        _LOGGER.info("API request to %s successful (%d keys in response)", 
                                    endpoint, len(response_data))
                    else:
                        _LOGGER.info("API request to %s successful (non-dict response)", endpoint)

                    return response_data

        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error making request to Ultimaker Cloud API: %s", err)
            _LOGGER.debug("ClientError details: %s", str(err))
            raise
        except asyncio.TimeoutError:
            _LOGGER.error(
                "Timeout error making request to Ultimaker Cloud API: %s", url
            )
            _LOGGER.debug("Request timed out after 10 seconds")
            raise
        except Exception as err:
            _LOGGER.error(
                "Unknown error making request to Ultimaker Cloud API: %s - %s",
                url,
                err,
            )
            _LOGGER.critical("Unexpected exception in _api_request: %s - %s", type(err).__name__, str(err))
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
