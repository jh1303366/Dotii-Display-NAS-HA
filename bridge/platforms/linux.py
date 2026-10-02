"""Headless Linux/NAS services; hardware provisioning stays on a desktop."""
from __future__ import annotations
import os
from pathlib import Path

class LinuxPlatformAdapter:
    name = "linux"
    startup_available = False
    bluetooth_available = False
    bluetooth_pair_on_connect = False
    serial_flash_available = False

    def runtime_folder(self) -> Path:
        configured = os.environ.get("DOTII_RUNTIME_DIR")
        if configured:
            if not Path(configured).is_absolute():
                raise ValueError("DOTII_RUNTIME_DIR must be absolute")
            return Path(configured)
        return Path.home() / ".local" / "share" / "Dotii"

    def hidden_creation_flags(self) -> int:
        return 0

    def startup_command(self, python_executable: Path, app_script: Path) -> str:
        raise OSError("NAS 自启动请通过 Docker 重启策略设置")

    def packaged_startup_command(self, management_center: Path) -> str:
        raise OSError("NAS 自启动请通过 Docker 重启策略设置")

    def current_startup_command(self, **kwargs) -> str:
        raise OSError("NAS 自启动请通过 Docker 重启策略设置")

    def startup_enabled(self) -> bool:
        return False

    def set_startup(self, enabled: bool, command: str) -> bool:
        raise OSError("NAS 自启动请通过 Docker 重启策略设置")

    def ffmpeg_candidates(self, runtime_folder: Path, tools_root: Path) -> list[Path]:
        return [runtime_folder / "tools/ffmpeg/bin/ffmpeg", tools_root / "ffmpeg/bin/ffmpeg", Path("/usr/bin/ffmpeg")]

    def codex_cli_candidates(self, runtime_folder: Path, application_root: Path) -> list[Path]:
        return [runtime_folder / "codex-cli/node_modules/@openai/codex/bin/codex.js", Path("/usr/local/bin/codex"), Path("/usr/bin/codex")]

    def bundled_node_candidates(self, application_root: Path) -> list[Path]:
        return [Path("/usr/local/bin/node"), Path("/usr/bin/node")]

    def esptool_python_candidates(self) -> list[Path]:
        return []

    def scan_serial_ports(self, run) -> list[dict[str, object]]:
        return []

    def valid_serial_port(self, port: str) -> bool:
        return False
