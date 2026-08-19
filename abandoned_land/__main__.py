import argparse
import logging
from pathlib import Path

from .adb import AdbController
from .runner import Runner
from .vision import Vision


def load_config(path: str) -> dict:
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_config(config: dict) -> None:
    required = {
        "runtime": ("loop_interval_seconds", "max_actions_per_minute"),
        "strategy": ("air_ratio_threshold", "ground_control_count"),
        "screen": ("playfield", "buttons", "enemy_colors"),
        "actions": (),
    }
    missing = [section for section, keys in required.items() if section not in config or any(key not in config[section] for key in keys)]
    if missing:
        raise SystemExit("配置缺少必要字段：" + ", ".join(missing))
    if not config["actions"]:
        raise SystemExit("配置至少需要一个 actions 技能")


def apply_profile(config: dict, profile_name: str | None) -> None:
    profile_name = profile_name or config.get("strategy", {}).get("active_profile")
    if not profile_name:
        return
    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        raise SystemExit(f"找不到天书配置档：{profile_name}。可用配置档：{', '.join(profiles) or '无'}")
    config["strategy"]["active_profile"] = profile_name
    config["strategy"]["enabled_actions"] = profiles[profile_name]["actions"]


def main() -> None:
    parser = argparse.ArgumentParser(description="遗弃之地主线推关助手")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--profile", help="入关前使用的天书配置档，例如 ground/air/boss")
    args = parser.parse_args()

    adb = AdbController()
    if args.list_devices:
        print("\n".join(adb.devices()) or "没有发现设备")
        return

    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"找不到配置文件：{config_path}。请先复制 config.example.yaml")
    config = load_config(str(config_path))
    validate_config(config)
    apply_profile(config, args.profile)
    adb = AdbController(device=config.get("device"), adb_path=config.get("adb_path"))
    logging.basicConfig(level=getattr(logging, config["runtime"].get("log_level", "INFO")))

    if args.calibrate:
        adb.save_screenshot("calibration.png")
        print("已保存 calibration.png，请据此修改 config.yaml 中的相对坐标。")
        return
    if args.inspect:
        image = adb.screenshot()
        image.save("inspect.png")
        vision = Vision(config)
        state = vision.read(image, 0)
        ready = vision.visual_ready(image)
        print({
            "screenshot": "inspect.png",
            "battle_screen": state.battle_screen,
            "base_hp": round(state.base_hp, 3),
            "base_hp_valid": state.base_hp_valid,
            "energy": round(state.energy, 3),
            "energy_valid": state.energy_valid,
            "spell_fill": round(state.spell_fill, 3),
            "ground_count": state.ground_count,
            "air_count": state.air_count,
            "elite_count": state.elite_count,
            "boss_count": state.boss_count,
            "card_sources": state.card_sources,
            "ready_actions": sorted(name for name, is_ready in ready.items() if is_ready),
        })
        return

    Runner(config, adb).run()


if __name__ == "__main__":
    main()
