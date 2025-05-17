"""Ultimaker printer integration."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_client import UltimakerLocalApiClient, UltimakerCloudApiClient
from .const import (
    CONF_API_TYPE,
    API_TYPE_LOCAL,
    API_TYPE_CLOUD,
    CONF_CLUSTER_ID,
    CONF_ORGANIZATION_ID,
    DEFAULT_SCAN_INTERVAL_LOCAL,
    DEFAULT_SCAN_INTERVAL_CLOUD,
    DOMAIN,
)
from .oauth2 import UltimakerOAuth2Implementation

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Initializing Ultimaker integration")

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ultimaker component."""
    _LOGGER.info("Setting up Ultimaker component")
    _LOGGER.debug("Initializing hass.data[%s] dictionary", DOMAIN)
    hass.data[DOMAIN] = {}
    _LOGGER.info("Ultimaker component setup completed successfully")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ultimaker from a config entry."""
    _LOGGER.info("Setting up Ultimaker config entry: %s", entry.entry_id)

    api_type = entry.data.get(CONF_API_TYPE)
    _LOGGER.info("API type: %s", api_type)

    if api_type == API_TYPE_CLOUD:
        _LOGGER.info("Setting up Ultimaker Cloud API")

        # Set up OAuth2 session
        _LOGGER.debug("Getting OAuth2 implementation")
        try:
            implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
            _LOGGER.debug("OAuth2 implementation retrieved successfully")
        except Exception as err:
            _LOGGER.critical("Failed to get OAuth2 implementation: %s", err)
            return False

        # If we have an organization_id in the config entry, update the implementation
        if CONF_ORGANIZATION_ID in entry.data:
            organization_id = entry.data[CONF_ORGANIZATION_ID]
            _LOGGER.info("Organization ID found in config: %s", organization_id)

            if hasattr(implementation, "update_organization_id"):
                implementation.update_organization_id(organization_id)
                _LOGGER.debug("Updated implementation with organization ID: %s", organization_id)
            else:
                _LOGGER.warning("Implementation does not support organization_id update")

        _LOGGER.debug("Creating OAuth2 session")
        oauth_session = config_entry_oauth2_flow.OAuth2Session(
            hass, entry, implementation
        )
        _LOGGER.debug("OAuth2 session created")

        # Get token
        _LOGGER.debug("Ensuring OAuth token is valid")
        try:
            await oauth_session.async_ensure_token_valid()
            _LOGGER.info("OAuth token validated successfully")
        except config_entry_oauth2_flow.OAuth2SessionException as err:
            _LOGGER.error("Error refreshing token: %s", err)
            _LOGGER.critical("OAuth token validation failed, cannot continue setup")
            return False

        # Get token info
        token = oauth_session.token
        # Mask token for logging
        masked_token = token["access_token"][:10] + "..." if token.get("access_token") else "[no token]"
        _LOGGER.debug("Retrieved token: %s", masked_token)

        token_expiry = datetime.now() + timedelta(seconds=token.get("expires_in", 3600))
        _LOGGER.debug("Token expires at: %s", token_expiry)

        # Create API client
        _LOGGER.debug("Creating Cloud API client")
        session = async_get_clientsession(hass)
        api_client = UltimakerCloudApiClient(
            session=session,
            token=token["access_token"],
            token_expiry=token_expiry,
            cluster_id=entry.data.get(CONF_CLUSTER_ID),
        )
        _LOGGER.debug("Cloud API client created")

        # Store OAuth session for token refresh
        api_client.oauth_session = oauth_session
        _LOGGER.debug("Stored OAuth session in API client for token refresh")

        # If no cluster ID is set, get the first available cluster
        cluster_id = entry.data.get(CONF_CLUSTER_ID)
        if not cluster_id:
            _LOGGER.info("No cluster ID configured, attempting to get first available cluster")
            try:
                _LOGGER.debug("Fetching available clusters")
                clusters = await api_client.get_clusters()
                _LOGGER.debug("Retrieved %d clusters", len(clusters) if clusters else 0)

                if clusters and len(clusters) > 0:
                    cluster_id = clusters[0].get("id")
                    _LOGGER.info("Selected cluster ID: %s", cluster_id)
                    api_client.select_cluster(cluster_id)
                    _LOGGER.debug("Updated API client with selected cluster")

                    # Update config entry with cluster ID
                    _LOGGER.debug("Updating config entry with cluster ID")
                    new_data = {**entry.data, CONF_CLUSTER_ID: cluster_id}
                    hass.config_entries.async_update_entry(entry, data=new_data)
                    _LOGGER.info("Config entry updated with cluster ID")
                else:
                    _LOGGER.warning("No clusters found, integration may not work correctly")
            except Exception as err:
                _LOGGER.error("Error getting clusters: %s", err)
                _LOGGER.critical("Failed to get clusters, cannot continue setup")
                return False

        # Set up coordinator
        scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL_CLOUD)
        _LOGGER.debug("Setting up data coordinator with scan interval: %s seconds", scan_interval)
        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"Ultimaker Cloud ({entry.data.get(CONF_CLUSTER_ID, 'Unknown')})",
            update_method=api_client.async_update,
            update_interval=timedelta(seconds=scan_interval),
        )
        _LOGGER.debug("Cloud API coordinator created")

    else:
        # Set up local API client
        _LOGGER.info("Setting up Ultimaker Local API")
        host = entry.data.get(CONF_HOST)
        if not host:
            _LOGGER.critical("No host configured for local API, cannot continue setup")
            return False

        _LOGGER.info("Using host: %s", host)
        _LOGGER.debug("Creating Local API client")
        session = async_get_clientsession(hass)
        api_client = UltimakerLocalApiClient(
            session=session,
            host=host,
        )
        _LOGGER.debug("Local API client created")

        # Set up coordinator
        scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL_LOCAL)
        _LOGGER.debug("Setting up data coordinator with scan interval: %s seconds", scan_interval)
        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"Ultimaker ({host})",
            update_method=api_client.async_update,
            update_interval=timedelta(seconds=scan_interval),
        )
        _LOGGER.debug("Local API coordinator created")

    # Initial data fetch
    _LOGGER.info("Performing initial data refresh")
    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("Initial data refresh completed successfully")
    except Exception as err:
        _LOGGER.error("Error during initial data refresh: %s", err)
        _LOGGER.warning("Integration will continue setup, but initial data may be missing")

    # Store API client and coordinator in hass.data
    _LOGGER.debug("Storing API client and coordinator in hass.data")
    hass.data[DOMAIN][entry.entry_id] = {
        "api_client": api_client,
        "coordinator": coordinator,
    }
    _LOGGER.debug("API client and coordinator stored successfully")

    # Set up platforms
    _LOGGER.info("Setting up platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("Platforms setup completed")

    _LOGGER.info("Ultimaker config entry setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Ultimaker config entry: %s", entry.entry_id)

    _LOGGER.debug("Unloading platforms for entry: %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        _LOGGER.debug("Platforms unloaded successfully, removing entry data from hass.data")
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Ultimaker config entry unloaded successfully: %s", entry.entry_id)
    else:
        _LOGGER.warning("Failed to unload all platforms for entry: %s", entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("Reloading Ultimaker config entry: %s", entry.entry_id)

    _LOGGER.debug("Unloading entry before reload")
    await async_unload_entry(hass, entry)

    _LOGGER.debug("Setting up entry again")
    await async_setup_entry(hass, entry)

    _LOGGER.info("Ultimaker config entry reloaded successfully: %s", entry.entry_id)
