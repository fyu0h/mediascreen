# -*- coding: utf-8 -*-
"""
插件注册表
管理所有已注册的插件
"""

from typing import Dict, List, Any, Optional
from plugins.base import BasePlugin


class PluginRegistry:
    """插件注册表"""

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}

    def register(self, plugin: BasePlugin) -> bool:
        """
        注册插件

        参数：
            plugin: 插件实例
        返回：是否注册成功
        """
        if not plugin.validate():
            print(f"[插件注册] 插件验证失败: {plugin.plugin_id}")
            return False

        if plugin.plugin_id in self._plugins:
            print(f"[插件注册] 插件已存在: {plugin.plugin_id}")
            return False

        self._plugins[plugin.plugin_id] = plugin
        print(f"[插件注册] 成功注册插件: {plugin.plugin_name} ({plugin.plugin_id})")
        return True

    def unregister(self, plugin_id: str) -> bool:
        """注销插件"""
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            return True
        return False

    def get_plugin(self, plugin_id: str) -> Optional[BasePlugin]:
        """获取插件实例"""
        return self._plugins.get(plugin_id)

    def get_all_plugins(self) -> List[BasePlugin]:
        """获取所有插件实例"""
        return list(self._plugins.values())

    def list_plugins(self) -> List[Dict[str, Any]]:
        """列出所有插件的基本信息"""
        return [plugin.to_dict() for plugin in self._plugins.values()]

    def get_all_sites(self) -> List[Dict[str, Any]]:
        """获取所有插件的所有站点"""
        sites = []
        for plugin in self._plugins.values():
            plugin_sites = plugin.get_sites()
            # 为每个站点添加插件信息
            for site in plugin_sites:
                site["plugin_id"] = plugin.plugin_id
                site["plugin_name"] = plugin.plugin_name
                sites.append(site)
        return sites

    def get_site(self, plugin_id: str, site_id: str) -> Optional[Dict[str, Any]]:
        """获取指定插件的指定站点"""
        plugin = self.get_plugin(plugin_id)
        if plugin:
            site = plugin.get_site_by_id(site_id)
            if site:
                site["plugin_id"] = plugin.plugin_id
                site["plugin_name"] = plugin.plugin_name
                return site
        return None


# 全局插件注册表实例
plugin_registry = PluginRegistry()


def register_builtin_plugins():
    """注册所有内置插件"""
    from plugins.builtin import (
        HKTWMediaPlugin,
        AsianChineseMediaPlugin,
        InternationalMediaPlugin,
        GovernmentImmigrationPlugin
    )

    plugin_registry.register(HKTWMediaPlugin())
    plugin_registry.register(AsianChineseMediaPlugin())
    plugin_registry.register(InternationalMediaPlugin())
    plugin_registry.register(GovernmentImmigrationPlugin())

    print(f"[插件系统] 共注册 {len(plugin_registry.get_all_plugins())} 个内置插件")
