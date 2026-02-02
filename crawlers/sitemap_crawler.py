# -*- coding: utf-8 -*-
"""
Sitemap 爬虫模块
从网站的 sitemap.xml 获取文章列表
"""

import requests
import xml.etree.ElementTree as ET
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re

from models.logger import log_request, log_operation


class SitemapCrawler:
    """Sitemap 爬虫"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        # XML 命名空间
        self.namespaces = {
            'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
            'news': 'http://www.google.com/schemas/sitemap-news/0.9',
            'image': 'http://www.google.com/schemas/sitemap-image/1.1',
            'video': 'http://www.google.com/schemas/sitemap-video/1.1'
        }

    def fetch_sitemap(self, url: str) -> Optional[str]:
        """获取 sitemap 内容"""
        start_time = time.time()
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            duration_ms = (time.time() - start_time) * 1000

            log_request(
                action='获取 Sitemap',
                url=url,
                method='GET',
                request_headers=self.headers,
                response_status=response.status_code,
                response_headers=dict(response.headers),
                response_body=response.text[:5000] if response.text else None,
                duration_ms=duration_ms,
                status='success' if response.status_code == 200 else 'warning'
            )

            if response.status_code == 200:
                return response.text
            return None
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_request(
                action='获取 Sitemap',
                url=url,
                method='GET',
                request_headers=self.headers,
                duration_ms=duration_ms,
                status='error',
                error=str(e)
            )
            print(f"获取 sitemap 失败: {url}, 错误: {e}")
            return None

    def parse_sitemap_index(self, content: str) -> List[str]:
        """解析 sitemap index，返回子 sitemap URL 列表"""
        sitemap_urls = []
        try:
            root = ET.fromstring(content)
            # 查找 sitemapindex
            for sitemap in root.findall('.//sm:sitemap', self.namespaces):
                loc = sitemap.find('sm:loc', self.namespaces)
                if loc is not None and loc.text:
                    sitemap_urls.append(loc.text.strip())

            # 如果没有命名空间的情况
            if not sitemap_urls:
                for sitemap in root.findall('.//sitemap'):
                    loc = sitemap.find('loc')
                    if loc is not None and loc.text:
                        sitemap_urls.append(loc.text.strip())
        except ET.ParseError as e:
            print(f"解析 sitemap index 失败: {e}")
        return sitemap_urls

    def parse_urlset(self, content: str, source_name: str = '', country_code: str = '',
                     coords: List[float] = None) -> List[Dict[str, Any]]:
        """解析 urlset，返回文章列表"""
        articles = []
        try:
            root = ET.fromstring(content)

            # 尝试带命名空间解析
            urls = root.findall('.//sm:url', self.namespaces)
            if not urls:
                # 尝试不带命名空间
                urls = root.findall('.//url')

            for url_elem in urls:
                article = self._parse_url_element(url_elem, source_name, country_code, coords)
                if article:
                    articles.append(article)

        except ET.ParseError as e:
            print(f"解析 urlset 失败: {e}")

        return articles

    def _parse_url_element(self, url_elem, source_name: str, country_code: str,
                          coords: List[float]) -> Optional[Dict[str, Any]]:
        """解析单个 URL 元素"""
        # 获取 loc
        loc = url_elem.find('sm:loc', self.namespaces)
        if loc is None:
            loc = url_elem.find('loc')
        if loc is None or not loc.text:
            return None

        url = loc.text.strip()

        # 获取 lastmod
        lastmod = url_elem.find('sm:lastmod', self.namespaces)
        if lastmod is None:
            lastmod = url_elem.find('lastmod')
        lastmod_str = lastmod.text.strip() if lastmod is not None and lastmod.text else None

        # 解析日期
        pub_date = None
        if lastmod_str:
            pub_date = self._parse_date(lastmod_str)

        # 尝试获取新闻标题（news sitemap）
        title = None
        news_elem = url_elem.find('.//news:news', self.namespaces)
        if news_elem is not None:
            title_elem = news_elem.find('news:title', self.namespaces)
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()

            # 尝试获取发布日期
            pub_date_elem = news_elem.find('news:publication_date', self.namespaces)
            if pub_date_elem is not None and pub_date_elem.text:
                pub_date = self._parse_date(pub_date_elem.text.strip())

        # 如果没有标题，从 URL 提取
        if not title:
            title = self._extract_title_from_url(url)

        return {
            'loc': url,
            'title': title,
            'source_name': source_name,
            'country_code': country_code,
            'coords': coords,
            'pub_date': pub_date,
            'lastmod': lastmod_str,
            'fetched_at': datetime.now()
        }

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        formats = [
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%Y/%m/%d',
        ]

        # 处理时区格式
        date_str = re.sub(r'(\d{2}):(\d{2})$', r'\1\2', date_str)

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def _extract_title_from_url(self, url: str) -> str:
        """从 URL 提取标题"""
        parsed = urlparse(url)
        path = parsed.path

        # 获取最后一段路径
        parts = [p for p in path.split('/') if p]
        if not parts:
            return url

        last_part = parts[-1]

        # 移除文件扩展名
        last_part = re.sub(r'\.(html?|php|aspx?|jsp)$', '', last_part, flags=re.IGNORECASE)

        # 替换分隔符为空格
        title = re.sub(r'[-_]+', ' ', last_part)

        # URL 解码
        try:
            from urllib.parse import unquote
            title = unquote(title)
        except:
            pass

        return title if title else url

    def crawl(self, site: Dict[str, Any], max_articles: int = 500) -> Dict[str, Any]:
        """
        爬取站点的 sitemap
        参数：
            site: 站点信息 {name, url, sitemap_url, country_code, coords}
            max_articles: 最大文章数
        返回：
            {success: bool, articles: [...], error: str}
        """
        sitemap_url = site.get('sitemap_url')
        if not sitemap_url:
            return {'success': False, 'articles': [], 'error': '未配置 sitemap URL'}

        source_name = site.get('name', '')
        country_code = site.get('country_code', '')
        coords = site.get('coords', [])

        log_operation(
            action=f'Sitemap爬取站点: {source_name}',
            details={'url': sitemap_url, 'method': 'sitemap', 'max_articles': max_articles},
            status='info'
        )

        articles = []

        # 获取 sitemap
        content = self.fetch_sitemap(sitemap_url)
        if not content:
            log_operation(
                action=f'Sitemap爬取失败: {source_name}',
                details={'url': sitemap_url, 'error': '无法获取 sitemap'},
                status='error'
            )
            return {'success': False, 'articles': [], 'error': f'无法获取 sitemap: {sitemap_url}'}

        # 判断是 sitemap index 还是 urlset
        if '<sitemapindex' in content:
            # 是 sitemap index，获取子 sitemap
            sub_sitemaps = self.parse_sitemap_index(content)

            # 优先处理 news sitemap
            news_sitemaps = [s for s in sub_sitemaps if 'news' in s.lower()]
            other_sitemaps = [s for s in sub_sitemaps if 'news' not in s.lower()]

            for sub_url in (news_sitemaps + other_sitemaps)[:5]:  # 最多处理5个子sitemap
                sub_content = self.fetch_sitemap(sub_url)
                if sub_content:
                    sub_articles = self.parse_urlset(sub_content, source_name, country_code, coords)
                    articles.extend(sub_articles)

                    if len(articles) >= max_articles:
                        break
        else:
            # 直接是 urlset
            articles = self.parse_urlset(content, source_name, country_code, coords)

        # 限制数量
        articles = articles[:max_articles]

        log_operation(
            action=f'Sitemap爬取完成: {source_name}',
            details={'url': sitemap_url, 'articles_count': len(articles)},
            status='success'
        )

        return {
            'success': True,
            'articles': articles,
            'count': len(articles),
            'error': None
        }
