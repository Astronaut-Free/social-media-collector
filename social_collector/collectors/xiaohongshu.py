from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..models import AuthRequiredError, BaseCollector, CollectorError, ContentMeta, NoteType, Platform
from ..opencli import run_opencli
from ..utils import parse_count, resolve_redirect


class XiaohongshuCollector(BaseCollector):
    platform = Platform.XIAOHONGSHU
    supported_domains = ("xiaohongshu.com", "xhslink.com", "xhslink.cn")

    def _resolve(self, url: str) -> str:
        if "xhslink." in url:
            return resolve_redirect(url, ("xiaohongshu.com",))
        return url

    @staticmethod
    def _note_id(url: str) -> str:
        patterns = (
            r"/(?:explore|item|discovery/item)/([a-f0-9]+)",
            r"/search_result/([a-f0-9]+)",
            r"/user/profile/[a-f0-9]+/([a-f0-9]+)",
            r"[?&]noteId=([a-f0-9]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def collect(self, url: str) -> ContentMeta:
        real_url = self._resolve(url)
        note_id = self._note_id(real_url)
        if not note_id:
            raise CollectorError(f"Could not find a Xiaohongshu note id in URL: {real_url}")

        raw = run_opencli(["xiaohongshu", "note", real_url, "-f", "json"], timeout=60)
        data = self._normalize_opencli(raw)
        if not data:
            raise AuthRequiredError(
                "Xiaohongshu returned no note data. Sign in using your normal browser and reconnect Browser Bridge."
            )

        title = self._text(data.get("title"))
        desc = self._text(data.get("desc") or data.get("description"))
        author_value = data.get("author")
        author = self._text(author_value)
        author_id = self._text(data.get("authorId") or data.get("user_id"))
        if isinstance(author_value, dict):
            author = self._text(author_value.get("nickname") or author_value.get("name"))
            author_id = author_id or self._text(author_value.get("userId") or author_value.get("id"))

        note_type_text = self._text(data.get("type") or "normal").lower()
        meta = ContentMeta(
            platform=self.platform,
            url=real_url,
            title=title or "小红书笔记",
            desc=desc,
            author=author,
            author_id=author_id,
            note_type=NoteType.VIDEO if note_type_text == "video" else NoteType.NORMAL,
            extra={"note_id": note_id},
        )

        image_list = data.get("imageList") or data.get("images") or []
        if isinstance(image_list, list):
            for image in image_list[:20]:
                if isinstance(image, str):
                    url_value = image
                elif isinstance(image, dict):
                    url_value = image.get("url") or image.get("urlDefault") or ""
                else:
                    continue
                if isinstance(url_value, str) and url_value.startswith("http"):
                    meta.image_list.append({"url": url_value})

        video = data.get("video") or data.get("media") or {}
        if isinstance(video, dict):
            meta.video_url = self._text(video.get("masterUrl") or video.get("playAddr"))
            capa = video.get("capa") if isinstance(video.get("capa"), dict) else {}
            duration = (capa or {}).get("duration") or video.get("duration")
            try:
                meta.video_duration = int(duration) if duration else None
            except (TypeError, ValueError):
                pass
            if meta.video_url:
                meta.note_type = NoteType.VIDEO

        interact = data.get("interactInfo") or {}
        if isinstance(interact, dict):
            meta.liked_count = parse_count(interact.get("likedCount") or interact.get("likeCount"))
            meta.collected_count = parse_count(interact.get("collectedCount") or interact.get("collectCount"))
            meta.comment_count = parse_count(interact.get("commentCount"))
            meta.share_count = parse_count(interact.get("shareCount"))
            meta.play_count = parse_count(interact.get("viewCount") or interact.get("playCount"))

        meta.liked_count = meta.liked_count if meta.liked_count is not None else parse_count(data.get("likes"))
        meta.collected_count = meta.collected_count if meta.collected_count is not None else parse_count(data.get("collects"))
        meta.comment_count = meta.comment_count if meta.comment_count is not None else parse_count(data.get("comments"))
        if meta.image_list and not meta.cover_url:
            meta.cover_url = meta.image_list[0]["url"]
        return meta

    def download(self, meta: ContentMeta, output_dir: str | Path) -> list[str]:
        out = Path(output_dir).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        before = {p.resolve() for p in out.rglob("*") if p.is_file()}
        run_opencli(
            ["xiaohongshu", "download", meta.url, "--output", str(out)],
            timeout=180,
            expect_json=False,
        )
        after = {p.resolve() for p in out.rglob("*") if p.is_file()}
        return [str(path) for path in sorted(after - before)]

    def user_items(self, user: str, limit: int = 20) -> list[dict[str, Any]]:
        profile = user if user.startswith("http") else f"https://www.xiaohongshu.com/user/profile/{user}"
        data = run_opencli(
            ["xiaohongshu", "user", profile, "-f", "json", "--limit", str(max(1, limit))],
            timeout=90,
        )
        if not isinstance(data, list):
            return []
        result: list[dict[str, Any]] = []
        for item in data[:limit]:
            note_id = self._text(item.get("id")).split("?")[0]
            create_time = 0
            if len(note_id) >= 8:
                try:
                    create_time = int(note_id[:8], 16)
                except ValueError:
                    pass
            url = self._text(item.get("url")) or (
                f"https://www.xiaohongshu.com/explore/{note_id}" if note_id else ""
            )
            result.append({
                "content_id": note_id,
                "title": self._text(item.get("title")),
                "create_time": create_time,
                "url": url,
                "digg_count": parse_count(item.get("likes")),
                "collect_count": parse_count(item.get("collects")),
                "comment_count": parse_count(item.get("comments")),
                "share_count": parse_count(item.get("shares")),
                "cover_url": self._text(item.get("cover")),
            })
        return result

    @staticmethod
    def _normalize_opencli(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list):
            result: dict[str, Any] = {}
            for item in raw:
                if isinstance(item, dict) and "field" in item:
                    result[str(item["field"])] = item.get("value")
            return result
        return {}

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (str, int, float)):
            return str(value)
        return ""
