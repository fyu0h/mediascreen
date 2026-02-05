# -*- coding: utf-8 -*-
"""
插件通用爬取模块
使用 crawl4ai 进行网页抓取，调用专用解析器提取文章
"""

import asyncio
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
    print("[警告] crawl4ai 未安装，爬取功能将不可用")


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

    def __init__(self):
        if not CRAWL4AI_AVAILABLE:
            raise ImportError("crawl4ai 未安装，请运行: pip install crawl4ai")
        self.browser_config = BrowserConfig(headless=True, verbose=False)

    def _get_timeout_for_url(self, url: str) -> int:
        """根据URL获取对应的超时时间（秒）"""
        try:
            domain = urlparse(url).netloc.lower()
            # 检查是否有站点特定配置
            for site_domain, timeout in self.SITE_TIMEOUTS.items():
                if site_domain in domain:
                    return timeout
        except:
            pass
        return self.DEFAULT_TIMEOUT

    async def fetch_page(self, url: str, timeout: int = None) -> str:
        """
        异步获取页面内容（模拟正常浏览器）

        Args:
            url: 要抓取的URL
            timeout: 超时时间（秒），None则使用默认配置

        Returns:
            页面HTML内容，失败或超时返回空字符串
        """
        if timeout is None:
            timeout = self._get_timeout_for_url(url)

        timeout_ms = timeout * 1000

        try:
            config = CrawlerRunConfig(
                wait_until="domcontentloaded",
                page_timeout=timeout_ms,
                cache_mode=CacheMode.BYPASS
            )
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(url, config=config)
                if result.success:
                    return result.html
                print(f"[PluginCrawler] 页面抓取未成功 {url}")
                return ""
        except asyncio.TimeoutError:
            print(f"[PluginCrawler] ⏱️ 超时跳过 ({timeout}秒): {url}")
            return ""
        except Exception as e:
            error_msg = str(e)
            # 检查是否是Playwright超时错误
            if 'Timeout' in error_msg or 'timeout' in error_msg.lower():
                print(f"[PluginCrawler] ⏱️ 超时跳过 ({timeout}秒): {url}")
            else:
                print(f"[PluginCrawler] 获取页面失败 {url}: {e}")
            return ""

    def fetch_url_simple(self, url: str, timeout: int = 30) -> str:
        """简单HTTP请求获取页面（用于sitemap等不需要渲染的页面）"""
        try:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            if response.status_code == 200:
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
                except:
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

    async def crawl_haiwaiwang_sitemap(self, site: Dict[str, Any], max_articles: int = 50) -> Dict[str, Any]:
        """
        海外家园网专用 sitemap 爬取
        1. 获取 sitemap1.xml
        2. 筛选最近2天的文章
        3. 遍历每个URL获取标题
        """
        from plugins.parsers import parse_haiwaiwang_sitemap, parse_haiwaiwang

        sitemap_url = 'https://haiwaiwang.org/post-sitemap1.xml'
        articles = []

        try:
            # 1. 获取 sitemap
            print(f"[海外家园网] 获取 sitemap: {sitemap_url}")
            sitemap_content = self.fetch_url_simple(sitemap_url)

            if not sitemap_content:
                return {'success': False, 'articles': [], 'error': '无法获取sitemap'}

            # 2. 解析 sitemap
            sitemap_items = parse_haiwaiwang_sitemap(sitemap_content)
            print(f"[海外家园网] sitemap 包含 {len(sitemap_items)} 个URL")

            if not sitemap_items:
                return {'success': False, 'articles': [], 'error': 'sitemap为空或解析失败'}

            # 3. 筛选最近2天的文章
            now = datetime.now()
            two_days_ago = now - timedelta(days=2)
            recent_items = []

            for item in sitemap_items:
                lastmod = item.get('lastmod', '')
                if lastmod:
                    try:
                        # 解析时间格式: 2026-02-04 06:40 +00:00
                        mod_time = datetime.fromisoformat(lastmod.replace(' +00:00', '+00:00').replace(' ', 'T'))
                        mod_time = mod_time.replace(tzinfo=None)  # 移除时区
                        if mod_time >= two_days_ago:
                            recent_items.append(item)
                    except:
                        # 解析失败则包含
                        recent_items.append(item)
                else:
                    recent_items.append(item)

            # 限制数量
            recent_items = recent_items[:max_articles]
            print(f"[海外家园网] 筛选出 {len(recent_items)} 篇最近文章")

            # 4. 遍历获取标题
            for item in recent_items:
                url = item['url']
                try:
                    # 获取文章页面
                    html = await self.fetch_page(url)
                    if not html:
                        continue

                    # 解析标题
                    site_config = {
                        'name': site.get('name', '海外家园网'),
                        'url': url,
                        'current_url': url,
                        'country_code': site.get('country_code', 'US'),
                        'coords': site.get('coords', [-77.0369, 38.9072])
                    }
                    article_list = parse_haiwaiwang(html, site_config)

                    if article_list:
                        article = article_list[0]
                        article['loc'] = url
                        # 解析 lastmod 作为发布日期
                        if item.get('lastmod'):
                            try:
                                pub_date = datetime.fromisoformat(
                                    item['lastmod'].replace(' +00:00', '+00:00').replace(' ', 'T')
                                ).replace(tzinfo=None)
                                article['pub_date'] = pub_date
                            except:
                                pass
                        articles.append(article)
                        print(f"[海外家园网] 获取到: {article['title'][:30]}...")

                except Exception as e:
                    print(f"[海外家园网] 获取文章失败 {url}: {e}")
                    continue

            return {
                'success': True,
                'articles': articles,
                'error': None
            }

        except Exception as e:
            return {'success': False, 'articles': [], 'error': str(e)}

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

        # 海外家园网使用专用 sitemap 爬取
        if parser_name == 'haiwaiwang':
            return await self.crawl_haiwaiwang_sitemap(site, max_articles)

        try:
            # 获取页面
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


# 全局爬取器实例
_crawler_instance = None


def get_crawler() -> PluginCrawler:
    """获取爬取器单例"""
    global _crawler_instance
    if _crawler_instance is None:
        _crawler_instance = PluginCrawler()
    return _crawler_instance
