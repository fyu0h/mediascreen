# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

皇岗边检站全球舆情态势感知平台 - 基于 Flask 的实时新闻聚合与风险监控系统，从全球约30个新闻源抓取新闻，提供可视化仪表盘、风控告警、AI 舆情分析、新闻预览/翻译和 Telegram 群组监控。

## 技术栈

- **后端**: Python 3.10+ / Flask 2.3+
- **数据库**: MongoDB (pymongo 4.5+)，数据库名 `news_dashboard`
- **前端**: 原生 HTML/CSS/JS + ECharts (图表) + Leaflet (地图)
- **生产服务器**: Waitress (WSGI)
- **Telegram**: Telethon (异步客户端) + aiohttp (Webhook 推送)
- **AI/LLM**: 多提供商支持 (SiliconFlow / OpenAI / Google Gemini / Poixe / 自定义)
- **浏览器自动化**: Playwright + stealth（新闻预览截图、URL 重定向解析）

## 常用命令

| 命令 | 描述 |
| --- | --- |
| `pip install -r requirements.txt` | 安装依赖 |
| `python app.py` | 开发服务器 (localhost:5000) |
| `python run_production.py` | 生产环境 (Waitress, 0.0.0.0:5000) |
| `mongod` | 启动 MongoDB |

无自动化测试。

## 架构概览

```
app.py                        # Flask 入口，create_app() 工厂函数，注册蓝图和中间件
config.py                     # Config 类：MongoDB 连接、集合名常量、新闻源元数据、风控关键词
settings.json                 # 运行时配置（LLM多提供商、爬虫参数、Telegram、翻译）
├── models/
│   ├── mongo.py              # MongoDB 操作层（单例连接池，查询/聚合/统计/风控关键词/告警已读）
│   ├── plugins.py            # 插件订阅管理
│   ├── settings.py           # settings.json 读写、LLM 多提供商配置、AI 总结提示词
│   ├── telegram.py           # Telegram 数据模型（账号/群组/消息/报警）
│   ├── users.py              # 用户认证（session，默认 admin/admin123）
│   ├── sites.py              # 站点管理（域名→国家推断、坐标、sitemap 检测）
│   ├── tasks.py              # 后台任务管理
│   ├── logger.py             # 日志系统（操作/请求/系统日志）
│   └── console_log.py        # 实时控制台日志（stdout/stderr 拦截，环形缓冲区，SSE 推送）
├── plugins/
│   ├── base.py               # BasePlugin 抽象基类
│   ├── registry.py           # PluginRegistry 全局单例注册表
│   ├── crawler.py            # 爬虫引擎（BeautifulSoup）
│   ├── parsers.py            # 站点专用解析器集合（40KB+，每站点一个函数）
│   ├── scheduler.py          # RSS 定时调度器
│   ├── crawl_scheduler.py    # 全量定时爬取调度器
│   ├── translator.py         # 标题翻译（多 LLM 提供商）
│   └── builtin/              # 4个内置插件（港台/亚洲/国际/政府移民媒体）
├── services/
│   └── telegram_monitor.py   # Telegram 群组实时监控服务
├── routes/
│   ├── api.py                # REST API（160+ 端点，/api/* 前缀）
│   └── views.py              # 页面渲染（/, /login, /logout）
├── templates/
│   ├── index.html            # 主仪表盘（94KB）
│   └── login.html            # 登录页
├── static/
│   ├── js/dashboard.js       # 前端逻辑（原生 JS）
│   ├── css/dashboard.css     # 样式（科技深色主题）
│   ├── images/               # 静态图片资源
│   └── uploads/              # 用户上传文件
└── docs/
    ├── plans/                # 开发计划文档
    └── reports/              # 报告文档
```

## 核心架构要点

### 数据流
插件层 → 爬虫/解析器 → 翻译（非中文标题）→ MongoDB `news_articles`（按 `loc` 去重）→ REST API → 前端仪表盘

### 插件系统
- 继承 `BasePlugin`，实现 `get_sites()` 返回站点配置列表
- 每个站点配置包含：`id`, `name`, `url`, `domain`, `country_code`, `coords`, `fetch_method`, `sitemap_url`
- 4种抓取方式：`sitemap`（XML）、`crawler`（全量爬取）、`scheduler`（RSS 定时）、`special`（专用解析器）
- 新增站点解析器在 `plugins/parsers.py` 中添加对应函数
- 插件通过 `PluginRegistry` 全局注册表管理
- 4个内置插件：`hk_tw_media`（港台媒体）、`asian_chinese_media`（亚洲华语）、`international_media`（国际媒体）、`government_immigration`（政府移民）

