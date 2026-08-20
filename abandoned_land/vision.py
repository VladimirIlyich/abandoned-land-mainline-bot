from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from statistics import median
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
    battle_screen: bool = True
    base_hp_valid: bool = True
    energy_valid: bool = True
    enemy_valid: bool = True

    @property
    def total_enemies(self) -> int:
        # boss/elite 常共用一套颜色掩码，取较大值避免同一目标被重复计算。
        return self.ground_count + self.air_count + max(self.elite_count, self.boss_count)

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


def _dark_entity_stats(image: Image.Image, box: list[float], y_range: tuple[float, float], min_area: int = 250) -> tuple[int, tuple[float, float] | None]:
    """识别当前版本的黑色敌人轮廓，避开彩色背景和伤害数字。"""
    import cv2
    import numpy as np
    hsv = _roi(image, box)
    mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([179, 110, 65]))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    count, _, stats, centers = cv2.connectedComponentsWithStats(mask)
    w, h = image.size
    x0, y0, rw, rh = box
    candidates: list[tuple[float, float, int]] = []
    for i in range(1, count):
        x, y, cw, ch, area = stats[i]
        cx = x0 + (centers[i][0] / max(w * rw, 1)) * rw
        cy = y0 + (centers[i][1] / max(h * rh, 1)) * rh
        if not (y_range[0] <= cy <= y_range[1]):
            continue
        if area < min_area or cw < 18 or ch < 18 or cw > 140 or ch > 90:
            continue
        # 左侧基地人物不是敌人；当前关卡敌人从画面中部开始出现。
        if cx < 0.28:
            continue
        candidates.append((cx, cy, int(area)))

    # 一个飞行敌人可能被伤害特效切成多个块，按邻近中心合并。
    clusters: list[list[tuple[float, float, int]]] = []
    for candidate in sorted(candidates):
        for cluster in clusters:
            if min(abs(candidate[0] - item[0]) for item in cluster) <= 0.065 and abs(candidate[1] - cluster[0][1]) <= 0.10:
                cluster.append(candidate)
                break
        else:
            clusters.append([candidate])
    if not clusters:
        return 0, None
    total_area = sum(item[2] for cluster in clusters for item in cluster)
    center = (
        sum(item[0] * item[2] for cluster in clusters for item in cluster) / total_area,
        sum(item[1] * item[2] for cluster in clusters for item in cluster) / total_area,
    )
    return len(clusters), center


def _red_bar_stats(image: Image.Image, box: list[float]) -> tuple[int, tuple[float, float] | None]:
    """识别敌人上方的长红血条，作为精英/首领的稳定提示。"""
    import cv2
    import numpy as np
    hsv = _roi(image, box)
    # 实机血条在特效叠加时会偏橙红，放宽色相上限但仍用长宽比过滤。
    lower = cv2.inRange(hsv, np.array([0, 80, 45]), np.array([20, 255, 255]))
    upper = cv2.inRange(hsv, np.array([170, 100, 55]), np.array([179, 255, 255]))
    mask = cv2.bitwise_or(lower, upper)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 5), np.uint8))
    count, _, stats, centers = cv2.connectedComponentsWithStats(mask)
    w, h = image.size
    x0, y0, rw, rh = box
    bars: list[tuple[float, float, int]] = []
    for i in range(1, count):
        x, y, cw, ch, area = stats[i]
        if area < 180 or cw < 70 or ch < 4 or ch > 100 or cw / max(ch, 1) < 5:
            continue
        cx = x0 + (centers[i][0] / max(w * rw, 1)) * rw
        cy = y0 + (centers[i][1] / max(h * rh, 1)) * rh
        if not (0.25 <= cx <= 0.98 and 0.18 <= cy <= 0.72):
            continue
        bars.append((cx, min(0.76, cy + 0.08), int(area)))
    if not bars:
        return 0, None
    total_area = sum(item[2] for item in bars)
    center = (
        sum(item[0] * item[2] for item in bars) / total_area,
        sum(item[1] * item[2] for item in bars) / total_area,
    )
    return len(bars), center


