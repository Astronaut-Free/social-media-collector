from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from ..models import BaseCollector, CollectorError, ContentMeta, NoteType, Platform
from ..utils import DEFAULT_UA, require_ytdlp, resolve_redirect, timestamp_to_text, ytdlp_options


class BilibiliCollector(BaseCollector):
    platform = Platform.BILIBILI
    supported_domains = ("bilibili.com", "b23.tv")

    def _resolve(self, url: str) -> str:
        if "b23.tv" in url:
            return resolve_redirect(url, ("bilibili.com", "b23.tv"))
        return url

    @staticmethod
    def _ids(url: str) -> tuple[str, str]:
        bvid = ""
        aid = ""
        match = re.search(r"(BV[0-9A-Za-z]{10})", url)
        if match:
            bvid = match.group(1)
        match = re.search(r"(?:/|\b)av(\d+)", url, re.IGNORECASE)
        if match:
            aid = match.group(1)
        return bvid, aid

    def collect(self, url: str) -> ContentMeta:
        real_url = self._resolve(url)
        bvid, aid = self._ids(real_url)
        if not bvid and not aid:
            raise CollectorError(f"Could not find a BV/AV id in Bilibili URL: {real_url}")

        meta = ContentMeta(
            platform=self.platform,
            url=real_url,
            note_type=NoteType.VIDEO,
            extra={"bvid": bvid, "aid": aid, "pages": []},
        )
        try:
            self._from_api(meta, bvid=bvid, aid=aid)
        except Exception:
            self._from_ytdlp(meta)
        if not meta.title:
            meta.title = bvid or f"av{aid}"
        return meta

    def _from_api(self, meta: ContentMeta, *, bvid: str, aid: str) -> None:
        query = f"bvid={bvid}" if bvid else f"aid={aid}"
        response = requests.get(
            f"https://api.bilibili.com/x/web-interface/view?{query}",
            headers={"User-Agent": DEFAULT_UA, "Referer": "https://www.bilibili.com/"},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") not in (0, None):
            raise CollectorError(str(payload.get("message") or payload.get("code")))
        data = payload.get("data") or {}
        if not data:
            raise CollectorError("Bilibili API returned no data")

        owner = data.get("owner") or {}
        stat = data.get("stat") or {}
        meta.title = data.get("title") or ""
        meta.desc = data.get("desc") or ""
        meta.author = owner.get("name") or ""
        meta.author_id = str(owner.get("mid") or "")
        if meta.author_id:
            meta.author_url = f"https://space.bilibili.com/{meta.author_id}"
        meta.cover_url = data.get("pic") or ""
        meta.publish_time = timestamp_to_text(data.get("pubdate"))
        meta.video_duration = int(data.get("duration") or 0) or None
        meta.play_count = self._int(stat.get("view"))
        meta.liked_count = self._int(stat.get("like"))
        meta.comment_count = self._int(stat.get("reply"))
        meta.share_count = self._int(stat.get("share"))
        meta.collected_count = self._int(stat.get("favorite"))
        meta.extra["pages"] = [
            {
                "page": page.get("page", index + 1),
                "part": page.get("part", ""),
                "cid": page.get("cid", ""),
            }
            for index, page in enumerate(data.get("pages") or [])
        ]

    def _from_ytdlp(self, meta: ContentMeta) -> None:
        yt_dlp = require_ytdlp()
        opts = ytdlp_options("bilibili")
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(meta.url, download=False)
        if not info:
            return
        meta.title = info.get("title") or meta.title
        meta.desc = info.get("description") or meta.desc
        meta.author = info.get("uploader") or info.get("creator") or meta.author
        meta.author_id = str(info.get("uploader_id") or info.get("channel_id") or meta.author_id)
        if meta.author_id and meta.author_id.isdigit():
            meta.author_url = f"https://space.bilibili.com/{meta.author_id}"
        meta.cover_url = info.get("thumbnail") or meta.cover_url
        meta.publish_time = timestamp_to_text(info.get("timestamp")) or meta.publish_time
        meta.video_duration = self._int(info.get("duration"))
        meta.play_count = self._int(info.get("view_count"))
        meta.liked_count = self._int(info.get("like_count"))
        meta.comment_count = self._int(info.get("comment_count"))

    def download(self, meta: ContentMeta, output_dir: str | Path) -> list[str]:
        yt_dlp = require_ytdlp()
        out = Path(output_dir).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        before = {p.resolve() for p in out.rglob("*") if p.is_file()}
        opts = ytdlp_options("bilibili", download=True, output_dir=out)
        opts.update({
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "merge_output_format": "mp4",
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([meta.url])
        after = {p.resolve() for p in out.rglob("*") if p.is_file()}
        return [str(path) for path in sorted(after - before)]

    def user_items(self, user: str, limit: int = 20) -> list[dict[str, Any]]:
        profile = user if user.startswith("http") else f"https://space.bilibili.com/{user}/video"
        yt_dlp = require_ytdlp()
        opts = ytdlp_options("bilibili")
        opts.update({"extract_flat": True, "playlistend": max(1, limit), "noplaylist": False})
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(profile, download=False)
        entries = (info or {}).get("entries") or []
        result: list[dict[str, Any]] = []
        for item in entries[:limit]:
            if not item:
                continue
            video_id = item.get("id") or ""
            url = item.get("url") or item.get("webpage_url") or ""
            if url and not url.startswith("http") and video_id:
                url = f"https://www.bilibili.com/video/{video_id}"
            result.append({
                "content_id": video_id,
                "title": item.get("title") or "",
                "url": url,
                "create_time": item.get("timestamp") or 0,
            })
        return result

    @staticmethod
    def _int(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
