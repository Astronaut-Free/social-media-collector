"""Read-only MCP tools for Feishu-stored Xiaohongshu image references.

Run with: python -m social_collector.mcp_server
Requires: pip install -e '.[mcp]'

This is a local STDIO MCP server. Connecting it to ChatGPT requires an
independently secured, remotely reachable MCP deployment; see docs/FEISHU_MCP.md.
"""
from __future__ import annotations

from urllib.parse import urlsplit

import requests
from mcp.server.fastmcp import FastMCP, Image

from .feishu import FeishuClient, _text
from .feishu_schema import CONTENT_TABLE_NAME
from .image_manifest import decode_image_list

mcp = FastMCP("social-media-collector-feishu-images")
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_HOSTS = ("xhscdn.com", "xiaohongshu.com")
ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpeg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}


def _content_records() -> list[dict]:
    client = FeishuClient.from_env()
    if not client.app_token:
        raise ValueError("Missing Feishu Base token; first run 'python cli.py feishu setup' locally.")
    table = next((row for row in client.list_tables() if row.get("name") == CONTENT_TABLE_NAME), None)
    if not table:
        raise ValueError("Feishu 素材内容池 not found; run 'python cli.py feishu setup' locally.")
    return client.list_records(str(table["table_id"]))


def _find_note(content_id: str) -> dict:
    for row in _content_records():
        fields = row.get("fields") or {}
        if _text(fields.get("内容ID")) == content_id:
            return row
    raise ValueError(f"No material record found for content_id={content_id!r}")


@mcp.tool()
def list_xiaohongshu_notes(limit: int = 20) -> list[dict]:
    """List up to 50 recent Xiaohongshu entries stored in Feishu's 素材内容池."""
    limit = max(1, min(int(limit), 50))
    notes = []
    for row in reversed(_content_records()):
        fields = row.get("fields") or {}
        if _text(fields.get("来源平台")) != "小红书":
            continue
        notes.append({
            "record_id": row.get("record_id"),
            "content_id": _text(fields.get("内容ID")),
            "title": _text(fields.get("素材标题")),
            "author": _text(fields.get("素材博主")),
            "image_count": len(decode_image_list(fields.get("图片列表JSON"))),
            "source": _text(fields.get("原始链接")),
        })
        if len(notes) >= limit:
            break
    return notes


@mcp.tool()
def get_note_images(content_id: str) -> dict:
    """Get all stored image references of a note, in their original image order."""
    if not content_id.strip():
        raise ValueError("content_id is required")
    fields = _find_note(content_id)["fields"]
    urls = decode_image_list(fields.get("图片列表JSON"))
    return {
        "content_id": content_id,
        "title": _text(fields.get("素材标题")),
        "author": _text(fields.get("素材博主")),
        "image_count": len(urls),
        "images": [{"index": index, **item} for index, item in enumerate(urls)],
        "warning": "Source image links may expire or require the authorized browser session.",
    }


def _safe_xhs_image_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        return (
            parts.scheme == "https"
            and parts.username is None
            and parts.password is None
            and any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_IMAGE_HOSTS)
        )
    except ValueError:
        return False


@mcp.tool()
def read_note_image(content_id: str, image_index: int = 0) -> Image:
    """Read a public/accessible Xiaohongshu image as actual image bytes for visual analysis.

    No login bypass, no redirect following, and no fetching arbitrary internet hosts.
    Fails explicitly when the image link is expired or access is restricted.
    """
    fields = _find_note(content_id)["fields"]
    images = decode_image_list(fields.get("图片列表JSON"))
    if image_index < 0 or image_index >= len(images):
        raise ValueError("Image index out of range; use get_note_images first.")
    url = images[image_index]["url"]
    if not _safe_xhs_image_url(url):
        raise ValueError("Image URL is not an approved Xiaohongshu HTTPS image host.")
    with requests.get(url, stream=True, timeout=20, allow_redirects=False) as response:
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError("Redirects are disabled for image retrieval.")
        mime = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        fmt = ALLOWED_IMAGE_TYPES.get(mime)
        if not fmt:
            raise ValueError("The image server did not return a supported image MIME type.")
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            total += len(chunk)
            if total > MAX_IMAGE_BYTES:
                raise ValueError("Image exceeds the 8 MB safety limit.")
            chunks.append(chunk)
    return Image(data=b"".join(chunks), format=fmt)


if __name__ == "__main__":
    mcp.run()
