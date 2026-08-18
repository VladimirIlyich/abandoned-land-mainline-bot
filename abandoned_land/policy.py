from dataclasses import dataclass
from .vision import GameState


@dataclass
class Decision:
    action: str | None
    reason: str


class MainlinePolicy:
    """把资源分成保命、空中处理、地面控制和积攒四种节奏。"""

    def __init__(self, config: dict):
        self.cfg = config["strategy"]

    def choose(self, state: GameState, ready: set[str]) -> Decision:
        if not ready:
            return Decision(None, "没有可用技能")

        emergency = state.base_hp <= self.cfg["emergency_base_hp"]
        danger = state.base_hp <= self.cfg["danger_base_hp"]
        air_heavy = state.air_count >= self.cfg["air_count_threshold"] or state.air_ratio >= self.cfg["air_ratio_threshold"]

        if emergency:
            for action in ("qingnv", "xuanshuiping", "wind_book", "volcano_book", "shigandang"):
                if action in ready:
                    return Decision(action, "基地危险，优先保命与拖延")

        if air_heavy:
            for action in ("wind_book", "volcano_book", "xuanshuiping", "qingnv"):
                if action in ready:
                    return Decision(action, "空中单位较多，跳过石敢当")

        if state.boss_count >= self.cfg["boss_count"]:
            for action in ("shigandang", "xuanshuiping", "qingnv", "volcano_book", "wind_book"):
                if action in ready:
                    return Decision(action, "精英或首领出现，集中控制")

        if state.ground_count >= self.cfg["ground_control_count"]:
            for action in ("shigandang", "xuanshuiping", "qingnv"):
                if action in ready:
                    return Decision(action, "地面怪达到控场数量")

        if danger and "xuanshuiping" in ready:
            return Decision("xuanshuiping", "基地进入危险区，先拖延")

        early_tank = state.elapsed_seconds < self.cfg["early_game_seconds"] and state.base_hp >= self.cfg["early_game_base_hp_floor"]
        if early_tank and state.energy < self.cfg["min_energy_to_spend"] / 100:
            return Decision(None, "前期允许掉血，符能未到释放线")

        if "ordinary_spell" in ready and state.energy >= self.cfg["min_energy_to_spend"] / 100:
            return Decision("ordinary_spell", "符能达到释放线")
        return Decision(None, "当前保留资源，等待更高价值目标")