def _bar_ratio(image: Image.Image, box: list[float], color: str) -> float:
    import cv2
    import numpy as np
    hsv = _roi(image, box)
    if color == "green":
        mask = cv2.inRange(hsv, np.array([35, 60, 60]), np.array([95, 255, 255]))
    elif color == "blue":
        mask = cv2.inRange(hsv, np.array([90, 60, 60]), np.array([140, 255, 255]))
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
        # 加载页的进度条也会产生长色块，不能把它当作一张符咒。
        if cw > rw * w * 0.18:
            continue
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
        window = max(1, int(config.get("screen", {}).get("resource_smoothing_window", 5)))
        self._base_hp_signals = deque(maxlen=window)
        self._energy_signals = deque(maxlen=window)

    def read(self, image: Image.Image, elapsed_seconds: float) -> GameState:
        screen = self.config["screen"]
        battle_detection = screen.get("battle_detection", {})
        min_landscape_ratio = battle_detection.get("min_landscape_ratio", 1.10)
        battle_screen = image.width >= image.height * min_landscape_ratio
        colors = screen["enemy_colors"]
        enemy_detection = screen.get("enemy_detection", {})
        spell = screen.get("spell_detection", {})
        base_hp_detection = screen.get("base_hp_detection", {})
        energy_detection = screen.get("energy_detection", {})
        cards = _detect_cards(image, spell["card_roi"], spell.get("min_card_area", 1500)) if spell.get("enabled", False) else []
        card_count = len(cards)
        max_cards = spell.get("max_cards", 10)
        spell_fill = min(1.0, card_count / max_cards) if max_cards else 0.0
        if enemy_detection.get("mode") == "dark_entities":
            ground_count, ground_position = _dark_entity_stats(image, screen["playfield"], (0.64, 0.76))
            air_count, air_position = _dark_entity_stats(image, screen["playfield"], (0.20, 0.58))
            special_count, special_position = _red_bar_stats(image, screen["playfield"])
            # 当前截图无法稳定区分“精英”和“首领”的血条样式；统一作为高威胁目标，
            # 交给策略优先使用鬼仆和控制技能，避免漏放鬼仆。
            boss_count, boss_position = 0, None
            elite_count, elite_position = special_count, special_position
        else:
            ground_count, ground_position = _color_stats(image, screen["playfield"], colors["ground"])
            air_count, air_position = _color_stats(image, screen["playfield"], colors["air"])
            boss_count, boss_position = _color_stats(image, screen["playfield"], colors["boss"], min_area=120)
            elite_count, elite_position = _color_stats(image, screen["playfield"], colors.get("elite", colors["boss"]), min_area=120)
        estimated_total = ground_count + air_count + max(elite_count, boss_count)
        enemy_valid = not enemy_detection.get("enabled", True) or estimated_total <= enemy_detection.get("max_total_enemies", 24)
        # 横屏实机基地护盾/血量显示为蓝色区域；绿色阈值会把正常满血误判为未校准。
        base_hp_signal = _bar_ratio(image, screen["base_hp_roi"], "blue")
        energy_signal = _bar_ratio(image, screen["energy_roi"], "blue")
        self._base_hp_signals.append(base_hp_signal)
        self._energy_signals.append(energy_signal)
        # 战斗特效、数字和技能遮罩会短暂覆盖资源条；中值比单帧值稳定，
        # 同时仍能在几帧内跟随真实的掉血和符能变化。
        base_hp_signal = float(median(self._base_hp_signals))
        energy_signal = float(median(self._energy_signals))
        base_hp_valid = not base_hp_detection.get("enabled", True) or base_hp_signal >= base_hp_detection.get("min_signal", 0.08)
        energy_valid = not energy_detection.get("enabled", True) or energy_signal >= energy_detection.get("min_signal", 0.08)
        card_sources: dict[str, list[float]] = {}
        for card_type, point in cards:
            card_sources.setdefault(card_type, point)
        return GameState(
            base_hp=min(1.0, base_hp_signal * 3.0),
            energy=min(1.0, energy_signal * 3.0),
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
            battle_screen=battle_screen,
            base_hp_valid=base_hp_valid,
            energy_valid=energy_valid,
            enemy_valid=enemy_valid,
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
