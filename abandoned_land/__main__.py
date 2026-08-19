import argparse
import logging
from pathlib import Path

from .adb import AdbController
from .runner import Runner


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
    logging.basicConfig(level=getattr(logging, config["runtime"].get("log_level", "INFO")))

    if args.calibrate:
        adb.save_screenshot("calibration.png")
        print("已保存 calibration.png，请据此修改 config.yaml 中的相对坐标。")
        return
    if args.inspect:
        adb.save_screenshot("inspect.png")
        print("已保存 inspect.png。当前版本识别结果需要在运行日志中查看。")
        return

    Runner(config, adb).run()


if __name__ == "__main__":
    main()
