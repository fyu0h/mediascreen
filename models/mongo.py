# -*- coding: utf-8 -*-
"""
MongoDB 连接与查询封装
"""

import atexit
from typing import Optional, Dict, List, Any, Iterator
from datetime import datetime, timedelta
import re
import threading

from pymongo import MongoClient as PyMongoClient
from pymongo.database import Database
from pymongo.collection import Collection

from config import Config

# 全局单例连接（PyMongo 的 MongoClient 本身是线程安全的）
_client: Optional[PyMongoClient] = None
_db: Optional[Database] = None
_lock = threading.Lock()

# 连接池配置
_POOL_MAX_SIZE = 50  # 最大连接数
_POOL_MIN_SIZE = 5   # 最小连接数


def get_db() -> Database:
    """
    获取数据库连接（全局单例，线程安全）
    PyMongo 的 MongoClient 内部已有连接池，所有线程共享即可
    """
    global _client, _db
    if _db is None:
        with _lock:
            if _db is None:
                _client = PyMongoClient(
                    Config.get_mongo_uri(),
                    maxPoolSize=_POOL_MAX_SIZE,
                    minPoolSize=_POOL_MIN_SIZE,
                    serverSelectionTimeoutMS=5000,  # 服务器选择超时 5秒
                    connectTimeoutMS=5000,           # 连接超时 5秒
                    socketTimeoutMS=30000,           # Socket 超时 30秒
                )
                _db = _client[Config.MONGO_DB]
    return _db


def close_db() -> None:
    """关闭数据库连接（通常在应用退出时调用）"""
    global _client, _db
    with _lock:
        if _client:
            _client.close()
            _client = None
            _db = None


# 注册退出时自动清理连接
atexit.register(close_db)


def ensure_articles_indexes() -> None:
    """
    创建 news_articles 集合的索引
    在应用启动时调用，提升查询性能
    """
    collection = get_articles_collection()

    try:
        # 获取现有索引名称
        existing_indexes = set(collection.index_information().keys())

        # 定义需要创建的索引
        indexes_to_create = []

        # 1. loc 唯一索引（用于去重检查）
        if 'loc_1' not in existing_indexes:
            from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT
            indexes_to_create.append(IndexModel([('loc', ASCENDING)], unique=True, name='loc_1'))

        # 2. fetched_at 降序索引（时间线查询）
        if 'fetched_at_-1' not in existing_indexes:
            from pymongo import IndexModel, DESCENDING
            indexes_to_create.append(IndexModel([('fetched_at', DESCENDING)], name='fetched_at_-1'))

        # 3. pub_date 降序索引（发布日期查询）
        if 'pub_date_-1' not in existing_indexes:
            from pymongo import IndexModel, DESCENDING
            indexes_to_create.append(IndexModel([('pub_date', DESCENDING)], name='pub_date_-1'))

        # 4. source_name 索引（按来源筛选）
        if 'source_name_1' not in existing_indexes:
            from pymongo import IndexModel, ASCENDING
            indexes_to_create.append(IndexModel([('source_name', ASCENDING)], name='source_name_1'))

        # 5. country_code 索引（按国家筛选）
        if 'country_code_1' not in existing_indexes:
            from pymongo import IndexModel, ASCENDING
            indexes_to_create.append(IndexModel([('country_code', ASCENDING)], name='country_code_1'))

        # 6. 复合索引 (pub_date, source_name)（常见组合查询）
        if 'pub_date_-1_source_name_1' not in existing_indexes:
            from pymongo import IndexModel, ASCENDING, DESCENDING
            indexes_to_create.append(IndexModel(
                [('pub_date', DESCENDING), ('source_name', ASCENDING)],
                name='pub_date_-1_source_name_1'
            ))

        # 7. title 文本索引（加速关键词搜索）
        if 'title_text' not in existing_indexes:
            from pymongo import IndexModel, TEXT
            indexes_to_create.append(IndexModel(
                [('title', TEXT)],
                name='title_text',
                default_language='none'  # 禁用语言分词，兼容中文
            ))

        # 批量创建索引
        if indexes_to_create:
            collection.create_indexes(indexes_to_create)
            print(f"[MongoDB] 已为 news_articles 创建 {len(indexes_to_create)} 个索引")

    except Exception as e:
        print(f"[MongoDB] 创建索引时出错: {e}")


