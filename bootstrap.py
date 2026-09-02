from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
TOOLS = ROOT / ".tools"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(str(x) for x in command))
    return subprocess.run(command, cwd=ROOT, check=check, text=True)


def _node_major() -> int | None:
    node = shutil.which("node")
    if not node:
        return None
    try:
        output = subprocess.check_output([node, "--version"], text=True, timeout=10).strip().lstrip("vV")
        return int(output.split(".", 1)[0])
    except Exception:
        return None


def install_python() -> Path:
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10+ is required")
    if not _venv_python().exists():
        _run([sys.executable, "-m", "venv", str(VENV)])
    python = _venv_python()
    _run([str(python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])
    _run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    return python


def install_opencli() -> dict[str, object]:
    node_major = _node_major()
    npm = shutil.which("npm")
    if node_major is None or node_major < 20 or not npm:
        return {
            "installed": False,
            "reason": "Node.js 20+ and npm are required before OpenCLI can be installed",
        }
    TOOLS.mkdir(parents=True, exist_ok=True)
    _run([npm, "install", "--prefix", str(TOOLS), "@jackwener/opencli"])
    return {"installed": True, "path": str(TOOLS / "node_modules" / ".bin" / "opencli")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Social Media Collector")
    parser.add_argument("--opencli", action="store_true", help="also install OpenCLI locally under .tools/")
    parser.add_argument("--all", action="store_true", help="install Python dependencies and OpenCLI when Node.js 20+ exists")
    args = parser.parse_args()

    result: dict[str, object] = {"python": {}, "opencli": {}}
    try:
        python = install_python()
        result["python"] = {"installed": True, "executable": str(python)}
        if args.opencli or args.all:
            result["opencli"] = install_opencli()
        else:
            result["opencli"] = {"installed": False, "reason": "not requested"}

        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("\nNext:")
        print(f"  {python} -m social_collector.cli doctor --json")
        print("  If doctor reports missing Node.js/FFmpeg, install them with your OS package manager and rerun bootstrap.")
        print("  Xiaohongshu requires the user's own normal browser login + OpenCLI Browser Bridge.")
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
