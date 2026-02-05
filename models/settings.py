# -*- coding: utf-8 -*-
"""
设置管理模块
存储 API 配置等系统设置
"""

import json
import os
from typing import Dict, Any, Optional
from datetime import datetime

# 设置文件路径
SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'settings.json')

# 默认设置
DEFAULT_SETTINGS = {
    'llm': {
        'provider': 'siliconflow',  # 当前选择的提供商
        'model': 'deepseek-ai/DeepSeek-V3',  # 当前选择的模型
        # 各提供商独立配置
        'providers': {
            'siliconflow': {
                'api_key': '',
                'api_url': 'https://api.siliconflow.cn/v1/chat/completions'
            },
            'deepseek': {
                'api_key': '',
                'api_url': 'https://api.deepseek.com/v1/chat/completions'
            },
            'openai': {
                'api_key': '',
                'api_url': 'https://api.openai.com/v1/chat/completions'
            },
            'gemini': {
                'api_key': '',
                'api_url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions'
            },
            'custom': {
                'api_key': '',
                'api_url': ''
            }
        }
    },
    'crawler': {
        'timeout': 30,
        'max_articles': 500,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    },
    'duty': {
        'leaders': [],   # 值班领导列表
        'officers': []   # 值班员列表
    },
    'summary': {
        'custom_prompt': ''  # 自定义AI总结提示词，为空则使用默认
    }
}

# 默认AI总结提示词
DEFAULT_SUMMARY_PROMPT = """你是一名专业的舆情分析师，服务于中国移民管理警察部门。
现在是 {date}。

我将为你提供今日获取的 {count} 条新闻，每条新闻包含标题和原始链接。
请根据这些信息完成深度舆情分析，并提取结构化数据供系统生成页面。

【今日新闻列表】
{news_list}

请严格按照以下 **PART 1 (文本报告)** 和 **PART 2 (数据输出)** 两部分进行输出：

---

### PART 1: 舆情分析报告（供人类阅读，使用中文）

## 一、今日舆情总结
今日全球舆情呈现多元化态势，主要聚焦于以下几个领域：

* **国际冲突与人道主义危机**: [简述当前主要冲突区域、伤亡/援助/国际反应等关键点]
* **重大国际关系动态**: [列举大国领导人互动、外交表态、双边摩擦等]
* **经济与科技热点**: [市值突破、产业周期、新兴领域、机构预警等]
* **移民与边境管理**: [各国最新移民/签证/遣返/劳动力政策动向、非法移民动态]
* **社会与文化议题**: [涉及移民的社会争议、种族冲突、软性文化新闻等]

## 二、热点新闻TOP5
请从上述新闻中选出最值得关注的5条热点新闻，按对**中国移民管理工作**或**国际局势**的重要程度排序。格式如下：
1. [新闻标题] - [重要原因一句话说明]
2. [新闻标题] - [重要原因一句话说明]
...

## 三、移民管理风险分析与应对建议
从中国移民管理警察的工作角度出发，结合今日舆情，分析可能存在的风险并提出建议：
* **出入境管理风险**（如：签证政策变动引发的流量变化、伪假证件风险等）
* **边境安全风险**（如：战乱地区的难民外溢、跨境犯罪、走私偷渡等）
* **涉外舆情风险**（如：针对特定国籍旅客的检查政策引发的舆论关注等）
* **口岸通关风险**（如：流行病传播、突发安全威胁等）

**[应对措施与建议]**
(针对上述风险提出2-3条具体可行的工作建议)

---

### PART 2: 结构化数据（供服务器解析，严禁省略）

请务必输出一个标准的 JSON 代码块，包含你在PART 1中引用的新闻。

```json
{{
  "news_data": {{
    "category_news": {{
      "international_conflict": [{{"title": "新闻标题", "url": "链接"}}],
      "international_relations": [{{"title": "新闻标题", "url": "链接"}}],
      "economy_tech": [{{"title": "新闻标题", "url": "链接"}}],
      "immigration_border": [{{"title": "新闻标题", "url": "链接"}}],
      "society_culture": [{{"title": "新闻标题", "url": "链接"}}]
    }},
    "top_5_news": [
      {{"rank": 1, "title": "新闻标题", "url": "链接"}},
      {{"rank": 2, "title": "新闻标题", "url": "链接"}},
      {{"rank": 3, "title": "新闻标题", "url": "链接"}},
      {{"rank": 4, "title": "新闻标题", "url": "链接"}},
      {{"rank": 5, "title": "新闻标题", "url": "链接"}}
    ]
  }}
}}
```

**重要约束：**
- category_news 中每个分类的数组只包含该分类实际引用的新闻
- 如果某分类没有相关新闻，则为空数组 []
- title 和 url 必须与输入的新闻列表完全一致"""

