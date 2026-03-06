# -*- coding: utf-8 -*-
"""
REST API 路由
提供统计数据、文章查询、地图数据、风控监控等接口
"""

import time
import socket
import ipaddress
from datetime import datetime
from urllib.parse import urlparse
from flask import Blueprint, request, jsonify, session, Response, stream_with_context
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


def _is_private_url(url: str) -> bool:
    """
    检查 URL 是否指向内网/私有地址，防止 SSRF 攻击。
    阻止访问：127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12,
              192.168.0.0/16, 169.254.0.0/16, localhost, ::1 等
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return True  # 无法解析主机名，视为不安全

        # 检查 localhost 等常见内网主机名
        blocked_hostnames = {'localhost', 'localhost.localdomain', '0.0.0.0'}
        if hostname.lower() in blocked_hostnames:
            return True

        # 将主机名解析为 IP 地址并检查是否为私有地址
        # 使用 getaddrinfo 同时支持 IPv4 和 IPv6
        addr_infos = socket.getaddrinfo(hostname, None)
        for addr_info in addr_infos:
            ip_str = addr_info[4][0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True

        return False
    except socket.gaierror:
        # DNS 解析失败（如被墙站点），不等于内网地址，放行
        # 实际 HTTP 请求会自行处理连接失败
        return False
    except (ValueError, OSError):
        # IP 格式异常或其他系统错误，视为不安全
        return True


# ==================== 认证中间件 ====================

@api_bp.before_request
def check_auth():
    """API 请求认证检查"""
    # 免认证白名单：这些路径无需登录即可访问
    exempt_paths = ['/api/auth/status', '/api/health']
    if request.path in exempt_paths:
        return None
    if 'user' not in session:
        return jsonify({'success': False, 'error': '未登录，请先登录'}), 401


# ==================== 认证接口 ====================

@api_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """获取当前登录状态"""
    user = session.get('user')
    if user:
        return success_response({
            'logged_in': True,
            'username': user['username'],
            'role': user.get('role', 'admin')
        })
    return success_response({'logged_in': False})


@api_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查端点（免认证），返回应用和数据库状态"""
    status = {'app': 'ok', 'mongodb': 'unknown'}
    http_code = 200
    try:
        from models.mongo import get_db
        db = get_db()
        db.command('ping')
        status['mongodb'] = 'ok'
    except Exception as e:
        status['mongodb'] = f'error: {str(e)[:100]}'
        http_code = 503
    return jsonify({'success': http_code == 200, 'data': status}), http_code


@api_bp.route('/auth/change-password', methods=['POST'])
def auth_change_password():
    """修改密码"""
    try:
        from models.users import change_password

        data = request.get_json(silent=True)
        if not data:
            return error_response('请求格式错误')

        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')

        if not old_password or not new_password:
            return error_response('请输入旧密码和新密码')

        if len(new_password) < 6:
            return error_response('新密码长度至少6位')

        username = session['user']['username']
        if change_password(username, old_password, new_password):
            log_operation(action='修改密码', details={'username': username}, status='success')
            return success_response({'message': '密码修改成功'})
        else:
            return error_response('旧密码错误')
    except Exception as e:
        log_error(action='修改密码失败', error=str(e))
        return error_response('修改密码失败，请重试', 500)


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
        log_error(action='获取概览统计失败', error=str(e))
        return error_response('获取概览统计失败，请稍后重试', 500)


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
        log_error(action='获取实时统计失败', error=str(e))
        return error_response('获取实时统计失败，请稍后重试', 500)


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
        log_error(action='获取源统计失败', error=str(e))
        return error_response('获取源统计失败，请稍后重试', 500)


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
        log_error(action='获取趋势统计失败', error=str(e))
        return error_response('获取趋势统计失败，请稍后重试', 500)


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
        log_error(action='获取国家统计失败', error=str(e))
        return error_response('获取国家统计失败，请稍后重试', 500)


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
        log_error(action='获取文章列表失败', error=str(e))
        return error_response('获取文章列表失败，请稍后重试', 500)


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
        log_error(action='获取地图标记失败', error=str(e))
        return error_response('获取地图标记失败，请稍后重试', 500)


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
        log_error(action='获取新闻源列表失败', error=str(e))
        return error_response('获取新闻源列表失败，请稍后重试', 500)


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
        log_error(action='获取新闻源详情失败', error=str(e))
        return error_response('获取新闻源详情失败，请稍后重试', 500)


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
        log_error(action='获取风控关键词失败', error=str(e))
        return error_response('获取风控关键词失败，请稍后重试', 500)


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
        log_error(action='添加关键词失败', error=str(e))
        return error_response('添加关键词失败，请稍后重试', 500)


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
        log_error(action='更新关键词失败', error=str(e))
        return error_response('更新关键词失败，请稍后重试', 500)


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
        log_error(action='删除关键词失败', error=str(e))
        return error_response('删除关键词失败，请稍后重试', 500)


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
        log_error(action='获取风控告警失败', error=str(e))
        return error_response('获取风控告警失败，请稍后重试', 500)


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
        log_error(action='获取日历数据失败', error=str(e))
        return error_response('获取日历数据失败，请稍后重试', 500)


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
        log_error(action='标记已读失败', error=str(e))
        return error_response('标记已读失败，请稍后重试', 500)


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
        log_error(action='获取风控统计失败', error=str(e))
        return error_response('获取风控统计失败，请稍后重试', 500)


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
        log_error(action='获取关键词趋势失败', error=str(e))
        return error_response('获取关键词趋势失败，请稍后重试', 500)


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
        log_error(action='获取站点列表失败', error=str(e))
        return error_response('获取站点列表失败，请稍后重试', 500)


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
        log_error(action='获取站点失败', error=str(e))
        return error_response('获取站点失败，请稍后重试', 500)


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
        log_error(action='获取国家列表失败', error=str(e))
        return error_response('获取国家列表失败，请稍后重试', 500)


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
        log_error(action='获取插件列表失败', error=str(e))
        return error_response('获取插件列表失败，请稍后重试', 500)


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
        log_error(action='获取插件详情失败', error=str(e))
        return error_response('获取插件详情失败，请稍后重试', 500)


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
        log_error(action='切换站点状态失败', error=str(e))
        return error_response('切换站点状态失败，请稍后重试', 500)


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
        log_error(action='修改抓取方式失败', error=str(e))
        return error_response('修改抓取方式失败，请稍后重试', 500)


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
        log_error(action='设置定时更新失败', error=str(e))
        return error_response('设置定时更新失败，请稍后重试', 500)


@api_bp.route('/plugins/<plugin_id>/sites/<site_id>/proxy', methods=['PUT'])
def plugins_set_proxy(plugin_id: str, site_id: str):
    """设置站点是否使用代理"""
    try:
        data = request.get_json()
        if data is None:
            return error_response('请求体不能为空', 400)

        use_proxy = data.get('use_proxy')
        if use_proxy is None:
            return error_response('缺少 use_proxy 参数', 400)

        from plugins.registry import plugin_registry
        site = plugin_registry.get_site(plugin_id, site_id)
        if not site:
            return error_response('站点不存在', 404)

        from models.plugins import set_use_proxy
        result = set_use_proxy(plugin_id, site_id, bool(use_proxy))

        log_operation(
            action=f'{"启用" if use_proxy else "禁用"}站点代理: {site.get("name")}',
            details={'plugin_id': plugin_id, 'site_id': site_id, 'use_proxy': use_proxy},
            status='success'
        )

        return success_response({
            'plugin_id': plugin_id,
            'site_id': site_id,
            'use_proxy': use_proxy,
            'message': f'站点代理已{"启用" if use_proxy else "禁用"}'
        })
    except Exception as e:
        log_error(action='设置站点代理失败', error=str(e))
        return error_response('设置站点代理失败，请稍后重试', 500)


@api_bp.route('/plugins/auto-update-sites', methods=['GET'])
def plugins_auto_update_sites():
    """
    获取所有启用定时更新的站点
    """
    try:
        data = get_auto_update_sites()
        return success_response(data)
    except Exception as e:
        log_error(action='获取定时更新站点失败', error=str(e))
        return error_response('获取定时更新站点失败，请稍后重试', 500)


@api_bp.route('/subscriptions', methods=['GET'])
def subscriptions_list():
    """
    获取所有已启用的站点（用于爬虫和前端展示）
    """
    try:
        data = get_enabled_sites()
        return success_response(data)
    except Exception as e:
        log_error(action='获取订阅列表失败', error=str(e))
        return error_response('获取订阅列表失败，请稍后重试', 500)


# ==================== 设置接口 ====================

