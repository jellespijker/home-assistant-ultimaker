from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import logging
import aiohttp
from .utils import get_mac_from_ip
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class UltimakerDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, ip, scan_interval):
        """Inicializa el coordinador."""
        self.ip = ip
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_method=self._async_update_data,
            update_interval=scan_interval,
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
                    latest_firmware_raw = await latest_fw_resp.text()
                    latest_firmware = latest_firmware_raw.strip('"') 
                camera_stream_url = f"http://{self.ip}/api/v1/camera/0/stream"
                camera_snapshot_url = f"http://{self.ip}/api/v1/camera/0/snapshot"
                mac_address = get_mac_from_ip(self.ip)
                
                return {
                    "printer": printer,
                    "print_job": print_job,
                    "system": system,
                    "ambient_temperature": ambient_temperature,
                    "latest_firmware": latest_firmware,
                    "camera_stream_url": camera_stream_url,
                    "camera_snapshot_url": camera_snapshot_url,
                    "mac": mac_address,
                }

        except Exception as err:
            raise UpdateFailed(f"Error comunicando con la API de Ultimaker: {err}")