from getmac import get_mac_address

def get_mac_from_ip(ip: str) -> str | None:
    """Try to get the MAC address for the given IP address."""
    try:
        return get_mac_address(ip=ip)
    except Exception:
        return None