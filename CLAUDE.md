# CLAUDE.md

## 项目概述
这是一个基于 **Python** 和 **Scrapy** 框架的高并发新闻抓取系统，旨在每日从全球约30个指定新闻源（包括大公报、路透社、纽约时报、政府官网等）获取最新的新闻标题、链接、发布时间和正文内容。

## 技术栈
- **核心语言**: Python 3.10+
- **爬虫框架**: Scrapy
- **动态渲染**: Scrapy-Playwright (用于处理 JS 动态加载的网站，如 NYT, BBC)
- **数据存储**: MongoDB (主要), JSONL (备份)
- **依赖管理**: `requirements.txt`

## 常用命令 (Commands)

| 命令 | 描述 |
| --- | --- |
| `pip install -r requirements.txt` | 安装项目依赖 |
| `playwright install chromium` | 安装 Playwright 浏览器内核 (用于动态页面) |
| `scrapy crawl universal_spider` | **启动主爬虫** (抓取所有配置的网站) |
| `scrapy crawl universal_spider -a domain=takungpao.com` | 仅测试/抓取特定域名 |
| `python main.py` | 通过 Python 脚本入口启动爬虫 (包含定时任务逻辑) |
| `scrapy shell "URL"` | 进入调试模式测试 XPath/CSS 选择器 |

## 架构规范 (Architecture)

### 1. 目录结构
- `spiders/`: 存放爬虫逻辑。建议使用 `universal_spider.py` 作为统一入口，根据 domain 分发处理逻辑。
- `items.py`: 定义标准数据结构 (`title`, `url`, `publish_date`, `content`, `source`, `crawled_at`)。
- `pipelines.py`: 数据清洗（去空、格式化时间）和持久化存储。
- `settings.py`: 包含反爬策略（User-Agent池、下载延迟）、并发数配置。

### 2. URL 管理
- 所有的目标网站及其配置（如域名、国家、是否需要渲染）应维护在外部配置文件或数据库中，避免硬编码在 Spider 中。

### 3. 反爬虫策略
- 必须配置 `DOWNLOAD_DELAY` (建议 1-3秒)。
- 必须使用随机 User-Agent。
- 针对 Cloudflare 保护的网站，优先尝试 `scrapy-impersonate` 或 `playwright`。

## 代码风格与规范 (Coding Guidelines)

1.  **语言偏好**:
    - **所有代码注释必须使用中文**。
    - **Claude 的回复解释必须使用中文**。

2.  **代码完整性**:
    - **严禁省略代码**。在修改或生成文件时，必须输出文件的**完整内容**，不要使用 `// ... rest of code` 或 `Pass` 占位符。

3.  **错误处理**:
    - 所有的解析逻辑 (`parse` 方法) 必须包含 `try-except` 块，防止因单个页面结构变化导致整个爬虫崩溃。
    - 如果缺少核心字段（如标题或 URL），应丢弃该 Item 并记录 Warning 日志。

4.  **类型提示**:
    - 尽可能使用 Python 的 Type Hints (e.g., `def parse(self, response: Response) -> Iterator[dict]:`).

## 任务清单 (Current Focus)
- [ ] 完善 `universal_spider.py` 中的域名分发逻辑。
- [ ] 为列表中的30个网站逐个实现 CSS/XPath 解析规则。
- [ ] 集成 MongoDB 存储管道。
- [ ] 部署定时任务 (Crontab)