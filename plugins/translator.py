# -*- coding: utf-8 -*-
"""
标题翻译模块
使用 LLM API 将非中文标题翻译为中文
"""

import re
import requests
from typing import Optional, List, Dict, Any
from models.settings import get_llm_config


def is_chinese(text: str) -> bool:
    """
    检测文本是否主要为中文
    如果中文字符占比超过30%，认为是中文
    """
    if not text:
        return False

    chinese_count = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(re.findall(r'\S', text))  # 非空白字符

    if total_chars == 0:
        return False

    return chinese_count / total_chars > 0.3


def translate_title(title: str, source_lang: str = 'auto') -> Optional[str]:
    """
    将标题翻译为中文

    参数:
        title: 原始标题
        source_lang: 源语言（auto=自动检测）

    返回:
        翻译后的中文标题，失败返回 None
    """
    if not title or not title.strip():
        return None

    # 如果已经是中文，直接返回
    if is_chinese(title):
        return title

    # 获取 LLM 配置
    config = get_llm_config()
    api_key = config.get('api_key')
    api_url = config.get('api_url')
    model = config.get('model')

    # 使用默认配置（如果未配置）
    if not api_key:
        api_key = 'sk-bgyzpzozdwghavpnsnglmbnmwakalhspstohaoasancrtokl'
    if not api_url:
        api_url = 'https://api.siliconflow.cn/v1/chat/completions'
    if not model:
        model = 'Pro/Qwen/Qwen2.5-7B-Instruct'

    # 确保 URL 格式正确
    if not api_url.endswith('/chat/completions'):
        if '/v1' in api_url:
            api_url = api_url.rstrip('/') + '/chat/completions'
        else:
            api_url = api_url.rstrip('/') + '/v1/chat/completions'

    try:
        response = requests.post(
            api_url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': [
                    {
                        'role': 'user',
                        'content': f'翻译下面的内容为中文，不需要任何解释：\n{title}'
                    }
                ],
                'max_tokens': 200,
                'temperature': 0.1
            },
            timeout=60  # 增加超时时间到60秒
        )

        if response.status_code == 200:
            result = response.json()
            translated = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            translated = translated.strip()

            # 清理可能的引号
            if translated.startswith('"') and translated.endswith('"'):
                translated = translated[1:-1]
            if translated.startswith('「') and translated.endswith('」'):
                translated = translated[1:-1]
            if translated.startswith("'") and translated.endswith("'"):
                translated = translated[1:-1]

            return translated if translated else None
        else:
            print(f"[翻译] API 请求失败: {response.status_code} - {response.text[:100]}")
            return None

    except requests.exceptions.Timeout:
        print("[翻译] API 请求超时")
        return None
    except Exception as e:
        print(f"[翻译] 翻译失败: {e}")
        return None


def translate_titles_batch(titles: List[str], batch_size: int = 10) -> List[Optional[str]]:
    """
    批量翻译标题（逐个翻译，可优化为批量）

    参数:
        titles: 标题列表
        batch_size: 批次大小（预留接口）

    返回:
        翻译后的标题列表
    """
    results = []
    for title in titles:
        translated = translate_title(title)
        results.append(translated)
    return results


def process_articles_translation(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    处理文章列表，为非中文标题添加翻译

    参数:
        articles: 文章列表

    返回:
        处理后的文章列表，每篇文章会添加 title_cn 字段
    """
    for article in articles:
        title = article.get('title', '')

        if is_chinese(title):
            # 已是中文，直接使用
            article['title_cn'] = title
            article['needs_translation'] = False
        else:
            # 需要翻译
            translated = translate_title(title)
            if translated:
                article['title_cn'] = translated
                article['title_original'] = title
                article['needs_translation'] = False
            else:
                # 翻译失败，保留原标题
                article['title_cn'] = title
                article['needs_translation'] = True

    return articles


class TitleTranslator:
    """
    标题翻译器类
    支持缓存和批量翻译
    """

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._enabled = True

    def enable(self):
        """启用翻译"""
        self._enabled = True

    def disable(self):
        """禁用翻译"""
        self._enabled = False

    def is_enabled(self) -> bool:
        """检查翻译是否启用"""
        return self._enabled

    def translate(self, title: str) -> str:
        """
        翻译单个标题

        参数:
            title: 原始标题

        返回:
            翻译后的标题（如果翻译失败或已禁用，返回原标题）
        """
        if not title:
            return title

        if not self._enabled:
            return title

        # 检查缓存
        if title in self._cache:
            return self._cache[title]

        # 如果已经是中文
        if is_chinese(title):
            self._cache[title] = title
            return title

        # 翻译
        translated = translate_title(title)
        result = translated if translated else title

        # 缓存结果
        self._cache[title] = result

        return result

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()


# 全局翻译器实例
_translator_instance = None


def get_translator() -> TitleTranslator:
    """获取翻译器单例"""
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = TitleTranslator()
    return _translator_instance