from models.settings import (
    load_settings,
    save_settings,
    get_llm_config,
    get_deepseek_config,
    get_openai_config,
    get_api_providers,
    mask_api_key,
    API_PROVIDERS,
    get_translation_config,
    get_translation_prompt,
    set_translation_prompt,
    get_default_translation_prompt,
    get_translation_provider_api_key
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

        # 遮蔽代理敏感信息
        proxy_cfg = settings.get('crawler', {}).get('proxy', {})
        if proxy_cfg:
            if proxy_cfg.get('password'):
                proxy_cfg['password_masked'] = mask_api_key(proxy_cfg['password'])
                proxy_cfg['password_set'] = True
                proxy_cfg['password'] = ''
            else:
                proxy_cfg['password_masked'] = ''
                proxy_cfg['password_set'] = False
            if proxy_cfg.get('username'):
                proxy_cfg['username_masked'] = mask_api_key(proxy_cfg['username'])
                proxy_cfg['username_set'] = True
                proxy_cfg['username'] = ''
            else:
                proxy_cfg['username_masked'] = ''
                proxy_cfg['username_set'] = False

        return success_response(settings)
    except Exception as e:
        log_error(action='获取设置失败', error=str(e))
        return error_response('获取设置失败，请稍后重试', 500)


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

            # 更新代理设置
            if 'proxy' in cr:
                proxy = cr['proxy']
                if 'proxy' not in current_settings['crawler']:
                    current_settings['crawler']['proxy'] = {}
                proxy_cfg = current_settings['crawler']['proxy']

                if 'enabled' in proxy:
                    proxy_cfg['enabled'] = bool(proxy['enabled'])
                if 'host' in proxy:
                    proxy_cfg['host'] = proxy['host'].strip()
                if 'port' in proxy:
                    proxy_cfg['port'] = int(proxy['port'])
                if 'protocol' in proxy:
                    proxy_cfg['protocol'] = proxy['protocol'].strip()
                # 用户名和密码只在非空时才更新
                if 'username' in proxy and proxy['username']:
                    proxy_cfg['username'] = proxy['username'].strip()
                if 'password' in proxy and proxy['password']:
                    proxy_cfg['password'] = proxy['password'].strip()

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
        log_error(action='更新设置失败', error=str(e))
        return error_response('更新设置失败，请稍后重试', 500)


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

        # SSRF 防护：禁止访问内网地址
        if _is_private_url(api_url):
            return error_response('不允许访问内网地址', 403)

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
        log_error(action='测试失败', error=str(e))
        return error_response('测试失败，请稍后重试', 500)


@api_bp.route('/settings/test-proxy', methods=['POST'])
def test_proxy_connection():
    """测试代理连接"""
    try:
        from models.settings import load_settings
        settings = load_settings()
        proxy_cfg = settings.get('crawler', {}).get('proxy', {})

        host = proxy_cfg.get('host', '')
        port = proxy_cfg.get('port', 9000)
        username = proxy_cfg.get('username', '')
        password = proxy_cfg.get('password', '')
        protocol = proxy_cfg.get('protocol', 'http')

        if not host:
            return error_response('未配置代理地址', 400)

        if username and password:
            proxy_url = f"{protocol}://{username}:{password}@{host}:{port}"
        else:
            proxy_url = f"{protocol}://{host}:{port}"

        proxies = {"http": proxy_url, "https": proxy_url}

        import requests as http_requests
        resp = http_requests.get(
            'https://httpbin.org/ip',
            proxies=proxies,
            timeout=15
        )

        if resp.status_code == 200:
            ip_info = resp.json()
            return success_response({
                'message': '代理连接成功',
                'origin_ip': ip_info.get('origin', '未知')
            })
        else:
            return error_response(f'代理返回状态码 {resp.status_code}', 502)

    except Exception as e:
        error_msg = str(e)
        if 'ProxyError' in error_msg or 'proxy' in error_msg.lower():
            return error_response('代理连接失败: 认证错误或代理不可用', 502)
        if 'Timeout' in error_msg or 'timeout' in error_msg.lower():
            return error_response('代理连接超时', 504)
        return error_response(f'代理测试失败: {error_msg}', 500)


@api_bp.route('/layout', methods=['GET'])
def get_layout():
    """获取仪表盘布局配置"""
    try:
        settings = load_settings()
        layout = settings.get('layout', {})
        return success_response(layout)
    except Exception as e:
        log_error(action='获取布局失败', error=str(e))
        return error_response('获取布局失败，请稍后重试', 500)


@api_bp.route('/layout', methods=['PUT'])
def update_layout():
    """保存仪表盘布局配置"""
    try:
        data = request.get_json()
        if data is None:
            return error_response('请求体不能为空', 400)

        from models.settings import set_setting
        set_setting('layout', data)

        log_operation(
            action='更新仪表盘布局',
            details={'panels': list(data.get('panels', {}).keys())},
            status='success'
        )
        return success_response({'message': '布局已保存'})
    except Exception as e:
        log_error(action='保存布局失败', error=str(e))
        return error_response('保存布局失败，请稍后重试', 500)


@api_bp.route('/layout', methods=['DELETE'])
def reset_layout():
    """重置仪表盘布局为默认"""
    try:
        from models.settings import set_setting
        set_setting('layout', {})

        log_operation(
            action='重置仪表盘布局',
            details={},
            status='success'
        )
        return success_response({'message': '布局已重置'})
    except Exception as e:
        log_error(action='重置布局失败', error=str(e))
        return error_response('重置布局失败，请稍后重试', 500)


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
        log_error(action='获取值班信息失败', error=str(e))
        return error_response('获取值班信息失败，请稍后重试', 500)


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
        log_error(action='设置值班人员失败', error=str(e))
        return error_response('设置值班人员失败，请稍后重试', 500)


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
        log_error(action='更新文章失败', error=str(e))
        return error_response('更新文章失败，请稍后重试', 500)


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
        unregister_task, is_cancelled, has_running_task, get_running_task_id
    )
    from models.plugins import get_enabled_sites
    from plugins.crawler import get_crawler

    try:
        # 检查是否有任务正在运行
        if has_running_task():
            running_id = get_running_task_id()
            return error_response(f'已有爬虫任务正在运行 (ID: {running_id})，请等待完成或取消后再试', 409)

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
                skipped_count = 0
                total_articles = 0
                total_saved = 0
                sites_status = {}

                def crawl_single_site(site, index):
                    """爬取单个站点"""
                    if is_cancelled(task_id):
                        return None

                    site_id = site.get('id')
                    site_name = site.get('name', '')

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
                            'skipped': is_timeout,
                            'articles': 0,
                            'saved': 0,
                            'error': ('超时跳过' if is_timeout else error_msg)[:100]
                        }

                max_workers = min(5, total)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_site = {
                        executor.submit(crawl_single_site, site, i): site
                        for i, site in enumerate(sites)
                    }

                    for future in as_completed(future_to_site):
                        if is_cancelled(task_id):
                            executor.shutdown(wait=False, cancel_futures=True)
                            break

                        result = future.result()
                        if result is None:
                            continue

                        completed += 1
                        site_id = result['site_id']
                        sites_status[site_id] = result

                        if result['success']:
                            success_count += 1
                            total_articles += result['articles']
                            total_saved += result['saved']
                        elif result.get('skipped', False):
                            skipped_count += 1
                        else:
                            failed_count += 1

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

                if is_cancelled(task_id):
                    pass
                else:
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
        log_error(action='启动任务失败', error=str(e))
        return error_response('启动任务失败，请稍后重试', 500)


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


@api_bp.route('/crawl/site', methods=['POST'])
def crawl_single_site_api():
    """
    爬取单个站点
    请求体: { plugin_id: "xxx", site_id: "xxx" }
    返回: { fetched: 数量, saved: 数量 }
    """
    from plugins.registry import plugin_registry
    from plugins.crawler import get_crawler

    try:
        data = request.get_json() or {}
        plugin_id = data.get('plugin_id')
        site_id = data.get('site_id')

        if not plugin_id or not site_id:
            return error_response('缺少 plugin_id 或 site_id 参数', 400)

        # 从插件注册表查找站点配置
        plugin = plugin_registry.get_plugin(plugin_id)
        if not plugin:
            return error_response(f'未找到插件: {plugin_id}', 404)

        site = plugin.get_site_by_id(site_id)
        if not site:
            return error_response(f'未找到站点: {site_id}', 404)

        # 检查站点是否已启用
        from models.plugins import is_site_enabled, get_site_fetch_method
        if not is_site_enabled(plugin_id, site_id):
            return error_response('该站点未启用', 400)

        # 复制站点配置，注入 plugin_id（代理判断需要）
        site = dict(site)
        site['plugin_id'] = plugin_id

        # 检查是否有自定义抓取方式
        custom_method = get_site_fetch_method(plugin_id, site_id)
        if custom_method:
            site['fetch_method'] = custom_method

        # 执行爬取
        crawler = get_crawler()
        result = crawler.crawl_site(site, max_articles=100)

        site_name = site.get('name', '')
        print(f"[单站点更新] 开始爬取: {site_name}")

        if result['success']:
            articles = result.get('articles', [])
            saved_count = save_articles(articles) if articles else 0

            print(f"[单站点更新] {site_name}: 抓取 {len(articles)} 篇, 新增 {saved_count} 篇")

            log_operation(
                action='单站点爬取完成',
                details={
                    'plugin_id': plugin_id,
                    'site_id': site_id,
                    'site_name': site_name,
                    'fetched': len(articles),
                    'saved': saved_count
                },
                status='success'
            )

            return success_response({
                'site_name': site_name,
                'fetched': len(articles),
                'saved': saved_count
            })
        else:
            error_msg = result.get('error', '爬取失败')
            skipped = result.get('skipped', False)

            print(f"[单站点更新] {site_name}: {'超时跳过' if skipped else '失败'} - {error_msg}")

            log_operation(
                action='单站点爬取失败',
                details={
                    'plugin_id': plugin_id,
                    'site_id': site_id,
                    'site_name': site_name,
                    'error': error_msg,
                    'skipped': skipped
                },
                status='warning' if skipped else 'error'
            )

            return error_response(
                f'{"超时跳过" if skipped else error_msg}',
                500
            )

    except Exception as e:
        log_error(action='单站点爬取异常', error=str(e))
        return error_response(f'爬取失败: {str(e)[:100]}', 500)


# ==================== 调度器接口 ====================

@api_bp.route('/scheduler/status', methods=['GET'])
def scheduler_status():
    """获取调度器状态"""
    try:
        from plugins.scheduler import get_rss_scheduler
        scheduler = get_rss_scheduler()
        return success_response(scheduler.get_status())
    except Exception as e:
        log_error(action='获取调度器状态失败', error=str(e))
        return error_response('获取调度器状态失败，请稍后重试', 500)


@api_bp.route('/scheduler/trigger', methods=['POST'])
def scheduler_trigger():
    """手动触发一次更新"""
    try:
        from plugins.scheduler import get_rss_scheduler
        scheduler = get_rss_scheduler()
        scheduler.trigger_update()
        return success_response({'message': '已触发更新'})
    except Exception as e:
        log_error(action='触发更新失败', error=str(e))
        return error_response('触发更新失败，请稍后重试', 500)


# ==================== 定时全量爬取接口 ====================

@api_bp.route('/crawl/schedule', methods=['GET'])
def crawl_schedule_get():
    """获取定时全量爬取配置"""
    try:
        from plugins.crawl_scheduler import get_crawl_scheduler
        scheduler = get_crawl_scheduler()
        status = scheduler.get_status()

        # 同时返回settings中的配置
        from models.settings import get_setting
        status['config'] = {
            'enabled': get_setting('crawler.auto_crawl_enabled', False),
            'interval_minutes': get_setting('crawler.auto_crawl_interval', 30),
        }

        return success_response(status)
    except Exception as e:
        log_error(action='获取定时爬取配置失败', error=str(e))
        return error_response('获取定时爬取配置失败，请稍后重试', 500)


