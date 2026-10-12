# 飞书素材图片读取 MCP（试运行）

> 目的：复用本项目已有的采集器、Watchdog 和 Feishu API 代码，而不是重建爬虫。此集成属于**只读、链接型 MVP**，尚未完成持久化原图附件与端到端授权验收。

## 现有能力

- `python cli.py feishu setup` 会补齐缺少的字段，不改写同名字段的已有类型。
- 新增素材时，`图片数量` 和 `图片列表JSON` 保存采集器的 `image_list`（最多 20 张，保持原序）。
- 本地 MCP 提供 3 个工具：`list_xiaohongshu_notes`、`get_note_images`、`read_note_image`。
- `read_note_image` 会尝试将**已授权可访问**的图片返回为 MCP Image 内容，限制 HTTPS 小红书域名、图片类型及 8 MB 大小。带签名图片链接可能过期或拒绝外部访问。

## 前置条件

1. 飞书开放平台创建/使用已有自建应用，申请多维表格读权限（写入场景另需写权限），授予目标 Base 访问权限。
2. 在本机环境变量设置 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_BITABLE_APP_TOKEN`。**切勿将 App Secret、访问 Token、浏览器 Cookie 提交到 Git 或发送到聊天中。**
3. 安装 Python 3.10+ 和可选依赖：

```bash
python -m pip install -e '.[mcp]'
python cli.py feishu status
python cli.py feishu setup
python -m unittest discover -s tests
```

4. 新增一条有 `image_list` 的素材，确认飞书中 `图片列表JSON` 与 `图片数量` 有值。旧记录**不会自动回填**，需要单独补数流程。

## 在本地 MCP 客户端配置

示例 stdio 配置（把路径替换成项目绝对路径，不要把凭证写死在公共配置或仓库）：

```json
{
  "mcpServers": {
    "feishu-image-reader": {
      "command": "python",
      "args": ["-m", "social_collector.mcp_server"],
      "cwd": "/absolute/path/to/social-media-collector"
    }
  }
}
```

若使用的客户端不支持 `cwd`，在项目目录启动客户端或用受信任的启动脚本。MCP 子进程需要继承本机飞书环境变量。可通过 MCP Inspector 逐一试用 3 个工具。

## ChatGPT 接入边界

此仓库提供的是 **本地 stdio MCP**；ChatGPT 需要受支持的远程 MCP 接口与授权。**不能把 localhost 直接当作 ChatGPT 可访问服务**，也不要把不带身份认证的服务公开到互联网。只有完成安全部署、创建自定义插件、用户授权后，ChatGPT 会话才能读取飞书资料。

当前未执行飞书真实 API 的端到端测试，也没有浏览器登录会话，因此不能保证每个小红书 CDN 链接都能下载。为了长期可靠分析，应继续建设媒体落地/对象存储或飞书附件下载链路，并保留来源 provenance 和图片序号。

## 验收检查

1. `feishu status` 权限成功；
2. 新笔记 `图片数量` 与 `图片列表JSON` 正确；
3. MCP 列表能找到对应 `content_id`；
4. `get_note_images` 返回所有图片，次序一致；
5. `read_note_image` 对授权可读样本返回 Image 内容，过期链接给出明确失败；
6. 主分支未受影响，PR 审查通过后再合并。