def get_articles_collection() -> Collection:
    """获取文章集合"""
    return get_db()[Config.COLLECTION_ARTICLES]


def get_sources_collection() -> Collection:
    """获取新闻源集合"""
    return get_db()[Config.COLLECTION_SOURCES]


def get_keywords_collection() -> Collection:
    """获取关键词集合"""
    return get_db()['risk_keywords']


def get_alert_reads_collection() -> Collection:
    """获取告警已读记录集合"""
    return get_db()['alert_reads']


# ==================== 文章保存 ====================

def save_articles(articles: List[Dict[str, Any]], translate: bool = True) -> int:
    """
    保存文章到数据库（去重）
    参数：
        articles: 文章列表
        translate: 是否翻译非中文标题
    返回：新增的文章数量
    """
    if not articles:
        return 0

    # 如果启用翻译，处理标题
    if translate:
        try:
            from plugins.translator import process_articles_translation
            articles = process_articles_translation(articles)
        except Exception as e:
            print(f"[翻译] 标题翻译失败: {e}")

    collection = get_articles_collection()
    saved_count = 0

    for article in articles:
        loc = article.get('loc')
        if not loc:
            continue

        # 获取标题（优先使用翻译后的标题）
        title = article.get('title_cn') or article.get('title', '')
        title_original = article.get('title_original', '')

        # 使用 upsert 避免重复
        try:
            update_data = {
                '$set': {
                    'title': title,
                    'source_name': article.get('source_name', ''),
                    'country_code': article.get('country_code', ''),
                    'coords': article.get('coords', []),
                    'summary': article.get('summary', ''),
                    'lastmod': article.get('lastmod'),
                    'updated_at': datetime.now()
                },
                '$setOnInsert': {
                    'loc': loc,
                    'pub_date': article.get('pub_date'),
                    'imported_at': datetime.now()
                }
            }

            # 如果有原始标题，也保存
            if title_original:
                update_data['$set']['title_original'] = title_original

            result = collection.update_one(
                {'loc': loc},
                update_data,
                upsert=True
            )
            if result.upserted_id:
                saved_count += 1
        except Exception as e:
            print(f"保存文章失败: {loc}, 错误: {e}")

    return saved_count


def article_exists(url: str) -> bool:
    """检查文章是否已存在（使用 find_one 比 count_documents 更高效）"""
    if not url:
        return False
    collection = get_articles_collection()
    return collection.find_one({'loc': url}, {'_id': 1}) is not None


# ==================== 统计查询 ====================

def get_overview_stats() -> Dict[str, Any]:
    """
    获取概览统计数据
    返回：总文章数、源数、国家数、日期范围
    """
    articles = get_articles_collection()

    # 使用 estimated_document_count() 替代 count_documents({})
    # 前者基于集合元数据返回近似总数，无需全表扫描，性能远优于后者
    total_articles = articles.estimated_document_count()

    # 从插件系统获取已启用的站点数和国家数
    try:
        from plugins.registry import plugin_registry, register_builtin_plugins
        # 确保插件已注册
        if len(plugin_registry.get_all_plugins()) == 0:
            register_builtin_plugins()

        from models.plugins import get_enabled_sites
        enabled_sites = get_enabled_sites()
        total_sources = len(enabled_sites)
        # 统计已启用站点覆盖的国家
        enabled_countries = set(site.get('country_code') for site in enabled_sites if site.get('country_code'))
        total_countries = len(enabled_countries)
    except Exception as e:
        print(f"[统计] 获取插件站点失败: {e}")
        total_sources = 0
        total_countries = 0

    # 获取日期范围（只统计有 pub_date 的记录）
    date_pipeline = [
        {'$match': {'pub_date': {'$ne': None}}},
        {'$group': {
            '_id': None,
            'min_date': {'$min': '$pub_date'},
            'max_date': {'$max': '$pub_date'}
        }}
    ]
    date_result = list(articles.aggregate(date_pipeline))

    date_range = None
    if date_result:
        min_date = date_result[0].get('min_date')
        max_date = date_result[0].get('max_date')
        if min_date and max_date:
            date_range = {
                'start': min_date.strftime('%Y-%m-%d') if isinstance(min_date, datetime) else str(min_date)[:10],
                'end': max_date.strftime('%Y-%m-%d') if isinstance(max_date, datetime) else str(max_date)[:10]
            }

    return {
        'total_articles': total_articles,
        'total_sources': total_sources,
        'total_countries': total_countries,
        'date_range': date_range
    }


