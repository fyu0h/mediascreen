# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

皇岗边检站全球舆情态势感知平台 - 基于 Flask 的实时新闻聚合与风险监控系统，从全球约30个新闻源抓取新闻，提供可视化仪表盘、风控告警、AI 舆情分析和 Telegram 群组监控。

## 技术栈

- **后端**: Python 3.10+ / Flask 2.3+
- **数据库**: MongoDB (pymongo 4.5+)，数据库名 `news_dashboard`
- **前端**: 原生 HTML/CSS/JS + ECharts (图表) + Leaflet (地图)
- **生产服务器**: Waitress (WSGI)
- **Telegram**: Telethon (异步客户端)

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
config.py                     # Config 类：MongoDB 连接、集合名常量、DeepSeek API
settings.json                 # 运行时配置（LLM多提供商、爬虫参数、Telegram、翻译）
├── models/
│   ├── mongo.py              # MongoDB 操作层（单例连接池，查询/聚合/统计）
│   ├── plugins.py            # 插件订阅管理
│   ├── settings.py           # settings.json 读写
│   ├── telegram.py           # Telegram 数据模型（账号/群组/消息/报警）
│   ├── users.py              # 用户认证（session，默认 admin/admin123）
│   ├── sites.py              # 站点管理
│   ├── tasks.py              # 任务管理
│   ├── logger.py             # 日志系统
│   └── achievements.py       # 成果展示
├── plugins/
│   ├── base.py               # BasePlugin 抽象基类
│   ├── registry.py           # PluginRegistry 全局单例注册表
│   ├── crawler.py            # 爬虫引擎（BeautifulSoup）
│   ├── parsers.py            # 站点专用解析器集合（40KB+，每站点一个函数）
│   ├── scheduler.py          # RSS 定时调度器
│   ├── crawl_scheduler.py    # 全量爬取调度器
│   ├── translator.py         # 标题翻译（调用 LLM）
│   └── builtin/              # 4个内置插件（港台/亚洲/国际/政府）
├── services/
│   └── telegram_monitor.py   # Telegram 群组实时监控服务
├── routes/
│   ├── api.py                # REST API（40+ 端点，/api/* 前缀）
│   └── views.py              # 页面渲染（/, /login, /logout）
├── templates/
│   ├── index.html            # 主仪表盘（1500+ 行）
│   └── login.html            # 登录页
└── static/
    ├── js/dashboard.js       # 前端逻辑（6500+ 行，原生 JS）
    └── css/dashboard.css     # 样式（7800+ 行，科技深色主题）
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

### MongoDB 关键集合
- `news_articles`：新闻文章（`loc` 唯一索引）
- `plugin_subscriptions`：插件订阅配置（`plugin_id` + `site_id` 唯一）
- `risk_keywords`：风控关键词（high/medium/low 三级）
- `telegram_messages`/`telegram_alerts`：Telegram 消息和报警
- `users`：用户（角色 admin/viewer）
- `ai_summaries`：AI 舆情总结历史

### 认证
Session 认证，所有 `/api/*` 端点需登录。默认管理员 `admin/admin123`。

### API 响应格式
```json
{"success": true, "data": {...}}
```

### 配置层次
- `config.py`：静态配置（支持环境变量覆盖 MongoDB 连接）
- `settings.json`：运行时配置（LLM 多提供商、爬虫参数、Telegram、翻译、布局），通过 `models/settings.py` 读写，通过 `/api/settings` 端点管理

## 代码规范

1. **语言**: 所有代码注释和 Claude 回复必须使用**中文**
2. **完整性**: 严禁省略代码，修改文件时必须输出**完整内容**
3. **错误处理**: 爬虫解析逻辑必须使用 `try-except`，缺少核心字段时丢弃并记录 Warning
4. **类型提示**: 尽可能使用 Python Type Hints
5. **插件**: 每个站点独立插件

## 代码提交

每次完成修改后提交到 GitHub，为每个修改做好中文备注：

```bash
git add .
git commit -m "描述具体修改内容"
git push
```
