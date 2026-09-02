from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Platform(str, Enum):
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    BILIBILI = "bilibili"


class NoteType(str, Enum):
    VIDEO = "video"
    NORMAL = "normal"


@dataclass
class ContentMeta:
    platform: Platform
    url: str
    title: str = ""
    author: str = ""
    author_id: str = ""
    author_url: str = ""
    note_type: NoteType = NoteType.NORMAL
    desc: str = ""
    video_url: str = ""
    audio_url: str = ""
    cover_url: str = ""
    image_list: list[dict[str, Any]] = field(default_factory=list)
    publish_time: str = ""
    liked_count: int | None = None
    collected_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    play_count: int | None = None
    follower_count: int | None = None
    video_duration: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["platform"] = self.platform.value
        data["note_type"] = self.note_type.value
        return data


class CollectorError(RuntimeError):
    """Base error for a collector operation."""


class DependencyError(CollectorError):
    """A required runtime dependency is missing."""


class AuthRequiredError(CollectorError):
    """The platform requires the user's own authenticated browser/session."""


class BaseCollector(ABC):
    platform: Platform
    supported_domains: tuple[str, ...] = ()

    @abstractmethod
    def collect(self, url: str) -> ContentMeta:
        raise NotImplementedError

    @abstractmethod
    def download(self, meta: ContentMeta, output_dir: str | Path) -> list[str]:
        raise NotImplementedError

    def user_items(self, user: str, limit: int = 20) -> list[dict[str, Any]]:
        raise CollectorError(f"{self.platform.value} does not implement user listing")
