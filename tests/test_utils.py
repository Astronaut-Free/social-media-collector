import unittest

from social_collector.collectors.bilibili import BilibiliCollector
from social_collector.collectors.xiaohongshu import XiaohongshuCollector
from social_collector.utils import parse_count


class UtilityTests(unittest.TestCase):
    def test_parse_count(self):
        self.assertEqual(parse_count("1.9万"), 19000)
        self.assertEqual(parse_count("3,726"), 3726)
        self.assertIsNone(parse_count(""))

    def test_bilibili_ids(self):
        bvid, aid = BilibiliCollector._ids("https://www.bilibili.com/video/BV1xx411c7mD")
        self.assertEqual(bvid, "BV1xx411c7mD")
        self.assertEqual(aid, "")

    def test_xhs_note_id(self):
        value = XiaohongshuCollector._note_id("https://www.xiaohongshu.com/explore/64abc123def456")
        self.assertEqual(value, "64abc123def456")


if __name__ == "__main__":
    unittest.main()