def get_source_stats() -> List[Dict[str, Any]]:
    """
    获取各源文章数量统计
    返回：按文章数量降序排列的列表
    """
    articles = get_articles_collection()

    pipeline = [
        {'$group': {
            '_id': '$source_name',
            'count': {'$sum': 1}
        }},
        {'$sort': {'count': -1}},
        {'$project': {
            '_id': 0,
            'source': '$_id',
            'count': 1
        }}
    ]

    return list(articles.aggregate(pipeline))


def get_trend_stats(days: int = 30) -> List[Dict[str, Any]]:
    """
    获取时间趋势统计
    参数：days - 统计天数
    返回：按日期排序的每日文章数量
    """
    articles = get_articles_collection()

    # 计算起始日期
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    pipeline = [
        {'$match': {
            'pub_date': {
                '$gte': start_date,
                '$lte': end_date
            }
        }},
        {'$group': {
            '_id': {
                '$dateToString': {
                    'format': '%Y-%m-%d',
                    'date': '$pub_date'
                }
            },
            'count': {'$sum': 1}
        }},
        {'$sort': {'_id': 1}},
        {'$project': {
            '_id': 0,
            'date': '$_id',
            'count': 1
        }}
    ]

    return list(articles.aggregate(pipeline))


def get_country_stats() -> List[Dict[str, Any]]:
    """
    获取按国家统计的文章数量
    返回：按文章数量降序排列的列表
    """
    articles = get_articles_collection()

    pipeline = [
        {'$match': {'country_code': {'$ne': None}}},
        {'$group': {
            '_id': '$country_code',
            'count': {'$sum': 1}
        }},
        {'$sort': {'count': -1}},
        {'$project': {
            '_id': 0,
            'country': '$_id',
            'count': 1
        }}
    ]

    return list(articles.aggregate(pipeline))


# ==================== 文章查询 ====================

def search_articles(
    source: Optional[str] = None,
    keyword: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20
) -> Dict[str, Any]:
    """
    搜索文章
    参数：
        source: 新闻源名称
        keyword: 关键词（标题模糊搜索）
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        page: 页码
        page_size: 每页数量
    返回：包含文章列表和分页信息的字典
    """
    articles = get_articles_collection()

    # 构建查询条件
    query: Dict[str, Any] = {}

    if source:
        query['source_name'] = source

    if keyword:
        # 使用正则表达式进行模糊搜索（中文兼容性好）
        query['title'] = {'$regex': re.escape(keyword), '$options': 'i'}

    if start_date or end_date:
        date_query: Dict[str, Any] = {}
        if start_date:
            try:
                date_query['$gte'] = datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                pass
        if end_date:
            try:
                # 结束日期包含当天，所以加一天
                date_query['$lte'] = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            except ValueError:
                pass
        if date_query:
            query['pub_date'] = date_query

    # 计算总数
    total = articles.count_documents(query)

    # 分页查询
    skip = (page - 1) * page_size
    cursor = articles.find(query).sort('pub_date', -1).skip(skip).limit(page_size)

    # 格式化结果
    items = []
    for doc in cursor:
        item = {
            'title': doc.get('title', ''),
            'url': doc.get('loc', ''),
            'source': doc.get('source_name', ''),
            'pub_date': None,
            'country': doc.get('country_code', '')
        }
        pub_date = doc.get('pub_date')
        if pub_date:
            if isinstance(pub_date, datetime):
                item['pub_date'] = pub_date.strftime('%Y-%m-%d %H:%M')
            else:
                item['pub_date'] = str(pub_date)[:16]
        items.append(item)

    return {
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size
    }


