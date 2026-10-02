"""NAS device-code login through the official Codex app-server protocol."""
from __future__ import annotations
import queue
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from codex_app_server import AppServerClient, AppServerError, _resolve_codex_command

class CodexAuthService:
    def __init__(self, runtime: Path, cwd: Path, command: str | None, on_login) -> None:
        self.runtime, self.cwd, self.command = runtime, cwd, command
        self.on_login = on_login
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.status = dict(available=True, state="idle", detail="在 NAS 登录 Codex 后可独立读取额度。", verification_url="", user_code="")

    def snapshot(self) -> dict:
        with self.lock:
            return dict(self.status)

    def _update(self, **values) -> None:
        with self.lock:
            self.status.update(values)

    def start(self, *, login: bool) -> bool:
        with self.lock:
            if self.worker and self.worker.is_alive():
                return False
            self.cancel_event.clear()
            self.status.update(state="starting", detail="正在连接官方账号服务…", verification_url="", user_code="")
            self.worker = threading.Thread(target=self._run, args=(login,), name="codex-login", daemon=True)
            self.worker.start()
        return True

    def cancel(self) -> None:
        self.cancel_event.set()

    def stop(self) -> None:
        self.cancel()
        if self.worker:
            self.worker.join(timeout=2)

    def _run(self, login: bool) -> None:
        client = None
        try:
            command = _resolve_codex_command(self.command, self.runtime)
            client = AppServerClient(command, self.cwd, timeout=30)
            client.start()
            if not login:
                account = client.request("account/read", {"refreshToken": False})
                info = account.get("account") if isinstance(account, dict) else None
                linked = isinstance(info, dict) and info.get("type") == "chatgpt"
                self._update(state="logged_in" if linked else "logged_out", detail="NAS 已保存 Codex 登录状态。" if linked else "请点击登录 Codex，在官方页面授权此 NAS。")
                return
            if self.cancel_event.is_set():
                self._update(state="cancelled", detail="已取消登录。")
                return
            result = client.request("account/login/start", {"type": "chatgptDeviceCode"})
            url = str(result.get("verificationUrl") or "")
            code = str(result.get("userCode") or "")
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in {"auth.openai.com", "chatgpt.com"} or parsed.username or parsed.password or not code or len(code) > 64:
                raise ValueError("官方登录服务返回了无法识别的授权信息")
            self._update(state="waiting", detail="请打开官方授权页，输入验证码并登录你要显示额度的账号。", verification_url=url, user_code=code)
            deadline = time.monotonic() + 600
            while not self.cancel_event.is_set() and time.monotonic() < deadline:
                try:
                    event = client.notifications.get(timeout=.5)
                except queue.Empty:
                    if client.process is not None and client.process.poll() is not None:
                        raise AppServerError("登录服务已退出，请重新登录")
                    continue
                if event.get("method") != "account/login/completed":
                    continue
                params = event.get("params") or {}
                if params.get("loginId") != result.get("loginId"):
                    continue
                if not params.get("success"):
                    raise AppServerError("账号授权未完成，请重新登录并检查网络")
                self._update(state="logged_in", detail="Codex 授权成功，NAS 将自动更新额度。", verification_url="", user_code="")
                self.on_login()
                return
            try:
                client.request("account/login/cancel", {"loginId": result.get("loginId")})
            except (AppServerError, OSError):
                pass
            self._update(state="cancelled" if self.cancel_event.is_set() else "expired", detail="登录已取消，请重新开始。" if self.cancel_event.is_set() else "等待授权超时，请重新生成验证码。", verification_url="", user_code="")
        except (AppServerError, OSError, ValueError, TypeError) as error:
            # Keep tokens, response bodies, and sensitive auth errors out of the UI.
            detail = "账号服务连接失败，请检查 NAS 是否能访问 OpenAI，或稍后重新登录。"
            if "未找到" in str(error):
                detail = "未找到 Codex 运行组件，请检查镜像安装。"
            self._update(state="error", detail=detail, verification_url="", user_code="")
        finally:
            if client:
                client.close()
