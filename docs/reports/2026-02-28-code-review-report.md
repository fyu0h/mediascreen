# 全球舆情态势感知平台 — 代码审核报告

**审核日期**: 2026-02-28
**审核方法**: 6 个并行 Agent 静态代码审查
**审核范围**: 全项目 32 个 Python 文件、1 个 JS 文件(6800+行)、1 个 CSS 文件(7800+行)、2 个 HTML 模板、配置与部署文件

---

## 执行摘要

| 指标 | 值 |
|------|-----|
| 总发现数 | **102 项** |
| 严重(Critical) | **0** |
| 高(High) | **22** |
| 中(Medium) | **46** |
| 低(Low) | **34** |
| **整体评级** | **C+（需重点整改）** |

### 各审核域评级

| 审核域 | 评级 | 关键风险 |
|--------|------|----------|
| 安全审计 | **C-** | API 密钥泄露、无 CSRF/速率限制、SSRF |
| 后端架构 | **C+/B-** | api.py 单文件膨胀、初始化流程缺陷、代码重复 |
| 爬虫与数据管道 | **B** | 异步阻塞、浏览器资源管理、parsers.py 巨型文件 |
| 数据层 | **B-** | 正则查询无索引、N+1 查询、时区混乱 |
| 前端 | **C+** | XSS 注入风险、6800 行单体 JS、CDN 无 SRI |
| 部署与配置 | **C+** | 明文密钥、无备份策略、Nginx 安全缺失 |

---

## 一、严重问题

无严重问题。（CRIT-01 原评为严重，但因 GitHub 仓库为 Private，密钥泄露风险可控，已降级至中等优先级 MED-46。）

---

## 二、高优先级问题（22 项）

### 安全类（10 项）

| # | 问题 | 位置 | 修复建议 |
|---|------|------|----------|
| HIGH-01 | SECRET_KEY 每次重启随机生成，Session 全部失效 | `config.py:18` | 在环境变量中设置固定 SECRET_KEY |
| HIGH-02 | 默认弱密码 admin/admin123，无强制修改机制 | `models/users.py:155` | 首次登录强制改密 + 密码复杂度要求 |
| HIGH-03 | Session Cookie 缺少 Secure/SameSite 属性 | `app.py:19-35` | 配置 `SESSION_COOKIE_SECURE=True`, `SAMESITE='Lax'` |
| HIGH-04 | 无 CSRF 保护机制 | `app.py` 全文 | 集成 Flask-WTF CSRFProtect |
| HIGH-05 | 无速率限制，登录可被暴力破解 | `routes/views.py:21-53` | 集成 Flask-Limiter，登录 5次/分钟/IP |
| HIGH-06 | test-api 端点存在 SSRF 风险 | `routes/api.py:981-1048` | URL 白名单 + 内网地址过滤 |
| HIGH-07 | onclick 属性拼接变量导致 XSS 注入 | `dashboard.js:734,1263,1551` | 改用 data-* 属性 + 事件委托 |
| HIGH-08 | CDN 资源无 SRI 哈希校验 | `index.html:8,10,11` | 添加 integrity + crossorigin 属性 |
| HIGH-09 | MongoDB 默认无认证保护 | `config.py:33-34` | 部署时强制配置认证 |
| HIGH-10 | Nginx 配置缺少安全加固 | `nginx.conf.example` | 添加安全头、HTTPS、速率限制 |

### 架构类（6 项）

| # | 问题 | 位置 | 修复建议 |
|---|------|------|----------|
| HIGH-11 | `routes/api.py` 1500+ 行单文件，40+ 端点 | `routes/api.py` 全文 | 按业务域拆分为 5-8 个蓝图模块 |
| HIGH-12 | 初始化函数仅在 `__main__` 下执行，生产入口跳过 | `app.py:226-270` | 移入 `create_app()` 工厂函数 |
| HIGH-13 | 爬虫逻辑三处几乎相同的代码 (DRY 违反) | `api.py:1156-1496` | 抽取 `services/crawl_service.py` |
| HIGH-14 | 裸 `except:` 捕获（吞掉 SystemExit 等） | `logger.py:285-292` | 替换为 `except Exception:` |
| HIGH-15 | `parsers.py` 1200+ 行单体文件，22+ 解析器 | `plugins/parsers.py` | 拆分为 `parsers/` 包 |
| HIGH-16 | 6800+ 行单体 JS + 30+ 全局变量 | `dashboard.js` 全文 | 按功能域模块化拆分 |

