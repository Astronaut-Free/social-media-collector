import unittest

from social_collector.models import Platform
from social_collector.router import infer_platform


class RouterTests(unittest.TestCase):
    def test_bilibili(self):
        self.assertEqual(infer_platform("https://www.bilibili.com/video/BV1234567890"), Platform.BILIBILI)

    def test_douyin(self):
        self.assertEqual(infer_platform("https://v.douyin.com/abc"), Platform.DOUYIN)

    def test_xiaohongshu_cn_shortlink(self):
        self.assertEqual(infer_platform("https://xhslink.cn/a/abc"), Platform.XIAOHONGSHU)


if __name__ == "__main__":
    unittest.main()
