from __future__ import annotations

from urllib.parse import urlsplit

from .collectors import BilibiliCollector, DouyinCollector, XiaohongshuCollector
from .models import BaseCollector, CollectorError, Platform


_COLLECTORS: dict[Platform, type[BaseCollector]] = {
    Platform.DOUYIN: DouyinCollector,
    Platform.XIAOHONGSHU: XiaohongshuCollector,
    Platform.BILIBILI: BilibiliCollector,
}


def infer_platform(url: str) -> Platform:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    for platform, collector_type in _COLLECTORS.items():
        if any(host == domain or host.endswith("." + domain) for domain in collector_type.supported_domains):
            return platform
    raise CollectorError(f"Unsupported URL: {url}")


def get_collector(platform: Platform | str) -> BaseCollector:
    if isinstance(platform, str):
        try:
            platform = Platform(platform.lower())
        except ValueError as exc:
            raise CollectorError(f"Unsupported platform: {platform}") from exc
    return _COLLECTORS[platform]()
