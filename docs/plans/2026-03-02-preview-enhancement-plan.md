# 新闻预览系统增强 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复预览回退链截断 bug，引入 curl_cffi + trafilatura 增强抓取和提取能力，添加预览缓存和站点健康度监控。

**Architecture:** 分四阶段渐进实施——P0 修复现有 bug 并验证 Playwright ARM64 可用性；P1 引入 curl_cffi（TLS 指纹伪装）和 trafilatura（专业正文提取）作为增强层；P2 添加预览缓存、内容质量标识和站点健康度监控；P3 按需部署 x86 渲染代理。每阶段独立可验证，不阻塞后续阶段。

**Tech Stack:** Python 3.10+ / Flask / MongoDB / curl_cffi / trafilatura / Playwright v1.40+

**无自动化测试**：本项目无测试框架，所有验证通过手动 API 调用完成。

---

## 阶段一：P0 — 修复与止血（优先级最高）

### Task 1: 修复代理模式下 Level 2 回退链截断

**问题：** `routes/api.py:4100` 和 `4132` 行的 `if not proxy_url:` 导致代理模式下 Level 2（crawl4ai）和 Level 3（截图）被完全跳过，4级回退链退化为2级。

**Files:**
- Modify: `routes/api.py:4098-4142`

**Step 1: 修改 Level 2 — 代理模式下使用 curl_cffi 或 requests 增强抓取**

将第 4098-4128 行从：

```python
        # ===== Level 2: 无头浏览器 (crawl4ai) + 正文提取 =====
        # 代理模式跳过 crawl4ai（Playwright 代理隧道兼容性差，必定超时）
        if not proxy_url:
            try:
                import asyncio
                import os
                from plugins.crawler import get_crawler
                old_env = os.environ.get('PYTHONIOENCODING')
                os.environ['PYTHONIOENCODING'] = 'utf-8'
                crawler = get_crawler()
                loop = asyncio.new_event_loop()
                try:
                    crawler_html = loop.run_until_complete(crawler.fetch_page(url, timeout=20))
                finally:
                    loop.close()
                    if old_env is None:
                        os.environ.pop('PYTHONIOENCODING', None)
                    else:
                        os.environ['PYTHONIOENCODING'] = old_env

                if crawler_html:
                    title, blocks = _extract_content_blocks(crawler_html, base_url)
                    if _content_quality_ok(blocks):
                        return success_response({
                            'type': 'content',
                            'title': title,
                            'url': url,
                            'content': blocks
                        })
            except Exception as l2_err:
                log_error(f"Level 2 无头浏览器抓取失败: {url}", str(l2_err))
```

改为：

```python
        # ===== Level 2: 增强抓取 + 正文提取 =====
        # 无代理 → crawl4ai 无头浏览器 | 有代理 → curl_cffi/requests 增强请求头
        try:
            crawler_html = ''
            if not proxy_url:
                # 无代理：尝试 crawl4ai 无头浏览器（支持 JS 渲染）
                try:
                    import asyncio
                    import os
                    from plugins.crawler import get_crawler
                    old_env = os.environ.get('PYTHONIOENCODING')
                    os.environ['PYTHONIOENCODING'] = 'utf-8'
                    crawler = get_crawler()
                    loop = asyncio.new_event_loop()
                    try:
                        crawler_html = loop.run_until_complete(crawler.fetch_page(url, timeout=20))
                    finally:
                        loop.close()
                        if old_env is None:
                            os.environ.pop('PYTHONIOENCODING', None)
                        else:
                            os.environ['PYTHONIOENCODING'] = old_env
                except Exception:
                    crawler_html = ''
            else:
                # 有代理：使用 curl_cffi 模拟浏览器 TLS 指纹（如果可用），否则用增强 requests
                crawler_html = _enhanced_fetch(url, proxy_url)

            if crawler_html:
                title, blocks = _extract_content_blocks(crawler_html, base_url)
                if _content_quality_ok(blocks):
                    return success_response({
                        'type': 'content',
                        'title': title,
                        'url': url,
                        'content': blocks
                    })
        except Exception as l2_err:
            log_error(f"Level 2 增强抓取失败: {url}", str(l2_err))
```

