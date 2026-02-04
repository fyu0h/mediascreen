# -*- coding: utf-8 -*-
"""
REST API 路由
提供统计数据、文章查询、地图数据、风控监控等接口
"""

import time
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
    init_default_risk_keywords,
    get_alerts_count_by_day
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
        # 确保默认关键词已初始化
        init_default_risk_keywords()
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


# ==================== 订阅管理接口 ====================

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
    获取所有订阅站点
    返回：站点列表
    """
    try:
        data = get_all_sites()
        return success_response(data)
    except Exception as e:
        return error_response(f'获取站点列表失败: {str(e)}', 500)


@api_bp.route('/sites', methods=['POST'])
def sites_add():
    """
    添加新站点
    请求体：{name: "站点名称", url: "站点URL", auto_detect: true/false}
    """
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        name = data.get('name', '').strip()
        url = data.get('url', '').strip()
        auto_detect = data.get('auto_detect', True)

        if not name:
            return error_response('站点名称不能为空', 400)
        if not url:
            return error_response('站点 URL 不能为空', 400)

        site = add_site(name, url, auto_detect)

        log_operation(
            action=f'添加站点: {name}',
            details={'url': url, 'auto_detect': auto_detect, 'site_id': site.get('id')},
            status='success'
        )

        return success_response(site)
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        return error_response(f'添加站点失败: {str(e)}', 500)


@api_bp.route('/sites/<site_id>', methods=['GET'])
def sites_get(site_id: str):
    """获取单个站点信息"""
    try:
        site = get_site(site_id)
        if site:
            return success_response(site)
        return error_response('站点不存在', 404)
    except Exception as e:
        return error_response(f'获取站点失败: {str(e)}', 500)


@api_bp.route('/sites/<site_id>', methods=['PUT'])
def sites_update(site_id: str):
    """
    更新站点信息
    请求体：{name, url, country_code, status, fetch_method}（均可选）
    """
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        site = update_site(
            site_id,
            name=data.get('name'),
            url=data.get('url'),
            country_code=data.get('country_code'),
            status=data.get('status'),
            fetch_method=data.get('fetch_method')
        )

        if site:
            return success_response(site)
        return error_response('站点不存在', 404)
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        return error_response(f'更新站点失败: {str(e)}', 500)


@api_bp.route('/sites/<site_id>', methods=['DELETE'])
def sites_delete(site_id: str):
    """删除站点"""
    try:
        site = get_site(site_id)
        if delete_site(site_id):
            log_operation(
                action=f'删除站点: {site.get("name") if site else site_id}',
                details={'site_id': site_id},
                status='success'
            )
            return success_response({'message': '删除成功'})
        return error_response('站点不存在', 404)
    except Exception as e:
        return error_response(f'删除站点失败: {str(e)}', 500)


@api_bp.route('/sites/<site_id>/recheck', methods=['POST'])
def sites_recheck(site_id: str):
    """重新检测站点的 sitemap 支持"""
    try:
        result = recheck_sitemap(site_id)
        return success_response(result)
    except ValueError as e:
        return error_response(str(e), 400)
    except Exception as e:
        return error_response(f'检测失败: {str(e)}', 500)


@api_bp.route('/sites/check-url', methods=['POST'])
def sites_check_url():
    """
    检测 URL 的 sitemap 支持（不保存）
    请求体：{url: "站点URL"}
    """
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        url = data.get('url', '').strip()
        if not url:
            return error_response('URL 不能为空', 400)

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        result = check_sitemap(url)
        return success_response(result)
    except Exception as e:
        return error_response(f'检测失败: {str(e)}', 500)


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
    批量导入站点
    请求体：{sites: [{name: "名称", url: "URL"}, ...], auto_detect: true/false}
    """
    try:
        data = request.get_json()
        if not data:
            return error_response('请求体不能为空', 400)

        sites_data = data.get('sites', [])
        auto_detect = data.get('auto_detect', False)  # 批量导入默认不检测

        if not sites_data:
            return error_response('站点列表不能为空', 400)

        results = {
            'success': [],
            'failed': []
        }

        for item in sites_data:
            name = item.get('name', '').strip()
            url = item.get('url', '').strip()

            if not name or not url:
                results['failed'].append({
                    'name': name or '(空)',
                    'url': url or '(空)',
                    'error': '名称或URL为空'
                })
                continue

            try:
                site = add_site(name, url, auto_detect=auto_detect)
                results['success'].append({
                    'id': site['id'],
                    'name': site['name'],
                    'url': site['url'],
                    'country_code': site.get('country_code'),
                    'fetch_method': site.get('fetch_method')
                })
            except ValueError as e:
                results['failed'].append({
                    'name': name,
                    'url': url,
                    'error': str(e)
                })
            except Exception as e:
                results['failed'].append({
                    'name': name,
                    'url': url,
                    'error': f'导入失败: {str(e)}'
                })

        return success_response(results)
    except Exception as e:
        return error_response(f'批量导入失败: {str(e)}', 500)


