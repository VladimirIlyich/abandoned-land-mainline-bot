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


if __name__ == "__main__":
    unittest.main()
