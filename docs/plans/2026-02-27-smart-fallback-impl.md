# 新闻预览智能回退链实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 改造 `/api/news/preview` 端点，实现四级智能回退链（正文提取 → 无头浏览器 → 截图 → 缓存摘要），确保任何网站都能返回可用预览。

**Architecture:** 在现有正文提取逻辑基础上，增加内容质量检查、Playwright 截图回退和数据库缓存兜底。前端根据响应 `type` 字段渲染不同 UI。

**Tech Stack:** Python/Flask, Playwright (截图), BeautifulSoup (提取), 原生 JS/CSS (前端)

**设计文档:** `docs/plans/2026-02-27-smart-fallback-design.md`

---

### Task 1: 后端 — 重构 `/api/news/preview` 为智能回退链

**Files:**
- Modify: `routes/api.py` — 改造 `news_preview()` 函数

**改造要点：**

1. 将现有正文提取逻辑封装为 `_extract_content(html, url)` 内部函数
2. 增加内容质量检查：blocks < 3 或文本 < 100 字符视为失败
3. 新增 `_take_screenshot(url)` 函数：用 Playwright 截图转 Base64
4. 新增 `_get_cached_info(url)` 函数：从 MongoDB 查询缓存文章信息
5. 响应增加 `type` 字段："content" / "screenshot" / "cached"

---

### Task 2: CSS — 新增截图模式和缓存模式样式

**Files:**
- Modify: `static/css/dashboard.css`

**新增样式：**
- `.preview-screenshot-container`：截图展示区域（可滚动）
- `.preview-screenshot-img`：截图图片（max-width: 100%）
- `.preview-screenshot-hint`：截图模式提示文字
- `.preview-cached-container`：缓存信息卡片
- `.preview-mode-badge`：模式标识（截图模式/缓存模式）

---

### Task 3: 前端 JS — 改造 `openNewsPreview()` 支持多种渲染模式

**Files:**
- Modify: `static/js/dashboard.js`

**改造 renderPreviewContent 逻辑：**
- `type === "content"`：保持现有正文渲染
- `type === "screenshot"`：显示截图图片 + 提示信息
- `type === "cached"`：显示缓存信息卡片

---

### Task 4: 集成测试与提交
