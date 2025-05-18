"""API client for Ultimaker printers."""
import asyncio
import logging
import re
import xml.etree.ElementTree as ET
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
        self._last_successful_data = None
        self._consecutive_errors = 0
        self._max_consecutive_errors = 3
        _LOGGER.debug("UltimakerApiClientBase initialized")

    @property
    def latest_data(self) -> Dict[str, Any]:
        """Return the latest data."""
        return self._data or {}

    async def async_update(self) -> Dict[str, Any]:
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
        self._url_materials = LOCAL_API_URL.format(host) + "/materials"
        self._material_names_cache = {}  # Cache for material names
        _LOGGER.debug("Local API URLs configured: printer=%s, print_job=%s, system=%s, materials=%s", 
                     self._url_printer, self._url_print_job, self._url_system, self._url_materials)
        _LOGGER.info("UltimakerLocalApiClient initialized successfully")

    async def get_material_name(self, material_guid: str) -> str:
        """Get the human-readable name of a material from its GUID.

        Args:
            material_guid: The GUID of the material to look up

        Returns:
            The human-readable name of the material, or the GUID if the name cannot be determined
        """
        if not material_guid or material_guid == "unknown":
            _LOGGER.debug("No material GUID provided, returning 'unknown'")
            return "unknown"

        # Check if we already have this material name in the cache
        if material_guid in self._material_names_cache:
            _LOGGER.debug("Found material name in cache for GUID %s: %s", 
                         material_guid, self._material_names_cache[material_guid])
            return self._material_names_cache[material_guid]

        try:
            # Fetch the material XML from the API
            material_url = f"{self._url_materials}/{material_guid}"
            _LOGGER.debug("Fetching material data from %s", material_url)

            material_xml = await self._fetch_data(material_url)
            if not material_xml or not isinstance(material_xml, str):
                _LOGGER.debug("Failed to fetch material data for GUID %s", material_guid)
                return material_guid

            # Parse the XML to extract the material name
            try:
                # Try to parse as XML
                root = ET.fromstring(material_xml)

                # Look for the display name in the XML
                # The structure is typically <fdmmaterial><metadata><name>Material Name</name></metadata></fdmmaterial>
                name_elem = root.find(".//name")
                if name_elem is not None and name_elem.text:
                    material_name = name_elem.text.strip()
                    _LOGGER.debug("Found material name in XML for GUID %s: %s", material_guid, material_name)

                    # Cache the result for future use
                    self._material_names_cache[material_guid] = material_name
                    return material_name

                # If we couldn't find the name element, try to find brand and material
                brand_elem = root.find(".//metadata/properties/brand")
                material_elem = root.find(".//metadata/properties/material")

                if brand_elem is not None and brand_elem.text and material_elem is not None and material_elem.text:
                    brand = brand_elem.text.strip()
                    material = material_elem.text.strip()
                    material_name = f"{brand} {material}"
                    _LOGGER.debug("Constructed material name from brand and material for GUID %s: %s", 
                                 material_guid, material_name)

                    # Cache the result for future use
                    self._material_names_cache[material_guid] = material_name
                    return material_name

            except ET.ParseError:
                _LOGGER.debug("Failed to parse material XML for GUID %s", material_guid)

                # Try to extract the name using regex as a fallback
                match = re.search(r"<name>(.*?)</name>", material_xml)
                if match:
                    material_name = match.group(1).strip()
                    _LOGGER.debug("Extracted material name using regex for GUID %s: %s", 
                                 material_guid, material_name)

                    # Cache the result for future use
                    self._material_names_cache[material_guid] = material_name
                    return material_name

            # If all else fails, return the GUID
            _LOGGER.debug("Could not extract material name from XML for GUID %s", material_guid)
            return material_guid

        except Exception as err:
            _LOGGER.error("Error getting material name for GUID %s: %s", material_guid, err)
            return material_guid

    @Throttle(timedelta(seconds=DEFAULT_SCAN_INTERVAL_LOCAL))
    async def async_update(self) -> Dict[str, Any]:
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
                _LOGGER.debug("Failed to fetch printer data from %s (printer may be offline)", self._url_printer)
                self._consecutive_errors += 1
                _LOGGER.debug("Consecutive errors: %d/%d", self._consecutive_errors, self._max_consecutive_errors)

                # If we have previous successful data and haven't exceeded max consecutive errors,
                # use the cached data instead of failing
                if self._last_successful_data and self._consecutive_errors < self._max_consecutive_errors:
                    _LOGGER.debug("Using cached data from previous successful update")
                    self._data = self._last_successful_data.copy()
                    # Add a status indicator that we're using cached data
                    self._data["using_cached_data"] = True
                    return self._data
                else:
                    # If we've exceeded max consecutive errors or have no cached data, mark as not connected
                    _LOGGER.debug("Max consecutive errors exceeded or no cached data available")
                    self._data = {"status": "not connected"}
                    raise UpdateFailed("Failed to fetch printer data")

            _LOGGER.debug("Received printer data: %s", printer_data)

            # Use the printer data directly
            self._data = printer_data
            _LOGGER.debug("Stored printer data in self._data")

            # Fetch print job data first - we'll use it for both status verification and data enrichment
            _LOGGER.debug("Fetching print job data from %s", self._url_print_job)
            print_job_data = None
            try:
                print_job_data = await self._fetch_data(self._url_print_job)
                if print_job_data:
                    _LOGGER.debug("Received print job data: %s", print_job_data)
                else:
                    _LOGGER.debug("No print job data received (printer may be idle)")
            except Exception as err:
                _LOGGER.warning("Error fetching print job data (this is normal if no print job is active): %s", err)

            # Ensure status is always present
            if "status" not in self._data:
                _LOGGER.debug("Status field not found in printer data, defaulting to 'idle'")
                self._data["status"] = "idle"
            else:
                raw_status = self._data["status"]
                _LOGGER.debug("Raw printer status from API: %s", raw_status)

                # Verify the status is accurate by cross-checking with print job data
                if print_job_data:
                    job_state = print_job_data.get("state", "").lower()
                    job_progress = print_job_data.get("progress", 0)

                    # If printer says "printing" but job is complete or near complete, fix the status
                    if raw_status == "printing" and job_state in ["finished", "done", "complete", "success", "wait_cleanup"]:
                        _LOGGER.info("Printer reports 'printing' but job state is '%s', correcting status to 'idle'", job_state)
                        self._data["status"] = "idle"
                    elif raw_status == "printing" and job_progress >= 0.999:  # 99.9% or more
                        _LOGGER.info("Printer reports 'printing' but job progress is %.1f%%, correcting status to 'idle'", job_progress * 100)
                        self._data["status"] = "idle"
                    else:
                        _LOGGER.info("Printer status: %s (verified with job state: %s, progress: %.1f%%)", 
                                    raw_status, job_state, job_progress * 100)
                else:
                    # No print job data but printer says "printing" - this is inconsistent
                    if raw_status == "printing":
                        _LOGGER.warning("Printer reports 'printing' but no print job data found, correcting status to 'idle'")
                        self._data["status"] = "idle"
                    else:
                        _LOGGER.info("Printer status: %s (no active print job)", raw_status)

            # Now add the print job data to our data structure
            if print_job_data:
                _LOGGER.debug("Merging print job data into self._data")
                for key, value in print_job_data.items():
                    _LOGGER.debug("Adding print job field: %s = %s", key, value)
                    self._data[key] = value
            else:
                # Ensure essential print job fields are present even if no job is active
                _LOGGER.debug("Setting default print job fields")
                self._data.setdefault("state", "idle")
                self._data.setdefault("progress", 0)
                self._data.setdefault("time_total", 0)
                self._data.setdefault("time_elapsed", 0)

            # Log the final data structure for debugging
            _LOGGER.debug("Final data structure before returning: %s", self._data)

            # Log key fields for easier debugging
            _LOGGER.info("Final printer status: %s", self._data.get("status", "unknown"))
            if "state" in self._data:
                _LOGGER.info("Final print job state: %s", self._data.get("state", "unknown"))
            if "progress" in self._data:
                _LOGGER.info("Final print job progress: %.1f%%", self._data.get("progress", 0) * 100)

            # Ensure all required fields are present for sensors
            # This is critical for sensor availability
            _LOGGER.debug("Ensuring all required fields are present for sensors")

            # Ensure bed data is properly structured
            if "bed" not in self._data:
                _LOGGER.debug("Adding empty bed data structure")
                self._data["bed"] = {}

            if "temperature" not in self._data["bed"]:
                _LOGGER.debug("Adding empty bed temperature data structure")
                self._data["bed"]["temperature"] = {}

            if "current" not in self._data["bed"]["temperature"]:
                _LOGGER.debug("Adding default bed current temperature: 0")
                self._data["bed"]["temperature"]["current"] = 0

            if "target" not in self._data["bed"]["temperature"]:
                _LOGGER.debug("Adding default bed target temperature: 0")
                self._data["bed"]["temperature"]["target"] = 0

            if "type" not in self._data["bed"]:
                _LOGGER.debug("Adding default bed type: unknown")
                self._data["bed"]["type"] = "unknown"

            # Ensure heads data is properly structured
            if "heads" not in self._data or not self._data["heads"]:
                _LOGGER.debug("Adding empty heads data structure")
                self._data["heads"] = [{}]

            # Ensure first head has required fields
            head = self._data["heads"][0]

            if "extruders" not in head or not head["extruders"]:
                _LOGGER.debug("Adding empty extruders data structure to first head")
                head["extruders"] = [{}]

            # Ensure first extruder has required fields
            extruder = head["extruders"][0]

            if "hotend" not in extruder:
                _LOGGER.debug("Adding empty hotend data structure to first extruder")
                extruder["hotend"] = {}

            hotend = extruder["hotend"]

            if "temperature" not in hotend:
                _LOGGER.debug("Adding empty temperature data structure to first hotend")
                hotend["temperature"] = {}

            if "current" not in hotend["temperature"]:
                _LOGGER.debug("Adding default hotend current temperature: 0")
                hotend["temperature"]["current"] = 0

            if "target" not in hotend["temperature"]:
                _LOGGER.debug("Adding default hotend target temperature: 0")
                hotend["temperature"]["target"] = 0

            if "id" not in hotend:
                _LOGGER.debug("Adding default hotend ID: unknown")
                hotend["id"] = "unknown"

            if "statistics" not in hotend:
                _LOGGER.debug("Adding empty statistics data structure to first hotend")
                hotend["statistics"] = {}

            if "material_extruded" not in hotend["statistics"]:
                _LOGGER.debug("Adding default material extruded: 0")
                hotend["statistics"]["material_extruded"] = 0

            if "active_material" not in extruder:
                _LOGGER.debug("Adding empty active_material data structure to first extruder")
                extruder["active_material"] = {}

            if "length_remaining" not in extruder["active_material"]:
                _LOGGER.debug("Adding default material length remaining: 0")
                extruder["active_material"]["length_remaining"] = 0

            if "GUID" not in extruder["active_material"]:
                _LOGGER.debug("Adding default material GUID: unknown")
                extruder["active_material"]["GUID"] = "unknown"

            # If there's a second extruder, ensure it has the required fields
            if len(head["extruders"]) > 1:
                _LOGGER.debug("Second extruder found, ensuring it has required fields")
                extruder2 = head["extruders"][1]

                if "hotend" not in extruder2:
                    _LOGGER.debug("Adding empty hotend data structure to second extruder")
                    extruder2["hotend"] = {}

                hotend2 = extruder2["hotend"]

                if "temperature" not in hotend2:
                    _LOGGER.debug("Adding empty temperature data structure to second hotend")
                    hotend2["temperature"] = {}

                if "current" not in hotend2["temperature"]:
                    _LOGGER.debug("Adding default second hotend current temperature: 0")
                    hotend2["temperature"]["current"] = 0

                if "target" not in hotend2["temperature"]:
                    _LOGGER.debug("Adding default second hotend target temperature: 0")
                    hotend2["temperature"]["target"] = 0

                if "id" not in hotend2:
                    _LOGGER.debug("Adding default second hotend ID: unknown")
                    hotend2["id"] = "unknown"

                if "statistics" not in hotend2:
                    _LOGGER.debug("Adding empty statistics data structure to second hotend")
                    hotend2["statistics"] = {}

                if "material_extruded" not in hotend2["statistics"]:
                    _LOGGER.debug("Adding default material extruded for second hotend: 0")
                    hotend2["statistics"]["material_extruded"] = 0

                if "active_material" not in extruder2:
                    _LOGGER.debug("Adding empty active_material data structure to second extruder")
                    extruder2["active_material"] = {}

                if "length_remaining" not in extruder2["active_material"]:
                    _LOGGER.debug("Adding default material length remaining for second extruder: 0")
                    extruder2["active_material"]["length_remaining"] = 0

                if "GUID" not in extruder2["active_material"]:
                    _LOGGER.debug("Adding default material GUID for second extruder: unknown")
                    extruder2["active_material"]["GUID"] = "unknown"

            _LOGGER.info("Data structure prepared for sensors, all required fields are present")

            # Fetch material names for active materials
            _LOGGER.debug("Fetching material names for active materials")
            try:
                heads = self._data.get("heads", [])
                if heads and len(heads) > 0:
                    head = heads[0]
                    extruders = head.get("extruders", [])

                    # Process first extruder if present
                    if extruders and len(extruders) > 0:
                        extruder = extruders[0]
                        active_material = extruder.get("active_material", {})
                        # Try both uppercase and lowercase GUID keys
                        material_guid = active_material.get("GUID", active_material.get("guid", "unknown"))

                        if material_guid and material_guid != "unknown":
                            _LOGGER.debug("Fetching material name for hotend 1 material GUID: %s", material_guid)
                            material_name = await self.get_material_name(material_guid)
                            _LOGGER.debug("Got material name for hotend 1: %s", material_name)

                            # Add the material name to the data
                            active_material["material_name"] = material_name

                    # Process second extruder if present
                    if extruders and len(extruders) > 1:
                        extruder2 = extruders[1]
                        active_material2 = extruder2.get("active_material", {})
                        # Try both uppercase and lowercase GUID keys
                        material_guid2 = active_material2.get("GUID", active_material2.get("guid", "unknown"))

                        if material_guid2 and material_guid2 != "unknown":
                            _LOGGER.debug("Fetching material name for hotend 2 material GUID: %s", material_guid2)
                            material_name2 = await self.get_material_name(material_guid2)
                            _LOGGER.debug("Got material name for hotend 2: %s", material_name2)

                            # Add the material name to the data
                            active_material2["material_name"] = material_name2
            except Exception as err:
                _LOGGER.error("Error fetching material names: %s", err)
                # Continue with the update even if material name fetching fails

            # Log the structured data for debugging
            _LOGGER.debug("Final structured data: %s", self._data)

            _LOGGER.info("Successfully updated data from Ultimaker printer at %s", self._host)
        except aiohttp.ClientError as err:
            _LOGGER.debug("Connection error fetching data from Ultimaker printer at %s: %s (printer may be offline)", self._host, err)
            self._consecutive_errors += 1
            _LOGGER.debug("Consecutive errors: %d/%d", self._consecutive_errors, self._max_consecutive_errors)

            # If we have previous successful data and haven't exceeded max consecutive errors,
            # use the cached data instead of failing
            if self._last_successful_data and self._consecutive_errors < self._max_consecutive_errors:
                _LOGGER.debug("Using cached data due to connection error")
                self._data = self._last_successful_data.copy()
                # Add a status indicator that we're using cached data
                self._data["using_cached_data"] = True

                # Add sample time to data
                current_time = datetime.now()
                self._data["sampleTime"] = current_time
                _LOGGER.debug("Added sample time to cached data: %s", current_time)
                _LOGGER.debug("Update cycle completed with cached data for Ultimaker printer at %s", self._host)

                return self._data
            else:
                self._data = {"status": "not connected"}
                _LOGGER.debug("Setting status to 'not connected' due to connection error")
                raise UpdateFailed(f"Connection error: {err}")
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout error fetching data from Ultimaker printer at %s (printer may be offline)", self._host)
            self._consecutive_errors += 1
            _LOGGER.debug("Consecutive errors: %d/%d", self._consecutive_errors, self._max_consecutive_errors)

            # If we have previous successful data and haven't exceeded max consecutive errors,
            # use the cached data instead of failing
            if self._last_successful_data and self._consecutive_errors < self._max_consecutive_errors:
                _LOGGER.debug("Using cached data due to timeout error")
                self._data = self._last_successful_data.copy()
                # Add a status indicator that we're using cached data
                self._data["using_cached_data"] = True

                # Add sample time to data
                current_time = datetime.now()
                self._data["sampleTime"] = current_time
                _LOGGER.debug("Added sample time to cached data: %s", current_time)
                _LOGGER.debug("Update cycle completed with cached data for Ultimaker printer at %s", self._host)

                return self._data
            else:
                self._data = {"status": "timeout"}
                _LOGGER.debug("Setting status to 'timeout' due to timeout error")
                raise UpdateFailed("Connection timed out")
        except Exception as err:
            # For unknown errors, we'll keep error level for the main message to help with troubleshooting
            # but reduce the level of the follow-up messages
            _LOGGER.error("Unknown error fetching data from Ultimaker printer at %s: %s", self._host, err)
            self._consecutive_errors += 1
            _LOGGER.debug("Consecutive errors: %d/%d", self._consecutive_errors, self._max_consecutive_errors)

            # If we have previous successful data and haven't exceeded max consecutive errors,
            # use the cached data instead of failing
            if self._last_successful_data and self._consecutive_errors < self._max_consecutive_errors:
                _LOGGER.debug("Using cached data due to unknown error")
                self._data = self._last_successful_data.copy()
                # Add a status indicator that we're using cached data
                self._data["using_cached_data"] = True

                # Add sample time to data
                current_time = datetime.now()
                self._data["sampleTime"] = current_time
                _LOGGER.debug("Added sample time to cached data: %s", current_time)
                _LOGGER.debug("Update cycle completed with cached data for Ultimaker printer at %s", self._host)

                return self._data
            else:
                self._data = {"status": "error"}
                _LOGGER.debug("Setting status to 'error' due to unknown error")
                raise UpdateFailed(f"Unknown error: {err}")

        # Add sample time to data
        current_time = datetime.now()
        self._data["sampleTime"] = current_time
        _LOGGER.debug("Added sample time to data: %s", current_time)

        # Store this successful data for future use if needed
        self._last_successful_data = self._data.copy()
        # Reset consecutive error counter on successful update
        if self._consecutive_errors > 0:
            _LOGGER.info("Resetting consecutive error counter after successful update")
            self._consecutive_errors = 0

        _LOGGER.info("Update cycle completed for Ultimaker printer at %s", self._host)

        # Return the data for the coordinator
        _LOGGER.debug("Returning data to coordinator: %s", self._data)
        return self._data

    async def _fetch_data(self, url: str) -> Union[Dict[str, Any], str]:
        """Fetch data from the API."""
        _LOGGER.debug("Starting _fetch_data for URL: %s", url)
        start_time = datetime.now()

        try:
            # Increased timeout from 5 to 10 seconds to allow more time for responses
            with async_timeout.timeout(10):
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
                    _LOGGER.debug("Request to %s failed with status code %s", url, response.status)
                    return {}

                # Check if the response is expected to be JSON or text
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' in content_type or url.endswith('/printer') or url.endswith('/print_job'):
                    _LOGGER.debug("Parsing JSON response from %s", url)
                    data = await response.json()
                    _LOGGER.debug("Received data from %s: %s", url, data)
                else:
                    _LOGGER.debug("Parsing text response from %s", url)
                    data = await response.text()
                    _LOGGER.debug("Received text data from %s (length: %d)", url, len(data) if data else 0)

                # Check if data is empty or None
                if not data:
                    _LOGGER.debug(
                        "Empty data received from Ultimaker printer at %s using url %s (printer may be offline)",
                        self._host,
                        url,
                    )
                else:
                    if isinstance(data, dict):
                        _LOGGER.info("Successfully fetched data from %s (%s keys in response)", url, len(data))
                    else:
                        _LOGGER.info("Successfully fetched data from %s (non-dict response)", url)

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                _LOGGER.debug("_fetch_data completed for %s in %.3f seconds", url, duration)

                return data

        except aiohttp.ClientError as err:
            _LOGGER.debug("Printer %s is offline or unreachable: %s", self._host, err)
            _LOGGER.debug("ClientError details: %s", str(err))
            raise
        except asyncio.TimeoutError:
            _LOGGER.debug(
                "Timeout error occurred while polling Ultimaker printer at %s using url %s (printer may be offline)",
                self._host,
                url,
            )
            _LOGGER.debug("Request timed out after 10 seconds")
            raise
        except ValueError as err:
            _LOGGER.debug(
                "Invalid JSON response from Ultimaker printer at %s using url %s: %s",
                self._host,
                url,
                err,
            )
            _LOGGER.debug("JSON parsing error details: %s", str(err))
            return {}
        except Exception as err:
            # Keep error level for unknown exceptions to help with troubleshooting
            _LOGGER.error(
                "Unknown error occurred while polling Ultimaker printer at %s using url %s: %s",
                self._host,
                url,
                err,
            )
            _LOGGER.debug("Unexpected exception in _fetch_data: %s - %s", type(err).__name__, str(err))
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
    async def async_update(self) -> Dict[str, Any]:
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
            _LOGGER.debug("Setting status to 'not connected' due to connection error")
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout error fetching data from Ultimaker Cloud API (service may be offline)")
            self._data = {"status": "timeout"}
            _LOGGER.debug("Setting status to 'timeout' due to timeout error")
        except Exception as err:
            # Keep error level for unknown errors to help with troubleshooting
            _LOGGER.error("Unknown error fetching data from Ultimaker Cloud API: %s", err)
            _LOGGER.debug("Unexpected exception in async_update: %s - %s", type(err).__name__, str(err))
            self._data = {"status": "error"}
            _LOGGER.debug("Setting status to 'error' due to unknown error")

        # Add sample time to data
        current_time = datetime.now()
        self._data["sampleTime"] = current_time
        _LOGGER.debug("Added sample time to data: %s", current_time)
        _LOGGER.info("Update cycle completed for Ultimaker Cloud API")

        # Return the data for the coordinator
        _LOGGER.debug("Returning data to coordinator: %s", self._data)
        return self._data

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
                        _LOGGER.debug("Request to %s failed with status code %s", url, response.status)
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