# ==================== 地图数据 ====================

def get_map_markers() -> List[Dict[str, Any]]:
    """
    获取地图标记数据
    返回：包含坐标、文章数量和风控状态的标记列表
    """
    articles = get_articles_collection()

    # 获取所有风控关键词
    keywords_by_level = get_risk_keywords_flat()
    all_keywords = []
    keyword_levels = {}
    for level, keywords in keywords_by_level.items():
        for kw in keywords:
            all_keywords.append(kw)
            keyword_levels[kw.lower()] = level

    pipeline = [
        {'$match': {'coords': {'$ne': None}}},
        {'$group': {
            '_id': {
                'source': '$source_name',
                'coords': '$coords',
                'country': '$country_code'
            },
            'count': {'$sum': 1},
            'titles': {'$push': '$title'}  # 收集所有标题用于风控匹配
        }},
        {'$project': {
            '_id': 0,
            'source': '$_id.source',
            'coords': '$_id.coords',
            'country': '$_id.country',
            'count': 1,
            'titles': 1
        }}
    ]

    results = list(articles.aggregate(pipeline))

    # 为每个新闻源计算风控等级
    for item in results:
        titles = item.get('titles', [])
        risk_level = None  # 默认无风控警报
        risk_count = 0

        if all_keywords and titles:
            for title in titles:
                if not title:
                    continue
                for kw in all_keywords:
                    if re.search(re.escape(kw), title, re.IGNORECASE):
                        risk_count += 1
                        kw_level = keyword_levels.get(kw.lower(), 'low')
                        if kw_level == 'high':
                            risk_level = 'high'
                        elif kw_level == 'medium' and risk_level != 'high':
                            risk_level = 'medium'
                        elif risk_level is None:
                            risk_level = 'low'
                        break  # 每篇文章只计一次

        item['risk_level'] = risk_level
        item['risk_count'] = risk_count
        del item['titles']  # 不返回标题数组，减少数据量

    return results


# ==================== 新闻源查询 ====================

def get_source_list() -> List[str]:
    """
    获取所有新闻源名称列表
    返回：新闻源名称列表
    """
    sources = get_sources_collection()
    return sources.distinct('name')


def get_all_sources() -> List[Dict[str, Any]]:
    """
    获取所有新闻源详细信息
    返回：新闻源列表
    """
    sources = get_sources_collection()
    result = []
    for doc in sources.find():
        result.append({
            'name': doc.get('name', ''),
            'url': doc.get('url', ''),
            'country_code': doc.get('country_code', ''),
            'coords': doc.get('coords')
        })
    return result


# ==================== 风控关键词监控 ====================

def get_keyword_stats(keywords: List[str], days: int = 7) -> Dict[str, Any]:
    """
    统计关键词匹配的文章数量（优化版：使用聚合管道避免 N+1 查询）
    参数：
        keywords: 关键词列表
        days: 统计天数
    返回：各关键词匹配数量
    """
    if not keywords:
        return []

    articles = get_articles_collection()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # 构建正则表达式匹配所有关键词
    regex_pattern = '|'.join(re.escape(kw) for kw in keywords)

    # 使用聚合管道，一次查询获取所有匹配文章
    pipeline = [
        {
            '$match': {
                'title': {'$regex': regex_pattern, '$options': 'i'},
                'pub_date': {'$gte': start_date, '$lte': end_date}
            }
        },
        {
            '$project': {
                'title': 1
            }
        }
    ]

    # 获取所有匹配的文章标题
    matching_docs = list(articles.aggregate(pipeline))

    # 在内存中统计每个关键词的匹配次数
    keyword_counts = {kw: 0 for kw in keywords}
    for doc in matching_docs:
        title = doc.get('title', '')
        if not title:
            continue
        for kw in keywords:
            if re.search(re.escape(kw), title, re.IGNORECASE):
                keyword_counts[kw] += 1
                break  # 每篇文章只计入第一个匹配的关键词

    # 过滤并排序结果
    results = [{'keyword': kw, 'count': count} for kw, count in keyword_counts.items() if count > 0]
    results.sort(key=lambda x: x['count'], reverse=True)
    return results