@api_bp.route('/sites/batch-check', methods=['POST'])
def sites_batch_check():
    """
    一键检测所有站点的 sitemap 支持
    返回：检测结果列表
    """
    try:
        sites = get_all_sites()
        results = {
            'total': len(sites),
            'checked': 0,
            'sitemap': 0,
            'crawler': 0,
            'details': []
        }

        for site in sites:
            site_id = site.get('id')
            if not site_id:
                continue

            try:
                check_result = recheck_sitemap(site_id)
                updated_site = check_result['site']
                is_sitemap = updated_site.get('fetch_method') == 'sitemap'

                results['checked'] += 1
                if is_sitemap:
                    results['sitemap'] += 1
                else:
                    results['crawler'] += 1

                results['details'].append({
                    'id': site_id,
                    'name': updated_site.get('name'),
                    'fetch_method': updated_site.get('fetch_method'),
                    'sitemap_url': updated_site.get('sitemap_url'),
                    'success': True
                })
            except Exception as e:
                results['details'].append({
                    'id': site_id,
                    'name': site.get('name'),
                    'error': str(e),
                    'success': False
                })

        return success_response(results)
    except Exception as e:
        return error_response(f'批量检测失败: {str(e)}', 500)


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

        # 遮蔽 LLM API Key
        if 'llm' in settings and settings['llm'].get('api_key'):
            settings['llm']['api_key_masked'] = mask_api_key(settings['llm']['api_key'])
            settings['llm']['api_key_set'] = True
        else:
            settings['llm'] = settings.get('llm', {})
            settings['llm']['api_key_masked'] = ''
            settings['llm']['api_key_set'] = False

        # 不返回原始 API Key
        if 'llm' in settings:
            settings['llm'].pop('api_key', None)

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

        # 更新 LLM 设置
        if 'llm' in data:
            llm = data['llm']
            if 'provider' in llm:
                current_settings['llm']['provider'] = llm['provider'].strip()
            if 'api_url' in llm:
                current_settings['llm']['api_url'] = llm['api_url'].strip()
            if 'api_key' in llm and llm['api_key']:  # 只有提供了新的 key 才更新
                current_settings['llm']['api_key'] = llm['api_key'].strip()
            if 'model' in llm:
                current_settings['llm']['model'] = llm['model'].strip()

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

        api_url = data.get('api_url', '').strip()
        api_key = data.get('api_key', '').strip()
        model = data.get('model', '').strip()
        use_saved = data.get('use_saved', False)

        # 如果使用已保存的配置
        if use_saved or not api_key:
            config = get_llm_config()
            api_key = config.get('api_key', '')
            if not api_url:
                api_url = config.get('api_url', '')
            if not model:
                model = config.get('model', '')

        if not api_url or not api_key:
            return error_response('API URL 和 API Key 不能为空', 400)

        if not model:
            model = 'deepseek-ai/DeepSeek-V3'

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

