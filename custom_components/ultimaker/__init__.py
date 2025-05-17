"""Ultimaker printer integration"""
from homeassistant.core import HomeAssistant
import homeassistant.helpers.discovery

DOMAIN = "ultimaker"


def setup(hass: HomeAssistant, config):
    """Set up the Ultimaker integration."""
    # Data that you want to share with your platforms
    hass.data[DOMAIN] = {}

    # The sensor platform will be loaded by Home Assistant when explicitly configured
    return True
