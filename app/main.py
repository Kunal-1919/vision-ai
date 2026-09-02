from functools import lru_cache
from io import BytesIO
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from app.attendance_logger import AttendanceLogger
from app.auth import (
    RequireAdmin,
    RequireAuth,
    User,
    create_access_token,
    get_current_user,
    get_user_store,
)
from app.biometric import BiometricManager
from app.config import KNOWN_FACES_DIR, LIVENESS_MIN_FRAMES, SCENE_PHONE_THRESHOLD
from app.face_recognizer import FaceRecognizer
from app.geofence import GeofenceValidator
from app.scene_validator import SceneValidator

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="VisionAI Enterprise",
    description=(
        "Enterprise-grade Multimodal Biometric & AI Attendance Verification System. "
        "Integrates Edge AI face recognition, anti-spoofing liveness v2, GPS geofencing, "
        "and physical hardware terminal push sync (ZKTeco, Hikvision, Suprema, Wiegand). "
        "Built by Kunal Santosh Gawade — https://github.com/Kunal-1919"
    ),
    version="2.0.0-enterprise",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(status_code=500, content={"detail": "Internal server error. Please try again."})


class LoginRequest(BaseModel):
    username: str = Field(min_length=2)
    password: str = Field(min_length=6)


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
    person_id: str | None = None,
    person_name: str | None = None,
) -> dict:
    get_attendance_logger().log(
        status="blocked",
        reason=reason,
        message=message,
        office_name=office_name,
        distance_meters=distance_meters,
        person_id=person_id,
        person_name=person_name,
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
    return {"status": "ok", "service": "vision-ai", "version": "1.3.0"}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict:
    user = get_user_store().authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "user": user.to_public_dict()}


@app.get("/api/auth/me")
def auth_me(current_user: RequireAuth) -> dict:
    return {"user": current_user.to_public_dict()}


@app.get("/api/attendance/config")
def attendance_config(_: RequireAuth) -> dict:
    return get_geofence_validator().public_config()


@app.get("/api/attendance/stats")
def attendance_stats(_: RequireAdmin) -> dict:
    recognizer = get_face_recognizer()
    return get_attendance_logger().get_stats(enrolled_count=len(recognizer.persons))


@app.get("/api/attendance/logs")
def attendance_logs(_: RequireAdmin, limit: int = 20) -> dict:
    return {"logs": get_attendance_logger().get_recent(limit=min(limit, 100))}


@app.get("/api/users")
def list_users(_: RequireAdmin) -> dict:
    return {"users": [user.to_public_dict() for user in get_user_store().list_users()]}


@app.post("/api/recognize/face")
async def recognize_face(
    current_user: RequireAuth,
    files: list[UploadFile] = File(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    accuracy_meters: float | None = Form(None),
) -> dict:
    if current_user.role != "employee":
        raise HTTPException(
            status_code=403,
            detail="Only employees can mark attendance. Admins should use the dashboard to manage the system.",
        )

    if not current_user.person_id:
        raise HTTPException(
            status_code=403,
            detail="Your employee account is not linked to a face enrollment. Contact your administrator.",
        )

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
            person_id=current_user.person_id,
            person_name=current_user.name,
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
            person_id=current_user.person_id,
            person_name=current_user.name,
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
            person_id=current_user.person_id,
            person_name=current_user.name,
        )
    elif not result.recognized or not result.person:
        logger.log(
            status="blocked",
            reason="face_mismatch",
            message=result.message,
            confidence=result.confidence,
            office_name=geo_result.office_name,
            distance_meters=geo_result.distance_meters,
            person_id=current_user.person_id,
            person_name=current_user.name,
        )
    elif result.person.id != current_user.person_id:
        message = (
            "This activity is restricted. The recognized face does not match your logged-in account. "
            "You can only mark attendance for yourself."
        )
        return _blocked_response(
            message,
            reason="identity_mismatch",
            office_name=geo_result.office_name,
            distance_meters=geo_result.distance_meters,
            accuracy_meters=accuracy_meters,
            person_id=current_user.person_id,
            person_name=current_user.name,
        )
    else:
        logger.log(
            status="success",
            reason="verified",
            message=result.message,
            person_id=result.person.id,
            person_name=result.person.name,
            confidence=result.confidence,
            office_name=geo_result.office_name,
            distance_meters=geo_result.distance_meters,
        )

    if result.restricted or not result.recognized:
        return {
            "recognized": result.recognized,
            "live": result.live,
            "restricted": result.restricted or not result.recognized,
            "location_verified": True,
            "scene_verified": True,
            "confidence": result.confidence,
            "spoof_score": result.spoof_score,
            "message": result.message,
            "face_box": result.face_box,
            "person": result.person.to_public_dict() if result.person and result.recognized else None,
            "distance_meters": geo_result.distance_meters,
            "office_name": geo_result.office_name,
            "accuracy_meters": accuracy_meters,
        }

    return {
        "recognized": True,
        "live": result.live,
        "restricted": False,
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
def list_persons(_: RequireAdmin) -> dict:
    return {"persons": get_face_recognizer().list_persons()}


@app.get("/api/persons/{person_id}/photo")
def get_person_photo(person_id: str, current_user: RequireAuth):
    if current_user.role == "employee" and current_user.person_id != person_id:
        raise HTTPException(status_code=403, detail="You can only access your own profile photo.")

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
    _: RequireAdmin,
    person_id: str = Form(...),
    name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(""),
    email: str = Form(""),
    department: str = Form(""),
    notes: str = Form(""),
    photo: UploadFile = File(...),
) -> dict:
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

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
        user = get_user_store().create_employee_user(
            username=username,
            password=password,
            person_id=person["id"],
            name=name,
            email=email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "message": "Employee enrolled successfully with login credentials.",
        "person": person,
        "user": user.to_public_dict(),
    }


