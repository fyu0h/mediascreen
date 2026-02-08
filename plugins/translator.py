# -*- coding: utf-8 -*-
"""
标题翻译模块
使用 LLM API 将非中文标题翻译为中文
支持批量翻译（多条标题合并为一次 API 调用）和数据库去重
"""

import re
import requests
from typing import Optional, List, Dict, Any
from collections import OrderedDict
from models.settings import get_translation_config, get_translation_prompt

# 批量翻译配置
BATCH_SIZE = 10  # 每批翻译的标题数量


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


def _get_translation_api_config() -> Optional[Dict[str, str]]:
    """
    获取翻译 API 配置（内部复用）
    返回 {api_key, api_url, model}，配置不完整返回 None
    """
    config = get_translation_config()
    api_key = config.get('api_key')
    api_url = config.get('api_url')
    model = config.get('model')

    if not api_key:
        print("[翻译] 未配置翻译 API 密钥，请在系统设置中配置")
        return None
    if not api_url:
        print("[翻译] 未配置翻译 API 地址，请在系统设置中配置")
        return None
    if not model:
        model = 'Pro/Qwen/Qwen2.5-7B-Instruct'

    # 确保 URL 格式正确
    if not api_url.endswith('/chat/completions'):
        if '/v1' in api_url:
            api_url = api_url.rstrip('/') + '/chat/completions'
        else:
            api_url = api_url.rstrip('/') + '/v1/chat/completions'

    return {'api_key': api_key, 'api_url': api_url, 'model': model}


def _clean_translated_text(text: str) -> str:
    """清理翻译结果中的多余引号"""
    text = text.strip()
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    if text.startswith('「') and text.endswith('」'):
        text = text[1:-1]
    if text.startswith("'") and text.endswith("'"):
        text = text[1:-1]
    return text


def translate_title(title: str, source_lang: str = 'auto') -> Optional[str]:
    """
    将单个标题翻译为中文（保留用于测试 API 等单条场景）

    参数:
        title: 原始标题
        source_lang: 源语言（auto=自动检测）

    返回:
        翻译后的中文标题，失败返回 None
    """
    if not title or not title.strip():
        return None

    if is_chinese(title):
        return title

    api_config = _get_translation_api_config()
    if not api_config:
        return None

    prompt_template = get_translation_prompt()
    prompt = prompt_template.replace('{text}', title)

    try:
        response = requests.post(
            api_config['api_url'],
            headers={
                'Authorization': f'Bearer {api_config["api_key"]}',
                'Content-Type': 'application/json'
            },
            json={
                'model': api_config['model'],
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 200,
                'temperature': 0.1
            },
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            translated = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            translated = _clean_translated_text(translated)
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


def _translate_batch_api(titles: List[str]) -> List[Optional[str]]:
    """
    批量翻译：将多条标题合并为一次 API 调用

    发送格式:
        1. Title one
        2. Title two
        3. Title three

    期望返回:
        1. 标题一
        2. 标题二
        3. 标题三

    参数:
        titles: 需要翻译的标题列表（已过滤中文）

    返回:
        翻译结果列表，与输入顺序一一对应，失败项为 None
    """
    if not titles:
        return []

    # 单条直接走单条接口
    if len(titles) == 1:
        return [translate_title(titles[0])]

    api_config = _get_translation_api_config()
    if not api_config:
        return [None] * len(titles)

    # 构建编号列表
    numbered_text = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(titles))

    system_prompt = (
        '你是翻译助手。将用户提供的编号标题逐条翻译为中文。'
        '严格保持编号格式，每行一条，只输出翻译结果，不要解释。'
    )

    try:
        response = requests.post(
            api_config['api_url'],
            headers={
                'Authorization': f'Bearer {api_config["api_key"]}',
                'Content-Type': 'application/json'
            },
            json={
                'model': api_config['model'],
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': numbered_text}
                ],
                'max_tokens': 100 * len(titles),  # 每条标题预留约100 token
                'temperature': 0.1
            },
            timeout=90
        )

        if response.status_code != 200:
            print(f"[批量翻译] API 请求失败: {response.status_code} - {response.text[:100]}")
            return [None] * len(titles)

        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')

        # 解析编号格式的返回结果
        return _parse_batch_response(content, len(titles))

    except requests.exceptions.Timeout:
        print("[批量翻译] API 请求超时")
        return [None] * len(titles)
    except Exception as e:
        print(f"[批量翻译] 翻译失败: {e}")
        return [None] * len(titles)


def _parse_batch_response(content: str, expected_count: int) -> List[Optional[str]]:
    """
    解析批量翻译的返回结果

    支持格式:
        1. 翻译结果
        1、翻译结果
        1）翻译结果
    """
    results: Dict[int, str] = {}

    for line in content.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        # 匹配编号: "1. xxx", "1、xxx", "1）xxx", "1) xxx"
        match = re.match(r'^(\d+)\s*[.、）)]\s*(.+)', line)
        if match:
            idx = int(match.group(1))
            text = _clean_translated_text(match.group(2))
            if 1 <= idx <= expected_count and text:
                results[idx] = text

    # 按顺序组装结果
    return [results.get(i + 1) for i in range(expected_count)]


