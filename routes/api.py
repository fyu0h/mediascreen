# -*- coding: utf-8 -*-
"""
REST API 路由
提供统计数据、文章查询、地图数据、风控监控等接口
"""

import time
from datetime import datetime
from flask import Blueprint, request, jsonify
from typing import Any

from config import Config
from models.logger import (
    log_operation, log_request, log_system, log_error,
    get_logs as get_log_entries, get_log_by_id, clear_logs, get_stats as get_log_stats
)
from models.mongo import (
    get_overview_stats,
    get_source_stats,
    get_trend_stats,
    get_country_stats,
    search_articles,
    get_map_markers,
    get_source_list,
    get_all_sources,
    get_keyword_stats,
    get_risk_alerts,
    get_keyword_trend,
    get_realtime_stats,
    get_all_risk_keywords,
    get_risk_keywords_flat,
    add_risk_keyword,
    update_risk_keyword,
    delete_risk_keyword,
    get_alerts_count_by_day,
    mark_alert_read,
    get_read_alerts
)

api_bp = Blueprint('api', __name__, url_prefix='/api')


def success_response(data: Any) -> tuple:
    """成功响应封装"""
    return jsonify({'success': True, 'data': data}), 200


def error_response(message: str, code: int = 400) -> tuple:
    """错误响应封装"""
    return jsonify({'success': False, 'error': message}), code


# ==================== 统计接口 ====================

@api_bp.route('/stats/overview', methods=['GET'])
def stats_overview():
    """
    概览统计
    返回：总文章数、源数、国家数、日期范围
    """
    try:
        data = get_overview_stats()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取概览统计失败: {str(e)}', 500)


@api_bp.route('/stats/realtime', methods=['GET'])
def stats_realtime():
    """
    实时统计（大屏展示用）
    返回：今日新增、本周新增、环比变化等
    """
    try:
        data = get_realtime_stats()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取实时统计失败: {str(e)}', 500)


@api_bp.route('/stats/sources', methods=['GET'])
def stats_sources():
    """
    各源文章数量统计（柱状图数据）
    返回：[{source: "源名称", count: 数量}, ...]
    """
    try:
        data = get_source_stats()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取源统计失败: {str(e)}', 500)


@api_bp.route('/stats/trend', methods=['GET'])
def stats_trend():
    """
    时间趋势统计（折线图数据）
    参数：days - 统计天数（默认30）
    返回：[{date: "YYYY-MM-DD", count: 数量}, ...]
    """
    try:
        days = request.args.get('days', 30, type=int)
        # 限制最大天数
        days = min(days, 365)
        data = get_trend_stats(days)
        return success_response(data)
    except Exception as e:
        return error_response(f'获取趋势统计失败: {str(e)}', 500)


@api_bp.route('/stats/countries', methods=['GET'])
def stats_countries():
    """
    按国家统计
    返回：[{country: "国家代码", count: 数量}, ...]
    """
    try:
        data = get_country_stats()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取国家统计失败: {str(e)}', 500)


# ==================== 文章接口 ====================

@api_bp.route('/articles', methods=['GET'])
def articles():
    """
    分页文章列表（支持筛选）
    参数：
        source - 新闻源名称
        keyword - 关键词（标题搜索）
        start_date - 开始日期 (YYYY-MM-DD)
        end_date - 结束日期 (YYYY-MM-DD)
        page - 页码（默认1）
        page_size - 每页数量（默认20，最大100）
    返回：{items: [...], total: 总数, page: 当前页, page_size: 每页数量, total_pages: 总页数}
    """
    try:
        source = request.args.get('source', None)
        keyword = request.args.get('keyword', None)
        start_date = request.args.get('start_date', None)
        end_date = request.args.get('end_date', None)
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', Config.DEFAULT_PAGE_SIZE, type=int)

        # 参数验证
        page = max(1, page)
        page_size = max(1, min(page_size, Config.MAX_PAGE_SIZE))

        data = search_articles(
            source=source,
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size
        )
        return success_response(data)
    except Exception as e:
        return error_response(f'获取文章列表失败: {str(e)}', 500)


# ==================== 地图接口 ====================

@api_bp.route('/map/markers', methods=['GET'])
def map_markers():
    """
    地图标记数据
    返回：[{source: "源名称", coords: [经度, 纬度], country: "国家代码", count: 数量}, ...]
    注意：coords 在数据中是 [经度, 纬度]，前端 Leaflet 需要翻转为 [纬度, 经度]
    """
    try:
        data = get_map_markers()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取地图标记失败: {str(e)}', 500)


# ==================== 新闻源接口 ====================

@api_bp.route('/sources', methods=['GET'])
def sources():
    """
    新闻源名称列表（下拉筛选用）
    返回：["源名称1", "源名称2", ...]
    """
    try:
        data = get_source_list()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取新闻源列表失败: {str(e)}', 500)


@api_bp.route('/sources/detail', methods=['GET'])
def sources_detail():
    """
    新闻源详细信息
    返回：[{name: "源名称", url: "URL", country_code: "国家代码", coords: [经度, 纬度]}, ...]
    """
    try:
        data = get_all_sources()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取新闻源详情失败: {str(e)}', 500)


# ==================== 风控监控接口 ====================

@api_bp.route('/risk/keywords', methods=['GET'])
def risk_keywords_list():
    """
    获取所有风控关键词（包含ID，用于管理）
    返回：{high: [{id, keyword, created_at}, ...], medium: [...], low: [...]}
    """
    try:
        data = get_all_risk_keywords()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取风控关键词失败: {str(e)}', 500)


@api_bp.route('/risk/keywords', methods=['POST'])
def risk_keywords_add():
    """
    添加风控关键词
    请求体：{keyword: "关键词", level: "high/medium/low"}
    """
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        keyword = data.get('keyword', '').strip()
        level = data.get('level', '').strip()

        if not keyword:
            return error_response('关键词不能为空', 400)
        if not level:
            return error_response('风险等级不能为空', 400)

        result = add_risk_keyword(keyword, level)
        return success_response({
            'id': result.get('id'),
            'keyword': result.get('keyword'),
            'level': level
        })
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        return error_response(f'添加关键词失败: {str(e)}', 500)


@api_bp.route('/risk/keywords/<keyword_id>', methods=['PUT'])
def risk_keywords_update(keyword_id: str):
    """
    更新风控关键词
    请求体：{keyword: "新关键词"（可选）, level: "新等级"（可选）}
    """
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        keyword = data.get('keyword')
        level = data.get('level')

        if keyword is not None:
            keyword = keyword.strip()
            if not keyword:
                return error_response('关键词不能为空', 400)

        if level is not None:
            level = level.strip()

        success = update_risk_keyword(keyword_id, keyword, level)
        if success:
            return success_response({'message': '更新成功'})
        else:
            return error_response('未找到该关键词或无需更新', 404)
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        return error_response(f'更新关键词失败: {str(e)}', 500)


@api_bp.route('/risk/keywords/<keyword_id>', methods=['DELETE'])
def risk_keywords_delete(keyword_id: str):
    """
    删除风控关键词
    """
    try:
        success = delete_risk_keyword(keyword_id)
        if success:
            return success_response({'message': '删除成功'})
        else:
            return error_response('未找到该关键词', 404)
    except Exception as e:
        return error_response(f'删除关键词失败: {str(e)}', 500)


