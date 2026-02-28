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
    香港大公报（大公文匯網）专用解析器
    数据源: https://www.tkww.hk/top_news
    URL格式: /a/YYYYMM/DD/AP{hash}.html
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.tkww.hk'
    article_pattern = re.compile(r'/a/\d{6}/\d{2}/AP[0-9a-fA-F]+\.html')

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 1) 列表区文章：<a class="common-column-list-unit-title-1">
        for link in soup.find_all('a', class_=re.compile(r'common-column-list-unit-title-1')):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get('title', '').strip() or link.get_text(strip=True)
            if len(title) < 5:
                continue

            # 尝试从相邻时间元素提取日期
            pub_date = _parse_tkww_date_from_context(link) or _parse_tkww_date_from_url(href) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'takungpao'))

        # 2) 焦点头条区：<a class="img-box-shadow" title="...">
        for link in soup.find_all('a', class_='img-box-shadow'):
            href = link.get('href', '').strip()
            title = link.get('title', '').strip()
            if not href or not title or len(title) < 5:
                continue
            if not article_pattern.search(href):
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)

            pub_date = _parse_tkww_date_from_url(href) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'takungpao'))

    except Exception as e:
        print(f"[大公报解析器] 错误: {e}")

    return articles


def _parse_tkww_date_from_context(element) -> Optional[datetime]:
    """从文章列表项的相邻时间元素提取日期，格式：2026.02.28 22:16"""
    try:
        parent = element.find_parent('div', class_='common-column-list-unit-1')
        if not parent:
            parent = element.find_parent('div', class_=re.compile(r'common-column-list-unit'))
        if parent:
            time_span = parent.find('span', class_='common-column-list-unit-bottom-time1-1')
            if time_span:
                return datetime.strptime(time_span.get_text(strip=True), '%Y.%m.%d %H:%M')
    except Exception:
        pass
    return None


def _parse_tkww_date_from_url(url: str) -> Optional[datetime]:
    """从 tkww URL 提取日期，格式：/a/YYYYMM/DD/..."""
    try:
        m = re.search(r'/a/(\d{4})(\d{2})/(\d{2})/', url)
        if m:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except Exception:
        pass
    return None


