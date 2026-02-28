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
            'aimlapi': {
                'api_key': '',
                'api_url': 'https://api.aimlapi.com/v1/chat/completions'
            },
            'poixe': {
                'api_key': '',
                'api_url': 'https://api.poixe.com/v1/chat/completions'
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
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'auto_crawl_enabled': False,   # 是否启用定时全量爬取
        'auto_crawl_interval': 30,     # 爬取间隔（分钟），默认30分钟
        'proxy': {
            'enabled': False,
            'host': '',
            'port': 9000,
            'username': '',
            'password': '',
            'protocol': 'http'
        }
    },
    'duty': {
        'leaders': [],   # 值班领导列表
        'officers': []   # 值班员列表
    },
    'summary': {
        'custom_prompt': ''  # 自定义AI总结提示词，为空则使用默认
    },
    'telegram': {
        'webhook_url': '',           # 企业微信 Webhook URL
        'webhook_enabled': False,    # 是否启用 Webhook 推送
        'monitor_enabled': False,    # 是否启用监控服务
    },
    'translation': {
        'provider': 'siliconflow',  # 翻译使用的提供商
        'model': 'Pro/Qwen/Qwen2.5-7B-Instruct',  # 翻译使用的模型
        'custom_prompt': '',  # 自定义翻译提示词
        # 各提供商独立配置（翻译专用）
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
            'aimlapi': {
                'api_key': '',
                'api_url': 'https://api.aimlapi.com/v1/chat/completions'
            },
            'poixe': {
                'api_key': '',
                'api_url': 'https://api.poixe.com/v1/chat/completions'
            },
            'custom': {
                'api_key': '',
                'api_url': ''
            }
        }
    }
}

