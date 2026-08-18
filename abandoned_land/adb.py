import subprocess
from pathlib import Path


class AdbController:
    def __init__(self, device: str | None = None):
        self.device = device

    def _base(self) -> list[str]:
        args = ["adb"]
        if self.device:
            args += ["-s", self.device]
        return args

    def _run(self, *args: str, binary: bool = False):
        result = subprocess.run(self._base() + list(args), check=True, capture_output=True)
        return result.stdout if binary else result.stdout.decode("utf-8", errors="replace")

    def devices(self) -> list[str]:
        output = self._run("devices")
        return [line.split("\t", 1)[0] for line in output.splitlines()[1:] if "\tdevice" in line]

    def screenshot(self):
        from PIL import Image
        from io import BytesIO
        return Image.open(BytesIO(self._run("exec-out", "screencap", "-p", binary=True))).convert("RGB")

    def save_screenshot(self, path: str) -> None:
        self.screenshot().save(path)

    def tap(self, x: int, y: int) -> None:
        self._run("shell", "input", "tap", str(x), str(y))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._run("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))