def get_risk_alerts(keywords_by_level: Dict[str, List[str]], limit: int = 50,
                    date_str: str = None, filter_keyword: str = None) -> List[Dict[str, Any]]:
    """
    获取风控告警文章列表
    参数：
        keywords_by_level: 按风险等级分类的关键词 {"high": [...], "medium": [...], "low": [...]}
        limit: 返回数量限制
        date_str: 指定日期 (YYYY-MM-DD)，可选
        filter_keyword: 筛选关键词，可选
    返回：匹配风控关键词的文章列表（按时间降序）
    """
    articles = get_articles_collection()

    # 构建所有关键词的正则表达式
    all_keywords = []
    keyword_levels = {}  # 关键词 -> 风险等级映射

    for level, keywords in keywords_by_level.items():
        for kw in keywords:
            all_keywords.append(kw)
            keyword_levels[kw.lower()] = level

    if not all_keywords:
        return []

    # 如果指定了筛选关键词，只用该关键词查询
    if filter_keyword:
        regex_pattern = re.escape(filter_keyword)
    else:
        regex_pattern = '|'.join(re.escape(kw) for kw in all_keywords)

    query = {
        'title': {'$regex': regex_pattern, '$options': 'i'}
    }

    # 添加日期筛选
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
            next_date = target_date + timedelta(days=1)
            query['pub_date'] = {
                '$gte': target_date,
                '$lt': next_date
            }
        except ValueError:
            pass  # 日期格式错误，忽略日期筛选

    cursor = articles.find(query).sort('pub_date', -1).limit(limit)

    # 先收集所有结果和URL
    results = []
    article_urls = []

    for doc in cursor:
        title = doc.get('title', '')
        url = doc.get('loc', '')
        article_urls.append(url)

        # 确定匹配的关键词和风险等级
        matched_level = 'low'
        matched_keywords = []

        for kw in all_keywords:
            if re.search(re.escape(kw), title, re.IGNORECASE):
                matched_keywords.append(kw)
                kw_level = keyword_levels.get(kw.lower(), 'low')
                # 取最高风险等级
                if kw_level == 'high':
                    matched_level = 'high'
                elif kw_level == 'medium' and matched_level != 'high':
                    matched_level = 'medium'

        pub_date = doc.get('pub_date')
        pub_date_str = None
        if pub_date:
            if isinstance(pub_date, datetime):
                pub_date_str = pub_date.strftime('%Y-%m-%d %H:%M')
            else:
                pub_date_str = str(pub_date)[:16]

        results.append({
            'title': title,
            'url': url,
            'source': doc.get('source_name', ''),
            'country': doc.get('country_code', ''),
            'pub_date': pub_date_str,
            'risk_level': matched_level,
            'matched_keywords': matched_keywords[:3]  # 最多显示3个匹配关键词
        })

    # 批量获取已读状态
    read_status = get_read_alerts(article_urls) if article_urls else {}

    # 为每个结果添加已读状态
    for item in results:
        url = item['url']
        if url in read_status:
            item['is_read'] = True
            item['read_at'] = read_status[url].get('read_at', '')
            item['reader_name'] = read_status[url].get('reader_name', '')
        else:
            item['is_read'] = False
            item['read_at'] = None
            item['reader_name'] = None

    return results


