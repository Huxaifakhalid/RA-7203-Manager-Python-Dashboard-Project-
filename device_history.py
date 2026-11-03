import json
import os
from datetime import datetime


HISTORY_FILE = "device_history.json"


def load_devices():
    """
    Load previously connected devices.

    Returns:
        list[dict]
    """

    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def save_devices(devices):
    """
    Save device history to disk.
    """

    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as file:
            json.dump(devices, file, indent=4)

    except Exception as e:
        print(f"[HISTORY] Save error: {e}")


def add_or_update_device(ip, device_type="Receiver", connected=True):
    """
    Add a new IP or update an existing IP.
    """

    devices = load_devices()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    existing = None

    for device in devices:
        if device.get("ip") == ip:
            existing = device
            break

    if existing is None:

        devices.append({
            "device": device_type,
            "ip": ip,
            "status": "Connected" if connected else "Offline",
            "last_connected": now
        })

    else:

        existing["device"] = device_type
        existing["status"] = "Connected" if connected else "Offline"

        if connected:
            existing["last_connected"] = now

    save_devices(devices)

    return devices


def set_device_status(ip, connected):
    """
    Update only the connection status.
    """

    devices = load_devices()

    for device in devices:

        if device.get("ip") == ip:

            device["status"] = (
                "Connected" if connected else "Offline"
            )

            if connected:
                device["last_connected"] = (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )

            break

    save_devices(devices)

    return devices