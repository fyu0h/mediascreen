# 新闻预览页面实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用户点击新闻时在条目下方内嵌展开预览区域，后台实时爬取原始页面通过 iframe srcdoc 渲染，提供访问原始链接按钮。

**Architecture:** 新增后端 `/api/news/preview` 端点复用 PluginCrawler 抓取并处理 HTML（注入 base 标签、移除 script），前端将所有 `window.open` 调用替换为统一的 `openNewsPreview()` 函数实现手风琴展开效果，iframe srcdoc 渲染处理后的 HTML。

**Tech Stack:** Python/Flask (后端), BeautifulSoup (HTML处理), 原生 JS (前端), CSS (样式)

**设计文档:** `docs/plans/2026-02-27-news-preview-design.md`

---

### Task 1: 后端 — 新增 `/api/news/preview` 端点

**Files:**
- Modify: `routes/api.py` — 文件顶部 import 区域 + 文件末尾新增端点

**Step 1: 在 `routes/api.py` 顶部添加 import**

在现有 import 区域（约第8行 `from flask import ...` 之后）添加：

```python
import asyncio
import re
from urllib.parse import urlparse, urljoin
```

在现有 models import 之后添加：

```python
from plugins.crawler import get_crawler
```

**Step 2: 在 `routes/api.py` 末尾新增端点**

在文件末尾添加以下端点：

```python
@api_bp.route('/news/preview', methods=['GET'])
def news_preview():
    """获取新闻预览内容 — 抓取原始页面并处理 HTML"""
    if 'user' not in session:
        return error_response('未登录', 401)

    url = request.args.get('url', '').strip()
    if not url:
        return error_response('缺少 url 参数', 400)

    # 校验 URL 合法性
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return error_response('URL 必须以 http 或 https 开头', 400)

    try:
        # 复用爬虫抓取页面
        crawler = get_crawler()
        loop = asyncio.new_event_loop()
        try:
            html = loop.run_until_complete(crawler.fetch_page(url, timeout=15))
        finally:
            loop.close()

        if not html:
            return error_response('无法抓取页面内容', 502)

        # HTML 内容大小检查（>5MB 截断）
        if len(html) > 5 * 1024 * 1024:
            html = html[:5 * 1024 * 1024]

        # HTML 处理：移除 script，注入 base 标签
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # 移除所有 script 标签
        for script in soup.find_all('script'):
            script.decompose()

        # 注入 base 标签确保相对路径资源正确加载
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        base_tag = soup.new_tag('base', href=base_url)
        if soup.head:
            soup.head.insert(0, base_tag)
        elif soup.html:
            head_tag = soup.new_tag('head')
            head_tag.insert(0, base_tag)
            soup.html.insert(0, head_tag)

        processed_html = str(soup)
        return success_response({'html': processed_html, 'url': url})

    except Exception as e:
        log_error(f"新闻预览抓取失败: {url}", str(e))
        return error_response(f'抓取失败: {str(e)}', 502)
```

**Step 3: 提交**

```bash
git add routes/api.py
git commit -m "feat: 新增 /api/news/preview 端点，支持抓取并预览新闻原始页面"
```

---

### Task 2: CSS — 新增预览区域样式

**Files:**
- Modify: `static/css/dashboard.css` — 在媒体查询之前（约第7750行前）插入新样式块

**Step 1: 在 `dashboard.css` 的媒体查询区域之前添加预览样式**

在 `/* ========== 移动端适配 ==========*/` 注释之前插入以下样式：

