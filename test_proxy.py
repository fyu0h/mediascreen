# -*- coding: utf-8 -*-
"""
代理连接独立测试脚本
测试 GeoNode 住宅代理是否能正常访问目标站点
"""

import sys
import time
import requests

# ========== 代理配置 ==========
PROXY_HOST = "us.proxy.geonode.io"
PROXY_PORT = 9000
PROXY_USER = "geonode_pzDMwtR0xl-type-residential"
PROXY_PASS = "5c614bb3-07fc-4380-b34b-94af665dfa1c"
PROXY_URL = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

# 测试目标
TEST_URLS = [
    "https://httpbin.org/ip",
    "https://www.foxnews.com",
    "https://www.bbc.com",
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def test_requests_direct(url: str) -> bool:
    """直连测试"""
    print(f"\n{'='*60}")
    print(f"[直连] {url}")
    print('='*60)
    try:
        start = time.time()
        resp = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        elapsed = time.time() - start
        print(f"  状态码: {resp.status_code}")
        print(f"  耗时:   {elapsed:.2f}s")
        print(f"  内容长度: {len(resp.text)} 字符")
        if 'httpbin' in url:
            print(f"  出口 IP: {resp.json().get('origin', '未知')}")
        else:
            print(f"  标题: {resp.text[:200]}...")
        return resp.status_code == 200
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return False


def test_requests_proxy(url: str) -> bool:
    """通过代理测试"""
    print(f"\n{'='*60}")
    print(f"[代理] {url}")
    print(f"  代理: {PROXY_HOST}:{PROXY_PORT}")
    print('='*60)
    proxies = {"http": PROXY_URL, "https": PROXY_URL}
    try:
        start = time.time()
        resp = requests.get(url, headers=HEADERS, timeout=30, proxies=proxies, verify=False)
        elapsed = time.time() - start
        print(f"  状态码: {resp.status_code}")
        print(f"  耗时:   {elapsed:.2f}s")
        print(f"  内容长度: {len(resp.text)} 字符")
        if 'httpbin' in url:
            print(f"  出口 IP: {resp.json().get('origin', '未知')}")
        else:
            # 打印前300字符
            print(f"  内容预览: {resp.text[:300]}...")
        return resp.status_code == 200
    except requests.exceptions.ProxyError as e:
        print(f"  ❌ 代理错误: {e}")
        return False
    except requests.exceptions.ConnectTimeout:
        print(f"  ❌ 代理连接超时")
        return False
    except requests.exceptions.Timeout:
        print(f"  ❌ 请求超时")
        return False
    except Exception as e:
        print(f"  ❌ 失败: {type(e).__name__}: {e}")
        return False


def test_crawl4ai_proxy(url: str) -> bool:
    """通过 crawl4ai 无头浏览器 + 代理测试"""
    print(f"\n{'='*60}")
    print(f"[crawl4ai + 代理] {url}")
    print('='*60)
    try:
        import asyncio
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

        async def _do_fetch():
            # 使用 proxy_config（新 API）
            proxy_config = {
                "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                "username": PROXY_USER,
                "password": PROXY_PASS,
            }
            browser_cfg = BrowserConfig(
                headless=True,
                verbose=False,
                proxy_config=proxy_config
            )
            config = CrawlerRunConfig(
                wait_until="domcontentloaded",
                page_timeout=30000,
                cache_mode=CacheMode.BYPASS
            )
            start = time.time()
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                result = await crawler.arun(url, config=config)
                elapsed = time.time() - start
                print(f"  成功: {result.success}")
                print(f"  耗时: {elapsed:.2f}s")
                if result.success:
                    print(f"  HTML 长度: {len(result.html)} 字符")
                    print(f"  内容预览: {result.html[:300]}...")
                else:
                    print(f"  错误: {result.error_message if hasattr(result, 'error_message') else '未知'}")
                return result.success

        return asyncio.run(_do_fetch())
    except ImportError:
        print("  ⚠️ crawl4ai 未安装，跳过此测试")
        return False
    except Exception as e:
        print(f"  ❌ 失败: {type(e).__name__}: {e}")
        return False


def test_crawl4ai_proxy_string(url: str) -> bool:
    """通过 crawl4ai 无头浏览器 + 代理（字符串格式）测试"""
    print(f"\n{'='*60}")
    print(f"[crawl4ai + 代理字符串] {url}")
    print('='*60)
    try:
        import asyncio
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

        async def _do_fetch():
            # 使用旧的字符串格式，看是否也能工作
            browser_cfg = BrowserConfig(
                headless=True,
                verbose=False,
                proxy=PROXY_URL
            )
            config = CrawlerRunConfig(
                wait_until="domcontentloaded",
                page_timeout=30000,
                cache_mode=CacheMode.BYPASS
            )
            start = time.time()
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                result = await crawler.arun(url, config=config)
                elapsed = time.time() - start
                print(f"  成功: {result.success}")
                print(f"  耗时: {elapsed:.2f}s")
                if result.success:
                    print(f"  HTML 长度: {len(result.html)} 字符")
                else:
                    print(f"  错误: {result.error_message if hasattr(result, 'error_message') else '未知'}")
                return result.success

        return asyncio.run(_do_fetch())
    except ImportError:
        print("  ⚠️ crawl4ai 未安装，跳过此测试")
        return False
    except Exception as e:
        print(f"  ❌ 失败: {type(e).__name__}: {e}")
        return False


def main():
    print("=" * 60)
    print("  GeoNode 代理连接测试")
    print(f"  代理: {PROXY_HOST}:{PROXY_PORT}")
    print(f"  用户: {PROXY_USER[:20]}...")
    print("=" * 60)

    results = {}

    # ===== 第一阶段：requests 测试 =====
    print("\n\n▶ 第一阶段：requests 库测试")
    print("─" * 40)

    for url in TEST_URLS:
        # 直连
        key_direct = f"直连 {url}"
        results[key_direct] = test_requests_direct(url)

        # 代理
        key_proxy = f"代理 {url}"
        results[key_proxy] = test_requests_proxy(url)

    # ===== 第二阶段：crawl4ai 测试 =====
    print("\n\n▶ 第二阶段：crawl4ai 无头浏览器测试")
    print("─" * 40)

    # 只测试 foxnews（最关键的）
    fox_url = "https://www.foxnews.com"

    key_c4ai = f"crawl4ai proxy_config {fox_url}"
    results[key_c4ai] = test_crawl4ai_proxy(fox_url)

    key_c4ai_str = f"crawl4ai proxy字符串 {fox_url}"
    results[key_c4ai_str] = test_crawl4ai_proxy_string(fox_url)

    # ===== 汇总 =====
    print("\n\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)
    for name, ok in results.items():
        status = "✅ 成功" if ok else "❌ 失败"
        print(f"  {status}  {name}")

    success_count = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  总计: {success_count}/{total} 通过")


if __name__ == '__main__':
    # 禁用 requests 的 SSL 警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
