from __future__ import annotations

from dataclasses import dataclass
@dataclass
class GameState:
    base_hp: float
    energy: float
    ground_count: int
    air_count: int
    boss_count: int
    elapsed_seconds: float

    @property
    def total_enemies(self) -> int:
        return self.ground_count + self.air_count + self.boss_count

    @property
    def air_ratio(self) -> float:
        total = self.total_enemies
        return self.air_count / total if total else 0.0


def _roi(image: Image.Image, box: list[float]) -> np.ndarray:
    import cv2
    import numpy as np
    w, h = image.size
    x, y, rw, rh = box
    return cv2.cvtColor(np.asarray(image.crop((int(x*w), int(y*h), int((x+rw)*w), int((y+rh)*h)))), cv2.COLOR_RGB2HSV)


def _count_color(image: Image.Image, box: list[float], bounds: list[list[int]], min_area: int = 45) -> int:
    import cv2
    import numpy as np
    hsv = _roi(image, box)
    mask = cv2.inRange(hsv, np.array(bounds[0]), np.array(bounds[1]))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    return sum(1 for area in stats[1:, cv2.CC_STAT_AREA] if area >= min_area)


def _bar_ratio(image: Image.Image, box: list[float], color: str) -> float:
    import cv2
    import numpy as np
    hsv = _roi(image, box)
    if color == "green":
        mask = cv2.inRange(hsv, np.array([35, 60, 60]), np.array([95, 255, 255]))
    else:
        mask = cv2.inRange(hsv, np.array([0, 60, 60]), np.array([20, 255, 255]))
    return float(np.count_nonzero(mask)) / max(mask.size, 1)


class Vision:
    def __init__(self, config: dict):
        self.config = config

    def read(self, image: Image.Image, elapsed_seconds: float) -> GameState:
        screen = self.config["screen"]
        colors = screen["enemy_colors"]
        return GameState(
            base_hp=min(1.0, _bar_ratio(image, screen["base_hp_roi"], "green") * 3.0),
            energy=min(1.0, _bar_ratio(image, screen["energy_roi"], "blue") * 3.0),
            ground_count=_count_color(image, screen["playfield"], colors["ground"]),
            air_count=_count_color(image, screen["playfield"], colors["air"]),
            boss_count=_count_color(image, screen["playfield"], colors["boss"], min_area=120),
            elapsed_seconds=elapsed_seconds,
        )
