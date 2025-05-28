import logging
from datetime import timedelta
import aiohttp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

class UltimakerDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, ip):
        """Inicializa el coordinador."""
        self.ip = ip
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} Coordinator",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self):
        """Solicita los datos de la impresora Ultimaker."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://{self.ip}/api/v1/printer") as printer_resp:
                    printer = await printer_resp.json()
                async with session.get(f"http://{self.ip}/api/v1/print_job") as job_resp:
                    print_job = await job_resp.json()
                async with session.get(f"http://{self.ip}/api/v1/system") as system_resp:
                    system = await system_resp.json()
                async with session.get(f"http://{self.ip}/api/v1/ambient_temperature") as temp_resp:
                    ambient_temperature = await temp_resp.json()
                async with session.get(f"http://{self.ip}/api/v1/system/firmware/latest") as latest_fw_resp:
                    latest_firmware = await latest_fw_resp.text()
                camera_stream_url = f"http://{self.ip}/api/v1/camera/0/stream"
                camera_snapshot_url = f"http://{self.ip}/api/v1/camera/0/snapshot"

                return {
                    "printer": printer,
                    "print_job": print_job,
                    "system": system,
                    "ambient_temperature": ambient_temperature,
                    "latest_firmware": latest_firmware,
                    "camera_stream_url": camera_stream_url,
                    "camera_snapshot_url": camera_snapshot_url,
                }

        except Exception as err:
            raise UpdateFailed(f"Error comunicando con la API de Ultimaker: {err}")