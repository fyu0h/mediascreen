# 全球舆情态势感知平台 — 代码审核计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to dispatch parallel review agents.

**Goal:** 组建 Agent 团队，对整个项目代码进行全方位审核，输出结构化审核报告。

**Architecture:** 将代码库按职责边界拆分为 6 个审核域，每个域由独立 Agent 并行审核。各 Agent 输出子报告，最终由主 Agent 汇总为完整审核报告。

**Tech Stack:** Python 3.10+ / Flask / MongoDB / 原生 JS / ECharts / Leaflet / Telethon

---

## 审核域划分与 Agent 分配

| Agent # | 审核域 | 覆盖文件 | 关注点 |
|---------|--------|----------|--------|
| Agent 1 | 安全审计 | 全项目 | API 密钥泄露、认证鉴权、注入攻击、CORS、会话管理 |
| Agent 2 | 后端架构 | `app.py`, `config.py`, `routes/`, `models/`, `services/` | 架构设计、代码质量、错误处理、类型一致性 |
| Agent 3 | 爬虫与数据管道 | `plugins/` 全目录 | 解析器健壮性、调度逻辑、翻译模块、插件系统设计 |
| Agent 4 | 数据层 | `models/mongo.py`, `models/*.py`, `config.py` | MongoDB 查询性能、索引策略、连接管理、数据一致性 |
| Agent 5 | 前端 | `static/js/dashboard.js`, `static/css/dashboard.css`, `templates/` | 代码组织、XSS 风险、性能瓶颈、可维护性 |
| Agent 6 | 部署与配置 | `settings.json`, `requirements.txt`, `deploy.*`, `start.*`, `nginx.conf.example`, `run_production.py` | 敏感信息管理、依赖安全、部署流程完备性 |

---

## Task 1: Agent 1 — 安全审计

**Files (全项目扫描，重点关注):**
- `settings.json` — **已知问题: 明文 API 密钥泄露，已被 git 跟踪**
- `config.py` — SECRET_KEY、数据库凭据
- `routes/api.py` — 认证中间件、输入校验
- `routes/views.py` — 登录逻辑
- `models/users.py` — 密码存储、默认凭据
- `app.py` — CORS 配置、会话管理
- `plugins/translator.py` — 外部 API 调用
- `services/telegram_monitor.py` — Telegram 凭据
- `templates/*.html` — XSS 注入点

**审核清单:**

1. **敏感信息泄露**
   - [ ] `settings.json` 中的 API 密钥是否明文存储且被 git 跟踪
   - [ ] `.gitignore` 是否遗漏了 `settings.json`
   - [ ] `config.py` 的 `SECRET_KEY` 是否每次启动随机生成（无法持久化 session）
   - [ ] 日志中是否可能记录了敏感信息（请求头中的 cookie/token 过滤是否完整）

2. **认证与鉴权**
   - [ ] `check_auth()` 中间件是否覆盖所有 API 端点
   - [ ] 默认密码 `admin/admin123` 是否有强制修改提示
   - [ ] Session 配置（过期时间、httponly、secure 标记）
   - [ ] 是否存在越权风险（admin vs viewer 角色是否实际区分）

3. **注入攻击**
   - [ ] MongoDB 查询是否存在 NoSQL 注入风险（用户输入直接传入查询条件）
   - [ ] `request.get_json()` 解析后的数据是否做了类型校验
   - [ ] URL 参数是否做了合理的清洗和限制

4. **CORS 配置**
   - [ ] 允许的 origins 是否过于宽泛
   - [ ] `supports_credentials: True` 是否必要

5. **其他安全关注**
   - [ ] HTTP vs HTTPS（是否强制 HTTPS）
   - [ ] 速率限制（是否有任何 API 限流机制）
   - [ ] CSRF 保护（Flask 是否启用了 CSRF token）

---

## Task 2: Agent 2 — 后端架构审核

**Files:**
- `app.py` — 应用工厂、中间件
- `config.py` — 配置结构
- `routes/api.py` — REST API（40+ 端点）
- `routes/views.py` — 页面路由
- `models/__init__.py`, `models/logger.py`, `models/settings.py`, `models/tasks.py`, `models/achievements.py`
- `services/telegram_monitor.py` — 异步服务

**审核清单:**

