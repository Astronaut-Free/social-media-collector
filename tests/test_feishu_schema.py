import unittest

from social_collector.feishu_schema import CONTENT_FIELDS, MONITOR_FIELDS, CHECKBOX, DATE, NUMBER, SINGLE_SELECT, TEXT, URL


class FeishuSchemaTests(unittest.TestCase):
    def test_field_names_are_unique(self):
        self.assertEqual(len(CONTENT_FIELDS), len({field.name for field in CONTENT_FIELDS}))
        self.assertEqual(len(MONITOR_FIELDS), len({field.name for field in MONITOR_FIELDS}))

    def test_required_collection_fields_exist(self):
        types = {field.name: field.type for field in CONTENT_FIELDS}
        self.assertEqual(types["素材标题"], TEXT)
        self.assertEqual(types["来源平台"], SINGLE_SELECT)
        self.assertEqual(types["原始链接"], URL)
        self.assertEqual(types["素材发布时间"], DATE)
        self.assertEqual(types["点赞数"], NUMBER)
        self.assertEqual(types["去参链接"], TEXT)

    def test_required_monitor_fields_exist(self):
        types = {field.name: field.type for field in MONITOR_FIELDS}
        self.assertEqual(types["博主名称"], TEXT)
        self.assertEqual(types["来源平台"], SINGLE_SELECT)
        self.assertEqual(types["启用监控"], CHECKBOX)
        self.assertEqual(types["最近检查时间"], DATE)
        self.assertEqual(types["主页链接"], URL)


if __name__ == "__main__": unittest.main()