def parse_hkcna(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    香港新闻网专用解析器
    基于语义化HTML精准定位文章，覆盖轮播图、头条、实时新闻、分类栏目等区域
    URL格式: docDetail.jsp?id={数字}&channel={数字}
    """
    articles = []
    seen_urls = set()
    base_url = 'http://hkcna.hk'

    # 文章URL正则：匹配 docDetail.jsp?id=xxx&channel=xxx（兼容 &amp; 编码）
    article_pattern = re.compile(r'docDetail\.jsp\?id=(\d+)(?:&amp;|&)channel=(\d+)')

    def _add_article(href: str, title: str, date_str: str = None) -> bool:
        """处理单个链接，成功添加返回True"""
        if not article_pattern.search(href):
            return False

        # URL补全和规范化：统一 &amp; 为 &
        href = href.replace('&amp;', '&')
        if not href.startswith('http'):
            href = urljoin(base_url, href)

        if href in seen_urls:
            return False
        seen_urls.add(href)

        # 清理标题：移除实时新闻末尾的时间（如 "　　22:11"）
        title = re.sub(r'[\s\u3000]+\d{1,2}:\d{2}\s*$', '', title).strip()
        if len(title) < 5:
            return False

        # 日期解析：优先使用列表中的日期（格式 MM-DD），回退到当前时间
        pub_date = None
        if date_str:
            try:
                month, day = map(int, date_str.split('-'))
                pub_date = datetime(datetime.now().year, month, day)
            except Exception:
                pass
        if not pub_date:
            pub_date = datetime.now()

        articles.append(create_article(href, title, site, pub_date, 'hkcna'))
        return True

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 1. 轮播图区域：标题在 .black p 中
        for slide_li in soup.select('.slideBox .bd ul li'):
            link = slide_li.find('a', href=True)
            title_p = slide_li.select_one('.black p')
            if link and title_p:
                _add_article(link['href'], title_p.get_text(strip=True))

        # 2. 头条焦点 + 头条列表
        news_con = soup.select_one('.newsCon')
        if news_con:
            # 焦点标题
            focus_link = news_con.select_one('h4 > a')
            if focus_link:
                _add_article(focus_link['href'], focus_link.get_text(strip=True))
            # 列表
            for li in news_con.select('.newsList li a'):
                _add_article(li['href'], li.get_text(strip=True))

        # 3. 实时新闻滚动区
        for li_a in soup.select('.ssxw .infoList li a'):
            _add_article(li_a['href'], li_a.get_text(strip=True))

        # 4. 分类栏目（港澳/大湾区/台湾/内地/国际等）
        for box in soup.select('.boxDiv'):
            # 焦点文章
            focus_link = box.select_one('.boxLeft h4 a')
            if focus_link:
                _add_article(focus_link['href'], focus_link.get_text(strip=True))
            # 列表文章（含日期）
            for li in box.select('.boxRight .boxList li'):
                link = li.find('a', href=True)
                date_span = li.find('span')
                if link:
                    date_str = date_span.get_text(strip=True) if date_span else None
                    _add_article(link['href'], link.get_text(strip=True), date_str)

        # 5. 兜底：如果语义化选择器未匹配到文章，回退到遍历所有链接
        if not articles:
            print("[香港新闻网解析器] 语义化选择器未匹配，启用兜底遍历模式")
            for link in soup.find_all('a', href=True):
                title = link.get_text(strip=True)
                if title:
                    _add_article(link['href'], title)

    except Exception as e:
        print(f"[香港新闻网解析器] 错误: {e}")

    return articles


def parse_mingpao(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    明报专用解析器
    新版URL格式: /(pns|ins)/{分类}/article/{YYYYMMDD}/s{编号}/{文章ID}/{标题slug}
    示例: /pns/要聞/article/20260301/s00001/1772303190286/美以向伊朗開戰...
    """
    articles = []
    seen_urls = set()
    base_url = 'https://news.mingpao.com'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 新版明报文章URL模式：包含 /article/ 路径段
        article_pattern = re.compile(r'/(pns|ins)/[^/]+/article/(\d{8})/s\d+/')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not href:
                continue

            if not article_pattern.search(href):
                continue

            # 补全相对路径
            if href.startswith('/'):
                href = base_url + href

            # 排除非 news.mingpao.com 的链接
            if 'news.mingpao.com' not in href:
                continue

            if href in seen_urls:
                continue
            seen_urls.add(href)

            # 提取标题：优先 title 属性，其次子元素 h5/h1/h2 文本，最后链接文本
            title = link.get('title', '').strip()
            if not title:
                heading = link.find(['h5', 'h1', 'h2'])
                if heading:
                    title = heading.get_text(strip=True)
            if not title:
                title = link.get_text(strip=True)

            if len(title) < 5:
                continue

            # 从URL中提取发布日期
            pub_date = datetime.now()
            date_match = article_pattern.search(href)
            if date_match:
                try:
                    pub_date = datetime.strptime(date_match.group(2), '%Y%m%d')
                except ValueError:
                    pass

            articles.append(create_article(href, title, site, pub_date, 'mingpao'))

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
    共同社中文（共同網）专用解析器
    数据源: https://tchina.kyodonews.net/
    URL格式: /articles/-/{数字}
    注意：页面需滚动到底部才能加载全部内容，建议配合浏览器自动化抓取
    """
    articles = []
    seen_urls = set()
    base_url = 'https://tchina.kyodonews.net'
    article_pattern = re.compile(r'/articles/-/\d+')

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 1) 头条主图区：<a class="top-news-main__link">
        for link in soup.find_all('a', class_='top-news-main__link'):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            h3 = link.find('h3', class_='top-news-main__ttl')
            title = h3.get_text(strip=True) if h3 else link.get_text(strip=True)
            if len(title) < 5:
                continue
            pub_date = _parse_kyodo_time(link) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'kyodo_cn'))

        # 2) 副头条区：<a class="top-news-sub__link">
        for link in soup.find_all('a', class_='top-news-sub__link'):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            title = link.get_text(strip=True)
            if len(title) < 5:
                continue
            pub_date = _parse_kyodo_time(link) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'kyodo_cn'))

        # 3) 最新报道列表：<a class="m-article-item-ttl__link">
        for link in soup.find_all('a', class_='m-article-item-ttl__link'):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)
            title = link.get_text(strip=True)
            if len(title) < 5:
                continue
            pub_date = _parse_kyodo_time(link) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'kyodo_cn'))

    except Exception as e:
        print(f"[共同社解析器] 错误: {e}")

    return articles


def _parse_kyodo_time(element) -> Optional[datetime]:
    """从共同社文章元素的相邻 <time datetime="..."> 提取 ISO 时间"""
    try:
        # 在父级 article/div 容器中找 <time>
        for parent_class in ['top-news-sub__item', 'top-news-main', 'm-article-item']:
            parent = element.find_parent('article', class_=parent_class) or \
                     element.find_parent('div', class_=parent_class)
            if parent:
                time_tag = parent.find('time')
                if time_tag and time_tag.get('datetime'):
                    return datetime.fromisoformat(time_tag['datetime'])
        # 回退：在同级或父级中找任意 <time>
        parent = element.find_parent(['article', 'div'])
        if parent:
            time_tag = parent.find('time')
            if time_tag and time_tag.get('datetime'):
                return datetime.fromisoformat(time_tag['datetime'])
    except Exception:
        pass
    return None


def parse_nhk_cn(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    NHK新闻专用解析器
    数据源: https://news.web.nhk/newsweb
    URL格式: /newsweb/na/na-k{数字}
    """
    articles = []
    seen_urls = set()
    base_url = 'https://news.web.nhk'
    article_pattern = re.compile(r'/newsweb/na/na-k\d+')

    try:
        soup = BeautifulSoup(html, 'html.parser')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue

            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            # 标题在 <strong> 或 <p> 子元素中
            strong = link.find('strong')
            title = strong.get_text(strip=True) if strong else link.get_text(strip=True)
            if len(title) < 3:
                continue

            # 从 <time datetime="..."> 提取日期
            pub_date = _parse_nhk_time(link) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'nhk_cn'))

    except Exception as e:
        print(f"[NHK解析器] 错误: {e}")

    return articles


