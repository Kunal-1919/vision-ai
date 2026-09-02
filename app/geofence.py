import json
import math
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
        if not path.exists():
            default = cls(
                name="Office Premises",
                latitude=19.0760,
                longitude=72.8777,
                radius_meters=150.0,
                max_accuracy_meters=100.0,
                enabled=True,
            )
            path.write_text(
                json.dumps(
                    {
                        "name": default.name,
                        "latitude": default.latitude,
                        "longitude": default.longitude,
                        "radius_meters": default.radius_meters,
                        "max_accuracy_meters": default.max_accuracy_meters,
                        "enabled": default.enabled,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return default

        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return cls(
            name=payload.get("name", "Office Premises"),
            latitude=float(payload["latitude"]),
            longitude=float(payload["longitude"]),
            radius_meters=float(payload.get("radius_meters", 150)),
            max_accuracy_meters=float(payload.get("max_accuracy_meters", 100)),
            enabled=bool(payload.get("enabled", True)),
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
        "Please allow location access and try again."
    )

    def __init__(self, office: OfficeLocation | None = None):
        self.office = office or OfficeLocation.from_file()

    def validate(
        self,
        latitude: float | None,
        longitude: float | None,
        accuracy_meters: float | None = None,
    ) -> GeofenceResult:
        if not self.office.enabled:
            return GeofenceResult(
                allowed=True,
                restricted=False,
                message="Office geofence disabled.",
                office_name=self.office.name,
            )

        if latitude is None or longitude is None:
            return GeofenceResult(
                allowed=False,
                restricted=True,
                message=self.MISSING_LOCATION_MESSAGE,
                office_name=self.office.name,
            )

        if accuracy_meters is not None and accuracy_meters > self.office.max_accuracy_meters:
            return GeofenceResult(
                allowed=False,
                restricted=True,
                message=self.ACCURACY_MESSAGE,
                office_name=self.office.name,
                accuracy_meters=accuracy_meters,
            )

        distance = self._distance_meters(
            latitude,
            longitude,
            self.office.latitude,
            self.office.longitude,
        )

        if distance <= self.office.radius_meters:
            return GeofenceResult(
                allowed=True,
                restricted=False,
                message=f"Location verified at {self.office.name}.",
                distance_meters=round(distance, 2),
                office_name=self.office.name,
                accuracy_meters=accuracy_meters,
            )

        return GeofenceResult(
            allowed=False,
            restricted=True,
            message=(
                f"{self.RESTRICTED_MESSAGE} "
                f"You are approximately {int(distance)} meters away from {self.office.name}."
            ),
            distance_meters=round(distance, 2),
            office_name=self.office.name,
            accuracy_meters=accuracy_meters,
        )

    def public_config(self) -> dict:
        return {
            "enabled": self.office.enabled,
            "office_name": self.office.name,
            "radius_meters": self.office.radius_meters,
            "max_accuracy_meters": self.office.max_accuracy_meters,
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
