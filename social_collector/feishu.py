from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from .feishu_schema import CONTENT_FIELDS, CONTENT_TABLE_NAME, MONITOR_FIELDS, MONITOR_TABLE_NAME
from .models import CollectorError, NoteType, Platform
from .image_manifest import normalize_image_list

BASE_URL = "https://open.feishu.cn/open-apis"


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text") or value.get("link") or "").strip()
    if isinstance(value, list):
        for item in value:
            candidate = _text(item)
            if candidate:
                return candidate
        return ""
    return str(value or "").strip()


def _url_cell(url: str, text: str = "") -> dict[str, str]:
    return {"link": url, "text": text or url}


def _canonical_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
    except Exception:
        return url.strip()


def _date_ms(value: str) -> int | None:
    if not value:
        return None
    normalized = value.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            target = normalized[:16] if "%H" in fmt else normalized[:10]
            return int(datetime.strptime(target, fmt).timestamp() * 1000)
        except ValueError:
            continue
    return None


def _platform_label(value: Platform | str) -> str:
    text = value.value if isinstance(value, Platform) else str(value).lower()
    return {"douyin": "抖音", "xiaohongshu": "小红书", "bilibili": "B站"}.get(text, text)


def _platform_value(value: Any) -> str:
    text = _text(value).lower()
    mapping = {"抖音": "douyin", "douyin": "douyin", "小红书": "xiaohongshu", "xiaohongshu": "xiaohongshu", "xhs": "xiaohongshu", "b站": "bilibili", "哔哩哔哩": "bilibili", "bilibili": "bilibili"}
    if text in mapping:
        return mapping[text]
    raise CollectorError(f"Unsupported Feishu monitor platform: {text}")


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, *, app_token: str = "", state_path: str | Path = "data/feishu.json"):
        self.app_id = app_id.strip()
        self.app_secret = app_secret.strip()
        self.app_token = app_token.strip()
        self.state_path = Path(state_path)
        self._token = ""
        self._state = self._load_state()
        if not self.app_token:
            self.app_token = str(self._state.get("app_token") or "").strip()

    @classmethod
    def from_env(cls) -> "FeishuClient":
        app_id = os.environ.get("FEISHU_APP_ID", "").strip()
        app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
        if not app_id or not app_secret:
            raise CollectorError("Feishu is not configured. Set FEISHU_APP_ID and FEISHU_APP_SECRET.")
        return cls(app_id, app_secret, app_token=os.environ.get("FEISHU_BITABLE_APP_TOKEN", ""), state_path=os.environ.get("FEISHU_STATE_FILE", "data/feishu.json"))

    @staticmethod
    def env_configured() -> bool:
        return bool(os.environ.get("FEISHU_APP_ID", "").strip() and os.environ.get("FEISHU_APP_SECRET", "").strip())

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(self._state)
        if self.app_token:
            payload["app_token"] = self.app_token
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.state_path)

    def _get_token(self) -> str:
        if self._token:
            return self._token
        response = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal", json={"app_id": self.app_id, "app_secret": self.app_secret}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        token = payload.get("tenant_access_token") or ""
        if not token:
            raise CollectorError(f"Feishu authentication failed: code={payload.get('code')} msg={payload.get('msg')}")
        self._token = token
        return token

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, body: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.request(method, f"{BASE_URL}{path}", headers={"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json; charset=utf-8"}, params=params, json=body, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") not in (0, None):
            raise CollectorError(f"Feishu API failed: code={payload.get('code')} msg={payload.get('msg')}")
        data = payload.get("data") or {}
        return data if isinstance(data, dict) else {}

    def create_base(self, name: str = "Social Media Collector") -> str:
        body: dict[str, Any] = {"name": name}
        folder_token = os.environ.get("FEISHU_FOLDER_TOKEN", "").strip()
        if folder_token:
            body["folder_token"] = folder_token
        data = self._request("POST", "/bitable/v1/apps", body=body)
        app = data.get("app") if isinstance(data.get("app"), dict) else data
        token = str((app or {}).get("app_token") or data.get("app_token") or "").strip()
        if not token:
            raise CollectorError("Feishu created a base but no app_token was returned")
        self.app_token = token
        self._save_state()
        return token

    def ensure_app_token(self, name: str = "Social Media Collector") -> str:
        return self.app_token or self.create_base(name)

    def list_tables(self) -> list[dict[str, Any]]:
        self.ensure_app_token()
        data = self._request("GET", f"/bitable/v1/apps/{self.app_token}/tables", params={"page_size": 100})
        return [item for item in (data.get("items") or []) if isinstance(item, dict)]

    def create_table(self, name: str, fields: tuple[Any, ...]) -> str:
        self.ensure_app_token()
        table = {"name": name, "default_view_name": "全部", "fields": [field.to_api() for field in fields]}
        try:
            data = self._request("POST", f"/bitable/v1/apps/{self.app_token}/tables", body={"table": table})
        except Exception:
            data = self._request("POST", f"/bitable/v1/apps/{self.app_token}/tables", body={"table": {"name": name, "default_view_name": "全部"}})
        table_id = str(data.get("table_id") or (data.get("table") or {}).get("table_id") or "")
        if not table_id:
            raise CollectorError(f"Feishu did not return table_id for {name}")
        return table_id

    def list_fields(self, table_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields", params={"page_size": 100})
        return [item for item in (data.get("items") or []) if isinstance(item, dict)]

    def ensure_fields(self, table_id: str, fields: tuple[Any, ...]) -> dict[str, Any]:
        existing = {str(row.get("field_name") or ""): row for row in self.list_fields(table_id)}
        created: list[str] = []
        mismatched: list[dict[str, Any]] = []
        for spec in fields:
            current = existing.get(spec.name)
            if current:
                if int(current.get("type") or 0) != spec.type:
                    mismatched.append({"field": spec.name, "expected_type": spec.type, "actual_type": current.get("type")})
                continue
            self._request("POST", f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/fields", body=spec.to_api())
            created.append(spec.name)
        return {"created": created, "type_mismatches": mismatched}

    def ensure_table(self, name: str, fields: tuple[Any, ...]) -> tuple[str, dict[str, Any]]:
        found = next((row for row in self.list_tables() if str(row.get("name") or "") == name), None)
        table_id = str((found or {}).get("table_id") or "")
        if not table_id:
            table_id = self.create_table(name, fields)
        return table_id, self.ensure_fields(table_id, fields)

    def setup(self, name: str = "Social Media Collector") -> dict[str, Any]:
        self.ensure_app_token(name)
        content_id, content_report = self.ensure_table(CONTENT_TABLE_NAME, CONTENT_FIELDS)
        monitor_id, monitor_report = self.ensure_table(MONITOR_TABLE_NAME, MONITOR_FIELDS)
        self._state["tables"] = {CONTENT_TABLE_NAME: content_id, MONITOR_TABLE_NAME: monitor_id}
        self._save_state()
        return {"ok": True, "app_token_configured": bool(self.app_token), "tables": self._state["tables"], "field_reports": {CONTENT_TABLE_NAME: content_report, MONITOR_TABLE_NAME: monitor_report}}

    def table_id(self, name: str) -> str:
        tables = self._state.get("tables") or {}
        value = str(tables.get(name) or "").strip() if isinstance(tables, dict) else ""
        if not value:
            self.setup()
            tables = self._state.get("tables") or {}
            value = str(tables.get(name) or "").strip()
        if not value:
            raise CollectorError(f"Feishu table is not configured: {name}")
        return value

    def list_records(self, table_id: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_token = ""
        while True:
            params: dict[str, Any] = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            data = self._request("GET", f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records", params=params)
            records.extend(item for item in (data.get("items") or []) if isinstance(item, dict))
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token") or "")
            if not page_token:
                break
        return records

    def create_record(self, table_id: str, fields: dict[str, Any]) -> str:
        data = self._request("POST", f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records", body={"fields": fields})
        record = data.get("record") if isinstance(data.get("record"), dict) else data
        return str((record or {}).get("record_id") or "")

    def update_record(self, table_id: str, record_id: str, fields: dict[str, Any]) -> None:
        self._request("PUT", f"/bitable/v1/apps/{self.app_token}/tables/{table_id}/records/{record_id}", body={"fields": fields})


class FeishuIntegration:
    def __init__(self, client: FeishuClient):
        self.client = client
        self._existing_ids: set[str] | None = None

    @classmethod
    def from_env(cls, *, auto_setup: bool = True) -> "FeishuIntegration":
        client = FeishuClient.from_env()
        integration = cls(client)
        if auto_setup:
            client.setup()
        return integration

    @staticmethod
    def env_configured() -> bool:
        return FeishuClient.env_configured()

    def setup(self) -> dict[str, Any]:
        return self.client.setup()

    def status(self) -> dict[str, Any]:
        self.client._get_token()
        configured = self.client._state.get("tables") or {}
        if not self.client.app_token:
            return {"ok": True, "authenticated": True, "base_configured": False, "configured_tables": configured, "available_tables": []}
        tables = self.client.list_tables()
        return {"ok": True, "authenticated": True, "base_configured": True, "configured_tables": configured, "available_tables": [{"name": row.get("name"), "table_id": row.get("table_id")} for row in tables]}

    def list_monitors(self) -> list[dict[str, Any]]:
        table_id = self.client.table_id(MONITOR_TABLE_NAME)
        result: list[dict[str, Any]] = []
        for record in self.client.list_records(table_id):
            fields = record.get("fields") or {}
            if fields.get("启用监控") is False:
                continue
            record_id = str(record.get("record_id") or "").strip()
            try:
                platform = _platform_value(fields.get("来源平台"))
            except CollectorError:
                continue
            profile = _text(fields.get("主页链接"))
            creator_id = _text(fields.get("博主ID"))
            user = profile or creator_id
            if not user:
                continue
            try:
                limit = int(fields.get("每次抓取数量") or 20)
            except (TypeError, ValueError):
                limit = 20
            result.append({"id": f"feishu:{record_id}", "record_id": record_id, "platform": platform, "user": user, "name": _text(fields.get("博主名称")), "limit": max(1, min(limit, 200)), "latest_id": _text(fields.get("最新发布ID")), "enabled": True})
        return result

    def add_monitor(self, *, platform: Platform | str, user: str, name: str = "", limit: int = 20) -> str:
        table_id = self.client.table_id(MONITOR_TABLE_NAME)
        platform_value = platform.value if isinstance(platform, Platform) else str(platform).lower()
        fields: dict[str, Any] = {"博主名称": name.strip() or user.strip()[:80], "来源平台": _platform_label(platform_value), "启用监控": True, "每次抓取数量": max(1, min(int(limit), 200)), "监控状态": "未初始化", "全量爬取周期": "不爬取", "全量爬取状态": "未爬取"}
        if user.strip().startswith("http"):
            fields["主页链接"] = _url_cell(user.strip(), "打开主页")
        else:
            fields["博主ID"] = user.strip()
        return self.client.create_record(table_id, fields)

    def _content_ids(self) -> set[str]:
        if self._existing_ids is not None:
            return self._existing_ids
        result: set[str] = set()
        for record in self.client.list_records(self.client.table_id(CONTENT_TABLE_NAME)):
            content_id = _text((record.get("fields") or {}).get("内容ID"))
            if content_id:
                result.add(content_id)
        self._existing_ids = result
        return result

    def write_new_items(self, monitor: dict[str, Any], enriched: list[dict[str, Any]]) -> None:
        table_id = self.client.table_id(CONTENT_TABLE_NAME)
        existing = self._content_ids()
        for row in enriched:
            item = row.get("item") or {}
            meta = row.get("meta") or {}
            identity = str(row.get("identity") or "")
            content_id = str(item.get("content_id") or meta.get("extra", {}).get("bvid") or identity)
            if content_id and content_id in existing:
                continue
            url = str(meta.get("url") or item.get("url") or "").strip()
            platform = str(meta.get("platform") or monitor.get("platform") or "")
            note_type = str(meta.get("note_type") or "")
            publish_ms = _date_ms(str(meta.get("publish_time") or ""))
            now_ms = _now_ms()
            content_form = "视频" if note_type == NoteType.VIDEO.value or (not note_type and platform in ("douyin", "bilibili")) else "图文"
            monitor_user = str(monitor.get("user") or "")
            fallback_blogger_id = "" if monitor_user.startswith("http") else monitor_user
            fields: dict[str, Any] = {"素材标题": str(meta.get("title") or item.get("title") or ""), "来源平台": _platform_label(platform), "素材博主": str(meta.get("author") or monitor.get("name") or ""), "博主ID": str(meta.get("author_id") or fallback_blogger_id), "内容ID": content_id, "内容形式": content_form, "素材正文": str(meta.get("desc") or item.get("desc") or ""), "收藏时间": now_ms, "互动数据更新时间": now_ms, "去参链接": _canonical_url(url) if url else "", "采集状态": "采集失败" if row.get("collect_error") else "已采集"}
            if url:
                fields["原始链接"] = _url_cell(url, "打开原文")
            cover = str(meta.get("cover_url") or item.get("cover_url") or "").strip()
            if cover:
                fields["封面链接"] = _url_cell(cover, "封面")
            image_list = normalize_image_list(meta.get("image_list"))
            if image_list:
                fields["图片数量"] = len(image_list)
                fields["图片列表JSON"] = json.dumps(image_list, ensure_ascii=False, separators=(",", ":"))
            if publish_ms is not None:
                fields["素材发布时间"] = publish_ms
            numeric = {"视频时长": meta.get("video_duration"), "博主粉丝数": meta.get("follower_count"), "点赞数": meta.get("liked_count", item.get("digg_count")), "收藏数": meta.get("collected_count", item.get("collect_count")), "评论数": meta.get("comment_count", item.get("comment_count")), "分享数": meta.get("share_count", item.get("share_count")), "播放量/阅读量": meta.get("play_count", item.get("play_count"))}
            for field_name, value in numeric.items():
                if value is not None:
                    fields[field_name] = value
            fields = {key: value for key, value in fields.items() if value not in ("", None)}
            self.client.create_record(table_id, fields)
            if content_id:
                existing.add(content_id)

    def mark_success(self, monitor: dict[str, Any], *, latest_id: str = "") -> None:
        record_id = str(monitor.get("record_id") or "").strip()
        if not record_id:
            return
        fields: dict[str, Any] = {"最近检查时间": _now_ms(), "监控状态": "正常", "最后错误": ""}
        if latest_id:
            fields["最新发布ID"] = latest_id
        self.client.update_record(self.client.table_id(MONITOR_TABLE_NAME), record_id, fields)

    def mark_error(self, monitor: dict[str, Any], message: str) -> None:
        record_id = str(monitor.get("record_id") or "").strip()
        if not record_id:
            return
        self.client.update_record(self.client.table_id(MONITOR_TABLE_NAME), record_id, {"最近检查时间": _now_ms(), "监控状态": "异常", "最后错误": str(message)[:1000]})