def _parse_nhk_time(element) -> Optional[datetime]:
    """从 NHK 文章元素中提取 <time datetime="..."> 的 ISO 时间"""
    try:
        # 先在链接内部找
        time_tag = element.find('time')
        # 再在父级容器中找
        if not time_tag:
            parent = element.find_parent('li') or element.find_parent('div')
            if parent:
                time_tag = parent.find('time')
        if time_tag and time_tag.get('datetime'):
            dt_str = time_tag['datetime']
            # 格式: 2026-03-01T05:05:40+09:00
            return datetime.fromisoformat(dt_str)
    except Exception:
        pass
    return None


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
    哈萨克斯坦国际通讯社（哈通社）专用解析器
    数据源: https://cn.inform.kz/
    URL格式: /news/{slug}/
    """
    articles = []
    seen_urls = set()
    base_url = 'https://cn.inform.kz'
    article_pattern = re.compile(r'/news/[a-zA-Z0-9_-]+-[a-f0-9]+/')

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 1) 最新新闻卡片：<div class="lastCard">
        for card in soup.find_all('div', class_='lastCard'):
            link = card.find('a', href=True)
            if not link:
                continue
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)

            title_div = card.find('div', class_='lastCard__title')
            title = title_div.get_text(strip=True) if title_div else ''
            if len(title) < 5:
                continue

            time_div = card.find('div', class_='lastCard__time')
            pub_date = _parse_inform_time(time_div) if time_div else datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'inform_kz'))

        # 2) 分类新闻卡片：<div class="categoryCard">
        for card in soup.find_all('div', class_='categoryCard'):
            link = card.find('a', href=True)
            if not link:
                continue
            href = link.get('href', '').strip()
            if not article_pattern.search(href):
                continue
            if not href.startswith('http'):
                href = base_url + href
            if href in seen_urls:
                continue
            seen_urls.add(href)

            title_div = card.find('div', class_='categoryCard__title')
            title = title_div.get_text(strip=True) if title_div else ''
            if len(title) < 5:
                continue

            time_div = card.find('div', class_='categoryCard__time')
            pub_date = _parse_inform_time(time_div) if time_div else datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'inform_kz'))

    except Exception as e:
        print(f"[哈通社解析器] 错误: {e}")

    return articles


# 哈通社中文月份映射
_INFORM_MONTHS = {
    '一月': 1, '二月': 2, '三月': 3, '四月': 4,
    '五月': 5, '六月': 6, '七月': 7, '八月': 8,
    '九月': 9, '十月': 10, '十一月': 11, '十二月': 12,
}


def _parse_inform_time(time_div) -> Optional[datetime]:
    """解析哈通社时间格式：'23:00, 28 二月 2026'"""
    try:
        text = time_div.get_text(strip=True)
        # 格式: HH:MM, DD 月份 YYYY
        m = re.match(r'(\d{1,2}):(\d{2}),\s*(\d{1,2})\s+(\S+)\s+(\d{4})', text)
        if m:
            hour, minute, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            month = _INFORM_MONTHS.get(m.group(4), 0)
            year = int(m.group(5))
            if month:
                return datetime(year, month, day, hour, minute)
    except Exception:
        pass
    return None


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

            # 处理各种URL格式：协议相对、路径相对、完整URL
            if href.startswith('//'):
                href = 'https:' + href
            elif href.startswith('/'):
                href = base_url + href

            # 规范化：去除域名重复（如 foxnews.com//www.foxnews.com/...）
            href = re.sub(r'(https?://www\.foxnews\.com)/+www\.foxnews\.com/', r'\1/', href)

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
    基于语义化HTML精准定位文章，支持多级分类和URL编码中文字符
    URL格式: /cn/{分类}/YYYYMMDD-{slug} 或 /cn/{分类}/{子分类}/YYYYMMDD-{slug}
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.rfi.fr'

    # 宽松正则：支持多级分类路径 + URL编码中文字符
    article_pattern = re.compile(r'/cn/(?:[^/]+/)+\d{8}-\S+')

    def _process_link(link_tag) -> bool:
        """处理单个链接标签，成功添加返回True"""
        href = link_tag.get('href', '').strip()
        if not article_pattern.search(href):
            return False

        # URL补全
        if href.startswith('/'):
            href = base_url + href

        if href in seen_urls:
            return False
        seen_urls.add(href)

        # 提取标题：优先从父级h2获取，回退到链接文本
        title = ''
        parent_h2 = link_tag.find_parent('h2')
        if parent_h2:
            title = parent_h2.get_text(strip=True)
        if not title:
            title = link_tag.get_text(strip=True)
        if len(title) < 5:
            return False

        pub_date = extract_date_from_url(href) or datetime.now()
        articles.append(create_article(href, title, site, pub_date, 'rfi'))
        return True

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 主逻辑：语义化CSS选择器精准定位文章标题链接
        title_links = soup.select('div.article__title a[data-article-item-link]')
        for link in title_links:
            _process_link(link)

        # 兜底：如果语义化选择器未匹配到文章（RFI改版），回退到遍历所有<a>标签
        if not articles:
            print("[RFI解析器] 语义化选择器未匹配，启用兜底遍历模式")
            for link in soup.find_all('a', href=True):
                _process_link(link)

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
    数据源: https://www.state.gov/press-releases/
    URL格式: /releases/office-of-the-spokesperson/YYYY/MM/slug/
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.state.gov'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 文章列表项：<li class="collection-result">
        for item in soup.find_all('li', class_='collection-result'):
            link = item.find('a', class_='collection-result__link')
            if not link:
                continue

            href = link.get('href', '').strip()
            if not href or 'state.gov' not in href and not href.startswith('/'):
                continue
            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 10:
                continue

            # 日期：<div class="collection-result-meta"> 内的 <span dir="ltr">February 27, 2026</span>
            pub_date = _parse_state_gov_date(item) or datetime.now()
            articles.append(create_article(href, title, site, pub_date, 'us_state'))

    except Exception as e:
        print(f"[美国国务院解析器] 错误: {e}")

    return articles


def _parse_state_gov_date(item) -> Optional[datetime]:
    """从 collection-result-meta 中提取日期，格式：February 27, 2026"""
    try:
        meta = item.find('div', class_='collection-result-meta')
        if meta:
            # 日期在 <span dir="ltr"> 中
            for span in meta.find_all('span'):
                text = span.get_text(strip=True)
                try:
                    return datetime.strptime(text, '%B %d, %Y')
                except ValueError:
                    continue
    except Exception:
        pass
    return None


def parse_uscis(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    美国移民局（USCIS）专用解析器
    数据源: https://www.uscis.gov/newsroom/all-news
    URL格式: /newsroom/news-releases/slug 或 /newsroom/alerts/slug
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.uscis.gov'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 文章列表行：<div class="views-row">
        for row in soup.find_all('div', class_='views-row'):
            # 标题：<div class="views-field-title"> 内的 <a>
            title_div = row.find('div', class_='views-field-title')
            if not title_div:
                continue
            link = title_div.find('a', href=True)
            if not link:
                continue

            href = link.get('href', '').strip()
            if not href:
                continue
            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 10:
                continue

            # 日期：<time datetime="2026-02-26T22:04:30Z">
            pub_date = datetime.now()
            time_tag = row.find('time')
            if time_tag and time_tag.get('datetime'):
                try:
                    pub_date = datetime.fromisoformat(time_tag['datetime'].replace('Z', '+00:00'))
                except Exception:
                    pass

            articles.append(create_article(href, title, site, pub_date, 'uscis'))

    except Exception as e:
        print(f"[USCIS解析器] 错误: {e}")

    return articles


def parse_au_homeaffairs(html: str, site: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    澳大利亚内政部（移民局）专用解析器
    数据源: https://www.homeaffairs.gov.au/news-media/archive
    URL格式: /news-media/archive/article?itemId={数字}
    注意：页面由 Angular 动态渲染，建议配合浏览器自动化抓取
    """
    articles = []
    seen_urls = set()
    base_url = 'https://www.homeaffairs.gov.au'

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 文章容器：<div class="news-article">
        for article_div in soup.find_all('div', class_='news-article'):
            # 标题：<h3 class="title"><a href="...">标题</a></h3>
            h3 = article_div.find('h3', class_='title')
            if not h3:
                continue
            link = h3.find('a', href=True)
            if not link:
                continue

            href = link.get('href', '').strip()
            if not href:
                continue
            if href.startswith('/'):
                href = base_url + href

            if href in seen_urls:
                continue
            seen_urls.add(href)

            title = link.get_text(strip=True)
            if len(title) < 5:
                continue

            # 日期：<div class="date">19 Feb 2026</div>
            pub_date = datetime.now()
            date_div = article_div.find('div', class_='date')
            if date_div:
                try:
                    pub_date = datetime.strptime(date_div.get_text(strip=True), '%d %b %Y')
                except Exception:
                    pass

            articles.append(create_article(href, title, site, pub_date, 'au_homeaffairs'))

    except Exception as e:
        print(f"[澳大利亚内政部解析器] 错误: {e}")

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