**Step 2: 修改 Level 3 — 代理模式下仍可尝试截图（如果 Playwright 可用）**

将第 4130-4142 行从：

```python
        # ===== Level 3: Playwright 全页截图 =====
        # 代理模式跳过 Playwright 截图（同样不兼容代理隧道）
        if not proxy_url:
            try:
                screenshot_b64 = _take_page_screenshot(url)
                if screenshot_b64:
                    return success_response({
                        'type': 'screenshot',
                        'image': f'data:image/png;base64,{screenshot_b64}',
                        'url': url
                    })
            except Exception as l3_err:
                log_error(f"Level 3 截图失败: {url}", str(l3_err))
```

改为：

```python
        # ===== Level 3: Playwright 全页截图 =====
        # 无论是否有代理都尝试截图（Playwright 自身支持代理参数）
        try:
            screenshot_b64 = _take_page_screenshot(url)
            if screenshot_b64:
                return success_response({
                    'type': 'screenshot',
                    'image': f'data:image/png;base64,{screenshot_b64}',
                    'url': url
                })
        except Exception as l3_err:
            log_error(f"Level 3 截图失败: {url}", str(l3_err))
```

**Step 3: 添加 `_enhanced_fetch` 辅助函数**

在 `routes/api.py` 的 `_get_global_proxy_url` 函数前（约第 4005 行）添加：

```python
def _enhanced_fetch(url: str, proxy_url: str = '') -> str:
    """增强 HTTP 抓取 — 尝试 curl_cffi（TLS 指纹伪装），回退到 requests Session"""
    import requests as http_requests

    # 增强请求头（模拟真实浏览器完整 headers）
    enhanced_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Sec-Ch-Ua': '"Chromium";v="120", "Google Chrome";v="120", "Not-A.Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'Connection': 'keep-alive',
    }
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    # 尝试 curl_cffi（模拟浏览器 TLS 指纹）
    try:
        from curl_cffi import requests as curl_requests
        from models.settings import load_settings
        settings = load_settings()
        impersonate = settings.get('crawler', {}).get('curl_cffi_impersonate', 'chrome120')
        resp = curl_requests.get(
            url,
            headers=enhanced_headers,
            timeout=15,
            verify=False,
            proxies=proxies,
            impersonate=impersonate
        )
        if resp.status_code == 200:
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return resp.text
    except ImportError:
        pass  # curl_cffi 未安装，回退
    except Exception:
        pass  # curl_cffi 请求失败，回退

    # 回退：使用 requests Session（复用 TCP 连接和 Cookie）
    try:
        s = http_requests.Session()
        s.headers.update(enhanced_headers)
        resp = s.get(url, timeout=15, verify=False, proxies=proxies)
        if resp.status_code == 200:
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return resp.text
    except Exception:
        pass

    return ''
```

**Step 4: 手动验证**

```bash
# 启动开发服务器
python app.py

# 测试预览端点（无代理）
curl "http://localhost:5000/api/news/preview?url=https://www.bbc.com/news" -b "session=<cookie>"

# 测试预览端点（有代理时 — 确认 Level 2 不再被跳过）
# 在 settings.json 中开启代理后重复测试
```

**Step 5: 提交**

```bash
git add routes/api.py
git commit -m "fix: 修复代理模式下预览回退链截断 — Level 2/3 不再被跳过"
```

---

### Task 2: 更新 settings.json 默认配置支持 curl_cffi

**Files:**
- Modify: `models/settings.py:52-66`

**Step 1: 在 DEFAULT_SETTINGS 的 crawler.proxy 同级添加 curl_cffi 配置**

