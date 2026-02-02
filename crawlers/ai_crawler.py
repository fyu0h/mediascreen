# -*- coding: utf-8 -*-
"""
AI 爬虫模块
使用 Crawl4AI 爬取网页，通过 DeepSeek 分析提取文章信息
"""

import requests
import json
import re
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from models.logger import log_request, log_operation


class AICrawler:
    """AI 驱动的爬虫"""

    def __init__(self, api_key: str = None, api_url: str = None, model: str = None,
                 deepseek_api_key: str = None, deepseek_base_url: str = None):
        """
        初始化 AI 爬虫
        参数：
            api_key: API 密钥
            api_url: API 地址
            model: 模型名称
            deepseek_api_key: (兼容旧参数) DeepSeek API 密钥
            deepseek_base_url: (兼容旧参数) DeepSeek API 地址
        """
        self.api_key = api_key or deepseek_api_key
        self.api_url = api_url or deepseek_base_url or 'https://api.siliconflow.cn/v1/chat/completions'
        self.model = model or 'deepseek-ai/DeepSeek-V3'

        # 确保 URL 格式正确
        if self.api_url and not self.api_url.endswith('/chat/completions'):
            if '/v1' not in self.api_url:
                self.api_url = self.api_url.rstrip('/') + '/v1/chat/completions'
            else:
                self.api_url = self.api_url.rstrip('/') + '/chat/completions'

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.timeout = 30

    def fetch_page(self, url: str) -> Optional[str]:
        """获取网页内容"""
        start_time = time.time()
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.encoding = response.apparent_encoding
            duration_ms = (time.time() - start_time) * 1000

            log_request(
                action='获取网页内容',
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
                action='获取网页内容',
                url=url,
                method='GET',
                request_headers=self.headers,
                duration_ms=duration_ms,
                status='error',
                error=str(e)
            )
            print(f"获取页面失败: {url}, 错误: {e}")
            return None

    def extract_text_content(self, html: str, base_url: str = '') -> Dict[str, Any]:
        """
        从 HTML 提取文本内容和链接
        返回：{text: 纯文本, links: [{text, href}, ...]}
        """
        soup = BeautifulSoup(html, 'html.parser')

        # 移除脚本、样式等无用标签
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript', 'iframe']):
            tag.decompose()

        # 提取主要内容区域
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|article|post|news', re.I)) or soup.body

        if not main_content:
            main_content = soup

        # 提取文本
        text = main_content.get_text(separator='\n', strip=True)

        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 提取链接
        links = []
        for a in main_content.find_all('a', href=True):
            href = a.get('href', '')
            link_text = a.get_text(strip=True)

            # 过滤无效链接
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue

            # 转为绝对 URL
            if base_url and not href.startswith(('http://', 'https://')):
                href = urljoin(base_url, href)

            if link_text and len(link_text) > 5:  # 过滤太短的链接文本
                links.append({
                    'text': link_text[:200],  # 限制长度
                    'href': href
                })

        return {
            'text': text[:15000],  # 限制文本长度
            'links': links[:100]   # 限制链接数量
        }

    def analyze_with_llm(self, content: Dict[str, Any], source_name: str = '') -> List[Dict[str, Any]]:
        """
        使用 LLM 分析内容，提取文章列表
        """
        if not self.api_key:
            raise ValueError("未配置 API 密钥")

        # 构建提示词
        prompt = self._build_prompt(content, source_name)

        request_body = {
            'model': self.model,
            'messages': [
                {
                    'role': 'system',
                    'content': '你是一个专业的新闻内容分析助手。你需要从网页内容中提取新闻文章列表。请严格按照JSON格式输出。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.1,
            'max_tokens': 4000
        }

        request_headers = {
            'Authorization': f'Bearer {self.api_key[:10]}***',  # 遮蔽 API Key
            'Content-Type': 'application/json'
        }

        start_time = time.time()
        try:
            response = requests.post(
                self.api_url,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json=request_body,
                timeout=60
            )
            duration_ms = (time.time() - start_time) * 1000

            response_body = None
            try:
                response_body = response.json()
            except:
                response_body = response.text[:2000]

            log_request(
                action='LLM 分析内容',
                url=self.api_url,
                method='POST',
                request_headers=request_headers,
                request_body={'model': self.model, 'messages': '[...]', 'temperature': 0.1, 'max_tokens': 4000},
                response_status=response.status_code,
                response_headers=dict(response.headers),
                response_body=response_body,
                duration_ms=duration_ms,
                status='success' if response.status_code == 200 else 'error'
            )

            if response.status_code == 200:
                result = response.json()
                content_text = result['choices'][0]['message']['content']
                return self._parse_llm_response(content_text)
            else:
                print(f"LLM API 错误: {response.status_code}, {response.text}")
                return []

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            log_request(
                action='LLM 分析内容',
                url=self.api_url,
                method='POST',
                request_headers=request_headers,
                request_body={'model': self.model, 'messages': '[...]'},
                duration_ms=duration_ms,
                status='error',
                error=str(e)
            )
            print(f"LLM 分析失败: {e}")
            return []

    def analyze_with_deepseek(self, content: Dict[str, Any], source_name: str = '') -> List[Dict[str, Any]]:
        """兼容旧方法名"""
        return self.analyze_with_llm(content, source_name)

    def _build_prompt(self, content: Dict[str, Any], source_name: str) -> str:
        """构建 LLM 提示词"""
        text = content.get('text', '')
        links = content.get('links', [])

        # 格式化链接列表
        links_text = '\n'.join([f"- [{l['text']}]({l['href']})" for l in links[:50]])

        prompt = f"""请分析以下新闻网站内容，提取所有新闻文章信息。

## 网页文本内容（部分）：
{text[:8000]}

## 网页中的链接：
{links_text}

## 要求：
1. 识别所有看起来像新闻文章的条目
2. 对于每篇文章，提取：
   - title: 文章标题（必需）
   - url: 文章链接（如果能从链接列表中匹配到）
   - summary: 文章摘要（如果有的话）
   - pub_date: 发布日期（如果能识别出来，格式：YYYY-MM-DD）

3. 只提取真正的新闻文章，忽略导航链接、广告等

请以JSON数组格式输出，示例：
```json
[
  {{"title": "文章标题1", "url": "https://...", "summary": "摘要...", "pub_date": "2024-01-01"}},
  {{"title": "文章标题2", "url": null, "summary": null, "pub_date": null}}
]
```

只输出JSON，不要其他解释。"""

        return prompt

    def _parse_llm_response(self, response_text: str) -> List[Dict[str, Any]]:
        """解析 LLM 返回的 JSON"""
        try:
            # 尝试提取 JSON 部分
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                json_str = json_match.group()
                articles = json.loads(json_str)

                # 验证和清理数据
                valid_articles = []
                for article in articles:
                    if isinstance(article, dict) and article.get('title'):
                        valid_articles.append({
                            'title': article.get('title', '').strip(),
                            'loc': article.get('url') or article.get('loc') or '',
                            'summary': article.get('summary', ''),
                            'pub_date': self._parse_date_str(article.get('pub_date'))
                        })
                return valid_articles
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
        except Exception as e:
            print(f"解析 LLM 响应失败: {e}")

        return []

    def _parse_date_str(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        if not date_str:
            return None

        formats = [
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%Y年%m月%d日',
            '%m/%d/%Y',
            '%d/%m/%Y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def crawl(self, site: Dict[str, Any], max_articles: int = 100) -> Dict[str, Any]:
        """
        使用 AI 爬取站点
        参数：
            site: 站点信息 {name, url, country_code, coords}
            max_articles: 最大文章数
        返回：
            {success: bool, articles: [...], error: str}
        """
        url = site.get('url')
        if not url:
            return {'success': False, 'articles': [], 'error': '未配置站点 URL'}

        source_name = site.get('name', '')
        country_code = site.get('country_code', '')
        coords = site.get('coords', [])

        log_operation(
            action=f'AI爬取站点: {source_name}',
            details={'url': url, 'method': 'ai', 'max_articles': max_articles},
            status='info'
        )

        # 获取页面内容
        html = self.fetch_page(url)
        if not html:
            log_operation(
                action=f'AI爬取失败: {source_name}',
                details={'url': url, 'error': '无法获取页面'},
                status='error'
            )
            return {'success': False, 'articles': [], 'error': f'无法获取页面: {url}'}

        # 提取文本和链接
        content = self.extract_text_content(html, url)

        if not content['text']:
            return {'success': False, 'articles': [], 'error': '页面内容为空'}

        # 使用 LLM 分析
        try:
            raw_articles = self.analyze_with_llm(content, source_name)
        except ValueError as e:
            return {'success': False, 'articles': [], 'error': str(e)}

        # 补充站点信息
        articles = []
        for article in raw_articles[:max_articles]:
            article['source_name'] = source_name
            article['country_code'] = country_code
            article['coords'] = coords
            article['fetched_at'] = datetime.now()
            articles.append(article)

        log_operation(
            action=f'AI爬取完成: {source_name}',
            details={'url': url, 'articles_count': len(articles)},
            status='success'
        )

        return {
            'success': True,
            'articles': articles,
            'count': len(articles),
            'error': None
        }


class Crawl4AIWrapper:
    """
    Crawl4AI 包装器（如果安装了 crawl4ai）
    提供更强大的动态页面爬取能力
    """

    def __init__(self):
        self.crawl4ai_available = False
        try:
            from crawl4ai import WebCrawler
            self.WebCrawler = WebCrawler
            self.crawl4ai_available = True
        except ImportError:
            print("Crawl4AI 未安装，将使用基础爬虫")

    def fetch_page(self, url: str) -> Optional[str]:
        """使用 Crawl4AI 获取页面"""
        if not self.crawl4ai_available:
            return None

        try:
            crawler = self.WebCrawler()
            crawler.warmup()
            result = crawler.run(url=url)
            if result.success:
                return result.html
            return None
        except Exception as e:
            print(f"Crawl4AI 获取页面失败: {e}")
            return None
