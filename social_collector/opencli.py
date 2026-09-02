from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from .models import AuthRequiredError, DependencyError
from .utils import parse_json_output, run_process


ROOT = Path(__file__).resolve().parent.parent


def _local_opencli() -> str | None:
    bin_dir = ROOT / ".tools" / "node_modules" / ".bin"
    candidates = [bin_dir / "opencli", bin_dir / "opencli.cmd", bin_dir / "opencli.ps1"]
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def opencli_command() -> list[str] | None:
    env_path = os.environ.get("OPENCLI_BIN", "").strip()
    if env_path and Path(env_path).expanduser().exists():
        return [str(Path(env_path).expanduser())]
    executable = shutil.which("opencli") or _local_opencli()
    return [executable] if executable else None


def run_opencli(args: list[str], *, timeout: int = 90, expect_json: bool = True) -> Any:
    command = opencli_command()
    if not command:
        raise DependencyError(
            "OpenCLI is missing. Run `python bootstrap.py --opencli`. "
            "Node.js 20+ is required."
        )
    proc = run_process(command + args, timeout=timeout)
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "OpenCLI failed").strip()
        lowered = message.lower()
        if any(token in lowered for token in ("auth", "login", "browser bridge", "extension", "empty_result")):
            raise AuthRequiredError(
                "OpenCLI could not access the signed-in browser session. "
                "Open the platform in your normal browser, sign in, and make sure Browser Bridge is connected."
            )
        raise RuntimeError(message[-800:])
    if not expect_json:
        return proc
    data = parse_json_output(proc.stdout)
    if data is None:
        raise RuntimeError("OpenCLI returned no JSON data")
    return data


def doctor() -> dict[str, Any]:
    command = opencli_command()
    if not command:
        return {"installed": False, "ready": False, "detail": "OpenCLI not found"}
    try:
        proc = run_process(command + ["doctor"], timeout=30)
        text = (proc.stdout or proc.stderr or "").strip()
        return {
            "installed": True,
            "ready": proc.returncode == 0,
            "detail": text[-1200:],
        }
    except Exception as exc:  # diagnostics must never crash the whole doctor command
        return {"installed": True, "ready": False, "detail": str(exc)}
