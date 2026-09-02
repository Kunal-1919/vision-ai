from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
KNOWN_FACES_DIR = DATA_DIR / "known_faces"
PERSONS_FILE = DATA_DIR / "persons.json"
MODELS_DIR = DATA_DIR / "models"

OFFICE_LOCATION_FILE = DATA_DIR / "office_location.json"

FACE_MATCH_THRESHOLD = 0.363
PET_CONFIDENCE_THRESHOLD = 0.35
LIVENESS_SPOOF_THRESHOLD = 0.42
LIVENESS_MIN_FRAMES = 3

for directory in (DATA_DIR, KNOWN_FACES_DIR, MODELS_DIR):
    directory.mkdir(parents=True, exist_ok=True)