### 性能类（4 项）

| # | 问题 | 位置 | 修复建议 |
|---|------|------|----------|
| HIGH-17 | `title` 字段无索引，$regex 全集合扫描 | `models/mongo.py:391,565,628` | 创建 Text Index 或复合索引 |
| HIGH-18 | `get_map_markers()` 收集所有标题到内存做双重循环匹配 | `models/mongo.py:445-510` | 下推到 MongoDB 聚合或限制数据范围 |
| HIGH-19 | `fetch_page` 异步函数中使用 `time.sleep` 阻塞事件循环 | `plugins/crawler.py:123` | 替换为 `await asyncio.sleep(delay)` |
| HIGH-20 | 每次请求完整写入 MongoDB 日志，无 TTL 索引 | `app.py:42-127` | 添加 TTL 索引 + 排除高频端点 |

### 可靠性类（2 项）

| # | 问题 | 位置 | 修复建议 |
|---|------|------|----------|
| HIGH-21 | Telegram `stop()` 竞态条件：异步断开未完成就清空 | `telegram_monitor.py:65-77` | 等待所有断开操作完成后再清空 |
| HIGH-22 | 无数据库备份策略 | 全局缺失 | 编写 mongodump 定时备份脚本 |

---

## 三、中等优先级问题（45 项）

### 安全（12 项）

| # | 问题 | 位置 |
|---|------|------|
| MED-01 | 日志记录完整请求体（含密码/API密钥） | `app.py:56-68` |
| MED-02 | admin/viewer 角色无实际权限区分 | `routes/api.py:56-60` |
| MED-03 | 部分输入参数缺少长度/格式校验 | `routes/api.py` 多处 |
| MED-04 | CORS 允许外部 HTTP 域名 + 携带凭据 | `app.py:28-35` |
| MED-05 | 地图弹窗数据未转义（存储型 XSS） | `dashboard.js:944,950` |
| MED-06 | AI 总结 Markdown 渲染缺乏 HTML 消毒 | `dashboard.js:4740-4742` |
| MED-07 | CSS 选择器注入风险 | `dashboard.js:1189,1198` |
| MED-08 | 前端 API 请求缺少 CSRF Token | `dashboard.js` 所有 fetch 调用 |
| MED-09 | logger.py 搜索参数未做 regex 转义 (ReDoS) | `models/logger.py:166-168` |
| MED-10 | ObjectId 转换未捕获异常，可能 500 错误 | `mongo.py`, `telegram.py` 多处 |
| MED-11 | 开发模式绑定 0.0.0.0 暴露全网络 | `app.py:265` |
| MED-12 | 默认密码在部署脚本中明文展示 | `deploy.sh:116`, `deploy.bat:89` |

### 架构/代码质量（11 项）

| # | 问题 | 位置 |
|---|------|------|
| MED-13 | `check_auth` 中间件阻断 `/api/auth/status` | `api.py:56-60` |
| MED-14 | SSE 爬取端点用 GET 执行副作用操作 | `api.py:1234` |
| MED-15 | `log_error` 参数类型不一致（传 str 期望 Exception） | `api.py:104` vs `logger.py` |
| MED-16 | `settings.json` 无缓存，每次调用都读文件 | `models/settings.py:264-281` |
| MED-17 | 模块级散乱导入 (违反 PEP 8) | `api.py:515,631,839` |
| MED-18 | Telegram `_clients` 字典线程安全问题 | `telegram_monitor.py:23,70-77` |
| MED-19 | 无自动重连机制，连接丢失后静默失效 | `telegram_monitor.py:92-107` |
| MED-20 | 注册表 `get_all_sites()` 修改原始站点数据 | `registry.py:56-66` |
| MED-21 | 全 plugins/ 目录使用 print 替代 logging | 全 plugins/ 目录 |
| MED-22 | `trigger_update()` 无任务重叠检测 | `scheduler.py:341-343` |
| MED-23 | 7800+ 行单体 CSS 文件 | `dashboard.css` 全文 |

### 性能（10 项）