def _get_existing_translations(locs: List[str]) -> Dict[str, str]:
    """
    从数据库查询已有的翻译结果（去重用）

    参数:
        locs: 文章 URL 列表

    返回:
        {loc: title_cn, ...} 已翻译的文章映射
    """
    if not locs:
        return {}

    try:
        from models.mongo import get_articles_collection
        collection = get_articles_collection()

        # 批量查询已存在的文章
        cursor = collection.find(
            {'loc': {'$in': locs}},
            {'loc': 1, 'title': 1, 'title_original': 1}
        )

        result = {}
        for doc in cursor:
            loc = doc.get('loc', '')
            title = doc.get('title', '')
            # 如果数据库中已有中文标题，视为已翻译
            if loc and title and is_chinese(title):
                result[loc] = title
        return result

    except Exception as e:
        print(f"[翻译去重] 查询数据库失败: {e}")
        return {}


def translate_titles_batch(titles: List[str], batch_size: int = BATCH_SIZE) -> List[Optional[str]]:
    """
    批量翻译标题

    参数:
        titles: 标题列表
        batch_size: 每批大小

    返回:
        翻译后的标题列表
    """
    results: List[Optional[str]] = []

    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        # 分离中文和非中文
        to_translate = []
        indices = []
        batch_results = [None] * len(batch)

        for j, title in enumerate(batch):
            if is_chinese(title):
                batch_results[j] = title
            else:
                to_translate.append(title)
                indices.append(j)

        # 批量翻译非中文标题
        if to_translate:
            translated = _translate_batch_api(to_translate)
            for k, idx in enumerate(indices):
                batch_results[idx] = translated[k]

        results.extend(batch_results)

    return results


def process_articles_translation(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    处理文章列表，为非中文标题添加翻译
    优化策略：
        1. 数据库去重 — 已翻译过的文章直接复用
        2. 批量翻译 — 多条标题合并为一次 API 调用

    参数:
        articles: 文章列表

    返回:
        处理后的文章列表，每篇文章会添加 title_cn 字段
    """
    if not articles:
        return articles

    # ===== 第一步：数据库去重 =====
    locs = [a.get('loc', '') for a in articles if a.get('loc')]
    existing = _get_existing_translations(locs)
    dedup_count = 0

    # 收集需要翻译的文章索引和标题
    need_translate_indices: List[int] = []
    need_translate_titles: List[str] = []

    for i, article in enumerate(articles):
        title = article.get('title', '')
        loc = article.get('loc', '')

        # 已是中文，直接使用
        if is_chinese(title):
            article['title_cn'] = title
            article['needs_translation'] = False
            continue

        # 数据库中已有翻译，直接复用
        if loc in existing:
            article['title_cn'] = existing[loc]
            article['title_original'] = title
            article['needs_translation'] = False
            dedup_count += 1
            continue

        # 需要翻译
        need_translate_indices.append(i)
        need_translate_titles.append(title)

    if dedup_count > 0:
        print(f"[翻译] 数据库去重跳过 {dedup_count} 篇已翻译文章")

    # ===== 第二步：批量翻译 =====
    if need_translate_titles:
        print(f"[翻译] 需要翻译 {len(need_translate_titles)} 篇，"
              f"分 {(len(need_translate_titles) + BATCH_SIZE - 1) // BATCH_SIZE} 批")

        # 按批次翻译
        for batch_start in range(0, len(need_translate_titles), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(need_translate_titles))
            batch_titles = need_translate_titles[batch_start:batch_end]
            batch_indices = need_translate_indices[batch_start:batch_end]

            translated_batch = _translate_batch_api(batch_titles)

            for j, idx in enumerate(batch_indices):
                article = articles[idx]
                translated = translated_batch[j] if j < len(translated_batch) else None

                if translated:
                    article['title_cn'] = translated
                    article['title_original'] = article.get('title', '')
                    article['needs_translation'] = False
                else:
                    # 翻译失败，保留原标题
                    article['title_cn'] = article.get('title', '')
                    article['needs_translation'] = True

    return articles


class TitleTranslator:
    """
    标题翻译器类
    支持 LRU 缓存和批量翻译
    """

    MAX_CACHE_SIZE = 10000  # 最大缓存条目数

    def __init__(self):
        self._cache: OrderedDict[str, str] = OrderedDict()
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

    @property
    def cache_size(self) -> int:
        """返回当前缓存大小"""
        return len(self._cache)

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

        # 检查缓存（命中时移到末尾，实现 LRU）
        if title in self._cache:
            self._cache.move_to_end(title)
            return self._cache[title]

        # 如果已经是中文
        if is_chinese(title):
            self._add_to_cache(title, title)
            return title

        # 翻译
        translated = translate_title(title)
        result = translated if translated else title

        # 缓存结果
        self._add_to_cache(title, result)

        return result

    def _add_to_cache(self, key: str, value: str):
        """添加到缓存，超过上限时删除最旧条目"""
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.MAX_CACHE_SIZE:
                # 删除最旧的条目（OrderedDict 的第一个）
                self._cache.popitem(last=False)
            self._cache[key] = value

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
