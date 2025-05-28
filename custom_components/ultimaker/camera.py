import logging
import subprocess
import re
import aiohttp
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, COORDINATOR

_LOGGER = logging.getLogger(__name__)


def get_mac_from_ip(ip):
    """Retrieve MAC address for a given IP using ARP table."""
    try:
        subprocess.run(["ping", "-c", "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = subprocess.run(["arp", "-n", ip], capture_output=True, text=True)
        match = re.search(r"(([a-fA-F0-9]{2}[:-]){5}[a-fA-F0-9]{2})", result.stdout)
        return match.group(0).lower() if match else None
    except Exception as e:
        _LOGGER.warning(f"Error getting MAC address for {ip}: {e}")
        return None


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Set up the Ultimaker camera platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    name = config_entry.data.get("name", "Ultimaker")
    async_add_entities([
        UltimakerCamera(name=f"{name} Camera", coordinator=coordinator, config_entry=config_entry)
    ], True)


class UltimakerCamera(Camera):
    def __init__(self, name, coordinator, config_entry):
        super().__init__()
        self._attr_name = name
        self._coordinator = coordinator
        self._attr_unique_id = f"{config_entry.entry_id}_camera"
        self._attr_is_streaming = True
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._attr_entity_picture = self._coordinator.data.get("camera_snapshot_url")

        ip = config_entry.data["host"]
        mac_address = get_mac_from_ip(ip)

        sys_data = self._coordinator.data.get("system", {})

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            connections={("mac", mac_address)} if mac_address else set(),
            name=config_entry.data.get("name", "Ultimaker"),
            manufacturer="Ultimaker",
            model=sys_data.get("variant", "Unknown"),
            sw_version=sys_data.get("firmware", "Unknown"),
            hw_version=str(sys_data.get("hardware", {}).get("revision", "Unknown")),
            serial_number=sys_data.get("guid", None),
        )

    async def stream_source(self):
        """Return the stream source URL (MUST be async method)."""
        return self._coordinator.data.get("camera_stream_url")

    async def async_camera_image(self, width=None, height=None):
        """Return a still image response from the camera."""
        url = self._coordinator.data.get("camera_snapshot_url")
        if not url:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        _LOGGER.warning(f"Snapshot HTTP status: {response.status}")
                        return None
        except Exception as e:
            _LOGGER.error(f"Error fetching snapshot: {e}")
            return None