在 `models/settings.py` 的 `DEFAULT_SETTINGS['crawler']` 字典中，`proxy` 键之后添加：

```python
'crawler': {
    'timeout': 30,
    'max_articles': 500,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'auto_crawl_enabled': False,
    'auto_crawl_interval': 30,
    'proxy': {
        'enabled': False,
        'host': '',
        'port': 9000,
        'username': '',
        'password': '',
        'protocol': 'http'
    },
    'curl_cffi_impersonate': 'chrome120',  # curl_cffi TLS 指纹伪装版本
},
```

**Step 2: 提交**

```bash
git add models/settings.py
git commit -m "feat: settings 增加 curl_cffi_impersonate 配置项"
```

---

### Task 3: Playwright ARM64 Chromium 可用性验证脚本

**目的：** 在 Oracle Cloud ARM64 服务器上验证 Playwright v1.40+ 自带的 ARM64 Chromium 是否可用。

**Files:**
- Create: `test_playwright_arm64.py`

**Step 1: 创建验证脚本**

```python
#!/usr/bin/env python3
"""Playwright ARM64 Chromium 可用性验证脚本"""
import sys
import platform

def main():
    print(f"系统架构: {platform.machine()}")
    print(f"操作系统: {platform.platform()}")
    print(f"Python: {sys.version}")
    print()

    # 检查 Playwright 版本
    try:
        import playwright
        print(f"Playwright 版本: {playwright.__version__}")
    except ImportError:
        print("❌ Playwright 未安装")
        print("   请执行: pip install playwright>=1.40")
        return False

    # 检查 Chromium 二进制
    print("\n--- 测试 Chromium 启动 ---")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            page.goto('https://httpbin.org/ip', timeout=15000)
            content = page.content()
            print(f"✅ Chromium 启动成功，页面内容长度: {len(content)}")
            browser.close()
            print("✅ Chromium ARM64 验证通过")
            return True
    except Exception as e:
        print(f"❌ Chromium 启动失败: {e}")

    # 尝试 Firefox 备选
    print("\n--- 测试 Firefox 备选 ---")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            page = browser.new_page()
            page.goto('https://httpbin.org/ip', timeout=15000)
            content = page.content()
            print(f"✅ Firefox 启动成功，页面内容长度: {len(content)}")
            browser.close()
            print("✅ Firefox ARM64 验证通过")
            return True
    except Exception as e:
        print(f"❌ Firefox 启动失败: {e}")

    # 尝试系统 Chromium
    print("\n--- 测试系统 Chromium ---")
    import shutil
    for name in ['chromium-browser', 'chromium', 'google-chrome']:
        path = shutil.which(name)
        if path:
            print(f"  找到系统浏览器: {path}")
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        executable_path=path,
                        args=['--no-sandbox', '--disable-dev-shm-usage']
                    )
                    page = browser.new_page()
                    page.goto('https://httpbin.org/ip', timeout=15000)
                    content = page.content()
                    print(f"✅ 系统 {name} 启动成功")
                    browser.close()
                    return True
            except Exception as e:
                print(f"  ❌ {name} 启动失败: {e}")

    print("\n❌ 所有浏览器方案均失败，建议启用 x86 VPS 渲染代理方案")
    return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
```

**Step 2: 在服务器上执行验证**

```bash
# SSH 到 Oracle ARM64 服务器后执行
pip install playwright>=1.40
playwright install chromium
python test_playwright_arm64.py
```

**Step 3: 根据验证结果决定后续方案**

- ✅ 通过 → 继续使用 Playwright，更新 crawl4ai 配置
- ❌ 失败 → 记录错误信息，评估 Plan B（firefox-esr）或 Plan C（x86 VPS）

**Step 4: 提交验证脚本**

```bash
git add test_playwright_arm64.py
git commit -m "feat: 添加 Playwright ARM64 可用性验证脚本"
```

---

## 阶段二：P1 — HTTP 层强化与正文提取升级