```css
/* ========== 新闻预览区域 ========== */
.news-preview-container {
    overflow: hidden;
    max-height: 0;
    transition: max-height 0.3s ease-out;
    border-top: 1px solid var(--border-color);
    background: rgba(0, 0, 0, 0.3);
}

.news-preview-container.active {
    max-height: 600px;
    transition: max-height 0.4s ease-in;
}

.news-preview-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background: rgba(0, 206, 209, 0.08);
    border-bottom: 1px solid var(--border-color);
}

.news-preview-toolbar .preview-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--accent-color);
    cursor: pointer;
    font-size: 12px;
    transition: background 0.2s, border-color 0.2s;
}

.news-preview-toolbar .preview-btn:hover {
    background: rgba(0, 206, 209, 0.15);
    border-color: var(--accent-color);
}

.news-preview-toolbar .preview-close-btn {
    color: var(--text-secondary);
}

.news-preview-toolbar .preview-close-btn:hover {
    color: var(--text-primary);
}

.news-preview-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--text-secondary);
    font-size: 14px;
}

.news-preview-loading .spinner {
    width: 24px;
    height: 24px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-right: 10px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.news-preview-iframe {
    width: 100%;
    height: 500px;
    border: none;
    background: #fff;
}

.news-preview-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 200px;
    color: var(--text-secondary);
    font-size: 14px;
    gap: 8px;
}

.news-preview-error .error-icon {
    font-size: 32px;
    opacity: 0.5;
}
```

**Step 2: 在移动端媒体查询中添加预览区域的响应式适配**

在 `@media (max-width: 768px)` 媒体查询块内添加：

```css
    .news-preview-iframe {
        height: 350px;
    }

    .news-preview-container.active {
        max-height: 450px;
    }
```

**Step 3: 提交**

```bash
git add static/css/dashboard.css
git commit -m "style: 新增新闻预览区域、工具栏、加载动画样式"
```

---

### Task 3: 前端 JS — 新增 `openNewsPreview()` 函数

**Files:**
- Modify: `static/js/dashboard.js` — 添加预览核心函数

**Step 1: 在 `dashboard.js` 中添加预览相关全局变量和核心函数**

在文件合适位置（如其他工具函数附近）添加以下代码：

```javascript
// ==================== 新闻预览功能 ====================
let currentPreviewController = null;  // 用于取消未完成的请求

/**
 * 打开新闻预览 — 在点击的新闻条目下方展开预览区域
 * @param {string} url - 新闻原始链接
 * @param {HTMLElement} articleEl - 被点击的新闻条目 DOM 元素
 */
function openNewsPreview(url, articleEl) {
    if (!url) return;

    // 检查是否已有预览展开 — 如果点击的是同一条目，则收起
    const existingPreview = articleEl.nextElementSibling;
    if (existingPreview && existingPreview.classList.contains('news-preview-container')) {
        closeNewsPreview(existingPreview);
        return;
    }

    // 关闭其他已展开的预览
    document.querySelectorAll('.news-preview-container').forEach(el => {
        closeNewsPreview(el);
    });

    // 取消之前未完成的请求
    if (currentPreviewController) {
        currentPreviewController.abort();
    }
    currentPreviewController = new AbortController();

    // 创建预览容器
    const container = document.createElement('div');
    container.className = 'news-preview-container';
    container.innerHTML = `
        <div class="news-preview-toolbar">
            <button class="preview-btn preview-open-btn" onclick="window.open('${escapeHtml(url)}', '_blank'); event.stopPropagation();">
                &#128279; 访问原始链接
            </button>
            <button class="preview-btn preview-close-btn" onclick="closeNewsPreview(this.closest('.news-preview-container')); event.stopPropagation();">
                &#10005; 收起
            </button>
        </div>
        <div class="news-preview-loading">
            <div class="spinner"></div>
            正在加载预览...
        </div>
    `;

    // 插入到被点击条目之后
    articleEl.insertAdjacentElement('afterend', container);

    // 触发展开动画（需要延迟以触发 CSS transition）
    requestAnimationFrame(() => {
        container.classList.add('active');
    });

    // 发起 API 请求
    fetch(`/api/news/preview?url=${encodeURIComponent(url)}`, {
        signal: currentPreviewController.signal
    })
    .then(res => res.json())
    .then(data => {
        const loadingEl = container.querySelector('.news-preview-loading');
        if (!loadingEl) return; // 容器已被移除

        if (data.success) {
            loadingEl.outerHTML = `<iframe class="news-preview-iframe" sandbox="allow-same-origin" srcdoc="${escapeHtml(data.data.html)}"></iframe>`;
        } else {
            loadingEl.outerHTML = `
                <div class="news-preview-error">
                    <div class="error-icon">&#9888;</div>
                    <div>无法加载预览内容</div>
                    <div>请点击上方「访问原始链接」查看原文</div>
                </div>
            `;
        }
    })
    .catch(err => {
        if (err.name === 'AbortError') return; // 请求被取消，忽略
        const loadingEl = container.querySelector('.news-preview-loading');
        if (loadingEl) {
            loadingEl.outerHTML = `
                <div class="news-preview-error">
                    <div class="error-icon">&#9888;</div>
                    <div>无法加载预览内容</div>
                    <div>请点击上方「访问原始链接」查看原文</div>
                </div>
            `;
        }
    });
}

/**
 * 关闭预览区域（带动画）
 */
function closeNewsPreview(container) {
    if (!container) return;
    container.classList.remove('active');
    setTimeout(() => {
        container.remove();
    }, 300); // 等待收起动画完成
}
```