def get_alerts_count_by_day(keywords_by_level: Dict[str, List[str]], year: int, month: int) -> Dict[str, int]:
    """
    获取指定月份每天的告警数量
    参数：
        keywords_by_level: 按风险等级分类的关键词
        year: 年份
        month: 月份
    返回：{日期字符串: 数量, ...}
    """
    articles = get_articles_collection()

    # 构建所有关键词
    all_keywords = []
    for level, keywords in keywords_by_level.items():
        all_keywords.extend(keywords)

    if not all_keywords:
        return {}

    # 计算月份的起止日期
    first_day = datetime(year, month, 1)
    if month == 12:
        last_day = datetime(year + 1, 1, 1)
    else:
        last_day = datetime(year, month + 1, 1)

    # 构建查询
    regex_pattern = '|'.join(re.escape(kw) for kw in all_keywords)
    query = {
        'title': {'$regex': regex_pattern, '$options': 'i'},
        'pub_date': {'$gte': first_day, '$lt': last_day}
    }

    # 聚合按天统计
    pipeline = [
        {'$match': query},
        {'$group': {
            '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$pub_date'}},
            'count': {'$sum': 1}
        }},
        {'$sort': {'_id': 1}}
    ]

    results = {}
    for doc in articles.aggregate(pipeline):
        if doc['_id']:
            results[doc['_id']] = doc['count']

    return results


def get_keyword_trend(keyword: str, days: int = 7) -> List[Dict[str, Any]]:
    """
    获取单个关键词的时间趋势
    参数：
        keyword: 关键词
        days: 统计天数
    返回：按日期的匹配数量
    """
    articles = get_articles_collection()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    pipeline = [
        {
            '$match': {
                'title': {'$regex': re.escape(keyword), '$options': 'i'},
                'pub_date': {'$gte': start_date, '$lte': end_date}
            }
        },
        {
            '$group': {
                '_id': {
                    '$dateToString': {
                        'format': '%Y-%m-%d',
                        'date': '$pub_date'
                    }
                },
                'count': {'$sum': 1}
            }
        },
        {'$sort': {'_id': 1}},
        {
            '$project': {
                '_id': 0,
                'date': '$_id',
                'count': 1
            }
        }
    ]

    return list(articles.aggregate(pipeline))


def get_realtime_stats() -> Dict[str, Any]:
    """
    获取实时统计数据（用于大屏展示）
    返回：今日新增、本周新增、活跃源数等
    """
    articles = get_articles_collection()
    now = datetime.now()

    # 今日开始时间
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # 本周开始时间（周一）
    week_start = today_start - timedelta(days=now.weekday())
    # 昨日
    yesterday_start = today_start - timedelta(days=1)

    # 今日新增
    today_count = articles.count_documents({'pub_date': {'$gte': today_start}})

    # 昨日新增（用于计算环比）
    yesterday_count = articles.count_documents({
        'pub_date': {'$gte': yesterday_start, '$lt': today_start}
    })

    # 本周新增
    week_count = articles.count_documents({'pub_date': {'$gte': week_start}})

    # 计算环比变化
    if yesterday_count > 0:
        change_rate = round((today_count - yesterday_count) / yesterday_count * 100, 1)
    else:
        change_rate = 0 if today_count == 0 else 100

    # 今日活跃源（今日有新文章的源数量）
    active_sources = len(articles.distinct('source_name', {'pub_date': {'$gte': today_start}}))

    return {
        'today_count': today_count,
        'yesterday_count': yesterday_count,
        'week_count': week_count,
        'change_rate': change_rate,
        'active_sources': active_sources,
        'update_time': now.strftime('%Y-%m-%d %H:%M:%S')
    }


# ==================== 风控关键词管理 ====================

COLLECTION_RISK_KEYWORDS = 'risk_keywords'


def get_risk_keywords_collection() -> Collection:
    """获取风控关键词集合"""
    return get_db()[COLLECTION_RISK_KEYWORDS]


def get_all_risk_keywords() -> Dict[str, List[Dict[str, Any]]]:
    """
    获取所有风控关键词（按等级分组）
    返回：{high: [{id, keyword}, ...], medium: [...], low: [...]}
    """
    collection = get_risk_keywords_collection()
    result = {'high': [], 'medium': [], 'low': []}

    for doc in collection.find().sort('created_at', -1):
        level = doc.get('level', 'low')
        if level in result:
            result[level].append({
                'id': str(doc['_id']),
                'keyword': doc.get('keyword', ''),
                'created_at': doc.get('created_at', '').strftime('%Y-%m-%d %H:%M') if doc.get('created_at') else ''
            })

    return result


