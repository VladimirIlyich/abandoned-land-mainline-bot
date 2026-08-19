# 遗弃之地主线推关助手

这是一个面向安卓手机抖音小游戏的屏幕识别 + ADB 点击/拖拽原型。它只通过手机截图和触控输入工作，不读取游戏进程、不修改内存、不抓包。

## 运行

1. 安装 Python 3.11+ 和 Android Platform Tools，把 `adb` 放进 PATH。
2. 手机打开开发者选项与 USB 调试，并允许这台电脑调试。
3. 安装依赖：

```powershell
python -m pip install -r requirements.txt
```

如果 `adb devices` 只能用绝对路径执行，请在 `config.yaml` 中将 `adb_path` 改为 Android Platform Tools 里的 `adb.exe` 完整路径；无线设备也可以将 `device` 填成 `192.168.1.75:37951`，避免误选离线模拟器。

4. 连接手机并确认：

```powershell
adb devices
python -m abandoned_land --list-devices
```

5. 复制配置并校准：

```powershell
Copy-Item config.example.yaml config.yaml
python -m abandoned_land --calibrate
```

6. 默认是观察模式，只打印将要执行的动作：

```powershell
python -m abandoned_land --config config.yaml
```

确认日志、按钮坐标和模板识别都正确后，把 `runtime.dry_run` 改为 `false`。

进入关卡前先在游戏内装备与关卡匹配的天书，然后选择对应配置档：

```powershell
python -m abandoned_land --config config.yaml --profile ground
python -m abandoned_land --config config.yaml --profile air
python -m abandoned_land --config config.yaml --profile boss
```

配置档只限制战斗中允许释放的天书，不会在游戏内替换装备。普通符咒会从截图中动态寻找当前可见卡牌，按颜色识别爆发、冰冻、眩晕和击退类型，再拖到检测到的怪物位置；因此卡牌数量变化时不依赖固定槽位。

## 当前战术

- 地面怪为主：石敢当天书优先控场；玄水瓶和青女负责拖延。
- 空中威胁达到阈值：跳过石敢当，改用火山或风系天书。
- 前期小怪：默认允许基地掉血，符能低于保留线时不浪费普通符咒。
- 精英/BOSS 或基地危险：临时提高技能优先级，先保命，再恢复积攒节奏。
- 所有坐标、颜色区域、技能按钮和天书按钮都在 YAML 中可调。

更完整的无红天书推关规律见 [GUIDE.md](GUIDE.md)，里面记录了参考视频、卡秒思路、首领窗口和空中波次处理。

不同手机分辨率、刘海区域和小游戏 UI 位置会不同；没有一张你的实机截图，识别区域只能先用相对坐标模板，首次运行请先保持 `dry_run: true`。

## 目录

- `abandoned_land/adb.py`：截图和触控输入
- `abandoned_land/vision.py`：状态识别
- `abandoned_land/policy.py`：推关策略
- `abandoned_land/runner.py`：主循环、节流、急停
- `config.example.yaml`：配置样例
- `tests/`：策略测试

## 安全边界

这是实验性质的 UI 自动化工具。请确认使用符合游戏规则和抖音平台规则。不要在支付、抽卡、账号登录等界面运行；运行时保留手机实体急停方式，按 `Ctrl+C` 可停止。
