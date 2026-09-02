import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import ATTENDANCE_LOG_FILE


@dataclass
class AttendanceRecord:
    id: str
    timestamp: str
    person_id: str | None
    person_name: str | None
    status: str
    reason: str
    message: str
    confidence: float = 0.0
    office_name: str | None = None
    distance_meters: float | None = None


class AttendanceLogger:
    def __init__(self, log_file: Path = ATTENDANCE_LOG_FILE):
        self.log_file = log_file
        if not self.log_file.exists():
            self._write([])

    def _read(self) -> list[dict]:
        with self.log_file.open(encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, records: list[dict]) -> None:
        self.log_file.write_text(json.dumps(records, indent=2), encoding="utf-8")

    def log(
        self,
        *,
        status: str,
        reason: str,
        message: str,
        person_id: str | None = None,
        person_name: str | None = None,
        confidence: float = 0.0,
        office_name: str | None = None,
        distance_meters: float | None = None,
    ) -> AttendanceRecord:
        record = AttendanceRecord(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc).isoformat(),
            person_id=person_id,
            person_name=person_name,
            status=status,
            reason=reason,
            message=message,
            confidence=confidence,
            office_name=office_name,
            distance_meters=distance_meters,
        )
        records = self._read()
        records.insert(0, asdict(record))
        self._write(records[:500])
        return record

    def get_recent(self, limit: int = 20) -> list[dict]:
        return self._read()[:limit]

    def get_stats(self, enrolled_count: int) -> dict:
        records = self._read()
        today = datetime.now(timezone.utc).date().isoformat()

        today_records = [r for r in records if r.get("timestamp", "").startswith(today)]
        successful_today = sum(1 for r in today_records if r.get("status") == "success")
        blocked_today = sum(1 for r in today_records if r.get("status") == "blocked")
        total_check_ins = sum(1 for r in records if r.get("status") == "success")

        reason_counts: dict[str, int] = {}
        for record in today_records:
            if record.get("status") == "blocked":
                reason = record.get("reason", "unknown")
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

        return {
            "enrolled_count": enrolled_count,
            "check_ins_today": successful_today,
            "blocked_today": blocked_today,
            "total_check_ins": total_check_ins,
            "blocked_reasons_today": reason_counts,
        }
