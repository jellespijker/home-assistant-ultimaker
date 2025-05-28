import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from .const import DOMAIN

class UltimakerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ultimaker."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step of the config flow."""
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_HOST): str,
            }),
        )