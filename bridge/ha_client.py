"""Small Home Assistant REST bridge. Credentials never enter device snapshots."""
from __future__ import annotations

import copy
import json
import math
import os
import re
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

DOMAINS = {"sensor", "binary_sensor", "light", "switch", "fan", "climate", "weather", "vacuum"}
MAX_ENTITIES = 32


def entity_role(entity_id, attrs):
    roles = {
        "sensor.tesla_battery_level": "vehicle_battery", "sensor.tesla_rated_battery_range": "vehicle_range",
        "sensor.tesla_inside_temp": "vehicle_temperature", "binary_sensor.tesla_locked": "vehicle_lock",
        "sensor.tesla_charging_state": "vehicle_charging", "sensor.tesla_state": "vehicle_status",
        "sensor.p20_pro_battery": "vacuum_battery", "sensor.nas_cpufu_zai": "nas_cpu",
        "sensor.nasnei_cun_shi_yong_lu": "nas_memory", "sensor.naswen_du": "nas_temperature",
    }
    return roles.get(entity_id, attrs.get("device_class", entity_id.split(".")[0]))


def entity_actions(domain, attrs, available):
    if not available: return []
    if domain == "vacuum":
        bits = int(attrs.get("supported_features", 0))
        return [name for name, mask in [("start", 8192), ("pause", 4), ("stop", 8), ("return_to_base", 16)] if bits & mask]
    if domain in {"light", "switch", "fan"}:
        actions = ["turn_on", "turn_off"]
        if domain == "light" and any(m not in {"onoff", "unknown"} for m in attrs.get("supported_color_modes", [])):
            actions.append("brightness")
        if domain == "fan" and int(attrs.get("supported_features", 0)) & 1: actions.append("percentage")
        return actions
    if domain == "climate": return ["mode"] + (["temperature"] if attrs.get("temperature") is not None else [])
    return []


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


class HAConfigStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()

    def read(self):
        with self.lock:
            if not self.path.exists():
                return {"url": "", "token": "", "entities": [], "revision": 0}
            return json.loads(self.path.read_text(encoding="utf-8"))

    def public(self):
        config = self.read()
        return {k: v for k, v in config.items() if k != "token"} | {"token_configured": bool(config["token"])}

    def write(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("配置格式不正确")
        with self.lock:
            old = self.read()
            url = str(payload.get("url", old["url"])).strip().rstrip("/")
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path or any(c.isspace() for c in url):
                raise ValueError("请填写 HA 地址，例如 http://192.168.1.12:8123")
            try:
                parsed.port
            except ValueError:
                raise ValueError("HA 端口不正确") from None
            token = payload.get("token") or old["token"]
            if not isinstance(token, str) or not token or len(token) > 4096 or any(c.isspace() for c in token):
                raise ValueError("请填写有效的 HA 长期访问令牌")
            if url != old["url"] and not payload.get("token") and old["url"]:
                raise ValueError("更换 HA 地址时需要重新填写令牌")
            entities = payload.get("entities", old["entities"])
            if not isinstance(entities, list) or len(entities) > MAX_ENTITIES:
                raise ValueError("最多选择 32 个实体")
            clean, seen = [], set()
            for item in entities:
                if not isinstance(item, dict):
                    raise ValueError("实体配置格式不正确")
                entity_id = item.get("entity_id", "")
                if not isinstance(entity_id, str) or not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", entity_id) or entity_id.split(".")[0] not in DOMAINS or len(entity_id) > 180 or entity_id in seen:
                    raise ValueError("实体重复或类型不支持")
                label = str(item.get("label", "")).strip()[:10]
                clean.append({"entity_id": entity_id, "label": label})
                seen.add(entity_id)
            config = {"url": url, "token": token, "entities": clean, "revision": old["revision"] + 1}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(config, stream, ensure_ascii=False)
            os.chmod(temp, 0o600)
            os.replace(temp, self.path)
            return self.public()


class HAService:
    def __init__(self, config: HAConfigStore, enabled=lambda: True):
        self.config = config
        self.enabled = enabled
        self.lock = threading.RLock()
        self.io_lock = threading.RLock()
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.cached = {"connected": False, "updated_at_epoch": 0, "revision": 0, "entities": [], "error": "尚未连接 HA", "command_note": ""}

    def request(self, config, path, body=None):
        req = Request(config["url"] + path, data=None if body is None else json.dumps(body).encode(),
                      headers={"Authorization": "Bearer " + config["token"], "Content-Type": "application/json"})
        try:
            with build_opener(NoRedirect).open(req, timeout=6) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise ValueError("HA 响应过大")
                return json.loads(raw)
        except HTTPError as error:
            raise ValueError("HA 令牌无效或已撤销" if error.code in {401, 403} else f"HA 请求失败（HTTP {error.code}）") from None
        except (URLError, TimeoutError, OSError):
            raise ValueError("连接 HA 失败，请检查网络和地址") from None
        except (UnicodeError, json.JSONDecodeError):
            raise ValueError("HA 返回了无效数据") from None

    def discover(self):
        config = self.config.read()
        if not config["token"]:
            raise ValueError("请先保存地址和访问令牌")
        with self.io_lock:
            states = self.request(config, "/api/states")
        if not isinstance(states, list):
            raise ValueError("HA 实体列表格式不正确")
        return [{"entity_id": x["entity_id"], "label": str(x.get("attributes", {}).get("friendly_name", x["entity_id"]))[:80],
                 "state": str(x.get("state", "unknown"))[:64]} for x in states
                if isinstance(x, dict) and str(x.get("entity_id", "")).split(".")[0] in DOMAINS]

    @staticmethod
    def entity(item, state, slot):
        attrs = state.get("attributes", {})
        domain = item["entity_id"].split(".")[0]
        value = str(state.get("state", "unavailable"))[:40]
        available = value not in {"unavailable", "unknown"}
        modes = [m for m in attrs.get("hvac_modes", []) if m in {"off", "cool", "heat", "auto", "dry", "fan_only", "heat_cool"}]
        return {"slot": slot, "entity_id": item["entity_id"], "label": item["label"] or str(attrs.get("friendly_name", item["entity_id"]))[:10],
                "domain": domain, "state": value, "available": available,
                "unit": str(attrs.get("unit_of_measurement", ""))[:8], "temperature": number(attrs.get("temperature")),
                "current_temperature": number(attrs.get("current_temperature")), "min_temp": number(attrs.get("min_temp")) or 16,
                "max_temp": number(attrs.get("max_temp")) or 30, "temp_step": max(number(attrs.get("target_temp_step")) or 1, 0.1),
                "hvac_modes": modes, "brightness": number(attrs.get("brightness")),
                "percentage": number(attrs.get("percentage")), "role": entity_role(item["entity_id"], attrs),
                "humidity": number(attrs.get("humidity")), "battery_level": number(attrs.get("battery_level")),
                "actions": entity_actions(domain, attrs, available)}

    def refresh(self):
        with self.io_lock:
            config = self.config.read()
            if not self.enabled() or not config["token"]:
                with self.lock:
                    self.cached.update(connected=False, revision=config["revision"], entities=[], error="页面已关闭" if not self.enabled() else "请先连接 HA")
                return
            try:
                states = self.request(config, "/api/states")
                if not isinstance(states, list):
                    raise ValueError("HA 实体列表格式不正确")
                mapping = {x.get("entity_id"): x for x in states if isinstance(x, dict)}
                entities = [self.entity(item, mapping.get(item["entity_id"], {"state": "unavailable"}), slot) for slot, item in enumerate(config["entities"])]
                # A save during the request must not publish the previous layout.
                if self.config.read()["revision"] != config["revision"]:
                    self.wake.set()
                    return
                with self.lock:
                    self.cached.update(connected=True, updated_at_epoch=int(time.time()), revision=config["revision"], entities=entities, error="")
            except ValueError as error:
                with self.lock:
                    self.cached.update(connected=False, error=str(error))

    def snapshot(self):
        with self.lock:
            result = copy.deepcopy(self.cached)
        result["connected"] = result["connected"] and self.enabled() and time.time() - result["updated_at_epoch"] <= 30 and result["revision"] == self.config.read()["revision"]
        return result

    def command(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("操作格式不正确")
        with self.io_lock:
            config = self.config.read()
            snapshot = self.snapshot()
            if not snapshot["connected"]:
                raise ValueError("HA 离线，暂时不能控制")
            if type(payload.get("revision")) is not int or payload["revision"] != config["revision"]:
                raise ValueError("页面配置已改变，请刷新后重试")
            slot = payload.get("slot")
            if type(slot) is not int or not 0 <= slot < len(config["entities"]):
                raise ValueError("实体不在已配置列表中")
            item = config["entities"][slot]
            current = self.request(config, "/api/states/" + item["entity_id"])
            entity = self.entity(item, current, slot)
            action = payload.get("action")
            if action not in entity["actions"]:
                raise ValueError("该设备当前不支持此操作")
            body = {"entity_id": item["entity_id"]}
            service = action
            if action == "mode":
                if payload.get("value") not in entity["hvac_modes"]:
                    raise ValueError("空调不支持此模式")
                service = "set_hvac_mode"
                body["hvac_mode"] = payload["value"]
            elif action == "temperature":
                value = number(payload.get("value"))
                if isinstance(payload.get("value"), bool) or value is None or not entity["min_temp"] <= value <= entity["max_temp"]:
                    raise ValueError("目标温度超出空调范围")
                steps = (value - entity["min_temp"]) / entity["temp_step"]
                if abs(steps - round(steps)) > 0.00001:
                    raise ValueError("目标温度不符合空调调节步进")
                service = "set_temperature"
                body["temperature"] = value
            elif action in {"brightness", "percentage"}:
                value = payload.get("value")
                if type(value) is not int or not 0 <= value <= 100:
                    raise ValueError("比例必须是 0–100 的整数")
                service = "turn_on" if action == "brightness" else "set_percentage"
                body["brightness_pct" if action == "brightness" else "percentage"] = value
            try:
                self.request(config, "/api/services/" + entity["domain"] + "/" + service, body)
                with self.lock:
                    self.cached["command_note"] = "指令已发送，等待设备状态更新"
                self.refresh()
                return {"ok": True, "ha": self.snapshot()}
            except ValueError as error:
                with self.lock:
                    self.cached["command_note"] = str(error)
                raise

    def start(self):
        def run():
            while not self.stop.is_set():
                self.refresh()
                self.wake.wait(5)
                self.wake.clear()
        threading.Thread(target=run, name="home-assistant", daemon=True).start()
