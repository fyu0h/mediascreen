# -*- coding: utf-8 -*-
"""
插件通用爬取模块
使用 crawl4ai 进行网页抓取，调用专用解析器提取文章
"""

import asyncio
import time
import threading
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse
from concurrent.futures import TimeoutError as FuturesTimeoutError

from bs4 import BeautifulSoup

# 导入解析器模块
from plugins.parsers import SPECIAL_PARSERS, get_parser

# crawl4ai 导入
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    print("[PluginCrawler] crawl4ai 未安装，将使用 requests 降级模式（不支持 JS 渲染）")


# HTTP 请求头
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}


class PluginCrawler:
    """插件通用爬取器"""

    # 默认超时时间（秒）
    DEFAULT_TIMEOUT = 60
    # 站点特定超时配置（某些站点可能需要更长/更短的超时）
    SITE_TIMEOUTS = {
        'thetimes.com': 30,  # The Times 需要VPN，设置较短超时快速跳过
        'nytimes.com': 45,
    }
    # 重试配置
    MAX_RETRIES = 2
    RETRY_DELAYS = [1, 2]  # 重试间隔（秒）

    def __init__(self):
        if CRAWL4AI_AVAILABLE:
            self.browser_config = BrowserConfig(headless=True, verbose=False)
        else:
            self.browser_config = None
            print("[PluginCrawler] 降级模式: 使用 requests 获取页面，不支持 JS 动态渲染")

    def _build_proxy_url(self) -> str:
        """根据 settings.json 构造代理 URL，配置不完整返回空串"""
        from models.settings import load_settings
        settings = load_settings()
        proxy_cfg = settings.get('crawler', {}).get('proxy', {})

        if not proxy_cfg.get('enabled'):
            return ''

        host = proxy_cfg.get('host', '')
        port = proxy_cfg.get('port', 9000)
        username = proxy_cfg.get('username', '')
        password = proxy_cfg.get('password', '')
        protocol = proxy_cfg.get('protocol', 'http')

        if not host:
            return ''

        if username and password:
            return f"{protocol}://{username}:{password}@{host}:{port}"
        return f"{protocol}://{host}:{port}"

    def _should_use_proxy(self, site: dict) -> bool:
        """判断该站点是否应使用代理（全局开关 + 站点开关均为 True）"""
        from models.settings import load_settings
        settings = load_settings()
        proxy_cfg = settings.get('crawler', {}).get('proxy', {})

        if not proxy_cfg.get('enabled'):
            return False

        from models.plugins import get_subscription
        plugin_id = site.get('plugin_id', '')
        site_id = site.get('id', '')
        if plugin_id and site_id:
            sub = get_subscription(plugin_id, site_id)
            if sub and sub.get('use_proxy'):
                return True
        return False

    def _get_timeout_for_url(self, url: str) -> int:
        """根据URL获取对应的超时时间（秒）"""
        try:
            domain = urlparse(url).netloc.lower()
            # 检查是否有站点特定配置
            for site_domain, timeout in self.SITE_TIMEOUTS.items():
                if site_domain in domain:
                    return timeout
        except Exception:
            pass
        return self.DEFAULT_TIMEOUT

    def _is_retryable_error(self, error: Exception) -> bool:
        """判断错误是否可重试（网络错误、临时故障等）"""
        error_msg = str(error).lower()
        # 不可重试的错误类型
        non_retryable = ['timeout', '404', '403', '401', 'not found', 'forbidden']
        if any(x in error_msg for x in non_retryable):
            return False
        # 可重试：网络错误、连接错误、临时故障
        retryable = ['connection', 'network', 'reset', 'refused', 'temporary', 'eof']
        return any(x in error_msg for x in retryable)

    async def fetch_page(self, url: str, timeout: int = None, proxy_url: str = '') -> str:
        """
        异步获取页面内容
        - crawl4ai 可用时：使用无头浏览器（支持 JS 渲染），带重试机制
        - crawl4ai 不可用时：降级为 requests.get()（纯 HTML）

        Args:
            url: 要抓取的URL
            timeout: 超时时间（秒），None则使用默认配置
            proxy_url: 代理地址

        Returns:
            页面HTML内容，失败或超时返回空字符串
        """
        if timeout is None:
            timeout = self._get_timeout_for_url(url)

        # crawl4ai 不可用时，降级为 requests
        if not CRAWL4AI_AVAILABLE:
            return self.fetch_url_simple(url, timeout=timeout, proxy_url=proxy_url)

        timeout_ms = timeout * 1000
        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # 根据是否有代理动态构造浏览器配置
                if proxy_url:
                    # 解析代理 URL 为 proxy_config 字典格式（crawl4ai 新 API）
                    from urllib.parse import urlparse as _urlparse
                    _parsed_proxy = _urlparse(proxy_url)
                    _proxy_config = {
                        "server": f"{_parsed_proxy.scheme}://{_parsed_proxy.hostname}:{_parsed_proxy.port}",
                    }
                    if _parsed_proxy.username:
                        _proxy_config["username"] = _parsed_proxy.username
                    if _parsed_proxy.password:
                        _proxy_config["password"] = _parsed_proxy.password
                    browser_cfg = BrowserConfig(headless=True, verbose=False, proxy_config=_proxy_config)
                else:
                    browser_cfg = self.browser_config

                config = CrawlerRunConfig(
                    wait_until="domcontentloaded",
                    page_timeout=timeout_ms,
                    cache_mode=CacheMode.BYPASS
                )
                async with AsyncWebCrawler(config=browser_cfg) as crawler:
                    result = await crawler.arun(url, config=config)
                    if result.success:
                        return result.html
                    print(f"[PluginCrawler] 页面抓取未成功 {url}")
                    return ""
            except asyncio.TimeoutError:
                print(f"[PluginCrawler] ⏱️ 超时跳过 ({timeout}秒): {url}")
                return ""
            except Exception as e:
                last_error = e
                error_msg = str(e)
                # 检查是否是超时错误
                if 'Timeout' in error_msg or 'timeout' in error_msg.lower():
                    print(f"[PluginCrawler] ⏱️ 超时跳过 ({timeout}秒): {url}")
                    return ""
                # 检查是否可重试
                if attempt < self.MAX_RETRIES and self._is_retryable_error(e):
                    delay = self.RETRY_DELAYS[attempt] if attempt < len(self.RETRY_DELAYS) else 2
                    print(f"[PluginCrawler] 重试 {attempt + 1}/{self.MAX_RETRIES} ({delay}秒后): {url}")
                    await asyncio.sleep(delay)  # 异步函数中使用异步睡眠，避免阻塞事件循环
                    continue
                print(f"[PluginCrawler] 获取页面失败 {url}: {e}")
                return ""

        print(f"[PluginCrawler] 重试耗尽 {url}: {last_error}")
        return ""

    def fetch_url_simple(self, url: str, timeout: int = 30, proxy_url: str = '') -> str:
        """简单HTTP请求获取页面（降级模式 / sitemap 等不需要渲染的页面）"""
        try:
            headers = {
                **DEFAULT_HEADERS,
                'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,ja;q=0.6,ko;q=0.5'
            }
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            response = requests.get(url, headers=headers, timeout=timeout, proxies=proxies)
            if response.status_code == 200:
                # 自动检测编码，避免中日韩文乱码
                response.encoding = response.apparent_encoding or response.encoding
                return response.text
            return ""
        except Exception as e:
            print(f"[PluginCrawler] HTTP请求失败 {url}: {e}")
            return ""

    def parse_articles_generic(self, html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        通用解析逻辑，从页面中提取所有看起来像新闻的链接
        当没有专用解析器时使用此方法
        """
        articles = []
        seen = set()
        base_url = site.get('url', '')
        source_name = site.get('name', '未知')
        country_code = site.get('country_code', '')
        coords = site.get('coords', [])

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # 移除导航、页眉、页脚等非内容区域
            for tag in soup.select('nav, header, footer, .nav, .menu, .sidebar, .advertisement, .ad, script, style, noscript'):
                tag.decompose()

            # 提取所有链接
            for link in soup.find_all('a', href=True):
                href = link.get('href', '').strip()
                title = link.get_text(strip=True)

                # 跳过短标题（可能是导航链接）
                if len(title) < 8:
                    continue

                # 跳过太长的标题（可能是段落文本）
                if len(title) > 200:
                    title = title[:200]

                # 补全相对 URL
                if not href.startswith('http'):
                    href = urljoin(base_url, href)

                # 过滤非文章链接
                href_lower = href.lower()
                if any(x in href_lower for x in [
                    'login', 'signup', 'register', 'contact', 'about',
                    'javascript:', 'mailto:', '#', 'privacy', 'terms',
                    'subscribe', 'cart', 'account', 'search'
                ]):
                    continue

                # 只保留同域名的链接
                try:
                    link_domain = urlparse(href).netloc.lower()
                    base_domain = urlparse(base_url).netloc.lower()
                    # 允许子域名
                    if not (link_domain == base_domain or link_domain.endswith('.' + base_domain) or base_domain.endswith('.' + link_domain)):
                        continue
                except Exception:
                    continue

                # 去重
                if href in seen:
                    continue
                seen.add(href)

                articles.append({
                    'loc': href,
                    'title': title,
                    'source_name': source_name,
                    'country_code': country_code,
                    'coords': coords,
                    'pub_date': datetime.now(),
                    'fetched_at': datetime.now(),
                    'method': 'generic_crawler'
                })

        except Exception as e:
            print(f"[PluginCrawler] 解析页面失败: {e}")

        return articles

    async def crawl_site_async(self, site: Dict[str, Any], max_articles: int = 100) -> Dict[str, Any]:
        """
        异步爬取单个站点

        返回: {success: bool, articles: list, error: str, skipped: bool}
        """
        url = site.get('url', '')
        name = site.get('name', '')
        parser_name = site.get('parser', '')

        if not url:
            return {'success': False, 'articles': [], 'error': '站点 URL 为空', 'skipped': False}

        try:
            # 判断是否使用代理
            proxy_url = ''
            if self._should_use_proxy(site):
                proxy_url = self._build_proxy_url()
                if proxy_url:
                    print(f"[PluginCrawler] 🔒 {name} 使用代理: {site.get('domain', '')}")

            # 获取页面
            # 优先级: 代理模式 → requests | crawl4ai不可用 → requests | 否则 → crawl4ai
            if proxy_url or not CRAWL4AI_AVAILABLE:
                html = self.fetch_url_simple(url, timeout=30, proxy_url=proxy_url)
            else:
                html = await self.fetch_page(url)

            if not html:
                # 区分超时跳过和其他错误
                timeout = self._get_timeout_for_url(url)
                return {
                    'success': False,
                    'articles': [],
                    'error': f'获取页面失败（超时 {timeout} 秒或网络问题）',
                    'skipped': True  # 标记为跳过，不影响整体任务
                }

            # 选择解析器
            if parser_name:
                parser = get_parser(parser_name)
                if parser:
                    # 使用专用解析器
                    articles = parser(html, site)
                    print(f"[PluginCrawler] {name} 使用专用解析器 '{parser_name}'，提取到 {len(articles)} 篇文章")
                else:
                    print(f"[PluginCrawler] 警告: 未找到解析器 '{parser_name}'，使用通用解析器")
                    articles = self.parse_articles_generic(html, site)
            else:
                # 使用通用解析器
                articles = self.parse_articles_generic(html, site)
                print(f"[PluginCrawler] {name} 使用通用解析器，提取到 {len(articles)} 篇文章")

            # 限制数量
            if len(articles) > max_articles:
                articles = articles[:max_articles]

            return {
                'success': True,
                'articles': articles,
                'error': None,
                'skipped': False
            }

        except asyncio.TimeoutError:
            print(f"[PluginCrawler] ⏱️ 站点超时跳过: {name}")
            return {
                'success': False,
                'articles': [],
                'error': f'站点超时，已跳过',
                'skipped': True
            }
        except Exception as e:
            error_msg = str(e)
            is_timeout = 'timeout' in error_msg.lower()
            return {
                'success': False,
                'articles': [],
                'error': f'超时跳过' if is_timeout else str(e),
                'skipped': is_timeout  # 超时标记为跳过
            }

    def crawl_site(self, site: Dict[str, Any], max_articles: int = 100) -> Dict[str, Any]:
        """
        同步爬取单个站点（封装异步方法）

        如果站点超时，返回 skipped=True 标记，让调用方知道可以继续处理其他站点
        """
        url = site.get('url', '')
        name = site.get('name', '未知站点')
        # 获取该站点的超时时间，同步方法额外加30秒作为缓冲
        site_timeout = self._get_timeout_for_url(url) + 30

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.crawl_site_async(site, max_articles))
                    return future.result(timeout=site_timeout)
            else:
                return loop.run_until_complete(self.crawl_site_async(site, max_articles))
        except (FuturesTimeoutError, asyncio.TimeoutError, TimeoutError):
            print(f"[PluginCrawler] ⏱️ 同步超时跳过: {name}")
            return {
                'success': False,
                'articles': [],
                'error': f'站点超时（{site_timeout}秒），已跳过',
                'skipped': True
            }
        except RuntimeError:
            try:
                return asyncio.run(self.crawl_site_async(site, max_articles))
            except Exception as e:
                error_msg = str(e)
                is_timeout = 'timeout' in error_msg.lower()
                return {
                    'success': False,
                    'articles': [],
                    'error': f'超时跳过' if is_timeout else str(e),
                    'skipped': is_timeout
                }


# 全局爬取器实例和锁
_crawler_instance = None
_crawler_lock = threading.Lock()


def get_crawler() -> PluginCrawler:
    """获取爬取器单例（线程安全）"""
    global _crawler_instance
    if _crawler_instance is None:
        with _crawler_lock:
            # 双重检查锁定
            if _crawler_instance is None:
                _crawler_instance = PluginCrawler()
    return _crawler_instance
