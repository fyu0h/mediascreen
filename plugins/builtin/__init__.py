# -*- coding: utf-8 -*-
"""
内置插件初始化
自动加载所有内置插件
"""

from plugins.builtin.hk_tw_media import HKTWMediaPlugin
from plugins.builtin.asian_chinese_media import AsianChineseMediaPlugin
from plugins.builtin.international_media import InternationalMediaPlugin
from plugins.builtin.government_immigration import GovernmentImmigrationPlugin

# 导出所有插件类
__all__ = [
    'HKTWMediaPlugin',
    'AsianChineseMediaPlugin',
    'InternationalMediaPlugin',
    'GovernmentImmigrationPlugin'
]
