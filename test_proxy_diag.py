# -*- coding: utf-8 -*-
"""
精确诊断 crawl4ai / Playwright 代理问题
分三层测试：Playwright 直连 → Playwright+代理 → crawl4ai+代理
"""

import asyncio
import time
import urllib3
urllib3.disable_warnings()

PROXY_HOST = "us.proxy.geonode.io"
PROXY_PORT = 9000
PROXY_USER = "geonode_pzDMwtR0xl-type-residential"
PROXY_PASS = "5c614bb3-07fc-4380-b34b-94af665dfa1c"
TARGET_URL = "https://www.foxnews.com"


async def test_playwright_direct():
    """Playwright 直连（不用代理）"""
    print("\n[1/4] Playwright 直连")
    print("-" * 40)
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            start = time.time()
            resp = await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=20000)
            elapsed = time.time() - start
            html = await page.content()
            print(f"  状态码: {resp.status}")
            print(f"  耗时:   {elapsed:.2f}s")
            print(f"  HTML:   {len(html)} 字符")
            await browser.close()
            return True
    except Exception as e:
        print(f"  ❌ {type(e).__name__}: {e}")
        return False


async def test_playwright_proxy():
    """Playwright + 代理（launch 级别传入）"""
    print("\n[2/4] Playwright + 代理 (launch 级别)")
    print("-" * 40)
    try:
        from playwright.async_api import async_playwright
        proxy_cfg = {
            "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
            "username": PROXY_USER,
            "password": PROXY_PASS,
        }
        print(f"  proxy server:   {proxy_cfg['server']}")
        print(f"  proxy username: {PROXY_USER[:20]}...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                proxy=proxy_cfg
            )
            page = await browser.new_page()
            start = time.time()
            resp = await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            elapsed = time.time() - start
            html = await page.content()
            print(f"  状态码: {resp.status}")
            print(f"  耗时:   {elapsed:.2f}s")
            print(f"  HTML:   {len(html)} 字符")
            await browser.close()
            return True
    except Exception as e:
        print(f"  ❌ {type(e).__name__}: {e}")
        return False


async def test_playwright_proxy_context():
    """Playwright + 代理（context 级别传入）"""
    print("\n[3/4] Playwright + 代理 (context 级别)")
    print("-" * 40)
    try:
        from playwright.async_api import async_playwright
        proxy_cfg = {
            "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
            "username": PROXY_USER,
            "password": PROXY_PASS,
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(proxy=proxy_cfg)
            page = await context.new_page()
            start = time.time()
            resp = await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            elapsed = time.time() - start
            html = await page.content()
            print(f"  状态码: {resp.status}")
            print(f"  耗时:   {elapsed:.2f}s")
            print(f"  HTML:   {len(html)} 字符")
            await browser.close()
            return True
    except Exception as e:
        print(f"  ❌ {type(e).__name__}: {e}")
        return False


async def test_crawl4ai_proxy():
    """crawl4ai + proxy_config"""
    print("\n[4/4] crawl4ai + proxy_config")
    print("-" * 40)
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
        proxy_config = {
            "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
            "username": PROXY_USER,
            "password": PROXY_PASS,
        }
        browser_cfg = BrowserConfig(
            headless=True,
            verbose=True,  # 开启详细日志
            proxy_config=proxy_config
        )
        config = CrawlerRunConfig(
            wait_until="domcontentloaded",
            page_timeout=30000,
            cache_mode=CacheMode.BYPASS
        )
        start = time.time()
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(TARGET_URL, config=config)
            elapsed = time.time() - start
            print(f"  成功:   {result.success}")
            print(f"  耗时:   {elapsed:.2f}s")
            if result.success:
                print(f"  HTML:   {len(result.html)} 字符")
            else:
                err = getattr(result, 'error_message', None) or getattr(result, 'status_code', '未知')
                print(f"  错误:   {err}")
            return result.success
    except Exception as e:
        print(f"  ❌ {type(e).__name__}: {e}")
        return False


async def main():
    print("=" * 60)
    print("  crawl4ai / Playwright 代理诊断")
    print(f"  目标: {TARGET_URL}")
    print(f"  代理: {PROXY_HOST}:{PROXY_PORT}")
    print("=" * 60)

    results = {}
    results["Playwright 直连"] = await test_playwright_direct()
    results["Playwright+代理 (launch)"] = await test_playwright_proxy()
    results["Playwright+代理 (context)"] = await test_playwright_proxy_context()
    results["crawl4ai+proxy_config"] = await test_crawl4ai_proxy()

    print("\n" + "=" * 60)
    print("  诊断结果")
    print("=" * 60)
    for name, ok in results.items():
        print(f"  {'✅' if ok else '❌'}  {name}")

    # 给出建议
    print("\n  📋 建议:")
    if results["Playwright+代理 (launch)"] or results["Playwright+代理 (context)"]:
        if not results["crawl4ai+proxy_config"]:
            print("  → Playwright 代理正常，问题在 crawl4ai 层")
            print("  → 需要绕过 crawl4ai，直接用 Playwright 或 requests")
        else:
            print("  → 全部正常！")
    else:
        if results["Playwright 直连"]:
            print("  → Playwright 直连正常但代理失败")
            print("  → 代理可能不支持 Playwright/Chromium CONNECT 隧道")
            print("  → 建议：代理站点改用 requests 库抓取")
        else:
            print("  → Playwright 本身就有问题，需要检查安装")


if __name__ == '__main__':
    asyncio.run(main())