@api_bp.route('/crawl/schedule', methods=['PUT'])
def crawl_schedule_set():
    """
    更新定时全量爬取配置
    请求体: { enabled: bool, interval_minutes: int }
    """
    try:
        from plugins.crawl_scheduler import get_crawl_scheduler

        data = request.get_json() or {}
        enabled = data.get('enabled', False)
        interval_minutes = data.get('interval_minutes', 30)

        # 验证间隔范围
        if interval_minutes < 5:
            interval_minutes = 5
        elif interval_minutes > 1440:  # 最多24小时
            interval_minutes = 1440

        scheduler = get_crawl_scheduler()
        scheduler.update_settings(enabled, interval_minutes)

        log_operation(
            action='更新定时爬取配置',
            details={
                'enabled': enabled,
                'interval_minutes': interval_minutes
            },
            status='success'
        )

        return success_response({
            'enabled': enabled,
            'interval_minutes': interval_minutes,
            'message': f'定时爬取已{"启用" if enabled else "禁用"}' +
                       (f'，间隔{interval_minutes}分钟' if enabled else '')
        })
    except Exception as e:
        log_error(action='更新定时爬取配置失败', error=str(e))
        return error_response('更新定时爬取配置失败，请稍后重试', 500)


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
        log_error(action='获取日志失败', error=str(e))
        return error_response('获取日志失败，请稍后重试', 500)


@api_bp.route('/logs/<log_id>', methods=['GET'])
def logs_detail(log_id: str):
    """获取单条日志详情（包含完整的请求/响应数据）"""
    try:
        log = get_log_by_id(log_id)
        if log:
            return success_response(log)
        return error_response('日志不存在', 404)
    except Exception as e:
        log_error(action='获取日志详情失败', error=str(e))
        return error_response('获取日志详情失败，请稍后重试', 500)


@api_bp.route('/logs/stats', methods=['GET'])
def logs_stats():
    """获取日志统计"""
    try:
        data = get_log_stats()
        return success_response(data)
    except Exception as e:
        log_error(action='获取日志统计失败', error=str(e))
        return error_response('获取日志统计失败，请稍后重试', 500)


@api_bp.route('/logs', methods=['DELETE'])
def logs_clear():
    """清空所有日志"""
    try:
        count = clear_logs()
        log_system('清空日志', {'cleared_count': count}, status='success')
        return success_response({'message': f'已清空 {count} 条日志', 'count': count})
    except Exception as e:
        log_error(action='清空日志失败', error=str(e))
        return error_response('清空日志失败，请稍后重试', 500)


# ==================== 控制台实时输出接口 ====================


@api_bp.route('/console/stream', methods=['GET'])
def console_stream():
    """
    SSE 实时控制台输出流
    参数：last_id - 从该 ID 之后开始推送（默认 0）
    """
    from models.console_log import console_manager
    import json as json_module

    last_id = request.args.get('last_id', 0, type=int)

    def generate():
        nonlocal last_id
        while True:
            lines = console_manager.get_lines_after(last_id)
            if lines:
                for line in lines:
                    last_id = line['id']
                    yield f"id: {line['id']}\nevent: log\ndata: {json_module.dumps(line, ensure_ascii=False)}\n\n"
            else:
                yield f"event: heartbeat\ndata: {{}}\n\n"
                console_manager.wait_for_new_line(timeout=15.0)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@api_bp.route('/console/history', methods=['GET'])
def console_history():
    """
    获取控制台历史输出
    参数：lines - 返回最近 N 行（默认 200，最大 2000）
    """
    from models.console_log import console_manager

    try:
        lines = request.args.get('lines', 200, type=int)
        lines = min(lines, 2000)
        data = console_manager.get_history(lines)
        return success_response({
            'items': data,
            'latest_id': console_manager.get_latest_id()
        })
    except Exception as e:
        log_error(action='获取控制台历史失败', error=str(e))
        return error_response('获取控制台历史失败', 500)


@api_bp.route('/console/clear', methods=['POST'])
def console_clear():
    """清空控制台缓冲区"""
    from models.console_log import console_manager

    try:
        console_manager.clear()
        return success_response({'message': '控制台已清空'})
    except Exception as e:
        log_error(action='清空控制台失败', error=str(e))
        return error_response('清空控制台失败', 500)


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
        log_error(action='生成舆情总结失败', error=str(e))
        return error_response('生成舆情总结失败，请稍后重试', 500)


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
        log_error(action='获取历史记录失败', error=str(e))
        return error_response('获取历史记录失败，请稍后重试', 500)


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
        log_error(action='获取总结失败', error=str(e))
        return error_response('获取总结失败，请稍后重试', 500)


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
        log_error(action='获取总结失败', error=str(e))
        return error_response('获取总结失败，请稍后重试', 500)


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
        log_error(action='获取总结失败', error=str(e))
        return error_response('获取总结失败，请稍后重试', 500)


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
        log_error(action='获取提示词失败', error=str(e))
        return error_response('获取提示词失败，请稍后重试', 500)


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
        log_error(action='保存提示词失败', error=str(e))
        return error_response('保存提示词失败，请稍后重试', 500)


# ==================== 翻译设置 API ====================

@api_bp.route('/translation/settings', methods=['GET'])
def get_translation_settings():
    """获取翻译LLM设置"""
    try:
        settings = load_settings()
        trans_config = settings.get('translation', {})

        current_provider = trans_config.get('provider', 'siliconflow')
        providers_config = trans_config.get('providers', {})

        # 获取当前提供商的配置
        current_provider_config = providers_config.get(current_provider, {})
        current_api_key = current_provider_config.get('api_key', '')
        current_api_url = current_provider_config.get('api_url', '')

        # 构建返回的翻译配置
        translation_response = {
            'provider': current_provider,
            'model': trans_config.get('model', 'Pro/Qwen/Qwen2.5-7B-Instruct'),
            'api_url': current_api_url or API_PROVIDERS.get(current_provider, {}).get('api_url', ''),
            'api_key_set': bool(current_api_key),
            'api_key_masked': mask_api_key(current_api_key) if current_api_key else '',
            'providers_status': {}
        }

        # 检查每个提供商的 API Key 配置状态
        for provider_id in API_PROVIDERS.keys():
            provider_cfg = providers_config.get(provider_id, {})
            provider_key = provider_cfg.get('api_key', '')
            translation_response['providers_status'][provider_id] = {
                'api_key_set': bool(provider_key),
                'api_key_masked': mask_api_key(provider_key) if provider_key else '',
                'api_url': provider_cfg.get('api_url', API_PROVIDERS.get(provider_id, {}).get('api_url', ''))
            }

        return success_response({
            'translation': translation_response,
            'providers': API_PROVIDERS
        })
    except Exception as e:
        log_error(action='获取翻译设置失败', error=str(e))
        return error_response('获取翻译设置失败，请稍后重试', 500)


@api_bp.route('/translation/settings', methods=['PUT'])
def update_translation_settings():
    """更新翻译LLM设置"""
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        current_settings = load_settings()

        # 确保 translation.providers 存在
        if 'translation' not in current_settings:
            current_settings['translation'] = {
                'provider': 'siliconflow',
                'model': 'Pro/Qwen/Qwen2.5-7B-Instruct',
                'custom_prompt': '',
                'providers': {}
            }
        if 'providers' not in current_settings['translation']:
            current_settings['translation']['providers'] = {}

        # 更新翻译设置
        if 'translation' in data:
            trans = data['translation']
            provider = trans.get('provider', current_settings['translation'].get('provider', 'siliconflow')).strip()

            # 更新当前提供商
            current_settings['translation']['provider'] = provider

            # 更新模型
            if 'model' in trans:
                current_settings['translation']['model'] = trans['model'].strip()

            # 确保该提供商的配置存在
            if provider not in current_settings['translation']['providers']:
                current_settings['translation']['providers'][provider] = {
                    'api_key': '',
                    'api_url': API_PROVIDERS.get(provider, {}).get('api_url', '')
                }

            # 更新该提供商的 API URL
            if 'api_url' in trans:
                current_settings['translation']['providers'][provider]['api_url'] = trans['api_url'].strip()

            # 更新该提供商的 API Key（只有提供了新的 key 才更新）
            if 'api_key' in trans and trans['api_key']:
                current_settings['translation']['providers'][provider]['api_key'] = trans['api_key'].strip()

        if save_settings(current_settings):
            log_operation(
                action='更新翻译设置',
                details={'provider': current_settings.get('translation', {}).get('provider')},
                status='success'
            )
            return success_response({'message': '翻译设置已保存'})
        else:
            return error_response('保存翻译设置失败', 500)
    except Exception as e:
        log_error(action='更新翻译设置失败', error=str(e))
        return error_response('更新翻译设置失败，请稍后重试', 500)


@api_bp.route('/translation/prompt', methods=['GET'])
def translation_get_prompt():
    """获取翻译提示词配置"""
    try:
        current_prompt = get_translation_prompt()
        default_prompt = get_default_translation_prompt()
        return success_response({
            'prompt': current_prompt,
            'default_prompt': default_prompt,
            'is_custom': current_prompt != default_prompt
        })
    except Exception as e:
        log_error(action='获取翻译提示词失败', error=str(e))
        return error_response('获取翻译提示词失败，请稍后重试', 500)


@api_bp.route('/translation/prompt', methods=['PUT'])
def translation_set_prompt():
    """设置翻译提示词"""
    try:
        data = request.get_json()
        if data is None:
            return error_response('请求体不能为空', 400)

        prompt = data.get('prompt', '')

        # 验证提示词包含必要的占位符
        if prompt and prompt.strip():
            if '{text}' not in prompt:
                return error_response('提示词必须包含 {text} 占位符', 400)

        set_translation_prompt(prompt)

        log_operation(
            action='修改翻译提示词',
            details={'is_custom': bool(prompt and prompt.strip())},
            status='success'
        )

        return success_response({'message': '翻译提示词已保存'})
    except Exception as e:
        log_error(action='保存翻译提示词失败', error=str(e))
        return error_response('保存翻译提示词失败，请稍后重试', 500)


