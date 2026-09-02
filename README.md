# Social Media Collector

从 Taiyi 中独立摘出的 **抖音 / 小红书 / Bilibili** 内容采集器，并加入独立的 **Watchdog 博主监控** 与可选 **飞书多维表格集成**。

这个仓库与 Taiyi 完全独立：不依赖飞书也能运行；连接飞书后可以自动创建采集所需的数据表和字段，并由 Watchdog 自动发现新作品、完整采集元数据、写入飞书。

> 适用范围：采集你有权访问的公开内容，或使用你自己的正常登录会话。项目不会绕过验证码、登录、访问控制、限流或平台限制。

## 支持能力

| 能力 | Bilibili | 抖音 | 小红书 |
| --- | --- | --- | --- |
| 单条元数据 | ✅ | ✅ | ✅ |
| 媒体下载 | ✅ | ✅ | ✅ |
| 博主/主页列表 | ✅ | ✅ | ✅ |
| Watchdog 增量监控 | ✅ | ✅ | ✅ |
| 飞书自动入库 | ✅ | ✅ | ✅ |

## 首次安装

```bash
git clone https://github.com/Astronaut-Free/social-media-collector.git
cd social-media-collector
python bootstrap.py --all
python cli.py doctor --json
```

## 基础采集

```bash
python cli.py collect "<URL>"
python cli.py download "<URL>" --output downloads
python cli.py user "<creator>" --platform douyin --limit 20
python cli.py user "<creator>" --platform xiaohongshu --limit 20
python cli.py user "<creator>" --platform bilibili --limit 20
```

## Watchdog 博主监控

```bash
python cli.py watch add "<creator>" --platform douyin --name "博主A"
python cli.py watch list
python cli.py watch run --source local
python cli.py watch start --source local --interval 30m
```

Watchdog 本地状态保存在 `data/watchlist.json` 与 `data/watch_state.json`，`data/` 默认不提交 Git。

第一次检查默认只建立基线，不会把已有历史作品全部当成新作品。需要当前可见历史内容时：

```bash
python cli.py watch run --source local --include-existing --full-collect
```

之后按稳定内容 ID 去重，只输出真正新增的作品。最低监控间隔为 60 秒。

## 飞书多维表格自动搭建

飞书是可选能力。给企业自建应用配置多维表格读写/管理权限后设置：

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
```

已有多维表格时可设置：

```bash
FEISHU_BITABLE_APP_TOKEN=bascn_xxx
```

不设置 `FEISHU_BITABLE_APP_TOKEN` 时，`feishu setup` 会尝试创建新的 `Social Media Collector` 多维表格；可用 `FEISHU_FOLDER_TOKEN` 指定目录。

```bash
python cli.py feishu setup
python cli.py feishu status
```

`setup` 可重复执行：只补缺少字段；同名字段类型不一致只报告，不擅自修改已有结构。

### 博主监控池

| 字段 | 类型 |
| --- | --- |
| 博主名称 | 文本 |
| 来源平台 | 单选：抖音/小红书/B站 |
| 博主ID | 文本 |
| 主页链接 | 链接 |
| 启用监控 | 复选框 |
| 每次抓取数量 | 数字 |
| 最新发布ID | 文本 |
| 最近检查时间 | 日期 |
| 监控状态 | 单选 |
| 最后错误 | 文本 |
| 全量爬取周期 | 单选 |
| 全量爬取状态 | 文本 |
| 备注 | 文本 |

`全量爬取周期/状态` 保留为与 Taiyi 监控合同兼容的字段；当前 standalone Watchdog 核心是增量监控。

### 素材内容池

字段沿用 Taiyi 的采集侧合同，只保留独立采集需要的部分：

| 字段 | 类型 |
| --- | --- |
| 素材标题 | 文本 |
| 来源平台 | 单选 |
| 素材博主 | 文本 |
| 博主ID | 文本 |
| 内容ID | 文本 |
| 内容形式 | 单选：视频/图文 |
| 素材正文 | 文本 |
| 素材发布时间 | 日期 |
| 内容全文 | 文本 |
| 原始链接 | 链接 |
| 封面链接 | 链接 |
| 视频时长 | 数字（秒） |
| 收藏时间 | 日期 |
| 博主粉丝数 | 数字 |
| 点赞数 | 数字 |
| 收藏数 | 数字 |
| 评论数 | 数字 |
| 分享数 | 数字 |
| 播放量/阅读量 | 数字 |
| 互动数据更新时间 | 日期 |
| 去参链接 | 文本 |
| 采集状态 | 单选 |

AI 拆解、分类、公式、附件等 Taiyi 下游字段没有复制，因为不属于独立采集器职责。

添加飞书监控博主：

```bash
python cli.py feishu add-monitor "<creator>" --platform xiaohongshu --name "博主A" --limit 20
```

也可以直接在飞书“博主监控池”里新增/停用行。Watchdog 每轮都会重新读取表格。

## 飞书 + Watchdog 自动抓取

配置飞书凭证后，默认 `--source auto` 优先用飞书：

```bash
python cli.py watch run
python cli.py watch start --interval 30m
```

流程：

```text
博主监控池
  ↓
读取已启用博主
  ↓
user_items() 获取最新作品
  ↓
本地 seen_ids + 飞书 最新发布ID 判断增量
  ↓
发现新作品
  ↓
collect() 完整采集
  ↓
按 内容ID 去重
  ↓
写入 素材内容池
  ↓
更新 最新发布ID / 最近检查时间 / 监控状态
```

换电脑时即使没有本地 watch_state，也会利用飞书的“最新发布ID”恢复增量游标。

第一次就要写入当前可见历史作品：

```bash
python cli.py watch run --source feishu --include-existing
```

## 环境与登录

小红书和部分抖音博主列表使用 OpenCLI，需要 Node.js 20+ 与用户自己的正常浏览器登录态：

```bash
python bootstrap.py --opencli
```

需要登录时由用户正常登录并根据 `opencli doctor` 连接 Browser Bridge。本项目不绕过登录、验证码或平台访问限制。

Bilibili 等音视频合并可能需要 FFmpeg。`doctor` 会检查。

Cookie 可通过 `DOUYIN_COOKIE_FILE`、`BILIBILI_COOKIE_FILE` 或 `SOCIAL_COLLECTOR_COOKIE_FILE` 指向用户自己的 Netscape cookie 文件；Cookie、飞书密钥和本地状态都不应提交 Git。

## 目录

```text
social_collector/
├── collectors/
├── watchdog.py
├── feishu.py
├── feishu_schema.py
├── models.py
├── opencli.py
├── router.py
├── doctor.py
└── cli.py
```

## 和 Taiyi 的关系

采集行为参考并抽取自 Taiyi 的三个平台插件和采集字段合同；该仓库移除了 Taiyi 的飞书适配器、队列、Worker、数据库、Agent 编排等专属依赖。**Taiyi 原仓库不需要因此做任何修改。**