1. **架构设计**
   - [ ] `create_app()` 工厂函数是否遵循 Flask 最佳实践
   - [ ] 蓝图拆分是否合理（目前仅 api + views 两个蓝图）
   - [ ] `routes/api.py` 40+ 端点是否应该按功能拆分为多个蓝图
   - [ ] 初始化流程顺序（database → plugins → schedulers → telegram）是否有依赖问题

2. **代码质量**
   - [ ] 函数/方法长度是否合理，是否有过长的函数需要拆分
   - [ ] 重复代码检测（DRY 原则）
   - [ ] 类型注解的使用一致性
   - [ ] 异常处理是否恰当（是否吞掉了异常、是否有裸 except）

3. **API 设计**
   - [ ] RESTful 规范的遵循程度（HTTP 方法使用是否正确）
   - [ ] 响应格式一致性（`success_response` / `error_response` 是否所有端点都使用）
   - [ ] 分页参数的校验和限制
   - [ ] 缺少的输入校验

4. **日志系统**
   - [ ] 日志级别使用是否合理
   - [ ] 请求日志是否会产生过多数据（性能影响）
   - [ ] 日志中敏感数据过滤是否完整

---

## Task 3: Agent 3 — 爬虫与数据管道审核

**Files:**
- `plugins/base.py` — 插件基类
- `plugins/registry.py` — 注册表
- `plugins/crawler.py` — 爬虫引擎
- `plugins/parsers.py` — 站点解析器（40KB+，核心审核对象）
- `plugins/scheduler.py` — RSS 调度
- `plugins/crawl_scheduler.py` — 全量爬取调度
- `plugins/translator.py` — 翻译模块
- `plugins/builtin/*.py` — 4 个内置插件

**审核清单:**

1. **解析器健壮性** (`parsers.py`)
   - [ ] 每个解析器函数是否都有 try-except 包裹
   - [ ] 缺少核心字段（title、url）时是否正确丢弃并记录 Warning
   - [ ] 是否处理了网络超时、编码错误等边界情况
   - [ ] 单文件 40KB+ 是否应该按地区或类型拆分

2. **爬虫引擎** (`crawler.py`)
   - [ ] 请求超时配置是否合理
   - [ ] 并发/并行控制（是否会对目标站点产生过大压力）
   - [ ] User-Agent 是否可配置
   - [ ] 代理支持
   - [ ] robots.txt 合规性

3. **调度器**
   - [ ] 定时任务的线程安全性
   - [ ] 任务重叠检测（上一次未完成就启动下一次）
   - [ ] 异常恢复机制（单个站点失败是否会影响其他站点）

4. **翻译模块**
   - [ ] LLM API 调用是否有重试机制
   - [ ] 翻译失败时的降级策略
   - [ ] 批量翻译的效率

5. **插件系统设计**
   - [ ] `BasePlugin` 接口设计是否合理
   - [ ] 插件注册/发现机制
   - [ ] 插件间的隔离性

---

## Task 4: Agent 4 — 数据层审核

**Files:**
- `models/mongo.py` — MongoDB 核心操作（重点）
- `models/plugins.py` — 插件数据
- `models/sites.py` — 站点管理
- `models/telegram.py` — Telegram 数据
- `models/users.py` — 用户数据
- `config.py` — 数据库配置

**审核清单:**

1. **连接管理**
   - [ ] 单例连接池的线程安全实现
   - [ ] 连接池参数（maxPoolSize=50, minPoolSize=5）是否合理
   - [ ] 超时配置是否合理
   - [ ] 连接泄漏风险

2. **索引策略**
   - [ ] 已定义的索引是否覆盖了常见查询模式
   - [ ] 是否存在缺失的索引（导致全表扫描）
   - [ ] 复合索引的字段顺序是否最优
   - [ ] 唯一索引的合理性

3. **查询性能**
   - [ ] 聚合管道的效率
   - [ ] 是否有 N+1 查询问题
   - [ ] 大数据量下的分页策略（skip/limit vs cursor）
   - [ ] 查询条件是否合理利用索引

4. **数据一致性**
   - [ ] 写操作是否有原子性保证
   - [ ] 并发写入时的冲突处理
   - [ ] `loc` 唯一索引的去重可靠性

5. **数据模型**
   - [ ] 文档结构是否有 schema 约束或验证
   - [ ] 日期字段的时区处理一致性（`datetime.now()` vs `datetime.utcnow()`）
   - [ ] ObjectId 与字符串 ID 的转换一致性

---

## Task 5: Agent 5 — 前端审核

