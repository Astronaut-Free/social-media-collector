# Coding Agent Instructions

This repository is a standalone Douyin / Xiaohongshu / Bilibili collector with optional Watchdog and Feishu Bitable integration.

## Core rules

1. This repository must remain independent from Taiyi.
2. Run `python bootstrap.py --all` on first use, then `python cli.py doctor --json`.
3. Never print, commit, upload, or expose cookies, tokens, passwords, app secrets, browser storage, or `.env` contents.
4. Do not bypass CAPTCHA, login, access controls, rate limits, or platform restrictions. Ask the user to complete normal authorization when required.
5. Prefer repository-local `.venv` and `.tools/`.
6. Do not modify the user's Taiyi repository when working on this project.

## Collector commands

```bash
python cli.py collect "<content-url>"
python cli.py download "<content-url>" --output downloads
python cli.py user "<creator>" --platform douyin --limit 20
```

## Local Watchdog

```bash
python cli.py watch add "<creator>" --platform douyin --name "<name>"
python cli.py watch list
python cli.py watch run --source local
python cli.py watch start --source local --interval 30m
```

First check establishes a baseline. Use `--include-existing` only when the user explicitly wants current historical items treated as new. Minimum watch interval is 60 seconds.

## Feishu

Secrets are environment variables: `FEISHU_APP_ID`, `FEISHU_APP_SECRET`. Optional: `FEISHU_BITABLE_APP_TOKEN`, `FEISHU_FOLDER_TOKEN`, `FEISHU_STATE_FILE`.

```bash
python cli.py feishu setup
python cli.py feishu status
python cli.py feishu add-monitor "<creator>" --platform xiaohongshu --name "<name>"
```

Setup creates/verifies `博主监控池` and `素材内容池`. It adds missing fields and reports type mismatches instead of destructively changing existing fields.

When Feishu credentials exist, `--source auto` selects Feishu:

```bash
python cli.py watch run
python cli.py watch start --interval 30m
```

Feishu mode fully collects newly discovered content, deduplicates by 内容ID, writes it to 素材内容池, and updates 最新发布ID / 最近检查时间 / 监控状态.

## Exit codes

- `0`: success
- `2`: missing dependency
- `3`: normal user authentication/browser session required
- `4`: unsupported input/configuration/collector error
- `5`: unexpected runtime or monitoring failure
- `130`: interrupted by user
