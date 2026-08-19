import unittest

from abandoned_land.runner import Runner
from abandoned_land.vision import GameState


class FakeImage:
    width = 1000
    height = 500


class RunnerTests(unittest.TestCase):
    def config(self):
        return {
            "runtime": {"dry_run": True, "max_actions_per_minute": 90},
            "strategy": {},
            "screen": {
                "buttons": {"ordinary_spell": [0.32, 0.83]},
                "default_drag_target": [0.52, 0.48],
                "spell_detection": {"enabled": True},
            },
            "actions": {
                "ordinary_spell": {"kind": "drag", "source": [0.32, 0.83], "target": [0.52, 0.48]}
            },
        }

    def test_ordinary_spell_uses_available_card_when_requested_type_missing(self):
        runner = Runner(self.config(), object())
        state = GameState(1, 1, 0, 0, 0, 0, card_sources={"freeze": [0.47, 0.83]})
        source, target = runner._drag_points("ordinary_spell", FakeImage(), state, "ground", "stun")
        self.assertEqual(source, (470, 415))
        self.assertEqual(target, (520, 240))


if __name__ == "__main__":
    unittest.main()