@app.delete("/api/persons/{person_id}")
def delete_person(person_id: str, _: RequireAdmin) -> dict:
    recognizer = get_face_recognizer()
    deleted = recognizer.delete_person(person_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Person not found")
    get_user_store().delete_user_by_person_id(person_id)
    return {"message": f"Employee '{person_id}' deleted successfully."}


class BiometricDeviceRegisterRequest(BaseModel):
    name: str = Field(min_length=2)
    serial_number: str = Field(min_length=3)
    ip_address: str = Field(min_length=7)
    device_type: str = Field(min_length=2)
    vendor: str = Field(min_length=2)
    location: str = Field(min_length=2)


class BiometricWebhookPayload(BaseModel):
    device_id: str
    employee_id: str | None = None
    auth_mode: str = "face"
    status: str = "success"
    confidence: float = 99.4
    temperature_celsius: float | None = None


@lru_cache
def get_biometric_manager() -> BiometricManager:
    return BiometricManager()


@app.get("/api/biometric/devices")
def list_biometric_devices(_: RequireAdmin) -> dict:
    return {"devices": get_biometric_manager().list_devices()}


@app.post("/api/biometric/devices")
def register_biometric_device(payload: BiometricDeviceRegisterRequest, _: RequireAdmin) -> dict:
    device = get_biometric_manager().register_device(
        name=payload.name,
        serial_number=payload.serial_number,
        ip_address=payload.ip_address,
        device_type=payload.device_type,
        vendor=payload.vendor,
        location=payload.location,
    )
    return {"message": "Biometric terminal registered successfully.", "device": device}


@app.delete("/api/biometric/devices/{device_id}")
def delete_biometric_device(device_id: str, _: RequireAdmin) -> dict:
    deleted = get_biometric_manager().delete_device(device_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Biometric device not found.")
    return {"message": "Biometric device unlinked successfully."}


@app.post("/api/biometric/webhook")
def biometric_webhook(payload: BiometricWebhookPayload) -> dict:
    res = get_biometric_manager().ingest_hardware_event(
        device_id=payload.device_id,
        employee_id=payload.employee_id,
        auth_mode=payload.auth_mode,
        status=payload.status,
        confidence=payload.confidence,
        temperature_celsius=payload.temperature_celsius,
    )
    if payload.employee_id:
        person_name = payload.employee_id
        recognizer = get_face_recognizer()
        if payload.employee_id in recognizer.persons:
            person_name = recognizer.persons[payload.employee_id].name
        get_attendance_logger().log(
            status=payload.status,
            reason=f"hardware_{payload.auth_mode}",
            message=f"Hardware check-in via {payload.auth_mode.upper()} ({payload.device_id})",
            person_id=payload.employee_id,
            person_name=person_name,
            confidence=payload.confidence,
        )
    return res


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
