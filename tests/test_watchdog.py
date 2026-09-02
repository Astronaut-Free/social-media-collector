import tempfile
import unittest
from pathlib import Path

from social_collector.models import BaseCollector, ContentMeta, NoteType, Platform
from social_collector.watchdog import WatchStore, Watchdog, parse_interval


class FakeCollector(BaseCollector):
    platform = Platform.DOUYIN
    def __init__(self, items): self.items = items
    def collect(self, url): return ContentMeta(platform=self.platform, url=url, title="full", note_type=NoteType.VIDEO)
    def download(self, meta, output_dir): return []
    def user_items(self, user, limit=20): return list(self.items)[:limit]


class WatchdogTests(unittest.TestCase):
    def test_first_run_builds_baseline_then_detects_new_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WatchStore(Path(tmp))
            store.add(platform=Platform.DOUYIN, user="creator-1", limit=20)
            collector = FakeCollector([{"content_id": "b", "url": "https://example.com/b"}, {"content_id": "a", "url": "https://example.com/a"}])
            watchdog = Watchdog(store=store, collector_factory=lambda _: collector)
            self.assertEqual(watchdog.run_once()["new_count"], 0)
            collector.items.insert(0, {"content_id": "c", "url": "https://example.com/c"})
            second = watchdog.run_once()
            self.assertEqual(second["new_count"], 1)
            self.assertEqual(second["results"][0]["new_items"][0]["item"]["content_id"], "c")

    def test_include_existing_emits_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WatchStore(Path(tmp))
            store.add(platform=Platform.DOUYIN, user="creator-1", limit=20)
            collector = FakeCollector([{"content_id": "a", "url": "https://example.com/a"}])
            result = Watchdog(store=store, collector_factory=lambda _: collector).run_once(include_existing=True, full_collect=True)
            self.assertEqual(result["new_count"], 1)
            self.assertEqual(result["results"][0]["new_items"][0]["meta"]["title"], "full")

    def test_feishu_latest_cursor_can_resume_without_local_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            collector = FakeCollector([{"content_id": "new", "url": "https://example.com/new"}, {"content_id": "old", "url": "https://example.com/old"}])
            result = Watchdog(store=WatchStore(Path(tmp)), collector_factory=lambda _: collector).run_once(monitors=[{"id": "feishu:rec1", "platform": "douyin", "user": "creator-1", "limit": 20, "latest_id": "old", "enabled": True}])
            self.assertEqual(result["new_count"], 1)
            self.assertEqual(result["results"][0]["new_items"][0]["item"]["content_id"], "new")

    def test_interval_parser(self):
        self.assertEqual(parse_interval("30m"), 1800)
        self.assertEqual(parse_interval("2h"), 7200)
        self.assertEqual(parse_interval("60s"), 60)
        with self.assertRaises(ValueError): parse_interval("30s")


if __name__ == "__main__": unittest.main()
