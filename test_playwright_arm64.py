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
