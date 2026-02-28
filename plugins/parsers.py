# -*- coding: utf-8 -*-
"""
专用解析器模块
为每个站点提供定制的HTML解析逻辑
"""

import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


# ==================== 工具函数 ====================

def clean_title(title: str) -> str:
    """清理标题文本"""
    if not title:
        return ''
    # 移除多余空白
    title = ' '.join(title.split())
    # 移除常见的无意义后缀
    suffixes = [' - ', ' | ', ' – ', ' — ']
    for suffix in suffixes:
        if suffix in title:
            parts = title.rsplit(suffix, 1)
            if len(parts[0]) > 10:  # 确保剩余部分足够长
                title = parts[0]
    return title.strip()


def is_valid_article_url(url: str, domain: str) -> bool:
    """检查URL是否为有效的文章链接"""
    if not url:
        return False
    url_lower = url.lower()
    # 排除非文章链接
    exclude_patterns = [
        'javascript:', 'mailto:', '#', 'void(0)',
        '/login', '/signup', '/register', '/subscribe',
        '/contact', '/about', '/privacy', '/terms',
        '/search', '/tag/', '/category/', '/author/',
        '.pdf', '.jpg', '.png', '.gif', '.mp4', '.mp3'
    ]
    for pattern in exclude_patterns:
        if pattern in url_lower:
            return False
    return True