**Files:**
- `static/js/dashboard.js` — 前端逻辑（6500+ 行，核心审核对象）
- `static/css/dashboard.css` — 样式（7800+ 行）
- `templates/index.html` — 主仪表盘（1500+ 行）
- `templates/login.html` — 登录页

**审核清单:**

1. **代码组织**
   - [ ] 6500+ 行单文件 JS 的可维护性评估
   - [ ] 是否有模块化/组件化拆分的可能性
   - [ ] 全局变量和命名空间污染
   - [ ] 函数职责是否单一、长度是否合理

2. **安全**
   - [ ] XSS 风险：是否有 `innerHTML` 直接插入用户输入或新闻内容
   - [ ] 敏感数据是否暴露在前端（API 密钥、内部 URL）
   - [ ] CSP（内容安全策略）头是否设置

3. **性能**
   - [ ] DOM 操作是否高效（是否频繁重排/重绘）
   - [ ] 定时器和轮询是否可能导致内存泄漏
   - [ ] 大量新闻数据的渲染策略（虚拟滚动？分页？）
   - [ ] ECharts/Leaflet 实例的生命周期管理

4. **CSS**
   - [ ] 7800+ 行单文件 CSS 的可维护性
   - [ ] 是否有大量重复样式
   - [ ] 响应式设计的完善程度
   - [ ] CSS 选择器性能

5. **HTML 模板**
   - [ ] Jinja2 模板的使用是否安全（自动转义）
   - [ ] 外部资源（CDN）的完整性校验（SRI hash）
   - [ ] 无障碍(a11y)基础检查

---

## Task 6: Agent 6 — 部署与配置审核

**Files:**
- `settings.json` — 运行时配置（**已知安全问题**）
- `settings.example.json` — 配置模板
- `requirements.txt` — Python 依赖
- `run_production.py` — 生产环境入口
- `deploy.sh`, `deploy.bat` — 部署脚本
- `start.sh`, `start.bat` — 启动脚本
- `nginx.conf.example` — Nginx 配置
- `.gitignore` — 忽略规则

**审核清单:**

1. **敏感信息管理**
   - [ ] `settings.json` 是否应该加入 `.gitignore`（当前含明文 API 密钥）
   - [ ] 环境变量 vs 配置文件的使用策略
   - [ ] `settings.example.json` 是否安全（无真实密钥）

2. **依赖安全**
   - [ ] `requirements.txt` 中依赖版本是否有已知漏洞
   - [ ] 依赖是否固定到具体版本（避免供应链攻击）
   - [ ] 是否缺少必要的依赖（如 Playwright 是否需要列入）

3. **生产部署**
   - [ ] Waitress 配置是否优化（工作线程数、超时等）
   - [ ] Nginx 反向代理配置的安全性和性能
   - [ ] HTTPS/TLS 配置
   - [ ] 日志轮转策略

4. **启动与部署脚本**
   - [ ] 脚本是否处理了错误情况
   - [ ] 环境检查（Python 版本、MongoDB 是否运行等）
   - [ ] 进程管理（是否有守护进程/supervisor 集成）

5. **运维就绪度**
   - [ ] 健康检查端点是否存在
   - [ ] 监控指标是否可观测
   - [ ] 备份与恢复策略
   - [ ] 版本化/发布管理

---

## Task 7: 汇总审核报告

**前置依赖:** Task 1-6 全部完成

**输出文件:** `docs/reports/2026-02-27-code-review-report.md`

**报告结构:**

```markdown
# 全球舆情态势感知平台 — 代码审核报告
日期: 2026-02-27

## 执行摘要
- 审核范围概述
- 整体质量评级（A/B/C/D/F 五级）
- 关键发现数量统计（严重/高/中/低）

## 一、严重问题（需立即修复）
编号 | 问题 | 风险等级 | 影响范围 | 修复建议

## 二、高优先级问题
编号 | 问题 | 风险等级 | 影响范围 | 修复建议

## 三、中等优先级问题（建议修复）
编号 | 问题 | 类型 | 修复建议

## 四、低优先级改进建议
编号 | 建议 | 类型 | 说明

## 五、各审核域详细报告
### 5.1 安全审计
### 5.2 后端架构
### 5.3 爬虫与数据管道
### 5.4 数据层
### 5.5 前端
### 5.6 部署与配置

## 六、架构改进路线图
- 短期（1-2周）: 安全修复
- 中期（1-2月）: 架构优化
- 长期（3-6月）: 技术债务清理
```