# 默认AI总结提示词
DEFAULT_SUMMARY_PROMPT = """你是一名资深的舆情分析师，专职服务于中国移民管理警察部门。你具备极高的政治敏锐度，擅长从复杂的国际新闻中捕捉涉边、涉外、涉移民管理的风险动向。

现在是 {date}。

我将为你提供今日获取的 {count} 条新闻，每条新闻包含标题和原始链接。请根据这些信息完成深度舆情分析，并提取结构化数据。

【今日新闻列表】
{news_list}

请严格按照以下 PART 1 (文本报告) 和 PART 2 (数据输出) 两部分进行输出：

---

## PART 1: 舆情分析报告（供决策参考）

### 一、今日舆情态势总结
简要概述今日全球舆情对中国出入境管理和边境安全的影响态势：

* **国际冲突与安全形势**: [分析主要冲突区域对人口非法流动、难民外溢的潜在影响]
* **重大外交与政策变动**: [大国签证政策、双边互免协定、或针对华人的出入境政策调整]
* **全球经济与人员流动**: [经济波动引起的劳动力移民倾向、高新人才流动趋势等]
* **移民管理专业领域**: [各国边境管控新技术、反偷渡行动、遣返政策等最新动态]
* **社会热点与涉外舆论**: [涉及国门形象、外籍人员在华管理、种族/身份政治等议题]

### 二、关键热点 TOP5
从移民管理警察工作视角出发，筛选最具价值的5条新闻并排序。

1. [新闻标题] —— 【研判理由】: [用一句话说明该新闻对中国移民管理工作的直接或间接影响]
2. ...（以此类推至第5条）

### 三、专业风险研判与预警建议
基于今日舆情，从专业角度分析以下风险点：

* **非法出入境风险**：是否出现特定地区人员偷渡、骗办签证、逾期滞留的新趋势？
* **边境维稳风险**：周边国家动荡是否可能导致边境压力增大或跨境犯罪上升？
* **涉外管理舆论风险**：是否有涉及出入境执法、外籍人员服务管理的负面舆情苗头？
* **口岸公共安全风险**：是否存在流行病输入、违禁品走私等突发安全威胁？

**【应对建议】** (请从情报研判角度提出2-3条具体、皇岗边检站职权范围内可操作的管理对策)

---

## PART 2: 结构化数据（供系统解析，严禁省略）

请输出标准的 JSON 代码块。注意：category_news 必须包含你在分析过程中分类的所有新闻标题，严禁漏掉任何一条已处理的新闻。

```json
{{
  "news_data": {{
    "category_news": {{
      "international_conflict": [
        {{"title": "新闻标题1"}},
        {{"title": "新闻标题2"}}
      ],
      "international_relations": [
        {{"title": "新闻标题3"}}
      ],
      "economy_tech": [],
      "immigration_border": [
        {{"title": "新闻标题4"}}
      ],
      "society_culture": []
    }},
    "top_5_news": [
      {{"rank": 1, "title": "新闻标题1"}},
      {{"rank": 2, "title": "新闻标题2"}},
      {{"rank": 3, "title": "新闻标题3"}},
      {{"rank": 4, "title": "新闻标题4"}},
      {{"rank": 5, "title": "新闻标题5"}}
    ]
  }}
}}
```

**输出约束：**
1. **全量归档**：category_news 必须包含所有提供的新闻中被你判定为有参考价值的标题
2. **严禁省略**：始终输出完整的 JSON 结构，不允许使用 `...` 或 `(此处略)`
3. **字段精简**：JSON 中绝对不可以出现 url 字段，仅保留 title
4. **格式一致**：title 必须与输入列表原始文字完全匹配
5. **代码块格式**：必须使用 ```json 和 ``` 包裹 JSON 数据"""

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
            {'id': 'gemini-2.5-pro', 'name': 'Gemini 2.5 Pro'},
            {'id': 'gemini-2.0-flash', 'name': 'Gemini 2.0 Flash'},
            {'id': 'gemini-2.0-flash-lite', 'name': 'Gemini 2.0 Flash Lite'},
            {'id': 'gemini-1.5-pro', 'name': 'Gemini 1.5 Pro'},
            {'id': 'gemini-1.5-flash', 'name': 'Gemini 1.5 Flash'},
        ]
    },
    'aimlapi': {
        'name': 'AIML API',
        'api_url': 'https://api.aimlapi.com/v1/chat/completions',
        'models': [
            {'id': 'google/gemini-3-flash-preview', 'name': 'Gemini 3 Flash Preview'},
            {'id': 'gpt-4o', 'name': 'GPT-4o'},
            {'id': 'gpt-4o-mini', 'name': 'GPT-4o Mini'},
            {'id': 'claude-3-5-sonnet', 'name': 'Claude 3.5 Sonnet'},
            {'id': 'deepseek-chat', 'name': 'DeepSeek Chat'},
        ]
    },
    'poixe': {
        'name': 'Poixe',
        'api_url': 'https://api.poixe.com/v1/chat/completions',
        'models': [
            {'id': 'gpt-3.5-turbo-0125:free', 'name': 'GPT-3.5 Turbo (免费)'},
            {'id': 'gpt-5.2', 'name': 'GPT-5.2'},
            {'id': 'claude-opus-4-20250514', 'name': 'Claude Opus 4'},
            {'id': 'gemini-2.5-pro', 'name': 'Gemini 2.5 Pro'},
            {'id': 'deepseek-r1', 'name': 'DeepSeek R1'},
            {'id': 'gpt-4o', 'name': 'GPT-4o'},
            {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo'},
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


# 默认翻译提示词
DEFAULT_TRANSLATION_PROMPT = "翻译下面的内容为中文，不需要任何解释：\n{text}"


def get_translation_config() -> Dict[str, str]:
    """获取翻译 LLM 配置"""
    settings = load_settings()
    trans_config = settings.get('translation', {})

    # 获取当前选择的提供商
    provider = trans_config.get('provider', 'siliconflow')
    model = trans_config.get('model', 'Pro/Qwen/Qwen2.5-7B-Instruct')

    # 获取该提供商的配置
    providers_config = trans_config.get('providers', {})
    provider_config = providers_config.get(provider, {})

    # 获取 API Key 和 URL
    api_key = provider_config.get('api_key', '')
    api_url = provider_config.get('api_url', '')

    # 如果翻译没有配置，回退到LLM配置
    if not api_key:
        llm_config = get_llm_config()
        api_key = llm_config.get('api_key', '')

    if not api_url:
        api_url = API_PROVIDERS.get(provider, {}).get('api_url', '')

    return {
        'provider': provider,
        'api_key': api_key,
        'api_url': api_url,
        'model': model
    }


def get_translation_prompt() -> str:
    """获取翻译提示词（自定义或默认）"""
    settings = load_settings()
    custom_prompt = settings.get('translation', {}).get('custom_prompt', '')
    if custom_prompt and custom_prompt.strip():
        return custom_prompt.strip()
    return DEFAULT_TRANSLATION_PROMPT


def set_translation_prompt(prompt: str) -> bool:
    """设置自定义翻译提示词"""
    return set_setting('translation.custom_prompt', prompt)


def get_default_translation_prompt() -> str:
    """获取默认翻译提示词"""
    return DEFAULT_TRANSLATION_PROMPT


def get_translation_provider_api_key(provider: str) -> str:
    """获取指定提供商的翻译 API Key"""
    settings = load_settings()
    trans_config = settings.get('translation', {})
    providers_config = trans_config.get('providers', {})
    provider_config = providers_config.get(provider, {})
    return provider_config.get('api_key', '')