from crawlers import SitemapCrawler, AICrawler
from models.mongo import save_articles, get_articles_collection


@api_bp.route('/crawl/sitemap/<site_id>', methods=['POST'])
def crawl_sitemap(site_id: str):
    """
    使用 Sitemap 方式爬取站点文章
    """
    try:
        site = get_site(site_id)
        if not site:
            return error_response('站点不存在', 404)

        if not site.get('sitemap_url'):
            return error_response('该站点未配置 Sitemap URL', 400)

        crawler = SitemapCrawler()
        result = crawler.crawl(site, max_articles=500)

        if not result['success']:
            return error_response(result.get('error', '爬取失败'), 500)

        # 保存文章到数据库
        articles = result.get('articles', [])
        saved_count = 0
        if articles:
            saved_count = save_articles(articles)

        return success_response({
            'site_id': site_id,
            'site_name': site.get('name'),
            'method': 'sitemap',
            'fetched': len(articles),
            'saved': saved_count
        })
    except Exception as e:
        return error_response(f'爬取失败: {str(e)}', 500)


@api_bp.route('/crawl/ai/<site_id>', methods=['POST'])
def crawl_ai(site_id: str):
    """
    使用 AI 方式爬取站点文章
    """
    try:
        site = get_site(site_id)
        if not site:
            return error_response('站点不存在', 404)

        # 从设置获取 API 配置
        llm_config = get_llm_config()
        if not llm_config.get('api_key'):
            return error_response('未配置 API Key，请在设置中配置', 400)

        crawler = AICrawler(
            api_key=llm_config['api_key'],
            api_url=llm_config['api_url'],
            model=llm_config.get('model', 'deepseek-ai/DeepSeek-V3')
        )
        result = crawler.crawl(site, max_articles=100)

        if not result['success']:
            return error_response(result.get('error', '爬取失败'), 500)

        # 保存文章到数据库
        articles = result.get('articles', [])
        saved_count = 0
        if articles:
            saved_count = save_articles(articles)

        return success_response({
            'site_id': site_id,
            'site_name': site.get('name'),
            'method': 'ai',
            'fetched': len(articles),
            'saved': saved_count
        })
    except Exception as e:
        return error_response(f'爬取失败: {str(e)}', 500)


@api_bp.route('/crawl/batch', methods=['POST'])
def crawl_batch():
    """
    批量爬取所有站点
    请求体：{method: "auto"|"sitemap"|"ai"} - auto 根据站点配置自动选择
    """
    try:
        data = request.get_json() or {}
        method = data.get('method', 'auto')

        sites = get_all_sites()
        results = {
            'total': len(sites),
            'success': 0,
            'failed': 0,
            'total_articles': 0,
            'details': []
        }

        sitemap_crawler = SitemapCrawler()
        ai_crawler = None
        llm_config = get_llm_config()
        if llm_config.get('api_key'):
            ai_crawler = AICrawler(
                api_key=llm_config['api_key'],
                api_url=llm_config['api_url'],
                model=llm_config.get('model', 'deepseek-ai/DeepSeek-V3')
            )

        for site in sites:
            site_id = site.get('id')
            site_name = site.get('name', '')
            fetch_method = site.get('fetch_method', 'unknown')

            try:
                # 选择爬取方式
                use_sitemap = False
                if method == 'sitemap':
                    use_sitemap = True
                elif method == 'ai':
                    use_sitemap = False
                else:  # auto
                    use_sitemap = fetch_method == 'sitemap' and site.get('sitemap_url')

                if use_sitemap:
                    if not site.get('sitemap_url'):
                        raise ValueError('未配置 Sitemap URL')
                    result = sitemap_crawler.crawl(site)
                else:
                    if not ai_crawler:
                        raise ValueError('未配置 DeepSeek API Key')
                    result = ai_crawler.crawl(site)

                if result['success']:
                    articles = result.get('articles', [])
                    saved_count = save_articles(articles) if articles else 0
                    results['success'] += 1
                    results['total_articles'] += saved_count
                    results['details'].append({
                        'id': site_id,
                        'name': site_name,
                        'method': 'sitemap' if use_sitemap else 'ai',
                        'fetched': len(articles),
                        'saved': saved_count,
                        'success': True
                    })
                else:
                    raise ValueError(result.get('error', '爬取失败'))

            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'id': site_id,
                    'name': site_name,
                    'error': str(e),
                    'success': False
                })

        return success_response(results)
    except Exception as e:
        return error_response(f'批量爬取失败: {str(e)}', 500)


