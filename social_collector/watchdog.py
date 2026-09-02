from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .models import BaseCollector, CollectorError, Platform
from .router import get_collector


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_interval(value: str | int | float) -> int:
    """Parse 30m / 2h / 90s into seconds. Minimum is 60 seconds."""
    if isinstance(value, (int, float)):
        seconds = int(value)
    else:
        text = str(value).strip().lower()
        if not text:
            raise ValueError("interval cannot be empty")
        units = {"s": 1, "m": 60, "h": 3600}
        if text[-1:] in units:
            seconds = int(float(text[:-1]) * units[text[-1]])
        else:
            seconds = int(float(text))
    if seconds < 60:
        raise ValueError("watch interval must be at least 60 seconds")
    return seconds


def monitor_id(platform: Platform | str, user: str) -> str:
    value = platform.value if isinstance(platform, Platform) else str(platform).lower()
    raw = f"{value}\n{user.strip()}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def item_identity(item: dict[str, Any]) -> str:
    content_id = str(item.get("content_id") or item.get("id") or "").strip()
    if content_id:
        return content_id
    url = str(item.get("url") or "").strip()
    if url:
        return hashlib.sha1(url.encode("utf-8")).hexdigest()
    basis = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


class WatchStore:
    def __init__(self, root: str | Path = "data"):
        self.root = Path(root)
        self.watchlist_path = self.root / "watchlist.json"
        self.state_path = self.root / "watch_state.json"

    def _read(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default

    def _write(self, path: Path, data: Any) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        temp.replace(path)

    def list_monitors(self) -> list[dict[str, Any]]:
        rows = self._read(self.watchlist_path, [])
        return rows if isinstance(rows, list) else []

    def add(
        self,
        *,
        platform: Platform,
        user: str,
        name: str = "",
        limit: int = 20,
    ) -> dict[str, Any]:
        user = user.strip()
        if not user:
            raise ValueError("creator id/profile URL cannot be empty")
        rows = self.list_monitors()
        mid = monitor_id(platform, user)
        row = {
            "id": mid,
            "platform": platform.value,
            "user": user,
            "name": name.strip(),
            "limit": max(1, min(int(limit), 200)),
            "enabled": True,
            "created_at": _now_iso(),
        }
        replaced = False
        for index, existing in enumerate(rows):
            if existing.get("id") == mid:
                row["created_at"] = existing.get("created_at") or row["created_at"]
                rows[index] = row
                replaced = True
                break
        if not replaced:
            rows.append(row)
        self._write(self.watchlist_path, rows)
        return row

    def remove(self, mid: str) -> bool:
        rows = self.list_monitors()
        remaining = [row for row in rows if row.get("id") != mid]
        changed = len(remaining) != len(rows)
        if changed:
            self._write(self.watchlist_path, remaining)
            state = self._read(self.state_path, {})
            if isinstance(state, dict) and mid in state:
                state.pop(mid, None)
                self._write(self.state_path, state)
        return changed

    def get_state(self, mid: str) -> dict[str, Any]:
        state = self._read(self.state_path, {})
        if not isinstance(state, dict):
            return {}
        row = state.get(mid) or {}
        return row if isinstance(row, dict) else {}

    def set_state(self, mid: str, row: dict[str, Any]) -> None:
        state = self._read(self.state_path, {})
        if not isinstance(state, dict):
            state = {}
        state[mid] = row
        self._write(self.state_path, state)


class Watchdog:
    def __init__(
        self,
        store: WatchStore | None = None,
        collector_factory: Callable[[Platform | str], BaseCollector] = get_collector,
    ):
        self.store = store or WatchStore()
        self.collector_factory = collector_factory

    def run_once(
        self,
        *,
        monitors: list[dict[str, Any]] | None = None,
        include_existing: bool = False,
        full_collect: bool = False,
        sink: Any = None,
    ) -> dict[str, Any]:
        monitor_rows = monitors if monitors is not None else self.store.list_monitors()
        results: list[dict[str, Any]] = []
        total_new = 0

        for monitor in monitor_rows:
            if monitor.get("enabled") is False:
                continue
            result = self._check_one(
                monitor,
                include_existing=include_existing,
                full_collect=full_collect,
                sink=sink,
            )
            results.append(result)
            total_new += int(result.get("new_count") or 0)

        return {
            "ok": all(not row.get("error") for row in results),
            "checked": len(results),
            "new_count": total_new,
            "results": results,
        }

    def _check_one(
        self,
        monitor: dict[str, Any],
        *,
        include_existing: bool,
        full_collect: bool,
        sink: Any,
    ) -> dict[str, Any]:
        mid = str(monitor.get("id") or "").strip()
        platform = Platform(str(monitor.get("platform") or "").lower())
        user = str(monitor.get("user") or "").strip()
        if not mid:
            mid = monitor_id(platform, user)
            monitor["id"] = mid
        if not user:
            return {"monitor_id": mid, "error": "creator id/profile URL is empty", "new_count": 0}

        collector = self.collector_factory(platform)
        state = self.store.get_state(mid)
        initialized = bool(state.get("initialized"))
        seen = {str(value) for value in (state.get("seen_ids") or []) if value}

        try:
            items = collector.user_items(user, max(1, int(monitor.get("limit") or 20)))
            current_pairs = [(item_identity(item), item) for item in items if isinstance(item, dict)]
            if initialized:
                new_pairs = [(iid, item) for iid, item in current_pairs if iid not in seen]
            elif include_existing:
                new_pairs = current_pairs
            else:
                previous_latest = str(monitor.get("latest_id") or "").strip()
                if previous_latest:
                    new_pairs = []
                    found_previous = False
                    for iid, item in current_pairs:
                        if iid == previous_latest:
                            found_previous = True
                            break
                        new_pairs.append((iid, item))
                    if not found_previous:
                        new_pairs = current_pairs
                else:
                    new_pairs = []

            enriched: list[dict[str, Any]] = []
            for iid, item in new_pairs:
                row: dict[str, Any] = {"identity": iid, "item": item}
                if full_collect:
                    url = str(item.get("url") or "").strip()
                    if url:
                        try:
                            row["meta"] = collector.collect(url).to_dict()
                        except Exception as exc:
                            row["collect_error"] = str(exc)
                enriched.append(row)

            if sink is not None and enriched:
                sink.write_new_items(monitor, enriched)

            latest_id = current_pairs[0][0] if current_pairs else ""
            if sink is not None and hasattr(sink, "mark_success"):
                sink.mark_success(monitor, latest_id=latest_id)

            merged = [iid for iid, _ in current_pairs] + list(seen)
            compact_seen = list(dict.fromkeys(merged))[:2000]
            self.store.set_state(
                mid,
                {
                    "initialized": True,
                    "seen_ids": compact_seen,
                    "last_checked_at": _now_iso(),
                },
            )
            return {
                "monitor_id": mid,
                "platform": platform.value,
                "user": user,
                "initialized_before": initialized,
                "fetched_count": len(items),
                "new_count": len(enriched),
                "new_items": enriched,
            }
        except Exception as exc:
            if sink is not None and hasattr(sink, "mark_error"):
                try:
                    sink.mark_error(monitor, str(exc))
                except Exception:
                    pass
            return {
                "monitor_id": mid,
                "platform": platform.value,
                "user": user,
                "new_count": 0,
                "error": str(exc),
            }

    def run_forever(
        self,
        *,
        interval: str | int = "30m",
        monitors_provider: Callable[[], list[dict[str, Any]]] | None = None,
        include_existing: bool = False,
        full_collect: bool = False,
        sink: Any = None,
        on_result: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        seconds = parse_interval(interval)
        while True:
            monitors = monitors_provider() if monitors_provider else None
            result = self.run_once(
                monitors=monitors,
                include_existing=include_existing,
                full_collect=full_collect,
                sink=sink,
            )
            if on_result:
                on_result(result)
            time.sleep(seconds)
