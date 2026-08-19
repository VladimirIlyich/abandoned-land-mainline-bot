from dataclasses import dataclass
from .vision import GameState


@dataclass
class Decision:
    action: str | None
    reason: str
    target: str | None = None
    spell_type: str | None = None


class MainlinePolicy:
    """按波次和威胁类型分配控制、输出与符能。

    这里故意不追求固定脚本，而是每帧从四种节奏中选一个：积攒、地面控场、
    空中处理、首领爆发。这样遇到随机刷怪时，不会因为固定秒表把技能交空。
    """

    def __init__(self, config: dict):
        self.cfg = config["strategy"]
        enabled = self.cfg.get("enabled_actions")
        # 旧配置没有 enabled_actions 时，保留原来的“所有 actions 可用”行为。
        self.enabled_actions = set(enabled) if enabled else None

    def choose(self, state: GameState, ready: set[str]) -> Decision:
        if self.enabled_actions is not None:
            ready = ready & self.enabled_actions
        if not ready:
            return Decision(None, "没有可用技能")

        spell_type = self._spell_type(state)

        if state.spell_full and "ordinary_spell" in ready:
            return Decision("ordinary_spell", f"符咒槽已满({state.spell_fill:.0%})，先清槽让新符咒继续生成", "ground", spell_type)

        if state.total_enemies == 0:
            return Decision(None, "场上没有目标，不提前交技能")

        emergency = state.base_hp <= self.cfg["emergency_base_hp"]
        danger = state.base_hp <= self.cfg["danger_base_hp"]
        air_heavy = state.air_count >= self.cfg["air_count_threshold"] or state.air_ratio >= self.cfg["air_ratio_threshold"]

        if emergency:
            for action in ("xuanshuiping", "qingnv", "wind_book", "volcano_book", "shigandang"):
                if action in ready:
                    return Decision(action, "基地危险，优先保命与拖延", "ground")

        if air_heavy:
            for action in ("wind_book", "volcano_book", "xuanshuiping", "qingnv"):
                if action in ready:
                    return Decision(action, "空中单位较多，跳过石敢当，优先对空或全屏拖延", "air")

        if state.elite_count + state.boss_count >= self.cfg["boss_count"]:
            # 先冻住/拖住，再把火山落在首领脚下；石敢当只作无青女时的打断。
            for action in ("ghost_skill", "qingnv", "volcano_book", "shigandang", "xuanshuiping", "wind_book"):
                if action in ready:
                    return Decision(action, "精英/首领窗口：优先鬼仆，再控制和输出", "elite")

        if state.ground_count >= self.cfg["ground_control_count"]:
            for action in ("shigandang", "xuanshuiping", "qingnv"):
                if action in ready:
                    return Decision(action, "地面怪达到控场数量，建立控制覆盖", "ground")

        if danger and "xuanshuiping" in ready:
            return Decision("xuanshuiping", "基地进入危险区，先拖延", "ground")

        safe_to_tank = (
            state.base_hp >= self.cfg["early_game_base_hp_floor"]
            and state.base_hp > self.cfg["danger_base_hp"]
            and state.elite_count + state.boss_count == 0
            and not air_heavy
        )
        if safe_to_tank and state.energy < self.cfg["min_energy_to_spend"] / 100:
            return Decision(None, "血量安全且无精英/空中高压，允许卖血攒符能")

        if "ordinary_spell" in ready and state.energy >= self.cfg["min_energy_to_spend"] / 100:
            return Decision("ordinary_spell", "符能达到释放线", "ground", spell_type)
        return Decision(None, "当前保留资源，等待更高价值目标")

    def _spell_type(self, state: GameState) -> str:
        if state.base_hp <= self.cfg["danger_base_hp"]:
            return "freeze"
        if state.air_count >= self.cfg["air_count_threshold"] or state.air_ratio >= self.cfg["air_ratio_threshold"]:
            return "knockback"
        if state.ground_count >= self.cfg["ground_control_count"]:
            return "stun"
        return "damage"