@api_bp.route('/translation/test-api', methods=['POST'])
def test_translation_api():
    """测试翻译API连接"""
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
            api_key = get_translation_provider_api_key(provider)

        if not api_key:
            return error_response('未配置 API Key', 400)

        if not api_url:
            api_url = API_PROVIDERS.get(provider, {}).get('api_url', '')

        if not api_url:
            return error_response('未配置 API URL', 400)

        # 确保 URL 格式正确
        if not api_url.endswith('/chat/completions'):
            if '/v1' in api_url:
                api_url = api_url.rstrip('/') + '/chat/completions'
            else:
                api_url = api_url.rstrip('/') + '/v1/chat/completions'

        # SSRF 防护：禁止访问内网地址
        if _is_private_url(api_url):
            return error_response('不允许访问内网地址', 403)

        if not model:
            model = 'Pro/Qwen/Qwen2.5-7B-Instruct'

        import requests
        response = requests.post(
            api_url,
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': 'Translate to Chinese: Hello World'}],
                'max_tokens': 100,
                'temperature': 0.1
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            translated = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            return success_response({
                'message': '连接成功',
                'model': model,
                'response': translated[:100] if translated else '(无响应)'
            })
        else:
            return error_response(f'API 错误: {response.status_code} - {response.text[:200]}', 400)
    except requests.exceptions.Timeout:
        return error_response('连接超时', 408)
    except Exception as e:
        log_error(action='测试失败', error=str(e))
        return error_response('测试失败，请稍后重试', 500)


# ==================== Telegram 监控接口 ====================

# ---------- 账号管理 ----------

@api_bp.route('/telegram/accounts', methods=['GET'])
def telegram_accounts_list():
    """获取 Telegram 账号列表"""
    try:
        from models.telegram import get_all_accounts
        accounts = get_all_accounts()
        return success_response(accounts)
    except Exception as e:
        log_error(action='获取账号列表失败', error=str(e))
        return error_response('获取账号列表失败，请稍后重试', 500)


@api_bp.route('/telegram/accounts', methods=['POST'])
def telegram_accounts_add():
    """添加 Telegram 账号"""
    try:
        data = request.get_json()
        if not data:
            return error_response('请求数据为空')

        name = data.get('name', '').strip()
        api_id = data.get('api_id', '').strip()
        api_hash = data.get('api_hash', '').strip()
        phone = data.get('phone', '').strip()

        if not all([name, api_id, api_hash, phone]):
            return error_response('请填写完整的账号信息')

        from models.telegram import add_account
        account = add_account(name, api_id, api_hash, phone)
        return success_response(account)
    except ValueError as e:
        return error_response(str(e))
    except Exception as e:
        log_error(action='添加账号失败', error=str(e))
        return error_response('添加账号失败，请稍后重试', 500)


@api_bp.route('/telegram/accounts/<account_id>', methods=['DELETE'])
def telegram_accounts_delete(account_id):
    """删除 Telegram 账号"""
    try:
        from models.telegram import delete_account
        if delete_account(account_id):
            return success_response({'message': '账号已删除'})
        return error_response('账号不存在', 404)
    except Exception as e:
        log_error(action='删除账号失败', error=str(e))
        return error_response('删除账号失败，请稍后重试', 500)


@api_bp.route('/telegram/accounts/<account_id>/connect', methods=['POST'])
def telegram_accounts_connect(account_id):
    """发起 Telegram 账号连接"""
    try:
        from services.telegram_monitor import telegram_monitor
        result = telegram_monitor.connect_account(account_id)
        if result.get('success'):
            return success_response(result)
        return error_response(result.get('error', '连接失败'))
    except Exception as e:
        log_error(action='连接失败', error=str(e))
        return error_response('连接失败，请稍后重试', 500)


@api_bp.route('/telegram/accounts/<account_id>/verify', methods=['POST'])
def telegram_accounts_verify(account_id):
    """验证 Telegram 登录码"""
    try:
        data = request.get_json()
        code = data.get('code', '').strip()
        password = data.get('password', '').strip() or None

        if not code:
            return error_response('请输入验证码')

        from services.telegram_monitor import telegram_monitor
        result = telegram_monitor.verify_code(account_id, code, password)
        if result.get('success'):
            return success_response(result)
        return error_response(result.get('error', '验证失败'))
    except Exception as e:
        log_error(action='验证失败', error=str(e))
        return error_response('验证失败，请稍后重试', 500)


# ---------- 群组管理 ----------

@api_bp.route('/telegram/groups', methods=['GET'])
def telegram_groups_list():
    """获取订阅群组列表"""
    try:
        account_id = request.args.get('account_id')
        from models.telegram import get_all_groups
        groups = get_all_groups(account_id)
        return success_response(groups)
    except Exception as e:
        log_error(action='获取群组列表失败', error=str(e))
        return error_response('获取群组列表失败，请稍后重试', 500)


@api_bp.route('/telegram/groups/search', methods=['POST'])
def telegram_groups_search():
    """搜索 Telegram 群组"""
    try:
        data = request.get_json()
        account_id = data.get('account_id', '')
        query = data.get('query', '').strip()

        if not account_id:
            return error_response('请指定账号')
        if not query:
            return error_response('请输入搜索关键词')

        from services.telegram_monitor import telegram_monitor
        result = telegram_monitor.search_groups(account_id, query)
        if result.get('success'):
            return success_response(result.get('groups', []))
        return error_response(result.get('error', '搜索失败'))
    except Exception as e:
        log_error(action='搜索失败', error=str(e))
        return error_response('搜索失败，请稍后重试', 500)


@api_bp.route('/telegram/groups/subscribe', methods=['POST'])
def telegram_groups_subscribe():
    """订阅群组"""
    try:
        data = request.get_json()
        account_id = data.get('account_id', '')
        group_id = data.get('group_id')
        group_title = data.get('group_title', '')
        group_link = data.get('group_link', '')

        if not all([account_id, group_id, group_title]):
            return error_response('参数不完整')

        from models.telegram import subscribe_group
        group = subscribe_group(account_id, int(group_id), group_title, group_link)
        return success_response(group)
    except ValueError as e:
        return error_response(str(e))
    except Exception as e:
        log_error(action='订阅失败', error=str(e))
        return error_response('订阅失败，请稍后重试', 500)


@api_bp.route('/telegram/groups/<group_db_id>', methods=['DELETE'])
def telegram_groups_unsubscribe(group_db_id):
    """取消订阅群组"""
    try:
        from models.telegram import unsubscribe_group
        if unsubscribe_group(group_db_id):
            return success_response({'message': '已取消订阅'})
        return error_response('群组不存在', 404)
    except Exception as e:
        log_error(action='取消订阅失败', error=str(e))
        return error_response('取消订阅失败，请稍后重试', 500)


@api_bp.route('/telegram/groups/<group_db_id>/toggle', methods=['POST'])
def telegram_groups_toggle(group_db_id):
    """切换群组启用/禁用"""
    try:
        from models.telegram import toggle_group
        new_state = toggle_group(group_db_id)
        return success_response({'enabled': new_state})
    except Exception as e:
        log_error(action='切换状态失败', error=str(e))
        return error_response('切换状态失败，请稍后重试', 500)


# ---------- 关键词管理 ----------

@api_bp.route('/telegram/keywords', methods=['GET'])
def telegram_keywords_list():
    """获取关键词列表"""
    try:
        from models.telegram import get_all_tg_keywords
        keywords = get_all_tg_keywords()
        return success_response(keywords)
    except Exception as e:
        log_error(action='获取关键词失败', error=str(e))
        return error_response('获取关键词失败，请稍后重试', 500)


@api_bp.route('/telegram/keywords', methods=['POST'])
def telegram_keywords_add():
    """添加关键词"""
    try:
        data = request.get_json()
        keyword = data.get('keyword', '').strip()
        level = data.get('level', 'low')

        if not keyword:
            return error_response('关键词不能为空')

        from models.telegram import add_tg_keyword
        kw = add_tg_keyword(keyword, level)
        return success_response(kw)
    except ValueError as e:
        return error_response(str(e))
    except Exception as e:
        log_error(action='添加关键词失败', error=str(e))
        return error_response('添加关键词失败，请稍后重试', 500)


@api_bp.route('/telegram/keywords/<keyword_id>', methods=['PUT'])
def telegram_keywords_update(keyword_id):
    """更新关键词"""
    try:
        data = request.get_json()
        keyword = data.get('keyword')
        level = data.get('level')
        enabled = data.get('enabled')

        from models.telegram import update_tg_keyword
        if update_tg_keyword(keyword_id, keyword, level, enabled):
            return success_response({'message': '更新成功'})
        return error_response('未做任何修改')
    except ValueError as e:
        return error_response(str(e))
    except Exception as e:
        log_error(action='更新失败', error=str(e))
        return error_response('更新失败，请稍后重试', 500)


@api_bp.route('/telegram/keywords/<keyword_id>', methods=['DELETE'])
def telegram_keywords_delete(keyword_id):
    """删除关键词"""
    try:
        from models.telegram import delete_tg_keyword
        if delete_tg_keyword(keyword_id):
            return success_response({'message': '已删除'})
        return error_response('关键词不存在', 404)
    except Exception as e:
        log_error(action='删除失败', error=str(e))
        return error_response('删除失败，请稍后重试', 500)


# ---------- 报警与消息 ----------

@api_bp.route('/telegram/alerts', methods=['GET'])
def telegram_alerts_list():
    """获取报警列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 20, type=int)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        group_id = request.args.get('group_id', type=int)
        level = request.args.get('level')

        from models.telegram import get_alerts
        data = get_alerts(page, page_size, unread_only, group_id, level)
        return success_response(data)
    except Exception as e:
        log_error(action='获取报警列表失败', error=str(e))
        return error_response('获取报警列表失败，请稍后重试', 500)


@api_bp.route('/telegram/alerts/<alert_id>/read', methods=['POST'])
def telegram_alerts_mark_read(alert_id):
    """标记报警已读"""
    try:
        from models.telegram import mark_alert_read as tg_mark_read
        if tg_mark_read(alert_id):
            return success_response({'message': '已标记已读'})
        return error_response('报警不存在', 404)
    except Exception as e:
        log_error(action='标记失败', error=str(e))
        return error_response('标记失败，请稍后重试', 500)


@api_bp.route('/telegram/messages', methods=['GET'])
def telegram_messages_list():
    """获取消息历史"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 50, type=int)
        group_id = request.args.get('group_id', type=int)

        from models.telegram import get_messages
        data = get_messages(group_id, page, page_size)
        return success_response(data)
    except Exception as e:
        log_error(action='获取消息失败', error=str(e))
        return error_response('获取消息失败，请稍后重试', 500)


# ---------- 统计分析 ----------

@api_bp.route('/telegram/stats/overview', methods=['GET'])
def telegram_stats_overview():
    """Telegram 概览统计"""
    try:
        from models.telegram import get_overview_stats as tg_overview
        data = tg_overview()
        return success_response(data)
    except Exception as e:
        log_error(action='获取统计失败', error=str(e))
        return error_response('获取统计失败，请稍后重试', 500)


@api_bp.route('/telegram/stats/alert-trend', methods=['GET'])
def telegram_stats_alert_trend():
    """报警趋势"""
    try:
        days = request.args.get('days', 7, type=int)
        from models.telegram import get_alert_trend
        data = get_alert_trend(days)
        return success_response(data)
    except Exception as e:
        log_error(action='获取趋势失败', error=str(e))
        return error_response('获取趋势失败，请稍后重试', 500)


@api_bp.route('/telegram/stats/keyword-hotness', methods=['GET'])
def telegram_stats_keyword_hotness():
    """关键词热度"""
    try:
        limit = request.args.get('limit', 20, type=int)
        from models.telegram import get_keyword_hotness
        data = get_keyword_hotness(limit)
        return success_response(data)
    except Exception as e:
        log_error(action='获取热度失败', error=str(e))
        return error_response('获取热度失败，请稍后重试', 500)


@api_bp.route('/telegram/stats/group-activity', methods=['GET'])
def telegram_stats_group_activity():
    """群组活跃度"""
    try:
        days = request.args.get('days', 7, type=int)
        from models.telegram import get_group_activity
        data = get_group_activity(days)
        return success_response(data)
    except Exception as e:
        log_error(action='获取活跃度失败', error=str(e))
        return error_response('获取活跃度失败，请稍后重试', 500)


# ---------- 设置与控制 ----------

@api_bp.route('/telegram/webhook/settings', methods=['GET'])
def telegram_webhook_settings_get():
    """获取 Webhook 配置"""
    try:
        from models.settings import get_setting
        data = {
            'webhook_url': get_setting('telegram.webhook_url', ''),
            'webhook_enabled': get_setting('telegram.webhook_enabled', False),
        }
        return success_response(data)
    except Exception as e:
        log_error(action='获取配置失败', error=str(e))
        return error_response('获取配置失败，请稍后重试', 500)


@api_bp.route('/telegram/webhook/settings', methods=['PUT'])
def telegram_webhook_settings_update():
    """更新 Webhook 配置"""
    try:
        data = request.get_json()
        from models.settings import set_setting
        if 'webhook_url' in data:
            set_setting('telegram.webhook_url', data['webhook_url'])
        if 'webhook_enabled' in data:
            set_setting('telegram.webhook_enabled', data['webhook_enabled'])
        return success_response({'message': '配置已保存'})
    except Exception as e:
        log_error(action='保存配置失败', error=str(e))
        return error_response('保存配置失败，请稍后重试', 500)


@api_bp.route('/telegram/webhook/test', methods=['POST'])
def telegram_webhook_test():
    """测试 Webhook 推送"""
    try:
        data = request.get_json() or {}
        webhook_url = data.get('webhook_url')

        from services.telegram_monitor import telegram_monitor
        result = telegram_monitor.test_webhook(webhook_url)
        if result.get('success'):
            return success_response(result)
        return error_response(result.get('error', '推送失败'))
    except Exception as e:
        log_error(action='测试失败', error=str(e))
        return error_response('测试失败，请稍后重试', 500)


@api_bp.route('/telegram/monitor/status', methods=['GET'])
def telegram_monitor_status():
    """获取监控状态"""
    try:
        from services.telegram_monitor import telegram_monitor
        data = telegram_monitor.get_status()
        return success_response(data)
    except Exception as e:
        log_error(action='获取状态失败', error=str(e))
        return error_response('获取状态失败，请稍后重试', 500)


@api_bp.route('/telegram/monitor/start', methods=['POST'])
def telegram_monitor_start():
    """启动监控服务"""
    try:
        from services.telegram_monitor import telegram_monitor
        telegram_monitor.start()
        return success_response({'message': '监控服务已启动'})
    except Exception as e:
        log_error(action='启动失败', error=str(e))
        return error_response('启动失败，请稍后重试', 500)


@api_bp.route('/telegram/monitor/stop', methods=['POST'])
def telegram_monitor_stop():
    """停止监控服务"""
    try:
        from services.telegram_monitor import telegram_monitor
        telegram_monitor.stop()
        return success_response({'message': '监控服务已停止'})
    except Exception as e:
        log_error(action='停止失败', error=str(e))
        return error_response('停止失败，请稍后重试', 500)


# ==================== 站点健康度 API ====================


@api_bp.route('/sites/health', methods=['GET'])
def sites_health():
    """获取所有站点健康度"""
    if 'user' not in session:
        return error_response('未登录', 401)
    from models.mongo import get_sites_health
    health_list = get_sites_health()
    return success_response(health_list)


# ==================== 新闻预览辅助函数 ====================


def _extract_with_trafilatura(html: str, url: str) -> tuple:
    """使用 trafilatura 提取正文，返回 (title, content_blocks) 或 (None, None)"""
    try:
        import trafilatura
        # 提取结构化数据（含标题）
        result = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            include_images=False,
            favor_precision=True,
            deduplicate=True,
        )
        if not result or len(result) < 50:
            return None, None

        # 提取标题
        metadata = trafilatura.extract(
            html, url=url, output_format='xmltei',
            include_comments=False, favor_precision=True
        )
        title = ''
        if metadata:
            from bs4 import BeautifulSoup
            tei_soup = BeautifulSoup(metadata, 'html.parser')
            title_tag = tei_soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
        if not title:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            t = soup.find('title')
            if t:
                title = t.get_text(strip=True)

        # 将纯文本转换为 content blocks 格式
        blocks = []
        for para in result.split('\n'):
            para = para.strip()
            if not para:
                continue
            # 简单启发式：全大写或较短的文本可能是标题
            if len(para) < 80 and para == para.upper() and len(para) > 5:
                blocks.append({'type': 'heading', 'level': 3, 'text': para})
            else:
                blocks.append({'type': 'paragraph', 'text': para})

        if blocks:
            return title, blocks
    except ImportError:
        pass  # trafilatura 未安装
    except Exception:
        pass
    return None, None


