"""Ultimaker printer integration"""
DOMAIN = "ultimaker"


def setup(hass, config):
    """Your controller/hub specific code."""
    # Data that you want to share with your platforms
    hass.data[DOMAIN] = {"x": 0}

    hass.helpers.discovery.load_platform("sensor", DOMAIN, {}, config)

    return True