### Task 4: 引入 curl_cffi 依赖

**Files:**
- Modify: `requirements.txt:19-20`

**Step 1: 在 requirements.txt 中添加 curl_cffi 和 trafilatura**

在 `# Crawl4AI（可选）` 注释后添加：

```
# Crawl4AI（可选，用于动态页面爬取）
# crawl4ai>=0.2.0

# TLS 指纹伪装 HTTP 客户端（可选，用于绕过反爬）
# curl_cffi>=0.7.0

# 专业网页正文提取（可选，提升预览正文质量）
# trafilatura>=1.8.0
```

注意：保持注释形式（可选依赖），与 crawl4ai 风格一致。服务器上手动安装。

**Step 2: 在服务器上安装**

```bash
pip install curl_cffi>=0.7.0
pip install trafilatura>=1.8.0
```

**Step 3: 提交**

```bash
git add requirements.txt
git commit -m "feat: requirements 增加 curl_cffi 和 trafilatura 可选依赖"
```

---

### Task 5: 引入 trafilatura 正文提取增强

**Files:**
- Modify: `routes/api.py:3750-3850`

**Step 1: 在 `_extract_content_blocks` 函数前添加 trafilatura 提取函数**

在 `routes/api.py` 约第 3748 行（`_extract_content_blocks` 函数定义前）添加：

```python
def _extract_with_trafilatura(html: str, url: str) -> tuple:
    """使用 trafilatura 提取正文，返回 (title, content_blocks) 或 (None, None)"""
    try:
        import trafilatura
        # 提取结构化数据（含标题）
        result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            include_images=False,
            favor_precision=True,
            deduplicate=True,
        )
        if not result or len(result) < 50:
            return None, None

        # 提取标题
        metadata = trafilatura.extract(
            html, url=url, output_format='xmltei',
            include_comments=False, favor_precision=True
        )
        title = ''
        if metadata:
            from bs4 import BeautifulSoup
            tei_soup = BeautifulSoup(metadata, 'html.parser')
            title_tag = tei_soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
        if not title:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            t = soup.find('title')
            if t:
                title = t.get_text(strip=True)

        # 将纯文本转换为 content blocks 格式
        blocks = []
        for para in result.split('\n'):
            para = para.strip()
            if not para:
                continue
            # 简单启发式：全大写或较短的文本可能是标题
            if len(para) < 80 and para == para.upper() and len(para) > 5:
                blocks.append({'type': 'heading', 'level': 3, 'text': para})
            else:
                blocks.append({'type': 'paragraph', 'text': para})

        if blocks:
            return title, blocks
    except ImportError:
        pass  # trafilatura 未安装
    except Exception:
        pass
    return None, None
```

**Step 2: 修改预览端点 Level 1 的正文提取逻辑**

在 `routes/api.py` 约第 4086-4096 行，将 Level 1 成功获取 HTML 后的提取逻辑从：

```python
        if html and not is_cf:
            title, blocks = _extract_content_blocks(html, base_url)
            if _content_quality_ok(blocks):
                return success_response({
                    'type': 'content',
                    'title': title,
                    'url': url,
                    'content': blocks
                })
```

改为：

```python
        if html and not is_cf:
            # 优先使用 trafilatura 提取（精度更高）
            title, blocks = _extract_with_trafilatura(html, url)
            if not blocks:
                # 回退到 BeautifulSoup 自研提取器
                title, blocks = _extract_content_blocks(html, base_url)
            if _content_quality_ok(blocks):
                return success_response({
                    'type': 'content',
                    'title': title,
                    'url': url,
                    'content': blocks
                })
```

**Step 3: 同样修改 Level 2 的正文提取逻辑**

在 Level 2 中 `if crawler_html:` 之后，同样使用 trafilatura 优先提取：

