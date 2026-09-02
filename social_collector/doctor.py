from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from typing import Any

from .opencli import doctor as opencli_doctor


def _version(command: str, args: list[str] | None = None) -> str:
    exe = shutil.which(command)
    if not exe:
        return ""
    try:
        proc = subprocess.run(
            [exe] + (args or ["--version"]),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return (proc.stdout or proc.stderr or "").strip().splitlines()[0]
    except Exception:
        return ""


def _node_major(version: str) -> int | None:
    text = version.strip().lstrip("vV")
    try:
        return int(text.split(".", 1)[0])
    except (TypeError, ValueError):
        return None


def collect_status() -> dict[str, Any]:
    python_ok = sys.version_info >= (3, 10)
    requests_ok = importlib.util.find_spec("requests") is not None
    ytdlp_ok = importlib.util.find_spec("yt_dlp") is not None
    ffmpeg = shutil.which("ffmpeg")
    node_version = _version("node")
    node_major = _node_major(node_version)
    npm = shutil.which("npm")
    opencli = opencli_doctor()

    core_ready = python_ok and requests_ok and ytdlp_ok
    return {
        "python": {
            "ready": python_ok,
            "version": sys.version.split()[0],
            "minimum": "3.10",
        },
        "python_packages": {
            "requests": requests_ok,
            "yt_dlp": ytdlp_ok,
        },
        "system": {
            "ffmpeg": {"installed": bool(ffmpeg), "path": ffmpeg or ""},
            "node": {
                "installed": bool(node_version),
                "version": node_version,
                "ready_for_opencli": bool(node_major and node_major >= 20),
            },
            "npm": {"installed": bool(npm), "path": npm or ""},
        },
        "opencli": opencli,
        "capabilities": {
            "bilibili_collect": core_ready,
            "bilibili_download": core_ready,
            "douyin_collect": core_ready,
            "douyin_download": core_ready,
            "douyin_user": bool(opencli.get("ready")),
            "xiaohongshu_collect": bool(opencli.get("ready")),
            "xiaohongshu_download": bool(opencli.get("ready")),
            "xiaohongshu_user": bool(opencli.get("ready")),
        },
        "ready_core": core_ready,
        "notes": [
            "ffmpeg is recommended for merging separate video/audio streams.",
            "Xiaohongshu and Douyin user listing use OpenCLI and the user's normal signed-in browser session.",
            "This project does not bypass login, CAPTCHA, access controls, or platform restrictions.",
        ],
    }


def print_status(*, pretty: bool = True) -> int:
    status = collect_status()
    print(json.dumps(status, ensure_ascii=False, indent=2 if pretty else None))
    return 0 if status["ready_core"] else 2
