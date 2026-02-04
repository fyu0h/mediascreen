# -*- coding: utf-8 -*-
"""
插件基类
所有内置插件都需要继承此基类
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BasePlugin(ABC):
    """插件基类"""

    # 插件元信息（子类必须定义）
    plugin_id: str = ""           # 唯一标识，如 "major_news"
    plugin_name: str = ""         # 显示名称，如 "主流国际媒体"
    plugin_description: str = ""  # 插件描述
    plugin_version: str = "1.0.0" # 版本号

    # 支持的抓取方式
    supported_fetch_methods: List[str] = ["sitemap", "crawler"]

    @abstractmethod
    def get_sites(self) -> List[Dict[str, Any]]:
        """
        返回该插件包含的所有站点配置

        返回格式:
        [
            {
                "id": "major_news_ap",      # 站点唯一ID（插件ID_站点名）
                "name": "美联社",            # 站点名称
                "url": "https://apnews.com", # 站点URL
                "domain": "apnews.com",      # 域名
                "country_code": "US",        # 国家代码
                "coords": [-77.0369, 38.9072], # 坐标 [经度, 纬度]
                "fetch_method": "sitemap",   # 默认抓取方式
                "sitemap_url": "https://apnews.com/sitemap.xml", # Sitemap地址
                "description": "美联社官方网站", # 站点描述
                "enabled_by_default": True   # 是否默认启用
            },
            ...
        ]
        """
        pass

    def get_site_by_id(self, site_id: str) -> Optional[Dict[str, Any]]:
        """根据站点ID获取站点配置"""
        for site in self.get_sites():
            if site.get("id") == site_id:
                return site
        return None

    def get_site_ids(self) -> List[str]:
        """获取所有站点ID列表"""
        return [site.get("id") for site in self.get_sites()]

    def validate(self) -> bool:
        """验证插件配置是否有效"""
        if not self.plugin_id:
            return False
        if not self.plugin_name:
            return False
        sites = self.get_sites()
        if not sites:
            return False
        # 检查每个站点是否有必要字段
        required_fields = ["id", "name", "url", "country_code"]
        for site in sites:
            for field in required_fields:
                if not site.get(field):
                    return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """将插件信息转换为字典"""
        return {
            "id": self.plugin_id,
            "name": self.plugin_name,
            "description": self.plugin_description,
            "version": self.plugin_version,
            "site_count": len(self.get_sites()),
            "supported_fetch_methods": self.supported_fetch_methods
        }
