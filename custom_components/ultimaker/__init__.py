from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import load_platform

"""Ultimaker printer integration"""
DOMAIN = "ultimaker"


def setup(hass: HomeAssistant, config):
    """Your controller/hub specific code."""
    # Data that you want to share with your platforms
    hass.data[DOMAIN] = {"x": 0}

    load_platform(hass, "sensor", DOMAIN, {}, config)

    return True