@api_bp.route('/risk/alerts', methods=['GET'])
def risk_alerts():
    """
    获取风控告警列表
    参数：
        limit - 返回数量（默认50，最大500）
        date - 指定日期 (YYYY-MM-DD)，可选
        keyword - 筛选关键词，可选
    返回：匹配风控关键词的文章列表
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 500)  # 最大500条
        date_str = request.args.get('date', None)
        filter_keyword = request.args.get('keyword', None)

        # 从数据库获取关键词
        keywords = get_risk_keywords_flat()
        data = get_risk_alerts(keywords, limit, date_str=date_str, filter_keyword=filter_keyword)
        return success_response(data)
    except Exception as e:
        return error_response(f'获取风控告警失败: {str(e)}', 500)


@api_bp.route('/risk/alerts/calendar', methods=['GET'])
def risk_alerts_calendar():
    """
    获取指定月份每天的告警数量（日历视图用）
    参数：
        year - 年份
        month - 月份
    返回：{日期: 数量, ...}
    """
    try:
        import calendar
        from datetime import date

        year = request.args.get('year', date.today().year, type=int)
        month = request.args.get('month', date.today().month, type=int)

        # 从数据库获取关键词
        keywords = get_risk_keywords_flat()
        data = get_alerts_count_by_day(keywords, year, month)
        return success_response(data)
    except Exception as e:
        return error_response(f'获取日历数据失败: {str(e)}', 500)


@api_bp.route('/risk/alerts/read', methods=['POST'])
def risk_alerts_mark_read():
    """
    标记告警为已读
    请求体：{url: "文章URL", reader_name: "阅读者姓名（可选）"}
    """
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        url = data.get('url', '').strip()
        reader_name = data.get('reader_name', '').strip()

        if not url:
            return error_response('文章URL不能为空', 400)

        success = mark_alert_read(url, reader_name if reader_name else None)

        if success:
            return success_response({
                'message': '已标记为已读',
                'url': url,
                'reader_name': reader_name
            })
        else:
            return error_response('标记已读失败', 500)

    except Exception as e:
        return error_response(f'标记已读失败: {str(e)}', 500)


@api_bp.route('/risk/stats', methods=['GET'])
def risk_stats():
    """
    获取风控关键词统计
    参数：days - 统计天数（默认7）
    返回：各关键词匹配数量（按风险等级分组）
    """
    try:
        days = request.args.get('days', 7, type=int)
        days = min(days, 30)

        # 从数据库获取关键词
        keywords_by_level = get_risk_keywords_flat()

        result = {}
        for level, keywords in keywords_by_level.items():
            if keywords:
                stats = get_keyword_stats(keywords, days)
                result[level] = stats
            else:
                result[level] = []

        # 计算各等级总数
        summary = {
            'high_total': sum(item['count'] for item in result.get('high', [])),
            'medium_total': sum(item['count'] for item in result.get('medium', [])),
            'low_total': sum(item['count'] for item in result.get('low', []))
        }

        return success_response({
            'stats': result,
            'summary': summary
        })
    except Exception as e:
        return error_response(f'获取风控统计失败: {str(e)}', 500)


@api_bp.route('/risk/trend', methods=['GET'])
def risk_trend():
    """
    获取风控关键词趋势
    参数：keyword - 关键词, days - 统计天数（默认7）
    返回：该关键词的时间趋势
    """
    try:
        keyword = request.args.get('keyword', '')
        days = request.args.get('days', 7, type=int)

        if not keyword:
            return error_response('关键词不能为空', 400)

        days = min(days, 30)
        data = get_keyword_trend(keyword, days)
        return success_response(data)
    except Exception as e:
        return error_response(f'获取关键词趋势失败: {str(e)}', 500)


# ==================== 订阅管理接口（已废弃，使用插件管理替代） ====================

from models.sites import (
    get_all_sites,
    get_site,
    add_site,
    update_site,
    delete_site,
    recheck_sitemap,
    check_sitemap,
    COUNTRY_COORDS
)


@api_bp.route('/sites', methods=['GET'])
def sites_list():
    """
    获取所有订阅站点（兼容旧接口）
    注：推荐使用 /api/plugins 和 /api/subscriptions 接口
    """
    try:
        # 优先从插件系统获取已启用的站点
        from models.plugins import get_enabled_sites
        data = get_enabled_sites()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取站点列表失败: {str(e)}', 500)


@api_bp.route('/sites', methods=['POST'])
def sites_add():
    """
    添加新站点（已禁用）
    请使用插件管理功能
    """
    return error_response('手动添加站点功能已禁用，请使用插件管理功能', 400)


@api_bp.route('/sites/<site_id>', methods=['GET'])
def sites_get(site_id: str):
    """获取单个站点信息"""
    try:
        # 先从插件系统查找
        from models.plugins import get_enabled_sites
        for site in get_enabled_sites():
            if site.get('id') == site_id:
                return success_response(site)
        return error_response('站点不存在', 404)
    except Exception as e:
        return error_response(f'获取站点失败: {str(e)}', 500)


@api_bp.route('/sites/<site_id>', methods=['PUT'])
def sites_update(site_id: str):
    """
    更新站点信息（已禁用）
    请使用插件管理功能
    """
    return error_response('请使用插件管理功能修改站点配置', 400)


@api_bp.route('/sites/<site_id>', methods=['DELETE'])
def sites_delete(site_id: str):
    """
    删除站点（已禁用）
    请使用插件管理功能
    """
    return error_response('请使用插件管理功能禁用站点', 400)


@api_bp.route('/sites/<site_id>/recheck', methods=['POST'])
def sites_recheck(site_id: str):
    """重新检测站点的 sitemap 支持（已禁用）"""
    return error_response('此功能已禁用，站点配置由插件预设', 400)


@api_bp.route('/sites/check-url', methods=['POST'])
def sites_check_url():
    """
    检测 URL 的 sitemap 支持（已禁用）
    """
    return error_response('此功能已禁用，站点配置由插件预设', 400)


@api_bp.route('/sites/countries', methods=['GET'])
def sites_countries():
    """获取支持的国家列表"""
    try:
        countries = [
            {'code': code, 'coords': coords}
            for code, coords in COUNTRY_COORDS.items()
        ]
        return success_response(countries)
    except Exception as e:
        return error_response(f'获取国家列表失败: {str(e)}', 500)


@api_bp.route('/sites/batch-import', methods=['POST'])
def sites_batch_import():
    """
    批量导入站点（已禁用）
    """
    return error_response('批量导入功能已禁用，请使用插件管理功能', 400)


@api_bp.route('/sites/batch-check', methods=['POST'])
def sites_batch_check():
    """
    一键检测所有站点的 sitemap 支持（已禁用）
    """
    return error_response('此功能已禁用，站点配置由插件预设', 400)


# ==================== 插件管理接口 ====================

from models.plugins import (
    get_plugins_with_status,
    get_enabled_sites,
    toggle_site,
    set_fetch_method,
    set_auto_update,
    get_auto_update_sites,
    is_site_enabled,
    get_site_fetch_method
)
from plugins.registry import plugin_registry


@api_bp.route('/plugins', methods=['GET'])
def plugins_list():
    """
    获取所有插件及其站点状态
    返回：插件列表，每个插件包含站点列表和启用状态
    """
    try:
        data = get_plugins_with_status()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取插件列表失败: {str(e)}', 500)


@api_bp.route('/plugins/<plugin_id>', methods=['GET'])
def plugins_get(plugin_id: str):
    """获取单个插件详情"""
    try:
        plugin = plugin_registry.get_plugin(plugin_id)
        if not plugin:
            return error_response('插件不存在', 404)

        # 获取完整状态
        plugins_data = get_plugins_with_status()
        for p in plugins_data:
            if p['id'] == plugin_id:
                return success_response(p)

        return error_response('插件不存在', 404)
    except Exception as e:
        return error_response(f'获取插件详情失败: {str(e)}', 500)


@api_bp.route('/plugins/<plugin_id>/sites/<site_id>/toggle', methods=['POST'])
def plugins_toggle_site(plugin_id: str, site_id: str):
    """
    切换站点启用状态
    请求体：{enabled: true/false}
    """
    try:
        data = request.get_json()
        if data is None:
            return error_response('请求体不能为空', 400)

        enabled = data.get('enabled')
        if enabled is None:
            return error_response('缺少 enabled 参数', 400)

        # 验证插件和站点存在
        site = plugin_registry.get_site(plugin_id, site_id)
        if not site:
            return error_response('站点不存在', 404)

        result = toggle_site(plugin_id, site_id, enabled)

        log_operation(
            action=f'{"启用" if enabled else "禁用"}站点: {site.get("name")}',
            details={'plugin_id': plugin_id, 'site_id': site_id, 'enabled': enabled},
            status='success'
        )

        return success_response({
            'plugin_id': plugin_id,
            'site_id': site_id,
            'enabled': enabled,
            'message': f'站点已{"启用" if enabled else "禁用"}'
        })
    except Exception as e:
        return error_response(f'切换站点状态失败: {str(e)}', 500)


@api_bp.route('/plugins/<plugin_id>/sites/<site_id>/method', methods=['PUT'])
def plugins_set_method(plugin_id: str, site_id: str):
    """
    修改站点的抓取方式
    请求体：{method: "sitemap"|"crawler"|"special"|null}
    null 表示恢复默认
    """
    try:
        data = request.get_json()
        if data is None:
            return error_response('请求体不能为空', 400)

        method = data.get('method')
        if method is not None and method not in ['sitemap', 'crawler', 'special']:
            return error_response('无效的抓取方式，只支持 sitemap、crawler 或 special', 400)

        # 验证插件和站点存在
        site = plugin_registry.get_site(plugin_id, site_id)
        if not site:
            return error_response('站点不存在', 404)

        result = set_fetch_method(plugin_id, site_id, method)

        log_operation(
            action=f'修改站点抓取方式: {site.get("name")}',
            details={'plugin_id': plugin_id, 'site_id': site_id, 'method': method or '默认'},
            status='success'
        )

        return success_response({
            'plugin_id': plugin_id,
            'site_id': site_id,
            'method': method or site.get('fetch_method', 'crawler'),
            'message': '抓取方式已更新'
        })
    except Exception as e:
        return error_response(f'修改抓取方式失败: {str(e)}', 500)


@api_bp.route('/plugins/<plugin_id>/sites/<site_id>/auto-update', methods=['PUT'])
def plugins_set_auto_update(plugin_id: str, site_id: str):
    """
    设置站点的定时更新配置
    请求体：{auto_update: true/false, update_interval: 秒数（可选）}
    """
    try:
        data = request.get_json()
        if data is None:
            return error_response('请求体不能为空', 400)

        auto_update = data.get('auto_update')
        if auto_update is None:
            return error_response('缺少 auto_update 参数', 400)

        update_interval = data.get('update_interval')
        if update_interval is not None:
            update_interval = int(update_interval)
            # 最小间隔60秒，最大间隔24小时
            if update_interval < 60:
                update_interval = 60
            elif update_interval > 86400:
                update_interval = 86400

        # 验证插件和站点存在
        site = plugin_registry.get_site(plugin_id, site_id)
        if not site:
            return error_response('站点不存在', 404)

        result = set_auto_update(plugin_id, site_id, auto_update, update_interval)

        log_operation(
            action=f'设置站点定时更新: {site.get("name")}',
            details={
                'plugin_id': plugin_id,
                'site_id': site_id,
                'auto_update': auto_update,
                'update_interval': update_interval or result.get('update_interval')
            },
            status='success'
        )

        return success_response({
            'plugin_id': plugin_id,
            'site_id': site_id,
            'auto_update': auto_update,
            'update_interval': result.get('update_interval', 300),
            'message': f'定时更新已{"启用" if auto_update else "禁用"}'
        })
    except Exception as e:
        return error_response(f'设置定时更新失败: {str(e)}', 500)


@api_bp.route('/plugins/auto-update-sites', methods=['GET'])
def plugins_auto_update_sites():
    """
    获取所有启用定时更新的站点
    """
    try:
        data = get_auto_update_sites()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取定时更新站点失败: {str(e)}', 500)


@api_bp.route('/subscriptions', methods=['GET'])
def subscriptions_list():
    """
    获取所有已启用的站点（用于爬虫和前端展示）
    """
    try:
        data = get_enabled_sites()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取订阅列表失败: {str(e)}', 500)


# ==================== 设置接口 ====================

from models.settings import (
    load_settings,
    save_settings,
    get_llm_config,
    get_deepseek_config,
    get_openai_config,
    get_api_providers,
    mask_api_key,
    API_PROVIDERS
)


@api_bp.route('/settings', methods=['GET'])
def get_settings():
    """
    获取系统设置（API Key 会被遮蔽）
    """
    try:
        settings = load_settings()

        # 处理 LLM 设置
        llm_config = settings.get('llm', {})
        current_provider = llm_config.get('provider', 'siliconflow')
        providers_config = llm_config.get('providers', {})

        # 获取当前提供商的配置
        current_provider_config = providers_config.get(current_provider, {})
        current_api_key = current_provider_config.get('api_key', '')
        current_api_url = current_provider_config.get('api_url', '')

        # 构建返回的 LLM 配置
        llm_response = {
            'provider': current_provider,
            'model': llm_config.get('model', 'deepseek-ai/DeepSeek-V3'),
            'api_url': current_api_url,
            'api_key_set': bool(current_api_key),
            'api_key_masked': mask_api_key(current_api_key) if current_api_key else '',
            # 各提供商的 Key 配置状态
            'providers_status': {}
        }

        # 检查每个提供商的 API Key 配置状态
        for provider_id in API_PROVIDERS.keys():
            provider_cfg = providers_config.get(provider_id, {})
            provider_key = provider_cfg.get('api_key', '')
            llm_response['providers_status'][provider_id] = {
                'api_key_set': bool(provider_key),
                'api_key_masked': mask_api_key(provider_key) if provider_key else '',
                'api_url': provider_cfg.get('api_url', API_PROVIDERS.get(provider_id, {}).get('api_url', ''))
            }

        settings['llm'] = llm_response

        # 添加 API 提供商列表
        settings['providers'] = API_PROVIDERS

        return success_response(settings)
    except Exception as e:
        return error_response(f'获取设置失败: {str(e)}', 500)


@api_bp.route('/settings', methods=['PUT'])
def update_settings():
    """
    更新系统设置
    """
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        current_settings = load_settings()

        # 确保 llm.providers 存在
        if 'llm' not in current_settings:
            current_settings['llm'] = {}
        if 'providers' not in current_settings['llm']:
            current_settings['llm']['providers'] = {}

        # 更新 LLM 设置
        if 'llm' in data:
            llm = data['llm']
            provider = llm.get('provider', current_settings['llm'].get('provider', 'siliconflow')).strip()

            # 更新当前提供商
            current_settings['llm']['provider'] = provider

            # 更新模型
            if 'model' in llm:
                current_settings['llm']['model'] = llm['model'].strip()

            # 确保该提供商的配置存在
            if provider not in current_settings['llm']['providers']:
                current_settings['llm']['providers'][provider] = {
                    'api_key': '',
                    'api_url': API_PROVIDERS.get(provider, {}).get('api_url', '')
                }

            # 更新该提供商的 API URL
            if 'api_url' in llm:
                current_settings['llm']['providers'][provider]['api_url'] = llm['api_url'].strip()

            # 更新该提供商的 API Key（只有提供了新的 key 才更新）
            if 'api_key' in llm and llm['api_key']:
                current_settings['llm']['providers'][provider]['api_key'] = llm['api_key'].strip()

        # 更新爬虫设置
        if 'crawler' in data:
            cr = data['crawler']
            if 'timeout' in cr:
                current_settings['crawler']['timeout'] = int(cr['timeout'])
            if 'max_articles' in cr:
                current_settings['crawler']['max_articles'] = int(cr['max_articles'])

        # 更新值班人员设置
        if 'duty' in data:
            duty = data['duty']
            if 'duty' not in current_settings:
                current_settings['duty'] = {}
            if 'person_name' in duty:
                current_settings['duty']['person_name'] = duty['person_name'].strip()

        if save_settings(current_settings):
            log_operation(
                action='更新系统设置',
                details={'provider': current_settings.get('llm', {}).get('provider')},
                status='success'
            )
            return success_response({'message': '设置已保存'})
        else:
            return error_response('保存设置失败', 500)
    except Exception as e:
        return error_response(f'更新设置失败: {str(e)}', 500)


@api_bp.route('/settings/test-api', methods=['POST'])
def test_api_connection():
    """
    测试 API 连接
    """
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        provider = data.get('provider', 'siliconflow').strip()
        api_url = data.get('api_url', '').strip()
        api_key = data.get('api_key', '').strip()
        model = data.get('model', '').strip()
        use_saved = data.get('use_saved', False)

        # 如果使用已保存的配置
        if use_saved or not api_key:
            from models.settings import get_provider_api_key
            api_key = get_provider_api_key(provider)

        if not api_url:
            api_url = API_PROVIDERS.get(provider, {}).get('api_url', '')

        if not model:
            models = API_PROVIDERS.get(provider, {}).get('models', [])
            model = models[0]['id'] if models else 'deepseek-ai/DeepSeek-V3'

        if not api_url or not api_key:
            return error_response('API URL 和 API Key 不能为空', 400)

        # 确保 URL 格式正确
        if not api_url.endswith('/chat/completions'):
            api_url = api_url.rstrip('/') + '/v1/chat/completions' if '/v1' not in api_url else api_url

        # 测试连接
        import requests as req
        try:
            response = req.post(
                api_url,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': 'Hi'}],
                    'max_tokens': 5
                },
                timeout=15
            )

            if response.status_code == 200:
                return success_response({'message': '连接成功', 'status': 'ok'})
            elif response.status_code == 401:
                return error_response('API Key 无效', 401)
            else:
                error_msg = response.text[:200] if response.text else f'HTTP {response.status_code}'
                return error_response(f'连接失败: {error_msg}', response.status_code)

        except req.exceptions.Timeout:
            return error_response('连接超时', 408)
        except req.exceptions.ConnectionError:
            return error_response('无法连接到 API 服务器', 503)

    except Exception as e:
        return error_response(f'测试失败: {str(e)}', 500)


@api_bp.route('/duty', methods=['GET'])
def get_duty():
    """获取今日值班人员"""
    try:
        settings = load_settings()
        duty = settings.get('duty', {})
        return success_response({
            'leaders': duty.get('leaders', []),
            'officers': duty.get('officers', [])
        })
    except Exception as e:
        return error_response(f'获取值班信息失败: {str(e)}', 500)


@api_bp.route('/duty', methods=['PUT'])
def update_duty():
    """设置今日值班人员"""
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        leaders = data.get('leaders', [])
        officers = data.get('officers', [])

        # 清理空字符串
        leaders = [name.strip() for name in leaders if name and name.strip()]
        officers = [name.strip() for name in officers if name and name.strip()]

        settings = load_settings()
        if 'duty' not in settings:
            settings['duty'] = {}
        settings['duty']['leaders'] = leaders
        settings['duty']['officers'] = officers

        if save_settings(settings):
            return success_response({
                'message': '值班人员已更新',
                'leaders': leaders,
                'officers': officers
            })
        else:
            return error_response('保存失败', 500)
    except Exception as e:
        return error_response(f'设置值班人员失败: {str(e)}', 500)


# ==================== 文章爬取接口 ====================

from models.mongo import save_articles

@api_bp.route('/crawl/update', methods=['POST'])
def crawl_update():
    """
    更新文章 - 多线程并发爬取所有已启用站点的新闻
    返回：爬取结果报表
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        from models.plugins import get_enabled_sites
        from plugins.crawler import get_crawler

        sites = get_enabled_sites()

        results = {
            'total': len(sites),
            'success': 0,
            'failed': 0,
            'total_articles': 0,
            'total_saved': 0,
            'details': []
        }

        if not sites:
            return success_response(results)

        def crawl_single_site(site):
            """爬取单个站点"""
            site_id = site.get('id')
            site_name = site.get('name', '')
            crawler = get_crawler()

            try:
                result = crawler.crawl_site(site, max_articles=100)

                if result['success']:
                    articles = result.get('articles', [])
                    saved_count = save_articles(articles) if articles else 0
                    return {
                        'id': site_id,
                        'name': site_name,
                        'fetched': len(articles),
                        'saved': saved_count,
                        'success': True
                    }
                else:
                    raise ValueError(result.get('error', '爬取失败'))

            except Exception as e:
                return {
                    'id': site_id,
                    'name': site_name,
                    'error': str(e),
                    'success': False
                }

        # 使用线程池并发爬取
        max_workers = min(5, len(sites))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(crawl_single_site, site) for site in sites]

            for future in as_completed(futures):
                detail = future.result()
                results['details'].append(detail)

                if detail['success']:
                    results['success'] += 1
                    results['total_articles'] += detail.get('fetched', 0)
                    results['total_saved'] += detail.get('saved', 0)
                else:
                    results['failed'] += 1

        return success_response(results)
    except Exception as e:
        return error_response(f'更新文章失败: {str(e)}', 500)