def _extract_content_blocks(html: str, base_url: str) -> tuple:
    """从 HTML 提取正文内容块，返回 (title, content_blocks)"""
    from bs4 import BeautifulSoup

    if len(html) > 5 * 1024 * 1024:
        html = html[:5 * 1024 * 1024]

    soup = BeautifulSoup(html, 'html.parser')

    # 提取页面标题
    title = ''
    title_tag = soup.find('title')
    if title_tag:
        title = title_tag.get_text(strip=True)

    # 尝试提取正文区域
    article_selectors = [
        'article', '[role="main"]', '.article-body', '.article-content',
        '.post-content', '.entry-content', '.story-body', '.content-body',
        '#article-body', '#content', '.detail-content', '.news-content', 'main'
    ]
    content_el = None
    for sel in article_selectors:
        content_el = soup.select_one(sel)
        if content_el:
            break
    if not content_el:
        content_el = soup.body or soup

    # 移除干扰元素
    for tag in content_el.find_all(['script', 'style', 'nav', 'header', 'footer',
                                     'aside', 'iframe', 'form', 'button',
                                     '.ad', '.ads', '.advertisement', '.sidebar',
                                     '.comment', '.comments', '.share', '.social']):
        tag.decompose()

    # 提取内容块
    content_blocks = []
    for el in content_el.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'img',
                                    'blockquote', 'ul', 'ol', 'figure', 'figcaption']):
        if el.name == 'img':
            src = el.get('src', '') or el.get('data-src', '') or el.get('data-original', '')
            if src:
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = base_url + src
                elif not src.startswith('http'):
                    src = base_url + '/' + src
                proxy_src = f"/api/proxy/image?url={src}"
                content_blocks.append({'type': 'image', 'src': proxy_src, 'alt': el.get('alt', '')})
        elif el.name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            text = el.get_text(strip=True)
            if text:
                content_blocks.append({'type': 'heading', 'level': int(el.name[1]), 'text': text})
        elif el.name == 'blockquote':
            text = el.get_text(strip=True)
            if text:
                content_blocks.append({'type': 'blockquote', 'text': text})
        elif el.name in ('ul', 'ol'):
            items = [li.get_text(strip=True) for li in el.find_all('li') if li.get_text(strip=True)]
            if items:
                content_blocks.append({'type': 'list', 'ordered': el.name == 'ol', 'items': items})
        elif el.name == 'figcaption':
            text = el.get_text(strip=True)
            if text:
                content_blocks.append({'type': 'caption', 'text': text})
        else:
            if el.name == 'figure':
                img = el.find('img')
                if img:
                    src = img.get('src', '') or img.get('data-src', '')
                    if src:
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = base_url + src
                        elif not src.startswith('http'):
                            src = base_url + '/' + src
                        proxy_src = f"/api/proxy/image?url={src}"
                        content_blocks.append({'type': 'image', 'src': proxy_src, 'alt': img.get('alt', '')})
                caption = el.find('figcaption')
                if caption:
                    text = caption.get_text(strip=True)
                    if text:
                        content_blocks.append({'type': 'caption', 'text': text})
            else:
                text = el.get_text(strip=True)
                if text and len(text) > 5:
                    content_blocks.append({'type': 'paragraph', 'text': text})

    return title, content_blocks


def _content_quality_ok(content_blocks: list) -> bool:
    """自适应质量检查 — 根据内容特征动态调整门槛"""
    if not content_blocks:
        return False

    text_blocks = [b for b in content_blocks if b['type'] in ('paragraph', 'heading', 'blockquote')]
    if not text_blocks:
        return False

    total_text = sum(len(b.get('text', '')) for b in text_blocks)
    block_count = len(text_blocks)

    # 宽松标准：有标题 + 正文，且总文本 ≥ 50 字符（快讯类新闻）
    has_heading = any(b.get('type') == 'heading' for b in text_blocks)
    has_paragraph = any(b.get('type') == 'paragraph' for b in text_blocks)
    if has_heading and has_paragraph and total_text >= 50:
        return True

    # 长文本标准：单段长文（某些站点全文放在一个 <p> 中）
    if total_text >= 200:
        return True

    # 原始标准：至少 3 个文本块，总字符 ≥ 100
    return block_count >= 3 and total_text >= 100


