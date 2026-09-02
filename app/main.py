from functools import lru_cache
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from app.attendance_logger import AttendanceLogger
from app.config import KNOWN_FACES_DIR, LIVENESS_MIN_FRAMES, SCENE_PHONE_THRESHOLD
from app.face_recognizer import FaceRecognizer
from app.geofence import GeofenceValidator
from app.scene_validator import SceneValidator

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="VisionAI",
    description=(
        "AI-powered secure attendance verification with face recognition, "
        "anti-spoofing, scene analysis, and GPS geofencing. "
        "Built by Kunal Santosh Gawade — https://github.com/Kunal-1919"
    ),
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache
def get_scene_validator() -> SceneValidator:
    return SceneValidator()


@lru_cache
def get_face_recognizer() -> FaceRecognizer:
    return FaceRecognizer()


@lru_cache
def get_geofence_validator() -> GeofenceValidator:
    return GeofenceValidator()


@lru_cache
def get_attendance_logger() -> AttendanceLogger:
    return AttendanceLogger()


def _validate_image_bytes(image_bytes: bytes) -> None:
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Invalid or corrupted image file") from exc


def _blocked_response(
    message: str,
    reason: str,
    office_name: str | None = None,
    distance_meters: float | None = None,
    accuracy_meters: float | None = None,
) -> dict:
    get_attendance_logger().log(
        status="blocked",
        reason=reason,
        message=message,
        office_name=office_name,
        distance_meters=distance_meters,
    )
    return {
        "recognized": False,
        "live": False,
        "restricted": True,
        "location_verified": reason != "geofence",
        "confidence": 0.0,
        "spoof_score": 0.0,
        "message": message,
        "face_box": None,
        "person": None,
        "distance_meters": distance_meters,
        "office_name": office_name,
        "accuracy_meters": accuracy_meters,
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "vision-ai", "version": "1.2.0"}


@app.get("/api/attendance/config")
def attendance_config() -> dict:
    return get_geofence_validator().public_config()


@app.get("/api/attendance/stats")
def attendance_stats() -> dict:
    recognizer = get_face_recognizer()
    return get_attendance_logger().get_stats(enrolled_count=len(recognizer.persons))


@app.get("/api/attendance/logs")
def attendance_logs(limit: int = 20) -> dict:
    return {"logs": get_attendance_logger().get_recent(limit=min(limit, 100))}


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
        return _blocked_response(
            geo_result.message,
            reason="geofence",
            office_name=geo_result.office_name,
            distance_meters=geo_result.distance_meters,
            accuracy_meters=geo_result.accuracy_meters,
        )

    image_bytes_list: list[bytes] = []
    for file in files:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Please upload image frames from the camera")
        image_bytes = await file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty frame uploaded")
        _validate_image_bytes(image_bytes)
        image_bytes_list.append(image_bytes)

    scene_result = get_scene_validator().validate(
        image_bytes_list[len(image_bytes_list) // 2],
        phone_threshold=SCENE_PHONE_THRESHOLD,
    )
    if not scene_result.allowed:
        return _blocked_response(
            scene_result.message,
            reason="scene",
            office_name=geo_result.office_name,
            distance_meters=geo_result.distance_meters,
            accuracy_meters=accuracy_meters,
        )

    result = get_face_recognizer().recognize(image_bytes_list)
    logger = get_attendance_logger()

    if result.restricted:
        reason = "liveness" if not result.live else "unknown"
        logger.log(
            status="blocked",
            reason=reason,
            message=result.message,
            office_name=geo_result.office_name,
            distance_meters=geo_result.distance_meters,
        )
    elif not result.recognized:
        logger.log(
            status="blocked",
            reason="face_mismatch",
            message=result.message,
            confidence=result.confidence,
            office_name=geo_result.office_name,
            distance_meters=geo_result.distance_meters,
        )
    else:
        logger.log(
            status="success",
            reason="verified",
            message=result.message,
            person_id=result.person.id if result.person else None,
            person_name=result.person.name if result.person else None,
            confidence=result.confidence,
            office_name=geo_result.office_name,
            distance_meters=geo_result.distance_meters,
        )

    return {
        "recognized": result.recognized,
        "live": result.live,
        "restricted": result.restricted,
        "location_verified": True,
        "scene_verified": True,
        "confidence": result.confidence,
        "spoof_score": result.spoof_score,
        "message": result.message,
        "face_box": result.face_box,
        "person": result.person.to_public_dict() if result.person else None,
        "distance_meters": geo_result.distance_meters,
        "office_name": geo_result.office_name,
        "accuracy_meters": accuracy_meters,
    }


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
