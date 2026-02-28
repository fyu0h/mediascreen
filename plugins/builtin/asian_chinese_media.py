# -*- coding: utf-8 -*-
"""
亚洲中文媒体插件
包含：纽约时报中文网、联合早报、星洲日报、共同社中文、NHK中文等
"""

from typing import List, Dict, Any
from plugins.base import BasePlugin


class AsianChineseMediaPlugin(BasePlugin):
    """亚洲中文媒体插件"""

    plugin_id = "asian_chinese_media"
    plugin_name = "亚洲中文媒体"
    plugin_description = "亚洲及海外中文媒体：联合早报、星洲日报、共同社、财联社等"
    plugin_version = "1.0.0"

    def get_sites(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "cn_nytimes",
                "name": "纽约时报中文网",
                "url": "https://cn.nytimes.com/",
                "domain": "cn.nytimes.com",
                "country_code": "US",
                "coords": [-73.9857, 40.7484],
                "fetch_method": "special",
                "parser": "nytimes",
                "sitemap_url": None,
                "description": "纽约时报中文网（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "sg_zaobao",
                "name": "联合早报",
                "url": "https://www.zaobao.com.sg/",
                "domain": "zaobao.com.sg",
                "country_code": "SG",
                "coords": [103.8198, 1.3521],
                "fetch_method": "special",
                "parser": "zaobao",
                "sitemap_url": None,
                "description": "新加坡联合早报（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "my_sinchew",
                "name": "星洲日报",
                "url": "https://www.sinchew.com.my/",
                "domain": "sinchew.com.my",
                "country_code": "MY",
                "coords": [101.6869, 3.1390],
                "fetch_method": "special",
                "parser": "sinchew",
                "sitemap_url": None,
                "description": "马来西亚星洲日报（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "jp_kyodo_cn",
                "name": "共同社中文",
                "url": "https://tchina.kyodonews.net/",
                "domain": "tchina.kyodonews.net",
                "country_code": "JP",
                "coords": [139.6917, 35.6895],
                "fetch_method": "special",
                "parser": "kyodo_cn",
                "sitemap_url": None,
                "description": "日本共同社中文网（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "jp_nhk_cn",
                "name": "NHK新闻",
                "url": "https://news.web.nhk/newsweb",
                "domain": "news.web.nhk",
                "country_code": "JP",
                "coords": [139.6917, 35.6895],
                "fetch_method": "special",
                "parser": "nhk_cn",
                "sitemap_url": None,
                "description": "NHK新闻速报（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "cn_cls",
                "name": "财联社",
                "url": "https://www.cls.cn/",
                "domain": "cls.cn",
                "country_code": "CN",
                "coords": [121.4737, 31.2304],
                "fetch_method": "special",
                "parser": "cls",
                "sitemap_url": None,
                "description": "财联社（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "us_sinovision",
                "name": "美国中文网",
                "url": "https://www.sinovision.net/",
                "domain": "sinovision.net",
                "country_code": "US",
                "coords": [-73.9857, 40.7484],
                "fetch_method": "special",
                "parser": "sinovision",
                "sitemap_url": None,
                "description": "美国中文网（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "haiwaiwang",
                "name": "海外家园网",
                "url": "https://haiwaiwang.org/",
                "domain": "haiwaiwang.org",
                "country_code": "US",
                "coords": [-77.0369, 38.9072],
                "fetch_method": "scheduler",
                "parser": None,
                "sitemap_url": None,
                "description": "海外家园网（RSS定时更新）",
                "enabled_by_default": True
            },
            {
                "id": "kz_inform",
                "name": "哈萨克斯坦国际通讯社",
                "url": "https://cn.inform.kz/",
                "domain": "cn.inform.kz",
                "country_code": "KZ",
                "coords": [71.4491, 51.1801],
                "fetch_method": "special",
                "parser": "inform_kz",
                "sitemap_url": None,
                "description": "哈萨克斯坦国际通讯社中文版（使用专用解析器）",
                "enabled_by_default": True
            },
            {
                "id": "kr_seoul_eco",
                "name": "首尔经济日报",
                "url": "https://money.udn.com/search/tagging/1001/%E9%A6%96%E7%88%BE",
                "domain": "money.udn.com",
                "country_code": "KR",
                "coords": [126.9780, 37.5665],
                "fetch_method": "special",
                "parser": "udn_seoul",
                "sitemap_url": None,
                "description": "联合新闻网首尔经济日报专题（使用专用解析器）",
                "enabled_by_default": True
            }
        ]
