# -*- coding: utf-8 -*-
"""
定时任务调度器
负责定期从RSS等源更新文章
"""

import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
import re

import requests

# 导入数据库操作
from models.mongo import save_articles, article_exists


class RSSScheduler:
    """
    通用RSS定时更新调度器
    支持多个站点的RSS定时更新
    """

    def __init__(self, interval: int = 300, startup_delay: int = 60):
        """
        初始化调度器

        Args:
            interval: 更新间隔（秒），默认300秒（5分钟）
            startup_delay: 启动延迟（秒），默认60秒，等待系统启动完成
        """
        self.interval = interval
        self.startup_delay = startup_delay
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_update: Optional[datetime] = None
        self.stats = {
            'total_fetched': 0,
            'total_saved': 0,
            'last_error': None,
            'sites': {}
        }

        # RSS源配置
        self.rss_sources = [
            {
                'id': 'apnews',
                'name': 'AP News',
                'country_code': 'US',
                'coords': [-77.0369, 38.9072],
                'rss_urls': [
                    'https://apnews.com/index.rss',
                ],
                'use_homepage': True,  # 也从主页抓取
                'homepage_url': 'https://apnews.com',
                'parser': 'apnews'
            },
            {
                'id': 'reuters',
                'name': '路透社',
                'country_code': 'GB',
                'coords': [-0.1276, 51.5074],
                'rss_urls': [
                    'https://news.google.com/rss/search?q=site%3Areuters.com&hl=en-US&gl=US&ceid=US%3Aen',
                ],
                'use_homepage': False,
                'google_news_rss': True,  # 使用Google News RSS
            },
            {
                'id': 'hkfp',
                'name': '香港自由新闻 (HKFP)',
                'country_code': 'HK',
                'coords': [114.1694, 22.3193],
                'rss_urls': [
                    'https://hongkongfp.com/feed/',
                ],
                'use_homepage': False,
            },
            {
                'id': 'cdt',
                'name': '中国数字时代 (CDT)',
                'country_code': 'US',
                'coords': [-122.2585, 37.8719],
                'rss_urls': [
                    'https://chinadigitaltimes.net/feed/',
                ],
                'use_homepage': False,
            },
            {
                'id': 'diplomat',
                'name': '外交官杂志 (The Diplomat)',
                'country_code': 'US',
                'coords': [-77.0369, 38.9072],
                'rss_urls': [
                    'https://thediplomat.com/feed/',
                ],
                'use_homepage': False,
            },
            {
                'id': 'haiwaiwang',
                'name': '海外家园网',
                'country_code': 'US',
                'coords': [-77.0369, 38.9072],
                'rss_urls': [
                    'https://haiwaiwang.org/feed/',
                ],
                'use_homepage': False,
            },
        ]

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*'
        }

    def start(self):
        """启动定时任务"""
        if self.running:
            print("[RSSScheduler] 调度器已在运行中")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print(f"[RSSScheduler] 调度器已启动，{self.startup_delay}秒后执行首次更新，之后每{self.interval}秒更新一次")

    def stop(self):
        """停止定时任务"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("[RSSScheduler] 调度器已停止")

    def _run_loop(self):
        """后台运行循环"""
        # 启动延迟，等待系统完全启动
        print(f"[RSSScheduler] 等待 {self.startup_delay} 秒后开始首次更新...")
        for _ in range(self.startup_delay):
            if not self.running:
                return
            time.sleep(1)

        while self.running:
            try:
                self._update_all()
            except Exception as e:
                self.stats['last_error'] = str(e)
                print(f"[RSSScheduler] 更新出错: {e}")

            # 等待下一次更新
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)

    def _update_all(self):
        """更新所有RSS源"""
        print(f"[RSSScheduler] 开始更新 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        for source in self.rss_sources:
            try:
                self._update_source(source)
            except Exception as e:
                print(f"[RSSScheduler] {source['name']} 更新失败: {e}")

        self.last_update = datetime.now()

    def _update_source(self, source: Dict[str, Any]):
        """更新单个RSS源"""
        source_id = source['id']
        source_name = source['name']
        articles = []
        seen_urls = set()

        # 从RSS获取
        for rss_url in source.get('rss_urls', []):
            try:
                rss_articles = self._fetch_rss(rss_url, source, seen_urls)
                articles.extend(rss_articles)
                print(f"[RSSScheduler] {source_name} RSS获取到 {len(rss_articles)} 篇")
            except Exception as e:
                print(f"[RSSScheduler] {source_name} RSS获取失败: {e}")

        # 从主页获取（如果配置了）
        if source.get('use_homepage') and source.get('homepage_url'):
            try:
                homepage_articles = self._fetch_homepage(source, seen_urls)
                articles.extend(homepage_articles)
                print(f"[RSSScheduler] {source_name} 主页获取到 {len(homepage_articles)} 篇")
            except Exception as e:
                print(f"[RSSScheduler] {source_name} 主页获取失败: {e}")

        if not articles:
            print(f"[RSSScheduler] {source_name} 未获取到文章")
            return

        # 统计
        self.stats['total_fetched'] += len(articles)

        # 过滤已存在的文章
        new_articles = [art for art in articles if not article_exists(art['loc'])]

        if new_articles:
            saved = save_articles(new_articles)
            self.stats['total_saved'] += saved
            self.stats['sites'][source_id] = {
                'last_update': datetime.now().isoformat(),
                'fetched': len(articles),
                'saved': saved
            }
            print(f"[RSSScheduler] {source_name} 保存了 {saved} 篇新文章")
        else:
            print(f"[RSSScheduler] {source_name} 没有新文章")

    def _fetch_rss(self, rss_url: str, source: Dict[str, Any], seen_urls: set) -> List[Dict[str, Any]]:
        """从RSS获取文章"""
        articles = []

        response = requests.get(rss_url, headers=self.headers, timeout=30)
        if response.status_code != 200:
            return articles

        content = response.text
        if not content.strip().startswith('<?xml'):
            return articles

        # 判断是否为Google News RSS
        is_google_news = source.get('google_news_rss', False) or 'news.google.com' in rss_url

        try:
            root = ET.fromstring(content)

            for item in root.findall('.//item'):
                title_el = item.find('title')
                link_el = item.find('link')
                pub_date_el = item.find('pubDate')
                source_el = item.find('source')

                if title_el is None or link_el is None:
                    continue

                title = title_el.text.strip() if title_el.text else ''
                link = link_el.text.strip() if link_el.text else ''

                if not title or not link:
                    continue

                # Google News RSS的标题格式: "标题 - 来源"，需要清理
                if is_google_news and ' - ' in title:
                    title = title.rsplit(' - ', 1)[0].strip()

                # Google News的链接是跳转链接，尝试提取原始链接
                # 但通常我们直接使用Google News链接也可以
                original_link = link

                # 去重
                if original_link in seen_urls:
                    continue
                seen_urls.add(original_link)

                # 解析发布日期
                pub_date = datetime.now()
                if pub_date_el is not None and pub_date_el.text:
                    try:
                        from email.utils import parsedate_to_datetime
                        pub_date = parsedate_to_datetime(pub_date_el.text)
                    except Exception:
                        pass

                articles.append({
                    'loc': original_link,
                    'title': title,
                    'source_name': source['name'],
                    'country_code': source['country_code'],
                    'coords': source['coords'],
                    'pub_date': pub_date,
                    'fetched_at': datetime.now(),
                    'method': 'google_news_rss' if is_google_news else 'rss'
                })

        except ET.ParseError as e:
            print(f"[RSSScheduler] RSS解析错误: {e}")

        return articles

    def _fetch_homepage(self, source: Dict[str, Any], seen_urls: set) -> List[Dict[str, Any]]:
        """从主页抓取文章"""
        articles = []
        parser_name = source.get('parser')

        if not parser_name:
            return articles

        try:
            from plugins.crawler import get_crawler
            from plugins.parsers import get_parser

            parser = get_parser(parser_name)
            if not parser:
                return articles

            crawler = get_crawler()

            # 使用crawl4ai抓取主页
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, crawler.fetch_page(source['homepage_url']))
                        html = future.result(timeout=120)
                else:
                    html = loop.run_until_complete(crawler.fetch_page(source['homepage_url']))
            except RuntimeError:
                html = asyncio.run(crawler.fetch_page(source['homepage_url']))

            if html:
                site_config = {
                    'name': source['name'],
                    'url': source['homepage_url'],
                    'country_code': source['country_code'],
                    'coords': source['coords']
                }
                all_articles = parser(html, site_config)

                # 过滤已见过的URL
                for art in all_articles:
                    if art['loc'] not in seen_urls:
                        seen_urls.add(art['loc'])
                        articles.append(art)

        except Exception as e:
            print(f"[RSSScheduler] 主页抓取失败: {e}")

        return articles

    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        return {
            'running': self.running,
            'interval': self.interval,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'stats': self.stats,
            'sources': [{'id': s['id'], 'name': s['name']} for s in self.rss_sources]
        }

    def trigger_update(self):
        """手动触发一次更新"""
        threading.Thread(target=self._update_all, daemon=True).start()

    def add_source(self, source: Dict[str, Any]):
        """添加新的RSS源"""
        self.rss_sources.append(source)


# 全局调度器实例
_scheduler_instance: Optional[RSSScheduler] = None


def get_rss_scheduler() -> RSSScheduler:
    """获取RSS调度器单例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = RSSScheduler(interval=300)  # 5分钟
    return _scheduler_instance


# 兼容旧接口
def get_apnews_scheduler() -> RSSScheduler:
    """获取调度器（兼容旧接口）"""
    return get_rss_scheduler()


def start_all_schedulers():
    """启动所有定时调度器"""
    scheduler = get_rss_scheduler()
    scheduler.start()


def stop_all_schedulers():
    """停止所有定时调度器"""
    global _scheduler_instance
    if _scheduler_instance:
        _scheduler_instance.stop()
