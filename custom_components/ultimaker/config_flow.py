"""Config flow for Ultimaker integration."""
import logging
import voluptuous as vol
from typing import Any, Dict, List, Optional

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN
from .const import (
    CONF_API_TYPE, 
    API_TYPE_LOCAL, 
    API_TYPE_CLOUD, 
    CONF_HOST, 
    CONF_CLUSTER_ID,
    CONF_ORGANIZATION_ID
)
from .api_client import UltimakerCloudApiClient

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Initializing Ultimaker config flow")

class UltimakerOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle Ultimaker OAuth2 authentication."""

    DOMAIN = DOMAIN
    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        _LOGGER.debug("Initializing UltimakerOAuth2FlowHandler")
        super().__init__()
        self._workspaces = []
        self._organization_id = None
        _LOGGER.debug("UltimakerOAuth2FlowHandler initialized")

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        _LOGGER.info("User initiated Ultimaker config flow")

        if user_input is None:
            _LOGGER.debug("No user input, showing API type selection form")
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_API_TYPE, default=API_TYPE_LOCAL): vol.In(
                            [API_TYPE_LOCAL, API_TYPE_CLOUD]
                        ),
                    }
                ),
            )

        _LOGGER.debug("User selected API type: %s", user_input[CONF_API_TYPE])

        if user_input[CONF_API_TYPE] == API_TYPE_LOCAL:
            _LOGGER.info("User selected local API, proceeding to local setup")
            return await self.async_step_local()

        # For cloud API, we might need to select an organization
        _LOGGER.info("User selected cloud API, proceeding to OAuth setup")
        self._organization_id = user_input.get(CONF_ORGANIZATION_ID)
        if self._organization_id:
            _LOGGER.debug("Organization ID provided: %s", self._organization_id)
        else:
            _LOGGER.debug("No organization ID provided")

        return await self.async_step_oauth()

    async def async_step_local(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle local API configuration."""
        _LOGGER.debug("Starting local API configuration step")

        if user_input is None:
            _LOGGER.debug("No user input, showing host input form")
            return self.async_show_form(
                step_id="local",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                    }
                ),
            )

        host = user_input[CONF_HOST]
        _LOGGER.info("User provided host: %s", host)

        # Create the config entry
        title = f"Ultimaker Printer ({host})"
        data = {
            CONF_API_TYPE: API_TYPE_LOCAL,
            CONF_HOST: host,
        }

        _LOGGER.info("Creating config entry with title: %s", title)
        _LOGGER.debug("Config entry data: %s", data)

        return self.async_create_entry(
            title=title,
            data=data,
        )

    async def async_step_pick_organization(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the step to pick an organization."""
        _LOGGER.debug("Starting organization selection step")

        if not self._workspaces:
            _LOGGER.warning("No organizations found, aborting flow")
            return self.async_abort(reason="no_organizations")

        if user_input is None:
            workspace_names = {w["id"]: w["name"] for w in self._workspaces}
            _LOGGER.debug("Available organizations: %s", workspace_names)
            _LOGGER.info("Showing organization selection form with %d options", len(workspace_names))
            return self.async_show_form(
                step_id="pick_organization",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ORGANIZATION_ID): vol.In(workspace_names),
                    }
                ),
            )

        # Store the selected organization ID
        self._organization_id = user_input[CONF_ORGANIZATION_ID]
        _LOGGER.info("User selected organization ID: %s", self._organization_id)

        # Find the organization name for better logging
        org_name = next((w["name"] for w in self._workspaces if w["id"] == self._organization_id), "Unknown")
        _LOGGER.info("Selected organization name: %s", org_name)

        # Re-authenticate with the selected organization
        _LOGGER.debug("Proceeding to OAuth step with selected organization")
        return await self.async_step_oauth()

    async def async_oauth_create_entry(self, data: Dict[str, Any]) -> FlowResult:
        """Create an entry for OAuth2 authenticated config flow."""
        _LOGGER.info("Creating OAuth entry for Ultimaker Cloud")

        # If we have a token, try to get user info and check for multiple workspaces
        if "token" in data and not self._organization_id:
            _LOGGER.debug("Token received and no organization ID set, checking for workspaces")

            # Mask token for logging
            token = data["token"]
            masked_token = token["access_token"][:10] + "..." if token.get("access_token") else "[no token]"
            _LOGGER.debug("Using access token: %s", masked_token)

            session = async_get_clientsession(self.hass)
            _LOGGER.debug("Creating temporary API client to fetch workspaces")
            api_client = UltimakerCloudApiClient(
                session=session,
                token=data["token"]["access_token"],
                token_expiry=None,  # Not needed for this check
            )

            try:
                # Get workspaces
                _LOGGER.info("Fetching available workspaces (organizations)")
                self._workspaces = await api_client.get_workspaces()
                _LOGGER.info("Found %d workspaces", len(self._workspaces))

                # If multiple workspaces and no organization ID selected yet, show selection
                if len(self._workspaces) > 1:
                    _LOGGER.info("Multiple workspaces found, redirecting to organization selection")
                    return await self.async_step_pick_organization()
                elif len(self._workspaces) == 1:
                    # If only one workspace, use it
                    self._organization_id = self._workspaces[0]["id"]
                    org_name = self._workspaces[0].get("name", "Unknown")
                    _LOGGER.info("Single workspace found, using organization: %s (%s)", 
                                org_name, self._organization_id)
                else:
                    _LOGGER.warning("No workspaces found, continuing without organization ID")
            except Exception as err:
                _LOGGER.error("Error getting workspaces: %s", err)
                _LOGGER.warning("Continuing with flow even without workspace information")
                # Continue with flow even if we can't get workspaces

        # Add organization ID to data if available
        if self._organization_id:
            _LOGGER.debug("Adding organization ID to config data: %s", self._organization_id)
            data[CONF_ORGANIZATION_ID] = self._organization_id
        else:
            _LOGGER.debug("No organization ID to add to config data")

        # Get cluster ID if available
        cluster_id = data.get(CONF_CLUSTER_ID)
        title = "Ultimaker Cloud"

        if cluster_id:
            _LOGGER.debug("Using cluster ID in title: %s", cluster_id)
            title = f"{title} ({cluster_id})"
        elif self._organization_id:
            # Try to find the organization name
            _LOGGER.debug("Looking for organization name for title")
            for workspace in self._workspaces:
                if workspace["id"] == self._organization_id:
                    org_name = workspace['name']
                    _LOGGER.debug("Using organization name in title: %s", org_name)
                    title = f"{title} ({org_name})"
                    break

        # Prepare final data for config entry
        final_data = {
            CONF_API_TYPE: API_TYPE_CLOUD,
            **data,
        }

        _LOGGER.info("Creating config entry with title: %s", title)
        _LOGGER.debug("Config entry data: %s", {
            k: v if k != "token" else "***REDACTED***" 
            for k, v in final_data.items()
        })

        return self.async_create_entry(
            title=title,
            data=final_data,
        )

class ConfigFlow(UltimakerOAuth2FlowHandler):
    """Handle a config flow for Ultimaker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        _LOGGER.info("Starting Ultimaker config flow")

        if user_input is None:
            _LOGGER.debug("No user input, showing API type selection form")
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_API_TYPE, default=API_TYPE_LOCAL): vol.In(
                            [API_TYPE_LOCAL, API_TYPE_CLOUD]
                        ),
                    }
                ),
            )

        _LOGGER.debug("User provided input: %s", user_input)
        api_type = user_input[CONF_API_TYPE]

        if api_type == API_TYPE_LOCAL:
            _LOGGER.info("User selected local API, proceeding to local setup")
            return await self.async_step_local(user_input)
        else:
            # For cloud API, redirect to OAuth flow
            _LOGGER.info("User selected cloud API, proceeding to OAuth setup")
            return await self.async_step_oauth()

    async def async_step_local(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle local API configuration."""
        _LOGGER.debug("Starting local API configuration step")

        if user_input is None or CONF_HOST not in user_input:
            _LOGGER.debug("No user input, showing host input form")
            return self.async_show_form(
                step_id="local",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                    }
                ),
            )

        host = user_input[CONF_HOST]
        _LOGGER.info("User provided host: %s", host)

        # Create the config entry
        title = f"Ultimaker Printer ({host})"
        data = {
            CONF_API_TYPE: API_TYPE_LOCAL,
            CONF_HOST: host,
        }

        _LOGGER.info("Creating config entry with title: %s", title)
        _LOGGER.debug("Config entry data: %s", data)

        return self.async_create_entry(
            title=title,
            data=data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)

class OptionsFlow(config_entries.OptionsFlow):
    """Handle options for the Ultimaker integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        _LOGGER.debug("Initializing Ultimaker options flow for entry: %s", config_entry.entry_id)
        self.config_entry = config_entry
        _LOGGER.debug("Options flow initialized with config entry: %s", config_entry.data)

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        _LOGGER.info("Starting options flow for entry: %s", self.config_entry.entry_id)

        if user_input is not None:
            _LOGGER.info("User provided options: %s", user_input)
            _LOGGER.debug("Saving options to config entry")
            return self.async_create_entry(title="", data=user_input)

        api_type = self.config_entry.data.get(CONF_API_TYPE, API_TYPE_LOCAL)
        _LOGGER.debug("API type from config entry: %s", api_type)

        if api_type == API_TYPE_LOCAL:
            _LOGGER.debug("Creating options schema for local API")
            scan_interval_default = self.config_entry.options.get("scan_interval", 10)
            decimal_default = self.config_entry.options.get("decimal", 2)
            _LOGGER.debug("Default values: scan_interval=%s, decimal=%s", 
                         scan_interval_default, decimal_default)

            options_schema = vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=scan_interval_default,
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                    vol.Optional(
                        "decimal",
                        default=decimal_default,
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
                }
            )
            _LOGGER.debug("Created options schema for local API")
        else:  # API_TYPE_CLOUD
            _LOGGER.debug("Creating options schema for cloud API")
            scan_interval_default = self.config_entry.options.get("scan_interval", 30)
            decimal_default = self.config_entry.options.get("decimal", 2)
            cluster_id_default = self.config_entry.options.get(CONF_CLUSTER_ID, "")
            _LOGGER.debug("Default values: scan_interval=%s, decimal=%s, cluster_id=%s", 
                         scan_interval_default, decimal_default, cluster_id_default)

            options_schema = vol.Schema(
                {
                    vol.Optional(
                        "scan_interval",
                        default=scan_interval_default,
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                    vol.Optional(
                        "decimal",
                        default=decimal_default,
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
                    vol.Optional(
                        CONF_CLUSTER_ID,
                        default=cluster_id_default,
                    ): str,
                }
            )
            _LOGGER.debug("Created options schema for cloud API")

        _LOGGER.info("Showing options form")
        return self.async_show_form(step_id="init", data_schema=options_schema)
