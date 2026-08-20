import unittest

try:
    from PIL import Image, ImageDraw
    from abandoned_land.vision import Vision, _red_bar_stats
    VISION_DEPS_AVAILABLE = True
except ModuleNotFoundError:
    VISION_DEPS_AVAILABLE = False


@unittest.skipUnless(VISION_DEPS_AVAILABLE, "需要 Pillow 和 OpenCV 才能运行视觉测试")
class VisionTests(unittest.TestCase):
    def test_long_red_enemy_bar_is_detected_as_special_target(self):
        image = Image.new("RGB", (1000, 500), (150, 130, 160))
        ImageDraw.Draw(image).rectangle((380, 220, 650, 232), fill=(220, 25, 25))
        count, position = _red_bar_stats(image, [0.0, 0.0, 1.0, 1.0])
        self.assertEqual(count, 1)
        self.assertIsNotNone(position)
        self.assertAlmostEqual(position[0], 0.515, places=2)

    def test_dark_mode_exposes_special_target_to_policy(self):
        image = Image.new("RGB", (1000, 500), (150, 130, 160))
        ImageDraw.Draw(image).rectangle((380, 220, 650, 232), fill=(220, 25, 25))
        config = {
            "screen": {
                "playfield": [0.0, 0.0, 1.0, 1.0],
                "enemy_colors": {"ground": [[0, 60, 50], [35, 255, 255]], "air": [[90, 40, 50], [140, 255, 255]], "boss": [[140, 40, 50], [179, 255, 255]], "elite": [[140, 40, 50], [179, 255, 255]]},
                "enemy_detection": {"enabled": True, "mode": "dark_entities", "max_total_enemies": 24},
                "spell_detection": {"enabled": False},
                "base_hp_roi": [0, 0, 0.1, 0.1],
                "energy_roi": [0, 0, 0.1, 0.1],
                "base_hp_detection": {"enabled": False},
                "energy_detection": {"enabled": False},
            }
        }
        state = Vision(config).read(image, 0)
        self.assertEqual(state.elite_count, 1)
        self.assertIsNotNone(state.elite_position)


if __name__ == "__main__":
    unittest.main()