def _take_page_screenshot(target_url: str) -> str:
    """使用 Playwright + stealth 反检测截取页面截图，返回 Base64 编码的 PNG"""
    import asyncio
    import base64
    import os
    import shutil

    async def _do_screenshot():
        from playwright.async_api import async_playwright
        from playwright_stealth import stealth_async
        async with async_playwright() as p:
            # 优先使用系统 Chrome，不存在则回退到 Playwright 内置 Chromium
            has_chrome = shutil.which('google-chrome') or shutil.which('chrome') or shutil.which('chromium')
            launch_kwargs = {
                'headless': True,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                ],
            }
            if has_chrome:
                launch_kwargs['channel'] = 'chrome'
            browser = await p.chromium.launch(**launch_kwargs)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
            )
            page = await context.new_page()
            await stealth_async(page)
            try:
                await page.goto(target_url, wait_until='networkidle', timeout=25000)
            except Exception:
                try:
                    await page.goto(target_url, wait_until='domcontentloaded', timeout=15000)
                except Exception:
                    pass
            # 等待页面渲染稳定
            await page.wait_for_timeout(2000)
            screenshot_bytes = await page.screenshot(full_page=True, type='png')
            await browser.close()
            return base64.b64encode(screenshot_bytes).decode('utf-8')

    old_env = os.environ.get('PYTHONIOENCODING')
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_do_screenshot())
    finally:
        loop.close()
        if old_env is None:
            os.environ.pop('PYTHONIOENCODING', None)
        else:
            os.environ['PYTHONIOENCODING'] = old_env


def _resolve_redirect_url(target_url: str) -> str:
    """
    解析中间跳转 URL（如 Google News RSS），返回最终真实文章 URL。
    使用 Playwright + stealth 反检测跟随 JS 重定向。
    """
    parsed = urlparse(target_url)
    is_google_news = (
        'news.google.com' in parsed.netloc and
        ('/rss/articles/' in parsed.path or '/articles/' in parsed.path)
    )
    if not is_google_news:
        return target_url

    try:
        import asyncio
        import os
        import shutil

        async def _follow_redirect():
            from playwright.async_api import async_playwright
            from playwright_stealth import stealth_async
            async with async_playwright() as p:
                # 优先使用系统 Chrome，不存在则回退到 Playwright 内置 Chromium
                has_chrome = shutil.which('google-chrome') or shutil.which('chrome') or shutil.which('chromium')
                launch_kwargs = {
                    'headless': True,
                    'args': [
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                    ],
                }
                if has_chrome:
                    launch_kwargs['channel'] = 'chrome'
                browser = await p.chromium.launch(**launch_kwargs)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                )
                page = await context.new_page()
                await stealth_async(page)
                try:
                    await page.goto(target_url, wait_until='domcontentloaded', timeout=15000)
                    # Google News 需要 JS 执行后才重定向，等待最多 10 秒
                    for _ in range(20):
                        await page.wait_for_timeout(500)
                        current = page.url
                        if 'news.google.com' not in current:
                            await browser.close()
                            return current
                except Exception:
                    pass
                final = page.url
                await browser.close()
                return final

        old_env = os.environ.get('PYTHONIOENCODING')
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        loop = asyncio.new_event_loop()
        try:
            resolved = loop.run_until_complete(_follow_redirect())
        finally:
            loop.close()
            if old_env is None:
                os.environ.pop('PYTHONIOENCODING', None)
            else:
                os.environ['PYTHONIOENCODING'] = old_env

        if resolved and 'news.google.com' not in resolved:
            return resolved
    except Exception as e:
        print(f"Google News URL 解析失败: {e}")

    return target_url


def _get_cached_article_info(target_url: str) -> dict:
    """从 MongoDB news_articles 集合查询文章缓存信息"""
    try:
        from models.mongo import get_articles_collection
        collection = get_articles_collection()
        doc = collection.find_one({'loc': target_url}, {'title': 1, 'source_name': 1, 'pub_date': 1})
        if doc:
            return {
                'title': doc.get('title', ''),
                'source': doc.get('source_name', ''),
                'pub_date': doc['pub_date'].strftime('%Y-%m-%d') if doc.get('pub_date') else ''
            }
    except Exception:
        pass
    return None


# ==================== 新闻预览端点 ====================


def _get_preview_cache(url: str) -> dict:
    """查询预览缓存"""
    try:
        from models.mongo import get_preview_cache_collection
        col = get_preview_cache_collection()
        cache = col.find_one({'url': url})
        if cache:
            return cache.get('result')
    except Exception:
        pass
    return None


def _set_preview_cache(url: str, result: dict):
    """写入预览缓存"""
    try:
        from models.mongo import get_preview_cache_collection
        from datetime import datetime
        col = get_preview_cache_collection()
        col.update_one(
            {'url': url},
            {'$set': {
                'url': url,
                'result': result,
                'cached_at': datetime.utcnow()
            }},
            upsert=True
        )
    except Exception:
        pass


def _enhanced_fetch(url: str, proxy_url: str = '') -> str:
    """增强 HTTP 抓取 — 尝试 curl_cffi（TLS 指纹伪装），回退到 requests Session"""
    import requests as http_requests

    # 增强请求头（模拟真实浏览器完整 headers）
    enhanced_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Sec-Ch-Ua': '"Chromium";v="120", "Google Chrome";v="120", "Not-A.Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'DNT': '1',
        'Connection': 'keep-alive',
    }
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    # 尝试 curl_cffi（模拟浏览器 TLS 指纹）
    try:
        from curl_cffi import requests as curl_requests
        from models.settings import load_settings
        settings = load_settings()
        impersonate = settings.get('crawler', {}).get('curl_cffi_impersonate', 'chrome120')
        resp = curl_requests.get(
            url,
            headers=enhanced_headers,
            timeout=15,
            verify=False,
            proxies=proxies,
            impersonate=impersonate
        )
        if resp.status_code == 200:
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return resp.text
    except ImportError:
        pass  # curl_cffi 未安装，回退
    except Exception:
        pass  # curl_cffi 请求失败，回退

    # 回退：使用 requests Session（复用 TCP 连接和 Cookie）
    try:
        s = http_requests.Session()
        s.headers.update(enhanced_headers)
        resp = s.get(url, timeout=15, verify=False, proxies=proxies)
        if resp.status_code == 200:
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return resp.text
    except Exception:
        pass

    return ''


def _get_global_proxy_url() -> str:
    """
    读取全局代理配置，返回代理 URL。
    全局开关关闭或配置不完整时返回空串。
    """
    try:
        settings = load_settings()
        proxy_cfg = settings.get('crawler', {}).get('proxy', {})
        if not proxy_cfg.get('enabled'):
            return ''
        host = proxy_cfg.get('host', '')
        if not host:
            return ''
        port = proxy_cfg.get('port', 9000)
        username = proxy_cfg.get('username', '')
        password = proxy_cfg.get('password', '')
        protocol = proxy_cfg.get('protocol', 'http')
        if username and password:
            return f"{protocol}://{username}:{password}@{host}:{port}"
        return f"{protocol}://{host}:{port}"
    except Exception:
        return ''


@api_bp.route('/news/preview', methods=['GET'])
def news_preview():
    """获取新闻预览内容 — 智能回退链（正文提取 → 无头浏览器 → 截图 → 缓存摘要）"""
    if 'user' not in session:
        return error_response('未登录', 401)

    url = request.args.get('url', '').strip()
    if not url:
        return error_response('缺少 url 参数', 400)

    # 校验 URL 合法性
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return error_response('URL 必须以 http 或 https 开头', 400)

    # SSRF 防护：禁止访问内网地址
    if _is_private_url(url):
        return error_response('不允许访问内网地址', 403)

    # 解析中间跳转 URL（如 Google News RSS 链接）
    original_url = url
    url = _resolve_redirect_url(url)
    if url != original_url:
        parsed = urlparse(url)
        # 跳转后再次检查 SSRF
        if _is_private_url(url):
            return error_response('不允许访问内网地址', 403)

    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # Cloudflare 检测标记
    cf_markers = ['Just a moment...', 'Checking your browser', 'cf-browser-verification',
                  'challenges.cloudflare.com', '_cf_chl_opt', 'Attention Required']

    # 检查全局代理配置
    proxy_url = _get_global_proxy_url()

    # 查询预览缓存
    cached_preview = _get_preview_cache(url)
    if cached_preview:
        return success_response(cached_preview)

    try:
        # ===== Level 1: requests.get() + 正文提取 =====
        html = None
        try:
            import requests as http_requests
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            }
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            resp = http_requests.get(url, headers=headers, timeout=15, verify=False, proxies=proxies)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            html = resp.text
        except Exception:
            pass

        is_cf = html and any(m in html for m in cf_markers)

        if html and not is_cf:
            # 优先使用 trafilatura 提取（精度更高）
            title, blocks = _extract_with_trafilatura(html, url)
            if not blocks:
                # 回退到 BeautifulSoup 自研提取器
                title, blocks = _extract_content_blocks(html, base_url)
            if _content_quality_ok(blocks):
                result_data = {
                    'type': 'content',
                    'quality': 'full',
                    'title': title,
                    'url': url,
                    'content': blocks
                }
                _set_preview_cache(url, result_data)
                return success_response(result_data)

        # ===== Level 2: 增强抓取 + 正文提取 =====
        # 无代理 → crawl4ai 无头浏览器 | 有代理 → curl_cffi/requests 增强请求头
        try:
            crawler_html = ''
            if not proxy_url:
                # 无代理：尝试 crawl4ai 无头浏览器（支持 JS 渲染）
                try:
                    import asyncio
                    import os
                    from plugins.crawler import get_crawler
                    old_env = os.environ.get('PYTHONIOENCODING')
                    os.environ['PYTHONIOENCODING'] = 'utf-8'
                    crawler = get_crawler()
                    loop = asyncio.new_event_loop()
                    try:
                        crawler_html = loop.run_until_complete(crawler.fetch_page(url, timeout=20))
                    finally:
                        loop.close()
                        if old_env is None:
                            os.environ.pop('PYTHONIOENCODING', None)
                        else:
                            os.environ['PYTHONIOENCODING'] = old_env
                except Exception:
                    crawler_html = ''
            else:
                # 有代理：使用 curl_cffi 模拟浏览器 TLS 指纹（如果可用），否则用增强 requests
                crawler_html = _enhanced_fetch(url, proxy_url)

            if crawler_html:
                # 优先使用 trafilatura 提取
                title, blocks = _extract_with_trafilatura(crawler_html, url)
                if not blocks:
                    title, blocks = _extract_content_blocks(crawler_html, base_url)
                if _content_quality_ok(blocks):
                    result_data = {
                        'type': 'content',
                        'quality': 'full',
                        'title': title,
                        'url': url,
                        'content': blocks
                    }
                    _set_preview_cache(url, result_data)
                    return success_response(result_data)
        except Exception as l2_err:
            log_error(f"Level 2 增强抓取失败: {url}", str(l2_err))

        # ===== Level 3: Playwright 全页截图 =====
        # 无论是否有代理都尝试截图（Playwright 自身支持代理参数）
        try:
            screenshot_b64 = _take_page_screenshot(url)
            if screenshot_b64:
                result_data = {
                    'type': 'screenshot',
                    'quality': 'screenshot',
                    'image': f'data:image/png;base64,{screenshot_b64}',
                    'url': url
                }
                _set_preview_cache(url, result_data)
                return success_response(result_data)
        except Exception as l3_err:
            log_error(f"Level 3 截图失败: {url}", str(l3_err))

        # ===== Level 4: 数据库缓存摘要 =====
        cached = _get_cached_article_info(url)
        if cached:
            return success_response({
                'type': 'cached',
                'quality': 'summary',
                'title': cached['title'],
                'source': cached['source'],
                'pub_date': cached['pub_date'],
                'url': url
            })

        # 所有回退都失败
        return error_response('无法预览该页面，请直接访问原始链接', 502)

    except Exception as e:
        log_error(f"新闻预览失败: {url}", str(e))
        return error_response(f'预览失败: {str(e)}', 502)


