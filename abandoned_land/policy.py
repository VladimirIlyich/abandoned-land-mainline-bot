from dataclasses import dataclass
from .vision import GameState


@dataclass
class Decision:
    action: str | None
    reason: str


class MainlinePolicy:
    """按波次和威胁类型分配控制、输出与符能。

    这里故意不追求固定脚本，而是每帧从四种节奏中选一个：积攒、地面控场、
    空中处理、首领爆发。这样遇到随机刷怪时，不会因为固定秒表把技能交空。
    """

    def __init__(self, config: dict):
        self.cfg = config["strategy"]

    def choose(self, state: GameState, ready: set[str]) -> Decision:
        if not ready:
            return Decision(None, "没有可用技能")

        if state.spell_full and "ordinary_spell" in ready:
            return Decision("ordinary_spell", f"符咒槽已满({state.spell_fill:.0%})，先清槽让新符咒继续生成")

        if state.total_enemies == 0:
            return Decision(None, "场上没有目标，不提前交技能")

        emergency = state.base_hp <= self.cfg["emergency_base_hp"]
        danger = state.base_hp <= self.cfg["danger_base_hp"]
        air_heavy = state.air_count >= self.cfg["air_count_threshold"] or state.air_ratio >= self.cfg["air_ratio_threshold"]

        if emergency:
            for action in ("xuanshuiping", "qingnv", "wind_book", "volcano_book", "shigandang"):
                if action in ready:
                    return Decision(action, "基地危险，优先保命与拖延")

        if air_heavy:
            for action in ("wind_book", "volcano_book", "xuanshuiping", "qingnv"):
                if action in ready:
                    return Decision(action, "空中单位较多，跳过石敢当，优先对空或全屏拖延")

        if state.elite_count + state.boss_count >= self.cfg["boss_count"]:
            # 先冻住/拖住，再把火山落在首领脚下；石敢当只作无青女时的打断。
            for action in ("ghost_skill", "qingnv", "volcano_book", "shigandang", "xuanshuiping", "wind_book"):
                if action in ready:
                    return Decision(action, "精英/首领窗口：优先鬼仆，再控制和输出")

        if state.ground_count >= self.cfg["ground_control_count"]:
            for action in ("shigandang", "xuanshuiping", "qingnv"):
                if action in ready:
                    return Decision(action, "地面怪达到控场数量，建立控制覆盖")

        if danger and "xuanshuiping" in ready:
            return Decision("xuanshuiping", "基地进入危险区，先拖延")

        early_tank = state.elapsed_seconds < self.cfg["early_game_seconds"] and state.base_hp >= self.cfg["early_game_base_hp_floor"]
        small_ground_pack = state.ground_count < self.cfg["early_game_ground_count_to_control"]
        if early_tank and small_ground_pack and state.energy < self.cfg["min_energy_to_spend"] / 100:
            return Decision(None, "前期允许掉血，符能未到释放线")

        if "ordinary_spell" in ready and state.energy >= self.cfg["min_energy_to_spend"] / 100:
            return Decision("ordinary_spell", "符能达到释放线")
        return Decision(None, "当前保留资源，等待更高价值目标")