@api_bp.route('/crawl/update/stream', methods=['GET'])
def crawl_update_stream():
    """
    更新文章（SSE 流式返回进度）- 多线程并发版本
    返回：Server-Sent Events 流
    """
    from flask import Response
    import json
    import queue
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def generate():
        from models.plugins import get_enabled_sites
        from plugins.crawler import get_crawler

        try:
            sites = get_enabled_sites()
            total = len(sites)

            # 发送初始化事件（包含站点列表）
            sites_info = [{'id': s.get('id'), 'name': s.get('name', '')} for s in sites]
            yield f"data: {json.dumps({'type': 'init', 'total': total, 'sites': sites_info, 'scheduler_sites': []})}\n\n"

            if total == 0:
                yield f"data: {json.dumps({'type': 'complete', 'success_count': 0, 'failed_count': 0, 'total_articles': 0, 'total_saved': 0, 'details': [], 'scheduler_count': 0})}\n\n"
                return

            # 结果队列
            result_queue = queue.Queue()
            completed_count = 0

            def crawl_single_site(site, index):
                """爬取单个站点的工作函数"""
                site_id = site.get('id')
                site_name = site.get('name', '')
                crawler = get_crawler()

                try:
                    result = crawler.crawl_site(site, max_articles=100)

                    if result['success']:
                        articles = result.get('articles', [])
                        article_count = len(articles)
                        saved_count = save_articles(articles) if articles else 0

                        return {
                            'index': index,
                            'site_id': site_id,
                            'site_name': site_name,
                            'success': True,
                            'article_count': article_count,
                            'saved_count': saved_count,
                            'error': None
                        }
                    else:
                        raise ValueError(result.get('error', '爬取失败'))

                except Exception as e:
                    return {
                        'index': index,
                        'site_id': site_id,
                        'site_name': site_name,
                        'success': False,
                        'article_count': 0,
                        'saved_count': 0,
                        'error': str(e)[:100]
                    }

            # 发送开始并发爬取的消息
            yield f"data: {json.dumps({'type': 'progress', 'message': '开始并发爬取...', 'total': total})}\n\n"

            # 使用线程池并发爬取
            max_workers = min(5, total)  # 限制并发数避免阻塞其他请求
            success_count = 0
            failed_count = 0
            total_articles = 0
            total_saved = 0
            details = []

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_site = {
                    executor.submit(crawl_single_site, site, i): site
                    for i, site in enumerate(sites)
                }

                # 收集结果
                for future in as_completed(future_to_site):
                    completed_count += 1
                    result = future.result()

                    if result['success']:
                        success_count += 1
                        total_articles += result['article_count']
                        total_saved += result['saved_count']
                        details.append({
                            'id': result['site_id'],
                            'name': result['site_name'],
                            'fetched': result['article_count'],
                            'saved': result['saved_count'],
                            'success': True
                        })
                        # 发送站点完成事件
                        yield f"data: {json.dumps({'type': 'site_done', 'completed': completed_count, 'total': total, 'site_id': result['site_id'], 'site_name': result['site_name'], 'success': True, 'article_count': result['article_count'], 'saved_count': result['saved_count']})}\n\n"
                    else:
                        failed_count += 1
                        details.append({
                            'id': result['site_id'],
                            'name': result['site_name'],
                            'error': result['error'],
                            'success': False
                        })
                        # 发送站点失败事件
                        yield f"data: {json.dumps({'type': 'site_done', 'completed': completed_count, 'total': total, 'site_id': result['site_id'], 'site_name': result['site_name'], 'success': False, 'error': result['error']})}\n\n"

            # 发送完成事件（包含完整报表）
            yield f"data: {json.dumps({'type': 'complete', 'success_count': success_count, 'failed_count': failed_count, 'total_articles': total_articles, 'total_saved': total_saved, 'details': details, 'scheduler_count': 0})}\n\n"

            # 记录日志
            log_operation(
                action='文章更新完成',
                details={
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'total_articles': total_articles,
                    'total_saved': total_saved,
                    'sites': [d['name'] for d in details if d['success']]
                },
                status='success' if failed_count == 0 else 'warning'
            )

        except Exception as e:
            log_operation(
                action='文章更新失败',
                details={'error': str(e)},
                status='error',
                error=str(e)
            )
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


