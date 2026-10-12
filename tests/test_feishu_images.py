import unittest

from social_collector.image_manifest import decode_image_list, normalize_image_list


class ImageManifestTests(unittest.TestCase):
    def test_normalize_deduplicates_and_preserves_order(self):
        items = [{"url": "https://sns-webpic-qc.xhscdn.com/a"}, "https://sns-webpic-qc.xhscdn.com/b", {"url": "https://sns-webpic-qc.xhscdn.com/a"}, {"url": "not-a-url"}]
        self.assertEqual(normalize_image_list(items), [
            {"url": "https://sns-webpic-qc.xhscdn.com/a"},
            {"url": "https://sns-webpic-qc.xhscdn.com/b"},
        ])

    def test_decode_bitable_rich_text(self):
        value = '[{"url":"https://sns-webpic-qc.xhscdn.com/a"}]'
        self.assertEqual(decode_image_list([{"text": value}]), [{"url": "https://sns-webpic-qc.xhscdn.com/a"}])

    def test_decode_invalid_json_returns_empty(self):
        self.assertEqual(decode_image_list("not-json"), [])


if __name__ == "__main__":
    unittest.main()