```python
            if crawler_html:
                # 优先使用 trafilatura 提取
                title, blocks = _extract_with_trafilatura(crawler_html, url)
                if not blocks:
                    title, blocks = _extract_content_blocks(crawler_html, base_url)
                if _content_quality_ok(blocks):
                    return success_response({
                        'type': 'content',
                        'title': title,
                        'url': url,
                        'content': blocks
                    })
```

**Step 4: 手动验证**

```bash
python app.py
# 测试一个中文新闻页面
curl "http://localhost:5000/api/news/preview?url=https://www.zaobao.com.sg" -b "session=<cookie>"
# 测试一个英文新闻页面
curl "http://localhost:5000/api/news/preview?url=https://www.bbc.com/news" -b "session=<cookie>"
```

**Step 5: 提交**

```bash
git add routes/api.py
git commit -m "feat: 引入 trafilatura 作为首选正文提取器，BeautifulSoup 作为回退"
```

---

### Task 6: 优化正文质量门槛（自适应）

**Files:**
- Modify: `routes/api.py:3844-3850`

**Step 1: 将 `_content_quality_ok` 改为自适应判断**

将原函数：

```python
def _content_quality_ok(content_blocks: list) -> bool:
    """检查提取内容质量是否足够（至少3个文本块且总文本≥100字符）"""
    text_blocks = [b for b in content_blocks if b['type'] in ('paragraph', 'heading', 'blockquote')]
    if len(text_blocks) < 3:
        return False
    total_text = sum(len(b.get('text', '')) for b in text_blocks)
    return total_text >= 100
```

改为：

```python
def _content_quality_ok(content_blocks: list) -> bool:
    """自适应质量检查 — 根据内容特征动态调整门槛"""
    if not content_blocks:
        return False

    text_blocks = [b for b in content_blocks if b['type'] in ('paragraph', 'heading', 'blockquote')]
    if not text_blocks:
        return False

    total_text = sum(len(b.get('text', '')) for b in text_blocks)
    block_count = len(text_blocks)

    # 宽松标准：有标题 + 正文，且总文本 ≥ 50 字符（快讯类新闻）
    has_heading = any(b.get('type') == 'heading' for b in text_blocks)
    has_paragraph = any(b.get('type') == 'paragraph' for b in text_blocks)
    if has_heading and has_paragraph and total_text >= 50:
        return True

    # 长文本标准：单段长文（某些站点全文放在一个 <p> 中）
    if total_text >= 200:
        return True

    # 原始标准：至少 3 个文本块，总字符 ≥ 100
    return block_count >= 3 and total_text >= 100
```

**Step 2: 提交**

```bash
git add routes/api.py
git commit -m "feat: 预览质量检查改为自适应门槛，减少快讯类新闻误杀"
```

---

## 阶段三：P2 — 体验优化

### Task 7: 添加预览结果缓存

**Files:**
- Modify: `routes/api.py:4032-4160`（news_preview 函数）
- Modify: `models/mongo.py`（添加缓存集合访问）

**Step 1: 在 `models/mongo.py` 中添加预览缓存集合和 TTL 索引初始化**

在 `models/mongo.py` 中合适位置添加：

```python
def get_preview_cache_collection():
    """获取预览缓存集合"""
    db = get_db()
    return db['preview_cache']

def init_preview_cache_index():
    """初始化预览缓存 TTL 索引（8小时过期）"""
    try:
        col = get_preview_cache_collection()
        col.create_index('cached_at', expireAfterSeconds=28800)
    except Exception:
        pass
```

**Step 2: 在 `routes/api.py` 中添加缓存读写辅助函数**

在 `_enhanced_fetch` 函数附近添加：