# ==================== 后台任务爬虫接口（推荐使用） ====================

@api_bp.route('/crawl/start', methods=['POST'])
def crawl_start():
    """
    启动后台爬虫任务
    立即返回 task_id，爬虫在后台线程执行
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from models.tasks import (
        create_task, update_task, register_running_task,
        unregister_task, is_cancelled
    )
    from models.plugins import get_enabled_sites
    from plugins.crawler import get_crawler

    try:
        sites = get_enabled_sites()

        if not sites:
            return success_response({
                'task_id': None,
                'message': '没有启用的站点'
            })

        # 创建任务记录
        task_id = create_task(task_type='crawl', sites=sites)

        def run_crawl_task():
            """后台执行爬虫任务"""
            try:
                update_task(task_id, {
                    'status': 'running',
                    'started_at': datetime.now(),
                    'message': '正在初始化...'
                })

                total = len(sites)
                completed = 0
                success_count = 0
                failed_count = 0
                skipped_count = 0  # 超时跳过的站点数
                total_articles = 0
                total_saved = 0
                sites_status = {}

                def crawl_single_site(site, index):
                    """爬取单个站点"""
                    # 检查是否被取消
                    if is_cancelled(task_id):
                        return None

                    site_id = site.get('id')
                    site_name = site.get('name', '')

                    # 更新当前正在爬取的站点
                    update_task(task_id, {
                        'current_site': site_name,
                        'message': f'正在获取: {site_name} ({index + 1}/{total})'
                    })

                    try:
                        crawler = get_crawler()
                        result = crawler.crawl_site(site, max_articles=100)

                        if result['success']:
                            articles = result.get('articles', [])
                            saved_count = save_articles(articles) if articles else 0
                            return {
                                'site_id': site_id,
                                'site_name': site_name,
                                'success': True,
                                'skipped': False,
                                'articles': len(articles),
                                'saved': saved_count,
                                'error': None
                            }
                        else:
                            # 区分超时跳过和真正失败
                            is_skipped = result.get('skipped', False)
                            return {
                                'site_id': site_id,
                                'site_name': site_name,
                                'success': False,
                                'skipped': is_skipped,
                                'articles': 0,
                                'saved': 0,
                                'error': result.get('error', '爬取失败')[:100]
                            }
                    except Exception as e:
                        error_msg = str(e)
                        is_timeout = 'timeout' in error_msg.lower()
                        return {
                            'site_id': site_id,
                            'site_name': site_name,
                            'success': False,
                            'skipped': is_timeout,  # 超时视为跳过
                            'articles': 0,
                            'saved': 0,
                            'error': ('超时跳过' if is_timeout else error_msg)[:100]
                        }

                # 并发爬取（限制并发数避免阻塞其他请求）
                max_workers = min(5, total)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_site = {
                        executor.submit(crawl_single_site, site, i): site
                        for i, site in enumerate(sites)
                    }

                    for future in as_completed(future_to_site):
                        # 检查取消
                        if is_cancelled(task_id):
                            executor.shutdown(wait=False, cancel_futures=True)
                            break

                        result = future.result()
                        if result is None:  # 被取消
                            continue

                        completed += 1
                        site_id = result['site_id']
                        sites_status[site_id] = result

                        if result['success']:
                            success_count += 1
                            total_articles += result['articles']
                            total_saved += result['saved']
                        elif result.get('skipped', False):
                            skipped_count += 1  # 超时跳过单独计数
                        else:
                            failed_count += 1

                        # 更新进度
                        progress = int((completed / total) * 100)
                        update_task(task_id, {
                            'progress': progress,
                            'completed_sites': completed,
                            'success_count': success_count,
                            'failed_count': failed_count,
                            'skipped_count': skipped_count,
                            'total_articles': total_articles,
                            'total_saved': total_saved,
                            'current_site': result['site_name'],
                            'sites_status': sites_status,
                            'message': f'已完成 {completed}/{total}'
                        })

                # 最终状态
                if is_cancelled(task_id):
                    # 已经在 cancel_task 中更新了状态
                    pass
                else:
                    # 构建完成消息
                    msg_parts = [f'{success_count}成功']
                    if skipped_count > 0:
                        msg_parts.append(f'{skipped_count}跳过')
                    if failed_count > 0:
                        msg_parts.append(f'{failed_count}失败')
                    msg_parts.append(f'保存{total_saved}篇')

                    update_task(task_id, {
                        'status': 'completed',
                        'progress': 100,
                        'skipped_count': skipped_count,
                        'finished_at': datetime.now(),
                        'message': f'完成: {", ".join(msg_parts)}'
                    })

                    # 记录日志
                    log_operation(
                        action='文章更新完成',
                        details={
                            'task_id': task_id,
                            'success_count': success_count,
                            'failed_count': failed_count,
                            'total_articles': total_articles,
                            'total_saved': total_saved
                        },
                        status='success' if failed_count == 0 else 'warning'
                    )

            except Exception as e:
                update_task(task_id, {
                    'status': 'failed',
                    'finished_at': datetime.now(),
                    'error': str(e)[:200],
                    'message': f'任务失败: {str(e)[:50]}'
                })
                log_operation(
                    action='文章更新失败',
                    details={'task_id': task_id, 'error': str(e)},
                    status='error'
                )
            finally:
                unregister_task(task_id)

        # 启动后台线程
        thread = threading.Thread(target=run_crawl_task, daemon=True)
        register_running_task(task_id, thread)
        thread.start()

        return success_response({
            'task_id': task_id,
            'total_sites': len(sites),
            'message': '任务已启动'
        })

    except Exception as e:
        return error_response(f'启动任务失败: {str(e)}', 500)


@api_bp.route('/crawl/status', methods=['GET'])
def crawl_status():
    """
    查询爬虫任务状态
    参数: task_id
    """
    from models.tasks import get_task_status

    task_id = request.args.get('task_id')
    if not task_id:
        return error_response('缺少 task_id 参数', 400)

    status = get_task_status(task_id)
    if not status:
        return error_response('任务不存在', 404)

    return success_response(status)


@api_bp.route('/crawl/cancel', methods=['POST'])
def crawl_cancel():
    """
    取消爬虫任务
    请求体: { task_id: "xxx" }
    """
    from models.tasks import cancel_task

    data = request.get_json() or {}
    task_id = data.get('task_id')

    if not task_id:
        return error_response('缺少 task_id 参数', 400)

    success = cancel_task(task_id)
    if success:
        log_operation(
            action='取消爬虫任务',
            details={'task_id': task_id},
            status='info'
        )
        return success_response({'message': '任务已取消'})
    else:
        return error_response('无法取消任务（可能已完成或不存在）', 400)


@api_bp.route('/crawl/history', methods=['GET'])
def crawl_history():
    """获取最近的爬虫任务历史"""
    from models.tasks import get_recent_tasks

    limit = int(request.args.get('limit', 10))
    tasks = get_recent_tasks(limit=min(limit, 50))

    # 格式化时间
    for task in tasks:
        if task.get('created_at'):
            task['created_at'] = task['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        if task.get('started_at'):
            task['started_at'] = task['started_at'].strftime('%Y-%m-%d %H:%M:%S')
        if task.get('finished_at'):
            task['finished_at'] = task['finished_at'].strftime('%Y-%m-%d %H:%M:%S')

    return success_response(tasks)


# ==================== 调度器接口 ====================

@api_bp.route('/scheduler/status', methods=['GET'])
def scheduler_status():
    """获取调度器状态"""
    try:
        from plugins.scheduler import get_rss_scheduler
        scheduler = get_rss_scheduler()
        return success_response(scheduler.get_status())
    except Exception as e:
        return error_response(f'获取调度器状态失败: {str(e)}', 500)


@api_bp.route('/scheduler/trigger', methods=['POST'])
def scheduler_trigger():
    """手动触发一次更新"""
    try:
        from plugins.scheduler import get_rss_scheduler
        scheduler = get_rss_scheduler()
        scheduler.trigger_update()
        return success_response({'message': '已触发更新'})
    except Exception as e:
        return error_response(f'触发更新失败: {str(e)}', 500)


# ==================== 日志接口 ====================

@api_bp.route('/logs', methods=['GET'])
def logs_list():
    """
    获取后台日志列表
    参数：
        type - 日志类型 (operation/request/system)
        status - 状态 (info/success/warning/error)
        limit - 返回数量（默认100，最大500）
        offset - 偏移量（默认0）
        search - 搜索关键词
    """
    try:
        log_type = request.args.get('type', None)
        status = request.args.get('status', None)
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        search = request.args.get('search', None)

        limit = min(limit, 500)

        data = get_log_entries(
            log_type=log_type,
            status=status,
            limit=limit,
            offset=offset,
            search=search
        )
        return success_response(data)
    except Exception as e:
        return error_response(f'获取日志失败: {str(e)}', 500)


@api_bp.route('/logs/<log_id>', methods=['GET'])
def logs_detail(log_id: str):
    """获取单条日志详情（包含完整的请求/响应数据）"""
    try:
        log = get_log_by_id(log_id)
        if log:
            return success_response(log)
        return error_response('日志不存在', 404)
    except Exception as e:
        return error_response(f'获取日志详情失败: {str(e)}', 500)


@api_bp.route('/logs/stats', methods=['GET'])
def logs_stats():
    """获取日志统计"""
    try:
        data = get_log_stats()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取日志统计失败: {str(e)}', 500)


@api_bp.route('/logs', methods=['DELETE'])
def logs_clear():
    """清空所有日志"""
    try:
        count = clear_logs()
        log_system('清空日志', {'cleared_count': count}, status='success')
        return success_response({'message': f'已清空 {count} 条日志', 'count': count})
    except Exception as e:
        return error_response(f'清空日志失败: {str(e)}', 500)


# ==================== 成果展示接口 ====================

from models.achievements import (
    get_all_achievements,
    get_achievement,
    add_achievement,
    update_achievement,
    delete_achievement,
    fetch_page_title,
    save_uploaded_image,
    delete_image
)


@api_bp.route('/achievements', methods=['GET'])
def achievements_list():
    """获取所有成果展示"""
    try:
        data = get_all_achievements()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取成果列表失败: {str(e)}', 500)


@api_bp.route('/achievements', methods=['POST'])
def achievements_add():
    """
    添加新成果
    支持 multipart/form-data 格式（带图片上传）
    """
    try:
        # 获取表单数据
        url = request.form.get('url', '').strip()
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()

        if not url:
            return error_response('引用链接不能为空', 400)

        # 确保 URL 有协议前缀
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # 如果没有提供标题，从链接抓取
        if not title:
            title = fetch_page_title(url)
            if not title:
                # 如果抓取失败，使用域名作为标题
                from urllib.parse import urlparse
                parsed = urlparse(url)
                title = parsed.netloc or '未命名成果'

        # 处理图片上传
        image_filename = None
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename:
                # 检查文件类型
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
                ext = image_file.filename.rsplit('.', 1)[-1].lower() if '.' in image_file.filename else ''
                if ext not in allowed_extensions:
                    return error_response('不支持的图片格式，请上传 PNG/JPG/GIF/WEBP 格式', 400)

                # 保存图片
                image_data = image_file.read()
                image_filename = save_uploaded_image(image_data, image_file.filename)

        # 添加成果
        achievement = add_achievement(
            title=title,
            url=url,
            image_filename=image_filename,
            description=description or None
        )

        log_operation(
            action=f'添加成果: {title[:30]}',
            details={'url': url, 'has_image': bool(image_filename)},
            status='success'
        )

        return success_response(achievement)

    except Exception as e:
        return error_response(f'添加成果失败: {str(e)}', 500)


@api_bp.route('/achievements/<achievement_id>', methods=['PUT'])
def achievements_update(achievement_id: str):
    """更新成果"""
    try:
        url = request.form.get('url', '').strip() if request.form else None
        title = request.form.get('title', '').strip() if request.form else None
        description = request.form.get('description', '').strip() if request.form else None

        # 处理图片上传
        image_filename = None
        if request.files and 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename:
                # 删除旧图片
                old_achievement = get_achievement(achievement_id)
                if old_achievement and old_achievement.get('image'):
                    delete_image(old_achievement['image'])

                # 保存新图片
                image_data = image_file.read()
                image_filename = save_uploaded_image(image_data, image_file.filename)

        # 更新成果
        achievement = update_achievement(
            achievement_id,
            title=title if title else None,
            url=url if url else None,
            image_filename=image_filename,
            description=description
        )

        if achievement:
            return success_response(achievement)
        return error_response('成果不存在', 404)

    except Exception as e:
        return error_response(f'更新成果失败: {str(e)}', 500)


@api_bp.route('/achievements/<achievement_id>', methods=['DELETE'])
def achievements_delete(achievement_id: str):
    """删除成果"""
    try:
        achievement = get_achievement(achievement_id)
        if delete_achievement(achievement_id):
            log_operation(
                action=f'删除成果: {achievement.get("title", "")[:30] if achievement else achievement_id}',
                details={'achievement_id': achievement_id},
                status='success'
            )
            return success_response({'message': '删除成功'})
        return error_response('成果不存在', 404)
    except Exception as e:
        return error_response(f'删除成果失败: {str(e)}', 500)


@api_bp.route('/achievements/fetch-title', methods=['POST'])
def achievements_fetch_title():
    """
    从URL抓取页面标题
    请求体：{url: "链接地址"}
    """
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        url = data.get('url', '').strip()
        if not url:
            return error_response('URL 不能为空', 400)

        # 确保 URL 有协议前缀
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        title = fetch_page_title(url)

        if title:
            return success_response({'title': title, 'url': url})
        else:
            return error_response('无法获取页面标题', 400)

    except Exception as e:
        return error_response(f'抓取标题失败: {str(e)}', 500)


# ==================== 舆情总结接口 ====================

import requests
import re
import json as json_module
from datetime import datetime, timedelta
from models.settings import get_llm_config, get_summary_prompt, set_summary_prompt, get_default_summary_prompt


def get_summaries_collection():
    """获取AI总结集合"""
    from models.mongo import get_db
    return get_db()[Config.COLLECTION_SUMMARIES]


def extract_json_from_content(content: str) -> dict:
    """从AI返回内容中提取JSON数据块"""
    def clean_json_string(s: str) -> str:
        """清理JSON字符串中的特殊字符"""
        # 替换中文引号为英文引号
        s = s.replace('"', '"').replace('"', '"')
        s = s.replace(''', "'").replace(''', "'")
        # 移除可能的BOM
        s = s.strip('\ufeff')
        return s

    try:
        # 尝试匹配 ```json ... ``` 代码块
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        match = re.search(json_pattern, content)

        if match:
            json_str = clean_json_string(match.group(1).strip())
            try:
                return json_module.loads(json_str)
            except json_module.JSONDecodeError as e:
                print(f"JSON代码块解析失败: {e}")
                # 尝试修复常见问题后重试
                try:
                    # 移除注释
                    json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
                    # 移除尾随逗号
                    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
                    return json_module.loads(json_str)
                except json_module.JSONDecodeError:
                    pass

        # 如果没有代码块或解析失败，尝试直接查找 JSON 对象
        # 先清理内容中的中文引号
        cleaned_content = clean_json_string(content)

        # 寻找包含 news_data 的 JSON
        json_start = cleaned_content.find('"news_data"')

        if json_start != -1:
            # 向前找到 { 开始
            brace_start = cleaned_content.rfind('{', 0, json_start)
            if brace_start != -1:
                # 从这个位置开始，找到匹配的 }
                depth = 0
                end_idx = brace_start
                for i in range(brace_start, len(cleaned_content)):
                    c = cleaned_content[i]
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            end_idx = i + 1
                            break

                if end_idx > brace_start:
                    json_str = cleaned_content[brace_start:end_idx]
                    try:
                        return json_module.loads(json_str)
                    except json_module.JSONDecodeError as e:
                        print(f"JSON对象解析失败: {e}")
                        # 尝试修复后重试
                        try:
                            json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
                            return json_module.loads(json_str)
                        except json_module.JSONDecodeError:
                            pass

        return {}
    except Exception as e:
        print(f"extract_json_from_content 异常: {e}")
        return {}


def _lookup_url_from_db(title: str) -> str:
    """
    从数据库中根据标题查找对应的URL
    """
    if not title:
        return ''

    try:
        from models.mongo import get_articles_collection
        collection = get_articles_collection()

        # 1. 精确匹配
        doc = collection.find_one({'title': title}, {'loc': 1})
        if doc and doc.get('loc'):
            return doc['loc']

        # 2. 正则模糊匹配（处理标题略有差异的情况）
        import re
        # 转义正则特殊字符
        escaped_title = re.escape(title)
        doc = collection.find_one(
            {'title': {'$regex': escaped_title, '$options': 'i'}},
            {'loc': 1}
        )
        if doc and doc.get('loc'):
            return doc['loc']

        # 3. 部分匹配（取标题前30个字符）
        if len(title) > 15:
            prefix = title[:30]
            escaped_prefix = re.escape(prefix)
            doc = collection.find_one(
                {'title': {'$regex': f'^{escaped_prefix}', '$options': 'i'}},
                {'loc': 1}
            )
            if doc and doc.get('loc'):
                return doc['loc']

        return ''
    except Exception as e:
        print(f"数据库查询URL失败: {e}")
        return ''


def _lookup_url_by_title(title: str, title_url_map: dict) -> str:
    """
    根据标题查找对应的URL
    支持模糊匹配（标题可能被AI略微修改）
    如果在 title_url_map 中找不到，会回退到数据库查询
    """
    if not title:
        return ''

    # 清理标题（与存储时的处理一致）
    safe_title = title.replace('.', '。').replace('$', '＄')

    # 1. 精确匹配 title_url_map
    if title_url_map and safe_title in title_url_map:
        return title_url_map[safe_title].get('url', '')

    # 2. 原始标题匹配
    if title_url_map:
        for key, value in title_url_map.items():
            if value.get('original_title') == title:
                return value.get('url', '')

    # 3. 模糊匹配（标题包含关系）
    if title_url_map:
        title_lower = title.lower().strip()
        for key, value in title_url_map.items():
            original = value.get('original_title', key).lower().strip()
            # 检查是否有足够的重叠
            if title_lower in original or original in title_lower:
                return value.get('url', '')
            # 检查前50个字符是否相同（处理标题被截断的情况）
            if len(title_lower) > 20 and len(original) > 20:
                if title_lower[:50] == original[:50]:
                    return value.get('url', '')

    # 4. 回退：从数据库中根据标题查询
    url = _lookup_url_from_db(title)
    if url:
        return url

    return ''


def _correct_structured_refs(structured_refs: dict, title_url_map: dict) -> dict:
    """
    使用 title_url_map 校正 structured_refs 中的URL
    解决AI返回无效URL的问题
    注意：即使没有找到URL，也要保留title
    """
    if not structured_refs:
        return structured_refs

    corrected = {}

    # 处理分类新闻
    category_news = structured_refs.get('category_news', {})
    if isinstance(category_news, dict):
        corrected_categories = {}
        for cat_key, items in category_news.items():
            if isinstance(items, list):
                corrected_items = []
                for item in items:
                    if isinstance(item, dict):
                        title = item.get('title', '')
                        if not title:
                            continue  # 没有标题的跳过
                        # 使用 title_url_map 校正 URL
                        url = _lookup_url_by_title(title, title_url_map) if title_url_map else ''
                        if not url:
                            # 尝试保留原有的有效URL
                            original_url = item.get('url', '')
                            if original_url and original_url not in ['#', '', '链接']:
                                url = original_url
                        # 无论是否有URL，只要有title就保留
                        corrected_items.append({
                            'title': title,
                            'url': url or ''
                        })
                corrected_categories[cat_key] = corrected_items
        corrected['category_news'] = corrected_categories

    # 处理 TOP5 新闻
    top_5 = structured_refs.get('top_5_news', [])
    if isinstance(top_5, list):
        corrected_top5 = []
        for item in top_5:
            if isinstance(item, dict):
                title = item.get('title', '')
                if not title:
                    continue  # 没有标题的跳过
                rank = item.get('rank', 0)
                url = _lookup_url_by_title(title, title_url_map) if title_url_map else ''
                if not url:
                    # 尝试保留原有的有效URL
                    original_url = item.get('url', '')
                    if original_url and original_url not in ['#', '', '链接']:
                        url = original_url
                # 无论是否有URL，只要有title就保留
                corrected_top5.append({
                    'rank': rank,
                    'title': title,
                    'url': url or ''
                })
        corrected['top_5_news'] = corrected_top5

    return corrected


@api_bp.route('/summary/daily', methods=['POST'])
def summary_daily():
    """
    生成当天舆情总结
    使用 LLM 分析当天所有新闻标题
    """
    try:
        # 获取今天的时间范围
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        # 从数据库获取今天的所有文章
        from models.mongo import get_articles_collection
        articles_collection = get_articles_collection()

        # 查询今天的文章
        cursor = articles_collection.find({
            'pub_date': {'$gte': today, '$lt': tomorrow}
        }).sort('pub_date', -1)

        articles = list(cursor)
        article_count = len(articles)

        if article_count == 0:
            return success_response({
                'summary': '今日暂无新闻数据。',
                'hot_news': [],
                'risk_analysis': '暂无数据进行风险分析。',
                'article_count': 0,
                'date': today.strftime('%Y年%m月%d日')
            })

        # 构建新闻列表（包含标题和URL）
        news_items = []
        title_url_map = {}  # 标题 -> {url, source}

        for i, article in enumerate(articles[:200], 1):  # 最多取200条
            source = article.get('source_name', '未知来源')
            title = article.get('title', '')
            url = article.get('loc', '') or article.get('url', '')  # 优先使用loc字段

            if title:
                # 新格式：包含标题和链接
                news_items.append(f"{i}. [{source}] {title}\n   链接: {url}")
                # 保存标题到URL的映射
                # 清理标题中的特殊字符（MongoDB键不能包含.或以$开头）
                safe_title = title.replace('.', '。').replace('$', '＄')
                title_url_map[safe_title] = {
                    'url': url,
                    'source': source,
                    'article_id': str(article.get('_id', '')),
                    'original_title': title  # 保存原始标题用于显示
                }

        news_list_text = '\n'.join(news_items)

        # 获取 LLM 配置
        llm_config = get_llm_config()
        api_key = llm_config.get('api_key')
        api_url = llm_config.get('api_url')
        model = llm_config.get('model')

        if not api_key:
            return error_response('未配置 LLM API Key，请在系统设置中配置', 400)

        # 获取提示词模板并填充变量
        prompt_template = get_summary_prompt()
        # 使用安全的字符串替换，避免花括号冲突
        prompt = prompt_template.replace('{date}', today.strftime('%Y年%m月%d日'))
        prompt = prompt.replace('{count}', str(article_count))
        prompt = prompt.replace('{news_list}', news_list_text)

        # 调用 LLM API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }

        payload = {
            'model': model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.7,
            'max_tokens': 4000  # 增加token限制以容纳JSON
        }

        response = requests.post(api_url, json=payload, headers=headers, timeout=180)

        if response.status_code != 200:
            log_operation(
                action='舆情总结生成失败',
                details={'status_code': response.status_code, 'response': response.text[:500]},
                status='error'
            )
            return error_response(f'LLM API 调用失败: {response.status_code}', 500)

        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')

        if not content:
            return error_response('LLM 返回内容为空', 500)

        # 提取JSON结构化数据（在try块内以防解析失败）
        try:
            news_data = extract_json_from_content(content)
        except Exception as json_err:
            print(f"JSON提取异常: {json_err}")
            news_data = {}

        # 解析文本报告部分
        # 移除JSON代码块后的内容用于文本解析
        text_content = re.sub(r'```json[\s\S]*?```', '', content).strip()
        # 也移除普通代码块
        text_content = re.sub(r'```[\s\S]*?```', '', text_content).strip()

        summary = ''
        hot_news_text = ''
        risk_analysis = ''

        # 尝试多种分割方式
        # 方式1: 使用 ## 分割（Markdown格式）
        if '##' in text_content:
            sections = text_content.split('##')
            for section in sections:
                section = section.strip()
                if '今日舆情' in section or '舆情总结' in section or '态势总结' in section:
                    summary = section.split('\n', 1)[1].strip() if '\n' in section else section
                elif '热点' in section or 'TOP5' in section or 'TOP 5' in section:
                    hot_news_text = section.split('\n', 1)[1].strip() if '\n' in section else section
                elif '风险' in section or '应对建议' in section or '预警' in section:
                    risk_analysis = section.split('\n', 1)[1].strip() if '\n' in section else section

        # 方式2: 使用中文序号分割（一、二、三、）
        if not summary and not hot_news_text:
            # 使用正则匹配中文序号标题
            pattern = r'[一二三四五六七八九十]+[、.．]\s*'
            parts = re.split(pattern, text_content)
            titles = re.findall(pattern + r'[^\n]+', text_content)

            for i, title in enumerate(titles):
                title_text = title.strip()
                part_content = parts[i + 1].strip() if i + 1 < len(parts) else ''

                if '舆情' in title_text or '总结' in title_text or '态势' in title_text:
                    summary = part_content
                elif '热点' in title_text or 'TOP' in title_text:
                    hot_news_text = part_content
                elif '风险' in title_text or '建议' in title_text or '预警' in title_text:
                    risk_analysis = part_content

        # 方式3: 使用 PART 分割
        if not summary and not hot_news_text:
            if 'PART 1' in text_content or 'PART 2' in text_content:
                # 提取 PART 1 内容
                part1_match = re.search(r'PART\s*1[:\s：]*([\s\S]*?)(?=PART\s*2|$)', text_content, re.IGNORECASE)
                if part1_match:
                    part1_content = part1_match.group(1).strip()
                    # 在 PART 1 中再次尝试分割
                    if '一、' in part1_content or '二、' in part1_content:
                        # 递归使用中文序号分割
                        sub_parts = re.split(r'[一二三四五六七八九十]+[、.．]\s*', part1_content)
                        sub_titles = re.findall(r'[一二三四五六七八九十]+[、.．][^\n]+', part1_content)

                        for i, title in enumerate(sub_titles):
                            part_content = sub_parts[i + 1].strip() if i + 1 < len(sub_parts) else ''

                            if '舆情' in title or '总结' in title or '态势' in title:
                                summary = part_content
                            elif '热点' in title or 'TOP' in title:
                                hot_news_text = part_content
                            elif '风险' in title or '建议' in title or '预警' in title:
                                risk_analysis = part_content
                    else:
                        # 整个 PART 1 作为总结
                        summary = part1_content

        # 如果仍然解析失败，直接返回原文
        if not summary and not hot_news_text and not risk_analysis:
            summary = text_content
            hot_news_text = ''
            risk_analysis = ''

        # 从news_data中提取结构化引用，并用title_url_map校正URL
        structured_refs = {}
        if isinstance(news_data, dict) and 'news_data' in news_data:
            nd = news_data.get('news_data', {})
            if isinstance(nd, dict):
                raw_refs = {
                    'category_news': nd.get('category_news', {}),
                    'top_5_news': nd.get('top_5_news', [])
                }
                structured_refs = _correct_structured_refs(raw_refs, title_url_map)

        # 保存到数据库
        summary_doc = {
            'date': today,
            'date_str': today.strftime('%Y年%m月%d日'),
            'summary': summary,
            'hot_news': hot_news_text,
            'risk_analysis': risk_analysis,
            'full_content': content,
            'article_count': article_count,
            'model': model,
            'title_url_map': title_url_map,
            'structured_refs': structured_refs,  # 新增：结构化引用数据
            'created_at': datetime.now()
        }

        summaries_collection = get_summaries_collection()

        # 获取当天已有记录数，生成序号
        today_count = summaries_collection.count_documents({'date': today})
        summary_doc['seq'] = today_count + 1  # 序号从1开始

        # 新增记录而不是覆盖
        result = summaries_collection.insert_one(summary_doc)
        summary_id = str(result.inserted_id)

        # 记录日志
        log_operation(
            action='生成舆情总结',
            details={
                'article_count': article_count,
                'date': today.strftime('%Y-%m-%d'),
                'model': model,
                'has_structured_refs': bool(structured_refs)
            },
            status='success'
        )

        return success_response({
            'id': summary_id,
            'seq': summary_doc['seq'],
            'summary': summary,
            'hot_news': hot_news_text,
            'risk_analysis': risk_analysis,
            'full_content': content,
            'article_count': article_count,
            'date': today.strftime('%Y年%m月%d日'),
            'model': model,
            'title_url_map': title_url_map,
            'structured_refs': structured_refs,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    except requests.Timeout:
        log_operation(action='舆情总结生成超时', status='error')
        return error_response('LLM API 请求超时，请稍后重试', 504)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"舆情总结生成异常详情:\n{error_detail}")
        log_operation(action='舆情总结生成异常', details={'error': str(e), 'traceback': error_detail[:1000]}, status='error')
        return error_response(f'生成舆情总结失败: {str(e)}', 500)


@api_bp.route('/summary/history', methods=['GET'])
def summary_history():
    """获取AI总结历史列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))

        summaries_collection = get_summaries_collection()

        # 查询总数
        total = summaries_collection.count_documents({})

        # 分页查询，按创建时间倒序（同一天的多条记录按时间排序）
        cursor = summaries_collection.find(
            {},
            {'title_url_map': 0}  # 不返回映射表（数据太大）
        ).sort([('date', -1), ('created_at', -1)]).skip((page - 1) * page_size).limit(page_size)

        items = []
        for doc in cursor:
            seq = doc.get('seq', 1)
            date_str_display = doc.get('date_str', doc['date'].strftime('%Y年%m月%d日'))
            # 如果同一天有多条记录，显示序号
            if seq > 1:
                date_str_display += f' (第{seq}次)'
            items.append({
                'id': str(doc['_id']),
                'seq': seq,
                'date': doc['date'].strftime('%Y-%m-%d'),
                'date_str': date_str_display,
                'article_count': doc.get('article_count', 0),
                'model': doc.get('model', ''),
                'created_at': doc.get('created_at', doc['date']).strftime('%Y-%m-%d %H:%M:%S'),
                'summary_preview': doc.get('summary', '')[:100] + '...' if len(doc.get('summary', '')) > 100 else doc.get('summary', '')
            })

        return success_response({
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': (total + page_size - 1) // page_size
        })
    except Exception as e:
        return error_response(f'获取历史记录失败: {str(e)}', 500)


