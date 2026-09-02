from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .doctor import print_status
from .models import AuthRequiredError, CollectorError, DependencyError, Platform
from .router import get_collector, infer_platform
from .watchdog import WatchStore, Watchdog, parse_interval


def _json(data: Any, pretty: bool = True) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2 if pretty else None, default=str))


def _platform(value: str | None, url: str | None = None) -> Platform:
    if value:
        return Platform(value.lower())
    if url:
        return infer_platform(url)
    raise CollectorError("Platform is required when it cannot be inferred from a URL")


def _resolve_watch_source(source: str):
    from .feishu import FeishuIntegration
    if source == "auto":
        source = "feishu" if FeishuIntegration.env_configured() else "local"
    if source == "feishu":
        integration = FeishuIntegration.from_env(auto_setup=True)
        return source, integration.list_monitors, integration
    return "local", None, None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="social-collector", description="Standalone Douyin, Xiaohongshu and Bilibili collector")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="check runtime dependencies and capabilities")
    doctor.add_argument("--json", action="store_true")
    collect = sub.add_parser("collect", help="collect metadata from one content URL")
    collect.add_argument("url")
    collect.add_argument("--platform", choices=[p.value for p in Platform])
    download = sub.add_parser("download", help="collect metadata and download media")
    download.add_argument("url")
    download.add_argument("--platform", choices=[p.value for p in Platform])
    download.add_argument("--output", default="downloads")
    user = sub.add_parser("user", help="list recent content from a creator/profile")
    user.add_argument("user")
    user.add_argument("--platform", choices=[p.value for p in Platform])
    user.add_argument("--limit", type=int, default=20)

    watch = sub.add_parser("watch", help="manage and run creator monitoring")
    ws = watch.add_subparsers(dest="watch_command", required=True)
    wadd = ws.add_parser("add", help="add a creator to the local watchlist")
    wadd.add_argument("user")
    wadd.add_argument("--platform", choices=[p.value for p in Platform])
    wadd.add_argument("--name", default="")
    wadd.add_argument("--limit", type=int, default=20)
    ws.add_parser("list", help="list local watched creators")
    wremove = ws.add_parser("remove", help="remove a local watched creator")
    wremove.add_argument("monitor_id")
    for command_name, help_text in (("run", "run one monitoring pass"), ("start", "run monitoring continuously")):
        command = ws.add_parser(command_name, help=help_text)
        command.add_argument("--source", choices=["auto", "local", "feishu"], default="auto")
        command.add_argument("--include-existing", action="store_true")
        command.add_argument("--full-collect", action="store_true")
        if command_name == "start":
            command.add_argument("--interval", default="30m")

    feishu = sub.add_parser("feishu", help="configure optional Feishu Bitable integration")
    fs = feishu.add_subparsers(dest="feishu_command", required=True)
    setup = fs.add_parser("setup", help="create/verify Feishu tables and fields")
    setup.add_argument("--name", default="Social Media Collector")
    fs.add_parser("status", help="check Feishu authentication and table configuration")
    fadd = fs.add_parser("add-monitor", help="add a monitored creator to Feishu")
    fadd.add_argument("user")
    fadd.add_argument("--platform", choices=[p.value for p in Platform])
    fadd.add_argument("--name", default="")
    fadd.add_argument("--limit", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pretty = not args.compact
    try:
        if args.command == "doctor":
            return print_status(pretty=pretty)
        if args.command == "collect":
            platform = _platform(args.platform, args.url)
            meta = get_collector(platform).collect(args.url)
            _json({"ok": True, "data": meta.to_dict()}, pretty)
            return 0
        if args.command == "download":
            platform = _platform(args.platform, args.url)
            collector = get_collector(platform)
            meta = collector.collect(args.url)
            paths = collector.download(meta, Path(args.output))
            _json({"ok": True, "data": meta.to_dict(), "files": paths}, pretty)
            return 0
        if args.command == "user":
            platform = _platform(args.platform, args.user if args.user.startswith("http") else None)
            items = get_collector(platform).user_items(args.user, max(1, args.limit))
            _json({"ok": True, "platform": platform.value, "count": len(items), "items": items}, pretty)
            return 0
        if args.command == "watch":
            store = WatchStore()
            watchdog = Watchdog(store=store)
            if args.watch_command == "add":
                platform = _platform(args.platform, args.user if args.user.startswith("http") else None)
                row = store.add(platform=platform, user=args.user, name=args.name, limit=args.limit)
                _json({"ok": True, "monitor": row}, pretty)
                return 0
            if args.watch_command == "list":
                rows = store.list_monitors()
                _json({"ok": True, "count": len(rows), "monitors": rows}, pretty)
                return 0
            if args.watch_command == "remove":
                removed = store.remove(args.monitor_id)
                _json({"ok": removed, "removed": args.monitor_id if removed else None}, pretty)
                return 0 if removed else 4
            source, provider, sink = _resolve_watch_source(args.source)
            full_collect = bool(args.full_collect or source == "feishu")
            if args.watch_command == "run":
                result = watchdog.run_once(monitors=provider() if provider else None, include_existing=args.include_existing, full_collect=full_collect, sink=sink)
                result["source"] = source
                _json(result, pretty)
                return 0 if result.get("ok") else 5
            if args.watch_command == "start":
                seconds = parse_interval(args.interval)
                _json({"ok": True, "event": "watch_started", "source": source, "interval_seconds": seconds}, pretty)
                def emit(result: dict[str, Any]) -> None:
                    payload = dict(result)
                    payload["source"] = source
                    _json(payload, pretty)
                watchdog.run_forever(interval=seconds, monitors_provider=provider, include_existing=args.include_existing, full_collect=full_collect, sink=sink, on_result=emit)
                return 0
        if args.command == "feishu":
            from .feishu import FeishuIntegration
            integration = FeishuIntegration.from_env(auto_setup=False)
            if args.feishu_command == "setup":
                _json(integration.client.setup(args.name), pretty)
                return 0
            if args.feishu_command == "status":
                _json(integration.status(), pretty)
                return 0
            if args.feishu_command == "add-monitor":
                integration.client.setup()
                platform = _platform(args.platform, args.user if args.user.startswith("http") else None)
                record_id = integration.add_monitor(platform=platform, user=args.user, name=args.name, limit=args.limit)
                _json({"ok": True, "record_id": record_id}, pretty)
                return 0
    except AuthRequiredError as exc:
        _json({"ok": False, "error": "auth_required", "message": str(exc)}, pretty)
        return 3
    except DependencyError as exc:
        _json({"ok": False, "error": "missing_dependency", "message": str(exc)}, pretty)
        return 2
    except (CollectorError, ValueError) as exc:
        _json({"ok": False, "error": "collector_error", "message": str(exc)}, pretty)
        return 4
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        _json({"ok": False, "error": "unexpected_error", "message": str(exc)}, pretty)
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
