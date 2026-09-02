import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.config import FACE_MATCH_THRESHOLD, KNOWN_FACES_DIR, MODELS_DIR, PERSONS_FILE
from app.liveness_detector import LivenessDetector

FACE_DETECTOR_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
    "face_detection_yunet_2023mar.onnx"
)
FACE_RECOGNIZER_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/"
    "face_recognition_sface_2021dec.onnx"
)


@dataclass
class Person:
    id: str
    name: str
    role: str
    email: str
    department: str
    photo_filename: str
    notes: str = ""

    def to_public_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "email": self.email,
            "department": self.department,
            "notes": self.notes,
            "photo_url": f"/api/persons/{self.id}/photo",
        }


@dataclass
class FaceMatch:
    recognized: bool
    person: Person | None
    confidence: float
    message: str
    face_box: list[int] | None = None
    live: bool = True
    restricted: bool = False
    spoof_score: float = 0.0


class FaceRecognizer:
    def __init__(self):
        self.detector_path = MODELS_DIR / "face_detection_yunet_2023mar.onnx"
        self.recognizer_path = MODELS_DIR / "face_recognition_sface_2021dec.onnx"
        self._ensure_models()
        self.detector = cv2.FaceDetectorYN.create(
            str(self.detector_path),
            "",
            (320, 320),
            0.6,
            0.3,
            5000,
        )
        self.recognizer = cv2.FaceRecognizerSF.create(
            str(self.recognizer_path),
            "",
        )
        self.persons: dict[str, Person] = {}
        self.embeddings: dict[str, np.ndarray] = {}
        self.liveness = LivenessDetector()
        self._load_persons()
        self._build_embeddings()

    def _ensure_models(self) -> None:
        for url, path in (
            (FACE_DETECTOR_URL, self.detector_path),
            (FACE_RECOGNIZER_URL, self.recognizer_path),
        ):
            if not path.exists():
                urllib.request.urlretrieve(url, path)

    def _load_persons(self) -> None:
        if not PERSONS_FILE.exists():
            self._seed_demo_persons()
        with PERSONS_FILE.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        self.persons = {
            item["id"]: Person(**item)
            for item in payload.get("persons", [])
        }

    def _seed_demo_persons(self) -> None:
        demo = {
            "persons": [
                {
                    "id": "demo-user",
                    "name": "Demo User",
                    "role": "Software Engineer",
                    "email": "demo@company.com",
                    "department": "Engineering",
                    "photo_filename": "demo-user.jpg",
                    "notes": "Replace this with your own photo in data/known_faces/",
                }
            ]
        }
        PERSONS_FILE.write_text(json.dumps(demo, indent=2), encoding="utf-8")

    def _read_image(self, image_bytes: bytes) -> np.ndarray:
        array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Invalid image data")
        return image

    def _detect_largest_face(self, image: np.ndarray):
        height, width = image.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(image)
        if faces is None or len(faces) == 0:
            return None
        faces = sorted(faces, key=lambda face: face[2] * face[3], reverse=True)
        return faces[0]

    def _embedding_for_face(self, image: np.ndarray, face) -> np.ndarray:
        aligned = self.recognizer.alignCrop(image, face)
        feature = self.recognizer.feature(aligned)
        return feature

    def _build_embeddings(self) -> None:
        self.embeddings.clear()
        for person_id, person in self.persons.items():
            photo_path = KNOWN_FACES_DIR / person.photo_filename
            if not photo_path.exists():
                continue
            image = cv2.imread(str(photo_path))
            if image is None:
                continue
            face = self._detect_largest_face(image)
            if face is None:
                continue
            self.embeddings[person_id] = self._embedding_for_face(image, face)

    def list_persons(self) -> list[dict]:
        return [person.to_public_dict() for person in self.persons.values()]

    def register_person(
        self,
        person_id: str,
        name: str,
        role: str,
        email: str,
        department: str,
        notes: str,
        photo_bytes: bytes,
    ) -> dict:
        safe_id = "".join(char for char in person_id.lower().replace(" ", "-") if char.isalnum() or char == "-")
        if not safe_id:
            raise ValueError("Person id is required")

        extension = ".jpg"
        photo_filename = f"{safe_id}{extension}"
        photo_path = KNOWN_FACES_DIR / photo_filename
        photo_path.write_bytes(photo_bytes)

        image = self._read_image(photo_bytes)
        face = self._detect_largest_face(image)
        if face is None:
            photo_path.unlink(missing_ok=True)
            raise ValueError("No face detected in the uploaded photo")

        person = Person(
            id=safe_id,
            name=name,
            role=role,
            email=email,
            department=department,
            photo_filename=photo_filename,
            notes=notes,
        )
        self.persons[safe_id] = person
        self.embeddings[safe_id] = self._embedding_for_face(image, face)
        self._persist_persons()
        return person.to_public_dict()

    def _persist_persons(self) -> None:
        payload = {
            "persons": [
                {
                    "id": person.id,
                    "name": person.name,
                    "role": person.role,
                    "email": person.email,
                    "department": person.department,
                    "photo_filename": person.photo_filename,
                    "notes": person.notes,
                }
                for person in self.persons.values()
            ]
        }
        PERSONS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def recognize(self, image_bytes_list: list[bytes]) -> FaceMatch:
        if not image_bytes_list:
            return FaceMatch(
                recognized=False,
                person=None,
                confidence=0.0,
                message=LivenessDetector.RESTRICTED_MESSAGE,
                live=False,
                restricted=True,
            )

        images = [self._read_image(image_bytes) for image_bytes in image_bytes_list]
        primary = images[len(images) // 2]
        face = self._detect_largest_face(primary)
        if face is None:
            return FaceMatch(
                recognized=False,
                person=None,
                confidence=0.0,
                message="No face detected. Please face the camera clearly.",
            )

        face_box = self._face_box(face)
        liveness = self.liveness.verify(images, face_box)
        if not liveness.is_live:
            return FaceMatch(
                recognized=False,
                person=None,
                confidence=0.0,
                message=liveness.message,
                face_box=face_box,
                live=False,
                restricted=True,
                spoof_score=liveness.spoof_score,
            )

        if not self.embeddings:
            return FaceMatch(
                recognized=False,
                person=None,
                confidence=0.0,
                message="No known persons enrolled yet. Register yourself first.",
                face_box=self._face_box(face),
            )

        probe = self._embedding_for_face(primary, face)
        best_id = None
        best_score = -1.0

        for person_id, embedding in self.embeddings.items():
            score = float(self.recognizer.match(probe, embedding, cv2.FaceRecognizerSF_FR_COSINE))
            if score > best_score:
                best_score = score
                best_id = person_id

        if best_id is None or best_score < FACE_MATCH_THRESHOLD:
            return FaceMatch(
                recognized=False,
                person=None,
                confidence=round(max(best_score, 0.0) * 100, 2),
                message="Face detected, but no matching person found.",
                face_box=self._face_box(face),
            )

        person = self.persons[best_id]
        return FaceMatch(
            recognized=True,
            person=person,
            confidence=round(best_score * 100, 2),
            message=f"Attendance verified. Welcome, {person.name}!",
            face_box=face_box,
            live=True,
            restricted=False,
            spoof_score=liveness.spoof_score,
        )

    def _face_box(self, face) -> list[int]:
        x, y, width, height = face[:4]
        return [int(x), int(y), int(width), int(height)]