def extract_date_from_url(url: str) -> Optional[datetime]:
    """从URL中提取日期"""
    # 常见日期格式: /2025/01/15/, /20250115/, /2025-01-15/
    patterns = [
        r'/(\d{4})/(\d{2})/(\d{2})/',
        r'/(\d{4})(\d{2})(\d{2})/',
        r'/(\d{4})-(\d{2})-(\d{2})/',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            try:
                year, month, day = map(int, match.groups())
                return datetime(year, month, day)
            except Exception:
                pass
    return None


def create_article(url: str, title: str, site: Dict[str, Any],
                   pub_date: datetime = None, method: str = 'parser') -> Dict[str, Any]:
    """创建标准文章字典"""
    return {
        'loc': url,
        'title': clean_title(title),
        'source_name': site.get('name', ''),
        'country_code': site.get('country_code', ''),
        'coords': site.get('coords', []),
        'pub_date': pub_date or datetime.now(),
        'fetched_at': datetime.now(),
        'method': method
    }


# ==================== 港澳台媒体解析器 ====================

def parse_takungpao(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    香港大公报专用解析器
    URL格式: /news/232108/2025/0204/xxxxx.html
    """
    articles = []
    seen_urls = set()
    base_url = 'http://www.takungpao.com.hk'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 文章链接模式
        article_pattern = re.compile(r'/news/\d+/\d{4}/\d{4}/\d+\.html')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            # 补全URL
            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            pub_date = extract_date_from_url(href) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'takungpao'))

    except Exception as e:
        print(f"[大公报解析器] 错误: {e}")

    return articles


def parse_hkcna(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    香港中通社专用解析器
    URL格式: /docxxx.htm 或 /content/2025/01/15/xxxxx.shtml
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.hkcna.hk'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 查找新闻列表区域的链接
        article_patterns = [
            re.compile(r'/content/\d{4}/\d{2}/\d{2}/\d+\.shtml'),
            re.compile(r'/doc\d+\.htm')
        ]

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()

            # 检查是否匹配文章模式
            is_article = any(p.search(href) for p in article_patterns)
            if not is_article:
                continue

            if href.startswith('/'):
                href = base_url + href
            elif not href.startswith('http'):
                href = base_url + '/' + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            pub_date = extract_date_from_url(href) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'hkcna'))

    except Exception as e:
        print(f"[香港中通社解析器] 错误: {e}")

    return articles


def parse_mingpao(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    明报专用解析器
    URL格式: /pns/xxx 或 /ins/xxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://news.mingpao.com'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 明报文章URL模式
        article_pattern = re.compile(r'/(pns|ins|fin|ent|spc)/\d+/s\d+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'mingpao'))

    except Exception as e:
        print(f"[明报解析器] 错误: {e}")

    return articles


def parse_scmp(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    南华早报专用解析器
    URL格式: /news/xxx/article/xxxxx 或 /economy/xxx/article/xxxxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.scmp.com'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # SCMP文章URL模式
        article_pattern = re.compile(r'/(news|economy|business|tech|lifestyle|sport|culture|comment|yp)/[^/]+/article/\d+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            # 获取标题 - 优先从父级heading获取
            title = ''
            parent_heading = link.find_parent(['h1', 'h2', 'h3', 'h4'])
            if parent_heading:
                title = parent_heading.get_text(strip=True)
            if not title:
                title = link.get_text(strip=True)

            if len(title) < 8:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'scmp'))

    except Exception as e:
        print(f"[南华早报解析器] 错误: {e}")

    return articles


# ==================== 亚洲中文媒体解析器 ====================

def parse_nytimes_cn(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    纽约时报中文网专用解析器
    URL格式: /china/20250204/xxxxx/zh-hant/
    """
    articles = []
    seen_urls = set()
    base_url = 'https://cn.nytimes.com'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 文章链接正则 - 支持相对URL和绝对URL
        article_url_pattern = re.compile(
            r'^(https?://cn\.nytimes\.com)?/[a-z-]+/\d{8}/[^/]+/(zh-han[st]/?)?'
        )

        # 需要提取的标题选择器（热门文章优先）
        headline_selectors = [
            '.hotStoryList a',
            'h2.leadHeadline a',
            'h3.subHeadline a',
            'h3.regularSummaryHeadline a',
            'h3.headline a',
            'h3.sfheadline a',
            'h3.commentSummaryHeadline a',
            '.storyWindow h3 a',
            '.mothThumbnail + h3 a',
        ]

        def process_link(link):
            href = link.get('href', '').strip()
            if not href or not article_url_pattern.match(href):
                return None

            if href.startswith('/'):
                href = base_url + href
            href = href.split('?')[0]

            if href in seen_urls:
                return None
            seen_urls.add(href)

            title = link.get('title', '').strip() or link.get_text(strip=True)
            if not title or len(title) < 5:
                return None

            pub_date = extract_date_from_url(href) or datetime.now()
            return create_article(href, title, site, pub_date, 'nytimes')

        for selector in headline_selectors:
            for link in soup.select(selector):
                article = process_link(link)
                if article:
                    articles.append(article)

        # 补充提取
        if len(articles) < 10:
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if article_url_pattern.match(href):
                    article = process_link(link)
                    if article:
                        articles.append(article)

    except Exception as e:
        print(f"[纽约时报中文网解析器] 错误: {e}")

    return articles


def parse_zaobao(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    联合早报专用解析器
    URL格式: /realtime/xxx/story20250204-xxxxx 或 /news/xxx/story20250204-xxxxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.zaobao.com.sg'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 联合早报文章URL模式
        article_pattern = re.compile(r'/(realtime|news|forum|finance|entertainment)/[^/]+/story\d+-\d+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            pub_date = extract_date_from_url(href) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'zaobao'))

    except Exception as e:
        print(f"[联合早报解析器] 错误: {e}")

    return articles


def parse_sinchew(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    星洲日报专用解析器
    URL格式: https://{subdomain}.sinchew.com.my/news/YYYYMMDD/category/id
    子域名包括: www, sarawak, johor, metro, northern, perak 等
    标题优先从 data-title 属性提取（比 get_text 更干净）
    """
    articles = []
    seen_urls = set()

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 星洲日报文章URL模式：匹配 sinchew.com.my 域名下包含 /news/YYYYMMDD/ 的链接
        article_pattern = re.compile(r'sinchew\.com\.my/news/\d{8}/')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()

            # 必须匹配文章URL模式
            if not article_pattern.search(href):
                continue

            # 跳过广告/赞助内容
            if '/advertorial/' in href:
                continue

            # 去重
            if href in seen_urls:
                continue
            seen_urls.add(href)

            # 优先从 data-title 属性提取标题（星洲网所有文章链接都有此属性）
            title = link.get('data-title', '').strip()
            if not title:
                # 尝试从 normal-title 子元素提取
                normal_title = link.select_one('.normal-title')
                if normal_title:
                    title = normal_title.get_text(strip=True)
                else:
                    title = link.get_text(strip=True)

            if len(title) < 5:
                continue

            pub_date = extract_date_from_url(href) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'sinchew'))

    except Exception as e:
        print(f"[星洲日报解析器] 错误: {e}")

    return articles


def parse_kyodo_cn(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    共同社中文专用解析器
    """
    articles = []
    seen_urls = set()
    base_url = 'https://tchina.kyodonews.net'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 共同社文章URL模式
        article_pattern = re.compile(r'/news/\d{4}/\d{2}/\d{2}/[a-z0-9-]+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            pub_date = extract_date_from_url(href) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'kyodo_cn'))

    except Exception as e:
        print(f"[共同社中文解析器] 错误: {e}")

    return articles


def parse_nhk_cn(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    NHK中文专用解析器
    URL格式: /nhkworld/zh/news/xxxxx/
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www3.nhk.or.jp'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # NHK中文文章URL模式
        article_pattern = re.compile(r'/nhkworld/zh/news/\d+/')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'nhk_cn'))

    except Exception as e:
        print(f"[NHK中文解析器] 错误: {e}")

    return articles


def parse_cls(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    财联社专用解析器
    URL格式: /detail/xxxxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.cls.cn'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 财联社文章URL模式
        article_pattern = re.compile(r'/detail/\d+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'cls'))

    except Exception as e:
        print(f"[财联社解析器] 错误: {e}")

    return articles


def parse_sinovision(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    美国中文网专用解析器
    URL格式: /portal.php?mod=view&aid=xxxxx 或 /news/xxxxx.html
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.sinovision.net'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 文章URL模式
        article_patterns = [
            re.compile(r'/portal\.php\?mod=view&aid=\d+'),
            re.compile(r'/\w+/\d+-\d+-\d+-\d+\.html')
        ]

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()

            is_article = any(p.search(href) for p in article_patterns)
            if not is_article:
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'sinovision'))

    except Exception as e:
        print(f"[美国中文网解析器] 错误: {e}")

    return articles


def parse_haiwaiwang(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    海外家园网专用解析器
    注意：此解析器用于解析单篇文章页面获取标题
    sitemap 爬取逻辑在 crawl_haiwaiwang_sitemap 函数中
    """
    articles = []
    base_url = 'https://haiwaiwang.org'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 从文章页面提取标题
        title = ''

        # 优先从 og:title 获取
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()

        # 从 title 标签获取
        if not title:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
                # 移除网站名称后缀
                if ' - ' in title:
                    title = title.rsplit(' - ', 1)[0].strip()
                if ' | ' in title:
                    title = title.rsplit(' | ', 1)[0].strip()

        # 从 h1 获取
        if not title:
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)

        # 从 entry-title 类获取
        if not title:
            entry_title = soup.find(class_='entry-title')
            if entry_title:
                title = entry_title.get_text(strip=True)

        if title and len(title) >= 5:
            # 获取当前页面URL
            url = site.get('url', '') or site.get('current_url', '')
            articles.append(create_article(url, title, site, datetime.now(), 'haiwaiwang'))

    except Exception as e:
        print(f"[海外家园网解析器] 错误: {e}")

    return articles


def parse_haiwaiwang_sitemap(xml_content: str) -> List[Dict[str, str]]:
    """
    解析海外家园网的 sitemap XML
    返回文章URL和最后修改时间列表
    """
    import xml.etree.ElementTree as ET

    articles = []

    try:
        root = ET.fromstring(xml_content)

        # XML 命名空间
        namespaces = {
            'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'
        }

        for url_elem in root.findall('.//sm:url', namespaces):
            loc = url_elem.find('sm:loc', namespaces)
            lastmod = url_elem.find('sm:lastmod', namespaces)

            if loc is not None and loc.text:
                url = loc.text.strip()
                # 只保留文章URL（数字ID格式）
                if re.match(r'https://haiwaiwang\.org/\d+/?$', url):
                    mod_time = lastmod.text.strip() if lastmod is not None and lastmod.text else ''
                    articles.append({
                        'url': url,
                        'lastmod': mod_time
                    })

    except ET.ParseError as e:
        print(f"[海外家园网Sitemap] XML解析错误: {e}")
    except Exception as e:
        print(f"[海外家园网Sitemap] 错误: {e}")

    return articles


def parse_inform_kz(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    哈萨克斯坦国际通讯社专用解析器
    URL格式: /cn/article/xxxxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://cn.inform.kz'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 文章URL模式
        article_pattern = re.compile(r'/article/\d+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'inform_kz'))

    except Exception as e:
        print(f"[哈萨克斯坦通讯社解析器] 错误: {e}")

    return articles


def parse_udn_seoul(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    联合新闻网首尔经济专题解析器
    """
    articles = []
    seen_urls = set()
    base_url = 'https://money.udn.com'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 联合新闻网文章URL模式
        article_pattern = re.compile(r'/money/story/\d+/\d+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'udn_seoul'))

    except Exception as e:
        print(f"[联合新闻网解析器] 错误: {e}")

    return articles


# ==================== 国际主流媒体解析器 ====================

def parse_apnews(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    美联社（AP News）专用解析器
    URL格式: /article/{slug}
    """
    articles = []
    seen_urls = set()
    base_url = 'https://apnews.com'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        article_url_pattern = re.compile(r'^(https://apnews\.com)?/article/[a-z0-9-]+')

        def process_link(link, priority=0):
            href = link.get('href', '').strip()
            if not href or not article_url_pattern.match(href):
                return None

            if href.startswith('/'):
                href = base_url + href
            href = href.split('?')[0]

            if href in seen_urls:
                return None
            seen_urls.add(href)

            title = ''
            parent_heading = link.find_parent(['h3', 'h2', 'h1'])
            if parent_heading:
                title = parent_heading.get_text(strip=True)
            if not title:
                title = link.get_text(strip=True)

            if not title or len(title) < 10:
                return None
            if len(title) > 300:
                title = title[:300] + '...'

            article = create_article(href, title, site, datetime.now(), 'apnews')
            article['priority'] = priority
            return article

        # 优先提取标题中的文章链接
        for link in soup.select('h3 a[href*="/article/"]'):
            article = process_link(link, priority=1)
            if article:
                articles.append(article)

        for link in soup.select('h2 a[href*="/article/"]'):
            article = process_link(link, priority=2)
            if article:
                articles.append(article)

        for link in soup.select('.PagePromo-content a[href*="/article/"]'):
            article = process_link(link, priority=3)
            if article:
                articles.append(article)

        for link in soup.find_all('a', href=article_url_pattern):
            article = process_link(link, priority=10)
            if article:
                articles.append(article)

        articles.sort(key=lambda x: x.get('priority', 10))
        for art in articles:
            art.pop('priority', None)

    except Exception as e:
        print(f"[AP News解析器] 错误: {e}")

    return articles


def parse_bbc(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    BBC News专用解析器
    URL格式: /news/xxx-xxxxx 或 /news/articles/xxxxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.bbc.com'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # BBC文章URL模式
        article_patterns = [
            re.compile(r'/news/[a-z-]+-\d+'),
            re.compile(r'/news/articles/[a-z0-9]+'),
            re.compile(r'/sport/[a-z-]+/\d+'),
        ]

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()

            is_article = any(p.search(href) for p in article_patterns)
            if not is_article:
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            # 获取标题
            title = ''
            parent_heading = link.find_parent(['h3', 'h2', 'h1'])
            if parent_heading:
                title = parent_heading.get_text(strip=True)
            if not title:
                title = link.get_text(strip=True)

            if len(title) < 8:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'bbc'))

    except Exception as e:
        print(f"[BBC解析器] 错误: {e}")

    return articles


def parse_foxnews(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    福克斯新闻专用解析器
    URL格式: /politics/xxx, /us/xxx, /world/xxx 等
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.foxnews.com'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 福克斯新闻文章URL模式
        article_pattern = re.compile(r'/(politics|us|world|opinion|media|entertainment|sports|lifestyle|science|tech)/[a-z0-9-]+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 8:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'foxnews'))

    except Exception as e:
        print(f"[福克斯新闻解析器] 错误: {e}")

    return articles


def parse_thetimes(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    泰晤士报专用解析器
    URL格式: /article/xxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.thetimes.com'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 泰晤士报文章URL模式
        article_pattern = re.compile(r'/article/[a-z0-9-]+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = ''
            parent_heading = link.find_parent(['h3', 'h2', 'h1'])
            if parent_heading:
                title = parent_heading.get_text(strip=True)
            if not title:
                title = link.get_text(strip=True)

            if len(title) < 8:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'thetimes'))

    except Exception as e:
        print(f"[泰晤士报解析器] 错误: {e}")

    return articles


def parse_rfi(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    法国国际广播电台中文版专用解析器
    URL格式: /cn/xxx/xxxxxxxx-xxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.rfi.fr'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # RFI文章URL模式
        article_pattern = re.compile(r'/cn/[^/]+/\d{8}-[a-z0-9-]+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            pub_date = extract_date_from_url(href) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'rfi'))

    except Exception as e:
        print(f"[RFI解析器] 错误: {e}")

    return articles


def parse_lb_ua(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    乌克兰LB新闻专用解析器
    URL格式: /news/2025/01/15/xxxxx.html
    """
    articles = []
    seen_urls = set()
    base_url = 'https://lb.ua'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # LB.UA文章URL模式
        article_pattern = re.compile(r'/news/\d{4}/\d{2}/\d{2}/\d+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            pub_date = extract_date_from_url(href) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'lb_ua'))

    except Exception as e:
        print(f"[乌克兰LB解析器] 错误: {e}")

    return articles


def parse_infobae(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Infobae专用解析器
    URL格式: /america/xxx/2025/01/15/xxxxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.infobae.com'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Infobae文章URL模式
        article_pattern = re.compile(r'/(america|mexico|colombia|peru|argentina)/[^/]+/\d{4}/\d{2}/\d{2}/[a-z0-9-]+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 8:
                continue

            pub_date = extract_date_from_url(href) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'infobae'))

    except Exception as e:
        print(f"[Infobae解析器] 错误: {e}")

    return articles


# ==================== 政府网站解析器 ====================

def parse_us_state(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    美国国务院专用解析器
    URL格式: /press-release/xxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.state.gov'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 美国国务院文章URL模式
        article_patterns = [
            re.compile(r'/(press-release|briefing|remarks|speeches)/[a-z0-9-]+'),
        ]

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()

            is_article = any(p.search(href) for p in article_patterns)
            if not is_article:
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 10:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'us_state'))

    except Exception as e:
        print(f"[美国国务院解析器] 错误: {e}")

    return articles


def parse_uscis(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    美国移民局专用解析器
    URL格式: /news/news-releases/xxx 或 /news/alerts/xxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.uscis.gov'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # USCIS文章URL模式
        article_pattern = re.compile(r'/news/(news-releases|alerts)/[a-z0-9-]+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 10:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'uscis'))

    except Exception as e:
        print(f"[USCIS解析器] 错误: {e}")

    return articles


def parse_au_homeaffairs(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    澳大利亚移民局专用解析器
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.homeaffairs.gov.au'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 澳大利亚内政部文章URL模式
        article_pattern = re.compile(r'/news-media/archive/[a-z0-9-]+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 10:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'au_homeaffairs'))

    except Exception as e:
        print(f"[澳大利亚移民局解析器] 错误: {e}")

    return articles


def parse_kr_immigration(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    韩国移民局专用解析器
    """
    articles = []
    seen_urls = set()
    base_url = 'http://www.immigration.go.kr'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 韩国移民局文章URL模式 - 通常使用动态参数
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()

            # 查找包含subview或view的链接
            if 'subview' not in href and 'view' not in href:
                continue

            if href.startswith('/'):
                href = base_url + href
            elif not href.startswith('http'):
                href = base_url + '/' + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'kr_immigration'))

    except Exception as e:
        print(f"[韩国移民局解析器] 错误: {e}")

    return articles


def parse_nl_ind(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    荷兰移民局专用解析器
    URL格式: /nl/nieuws/xxx
    """
    articles = []
    seen_urls = set()
    base_url = 'https://ind.nl'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 荷兰IND文章URL模式
        article_pattern = re.compile(r'/nl/nieuws/[a-z0-9-]+')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            articles.append(create_article(href, title, site, datetime.now(), 'nl_ind'))

    except Exception as e:
        print(f"[荷兰移民局解析器] 错误: {e}")

    return articles


# ==================== 解析器注册表 ====================

SPECIAL_PARSERS = {
    # 港澳台媒体
    'takungpao': parse_takungpao,
    'hkcna': parse_hkcna,
    'mingpao': parse_mingpao,
    'scmp': parse_scmp,

    # 亚洲中文媒体
    'nytimes': parse_nytimes_cn,
    'zaobao': parse_zaobao,
    'sinchew': parse_sinchew,
    'kyodo_cn': parse_kyodo_cn,
    'nhk_cn': parse_nhk_cn,
    'cls': parse_cls,
    'sinovision': parse_sinovision,
    'haiwaiwang': parse_haiwaiwang,
    'inform_kz': parse_inform_kz,
    'udn_seoul': parse_udn_seoul,

    # 国际主流媒体
    'apnews': parse_apnews,
    'bbc': parse_bbc,
    'foxnews': parse_foxnews,
    'thetimes': parse_thetimes,
    'rfi': parse_rfi,
    'lb_ua': parse_lb_ua,
    'infobae': parse_infobae,

    # 政府网站
    'us_state': parse_us_state,
    'uscis': parse_uscis,
    'au_homeaffairs': parse_au_homeaffairs,
    'kr_immigration': parse_kr_immigration,
    'nl_ind': parse_nl_ind,
}


def get_parser(parser_name: str):
    """获取指定名称的解析器"""
    return SPECIAL_PARSERS.get(parser_name)


def list_parsers() -> List[str]:
    """列出所有可用的解析器"""
    return list(SPECIAL_PARSERS.keys())
