import unittest
from abandoned_land.policy import MainlinePolicy
from abandoned_land.vision import GameState


CFG = {"strategy": {
    "air_ratio_threshold": 0.35, "air_count_threshold": 3,
    "min_energy_to_spend": 35, "reserve_energy": 25,
    "emergency_base_hp": 0.28, "danger_base_hp": 0.50,
    "early_game_seconds": 30, "early_game_base_hp_floor": 0.42,
    "early_game_ground_count_to_control": 7, "ground_control_count": 4,
    "delay_count": 3, "boss_count": 1,
}}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = MainlinePolicy(CFG)

    def state(self, **changes):
        data = dict(base_hp=.8, energy=.2, ground_count=0, air_count=0, boss_count=0, elapsed_seconds=10)
        data.update(changes)
        return GameState(**data)

    def test_air_heavy_skips_shigandang(self):
        d = self.policy.choose(self.state(air_count=4), {"shigandang", "wind_book"})
        self.assertEqual(d.action, "wind_book")

    def test_ground_group_uses_shigandang(self):
        d = self.policy.choose(self.state(ground_count=5), {"shigandang", "wind_book"})
        self.assertEqual(d.action, "shigandang")

    def test_early_low_energy_tanks(self):
        d = self.policy.choose(self.state(ground_count=2), {"ordinary_spell"})
        self.assertIsNone(d.action)

    def test_emergency_prefers_delay(self):
        d = self.policy.choose(self.state(base_hp=.2, ground_count=2), {"qingnv", "ordinary_spell"})
        self.assertEqual(d.action, "qingnv")

    def test_boss_freezes_before_damage_window(self):
        d = self.policy.choose(self.state(boss_count=1), {"qingnv", "volcano_book", "shigandang"})
        self.assertEqual(d.action, "qingnv")

    def test_empty_field_does_not_waste_skill(self):
        d = self.policy.choose(self.state(), {"shigandang", "ordinary_spell"})
        self.assertIsNone(d.action)

    def test_full_spell_slot_clears_before_enemy_logic(self):
        state = self.state(ground_count=0, spell_fill=.8, spell_full=True)
        d = self.policy.choose(state, {"ordinary_spell"})
        self.assertEqual(d.action, "ordinary_spell")

    def test_ghost_skill_is_reserved_for_elites(self):
        d = self.policy.choose(self.state(ground_count=5), {"ghost_skill", "shigandang"})
        self.assertEqual(d.action, "shigandang")
        d = self.policy.choose(self.state(elite_count=1), {"ghost_skill", "shigandang"})
        self.assertEqual(d.action, "ghost_skill")

    def test_safe_midwave_can_sell_hp_for_energy(self):
        d = self.policy.choose(self.state(elapsed_seconds=90, ground_count=2, energy=.2), {"ordinary_spell"})
        self.assertIsNone(d.action)


if __name__ == "__main__":
    unittest.main()