@api_bp.route('/crawl/batch/stream', methods=['GET'])
def crawl_batch_stream():
    """
    批量爬取所有站点（SSE 流式返回进度）
    参数：method - auto|sitemap|ai
    返回：Server-Sent Events 流
    """
    from flask import Response
    import json

    method = request.args.get('method', 'auto')

    def generate():
        sites = get_all_sites()
        total = len(sites)

        # 发送初始化事件
        yield f"data: {json.dumps({'type': 'init', 'total': total})}\n\n"

        if total == 0:
            yield f"data: {json.dumps({'type': 'complete', 'success': 0, 'failed': 0, 'total_articles': 0})}\n\n"
            return

        sitemap_crawler = SitemapCrawler()
        ai_crawler = None
        llm_config = get_llm_config()
        if llm_config.get('api_key'):
            ai_crawler = AICrawler(
                api_key=llm_config['api_key'],
                api_url=llm_config['api_url'],
                model=llm_config.get('model', 'deepseek-ai/DeepSeek-V3')
            )

        success_count = 0
        failed_count = 0
        total_articles = 0

        for index, site in enumerate(sites):
            site_id = site.get('id')
            site_name = site.get('name', '')
            fetch_method = site.get('fetch_method', 'unknown')

            # 发送进度事件 - 开始处理该站点
            yield f"data: {json.dumps({'type': 'progress', 'current': index + 1, 'total': total, 'site_id': site_id, 'site_name': site_name, 'status': 'processing'})}\n\n"

            try:
                # 选择爬取方式
                use_sitemap = False
                if method == 'sitemap':
                    use_sitemap = True
                elif method == 'ai':
                    use_sitemap = False
                else:  # auto
                    use_sitemap = fetch_method == 'sitemap' and site.get('sitemap_url')

                if use_sitemap:
                    if not site.get('sitemap_url'):
                        raise ValueError('未配置 Sitemap URL')
                    result = sitemap_crawler.crawl(site)
                else:
                    if not ai_crawler:
                        raise ValueError('未配置 API Key')
                    result = ai_crawler.crawl(site)

                if result['success']:
                    articles = result.get('articles', [])
                    saved_count = save_articles(articles) if articles else 0
                    success_count += 1
                    total_articles += saved_count

                    # 发送该站点成功事件
                    yield f"data: {json.dumps({'type': 'site_done', 'current': index + 1, 'total': total, 'site_id': site_id, 'site_name': site_name, 'success': True, 'method': 'sitemap' if use_sitemap else 'ai', 'fetched': len(articles), 'saved': saved_count, 'success_count': success_count, 'failed_count': failed_count, 'total_articles': total_articles})}\n\n"
                else:
                    raise ValueError(result.get('error', '爬取失败'))

            except Exception as e:
                failed_count += 1
                # 发送该站点失败事件
                yield f"data: {json.dumps({'type': 'site_done', 'current': index + 1, 'total': total, 'site_id': site_id, 'site_name': site_name, 'success': False, 'error': str(e), 'success_count': success_count, 'failed_count': failed_count, 'total_articles': total_articles})}\n\n"

        # 发送完成事件
        yield f"data: {json.dumps({'type': 'complete', 'success': success_count, 'failed': failed_count, 'total_articles': total_articles})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


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
