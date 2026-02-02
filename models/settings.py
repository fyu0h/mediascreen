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
        'provider': 'siliconflow',  # siliconflow / deepseek / openai
        'api_key': '',
        'api_url': 'https://api.siliconflow.cn/v1/chat/completions',
        'model': 'deepseek-ai/DeepSeek-V3'
    },
    'crawler': {
        'timeout': 30,
        'max_articles': 500,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
}

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
    config = settings.get('llm', {})

    # 优先使用环境变量
    from config import Config
    api_key = config.get('api_key') or Config.DEEPSEEK_API_KEY
    api_url = config.get('api_url') or 'https://api.siliconflow.cn/v1/chat/completions'

    return {
        'provider': config.get('provider', 'siliconflow'),
        'api_key': api_key,
        'api_url': api_url,
        'model': config.get('model', 'deepseek-ai/DeepSeek-V3')
    }


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
