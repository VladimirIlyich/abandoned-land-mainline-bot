import json
import logging
from pathlib import Path
import time
from collections import deque
from .policy import MainlinePolicy
from .vision import Vision

log = logging.getLogger(__name__)


class Runner:
    def __init__(self, config: dict, adb):
        self.config = config
        self.adb = adb
        self.vision = Vision(config)
        self.policy = MainlinePolicy(config)
        self.last_action_at: dict[str, float] = {}
        self.action_times = deque()
        self.started_at = time.monotonic()
        self.last_history_at = 0.0
        self.history_file = Path(config["runtime"].get("history_file", "run_history.jsonl"))

    def _record(self, state, decision, ready, now: float, event: str = "snapshot") -> None:
        interval = self.config["runtime"].get("history_interval_seconds", 1.0)
        if event == "snapshot" and now - self.last_history_at < interval:
            return
        self.last_history_at = now
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "event": event,
            "elapsed_seconds": round(state.elapsed_seconds, 2),
            "base_hp": round(state.base_hp, 3),
            "energy": round(state.energy, 3),
            "spell_fill": round(state.spell_fill, 3),
            "spell_full": state.spell_full,
            "ground_count": state.ground_count,
            "air_count": state.air_count,
            "elite_count": state.elite_count,
            "boss_count": state.boss_count,
            "ready_actions": sorted(ready),
            "decision": decision.action,
            "reason": decision.reason,
            "target": decision.target,
        }
        try:
            with self.history_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError as exc:
            log.warning("无法写入对局记录 %s: %s", self.history_file, exc)

    def _point(self, name: str, image) -> tuple[int, int]:
        x, y = self.config["screen"]["buttons"][name]
        return int(x * image.width), int(y * image.height)

    def _relative_point(self, point: list[float], image) -> tuple[int, int]:
        return int(point[0] * image.width), int(point[1] * image.height)

    def _drag_points(self, name: str, image, state=None, target_kind: str | None = None) -> tuple[tuple[int, int], tuple[int, int]]:
        spec = self.config["actions"][name]
        source = spec.get("source")
        if source is None:
            source = self.config["screen"]["buttons"][name]
        target = spec.get("target", self.config["screen"].get("default_drag_target", [0.52, 0.48]))
        if state is not None and target_kind:
            position = getattr(state, f"{target_kind}_position", None)
            if position is not None:
                target = list(position)
        return self._relative_point(source, image), self._relative_point(target, image)

    def _ready(self, now: float, visual_ready: dict[str, bool]) -> set[str]:
        local_ready = {name for name, spec in self.config["actions"].items() if now - self.last_action_at.get(name, -1e9) >= spec.get("cooldown", 0)}
        return {name for name in local_ready if visual_ready.get(name, True)}

    def _rate_ok(self, now: float) -> bool:
        limit = self.config["runtime"]["max_actions_per_minute"]
        while self.action_times and now - self.action_times[0] > 60:
            self.action_times.popleft()
        return len(self.action_times) < limit

    def _execute(self, action: str, image, now: float, state, decision) -> None:
        if self.config["runtime"].get("dry_run", True):
            if self.config["actions"][action]["kind"] == "drag":
                source, target = self._drag_points(action, image, state, decision.target)
                log.info("[dry-run] 拖拽 %s: %s -> %s", self.config["actions"][action]["label"], source, target)
            else:
                x, y = self._point(action, image)
                log.info("[dry-run] 点击 %s -> (%d,%d)", self.config["actions"][action]["label"], x, y)
        elif self.config["actions"][action]["kind"] == "drag":
            source, target = self._drag_points(action, image, state, decision.target)
            duration = self.config["actions"][action].get("duration_ms", 420)
            self.adb.swipe(source[0], source[1], target[0], target[1], duration)
            log.info("拖拽 %s: %s -> %s", self.config["actions"][action]["label"], source, target)
        else:
            x, y = self._point(action, image)
            self.adb.tap(x, y)
            log.info("点击 %s", self.config["actions"][action]["label"])
        self.last_action_at[action] = now
        self.action_times.append(now)

    def run(self) -> None:
        log.info("开始运行，dry_run=%s，按 Ctrl+C 停止", self.config["runtime"].get("dry_run", True))
        try:
            while True:
                loop_start = time.monotonic()
                image = self.adb.screenshot()
                elapsed = loop_start - self.started_at
                state = self.vision.read(image, elapsed)
                state.visual_ready = self.vision.visual_ready(image)
                now = time.monotonic()
                ready = self._ready(now, state.visual_ready)
                ready_books = ",".join(name for name in ("shigandang", "xuanshuiping", "qingnv", "volcano_book", "wind_book") if name in ready) or "无"
                decision = self.policy.choose(state, ready)
                log.info("血量=%.2f 符能=%.2f 符咒槽=%.0f%% 满=%s 地面=%d 空中=%d 精英=%d 首领=%d 可用天书=%s | %s (%s)", state.base_hp, state.energy, state.spell_fill * 100, state.spell_full, state.ground_count, state.air_count, state.elite_count, state.boss_count, ready_books, decision.action or "等待", decision.reason)
                self._record(state, decision, ready, now)
                if decision.action and self._rate_ok(now):
                    self._execute(decision.action, image, now, state, decision)
                    self._record(state, decision, ready, now, event="action")
                time.sleep(max(0.02, self.config["runtime"]["loop_interval_seconds"] - (time.monotonic() - loop_start)))
        except KeyboardInterrupt:
            log.info("已停止")
