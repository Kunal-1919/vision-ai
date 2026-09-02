from functools import lru_cache
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from app.config import KNOWN_FACES_DIR, LIVENESS_MIN_FRAMES, PET_CONFIDENCE_THRESHOLD
from app.face_recognizer import FaceRecognizer
from app.geofence import GeofenceValidator
from app.pet_classifier import PetClassifier

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="VisionAI",
    description=(
        "AI-powered image recognition and secure attendance verification. "
        "Built by Kunal Santosh Gawade — https://github.com/Kunal-1919"
    ),
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache
def get_pet_classifier() -> PetClassifier:
    return PetClassifier()


@lru_cache
def get_face_recognizer() -> FaceRecognizer:
    return FaceRecognizer()


@lru_cache
def get_geofence_validator() -> GeofenceValidator:
    return GeofenceValidator()


def _validate_image_bytes(image_bytes: bytes) -> None:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Invalid or corrupted image file") from exc


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "vision-ai"}


@app.post("/api/classify/pet")
async def classify_pet(file: UploadFile = File(...)) -> dict:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    _validate_image_bytes(image_bytes)
    prediction = get_pet_classifier().predict(image_bytes, PET_CONFIDENCE_THRESHOLD)
    return {
        "label": prediction.label,
        "confidence": prediction.confidence,
        "message": prediction.message,
        "top_predictions": prediction.top_predictions,
    }


@app.get("/api/attendance/config")
def attendance_config() -> dict:
    return get_geofence_validator().public_config()


@app.post("/api/recognize/face")
async def recognize_face(
    files: list[UploadFile] = File(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    accuracy_meters: float | None = Form(None),
) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="At least one camera frame is required")

    if len(files) < LIVENESS_MIN_FRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Live verification requires at least {LIVENESS_MIN_FRAMES} camera frames",
        )

    geo_result = get_geofence_validator().validate(latitude, longitude, accuracy_meters)
    if not geo_result.allowed:
        return {
            "recognized": False,
            "live": False,
            "restricted": True,
            "location_verified": False,
            "confidence": 0.0,
            "spoof_score": 0.0,
            "message": geo_result.message,
            "face_box": None,
            "person": None,
            "distance_meters": geo_result.distance_meters,
            "office_name": geo_result.office_name,
            "accuracy_meters": geo_result.accuracy_meters,
        }

    image_bytes_list: list[bytes] = []
    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Please upload image frames from the camera")
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty frame uploaded")
        _validate_image_bytes(image_bytes)
        image_bytes_list.append(image_bytes)

    result = get_face_recognizer().recognize(image_bytes_list)
    response = {
        "recognized": result.recognized,
        "live": result.live,
        "restricted": result.restricted,
        "location_verified": True,
        "confidence": result.confidence,
        "spoof_score": result.spoof_score,
        "message": result.message,
        "face_box": result.face_box,
        "person": result.person.to_public_dict() if result.person else None,
        "distance_meters": geo_result.distance_meters,
        "office_name": geo_result.office_name,
        "accuracy_meters": geo_result.accuracy_meters,
    }
    return response


@app.get("/api/persons")
def list_persons() -> dict:
    return {"persons": get_face_recognizer().list_persons()}


@app.get("/api/persons/{person_id}/photo")
def get_person_photo(person_id: str):
    recognizer = get_face_recognizer()
    person = recognizer.persons.get(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    photo_path = KNOWN_FACES_DIR / person.photo_filename
    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Photo not found")

    return FileResponse(photo_path)


@app.post("/api/persons/register")
async def register_person(
    person_id: str = Form(...),
    name: str = Form(...),
    role: str = Form(""),
    email: str = Form(""),
    department: str = Form(""),
    notes: str = Form(""),
    photo: UploadFile = File(...),
) -> dict:
    if not photo.content_type or not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload a face photo")

    photo_bytes = await photo.read()
    if not photo_bytes:
        raise HTTPException(status_code=400, detail="Empty photo uploaded")

    try:
        person = get_face_recognizer().register_person(
            person_id=person_id,
            name=name,
            role=role,
            email=email,
            department=department,
            notes=notes,
            photo_bytes=photo_bytes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"message": "Person registered successfully", "person": person}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
