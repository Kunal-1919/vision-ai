from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KNOWN_FACES_DIR = DATA_DIR / "known_faces"
PERSONS_FILE = DATA_DIR / "persons.json"
MODELS_DIR = DATA_DIR / "models"

OFFICE_LOCATION_FILE = DATA_DIR / "office_location.json"
ATTENDANCE_LOG_FILE = DATA_DIR / "attendance_log.json"
USERS_FILE = DATA_DIR / "users.json"

APP_ENV = os.environ.get("ENV", os.environ.get("VISIONAI_ENV", "development"))
PORT = int(os.environ.get("PORT", "8088"))
JWT_SECRET = os.environ.get("VISIONAI_JWT_SECRET", "visionai-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.environ.get("VISIONAI_JWT_EXPIRE_HOURS", "12"))

FACE_MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.28"))
SCENE_PHONE_THRESHOLD = float(os.environ.get("SCENE_PHONE_THRESHOLD", "0.12"))
LIVENESS_SPOOF_THRESHOLD = float(os.environ.get("LIVENESS_SPOOF_THRESHOLD", "0.65"))
LIVENESS_MIN_FRAMES = int(os.environ.get("LIVENESS_MIN_FRAMES", "3"))

for directory in (DATA_DIR, KNOWN_FACES_DIR, MODELS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