```python
def _get_preview_cache(url: str) -> dict:
    """查询预览缓存"""
    try:
        from models.mongo import get_preview_cache_collection
        col = get_preview_cache_collection()
        cache = col.find_one({'url': url})
        if cache:
            return cache.get('result')
    except Exception:
        pass
    return None

def _set_preview_cache(url: str, result: dict):
    """写入预览缓存"""
    try:
        from models.mongo import get_preview_cache_collection
        from datetime import datetime
        col = get_preview_cache_collection()
        col.update_one(
            {'url': url},
            {'$set': {
                'url': url,
                'result': result,
                'cached_at': datetime.utcnow()
            }},
            upsert=True
        )
    except Exception:
        pass
```

**Step 3: 在 `news_preview` 端点入口添加缓存查询，在成功返回前写入缓存**

在 `news_preview` 函数中，SSRF 检查后、Level 1 前添加：

```python
    # 查询预览缓存
    cached_preview = _get_preview_cache(url)
    if cached_preview:
        return success_response(cached_preview)
```

在每个成功的 `return success_response(...)` 前，添加缓存写入：

```python
    # 示例：Level 1 成功返回前
    result_data = {
        'type': 'content',
        'title': title,
        'url': url,
        'content': blocks
    }
    _set_preview_cache(url, result_data)
    return success_response(result_data)
```

对 Level 2、Level 3 的成功路径同样处理。Level 4（缓存摘要）可以不写入预览缓存（本身就是 DB 查询）。

**Step 4: 在 app.py 的 create_app 中初始化 TTL 索引**

在 `app.py` 的 `create_app()` 函数中，其他索引初始化附近添加：

```python
from models.mongo import init_preview_cache_index
init_preview_cache_index()
```

**Step 5: 手动验证**

```bash
python app.py
# 第一次预览（应走完整回退链）
curl "http://localhost:5000/api/news/preview?url=https://www.bbc.com/news" -b "session=<cookie>"
# 第二次预览同一 URL（应命中缓存，毫秒级返回）
curl "http://localhost:5000/api/news/preview?url=https://www.bbc.com/news" -b "session=<cookie>"
```

**Step 6: 提交**

```bash
git add routes/api.py models/mongo.py app.py
git commit -m "feat: 添加预览结果缓存（MongoDB TTL 8小时），同 URL 重复预览零延迟"
```

---

### Task 8: 添加预览内容质量标识

**目的：** 前端显示预览内容时，根据 `quality` 字段提示用户内容是完整正文还是摘要信息。

**Files:**
- Modify: `routes/api.py:4032-4160`（news_preview 返回数据中添加 quality 字段）
- Modify: `templates/index.html`（前端预览弹窗显示质量标识）

**Step 1: 在预览端点每个成功返回中添加 quality 字段**

各级别的返回数据中添加：

```python
# Level 1/2 成功（完整正文）
result_data = {
    'type': 'content',
    'quality': 'full',  # 完整正文
    'title': title,
    'url': url,
    'content': blocks
}

# Level 3 成功（截图）
result_data = {
    'type': 'screenshot',
    'quality': 'screenshot',  # 页面截图
    'image': f'data:image/png;base64,{screenshot_b64}',
    'url': url
}

# Level 4 成功（缓存摘要）
result_data = {
    'type': 'cached',
    'quality': 'summary',  # 仅摘要
    'title': cached['title'],
    'source': cached['source'],
    'pub_date': cached['pub_date'],
    'url': url
}
```

**Step 2: 在前端预览组件中根据 quality 字段显示提示**

在 `templates/index.html` 中处理预览数据渲染的 JavaScript 代码中，根据 `data.quality` 添加提示条：

```javascript
// 在渲染预览内容前，根据 quality 显示提示标签
let qualityBadge = '';
if (data.quality === 'full') {
    qualityBadge = '<span class="preview-badge badge-full">完整正文</span>';
} else if (data.quality === 'screenshot') {
    qualityBadge = '<span class="preview-badge badge-screenshot">页面截图</span>';
} else if (data.quality === 'summary') {
    qualityBadge = '<span class="preview-badge badge-summary">仅摘要信息</span>';
}
```

CSS 样式：

