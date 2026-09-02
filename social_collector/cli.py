from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .doctor import print_status
from .models import AuthRequiredError, CollectorError, DependencyError, Platform
from .router import get_collector, infer_platform


def _json(data: Any, pretty: bool = True) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2 if pretty else None, default=str))


def _platform(value: str | None, url: str | None = None) -> Platform:
    if value:
        return Platform(value.lower())
    if url:
        return infer_platform(url)
    raise CollectorError("Platform is required when it cannot be inferred from a URL")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="social-collector",
        description="Standalone Douyin, Xiaohongshu and Bilibili collector",
    )
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="check runtime dependencies and capabilities")
    doctor.add_argument("--json", action="store_true", help="kept for agent-friendly compatibility")

    collect = sub.add_parser("collect", help="collect metadata from one content URL")
    collect.add_argument("url")
    collect.add_argument("--platform", choices=[p.value for p in Platform])

    download = sub.add_parser("download", help="collect metadata and download media")
    download.add_argument("url")
    download.add_argument("--platform", choices=[p.value for p in Platform])
    download.add_argument("--output", default="downloads")

    user = sub.add_parser("user", help="list recent content from a creator/profile")
    user.add_argument("user", help="creator id or profile URL")
    user.add_argument("--platform", choices=[p.value for p in Platform])
    user.add_argument("--limit", type=int, default=20)

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
            collector = get_collector(platform)
            meta = collector.collect(args.url)
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
            collector = get_collector(platform)
            items = collector.user_items(args.user, max(1, args.limit))
            _json({"ok": True, "platform": platform.value, "count": len(items), "items": items}, pretty)
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
