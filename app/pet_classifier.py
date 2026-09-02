import io
from dataclasses import dataclass

import numpy as np
import torch
import torchvision.transforms as transforms
from PIL import Image
from torchvision import models

IMAGENET_DOG_CLASSES = set(range(151, 269))

IMAGENET_CAT_CLASSES = set(range(281, 286))

DOG_KEYWORDS = ("dog", "terrier", "retriever", "spaniel", "shepherd", "poodle", "husky", "bulldog", "mastiff", "hound", "collie", "pinscher", "schnauzer", "pekingese", "chihuahua", "malamute", "dalmatian", "beagle", "boxer", "pug", "dachshund", "corgi", "labrador", "greyhound", "whippet", "setter", "pointer", "papillon", "samoyed", "shiba", "akita", "vizsla", "weimaraner", "borzoi", "saluki", "basenji", "keeshond", "otterhound", "wolfhound", "affenpinscher", "bloodhound", "cairn", "komondor", "leonberg", "newfoundland", "rottweiler", "schipperke", "scotch", "staffordshire", "tibetan", "yorkshire", "groenendael", "malinois", "kelpie", "dingo", "dhole")
CAT_KEYWORDS = ("cat", "tabby", "tiger cat", "persian", "siamese", "egyptian cat", "cougar", "lynx", "leopard", "jaguar", "cheetah", "lion", "tiger")


@dataclass
class PetPrediction:
    label: str
    confidence: float
    message: str
    top_predictions: list[dict]


class PetClassifier:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        weights = models.MobileNet_V3_Large_Weights.DEFAULT
        self.model = models.mobilenet_v3_large(weights=weights).to(self.device)
        self.model.eval()
        self.preprocess = weights.transforms()
        self.categories = weights.meta["categories"]

    def _score_label(self, class_idx: int, label: str, prob: float) -> tuple[str, float]:
        lower = label.lower()
        if class_idx in IMAGENET_CAT_CLASSES or any(word in lower for word in CAT_KEYWORDS):
            return "cat", prob
        if class_idx in IMAGENET_DOG_CLASSES or any(word in lower for word in DOG_KEYWORDS):
            return "dog", prob
        return "unknown", prob * 0.25

    def predict(self, image_bytes: bytes, confidence_threshold: float = 0.35) -> PetPrediction:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(tensor)
            probabilities = torch.nn.functional.softmax(logits, dim=1)[0].cpu().numpy()

        ranked = np.argsort(probabilities)[::-1][:8]
        dog_score = 0.0
        cat_score = 0.0
        top_predictions: list[dict] = []

        for idx in ranked:
            label = self.categories[idx]
            prob = float(probabilities[idx])
            mapped, score = self._score_label(int(idx), label, prob)
            top_predictions.append({
                "label": label,
                "mapped": mapped,
                "confidence": round(prob * 100, 2),
            })
            if mapped == "dog":
                dog_score = max(dog_score, score)
            elif mapped == "cat":
                cat_score = max(cat_score, score)

        if dog_score >= cat_score and dog_score >= confidence_threshold:
            return PetPrediction(
                label="dog",
                confidence=round(dog_score * 100, 2),
                message="It's a dog!",
                top_predictions=top_predictions,
            )

        if cat_score > dog_score and cat_score >= confidence_threshold:
            return PetPrediction(
                label="cat",
                confidence=round(cat_score * 100, 2),
                message="It's a cat!",
                top_predictions=top_predictions,
            )

        best = top_predictions[0] if top_predictions else {"label": "unknown", "confidence": 0}
        return PetPrediction(
            label="unknown",
            confidence=best["confidence"],
            message="Could not confidently identify a dog or cat. Try a clearer photo.",
            top_predictions=top_predictions,
        )