```css
.preview-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    margin-bottom: 8px;
}
.badge-full { background: rgba(0, 200, 83, 0.2); color: #00c853; }
.badge-screenshot { background: rgba(255, 152, 0, 0.2); color: #ff9800; }
.badge-summary { background: rgba(244, 67, 54, 0.2); color: #f44336; }
```

**Step 3: 提交**

```bash
git add routes/api.py templates/index.html
git commit -m "feat: 预览内容添加质量标识（完整正文/截图/仅摘要）"
```

---

### Task 9: 站点健康度监控

**Files:**
- Modify: `models/mongo.py`（添加健康度统计集合）
- Modify: `plugins/crawler.py`（抓取完成后记录成功/失败）
- Modify: `routes/api.py`（添加健康度查询 API）

**Step 1: 在 `models/mongo.py` 中添加健康度集合和操作函数**

```python
def get_site_health_collection():
    """获取站点健康度集合"""
    db = get_db()
    return db['site_health']

def record_site_health(site_id: str, domain: str, success: bool, error_msg: str = ''):
    """记录站点抓取结果"""
    from datetime import datetime
    try:
        col = get_site_health_collection()
        col.update_one(
            {'site_id': site_id},
            {
                '$set': {
                    'domain': domain,
                    'last_attempt': datetime.utcnow(),
                    'last_success': datetime.utcnow() if success else None,
                    'last_error': error_msg if not success else '',
                },
                '$inc': {
                    'total_attempts': 1,
                    'total_successes': 1 if success else 0,
                    'total_failures': 0 if success else 1,
                    'consecutive_failures': 0 if success else 1,
                },
                '$setOnInsert': {'site_id': site_id}
            },
            upsert=True
        )
        # 成功时重置连续失败计数
        if success:
            col.update_one(
                {'site_id': site_id},
                {'$set': {'consecutive_failures': 0}}
            )
    except Exception:
        pass

def get_sites_health() -> list:
    """获取所有站点健康度列表"""
    try:
        col = get_site_health_collection()
        return list(col.find({}, {'_id': 0}).sort('consecutive_failures', -1))
    except Exception:
        return []
```

**Step 2: 在 `plugins/crawler.py` 的 `crawl_site_async` 方法末尾，记录抓取结果**

在 `crawl_site_async` 方法返回前，添加健康度记录：

```python
        # 记录站点健康度
        from models.mongo import record_site_health
        site_id = site.get('id', site.get('domain', ''))
        domain = site.get('domain', '')
        record_site_health(site_id, domain, success=True if articles else False,
                          error_msg='' if articles else '无法获取文章')
```

**Step 3: 在 `routes/api.py` 中添加健康度查询 API**

```python
@api_bp.route('/sites/health', methods=['GET'])
def sites_health():
    """获取所有站点健康度"""
    if 'user' not in session:
        return error_response('未登录', 401)
    from models.mongo import get_sites_health
    health_list = get_sites_health()
    return success_response(health_list)
```

**Step 4: 提交**

```bash
git add models/mongo.py plugins/crawler.py routes/api.py
git commit -m "feat: 添加站点健康度监控（抓取成功率追踪、连续失败计数）"
```

---

## 阶段四：P3 — 远期演进（按需）

### Task 10: x86 VPS 渲染代理（仅 Playwright ARM64 验证失败时执行）

**前置条件：** Task 3 验证脚本确认 Playwright ARM64 Chromium 不可用。

**方案概述：**
1. 租用廉价 x86 VPS（Vultr/Hetzner，$3-5/月，1核1GB 即可）
2. 在 x86 VPS 上部署轻量渲染服务
3. ARM64 主服务器通过 HTTP API 调用渲染服务

**Step 1: 在 x86 VPS 上部署渲染服务**

创建 `render_service.py`：