| # | 问题 | 位置 |
|---|------|------|
| MED-24 | `alert_reads` 集合缺少 `article_url` 索引 | `mongo.py:1019-1061` |
| MED-25 | `crawl_tasks` 集合缺少 `task_id` 索引 | `models/tasks.py:18-21` |
| MED-26 | 分页使用 skip/limit，深度分页性能差 | `mongo.py:414` |
| MED-27 | `get_plugins_with_status()` N+1 查询问题 | `plugins.py:263-315` |
| MED-28 | `get_realtime_stats()` 5 次独立 count_documents | `mongo.py:798-840` |
| MED-29 | 浏览器实例每次请求创建/销毁 | `crawler.py:103-106` |
| MED-30 | 5 个并发 worker 可能同时启动 5 个 Chromium | `crawl_scheduler.py:264` |
| MED-31 | 大列表完整 DOM 重建 (100+ innerHTML 赋值) | `dashboard.js` 多处 |
| MED-32 | 多重叠 API 轮询 + lastDataDigest 未使用 | `dashboard.js:1312-1380` |
| MED-33 | `get_overview_stats()` 用 count_documents({}) 扫全表 | `mongo.py:225` |

### 数据一致性（6 项）

| # | 问题 | 位置 |
|---|------|------|
| MED-34 | 全项目使用 datetime.now() 而非 UTC | 所有 models 文件 |
| MED-35 | save_articles() 并发 upsert 的 DuplicateKeyError 未区分处理 | `mongo.py:163-204` |
| MED-36 | add_risk_keyword() check-then-act 并发不安全 | `mongo.py:890-917` |
| MED-37 | `achievements.py` 使用 JSON 文件，并发写入不安全 | `models/achievements.py` |
| MED-38 | `settings.py` 文件读写无锁保护 | `models/settings.py` |
| MED-39 | delete_account() 两步删除非原子操作 | `telegram.py:118-127` |

### 部署/运维（6 项）

| # | 问题 | 位置 |
|---|------|------|
| MED-40 | 依赖版本约束过宽 (>=)，构建不可重现 | `requirements.txt` |
| MED-41 | 缺少运行时必要依赖声明 (playwright 等) | `requirements.txt` |
| MED-42 | Waitress 缺少关键生产配置 | `run_production.py:66-73` |
| MED-43 | 生产启动脚本中自动 pip install | `run_production.py:11-18` |
| MED-44 | 无健康检查端点 | 全局缺失 |
| MED-45 | 无监控指标采集 | 全局缺失 |

---

## 四、低优先级改进建议（34 项）

<details>
<summary>点击展开完整列表</summary>

| # | 建议 | 类型 |
|---|------|------|
| LOW-01 | MongoDB 查询安全实践良好（正面发现） | 安全 |
| LOW-02 | 登录失败统一返回"用户名或密码错误"（正面发现） | 安全 |
| LOW-03 | dashboard.js 需审查所有 innerHTML XSS | 安全 |
| LOW-04 | 错误信息未转义直接 innerHTML | 安全 |
| LOW-05 | 登录页缺少 autocomplete 属性 | 安全 |
| LOW-06 | 已废弃站点管理端点仍保留 | 架构 |
| LOW-07 | 类型注解不一致 | 代码质量 |
| LOW-08 | 日志 ID 截取 UUID4 前8位，碰撞风险 | 代码质量 |
| LOW-09 | 同步/异步 HTTP 库的 payload 构建重复 | 代码质量 |
| LOW-10 | RESTful URL 命名不一致 | API 设计 |
| LOW-11 | 分页参数校验不完整（负数 limit） | API 设计 |
| LOW-12 | BasePlugin 类属性无强制校验机制 | 设计 |
| LOW-13 | `supported_fetch_methods` 可变类属性 | 设计 |
| LOW-14 | 内置插件站点配置全部硬编码 | 设计 |
| LOW-15 | 部分站点使用 HTTP 而非 HTTPS | 安全 |
| LOW-16 | parsers.py 裸 except:pass | 健壮性 |
| LOW-17 | 大量解析器无日期时默认 datetime.now() | 健壮性 |
| LOW-18 | clean_title 可能误截包含分隔符的标题 | 健壮性 |
| LOW-19 | User-Agent 硬编码 Chrome 120 版本 | 设计 |
| LOW-20 | RSS 预检查 `startswith('<?xml')` 过于严格 | 健壮性 |
| LOW-21 | RSS 源配置与内置插件站点配置双重维护 | 设计 |
| LOW-22 | 翻译批量返回解析降级策略不足 | 健壮性 |
| LOW-23 | 翻译缓存 OrderedDict 线程不安全 | 线程安全 |
| LOW-24 | 全局单例均缺少线程安全保护 | 线程安全 |
| LOW-25 | 连接池参数 socketTimeoutMS=30000 可能偏短 | 性能 |
| LOW-26 | `system_logs` 集合缺少 `log_id` 索引 | 性能 |
| LOW-27 | 索引创建分散在多个文件多个函数中 | 设计 |
| LOW-28 | ensure_articles_indexes 中重复导入 | 代码质量 |
| LOW-29 | logger 集合无 TTL 索引，数据无限增长 | 运维 |
| LOW-30 | ObjectId 与自定义 ID 转换不一致 | 设计 |
| LOW-31 | 缺乏 MongoDB Schema 约束 | 设计 |
| LOW-32 | models/__init__.py 导入风格不一致 | 代码质量 |
| LOW-33 | 无版本管理与发布流程 | 运维 |
| LOW-34 | 无障碍(a11y)支持严重不足 | 设计 |

