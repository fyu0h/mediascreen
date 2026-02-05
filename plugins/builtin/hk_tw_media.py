# -*- coding: utf-8 -*-
"""
港澳台媒体插件
包含：大公报、香港中通社、明报、南华早报等
"""

from typing import List, Dict, Any
from plugins.base import BasePlugin


class HKTWMediaPlugin(BasePlugin):
    """港澳台媒体插件"""

    plugin_id = "hk_tw_media"
    plugin_name = "港澳台媒体"
    plugin_description = "香港、台湾主要媒体：大公报、香港中通社、明报、南华早报、香港自由新闻"
    plugin_version = "1.0.0"

    def get_sites(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "hk_takungpao",
                "name": "香港大公报",
                "url": "http://www.takungpao.com.hk/",
                "domain": "takungpao.com.hk",
                "country_code": "HK",
                "coords": [114.1694, 22.3193],
                "fetch_method": "special",
                "parser": "takungpao",
                "sitemap_url": None,
                "description": "香港大公报（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "hk_hkcna",
                "name": "香港中通社",
                "url": "https://www.hkcna.hk/",
                "domain": "hkcna.hk",
                "country_code": "HK",
                "coords": [114.1694, 22.3193],
                "fetch_method": "special",
                "parser": "hkcna",
                "sitemap_url": None,
                "description": "香港中国通讯社（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "hk_mingpao",
                "name": "明报",
                "url": "https://news.mingpao.com/",
                "domain": "mingpao.com",
                "country_code": "HK",
                "coords": [114.1694, 22.3193],
                "fetch_method": "special",
                "parser": "mingpao",
                "sitemap_url": None,
                "description": "香港明报新闻网（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "hk_scmp",
                "name": "南华早报",
                "url": "https://www.scmp.com/",
                "domain": "scmp.com",
                "country_code": "HK",
                "coords": [114.1694, 22.3193],
                "fetch_method": "special",
                "parser": "scmp",
                "sitemap_url": "https://www.scmp.com/sitemap.xml",
                "description": "南华早报（使用专用解析器 + Sitemap）",
                "enabled_by_default": True
            },
            {
                "id": "hk_hkfp",
                "name": "香港自由新闻 (HKFP)",
                "url": "https://hongkongfp.com/",
                "domain": "hongkongfp.com",
                "country_code": "HK",
                "coords": [114.1694, 22.3193],
                "fetch_method": "scheduler",
                "parser": None,
                "sitemap_url": None,
                "description": "Hong Kong Free Press（RSS定时更新）",
                "enabled_by_default": True
            }
        ]
