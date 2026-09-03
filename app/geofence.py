import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

from app.config import OFFICE_LOCATION_FILE


@dataclass
class OfficeLocation:
    name: str
    latitude: float
    longitude: float
    radius_meters: float
    max_accuracy_meters: float = 100.0
    enabled: bool = True

    @classmethod
    def from_file(cls, path: Path = OFFICE_LOCATION_FILE) -> "OfficeLocation":
        # Environment Variable Overrides
        env_enabled = os.environ.get("GEOFENCE_ENABLED")
        env_lat = os.environ.get("OFFICE_LATITUDE")
        env_lon = os.environ.get("OFFICE_LONGITUDE")
        env_radius = os.environ.get("OFFICE_RADIUS_METERS")
        env_max_acc = os.environ.get("OFFICE_MAX_ACCURACY_METERS")
        env_name = os.environ.get("OFFICE_NAME")

        if not path.exists():
            default = cls(
                name=env_name or "Leap India Office Premises",
                latitude=float(env_lat) if env_lat else 19.1727325,
                longitude=float(env_lon) if env_lon else 72.8605398,
                radius_meters=float(env_radius) if env_radius else 300.0,
                max_accuracy_meters=float(env_max_acc) if env_max_acc else 150.0,
                enabled=env_enabled.lower() == "true" if env_enabled else True,
            )
            default.save(path)
            return default

        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            payload = {}

        return cls(
            name=env_name or payload.get("name", "Leap India Office Premises"),
            latitude=float(env_lat) if env_lat else float(payload.get("latitude", 19.1727325)),
            longitude=float(env_lon) if env_lon else float(payload.get("longitude", 72.8605398)),
            radius_meters=float(env_radius) if env_radius else float(payload.get("radius_meters", 300)),
            max_accuracy_meters=float(env_max_acc) if env_max_acc else float(payload.get("max_accuracy_meters", 150)),
            enabled=env_enabled.lower() == "true" if env_enabled is not None else bool(payload.get("enabled", True)),
        )

    def save(self, path: Path = OFFICE_LOCATION_FILE) -> None:
        path.write_text(
            json.dumps(
                {
                    "name": self.name,
                    "latitude": self.latitude,
                    "longitude": self.longitude,
                    "radius_meters": self.radius_meters,
                    "max_accuracy_meters": self.max_accuracy_meters,
                    "enabled": self.enabled,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


@dataclass
class GeofenceResult:
    allowed: bool
    restricted: bool
    message: str
    distance_meters: float | None = None
    office_name: str | None = None
    accuracy_meters: float | None = None


class GeofenceValidator:
    RESTRICTED_MESSAGE = (
        "This activity is restricted. Attendance can only be marked from the office premises. "
        "You must be physically present at the office to check in."
    )

    ACCURACY_MESSAGE = (
        "This activity is restricted. Unable to verify your office location accurately. "
        "Please enable location services and try again from the office premises."
    )

    MISSING_LOCATION_MESSAGE = (
        "This activity is restricted. Office location is required for attendance check-in. "
        "Please allow location access on your phone browser and try again."
    )

    def __init__(self, office_file: Path = OFFICE_LOCATION_FILE):
        self.office_file = office_file

    def get_office(self) -> OfficeLocation:
        return OfficeLocation.from_file(self.office_file)

    def update_config(
        self,
        name: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_meters: float | None = None,
        max_accuracy_meters: float | None = None,
        enabled: bool | None = None,
    ) -> OfficeLocation:
        office = self.get_office()
        if name is not None:
            office.name = name
        if latitude is not None:
            office.latitude = latitude
        if longitude is not None:
            office.longitude = longitude
        if radius_meters is not None:
            office.radius_meters = radius_meters
        if max_accuracy_meters is not None:
            office.max_accuracy_meters = max_accuracy_meters
        if enabled is not None:
            office.enabled = enabled

        office.save(self.office_file)
        return office

    def validate(
        self,
        latitude: float | None,
        longitude: float | None,
        accuracy_meters: float | None = None,
    ) -> GeofenceResult:
        office = self.get_office()

        if not office.enabled:
            return GeofenceResult(
                allowed=True,
                restricted=False,
                message="Office geofence is currently disabled.",
                office_name=office.name,
            )

        if latitude is None or longitude is None:
            return GeofenceResult(
                allowed=False,
                restricted=True,
                message=self.MISSING_LOCATION_MESSAGE,
                office_name=office.name,
            )

        if accuracy_meters is not None and accuracy_meters > office.max_accuracy_meters:
            return GeofenceResult(
                allowed=False,
                restricted=True,
                message=(
                    f"Location accuracy is too low ({int(accuracy_meters)}m, max allowed {int(office.max_accuracy_meters)}m). "
                    "Please move near a window or turn on Precise Location in phone settings."
                ),
                office_name=office.name,
                accuracy_meters=accuracy_meters,
            )

        distance = self._distance_meters(
            latitude,
            longitude,
            office.latitude,
            office.longitude,
        )

        if distance <= office.radius_meters:
            return GeofenceResult(
                allowed=True,
                restricted=False,
                message=f"Location verified at {office.name}.",
                distance_meters=round(distance, 2),
                office_name=office.name,
                accuracy_meters=accuracy_meters,
            )

        return GeofenceResult(
            allowed=False,
            restricted=True,
            message=(
                f"{self.RESTRICTED_MESSAGE} "
                f"You are approximately {int(distance)} meters away from {office.name}."
            ),
            distance_meters=round(distance, 2),
            office_name=office.name,
            accuracy_meters=accuracy_meters,
        )

    def public_config(self) -> dict:
        office = self.get_office()
        return {
            "enabled": office.enabled,
            "office_name": office.name,
            "latitude": office.latitude,
            "longitude": office.longitude,
            "radius_meters": office.radius_meters,
            "max_accuracy_meters": office.max_accuracy_meters,
        }

    @staticmethod
    def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6_371_000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius * c
