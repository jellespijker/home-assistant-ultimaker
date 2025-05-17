"""Application credentials platform for Ultimaker."""
from typing import Optional
from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant

from .const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN, CONF_ORGANIZATION_ID
from .oauth2 import UltimakerOAuth2Implementation


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential, 
    organization_id: Optional[str] = None
) -> AuthImplementation:
    """Return auth implementation for Ultimaker."""
    return UltimakerOAuth2Implementation(
        hass=hass,
        client_id=credential.client_id,
        client_secret=credential.client_secret,
        organization_id=organization_id,
    )


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server for Ultimaker."""
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )
