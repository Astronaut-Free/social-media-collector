from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TEXT = 1
NUMBER = 2
SINGLE_SELECT = 3
MULTI_SELECT = 4
DATE = 5
CHECKBOX = 7
URL = 15
ATTACHMENT = 17

CONTENT_TABLE_NAME = "素材内容池"
MONITOR_TABLE_NAME = "博主监控池"


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: int
    options: tuple[str, ...] = ()

    def to_api(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"field_name": self.name, "type": self.type}
        if self.options and self.type in (SINGLE_SELECT, MULTI_SELECT):
            payload["property"] = {"options": [{"name": option} for option in self.options]}
        return payload


CONTENT_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("素材标题", TEXT),
    FieldSpec("来源平台", SINGLE_SELECT, ("抖音", "小红书", "B站")),
    FieldSpec("素材博主", TEXT),
    FieldSpec("博主ID", TEXT),
    FieldSpec("内容ID", TEXT),
    FieldSpec("内容形式", SINGLE_SELECT, ("视频", "图文")),
    FieldSpec("素材正文", TEXT),
    FieldSpec("素材发布时间", DATE),
    FieldSpec("内容全文", TEXT),
    FieldSpec("原始链接", URL),
    FieldSpec("封面链接", URL),
    FieldSpec("图片数量", NUMBER),
    FieldSpec("图片列表JSON", TEXT),
    FieldSpec("视频时长", NUMBER),
    FieldSpec("收藏时间", DATE),
    FieldSpec("博主粉丝数", NUMBER),
    FieldSpec("点赞数", NUMBER),
    FieldSpec("收藏数", NUMBER),
    FieldSpec("评论数", NUMBER),
    FieldSpec("分享数", NUMBER),
    FieldSpec("播放量/阅读量", NUMBER),
    FieldSpec("互动数据更新时间", DATE),
    FieldSpec("去参链接", TEXT),
    FieldSpec("采集状态", SINGLE_SELECT, ("已发现", "已采集", "采集失败")),
)


MONITOR_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("博主名称", TEXT),
    FieldSpec("来源平台", SINGLE_SELECT, ("抖音", "小红书", "B站")),
    FieldSpec("博主ID", TEXT),
    FieldSpec("主页链接", URL),
    FieldSpec("启用监控", CHECKBOX),
    FieldSpec("每次抓取数量", NUMBER),
    FieldSpec("最新发布ID", TEXT),
    FieldSpec("最近检查时间", DATE),
    FieldSpec("监控状态", SINGLE_SELECT, ("未初始化", "正常", "异常")),
    FieldSpec("最后错误", TEXT),
    FieldSpec("全量爬取周期", SINGLE_SELECT, ("不爬取", "近30天", "近90天", "全部")),
    FieldSpec("全量爬取状态", TEXT),
    FieldSpec("备注", TEXT),
)


TABLE_SCHEMAS: dict[str, tuple[FieldSpec, ...]] = {
    CONTENT_TABLE_NAME: CONTENT_FIELDS,
    MONITOR_TABLE_NAME: MONITOR_FIELDS,
}
