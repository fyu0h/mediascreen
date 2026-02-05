# -*- coding: utf-8 -*-
"""
国际主流媒体插件
包含：BBC、路透社、美联社、福克斯新闻、泰晤士报、法新社等
"""

from typing import List, Dict, Any
from plugins.base import BasePlugin


class InternationalMediaPlugin(BasePlugin):
    """国际主流媒体插件"""

    plugin_id = "international_media"
    plugin_name = "国际主流媒体"
    plugin_description = "全球主流新闻机构：BBC、路透社、美联社、福克斯新闻、泰晤士报、法新社等"
    plugin_version = "1.0.0"

    def get_sites(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "us_ap",
                "name": "美联社 (AP News)",
                "url": "https://apnews.com/",
                "domain": "apnews.com",
                "country_code": "US",
                "coords": [-77.0369, 38.9072],
                "fetch_method": "scheduler",
                "parser": "apnews",
                "sitemap_url": None,
                "description": "美联社官方新闻网站（RSS定时更新 + 专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "gb_reuters",
                "name": "路透社",
                "url": "https://www.reuters.com/",
                "domain": "reuters.com",
                "country_code": "GB",
                "coords": [-0.1276, 51.5074],
                "fetch_method": "scheduler",
                "sitemap_url": None,
                "description": "路透社新闻网（Google News RSS定时更新）",
                "enabled_by_default": True
            },
            {
                "id": "gb_bbc",
                "name": "BBC News",
                "url": "https://www.bbc.com/news",
                "domain": "bbc.com",
                "country_code": "GB",
                "coords": [-0.1276, 51.5074],
                "fetch_method": "special",
                "parser": "bbc",
                "sitemap_url": "https://www.bbc.com/sitemaps/https-sitemap-com-news-1.xml",
                "description": "英国广播公司（Sitemap + 专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "us_fox",
                "name": "福克斯新闻",
                "url": "https://www.foxnews.com/",
                "domain": "foxnews.com",
                "country_code": "US",
                "coords": [-73.9857, 40.7484],
                "fetch_method": "special",
                "parser": "foxnews",
                "sitemap_url": "https://www.foxnews.com/sitemap.xml",
                "description": "福克斯新闻（Sitemap + 专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "gb_times",
                "name": "泰晤士报",
                "url": "https://www.thetimes.com/",
                "domain": "thetimes.com",
                "country_code": "GB",
                "coords": [-0.1276, 51.5074],
                "fetch_method": "special",
                "parser": "thetimes",
                "sitemap_url": None,
                "description": "英国泰晤士报（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "fr_rfi",
                "name": "法国国际广播电台",
                "url": "https://www.rfi.fr/cn/",
                "domain": "rfi.fr",
                "country_code": "FR",
                "coords": [2.3522, 48.8566],
                "fetch_method": "special",
                "parser": "rfi",
                "sitemap_url": None,
                "description": "法国国际广播电台中文版（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "ua_lb",
                "name": "乌克兰LB新闻",
                "url": "https://lb.ua/",
                "domain": "lb.ua",
                "country_code": "UA",
                "coords": [30.5234, 50.4501],
                "fetch_method": "special",
                "parser": "lb_ua",
                "sitemap_url": None,
                "description": "乌克兰LB新闻网（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "ar_infobae",
                "name": "Infobae",
                "url": "https://www.infobae.com/america/",
                "domain": "infobae.com",
                "country_code": "AR",
                "coords": [-58.3816, -34.6037],
                "fetch_method": "special",
                "parser": "infobae",
                "sitemap_url": None,
                "description": "阿根廷Infobae美洲新闻（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "us_cdt",
                "name": "中国数字时代 (CDT)",
                "url": "https://chinadigitaltimes.net/",
                "domain": "chinadigitaltimes.net",
                "country_code": "US",
                "coords": [-122.2585, 37.8719],
                "fetch_method": "scheduler",
                "parser": None,
                "sitemap_url": None,
                "description": "China Digital Times（RSS定时更新）",
                "enabled_by_default": True
            },
            {
                "id": "us_diplomat",
                "name": "外交官杂志 (The Diplomat)",
                "url": "https://thediplomat.com/",
                "domain": "thediplomat.com",
                "country_code": "US",
                "coords": [-77.0369, 38.9072],
                "fetch_method": "scheduler",
                "parser": None,
                "sitemap_url": None,
                "description": "The Diplomat 亚太时政杂志（RSS定时更新）",
                "enabled_by_default": True
            }
        ]