</details>

---

## 五、各审核域详细报告

### 5.1 安全审计

**评级: C- (中高风险)**

| 统计 | 数量 |
|------|------|
| 严重 | 1 (API 密钥泄露) |
| 高 | 5 (SECRET_KEY/弱密码/无CSRF/无速率限制/Cookie不安全) |
| 中 | 5 (日志泄敏/角色虚设/输入校验/CORS/SSRF) |
| 低 | 2 |

**核心问题链**: `settings.json` 明文密钥泄露 + 默认弱密码 + 无登录速率限制→构成完整暴力破解攻击路径。无 CSRF 保护 + Session Cookie 安全属性缺失→Web 安全基线缺失。

**正面发现**: MongoDB 查询均使用参数化方式（无 NoSQL 注入）、`re.escape()` 防护正则注入、登录错误信息不泄露用户名。

### 5.2 后端架构

**评级: C+/B-**

| 统计 | 数量 |
|------|------|
| 高 | 6 (api.py膨胀/初始化缺陷/爬虫重复/裸except/SECRET_KEY/默认密码) |
| 中 | 8 (auth白名单/SSE语义/日志性能/settings缓存/参数传递等) |
| 低 | 5 |

**核心问题**: `routes/api.py` 单文件1500+行承载40+端点是最突出的可维护性问题。初始化流程仅在 `__main__` 下执行，Waitress 生产入口无法触发数据库索引创建和插件注册。

### 5.3 爬虫与数据管道

**评级: B**

| 统计 | 数量 |
|------|------|
| 高 | 4 (异步阻塞/浏览器资源/parsers.py巨文件/单例线程安全) |
| 中 | 10 (任务重叠/浏览器并发/注册表副作用/日期策略等) |
| 低 | 8 |

**正面发现**: 翻译模块(translator.py)设计最完善——重试机制、批量翻译、LRU 缓存、去重均到位，评级 A-。全量爬取调度器的任务管理（进度更新/取消检测/统计）也设计良好。

### 5.4 数据层

**评级: B-**

| 统计 | 数量 |
|------|------|
| 高 | 3 (title无索引/$regex性能/时区混乱) |
| 中 | 11 (N+1查询/缺失索引/skip分页/并发安全/文件存储等) |
| 低 | 6 |

**核心问题**: 大量 `$regex` + `$options:'i'` 查询无法利用索引，数据量增长后将成为严重瓶颈。全项目使用 `datetime.now()` 而非 UTC，与 MongoDB 内部 UTC 存储和聚合函数存在潜在冲突。

**正面发现**: 连接管理实现正确（双重检查锁定+连接池），`loc` 唯一索引去重可靠。

### 5.5 前端

**评级: C+**

| 统计 | 数量 |
|------|------|
| 高 | 4 (XSS注入/CDN无SRI/单体JS/全局污染) |
| 中 | 7 (超长函数/重复代码/DOM重建/轮询重叠/CSS/模板/a11y) |
| 低 | 7 |

