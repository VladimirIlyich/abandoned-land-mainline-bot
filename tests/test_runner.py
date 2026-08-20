import unittest

from abandoned_land.runner import Runner
from abandoned_land.vision import GameState


class FakeImage:
    width = 1000
    height = 500


class RunnerTests(unittest.TestCase):
    def config(self):
        return {
            "runtime": {"dry_run": True, "max_actions_per_minute": 90, "initial_release_mode": "book"},
            "strategy": {},
            "screen": {
                "buttons": {"ordinary_spell": [0.32, 0.83]},
                "mode_toggle_button": [0.07, 0.85],
                "default_drag_target": [0.52, 0.48],
                "spell_detection": {"enabled": True},
            },
            "actions": {
                "ordinary_spell": {"kind": "drag", "release_mode": "spell", "source": [0.32, 0.83], "target": [0.52, 0.48]}
            },
        }

    def test_ordinary_spell_uses_available_card_when_requested_type_missing(self):
        runner = Runner(self.config(), object())
        state = GameState(1, 1, 0, 0, 0, 0, card_sources={"freeze": [0.47, 0.83]})
        source, target = runner._drag_points("ordinary_spell", FakeImage(), state, "ground", "stun")
        self.assertEqual(source, (470, 415))
        self.assertEqual(target, (520, 240))
        self.assertEqual(runner.release_mode, "book")

    def test_release_mode_is_inferred_from_action(self):
        runner = Runner(self.config(), object())
        self.assertEqual(runner._required_release_mode("ordinary_spell"), "spell")


if __name__ == "__main__":
    unittest.main()
