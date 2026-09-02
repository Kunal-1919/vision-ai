import io
from dataclasses import dataclass

import numpy as np
import torch
from PIL import Image
from torchvision import models

PERSON_KEYWORDS = (
    "person", "man", "woman", "boy", "girl", "face", "head", "scuba diver",
    "bridegroom", "groom", "bride", "ballplayer", "matador", "nurse", "doctor",
    "firefighter", "police", "soldier", "monk", "nun", "pirate", "cowboy",
    "lifeguard", "referee", "jockey", "skier", "swimmer", "diver",
)

DEVICE_KEYWORDS = (
    "cellular telephone", "mobile phone", "hand-held computer", "iPod",
    "laptop", "notebook", "desktop computer", "monitor", "screen",
    "television", "tablet", "remote control", "pay-phone", "dial telephone",
)

PRINT_MEDIA_KEYWORDS = (
    "envelope", "book jacket", "comic book", "menu", "poster", "card",
)


@dataclass
class SceneValidation:
    allowed: bool
    restricted: bool
    message: str
    phone_detected: bool = False
    device_detected: bool = False
    person_confidence: float = 0.0
    flagged_objects: list[str] | None = None


class SceneValidator:
    """AI scene analysis for attendance — detects phones, screens, and invalid subjects in frame."""

    RESTRICTED_PHONE_MESSAGE = (
        "This activity is restricted. A phone or electronic device was detected in the camera frame. "
        "Please put away all devices and present only your live face for attendance."
    )

    RESTRICTED_SCENE_MESSAGE = (
        "This activity is restricted. The camera frame does not show a valid attendance subject. "
        "Please face the camera directly with no photos or printed materials visible."
    )

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        weights = models.MobileNet_V3_Large_Weights.DEFAULT
        self.model = models.mobilenet_v3_large(weights=weights).to(self.device)
        self.model.eval()
        self.preprocess = weights.transforms()
        self.categories = weights.meta["categories"]

    def validate(self, image_bytes: bytes, phone_threshold: float = 0.12) -> SceneValidation:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(tensor)
            probabilities = torch.nn.functional.softmax(logits, dim=1)[0].cpu().numpy()

        ranked = np.argsort(probabilities)[::-1][:12]
        person_score = 0.0
        flagged: list[str] = []
        phone_detected = False
        device_detected = False

        for idx in ranked:
            label = self.categories[idx]
            prob = float(probabilities[idx])
            lower = label.lower()

            if any(keyword in lower for keyword in PERSON_KEYWORDS):
                person_score = max(person_score, prob)

            if any(keyword in lower for keyword in DEVICE_KEYWORDS) and prob >= phone_threshold:
                device_detected = True
                flagged.append(f"{label} ({prob * 100:.1f}%)")
                if any(kw in lower for kw in ("telephone", "phone", "computer", "iPod", "tablet")):
                    phone_detected = True

            if any(keyword in lower for keyword in PRINT_MEDIA_KEYWORDS) and prob >= 0.18:
                flagged.append(f"{label} ({prob * 100:.1f}%)")

        if phone_detected or device_detected:
            return SceneValidation(
                allowed=False,
                restricted=True,
                message=self.RESTRICTED_PHONE_MESSAGE,
                phone_detected=phone_detected,
                device_detected=device_detected,
                person_confidence=round(person_score * 100, 2),
                flagged_objects=flagged,
            )

        if flagged and person_score < 0.08:
            return SceneValidation(
                allowed=False,
                restricted=True,
                message=self.RESTRICTED_SCENE_MESSAGE,
                person_confidence=round(person_score * 100, 2),
                flagged_objects=flagged,
            )

        return SceneValidation(
            allowed=True,
            restricted=False,
            message="Scene validated for attendance check-in.",
            person_confidence=round(person_score * 100, 2),
            flagged_objects=flagged or None,
        )
