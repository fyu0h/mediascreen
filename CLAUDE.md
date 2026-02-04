# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

皇岗边检站全球舆情态势感知平台 - 一个基于 Flask 的实时新闻聚合与风险监控系统，每日从全球约30个新闻源（大公报、路透社、纽约时报、政府官网等）抓取新闻，并提供可视化仪表盘展示。

## 技术栈

- **后端**: Python 3.10+ / Flask 2.3+
- **数据库**: MongoDB (pymongo 4.5+)
- **爬虫**: 自定义 Sitemap 解析器 + AI 爬虫 (DeepSeek/SiliconFlow API)
- **前端**: 原生 HTML/CSS/JS + ECharts (图表) + Leaflet (地图)

## 常用命令

| 命令 | 描述 |
| --- | --- |
| `pip install -r requirements.txt` | 安装 Python 依赖 |
| `python app.py` | 启动 Flask 开发服务器 (localhost:5000) |
| `mongod` | 启动本地 MongoDB 服务 |

## 架构概览

```
app.py                    # Flask 入口，注册蓝图
config.py                 # MongoDB 配置、风险关键词、新闻源元数据
├── models/
│   ├── mongo.py          # MongoDB 操作层 (查询、聚合、统计)
│   ├── sites.py          # 订阅站点管理 (sites.json)
│   ├── settings.py       # 系统设置 (LLM API、爬虫参数)
│   ├── logger.py         # 后端日志系统
│   └── achievements.py   # 成果展示管理
├── routes/
│   ├── api.py            # REST API (40+ 端点)
│   └── views.py          # 页面渲染
├── crawlers/
│   ├── sitemap_crawler.py # XML Sitemap 解析器
│   └── ai_crawler.py      # AI 驱动的页面内容提取
├── templates/index.html   # 主仪表盘页面
└── static/
    ├── js/dashboard.js    # 前端逻辑 (3400+ 行)
    └── css/dashboard.css  # 样式
```

## 核心数据流

1. **爬虫层** (`crawlers/`) → 从新闻站点抓取文章
2. **存储层** (`models/mongo.py`) → 存入 MongoDB `news_articles` 集合
3. **API层** (`routes/api.py`) → 提供 REST 接口
4. **展示层** (`static/js/dashboard.js`) → 渲染图表、地图、列表

## API 响应格式

所有 API 端点返回统一 JSON 格式：
```json
{"success": true, "data": {...}}
```

## 代码规范

1. **语言**: 所有代码注释和 Claude 回复必须使用**中文**
2. **完整性**: 严禁省略代码，修改文件时必须输出**完整内容**
3. **错误处理**: 爬虫解析逻辑必须使用 `try-except`，缺少核心字段时丢弃并记录 Warning
4. **类型提示**: 尽可能使用 Python Type Hints

## 当前任务 (Current Focus)

2. **内置插件模式**: 预置站点抓取方式 (通用HTML/Sitemap/RSS)，用户只需启用/禁用
3. **新功能**: Telegram 群组监控