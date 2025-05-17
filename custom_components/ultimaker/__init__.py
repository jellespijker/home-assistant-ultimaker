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

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ultimaker component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ultimaker from a config entry."""
    if entry.data.get(CONF_API_TYPE) == API_TYPE_CLOUD:
        # Set up OAuth2 session
        implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )

        # If we have an organization_id in the config entry, update the implementation
        if CONF_ORGANIZATION_ID in entry.data:
            organization_id = entry.data[CONF_ORGANIZATION_ID]
            if hasattr(implementation, "update_organization_id"):
                implementation.update_organization_id(organization_id)
                _LOGGER.debug("Using organization ID: %s", organization_id)

        oauth_session = config_entry_oauth2_flow.OAuth2Session(
            hass, entry, implementation
        )

        # Get token
        try:
            await oauth_session.async_ensure_token_valid()
        except config_entry_oauth2_flow.OAuth2SessionException as err:
            _LOGGER.error("Error refreshing token: %s", err)
            return False

        # Get token info
        token = oauth_session.token
        token_expiry = datetime.now() + timedelta(seconds=token.get("expires_in", 3600))

        # Create API client
        session = async_get_clientsession(hass)
        api_client = UltimakerCloudApiClient(
            session=session,
            token=token["access_token"],
            token_expiry=token_expiry,
            cluster_id=entry.data.get(CONF_CLUSTER_ID),
        )

        # Store OAuth session for token refresh
        api_client.oauth_session = oauth_session

        # If no cluster ID is set, get the first available cluster
        if not entry.data.get(CONF_CLUSTER_ID):
            try:
                clusters = await api_client.get_clusters()
                if clusters and len(clusters) > 0:
                    cluster_id = clusters[0].get("id")
                    api_client.select_cluster(cluster_id)

                    # Update config entry with cluster ID
                    new_data = {**entry.data, CONF_CLUSTER_ID: cluster_id}
                    hass.config_entries.async_update_entry(entry, data=new_data)
            except Exception as err:
                _LOGGER.error("Error getting clusters: %s", err)
                return False

        # Set up coordinator
        scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL_CLOUD)
        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"Ultimaker Cloud ({entry.data.get(CONF_CLUSTER_ID, 'Unknown')})",
            update_method=api_client.async_update,
            update_interval=timedelta(seconds=scan_interval),
        )
    else:
        # Set up local API client
        session = async_get_clientsession(hass)
        api_client = UltimakerLocalApiClient(
            session=session,
            host=entry.data[CONF_HOST],
        )

        # Set up coordinator
        scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL_LOCAL)
        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"Ultimaker ({entry.data[CONF_HOST]})",
            update_method=api_client.async_update,
            update_interval=timedelta(seconds=scan_interval),
        )

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Store API client and coordinator in hass.data
    hass.data[DOMAIN][entry.entry_id] = {
        "api_client": api_client,
        "coordinator": coordinator,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
