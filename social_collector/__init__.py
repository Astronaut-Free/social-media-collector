"""Standalone collectors for Douyin, Xiaohongshu and Bilibili."""

from .models import ContentMeta, Platform
from .router import get_collector, infer_platform

__all__ = ["ContentMeta", "Platform", "get_collector", "infer_platform"]
__version__ = "0.1.0"
