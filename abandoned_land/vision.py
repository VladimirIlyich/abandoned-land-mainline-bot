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
    elite_count: int = 0
    spell_fill: float = 0.0
    spell_full: bool = False
    visual_ready: dict[str, bool] | None = None
    ground_position: tuple[float, float] | None = None
    air_position: tuple[float, float] | None = None
    elite_position: tuple[float, float] | None = None
    boss_position: tuple[float, float] | None = None
    card_sources: dict[str, list[float]] | None = None

    @property
    def total_enemies(self) -> int:
        return self.ground_count + self.air_count + self.elite_count + self.boss_count

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


def _color_stats(image: Image.Image, box: list[float], bounds: list[list[int]], min_area: int = 45) -> tuple[int, tuple[float, float] | None]:
    import cv2
    import numpy as np
    hsv = _roi(image, box)
    mask = cv2.inRange(hsv, np.array(bounds[0]), np.array(bounds[1]))
    count, _, stats, centers = cv2.connectedComponentsWithStats(mask)
    valid = [(i, stats[i, cv2.CC_STAT_AREA]) for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= min_area]
    if not valid:
        return 0, None
    total_area = sum(area for _, area in valid)
    w, h = image.size
    x, y, rw, rh = box
    cx = sum(centers[i][0] * area for i, area in valid) / total_area
    cy = sum(centers[i][1] * area for i, area in valid) / total_area
    return len(valid), (x + (cx / max(w * rw, 1)) * rw, y + (cy / max(h * rh, 1)) * rh)


def _bar_ratio(image: Image.Image, box: list[float], color: str) -> float:
    import cv2
    import numpy as np
    hsv = _roi(image, box)
    if color == "green":
        mask = cv2.inRange(hsv, np.array([35, 60, 60]), np.array([95, 255, 255]))
    else:
        mask = cv2.inRange(hsv, np.array([0, 60, 60]), np.array([20, 255, 255]))
    return float(np.count_nonzero(mask)) / max(mask.size, 1)


def _mask_ratio(image: Image.Image, box: list[float], bounds: list[list[int]]) -> float:
    import cv2
    import numpy as np
    hsv = _roi(image, box)
    mask = cv2.inRange(hsv, np.array(bounds[0]), np.array(bounds[1]))
    return float(np.count_nonzero(mask)) / max(mask.size, 1)


def _card_type(hue: float) -> str:
    if hue <= 10 or hue >= 170:
        return "damage"
    if 90 <= hue <= 140:
        return "freeze"
    if 18 <= hue < 40:
        return "stun"
    if 40 <= hue < 90:
        return "knockback"
    return "damage"


def _detect_cards(image: Image.Image, box: list[float], min_area: int = 1500) -> list[tuple[str, list[float]]]:
    """检测当前手牌矩形，兼容卡牌数量变化时的动态排列。"""
    import cv2
    import numpy as np
    w, h = image.size
    hsv = _roi(image, box)
    mask = cv2.inRange(hsv, np.array([0, 55, 45]), np.array([179, 255, 255]))
    x0, y0, rw, rh = box
    detected: list[tuple[str, list[float]]] = []
    # 卡牌外发光会把相邻卡牌连成一个连通域，因此按列投影找卡牌间隙。
    scan_h = int(hsv.shape[0] * 0.85)
    projection = (mask[:scan_h] > 0).sum(axis=0)
    column_threshold = max(35, int(scan_h * 0.15))
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for index, value in enumerate(projection):
        if value > column_threshold and start is None:
            start = index
        elif value <= column_threshold and start is not None:
            if index - start >= rw * w * 0.025:
                runs.append((start, index))
            start = None
    if start is not None and len(projection) - start >= rw * w * 0.025:
        runs.append((start, len(projection)))

    for x, x_end in runs:
        cw = x_end - x
        row_projection = (mask[:scan_h, x:x_end] > 0).sum(axis=1)
        row_threshold = max(8, int(cw * 0.15))
        rows = np.flatnonzero(row_projection > row_threshold)
        if len(rows) == 0:
            continue
        y, y_end = int(rows[0]), int(rows[-1] + 1)
        ch = y_end - y
        if cw * ch < min_area or ch < rh * h * 0.35:
            continue
        inner = hsv[y + max(2, ch // 8): y + max(3, ch - ch // 8),
                    x + max(2, cw // 8): x + max(3, cw - cw // 8)]
        saturated = inner[inner[:, :, 1] > 70]
        if len(saturated) == 0:
            continue
        hue = float(np.median(saturated[:, 0]))
        center = [x0 + ((x + cw / 2) / max(rw * w, 1)) * rw,
                  y0 + ((y + ch / 2) / max(rh * h, 1)) * rh]
        detected.append((_card_type(hue), center))
    return sorted(detected, key=lambda item: item[1][0])


class Vision:
    def __init__(self, config: dict):
        self.config = config

    def read(self, image: Image.Image, elapsed_seconds: float) -> GameState:
        screen = self.config["screen"]
        colors = screen["enemy_colors"]
        spell = screen.get("spell_detection", {})
        cards = _detect_cards(image, spell["card_roi"], spell.get("min_card_area", 1500)) if spell.get("enabled", False) else []
        card_count = len(cards)
        max_cards = spell.get("max_cards", 10)
        spell_fill = min(1.0, card_count / max_cards) if max_cards else 0.0
        ground_count, ground_position = _color_stats(image, screen["playfield"], colors["ground"])
        air_count, air_position = _color_stats(image, screen["playfield"], colors["air"])
        boss_count, boss_position = _color_stats(image, screen["playfield"], colors["boss"], min_area=120)
        elite_count, elite_position = _color_stats(image, screen["playfield"], colors.get("elite", colors["boss"]), min_area=120)
        card_sources: dict[str, list[float]] = {}
        for card_type, point in cards:
            card_sources.setdefault(card_type, point)
        return GameState(
            base_hp=min(1.0, _bar_ratio(image, screen["base_hp_roi"], "green") * 3.0),
            energy=min(1.0, _bar_ratio(image, screen["energy_roi"], "blue") * 3.0),
            ground_count=ground_count,
            air_count=air_count,
            boss_count=boss_count,
            elapsed_seconds=elapsed_seconds,
            elite_count=elite_count,
            spell_fill=spell_fill,
            spell_full=spell.get("enabled", False) and card_count >= max_cards,
            ground_position=ground_position,
            air_position=air_position,
            elite_position=elite_position,
            boss_position=boss_position,
            card_sources=card_sources,
        )

    def visual_ready(self, image: Image.Image) -> dict[str, bool]:
        """估算技能按钮是否脱离冷却遮罩；阈值必须用实机截图校准。"""
        detection = self.config["screen"].get("cooldown_detection", {})
        if not detection.get("enabled", False):
            return {name: True for name in self.config["actions"]}

        import cv2
        import numpy as np
        screen = self.config["screen"]
        default_w, default_h = detection.get("roi_size", [0.07, 0.07])
        threshold = detection.get("ready_score_at", 0.42)
        result = {}
        for name in self.config["actions"]:
            if name not in screen["buttons"]:
                result[name] = False
                continue
            x, y = screen["buttons"][name]
            box = screen.get("action_rois", {}).get(name, [x - default_w / 2, y - default_h / 2, default_w, default_h])
            hsv = _roi(image, box)
            value = float(np.mean(hsv[:, :, 2])) / 255.0
            saturation = float(np.mean(hsv[:, :, 1])) / 255.0
            score = 0.65 * value + 0.35 * saturation
            result[name] = score >= threshold
        return result
