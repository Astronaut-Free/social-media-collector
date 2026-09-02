from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

import requests

from .models import DependencyError


DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def ensure_dir(path: str | Path) -> Path:
    p = Path(path).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_filename(value: str, fallback: str = "media") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", value or "").strip(" ._")
    return (cleaned[:120] or fallback)


def host_matches(url: str, domains: Iterable[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in domains)


def resolve_redirect(url: str, expected_domains: Iterable[str] | None = None, timeout: int = 15) -> str:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": DEFAULT_UA},
            allow_redirects=True,
            timeout=timeout,
            stream=True,
        )
        final = response.url or url
        response.close()
        if expected_domains and not host_matches(final, expected_domains):
            return url
        return final
    except requests.RequestException:
        return url


def download_http(
    url: str,
    output_dir: str | Path,
    filename: str,
    *,
    referer: str = "",
    timeout: int = 120,
) -> str | None:
    out_dir = ensure_dir(output_dir)
    target = out_dir / safe_filename(filename, "media")
    headers = {"User-Agent": DEFAULT_UA}
    if referer:
        headers["Referer"] = referer
    try:
        with requests.get(url, headers=headers, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            with target.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
        return str(target)
    except requests.RequestException:
        if target.exists():
            target.unlink(missing_ok=True)
        return None


def parse_count(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    multipliers = {"万": 10_000, "w": 10_000, "W": 10_000, "亿": 100_000_000}
    for suffix, multiplier in multipliers.items():
        if suffix in text:
            try:
                return int(float(text.replace(suffix, "")) * multiplier)
            except ValueError:
                return None
    try:
        return int(float(text))
    except ValueError:
        return None


def timestamp_to_text(value: Any) -> str:
    try:
        ts = int(float(value))
    except (TypeError, ValueError):
        return ""
    if ts > 10_000_000_000:
        ts //= 1000
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


def cookie_file(platform: str) -> str | None:
    keys = [
        f"{platform.upper()}_COOKIE_FILE",
        "SOCIAL_COLLECTOR_COOKIE_FILE",
    ]
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value and Path(value).expanduser().is_file():
            return str(Path(value).expanduser().resolve())
    for candidate in (
        Path("cookies") / f"{platform}.txt",
        Path(f"{platform}_cookies.txt"),
    ):
        if candidate.is_file():
            return str(candidate.resolve())
    return None


def require_ytdlp():
    try:
        import yt_dlp  # type: ignore
    except ImportError as exc:
        raise DependencyError("yt-dlp is missing. Run: python bootstrap.py") from exc
    return yt_dlp


def ytdlp_options(platform: str, *, download: bool = False, output_dir: str | Path | None = None) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    cookies = cookie_file(platform)
    if cookies:
        opts["cookiefile"] = cookies
    if not download:
        opts["skip_download"] = True
    elif output_dir is not None:
        out = ensure_dir(output_dir)
        opts["outtmpl"] = str(out / "%(title).100s-%(id)s.%(ext)s")
    return opts


def run_process(command: list[str], *, timeout: int = 120, cwd: str | Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def parse_json_output(text: str) -> Any:
    stripped = (text or "").strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        # Some CLIs log before printing JSON. Try the last JSON-looking line.
        for line in reversed(stripped.splitlines()):
            line = line.strip()
            if line.startswith(("{", "[")):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
    return None


def which(name: str) -> str | None:
    return shutil.which(name)
