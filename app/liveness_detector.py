from dataclasses import dataclass

import cv2
import numpy as np

from app.config import LIVENESS_SPOOF_THRESHOLD


@dataclass
class LivenessResult:
    is_live: bool
    spoof_score: float
    message: str
    checks: dict[str, float]


class LivenessDetector:
    """Detects photo/screen replay attacks for attendance verification."""

    RESTRICTED_MESSAGE = (
        "This activity is restricted. Live face verification failed. "
        "Please present your real face to the camera. Photos, phone screens, "
        "and printed images are not allowed."
    )

    def verify(self, images: list[np.ndarray], face_box: list[int] | None = None) -> LivenessResult:
        if not images:
            return LivenessResult(
                is_live=False,
                spoof_score=1.0,
                message=self.RESTRICTED_MESSAGE,
                checks={},
            )

        primary = images[len(images) // 2]
        roi = self._extract_roi(primary, face_box)
        if roi is None or roi.size == 0:
            return LivenessResult(
                is_live=False,
                spoof_score=1.0,
                message=self.RESTRICTED_MESSAGE,
                checks={},
            )

        checks = {
            "screen_pattern": self._screen_pattern_score(roi),
            "display_color_cast": self._display_color_cast_score(roi),
            "specular_glare": self._specular_glare_score(roi),
            "flat_texture": self._flat_texture_score(roi),
            "digital_sharpness": self._digital_sharpness_score(roi),
        }

        if len(images) >= 2:
            checks["static_replay"] = self._static_replay_score(images, face_box)
            checks["rigid_surface"] = self._rigid_surface_score(images, face_box)
        else:
            checks["static_replay"] = 0.55
            checks["rigid_surface"] = 0.45

        spoof_score = (
            checks["screen_pattern"] * 0.22
            + checks["display_color_cast"] * 0.12
            + checks["specular_glare"] * 0.15
            + checks["flat_texture"] * 0.15
            + checks["digital_sharpness"] * 0.08
            + checks["static_replay"] * 0.16
            + checks["rigid_surface"] * 0.12
        )

        is_live = spoof_score < LIVENESS_SPOOF_THRESHOLD
        return LivenessResult(
            is_live=is_live,
            spoof_score=round(spoof_score, 4),
            message="Live face verified." if is_live else self.RESTRICTED_MESSAGE,
            checks={key: round(value, 4) for key, value in checks.items()},
        )

    def _extract_roi(self, image: np.ndarray, face_box: list[int] | None) -> np.ndarray | None:
        if face_box is None:
            height, width = image.shape[:2]
            size = min(height, width)
            top = (height - size) // 2
            left = (width - size) // 2
            return image[top : top + size, left : left + size]

        x, y, width, height = face_box
        padding_x = int(width * 0.35)
        padding_y = int(height * 0.35)
        x1 = max(0, int(x) - padding_x)
        y1 = max(0, int(y) - padding_y)
        x2 = min(image.shape[1], int(x + width) + padding_x)
        y2 = min(image.shape[0], int(y + height) + padding_y)
        roi = image[y1:y2, x1:x2]
        if roi.size == 0:
            return None
        return roi

    def _screen_pattern_score(self, roi: np.ndarray) -> float:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (128, 128))
        spectrum = np.fft.fftshift(np.fft.fft2(resized))
        magnitude = np.log1p(np.abs(spectrum))

        center = magnitude.shape[0] // 2
        y_grid, x_grid = np.ogrid[: magnitude.shape[0], : magnitude.shape[1]]
        distance = np.sqrt((x_grid - center) ** 2 + (y_grid - center) ** 2)
        inner = magnitude[distance < 12].mean()
        outer = magnitude[(distance >= 18) & (distance < 42)].mean()
        ratio = outer / (inner + 1e-6)

        horizontal_energy = magnitude[center - 2 : center + 3, :].mean()
        vertical_energy = magnitude[:, center - 2 : center + 3].mean()
        grid_energy = (horizontal_energy + vertical_energy) / (magnitude.mean() + 1e-6)

        score = min(1.0, max(0.0, (ratio - 0.85) * 1.4))
        score = max(score, min(1.0, max(0.0, (grid_energy - 1.15) * 0.9)))
        return score

    def _display_color_cast_score(self, roi: np.ndarray) -> float:
        channels = cv2.split(roi.astype(np.float32))
        means = [channel.mean() for channel in channels]
        blue, green, red = means[0], means[1], means[2]
        total = blue + green + red + 1e-6

        blue_ratio = blue / total
        red_ratio = red / total
        saturation = roi.astype(np.float32).max(axis=2) - roi.astype(np.float32).min(axis=2)
        sat_mean = saturation.mean() / 255.0

        score = 0.0
        if blue_ratio > 0.36:
            score += min(1.0, (blue_ratio - 0.36) * 5.0)
        if red_ratio < 0.28:
            score += min(1.0, (0.28 - red_ratio) * 4.0)
        if sat_mean > 0.42:
            score += min(1.0, (sat_mean - 0.42) * 2.5)
        return min(1.0, score / 2.2)

    def _specular_glare_score(self, roi: np.ndarray) -> float:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        bright = (gray > 235).astype(np.uint8)
        bright_ratio = bright.mean()

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        value = hsv[:, :, 2]
        very_bright = (value > 245).astype(np.uint8)
        cluster_ratio = very_bright.mean()

        score = min(1.0, bright_ratio * 8.0)
        score = max(score, min(1.0, cluster_ratio * 10.0))
        return score

    def _flat_texture_score(self, roi: np.ndarray) -> float:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        block = 16
        variances = []
        for y in range(0, gray.shape[0] - block, block):
            for x in range(0, gray.shape[1] - block, block):
                patch = gray[y : y + block, x : x + block]
                variances.append(patch.var())

        if not variances:
            return 0.5

        low_variance_ratio = sum(variance < 90 for variance in variances) / len(variances)
        global_variance = gray.var()
        score = low_variance_ratio
        if global_variance < 180:
            score = max(score, min(1.0, (180 - global_variance) / 180))
        return min(1.0, score)

    def _digital_sharpness_score(self, roi: np.ndarray) -> float:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()

        if variance > 650:
            return min(1.0, (variance - 650) / 900)
        if variance < 55:
            return min(1.0, (55 - variance) / 55)
        return 0.0

    def _static_replay_score(self, images: list[np.ndarray], face_box: list[int] | None) -> float:
        diffs = []
        for first, second in zip(images, images[1:]):
            first_roi = self._extract_roi(first, face_box)
            second_roi = self._extract_roi(second, face_box)
            if first_roi is None or second_roi is None:
                continue
            first_gray = cv2.cvtColor(cv2.resize(first_roi, (96, 96)), cv2.COLOR_BGR2GRAY)
            second_gray = cv2.cvtColor(cv2.resize(second_roi, (96, 96)), cv2.COLOR_BGR2GRAY)
            diff = np.mean(np.abs(first_gray.astype(np.float32) - second_gray.astype(np.float32)))
            diffs.append(diff)

        if not diffs:
            return 0.6

        mean_diff = float(np.mean(diffs))
        if mean_diff < 1.2:
            return min(1.0, (1.2 - mean_diff) / 1.2)
        if mean_diff < 2.5:
            return min(0.8, (2.5 - mean_diff) / 2.5 * 0.5)
        return 0.0

    def _rigid_surface_score(self, images: list[np.ndarray], face_box: list[int] | None) -> float:
        if face_box is None:
            return 0.0

        x, y, width, height = face_box
        scores = []
        for first, second in zip(images, images[1:]):
            face_motion = self._region_motion(first, second, face_box)
            surround_box = self._surround_box(first.shape, face_box)
            surround_motion = self._region_motion(first, second, surround_box)
            if face_motion is None or surround_motion is None:
                continue

            if face_motion < 0.8 and surround_motion < 0.8:
                scores.append(0.75)
                continue

            ratio = min(face_motion, surround_motion) / (max(face_motion, surround_motion) + 1e-6)
            if ratio > 0.82 and face_motion > 0.8:
                scores.append(min(1.0, ratio))
            elif ratio > 0.9:
                scores.append(min(1.0, (ratio - 0.75) * 2.5))

        if not scores:
            return 0.0
        return float(np.mean(scores))

    def _surround_box(self, shape: tuple[int, ...], face_box: list[int]) -> list[int]:
        x, y, width, height = face_box
        pad = int(max(width, height) * 0.8)
        x1 = max(0, int(x) - pad)
        y1 = max(0, int(y) - pad)
        x2 = min(shape[1], int(x + width) + pad)
        y2 = min(shape[0], int(y + height) + pad)
        return [x1, y1, x2 - x1, y2 - y1]

    def _region_motion(
        self,
        first: np.ndarray,
        second: np.ndarray,
        box: list[int],
    ) -> float | None:
        x, y, width, height = box
        x2 = min(first.shape[1], int(x + width))
        y2 = min(first.shape[0], int(y + height))
        if x2 <= x or y2 <= y:
            return None

        first_patch = first[int(y) : y2, int(x) : x2]
        second_patch = second[int(y) : y2, int(x) : x2]
        if first_patch.size == 0 or second_patch.size == 0:
            return None

        first_gray = cv2.cvtColor(cv2.resize(first_patch, (64, 64)), cv2.COLOR_BGR2GRAY)
        second_gray = cv2.cvtColor(cv2.resize(second_patch, (64, 64)), cv2.COLOR_BGR2GRAY)
        return float(np.mean(np.abs(first_gray.astype(np.float32) - second_gray.astype(np.float32))))