### MongoDB 关键集合
- `news_articles`：新闻文章（`loc` 唯一索引）
- `plugin_subscriptions`：插件订阅配置（`plugin_id` + `site_id` 唯一）
- `risk_keywords`：风控关键词（high/medium/low 三级）
- `alert_reads`：告警已读记录
- `telegram_messages` / `telegram_alerts`：Telegram 消息和报警
- `telegram_accounts` / `telegram_groups` / `telegram_keywords`：Telegram 配置
- `users`：用户（角色 admin/viewer）
- `ai_summaries`：AI 舆情总结历史
- `logs`：系统日志

### API 模块分区（routes/api.py, 4000+ 行, 160+ 端点）

| 模块 | 端点前缀 | 功能 |
| --- | --- | --- |
| 认证 | `/api/auth/*` | 登录状态、修改密码、健康检查 |
| 统计 | `/api/stats/*` | 概览、实时、来源、趋势、国家 |
| 文章 | `/api/articles` | 分页列表、筛选搜索 |
| 地图 | `/api/map/*` | 地图标记数据 |
| 新闻源 | `/api/sources/*` | 源列表、详情 |
| 风控 | `/api/risk/*` | 关键词CRUD、告警列表、日历、已读标记、统计趋势 |
| 站点 | `/api/sites/*` | 站点CRUD（旧接口，部分已禁用） |
| 插件 | `/api/plugins/*` | 插件列表、站点开关、抓取方式、定时更新 |
| 设置 | `/api/settings/*` | 系统设置、布局配置、值班人员 |
| 爬虫 | `/api/crawl/*` | 后台任务爬虫（启动/状态/取消/历史）、SSE 流式进度 |
| 调度器 | `/api/scheduler/*` | 调度器状态、手动触发、定时爬取配置 |
| 日志 | `/api/logs/*` | 日志列表/详情/统计/清空 |
| 控制台 | `/api/console/*` | SSE 实时输出流、历史、清空 |
| 舆情总结 | `/api/summary/*` | AI 总结生成、历史、提示词管理 |
| 翻译 | `/api/translation/*` | 翻译设置、提示词、API 测试 |
| Telegram | `/api/telegram/*` | 账号/群组/关键词/报警/消息/统计/Webhook/监控控制 |
| 新闻预览 | `/api/news/preview` | 智能正文提取（回退链：正文→截图→缓存） |
| 新闻翻译 | `/api/news/translate` | 正文内容块翻译 |
| 图片代理 | `/api/proxy/image` | 服务端中转外部图片 |

### 认证
Session 认证，所有 `/api/*` 端点需登录（`/api/health` 除外）。默认管理员 `admin/admin123`。

### API 响应格式
```json
{"success": true, "data": {...}}
```

### 配置层次
- `config.py`：静态配置（支持环境变量覆盖 MongoDB 连接、SECRET_KEY 等）
- `settings.json`：运行时配置，通过 `models/settings.py` 读写，通过 `/api/settings` 端点管理
  - **LLM 多提供商**：SiliconFlow / OpenAI / Gemini / Poixe / 自定义（AI总结和翻译各自独立配置）
  - **爬虫参数**：超时、最大文章数、User-Agent、定时全量爬取
  - **Telegram**：Webhook URL、监控开关
  - **翻译**：独立的提供商/模型/提示词配置
  - **布局**：仪表盘可拖拽模块布局持久化

### LLM 提供商（settings.py 预设）
| 提供商 | API URL | 代表模型 |
| --- | --- | --- |
| SiliconFlow | `api.siliconflow.cn` | DeepSeek-V3, Qwen2.5 |
| OpenAI | `api.openai.com` | GPT-4o, GPT-3.5 |
| Google Gemini | `generativelanguage.googleapis.com` | Gemini 2.5 Pro |
| Poixe | `api.poixe.com` | GPT-5.2, GPT-4o |
| 自定义 | 用户自定义 | 自定义 |

## 代码规范

1. **语言**: 所有代码注释和 Claude 回复必须使用**中文**
2. **完整性**: 严禁省略代码，修改文件时必须输出**完整内容**
3. **错误处理**: 爬虫解析逻辑必须使用 `try-except`，缺少核心字段时丢弃并记录 Warning
4. **类型提示**: 尽可能使用 Python Type Hints
5. **插件**: 每个站点独立插件
6. **SSRF 防护**: 所有接受外部 URL 的端点必须检查私有地址（`_is_private_url()`）
7. **API Key 安全**: 设置接口返回遮蔽后的 API Key（`mask_api_key()`）
8. **以本地代码为准**：一切以本地代码为准

## 代码提交

每次完成修改后提交到 GitHub，为每个修改做好中文备注：

```bash
git add .
git commit -m "描述具体修改内容"
git push
```
