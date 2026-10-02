"""Require browser credentials before exposing a container on the LAN."""
import os
import sys
password = os.environ.get("DOTII_ADMIN_PASSWORD", "")
if len(password) < 12 or password == "change-this-password":
    raise SystemExit("请设置至少 12 位 DOTII_ADMIN_PASSWORD，然后重新启动容器")
if not os.environ.get("DOTII_PUBLIC_URL"):
    raise SystemExit("请设置 DOTII_PUBLIC_URL 为 NAS 的局域网地址和访问端口")
user = os.environ.get("DOTII_ADMIN_USER", "admin")
if not user or ":" in user or any(c in user + password for c in "\r\n"):
    raise SystemExit("管理用户名/密码格式无效")
os.umask(0o077)
from pathlib import Path
codex_home = Path(os.environ.get("CODEX_HOME", "/data/.codex"))
codex_home.mkdir(parents=True, exist_ok=True)
config = codex_home / "config.toml"
if not config.exists():
    config.write_text('cli_auth_credentials_store = "file"\n')
os.execv(sys.executable, [sys.executable, "bridge/codex_bridge.py", "--host", "0.0.0.0", "--app-server", "--app-server-interval", "30", *sys.argv[1:]])
