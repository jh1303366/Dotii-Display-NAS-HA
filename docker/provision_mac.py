"""Start the desktop BLE helper with the preconfigured NAS URL and token."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request

if sys.version_info < (3, 11):
    raise SystemExit("请先安装 Python 3.11 或以上，再运行 Mac 配网助手")

root = Path(__file__).resolve().parents[1]
os.chdir(root)
config_path = root / ".env"
if not config_path.is_file():
    raise SystemExit("缺少 .env，请使用包含配置的完整部署包")
config = dict(line.split("=", 1) for line in config_path.read_text().splitlines() if line and not line.startswith("#") and "=" in line)
if not config.get("STATE_DISPLAY_BRIDGE_TOKEN") or not config.get("DOTII_PUBLIC_URL"):
    raise SystemExit(".env 缺少 NAS 地址或设备令牌")
python = root / ".venv" / "bin" / "python"
if not python.exists():
    subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True)
subprocess.run([str(python), "-m", "pip", "install", "-r", "requirements-desktop.txt"], check=True)
env = {**os.environ, "DOTII_PUBLIC_URL": config["DOTII_PUBLIC_URL"], "STATE_DISPLAY_BRIDGE_TOKEN": config["STATE_DISPLAY_BRIDGE_TOKEN"]}
env.pop("DOTII_ADMIN_PASSWORD", None)
env.pop("DOTII_RUNTIME_DIR", None)
port = 8788
# Refuse to reuse a different service on the helper's port.
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", port))
process = subprocess.Popen([str(python), "bridge/codex_bridge.py", "--host", "127.0.0.1", "--port", str(port)], env=env)
try:
    for _ in range(100):
        if process.poll() is not None:
            raise SystemExit("电脑配网后端启动失败，请检查上方日志")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1):
                break
        except OSError:
            time.sleep(.1)
    else:
        raise SystemExit("等待配网后端启动超时")
    print("NAS 地址和设备令牌已加载。请在设置页扫描 Dotii、填写 Wi-Fi 并保存；NAS 目标输入框可以留空。按 Ctrl+C 关闭配网助手。", flush=True)
    subprocess.run(["open", f"http://127.0.0.1:{port}"], check=True)
    process.wait()
except KeyboardInterrupt:
    pass
finally:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
