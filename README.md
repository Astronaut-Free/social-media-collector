# Social Media Collector

从 Taiyi 中独立摘出的三个内容采集器：**抖音 / 小红书 / Bilibili**。

这个仓库与 Taiyi 完全独立：不依赖飞书、数据库、Agent 编排、Taiyi `core/` 或 Taiyi 的目录结构，可以单独分享、clone 和运行。

> 适用范围：采集你有权访问的公开内容或使用你自己的正常登录会话。项目不会绕过验证码、登录、访问控制或平台限制。

## 支持能力

| 平台 | 单条元数据 | 媒体下载 | 博主/主页列表 | 主要运行路径 |
| --- | --- | --- | --- | --- |
| Bilibili | ✅ | ✅ | ✅ | 官方网页 API + yt-dlp |
| 抖音 | ✅ | ✅ | ✅ | yt-dlp / 自己的登录 Cookie；主页列表使用 OpenCLI |
| 小红书 | ✅ | ✅ | ✅ | OpenCLI + 用户自己的浏览器登录会话 |

## 最快使用方式

新电脑 clone 后：

```bash
git clone https://github.com/Astronaut-Free/social-media-collector.git
cd social-media-collector
python bootstrap.py --all
```

然后运行环境检查：

```bash
# Windows
.venv\Scripts\python.exe cli.py doctor --json

# macOS / Linux
.venv/bin/python cli.py doctor --json
```

如果你是在 Codex / Claude Code 等 Coding Agent 里打开仓库，直接告诉它：

> 按 AGENTS.md 完成环境安装，然后采集这个链接：<URL>

Agent 会先运行 bootstrap/doctor，再执行采集命令。

## 统一 CLI

### 1. 检查环境

```bash
python cli.py doctor --json
```

### 2. 单条采集

平台会根据 URL 自动判断：

```bash
python cli.py collect "https://www.bilibili.com/video/BV..."
python cli.py collect "https://v.douyin.com/..."
python cli.py collect "https://www.xiaohongshu.com/explore/..."
```

### 3. 下载媒体

```bash
python cli.py download "<URL>" --output downloads
```

### 4. 获取博主近期内容

```bash
python cli.py user "<抖音 sec_uid>" --platform douyin --limit 20
python cli.py user "<小红书用户ID或主页URL>" --platform xiaohongshu --limit 20
python cli.py user "<B站 UID或主页URL>" --platform bilibili --limit 20
```

## 环境组成

### Python

要求 Python 3.10+。`bootstrap.py` 会：

1. 创建 `.venv`
2. 更新 pip/setuptools/wheel
3. 安装最小 Python 依赖

不会安装 Taiyi 的完整 `requirements.txt`。

### FFmpeg

Bilibili 等平台的视频、音频可能是分离流，yt-dlp 合并时需要 FFmpeg。`doctor` 会检查它是否存在。

### Node.js + OpenCLI

小红书采集和抖音博主列表使用 OpenCLI。要求 Node.js 20+。

如果 Node 已存在：

```bash
python bootstrap.py --opencli
```

OpenCLI 会安装到仓库自己的 `.tools/`，不要求全局 npm 安装。

小红书等需要登录态的功能仍然需要用户在正常浏览器中完成登录，并按 `opencli doctor` 的提示连接 Browser Bridge。登录和验证码不会由本项目自动绕过。

## Cookie

对于 yt-dlp 需要登录态的场景，可以使用**你自己的** Netscape 格式 cookie 文件：

```bash
DOUYIN_COOKIE_FILE=/path/to/douyin.txt
BILIBILI_COOKIE_FILE=/path/to/bilibili.txt
```

也支持统一变量：

```bash
SOCIAL_COLLECTOR_COOKIE_FILE=/path/to/cookies.txt
```

仓库默认忽略 `cookies/`、`cookies.json`、`.env` 等，避免误提交登录凭证。

## Python 调用

```python
from social_collector import get_collector

collector = get_collector("bilibili")
meta = collector.collect("https://www.bilibili.com/video/BV...")
print(meta.to_dict())
```

三个 Collector 都遵循同一接口：

```python
collector.collect(url)
collector.download(meta, output_dir)
collector.user_items(user_id_or_profile_url, limit=20)
```

## 目录

```text
social-media-collector/
├── social_collector/
│   ├── collectors/
│   │   ├── douyin.py
│   │   ├── xiaohongshu.py
│   │   └── bilibili.py
│   ├── models.py
│   ├── opencli.py
│   ├── router.py
│   ├── doctor.py
│   └── cli.py
├── bootstrap.py
├── cli.py
├── doctor.py
├── requirements.txt
├── pyproject.toml
├── AGENTS.md
└── README.md
```

## 和 Taiyi 的关系

代码来源和行为参考 Taiyi 现有 `plugins/douyin`、`plugins/xiaohongshu`、`plugins/bilibili`，但此仓库已经移除 Taiyi 专属依赖。Taiyi 原仓库无需因此做任何修改。
