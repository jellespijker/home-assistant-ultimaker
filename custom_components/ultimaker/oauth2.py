"""OAuth2 implementation for Ultimaker."""
import logging
from typing import Any, Callable, Dict, Optional, cast

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_get_clientsession,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN, CONF_ORGANIZATION_ID

_LOGGER = logging.getLogger(__name__)


class UltimakerOAuth2Implementation(
    config_entry_oauth2_flow.LocalOAuth2Implementation
):
    """Ultimaker OAuth2 implementation."""

    def __init__(
        self,
        hass: HomeAssistant,
        client_id: str,
        client_secret: str,
        organization_id: Optional[str] = None,
    ) -> None:
        """Initialize the Ultimaker OAuth2 implementation."""
        super().__init__(
            hass=hass,
            domain="ultimaker",
            client_id=client_id,
            client_secret=client_secret,
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        )
        self._organization_id = organization_id

    @property
    def extra_authorize_data(self) -> Dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        data = {
            "scope": "openid",
        }

        # Add organization_id if available
        if self._organization_id:
            data[CONF_ORGANIZATION_ID] = self._organization_id

        return data

    def update_organization_id(self, organization_id: str) -> None:
        """Update the organization ID for workspace switching."""
        self._organization_id = organization_id


async def async_setup_oauth2(
    hass: HomeAssistant,
    client_credential: ClientCredential,
    organization_id: Optional[str] = None,
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Set up OAuth2 for Ultimaker."""
    return UltimakerOAuth2Implementation(
        hass=hass,
        client_id=client_credential.client_id,
        client_secret=client_credential.client_secret,
        organization_id=organization_id,
    )


async def async_get_config_entry_implementation(
    hass: HomeAssistant, config_entry: Dict[str, Any]
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return the implementation for the config entry."""
    client_id = config_entry["client_id"]
    client_secret = config_entry["client_secret"]
    organization_id = config_entry.get(CONF_ORGANIZATION_ID)
    return UltimakerOAuth2Implementation(
        hass=hass,
        client_id=client_id,
        client_secret=client_secret,
        organization_id=organization_id,
    )