**Step 2: 提交**

```bash
git add static/js/dashboard.js
git commit -m "feat: 新增 openNewsPreview/closeNewsPreview 预览核心函数"
```

---

### Task 4: 前端 JS — 改造所有新闻点击跳转

**Files:**
- Modify: `static/js/dashboard.js` — 改造约 8 处 `window.open` 调用

**Step 1: 改造 `latest-article-item` 点击（约第392行）**

将：
```javascript
<div class="latest-article-item" onclick="window.open('${escapeHtml(article.url)}', '_blank')">
```

改为：
```javascript
<div class="latest-article-item" onclick="openNewsPreview('${escapeHtml(article.url)}', this)">
```

**Step 2: 改造 `source-article-item` 点击（约第3513行）**

将：
```javascript
<div class="source-article-item" onclick="window.open('${escapeHtml(article.url || '')}', '_blank')">
```

改为：
```javascript
<div class="source-article-item" onclick="openNewsPreview('${escapeHtml(article.url || '')}', this)">
```

**Step 3: 改造风控告警点击 — 第一处（约第847/851/856行）**

将三处 `window.open(url, '_blank');` 统一改为：

```javascript
// 找到对应的告警 DOM 元素并打开预览
const alertEl = document.querySelector(`.alert-item[data-url="${url}"]`);
if (alertEl) {
    openNewsPreview(url, alertEl);
} else {
    window.open(url, '_blank');
}
```

注意：需要在告警列表渲染时给 `.alert-item` 添加 `data-url` 属性。

**Step 4: 改造风控告警点击 — 第二处（约第2205/2208/2212行）**

与 Step 3 同样的改造逻辑。

**Step 5: 成果展示 `openAchievementLink` 保持不变**

`openAchievementLink(url)` 函数（第3831行）是成果展示的链接，**不改造**，保持直接跳转行为。

**Step 6: 提交**

```bash
git add static/js/dashboard.js
git commit -m "feat: 改造新闻列表和告警的点击跳转为内嵌预览"
```

---

### Task 5: 集成验证

**Step 1: 启动应用手动测试**

```bash
python app.py
```

**Step 2: 验证清单**

- [ ] 点击最新文章列表中的新闻 → 展开预览区域，显示加载动画，然后 iframe 渲染
- [ ] 再次点击同一条新闻 → 收起预览
- [ ] 点击另一条新闻 → 前一条收起，新的展开
- [ ] 点击「访问原始链接」按钮 → 新标签页打开原始页面
- [ ] 点击「收起」按钮 → 预览收起
- [ ] 来源文章列表中的新闻 → 同样展开预览
- [ ] 风控告警列表点击 → 展开预览（同时标记已读）
- [ ] 抓取失败时 → 显示错误提示，原始链接按钮可用
- [ ] 成果展示链接 → 仍然直接跳转（未改造）
- [ ] 移动端 → 预览区域高度适配

**Step 3: 最终提交并推送**

```bash
git push
```