def get_risk_keywords_flat() -> Dict[str, List[str]]:
    """
    获取所有风控关键词（扁平格式，用于匹配）
    返回：{high: [keyword1, ...], medium: [...], low: [...]}
    """
    collection = get_risk_keywords_collection()
    result = {'high': [], 'medium': [], 'low': []}

    for doc in collection.find():
        level = doc.get('level', 'low')
        keyword = doc.get('keyword', '')
        if level in result and keyword:
            result[level].append(keyword)

    return result


def add_risk_keyword(keyword: str, level: str) -> Dict[str, Any]:
    """
    添加风控关键词
    参数：
        keyword: 关键词
        level: 风险等级 (high/medium/low)
    返回：新建的关键词文档
    """
    collection = get_risk_keywords_collection()

    # 检查是否已存在
    existing = collection.find_one({'keyword': keyword})
    if existing:
        raise ValueError(f'关键词 "{keyword}" 已存在')

    # 验证等级
    if level not in ['high', 'medium', 'low']:
        raise ValueError('风险等级必须是 high、medium 或 low')

    doc = {
        'keyword': keyword.strip(),
        'level': level,
        'created_at': datetime.now()
    }

    result = collection.insert_one(doc)
    doc['id'] = str(result.inserted_id)
    return doc


def update_risk_keyword(keyword_id: str, keyword: Optional[str] = None, level: Optional[str] = None) -> bool:
    """
    更新风控关键词
    参数：
        keyword_id: 关键词ID
        keyword: 新关键词（可选）
        level: 新风险等级（可选）
    返回：是否更新成功
    """
    from bson import ObjectId

    collection = get_risk_keywords_collection()

    update_fields = {}
    if keyword is not None:
        # 检查新关键词是否与其他记录重复
        existing = collection.find_one({
            'keyword': keyword,
            '_id': {'$ne': ObjectId(keyword_id)}
        })
        if existing:
            raise ValueError(f'关键词 "{keyword}" 已存在')
        update_fields['keyword'] = keyword.strip()

    if level is not None:
        if level not in ['high', 'medium', 'low']:
            raise ValueError('风险等级必须是 high、medium 或 low')
        update_fields['level'] = level

    if not update_fields:
        return False

    update_fields['updated_at'] = datetime.now()

    result = collection.update_one(
        {'_id': ObjectId(keyword_id)},
        {'$set': update_fields}
    )

    return result.modified_count > 0


def delete_risk_keyword(keyword_id: str) -> bool:
    """
    删除风控关键词
    参数：
        keyword_id: 关键词ID
    返回：是否删除成功
    """
    from bson import ObjectId

    collection = get_risk_keywords_collection()
    result = collection.delete_one({'_id': ObjectId(keyword_id)})
    return result.deleted_count > 0


def init_default_risk_keywords() -> int:
    """
    初始化默认风控关键词（如果集合为空）
    返回：插入的关键词数量
    """
    from config import RISK_KEYWORDS

    collection = get_risk_keywords_collection()

    # 如果已有数据则跳过
    if collection.count_documents({}) > 0:
        return 0

    # 创建唯一索引
    collection.create_index('keyword', unique=True)

    # 插入默认关键词
    docs = []
    now = datetime.now()
    for level, keywords in RISK_KEYWORDS.items():
        for kw in keywords:
            docs.append({
                'keyword': kw,
                'level': level,
                'created_at': now
            })

    if docs:
        collection.insert_many(docs)

    return len(docs)


# ==================== 告警已读管理 ====================

