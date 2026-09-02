# Coding Agent Instructions

This repository is designed to be operated by Coding Agents such as Codex or Claude Code.

## Goal

Provide standalone collection for Douyin, Xiaohongshu and Bilibili without depending on Taiyi.

## First-run procedure

1. Read this file and `README.md`.
2. Run `python bootstrap.py --all`.
3. Run `.venv/bin/python -m social_collector.cli doctor --json` on macOS/Linux, or `.venv\\Scripts\\python.exe -m social_collector.cli doctor --json` on Windows.
4. If `doctor` reports missing system dependencies, install them using the machine's trusted package manager, then rerun steps 2-3:
   - Node.js 20+ is needed for OpenCLI.
   - FFmpeg is recommended for media merging performed by yt-dlp.
5. If Node.js was installed after the first bootstrap, rerun `python bootstrap.py --opencli`.
6. For Xiaohongshu and Douyin creator-list commands, run `opencli doctor`. The user must sign in to the platform using their normal browser and connect OpenCLI Browser Bridge when required.
7. Never print, commit, upload, or expose cookie contents, tokens, passwords, or browser storage.
8. Do not bypass CAPTCHA, login, access controls, rate limits, or platform restrictions. If authorization is required, ask the user to complete it normally.

## Commands

```bash
python cli.py doctor --json
python cli.py collect "<content-url>"
python cli.py download "<content-url>" --output downloads
python cli.py user "<creator-id-or-profile-url>" --platform douyin --limit 20
python cli.py user "<creator-id-or-profile-url>" --platform xiaohongshu --limit 20
python cli.py user "<creator-id-or-profile-url>" --platform bilibili --limit 20
```

All command results are JSON. Exit codes:

- `0`: success
- `2`: missing dependency
- `3`: user authentication/browser session required
- `4`: unsupported input or collector error
- `5`: unexpected runtime failure

## Cookie files

When a platform needs the user's own session, prefer a Netscape-format cookie file outside Git. Supported environment variables:

- `DOUYIN_COOKIE_FILE`
- `BILIBILI_COOKIE_FILE`
- `SOCIAL_COLLECTOR_COOKIE_FILE`

The `.gitignore` already excludes common cookie locations.