@api_bp.route('/summary/detail/<summary_id>', methods=['GET'])
def summary_get_by_id(summary_id):
    """根据ID获取AI总结详情"""
    try:
        from bson import ObjectId
        summaries_collection = get_summaries_collection()

        try:
            doc = summaries_collection.find_one({'_id': ObjectId(summary_id)})
        except Exception:
            return error_response('无效的ID格式', 400)

        if not doc:
            return success_response(None)

        # 校正 structured_refs 中的URL
        title_url_map = doc.get('title_url_map', {})
        structured_refs = doc.get('structured_refs', {})
        corrected_refs = _correct_structured_refs(structured_refs, title_url_map)

        return success_response({
            'id': str(doc['_id']),
            'seq': doc.get('seq', 1),
            'date': doc['date'].strftime('%Y-%m-%d'),
            'date_str': doc.get('date_str', doc['date'].strftime('%Y年%m月%d日')),
            'summary': doc.get('summary', ''),
            'hot_news': doc.get('hot_news', ''),
            'risk_analysis': doc.get('risk_analysis', ''),
            'full_content': doc.get('full_content', ''),
            'article_count': doc.get('article_count', 0),
            'model': doc.get('model', ''),
            'title_url_map': title_url_map,
            'structured_refs': corrected_refs,
            'created_at': doc.get('created_at', doc['date']).strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return error_response(f'获取总结失败: {str(e)}', 500)


@api_bp.route('/summary/<date_str>', methods=['GET'])
def summary_get_by_date(date_str):
    """获取指定日期的最新AI总结"""
    try:
        # 解析日期
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            return error_response('日期格式错误，请使用 YYYY-MM-DD 格式', 400)

        summaries_collection = get_summaries_collection()
        # 获取该日期最新的记录
        doc = summaries_collection.find_one(
            {'date': target_date},
            sort=[('created_at', -1)]
        )

        if not doc:
            return success_response(None)

        # 校正 structured_refs 中的URL
        title_url_map = doc.get('title_url_map', {})
        structured_refs = doc.get('structured_refs', {})
        corrected_refs = _correct_structured_refs(structured_refs, title_url_map)

        return success_response({
            'id': str(doc['_id']),
            'seq': doc.get('seq', 1),
            'date': doc['date'].strftime('%Y-%m-%d'),
            'date_str': doc.get('date_str', doc['date'].strftime('%Y年%m月%d日')),
            'summary': doc.get('summary', ''),
            'hot_news': doc.get('hot_news', ''),
            'risk_analysis': doc.get('risk_analysis', ''),
            'full_content': doc.get('full_content', ''),
            'article_count': doc.get('article_count', 0),
            'model': doc.get('model', ''),
            'title_url_map': title_url_map,
            'structured_refs': corrected_refs,
            'created_at': doc.get('created_at', doc['date']).strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return error_response(f'获取总结失败: {str(e)}', 500)


@api_bp.route('/summary/today', methods=['GET'])
def summary_get_today():
    """获取今天最新的AI总结（如果有）"""
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        summaries_collection = get_summaries_collection()
        # 获取当天最新的记录（按created_at倒序）
        doc = summaries_collection.find_one(
            {'date': today},
            sort=[('created_at', -1)]
        )

        if not doc:
            return success_response(None)

        # 校正 structured_refs 中的URL
        title_url_map = doc.get('title_url_map', {})
        structured_refs = doc.get('structured_refs', {})
        corrected_refs = _correct_structured_refs(structured_refs, title_url_map)

        return success_response({
            'id': str(doc['_id']),
            'seq': doc.get('seq', 1),
            'date': doc['date'].strftime('%Y-%m-%d'),
            'date_str': doc.get('date_str', doc['date'].strftime('%Y年%m月%d日')),
            'summary': doc.get('summary', ''),
            'hot_news': doc.get('hot_news', ''),
            'risk_analysis': doc.get('risk_analysis', ''),
            'full_content': doc.get('full_content', ''),
            'article_count': doc.get('article_count', 0),
            'model': doc.get('model', ''),
            'title_url_map': title_url_map,
            'structured_refs': corrected_refs,
            'created_at': doc.get('created_at', doc['date']).strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return error_response(f'获取总结失败: {str(e)}', 500)


@api_bp.route('/summary/prompt', methods=['GET'])
def summary_get_prompt():
    """获取AI总结提示词配置"""
    try:
        current_prompt = get_summary_prompt()
        default_prompt = get_default_summary_prompt()
        return success_response({
            'prompt': current_prompt,
            'default_prompt': default_prompt,
            'is_custom': current_prompt != default_prompt
        })
    except Exception as e:
        return error_response(f'获取提示词失败: {str(e)}', 500)


@api_bp.route('/summary/prompt', methods=['PUT'])
def summary_set_prompt():
    """设置AI总结提示词"""
    try:
        data = request.get_json()
        if data is None:
            return error_response('请求体不能为空', 400)

        prompt = data.get('prompt', '')

        # 验证提示词包含必要的占位符
        if prompt and prompt.strip():
            required_placeholders = ['{date}', '{count}', '{news_list}']
            missing = [p for p in required_placeholders if p not in prompt]
            if missing:
                return error_response(f'提示词必须包含以下占位符: {", ".join(missing)}', 400)

        set_summary_prompt(prompt)

        log_operation(
            action='修改AI总结提示词',
            details={'is_custom': bool(prompt and prompt.strip())},
            status='success'
        )

        return success_response({'message': '提示词已保存'})
    except Exception as e:
        return error_response(f'保存提示词失败: {str(e)}', 500)
