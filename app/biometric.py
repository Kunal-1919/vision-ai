import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATA_DIR

BIOMETRIC_DEVICES_FILE = DATA_DIR / "biometric_devices.json"


@dataclass
class BiometricDevice:
    id: str
    name: str
    serial_number: str
    ip_address: str
    device_type: str  # e.g., "Face+Fingerprint Terminal", "Optical Palm Reader", "RFID Gate Controller"
    vendor: str       # e.g., "ZKTeco", "Hikvision", "Suprema", "VisionAI Edge"
    location: str
    status: str       # "online", "standby", "offline"
    last_seen: str
    firmware_version: str = "v2.4.1-ent"

    def to_public_dict(self) -> dict:
        return asdict(self)


class BiometricManager:
    """Enterprise Biometric Hardware Integration & Device Sync Protocol Engine.
    
    Supports HTTP Push SDK, Wiegand-over-IP, and hardware event webhooks for physical 
    biometric terminals (ZKTeco, Hikvision, Suprema, Dahua) and edge AI cameras.
    """

    def __init__(self, devices_file: Path = BIOMETRIC_DEVICES_FILE):
        self.devices_file = devices_file
        self._ensure_devices()

    def _ensure_devices(self) -> None:
        if self.devices_file.exists():
            return

        default_devices = [
            {
                "id": "dev-zk-01",
                "name": "Main Entrance SpeedFace",
                "serial_number": "ZK-SF5L-89421",
                "ip_address": "192.168.1.105",
                "device_type": "Face + Fingerprint + RFID Terminal",
                "vendor": "ZKTeco",
                "location": "HQ Lobby Turnstile A",
                "status": "online",
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "firmware_version": "v4.1.8-push",
            },
            {
                "id": "dev-hik-02",
                "name": "R&D Lab Face Gate",
                "serial_number": "HK-DS-671M-1102",
                "ip_address": "192.168.1.112",
                "device_type": "AI Face Recognition Terminal",
                "vendor": "Hikvision",
                "location": "3rd Floor R&D Entrance",
                "status": "online",
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "firmware_version": "v3.2.0-ent",
            },
            {
                "id": "dev-sup-03",
                "name": "Server Room BioStation",
                "serial_number": "SUP-BS3-90211",
                "ip_address": "192.168.1.120",
                "device_type": "Multimodal Fingerprint & Palm Vein Reader",
                "vendor": "Suprema",
                "location": "Data Center Security Airlock",
                "status": "standby",
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "firmware_version": "v2.9.5-sec",
            },
        ]
        self._write(default_devices)

    def _read(self) -> list[dict]:
        with self.devices_file.open(encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, devices: list[dict]) -> None:
        self.devices_file.write_text(json.dumps(devices, indent=2), encoding="utf-8")

    def list_devices(self) -> list[dict]:
        return self._read()

    def register_device(
        self,
        name: str,
        serial_number: str,
        ip_address: str,
        device_type: str,
        vendor: str,
        location: str,
    ) -> dict:
        devices = self._read()
        device_id = f"dev-{uuid.uuid4().hex[:6]}"
        device = BiometricDevice(
            id=device_id,
            name=name,
            serial_number=serial_number,
            ip_address=ip_address,
            device_type=device_type,
            vendor=vendor,
            location=location,
            status="online",
            last_seen=datetime.now(timezone.utc).isoformat(),
        )
        devices.append(device.to_public_dict())
        self._write(devices)
        return device.to_public_dict()

    def delete_device(self, device_id: str) -> bool:
        devices = self._read()
        initial_len = len(devices)
        devices = [d for d in devices if d["id"] != device_id]
        if len(devices) < initial_len:
            self._write(devices)
            return True
        return False

    def ingest_hardware_event(
        self,
        device_id: str,
        employee_id: str | None,
        auth_mode: str,
        status: str,
        confidence: float = 99.4,
        temperature_celsius: float | None = None,
    ) -> dict:
        devices = self._read()
        for device in devices:
            if device["id"] == device_id or device["serial_number"] == device_id:
                device["last_seen"] = datetime.now(timezone.utc).isoformat()
                device["status"] = "online"
                break
        self._write(devices)

        return {
            "sync_status": "accepted",
            "device_id": device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "employee_id": employee_id,
            "auth_mode": auth_mode,
            "verification_status": status,
            "confidence": confidence,
            "temperature_celsius": temperature_celsius,
        }