# ==================== 新闻翻译端点 ====================

@api_bp.route('/news/translate', methods=['POST'])
def news_translate():
    """翻译新闻正文内容块 — 接收 content blocks，返回翻译后的 content blocks"""
    if 'user' not in session:
        return error_response('未登录', 401)

    data = request.get_json(silent=True)
    if not data:
        return error_response('请求格式错误', 400)

    title = data.get('title', '')
    content = data.get('content', [])

    if not content and not title:
        return error_response('缺少翻译内容', 400)

    try:
        from plugins.translator import is_chinese, _get_translation_api_config, _clean_translated_text
        import requests as http_requests

        api_config = _get_translation_api_config()
        if not api_config:
            return error_response('翻译服务未配置，请在系统设置中配置翻译 API', 503)

        # 收集所有需要翻译的文本块（编号 → 文本映射）
        texts_to_translate = []  # [(index_label, text)]
        text_sources = []  # [('title',) | ('content', idx, field)]

        # 标题
        if title and not is_chinese(title):
            texts_to_translate.append(title)
            text_sources.append(('title',))

        # 正文块
        for i, block in enumerate(content):
            block_type = block.get('type', '')
            text = ''
            if block_type in ('paragraph', 'heading', 'blockquote', 'caption'):
                text = block.get('text', '')
            elif block_type == 'list':
                # 列表项合并为一个翻译单元，用 | 分隔
                items = block.get('items', [])
                if items:
                    text = ' | '.join(items)

            if text and not is_chinese(text):
                texts_to_translate.append(text)
                text_sources.append(('content', i, block_type))

        # 如果没有需要翻译的内容（全是中文）
        if not texts_to_translate:
            return success_response({
                'title': title,
                'content': content,
                'all_chinese': True
            })

        # 构建编号列表，单次 LLM 调用批量翻译
        numbered_text = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(texts_to_translate))

        system_prompt = (
            '你是专业翻译助手。将用户提供的编号文本逐条翻译为中文。'
            '严格保持编号格式，每行一条，只输出翻译结果，不要解释。'
            '保持原文的语气和风格。如果文本中包含 | 分隔符，翻译后也保持 | 分隔。'
        )

        response = http_requests.post(
            api_config['api_url'],
            headers={
                'Authorization': f'Bearer {api_config["api_key"]}',
                'Content-Type': 'application/json'
            },
            json={
                'model': api_config['model'],
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': numbered_text}
                ],
                'max_tokens': 200 * len(texts_to_translate),
                'temperature': 0.1
            },
            timeout=120
        )

        if response.status_code != 200:
            return error_response(f'翻译 API 请求失败: {response.status_code}', 502)

        result = response.json()
        resp_content = result.get('choices', [{}])[0].get('message', {}).get('content', '')

        # 解析编号格式的返回结果
        import re
        translated_map = {}
        for line in resp_content.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(\d+)\s*[.、）)]\s*(.+)', line)
            if match:
                idx = int(match.group(1))
                text = _clean_translated_text(match.group(2))
                if 1 <= idx <= len(texts_to_translate) and text:
                    translated_map[idx] = text

        # 组装翻译结果
        translated_title = title
        translated_content = []

        for content_block in content:
            translated_content.append(dict(content_block))  # 浅拷贝

        trans_idx = 0
        for src in text_sources:
            trans_idx += 1
            translated_text = translated_map.get(trans_idx)
            if not translated_text:
                continue

            if src[0] == 'title':
                translated_title = translated_text
            elif src[0] == 'content':
                content_idx = src[1]
                block_type = src[2]
                if content_idx < len(translated_content):
                    if block_type == 'list':
                        # 还原 | 分隔的列表项
                        translated_content[content_idx]['items'] = [
                            item.strip() for item in translated_text.split('|')
                        ]
                    else:
                        translated_content[content_idx]['text'] = translated_text

        return success_response({
            'title': translated_title,
            'content': translated_content,
            'all_chinese': False
        })

    except Exception as e:
        log_error(f"新闻翻译失败", str(e))
        return error_response(f'翻译失败: {str(e)}', 500)


@api_bp.route('/proxy/image', methods=['GET'])
def proxy_image():
    """代理外部图片 — 使服务器中转图片请求，绕过客户端网络限制"""
    if 'user' not in session:
        return error_response('未登录', 401)

    image_url = request.args.get('url', '').strip()
    if not image_url:
        return error_response('缺少 url 参数', 400)

    # SSRF 防护：禁止访问内网地址
    if _is_private_url(image_url):
        return error_response('不允许访问内网地址', 403)

    try:
        import requests as http_requests
        from flask import Response
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        resp = http_requests.get(image_url, headers=headers, timeout=10, verify=False, stream=True)

        # 限制图片大小（最大 10MB）
        content_length = int(resp.headers.get('content-length', 0))
        if content_length > 10 * 1024 * 1024:
            return error_response('图片过大', 413)

        content_type = resp.headers.get('content-type', 'image/jpeg')
        return Response(
            resp.content,
            content_type=content_type,
            headers={
                'Cache-Control': 'public, max-age=86400'
            }
        )
    except Exception:
        # 返回 1x1 透明像素作为 fallback
        transparent_pixel = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        from flask import Response
        return Response(transparent_pixel, content_type='image/gif')


@api_bp.route('/defcon/current', methods=['GET'])
def get_defcon_level():
    """获取当前 DEFCON 威胁等级"""
    if 'user' not in session:
        return error_response('未登录', 401)

    try:
        import requests as http_requests
        from bs4 import BeautifulSoup

        # 获取页面内容
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = http_requests.get(
            'https://www.defconlevel.com/current-level',
            headers=headers,
            timeout=10,
            verify=False
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')

        # 提取当前等级
        current_level = None
        status_text = ""
        reason = ""

        # 查找当前等级（通常在 h2 或特定 class 中）
        level_elem = soup.find('h2', string=lambda t: t and 'DEFCON' in t)
        if level_elem:
            level_text = level_elem.get_text().strip()
            # 提取数字
            import re
            match = re.search(r'DEFCON\s*(\d)', level_text)
            if match:
                current_level = int(match.group(1))

        # 查找状态描述
        status_elem = soup.find('p', class_='status-description')
        if not status_elem:
            # 尝试其他可能的选择器
            status_elem = soup.find('div', class_='current-status')
        if status_elem:
            status_text = status_elem.get_text().strip()

        # 查找原因说明
        reason_elem = soup.find('div', class_='reason')
        if not reason_elem:
            reason_elem = soup.find('p', string=lambda t: t and 'Reason' in t)
        if reason_elem:
            reason = reason_elem.get_text().strip()

        # 如果没有找到，使用默认值
        if current_level is None:
            current_level = 3
            status_text = "数据获取中..."
            reason = "正在从 DEFCON Level 获取最新数据"

        # DEFCON 等级定义
        levels = [
            {
                'level': 5,
                'name': 'DEFCON 5',
                'name_cn': '和平时期',
                'color': '#00ff88',
                'description': '正常和平时期准备状态',
                'description_cn': '正常和平时期准备状态'
            },
            {
                'level': 4,
                'name': 'DEFCON 4',
                'name_cn': '提高警戒',
                'color': '#00d4ff',
                'description': '加强情报监控和安全措施',
                'description_cn': '加强情报监控和安全措施'
            },
            {
                'level': 3,
                'name': 'DEFCON 3',
                'name_cn': '军事戒备',
                'color': '#ffd700',
                'description': '军事准备状态高于正常水平',
                'description_cn': '军事准备状态高于正常水平'
            },
            {
                'level': 2,
                'name': 'DEFCON 2',
                'name_cn': '战备就绪',
                'color': '#ff8800',
                'description': '武装部队准备在6小时内部署作战',
                'description_cn': '武装部队准备在6小时内部署作战'
            },
            {
                'level': 1,
                'name': 'DEFCON 1',
                'name_cn': '核战边缘',
                'color': '#ff0044',
                'description': '最高戒备状态，核战争即将爆发',
                'description_cn': '最高戒备状态，核战争即将爆发'
            }
        ]

        return success_response({
            'current_level': current_level,
            'status': status_text,
            'reason': reason,
            'levels': levels,
            'updated_at': datetime.now().isoformat()
        })

    except Exception as e:
        log_error("获取 DEFCON 等级失败", str(e))
        # 返回默认数据
        return success_response({
            'current_level': 3,
            'status': '数据获取失败',
            'reason': f'无法连接到 DEFCON Level 服务器: {str(e)}',
            'levels': [
                {'level': 5, 'name': 'DEFCON 5', 'name_cn': '和平时期', 'color': '#00ff88', 'description_cn': '正常和平时期准备状态'},
                {'level': 4, 'name': 'DEFCON 4', 'name_cn': '提高警戒', 'color': '#00d4ff', 'description_cn': '加强情报监控和安全措施'},
                {'level': 3, 'name': 'DEFCON 3', 'name_cn': '军事戒备', 'color': '#ffd700', 'description_cn': '军事准备状态高于正常水平'},
                {'level': 2, 'name': 'DEFCON 2', 'name_cn': '战备就绪', 'color': '#ff8800', 'description_cn': '武装部队准备在6小时内部署作战'},
                {'level': 1, 'name': 'DEFCON 1', 'name_cn': '核战边缘', 'color': '#ff0044', 'description_cn': '最高戒备状态，核战争即将爆发'}
            ],
            'updated_at': datetime.now().isoformat()
        })


@api_bp.route('/events/timeline', methods=['GET'])
def get_events_timeline():
    """获取全球事件时间线（从缓存读取）"""
    if 'user' not in session:
        return error_response('未登录', 401)

    # 获取分页参数
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 20))

    try:
        from models.events import get_all_events, get_events_count

        log_system(f"从缓存获取事件链数据, offset: {offset}, limit: {limit}")

        # 从数据库获取事件
        events = get_all_events(skip=offset, limit=limit)
        total = get_events_count()

        log_system(f"获取到 {len(events)} 个事件，总数: {total}")

        # 转换为前端格式
        processed_events = []
        for event in events:
            # 优先使用中文，如果没有则使用英文
            title = event.get('title_cn') or event.get('title', '')
            description = event.get('description_cn') or event.get('description', '')
            location = event.get('location_cn') or event.get('location', '')

            processed_events.append({
                'event_id': str(event.get('_id', '')),
                'title': title,
                'description': description,
                'location': location,
                'timestamp': event.get('timestamp', ''),
                'severity': event.get('severity', 'medium'),
                'is_translated': bool(event.get('title_cn')),  # 标记是否已翻译
                'original_title': event.get('title', ''),
                'original_description': event.get('description', ''),
                'original_location': event.get('location', '')
            })

        return success_response({
            'events': processed_events,
            'total': total,
            'offset': offset,
            'limit': limit,
            'has_more': (offset + limit) < total,
            'updated_at': datetime.now().isoformat()
        })

    except Exception as e:
        log_error("获取事件时间线失败", str(e))
        return error_response(f'获取事件失败: {str(e)}', 500)


