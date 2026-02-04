# -*- coding: utf-8 -*-
"""
插件订阅管理模块
管理用户对插件站点的启用/禁用配置和定时更新设置
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from config import Config
from plugins.registry import plugin_registry


def get_subscriptions_collection():
    """获取插件订阅配置集合"""
    from models.mongo import get_db
    return get_db()[Config.COLLECTION_PLUGIN_SUBSCRIPTIONS]


def ensure_indexes():
    """确保必要的索引存在"""
    collection = get_subscriptions_collection()
    collection.create_index([("plugin_id", 1), ("site_id", 1)], unique=True)


def get_subscription(plugin_id: str, site_id: str) -> Optional[Dict[str, Any]]:
    """
    获取单个站点的订阅配置

    如果数据库中没有记录，返回 None（使用插件默认配置）
    """
    collection = get_subscriptions_collection()
    return collection.find_one({
        "plugin_id": plugin_id,
        "site_id": site_id
    })


def set_subscription(plugin_id: str, site_id: str, enabled: bool,
                     fetch_method_override: Optional[str] = None,
                     auto_update: bool = False,
                     update_interval: int = 300) -> Dict[str, Any]:
    """
    设置站点订阅配置

    参数：
        plugin_id: 插件ID
        site_id: 站点ID
        enabled: 是否启用
        fetch_method_override: 覆盖的抓取方式（None 表示使用默认）
        auto_update: 是否启用定时更新
        update_interval: 更新间隔（秒），默认300秒（5分钟）
    """
    collection = get_subscriptions_collection()
    now = datetime.now()

    doc = {
        "plugin_id": plugin_id,
        "site_id": site_id,
        "enabled": enabled,
        "fetch_method_override": fetch_method_override,
        "auto_update": auto_update,
        "update_interval": update_interval,
        "updated_at": now
    }

    result = collection.find_one_and_update(
        {"plugin_id": plugin_id, "site_id": site_id},
        {
            "$set": doc,
            "$setOnInsert": {"created_at": now}
        },
        upsert=True,
        return_document=True
    )

    return result


def toggle_site(plugin_id: str, site_id: str, enabled: bool) -> Dict[str, Any]:
    """切换站点启用状态"""
    current = get_subscription(plugin_id, site_id)
    fetch_method_override = current.get("fetch_method_override") if current else None
    auto_update = current.get("auto_update", False) if current else False
    update_interval = current.get("update_interval", 300) if current else 300

    return set_subscription(plugin_id, site_id, enabled, fetch_method_override, auto_update, update_interval)


def set_fetch_method(plugin_id: str, site_id: str, method: Optional[str]) -> Dict[str, Any]:
    """
    设置站点的抓取方式

    参数：
        method: 抓取方式 ("sitemap" / "crawler" / "special") 或 None（恢复默认）
    """
    current = get_subscription(plugin_id, site_id)

    if current:
        enabled = current.get("enabled", True)
        auto_update = current.get("auto_update", False)
        update_interval = current.get("update_interval", 300)
    else:
        site = plugin_registry.get_site(plugin_id, site_id)
        enabled = site.get("enabled_by_default", True) if site else True
        auto_update = False
        update_interval = 300

    return set_subscription(plugin_id, site_id, enabled, method, auto_update, update_interval)


def set_auto_update(plugin_id: str, site_id: str, auto_update: bool, update_interval: int = None) -> Dict[str, Any]:
    """
    设置站点的定时更新配置

    参数：
        plugin_id: 插件ID
        site_id: 站点ID
        auto_update: 是否启用定时更新
        update_interval: 更新间隔（秒），None 表示保持原有值
    """
    current = get_subscription(plugin_id, site_id)

    if current:
        enabled = current.get("enabled", True)
        fetch_method_override = current.get("fetch_method_override")
        if update_interval is None:
            update_interval = current.get("update_interval", 300)
    else:
        site = plugin_registry.get_site(plugin_id, site_id)
        enabled = site.get("enabled_by_default", True) if site else True
        fetch_method_override = None
        if update_interval is None:
            update_interval = 300

    return set_subscription(plugin_id, site_id, enabled, fetch_method_override, auto_update, update_interval)


def get_auto_update_sites() -> List[Dict[str, Any]]:
    """
    获取所有启用定时更新的站点

    返回格式与爬虫模块兼容
    """
    auto_update_sites = []

    for plugin in plugin_registry.get_all_plugins():
        for site in plugin.get_sites():
            plugin_id = plugin.plugin_id
            site_id = site.get("id")

            # 检查是否启用
            if not is_site_enabled(plugin_id, site_id):
                continue

            # 检查是否启用定时更新
            sub = get_subscription(plugin_id, site_id)
            if not sub or not sub.get("auto_update", False):
                continue

            fetch_method = get_site_fetch_method(plugin_id, site_id)
            update_interval = sub.get("update_interval", 300)

            auto_update_sites.append({
                "id": site_id,
                "plugin_id": plugin_id,
                "name": site.get("name"),
                "url": site.get("url"),
                "domain": site.get("domain"),
                "country_code": site.get("country_code"),
                "coords": site.get("coords"),
                "fetch_method": fetch_method,
                "parser": site.get("parser"),
                "sitemap_url": site.get("sitemap_url"),
                "auto_update": True,
                "update_interval": update_interval
            })

    return auto_update_sites


def get_all_subscriptions() -> List[Dict[str, Any]]:
    """获取所有订阅配置"""
    collection = get_subscriptions_collection()
    return list(collection.find())


def is_site_enabled(plugin_id: str, site_id: str) -> bool:
    """
    检查站点是否启用

    优先使用数据库配置，否则使用插件默认配置
    """
    sub = get_subscription(plugin_id, site_id)
    if sub is not None:
        return sub.get("enabled", True)

    # 使用插件默认配置
    site = plugin_registry.get_site(plugin_id, site_id)
    if site:
        return site.get("enabled_by_default", True)

    return False


def get_site_fetch_method(plugin_id: str, site_id: str) -> str:
    """
    获取站点的抓取方式

    优先使用用户覆盖配置，否则使用插件默认配置
    """
    sub = get_subscription(plugin_id, site_id)
    if sub and sub.get("fetch_method_override"):
        return sub.get("fetch_method_override")

    # 使用插件默认配置
    site = plugin_registry.get_site(plugin_id, site_id)
    if site:
        return site.get("fetch_method", "crawler")

    return "crawler"


def get_enabled_sites() -> List[Dict[str, Any]]:
    """
    获取所有已启用的站点

    返回格式与爬虫模块兼容
    """
    enabled_sites = []

    # 遍历所有插件的所有站点
    for plugin in plugin_registry.get_all_plugins():
        for site in plugin.get_sites():
            plugin_id = plugin.plugin_id
            site_id = site.get("id")

            # 检查是否启用
            if not is_site_enabled(plugin_id, site_id):
                continue

            # 获取实际的抓取方式
            fetch_method = get_site_fetch_method(plugin_id, site_id)

            # 构建与爬虫兼容的站点格式
            enabled_sites.append({
                "id": site_id,
                "plugin_id": plugin_id,
                "name": site.get("name"),
                "url": site.get("url"),
                "domain": site.get("domain"),
                "country_code": site.get("country_code"),
                "coords": site.get("coords"),
                "fetch_method": fetch_method,
                "parser": site.get("parser"),  # 专用解析器ID
                "sitemap_url": site.get("sitemap_url"),
                "sitemap_supported": fetch_method == "sitemap" and site.get("sitemap_url") is not None
            })

    return enabled_sites


def get_plugins_with_status() -> List[Dict[str, Any]]:
    """
    获取所有插件及其站点的完整状态

    返回格式用于前端展示
    """
    result = []

    for plugin in plugin_registry.get_all_plugins():
        plugin_data = plugin.to_dict()
        sites_with_status = []
        enabled_count = 0

        for site in plugin.get_sites():
            site_id = site.get("id")
            plugin_id = plugin.plugin_id

            # 获取启用状态
            enabled = is_site_enabled(plugin_id, site_id)
            if enabled:
                enabled_count += 1

            # 获取抓取方式
            fetch_method = get_site_fetch_method(plugin_id, site_id)

            # 获取订阅配置（包含定时更新设置）
            sub = get_subscription(plugin_id, site_id)
            has_custom_config = sub is not None
            auto_update = sub.get("auto_update", False) if sub else False
            update_interval = sub.get("update_interval", 300) if sub else 300

            sites_with_status.append({
                "id": site_id,
                "name": site.get("name"),
                "url": site.get("url"),
                "domain": site.get("domain"),
                "country_code": site.get("country_code"),
                "description": site.get("description", ""),
                "fetch_method": fetch_method,
                "default_fetch_method": site.get("fetch_method", "crawler"),
                "parser": site.get("parser"),
                "sitemap_url": site.get("sitemap_url"),
                "enabled": enabled,
                "has_custom_config": has_custom_config,
                "auto_update": auto_update,
                "update_interval": update_interval
            })

        plugin_data["sites"] = sites_with_status
        plugin_data["enabled_count"] = enabled_count
        result.append(plugin_data)

    return result


def init_default_subscriptions():
    """
    初始化默认订阅配置

    仅在集合为空时执行，将所有插件站点的默认状态写入数据库
    """
    collection = get_subscriptions_collection()

    # 如果已有数据，跳过初始化
    if collection.count_documents({}) > 0:
        return 0

    # 确保索引存在
    ensure_indexes()

    count = 0
    now = datetime.now()

    for plugin in plugin_registry.get_all_plugins():
        for site in plugin.get_sites():
            doc = {
                "plugin_id": plugin.plugin_id,
                "site_id": site.get("id"),
                "enabled": site.get("enabled_by_default", True),
                "fetch_method_override": None,
                "created_at": now,
                "updated_at": now
            }
            try:
                collection.insert_one(doc)
                count += 1
            except Exception:
                pass  # 忽略重复插入错误

    return count
