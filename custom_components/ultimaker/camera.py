from .const import DOMAIN, COORDINATOR
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import logging
import aiohttp



_LOGGER = logging.getLogger(__name__)


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

        ip = config_entry.data["ip"]
        mac = coordinator.data.get("mac")

        sys_data = self._coordinator.data.get("system", {})

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
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