def _translate_text(text: str, config: dict) -> str:
    """翻译文本的辅助函数"""
    if not text or not text.strip():
        return text

    try:
        import requests as http_requests

        provider = config.get('provider', 'siliconflow')
        api_key = config.get('api_key', '')
        model = config.get('model', 'Qwen/Qwen2.5-7B-Instruct')
        api_url = config.get('api_url', '')

        if not api_key or not api_url:
            log_system(f"翻译配置不完整: api_key={bool(api_key)}, api_url={bool(api_url)}")
            return text

        # 构建翻译提示词
        prompt = f"请将以下英文翻译成简体中文，只返回翻译结果，不要添加任何解释：\n\n{text}"

        # 调用 LLM API
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.3,
            'max_tokens': 1000
        }

        log_system(f"调用翻译 API: {api_url}, model: {model}")

        resp = http_requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30,  # 增加超时时间到30秒
            verify=False
        )

        log_system(f"翻译 API 响应状态: {resp.status_code}")

        if resp.status_code == 200:
            result = resp.json()
            translated = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            if translated:
                log_system(f"翻译成功: {text[:30]}... -> {translated[:30]}...")
                return translated
            else:
                log_system("翻译结果为空")
                return text
        else:
            log_error(f"翻译 API 返回错误", f"状态码: {resp.status_code}, 响应: {resp.text[:200]}")
            return text

    except Exception as e:
        log_error(f"翻译异常", str(e))
        return text


# ==================== 全球事件链 API ====================

@api_bp.route('/events/timeline', methods=['GET'])
def events_timeline():
    """获取事件时间线（支持中英文切换）"""
    try:
        from models.events import get_all_events, get_events_count
        from datetime import datetime

        # 获取参数
        lang = request.args.get('lang', 'en')  # en 或 cn
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', 20))

        # 获取事件数据
        events = get_all_events(skip=offset, limit=limit)
        total = get_events_count()

        # 根据语言选择字段
        processed_events = []
        for event in events:
            # 转换 ObjectId 为字符串
            if '_id' in event:
                event['_id'] = str(event['_id'])

            if lang == 'cn':
                # 中文模式：优先使用翻译后的字段，如果没有则使用英文原文
                processed_event = {
                    'event_id': event.get('event_id'),
                    'title': event.get('title_cn') or event.get('title', ''),
                    'description': event.get('description_cn') or event.get('description', ''),
                    'location': event.get('location_cn') or event.get('location', ''),
                    'timestamp': event.get('timestamp'),
                    'timestamp_sort': event.get('timestamp_sort'),
                    'severity': event.get('severity', 'medium'),
                    'has_translation': bool(event.get('title_cn'))  # 标记是否已翻译
                }
            else:
                # 英文模式：使用原始英文字段
                processed_event = {
                    'event_id': event.get('event_id'),
                    'title': event.get('title', ''),
                    'description': event.get('description', ''),
                    'location': event.get('location', ''),
                    'timestamp': event.get('timestamp'),
                    'timestamp_sort': event.get('timestamp_sort'),
                    'severity': event.get('severity', 'medium'),
                    'has_translation': bool(event.get('title_cn'))
                }

            processed_events.append(processed_event)

        # 判断是否还有更多数据
        has_more = (offset + len(processed_events)) < total

        return jsonify({
            'success': True,
            'data': {
                'events': processed_events,
                'total': total,
                'offset': offset,
                'has_more': has_more,
                'updated_at': datetime.now().isoformat()
            }
        })
    except Exception as e:
        log_error("获取事件时间线失败", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/events/list', methods=['GET'])
def events_list():
    """获取事件列表（分页）"""
    try:
        from models.events import get_all_events, get_events_count

        skip = int(request.args.get('skip', 0))
        limit = int(request.args.get('limit', 20))

        events = get_all_events(skip=skip, limit=limit)
        total = get_events_count()

        # 转换 ObjectId 为字符串
        for event in events:
            if '_id' in event:
                event['_id'] = str(event['_id'])

        return jsonify({
            'success': True,
            'data': {
                'events': events,
                'total': total,
                'skip': skip,
                'limit': limit
            }
        })
    except Exception as e:
        log_error("获取事件列表失败", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/events/service/status', methods=['GET'])
def events_service_status():
    """获取事件服务状态"""
    try:
        from services.events_service import get_events_service

        service = get_events_service()

        return jsonify({
            'success': True,
            'data': {
                'running': service.running,
                'fetch_interval': service.fetch_interval,
                'translate_interval': service.translate_interval
            }
        })
    except Exception as e:
        log_error("获取事件服务状态失败", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/events/service/start', methods=['POST'])
def events_service_start():
    """启动事件服务"""
    try:
        from services.events_service import start_events_service

        start_events_service()
        log_system("手动启动事件服务")

        return jsonify({
            'success': True,
            'message': '事件服务已启动'
        })
    except Exception as e:
        log_error("启动事件服务失败", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/events/service/stop', methods=['POST'])
def events_service_stop():
    """停止事件服务"""
    try:
        from services.events_service import stop_events_service

        stop_events_service()
        log_system("手动停止事件服务")

        return jsonify({
            'success': True,
            'message': '事件服务已停止'
        })
    except Exception as e:
        log_error("停止事件服务失败", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/events/fetch', methods=['POST'])
def events_fetch_now():
    """立即获取事件"""
    try:
        from services.events_service import get_events_service

        service = get_events_service()
        service._fetch_and_cache_events()

        log_system("手动触发事件获取")

        return jsonify({
            'success': True,
            'message': '事件获取完成'
        })
    except Exception as e:
        log_error("手动获取事件失败", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/events/clear', methods=['POST'])
def events_clear():
    """清理所有事件缓存"""
    try:
        from models.events import get_events_collection, get_events_count

        # 获取当前数量
        count_before = get_events_count()

        # 清理数据
        collection = get_events_collection()
        result = collection.delete_many({})

        log_system(f"清理事件缓存: 删除了 {result.deleted_count} 个事件")

        return jsonify({
            'success': True,
            'message': f'已清理 {result.deleted_count} 个事件',
            'data': {
                'deleted_count': result.deleted_count,
                'count_before': count_before
            }
        })
    except Exception as e:
        log_error("清理事件缓存失败", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/events/detail/<event_id>', methods=['GET'])
def events_detail(event_id):
    """获取事件详情"""
    try:
        from models.events import get_event_by_id

        # 获取语言参数
        lang = request.args.get('lang', 'en')

        # 获取事件
        event = get_event_by_id(event_id)

        if not event:
            return jsonify({
                'success': False,
                'message': '事件不存在'
            }), 404

        # 转换 ObjectId 为字符串
        if '_id' in event:
            event['_id'] = str(event['_id'])

        # 根据语言处理数据
        if lang == 'cn':
            # 中文模式：优先使用翻译
            detail = {
                'event_id': event.get('event_id'),
                'title': event.get('title_cn') or event.get('title', ''),
                'summary': event.get('summary_cn') or event.get('summary', ''),
                'description': event.get('description_cn') or event.get('description', ''),
                'location': event.get('location_cn') or event.get('location', ''),
                'timestamp': event.get('timestamp'),
                'severity': event.get('severity', 'medium'),
                'key_points': event.get('key_points', []),
                'has_translation': bool(event.get('title_cn'))
            }

            # 翻译关键点
            if detail['key_points'] and event.get('key_points_cn'):
                detail['key_points'] = event.get('key_points_cn')

        else:
            # 英文模式：使用原始数据
            detail = {
                'event_id': event.get('event_id'),
                'title': event.get('title', ''),
                'summary': event.get('summary', ''),
                'description': event.get('description', ''),
                'location': event.get('location', ''),
                'timestamp': event.get('timestamp'),
                'severity': event.get('severity', 'medium'),
                'key_points': event.get('key_points', []),
                'has_translation': bool(event.get('title_cn'))
            }

        return jsonify({
            'success': True,
            'data': detail
        })

    except Exception as e:
        log_error(f"获取事件详情失败: {event_id}", str(e))
        return jsonify({'success': False, 'message': str(e)}), 500