# 预设的 API 提供商配置
API_PROVIDERS = {
    'siliconflow': {
        'name': 'SiliconFlow',
        'api_url': 'https://api.siliconflow.cn/v1/chat/completions',
        'models': [
            {'id': 'deepseek-ai/DeepSeek-V3', 'name': 'DeepSeek V3'},
            {'id': 'Pro/THUDM/GLM-4-9B-0414', 'name': 'GLM-4-9B'},
            {'id': 'Qwen/Qwen2.5-72B-Instruct', 'name': 'Qwen2.5-72B'},
            {'id': 'deepseek-ai/DeepSeek-R1', 'name': 'DeepSeek R1'},
        ]
    },
    'deepseek': {
        'name': 'DeepSeek',
        'api_url': 'https://api.deepseek.com/v1/chat/completions',
        'models': [
            {'id': 'deepseek-chat', 'name': 'DeepSeek Chat'},
            {'id': 'deepseek-coder', 'name': 'DeepSeek Coder'},
        ]
    },
    'openai': {
        'name': 'OpenAI',
        'api_url': 'https://api.openai.com/v1/chat/completions',
        'models': [
            {'id': 'gpt-4o', 'name': 'GPT-4o'},
            {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini'},
            {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo'},
            {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo'},
        ]
    },
    'gemini': {
        'name': 'Google Gemini',
        'api_url': 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
        'models': [
            {'id': 'gemini-2.0-flash', 'name': 'Gemini 2.0 Flash'},
            {'id': 'gemini-2.0-flash-lite', 'name': 'Gemini 2.0 Flash Lite'},
            {'id': 'gemini-1.5-pro', 'name': 'Gemini 1.5 Pro'},
            {'id': 'gemini-1.5-flash', 'name': 'Gemini 1.5 Flash'},
        ]
    },
    'custom': {
        'name': '自定义',
        'api_url': '',
        'models': []
    }
}


def load_settings() -> Dict[str, Any]:
    """加载设置"""
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            # 合并默认设置（确保新增的设置项存在）
            merged = DEFAULT_SETTINGS.copy()
            for key, value in settings.items():
                if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key].update(value)
                else:
                    merged[key] = value
            return merged
    except (json.JSONDecodeError, IOError):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict[str, Any]) -> bool:
    """保存设置"""
    try:
        # 添加更新时间
        settings['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        print(f"保存设置失败: {e}")
        return False


def get_setting(key: str, default: Any = None) -> Any:
    """获取单个设置项（支持点号分隔的路径）"""
    settings = load_settings()

    keys = key.split('.')
    value = settings

    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default

    return value


def set_setting(key: str, value: Any) -> bool:
    """设置单个设置项（支持点号分隔的路径）"""
    settings = load_settings()

    keys = key.split('.')
    target = settings

    for k in keys[:-1]:
        if k not in target:
            target[k] = {}
        target = target[k]

    target[keys[-1]] = value
    return save_settings(settings)


def get_llm_config() -> Dict[str, str]:
    """获取 LLM 配置"""
    settings = load_settings()
    llm_config = settings.get('llm', {})

    # 获取当前选择的提供商
    provider = llm_config.get('provider', 'siliconflow')
    model = llm_config.get('model', 'deepseek-ai/DeepSeek-V3')

    # 获取该提供商的配置
    providers_config = llm_config.get('providers', {})
    provider_config = providers_config.get(provider, {})

    # 获取 API Key 和 URL
    api_key = provider_config.get('api_key', '')
    api_url = provider_config.get('api_url', '')

    # 如果没有配置，尝试从环境变量获取（兼容旧配置）
    if not api_key:
        from config import Config
        api_key = Config.DEEPSEEK_API_KEY

    # 如果没有 URL，使用默认值
    if not api_url:
        api_url = API_PROVIDERS.get(provider, {}).get('api_url', '')

    return {
        'provider': provider,
        'api_key': api_key,
        'api_url': api_url,
        'model': model
    }


def get_provider_api_key(provider: str) -> str:
    """获取指定提供商的 API Key"""
    settings = load_settings()
    llm_config = settings.get('llm', {})
    providers_config = llm_config.get('providers', {})
    provider_config = providers_config.get(provider, {})
    return provider_config.get('api_key', '')


def get_deepseek_config() -> Dict[str, str]:
    """获取 DeepSeek 配置（兼容旧接口）"""
    return get_llm_config()


def get_openai_config() -> Dict[str, str]:
    """获取 OpenAI 配置（兼容旧接口）"""
    return get_llm_config()


def get_api_providers() -> Dict[str, Any]:
    """获取所有 API 提供商配置"""
    return API_PROVIDERS


def mask_api_key(api_key: str) -> str:
    """遮蔽 API Key 中间部分"""
    if not api_key or len(api_key) < 10:
        return api_key
    return api_key[:6] + '*' * (len(api_key) - 10) + api_key[-4:]


def get_summary_prompt() -> str:
    """获取AI总结提示词（自定义或默认）"""
    settings = load_settings()
    custom_prompt = settings.get('summary', {}).get('custom_prompt', '')
    if custom_prompt and custom_prompt.strip():
        return custom_prompt.strip()
    return DEFAULT_SUMMARY_PROMPT


def set_summary_prompt(prompt: str) -> bool:
    """设置自定义AI总结提示词"""
    return set_setting('summary.custom_prompt', prompt)


def get_default_summary_prompt() -> str:
    """获取默认AI总结提示词"""
    return DEFAULT_SUMMARY_PROMPT