**核心问题**: `onclick` 属性中拼接变量值导致 XSS 注入（`escapeHtml` 无法防护 HTML 属性中的单引号解码）。6800+行单体 JS 文件严重阻碍团队协作。

**正面发现**: `escapeHtml()` 工具函数在大多数场景被正确使用；`AbortController` 请求取消机制良好；`BubbleManager` 是代码中为数不多的模块化设计；ECharts 实例正确复用；无 `eval()`/`new Function()`。

### 5.6 部署与配置

**评级: C+**

| 统计 | 数量 |
|------|------|
| 高 | 4 (密钥泄露/SECRET_KEY/弱密码/MongoDB无认证) |
| 中 | 7 (Nginx安全/备份/依赖版本/缺失依赖/Waitress配置/健康检查/日志轮转) |
| 低 | 4 |

**核心问题**: 系统不具备上线至生产环境的就绪度——无 HTTPS 强制、无备份策略、无健康检查、无监控指标。

---

## 六、架构改进路线图

### 短期（1-2 周）— 安全修复

| 优先级 | 任务 | 预计工时 |
|--------|------|----------|
| P0 | 吊销泄露的 API 密钥，清除 Git 历史 | 1h |
| P0 | 固定 SECRET_KEY（环境变量） | 15min |
| P0 | 配置 MongoDB 认证 | 1h |
| P0 | 首次登录强制修改默认密码 | 2h |
| P1 | 集成 Flask-Limiter（登录+敏感端点） | 2h |
| P1 | 修复 onclick XSS 漏洞（改用 data-* + 事件委托） | 3h |
| P1 | 添加 Session Cookie 安全属性 | 15min |
| P1 | CDN 资源添加 SRI 哈希 | 1h |
| P1 | SSRF 防护（URL 白名单 + 内网过滤） | 2h |

### 中期（1-2 月）— 架构优化

| 优先级 | 任务 | 预计工时 |
|--------|------|----------|
| P1 | 修复初始化流程（移入 create_app） | 1h |
| P1 | `title` 字段创建 Text Index | 2h |
| P1 | 补全缺失索引（alert_reads, crawl_tasks） | 1h |
| P1 | Nginx 安全加固（HTTPS/安全头/速率限制） | 3h |
| P2 | 拆分 `routes/api.py` 为多蓝图 | 8h |
| P2 | 抽取爬虫服务层消除重复代码 | 4h |
| P2 | 修复 N+1 查询（批量预加载） | 3h |
| P2 | 异步函数中 time.sleep→asyncio.sleep | 30min |
| P2 | 添加健康检查端点 | 1h |
| P2 | MongoDB 日志集合添加 TTL 索引 | 30min |
| P2 | 建立 mongodump 自动备份机制 | 3h |

### 长期（3-6 月）— 技术债务清理

| 优先级 | 任务 | 预计工时 |
|--------|------|----------|
| P2 | 前端 JS 模块化拆分 | 16h |
| P2 | `parsers.py` 拆分为包结构 | 8h |
| P2 | CSS 按组件拆分 | 8h |
| P3 | 统一时区处理 (datetime.now→UTC) | 4h |
| P3 | 全 plugins/ 迁移到 logging 模块 | 3h |
| P3 | CSRF Token 机制集成 | 4h |
| P3 | 角色权限实际区分 | 4h |
| P3 | settings/achievements 迁入 MongoDB | 4h |
| P3 | 引入自动化测试 | 20h+ |
| P3 | 监控指标采集 (Prometheus) | 4h |
| P3 | 依赖版本锁定 + 安全审计 | 2h |

---

## 附录：审核统计

### 按类型分布

```
安全问题      ████████████████████ 28 项
架构/代码质量  ████████████████████ 28 项
性能问题      ██████████████████   24 项
数据一致性    ████████             10 项
部署/运维     ████████████         12 项
```

### 按严重程度分布

```
严重(Critical) █                    1 项
高(High)       ██████████████████  22 项
中(Medium)     ████████████████████████████████████████  45 项
低(Low)        ██████████████████████████████████  34 项
```

---

*报告由 6 个并行审核 Agent 生成，审核耗时约 4 分钟。*
*审核工具: Claude Code Agent Teams — 静态代码分析*