def mark_alert_read(article_url: str, reader_name: str = None) -> bool:
    """
    标记告警为已读
    参数：
        article_url: 文章URL（唯一标识）
        reader_name: 阅读者姓名（可选）
    返回：是否成功
    """
    collection = get_alert_reads_collection()

    try:
        collection.update_one(
            {'article_url': article_url},
            {
                '$set': {
                    'article_url': article_url,
                    'read_at': datetime.now(),
                    'reader_name': reader_name
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        print(f"标记已读失败: {e}")
        return False


def get_read_alerts(article_urls: List[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    获取告警已读状态
    参数：
        article_urls: 文章URL列表，为空则返回所有
    返回：{article_url: {read_at, reader_name}, ...}
    """
    collection = get_alert_reads_collection()

    query = {}
    if article_urls:
        query = {'article_url': {'$in': article_urls}}

    result = {}
    for doc in collection.find(query):
        url = doc.get('article_url')
        read_at = doc.get('read_at')
        result[url] = {
            'read_at': read_at.strftime('%Y-%m-%d %H:%M') if isinstance(read_at, datetime) else str(read_at)[:16],
            'reader_name': doc.get('reader_name', '')
        }

    return result


def is_alert_read(article_url: str) -> bool:
    """
    检查告警是否已读
    参数：
        article_url: 文章URL
    返回：是否已读
    """
    collection = get_alert_reads_collection()
    return collection.find_one({'article_url': article_url}, {'_id': 1}) is not None


def ensure_alert_reads_indexes() -> None:
    """
    创建 alert_reads 集合的索引
    在应用启动时调用，提升告警已读查询性能
    """
    collection = get_alert_reads_collection()

    try:
        # 获取现有索引名称
        existing_indexes = set(collection.index_information().keys())

        indexes_to_create = []

        # article_url 唯一索引（每篇文章只有一条已读记录）
        if 'article_url_1' not in existing_indexes:
            from pymongo import IndexModel, ASCENDING
            indexes_to_create.append(IndexModel(
                [('article_url', ASCENDING)],
                unique=True,
                name='article_url_1'
            ))

        # 批量创建索引
        if indexes_to_create:
            collection.create_indexes(indexes_to_create)
            print(f"[MongoDB] 已为 alert_reads 创建 {len(indexes_to_create)} 个索引")

    except Exception as e:
        print(f"[MongoDB] 创建 alert_reads 索引时出错: {e}")


# ==================== 预览缓存 ====================


def get_preview_cache_collection():
    """获取预览缓存集合"""
    db = get_db()
    return db['preview_cache']


def init_preview_cache_index():
    """初始化预览缓存 TTL 索引（8小时过期）"""
    try:
        col = get_preview_cache_collection()
        # 检查是否已存在 TTL 索引
        existing = col.index_information()
        if 'cached_at_1' not in existing:
            col.create_index('cached_at', expireAfterSeconds=28800)
            print("[MongoDB] 已为 preview_cache 创建 TTL 索引（8小时过期）")
    except Exception as e:
        print(f"[MongoDB] 创建 preview_cache 索引时出错: {e}")


# ==================== 站点健康度监控 ====================


def get_site_health_collection():
    """获取站点健康度集合"""
    db = get_db()
    return db['site_health']


def record_site_health(site_id: str, domain: str, success: bool, error_msg: str = ''):
    """记录站点抓取结果"""
    from datetime import datetime
    try:
        col = get_site_health_collection()
        update_doc = {
            '$set': {
                'domain': domain,
                'last_attempt': datetime.utcnow(),
                'last_error': error_msg if not success else '',
            },
            '$inc': {
                'total_attempts': 1,
                'total_successes': 1 if success else 0,
                'total_failures': 0 if success else 1,
            },
            '$setOnInsert': {'site_id': site_id}
        }
        # 成功时更新 last_success 并重置连续失败计数
        if success:
            update_doc['$set']['last_success'] = datetime.utcnow()
            update_doc['$set']['consecutive_failures'] = 0
        else:
            update_doc['$inc']['consecutive_failures'] = 1

        col.update_one({'site_id': site_id}, update_doc, upsert=True)
    except Exception:
        pass


def get_sites_health() -> list:
    """获取所有站点健康度列表"""
    try:
        col = get_site_health_collection()
        return list(col.find({}, {'_id': 0}).sort('consecutive_failures', -1))
    except Exception:
        return []
