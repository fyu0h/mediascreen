# -*- coding: utf-8 -*-
"""
政府与移民局官网插件
包含：美国国务院、美国移民局、澳大利亚移民局、韩国移民局、荷兰移民局
"""

from typing import List, Dict, Any
from plugins.base import BasePlugin


class GovernmentImmigrationPlugin(BasePlugin):
    """政府与移民局官网插件"""

    plugin_id = "government_immigration"
    plugin_name = "政府与移民局"
    plugin_description = "各国政府新闻及移民局官方信息源"
    plugin_version = "1.0.0"

    def get_sites(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "us_state",
                "name": "美国国务院",
                "url": "https://www.state.gov/press-releases/",
                "domain": "state.gov",
                "country_code": "US",
                "coords": [-77.0369, 38.9072],
                "fetch_method": "special",
                "parser": "us_state",
                "sitemap_url": "https://www.state.gov/sitemap.xml",
                "description": "美国国务院新闻发布（Sitemap + 专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "us_uscis",
                "name": "美国移民局",
                "url": "https://www.uscis.gov/newsroom/all-news",
                "domain": "uscis.gov",
                "country_code": "US",
                "coords": [-77.0369, 38.9072],
                "fetch_method": "special",
                "parser": "uscis",
                "sitemap_url": None,
                "description": "美国公民及移民服务局新闻（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "au_homeaffairs",
                "name": "澳大利亚移民局",
                "url": "https://www.homeaffairs.gov.au/news-media/archive",
                "domain": "homeaffairs.gov.au",
                "country_code": "AU",
                "coords": [149.1300, -35.2809],
                "fetch_method": "special",
                "parser": "au_homeaffairs",
                "sitemap_url": None,
                "description": "澳大利亚内政部新闻（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "kr_immigration",
                "name": "韩国移民局",
                "url": "http://www.immigration.go.kr/immigration/3341/subview.do",
                "domain": "immigration.go.kr",
                "country_code": "KR",
                "coords": [126.9780, 37.5665],
                "fetch_method": "special",
                "parser": "kr_immigration",
                "sitemap_url": None,
                "description": "韩国出入境管理局新闻（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "nl_ind",
                "name": "荷兰移民局",
                "url": "https://ind.nl/nl/nieuws",
                "domain": "ind.nl",
                "country_code": "NL",
                "coords": [4.9041, 52.3676],
                "fetch_method": "special",
                "parser": "nl_ind",
                "sitemap_url": None,
                "description": "荷兰移民归化局新闻（使用专用解析器）",
                "enabled_by_default": True
            }
        ]
