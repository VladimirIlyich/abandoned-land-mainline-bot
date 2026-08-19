import logging
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

    def _point(self, name: str, image) -> tuple[int, int]:
        x, y = self.config["screen"]["buttons"][name]
        return int(x * image.width), int(y * image.height)

    def _ready(self, now: float, visual_ready: dict[str, bool]) -> set[str]:
        local_ready = {name for name, spec in self.config["actions"].items() if now - self.last_action_at.get(name, -1e9) >= spec.get("cooldown", 0)}
        return {name for name in local_ready if visual_ready.get(name, True)}

    def _rate_ok(self, now: float) -> bool:
        limit = self.config["runtime"]["max_actions_per_minute"]
        while self.action_times and now - self.action_times[0] > 60:
            self.action_times.popleft()
        return len(self.action_times) < limit

    def _execute(self, action: str, image, now: float) -> None:
        x, y = self._point(action, image)
        if self.config["runtime"].get("dry_run", True):
            log.info("[dry-run] %s -> (%d,%d)", self.config["actions"][action]["label"], x, y)
        elif self.config["actions"][action]["kind"] == "drag":
            self.adb.swipe(x, y, int(image.width * 0.52), int(image.height * 0.47), 280)
            log.info("拖拽 %s", self.config["actions"][action]["label"])
        else:
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
                log.info("血量=%.2f 符能=%.2f 符咒槽=%.0f%% 满=%s 地面=%d 空中=%d 首领=%d 可用天书=%s | %s (%s)", state.base_hp, state.energy, state.spell_fill * 100, state.spell_full, state.ground_count, state.air_count, state.boss_count, ready_books, decision.action or "等待", decision.reason)
                if decision.action and self._rate_ok(now):
                    self._execute(decision.action, image, now)
                time.sleep(max(0.02, self.config["runtime"]["loop_interval_seconds"] - (time.monotonic() - loop_start)))
        except KeyboardInterrupt:
            log.info("已停止")