```python
"""轻量级远程渲染服务 — 部署在 x86 VPS 上"""
from flask import Flask, request, jsonify
import asyncio
import base64

app = Flask(__name__)

@app.route('/render', methods=['POST'])
def render_page():
    """渲染页面并返回 HTML + 可选截图"""
    data = request.json
    url = data.get('url', '')
    screenshot = data.get('screenshot', False)

    async def _render():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=20000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)
            html = await page.content()
            img_b64 = ''
            if screenshot:
                img_bytes = await page.screenshot(full_page=True, type='png')
                img_b64 = base64.b64encode(img_bytes).decode()
            await browser.close()
            return html, img_b64

    loop = asyncio.new_event_loop()
    try:
        html, img = loop.run_until_complete(_render())
        return jsonify({'success': True, 'html': html, 'screenshot': img})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        loop.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8900)
```

```bash
# 在 x86 VPS 上
pip install flask playwright
playwright install chromium
python render_service.py
```

**Step 2: 在主服务器的 settings.json 中配置渲染代理地址**

在 `models/settings.py` 的 DEFAULT_SETTINGS 中添加：

```python
'render_proxy': {
    'enabled': False,
    'url': '',  # 例如 http://<x86-vps-ip>:8900
},
```

**Step 3: 在 `routes/api.py` 中添加远程渲染调用**

在 Level 2/3 失败后、Level 4 前，添加远程渲染尝试：

```python
        # ===== Level 2.5: 远程渲染代理（如果配置了 x86 VPS）=====
        render_proxy = load_settings().get('render_proxy', {})
        if render_proxy.get('enabled') and render_proxy.get('url'):
            try:
                import requests as http_requests
                render_resp = http_requests.post(
                    f"{render_proxy['url']}/render",
                    json={'url': url, 'screenshot': True},
                    timeout=25
                )
                if render_resp.status_code == 200:
                    render_data = render_resp.json()
                    if render_data.get('success'):
                        # 尝试从渲染 HTML 中提取正文
                        if render_data.get('html'):
                            title, blocks = _extract_with_trafilatura(render_data['html'], url)
                            if not blocks:
                                title, blocks = _extract_content_blocks(render_data['html'], base_url)
                            if _content_quality_ok(blocks):
                                result_data = {'type': 'content', 'quality': 'full',
                                              'title': title, 'url': url, 'content': blocks}
                                _set_preview_cache(url, result_data)
                                return success_response(result_data)
                        # 正文提取失败但有截图
                        if render_data.get('screenshot'):
                            result_data = {'type': 'screenshot', 'quality': 'screenshot',
                                          'image': f"data:image/png;base64,{render_data['screenshot']}",
                                          'url': url}
                            _set_preview_cache(url, result_data)
                            return success_response(result_data)
            except Exception as render_err:
                log_error(f"远程渲染代理失败: {url}", str(render_err))
```

**Step 4: 提交**

```bash
git add routes/api.py models/settings.py render_service.py
git commit -m "feat: 支持 x86 VPS 远程渲染代理（Playwright ARM64 不可用时的备选方案）"
```

---

## 实施检查清单

| # | 任务 | 阶段 | 预计耗时 | 依赖 |
|---|------|------|----------|------|
| 1 | 修复代理模式回退链截断 | P0 | 1h | 无 |
| 2 | settings 增加 curl_cffi 配置 | P0 | 15min | 无 |
| 3 | Playwright ARM64 验证脚本 | P0 | 30min | 无 |
| 4 | 添加 curl_cffi/trafilatura 依赖 | P1 | 15min | 无 |
| 5 | 引入 trafilatura 正文提取 | P1 | 1h | Task 4 |
| 6 | 优化质量门槛（自适应） | P1 | 30min | 无 |
| 7 | 预览结果缓存 | P2 | 1h | 无 |
| 8 | 内容质量标识（前后端） | P2 | 1h | Task 7 |
| 9 | 站点健康度监控 | P2 | 1.5h | 无 |
| 10 | x86 VPS 渲染代理 | P3 | 2h | Task 3 失败 |
