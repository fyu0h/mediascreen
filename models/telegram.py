# -*- coding: utf-8 -*-
"""
Telegram 监控数据模型
管理账号、群组、消息、关键词、报警的 CRUD 操作
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from bson import ObjectId

from models.mongo import get_db


# ==================== 集合访问 ====================

def get_telegram_accounts_collection():
    """获取 Telegram 账号集合"""
    return get_db()['telegram_accounts']


def get_telegram_groups_collection():
    """获取 Telegram 群组集合"""
    return get_db()['telegram_groups']


def get_telegram_messages_collection():
    """获取 Telegram 消息集合"""
    return get_db()['telegram_messages']


def get_telegram_keywords_collection():
    """获取 Telegram 关键词集合"""
    return get_db()['telegram_keywords']


def get_telegram_alerts_collection():
    """获取 Telegram 报警集合"""
    return get_db()['telegram_alerts']


# ==================== 索引初始化 ====================

def ensure_telegram_indexes():
    """确保 Telegram 相关集合的索引存在"""
    try:
        # 消息集合索引
        messages = get_telegram_messages_collection()
        messages.create_index([('group_id', 1), ('message_id', 1)], unique=True)
        messages.create_index([('timestamp', -1)])
        messages.create_index([('is_alert', 1)])

        # 报警集合索引
        alerts = get_telegram_alerts_collection()
        alerts.create_index([('timestamp', -1)])
        alerts.create_index([('is_read', 1)])
        alerts.create_index([('group_id', 1)])

        # 关键词集合索引
        keywords = get_telegram_keywords_collection()
        keywords.create_index('keyword', unique=True)

        # 群组集合索引
        groups = get_telegram_groups_collection()
        groups.create_index([('account_id', 1), ('group_id', 1)], unique=True)
    except Exception as e:
        print(f"[Telegram] 创建索引失败: {e}")


# ==================== 账号管理 ====================

def get_all_accounts() -> List[Dict[str, Any]]:
    """获取所有 Telegram 账号"""
    collection = get_telegram_accounts_collection()
    results = []
    for doc in collection.find().sort('created_at', -1):
        results.append({
            'id': str(doc['_id']),
            'name': doc.get('name', ''),
            'api_id': doc.get('api_id', ''),
            'api_hash': doc.get('api_hash', ''),
            'phone': doc.get('phone', ''),
            'status': doc.get('status', 'pending_auth'),
            'is_default': doc.get('is_default', False),
            'created_at': doc.get('created_at', '').strftime('%Y-%m-%d %H:%M') if doc.get('created_at') else ''
        })
    return results


def add_account(name: str, api_id: str, api_hash: str, phone: str) -> Dict[str, Any]:
    """添加 Telegram 账号"""
    collection = get_telegram_accounts_collection()

    # 检查手机号是否已存在
    if collection.find_one({'phone': phone}):
        raise ValueError(f'手机号 {phone} 已存在')

    # 如果是第一个账号，设为默认
    is_first = collection.count_documents({}) == 0

    doc = {
        'name': name.strip(),
        'api_id': api_id.strip(),
        'api_hash': api_hash.strip(),
        'phone': phone.strip(),
        'session_string': '',
        'status': 'pending_auth',
        'is_default': is_first,
        'created_at': datetime.now()
    }

    result = collection.insert_one(doc)
    doc['id'] = str(result.inserted_id)
    return doc


def delete_account(account_id: str) -> bool:
    """删除 Telegram 账号"""
    collection = get_telegram_accounts_collection()
    result = collection.delete_one({'_id': ObjectId(account_id)})

    if result.deleted_count > 0:
        # 同时删除该账号的群组订阅
        get_telegram_groups_collection().delete_many({'account_id': account_id})
        return True
    return False


def get_account_by_id(account_id: str) -> Optional[Dict[str, Any]]:
    """根据 ID 获取账号"""
    collection = get_telegram_accounts_collection()
    doc = collection.find_one({'_id': ObjectId(account_id)})
    if doc:
        return {
            'id': str(doc['_id']),
            'name': doc.get('name', ''),
            'api_id': doc.get('api_id', ''),
            'api_hash': doc.get('api_hash', ''),
            'phone': doc.get('phone', ''),
            'session_string': doc.get('session_string', ''),
            'status': doc.get('status', 'pending_auth'),
            'is_default': doc.get('is_default', False),
        }
    return None


def update_account_status(account_id: str, status: str, session_string: str = None) -> bool:
    """更新账号状态"""
    collection = get_telegram_accounts_collection()
    update_fields: Dict[str, Any] = {'status': status}
    if session_string is not None:
        update_fields['session_string'] = session_string
    result = collection.update_one(
        {'_id': ObjectId(account_id)},
        {'$set': update_fields}
    )
    return result.modified_count > 0


def get_default_account() -> Optional[Dict[str, Any]]:
    """获取默认账号"""
    collection = get_telegram_accounts_collection()
    doc = collection.find_one({'is_default': True})
    if not doc:
        # 没有默认账号，取第一个
        doc = collection.find_one()
    if doc:
        return {
            'id': str(doc['_id']),
            'name': doc.get('name', ''),
            'api_id': doc.get('api_id', ''),
            'api_hash': doc.get('api_hash', ''),
            'phone': doc.get('phone', ''),
            'session_string': doc.get('session_string', ''),
            'status': doc.get('status', 'pending_auth'),
            'is_default': doc.get('is_default', False),
        }
    return None


# ==================== 群组管理 ====================

def get_all_groups(account_id: str = None) -> List[Dict[str, Any]]:
    """获取所有订阅群组"""
    collection = get_telegram_groups_collection()
    query = {}
    if account_id:
        query['account_id'] = account_id
    results = []
    for doc in collection.find(query).sort('group_title', 1):
        results.append({
            'id': str(doc['_id']),
            'account_id': doc.get('account_id', ''),
            'group_id': doc.get('group_id', 0),
            'group_title': doc.get('group_title', ''),
            'group_link': doc.get('group_link', ''),
            'enabled': doc.get('enabled', True),
            'stats': doc.get('stats', {'total_messages': 0, 'alert_messages': 0})
        })
    return results


def subscribe_group(account_id: str, group_id: int, group_title: str, group_link: str = '') -> Dict[str, Any]:
    """订阅群组"""
    collection = get_telegram_groups_collection()

    # 检查是否已订阅
    if collection.find_one({'account_id': account_id, 'group_id': group_id}):
        raise ValueError(f'群组 "{group_title}" 已订阅')

    doc = {
        'account_id': account_id,
        'group_id': group_id,
        'group_title': group_title,
        'group_link': group_link,
        'enabled': True,
        'stats': {'total_messages': 0, 'alert_messages': 0},
        'created_at': datetime.now()
    }

    result = collection.insert_one(doc)
    doc['id'] = str(result.inserted_id)
    return doc


def unsubscribe_group(group_db_id: str) -> bool:
    """取消订阅群组"""
    collection = get_telegram_groups_collection()
    result = collection.delete_one({'_id': ObjectId(group_db_id)})
    return result.deleted_count > 0


def toggle_group(group_db_id: str) -> bool:
    """切换群组启用/禁用状态"""
    collection = get_telegram_groups_collection()
    doc = collection.find_one({'_id': ObjectId(group_db_id)})
    if not doc:
        return False
    new_enabled = not doc.get('enabled', True)
    collection.update_one(
        {'_id': ObjectId(group_db_id)},
        {'$set': {'enabled': new_enabled}}
    )
    return new_enabled


def get_enabled_group_ids() -> List[int]:
    """获取所有启用的群组 ID 列表"""
    collection = get_telegram_groups_collection()
    return [doc['group_id'] for doc in collection.find({'enabled': True}, {'group_id': 1})]


def increment_group_stats(group_id: int, is_alert: bool = False):
    """增加群组消息统计"""
    collection = get_telegram_groups_collection()
    inc_fields: Dict[str, int] = {'stats.total_messages': 1}
    if is_alert:
        inc_fields['stats.alert_messages'] = 1
    collection.update_many(
        {'group_id': group_id},
        {'$inc': inc_fields}
    )


# ==================== 关键词管理 ====================

def get_all_tg_keywords() -> Dict[str, List[Dict[str, Any]]]:
    """获取所有 Telegram 关键词（按等级分组）"""
    collection = get_telegram_keywords_collection()
    result: Dict[str, List[Dict[str, Any]]] = {'high': [], 'medium': [], 'low': []}

    for doc in collection.find().sort('created_at', -1):
        level = doc.get('level', 'low')
        if level in result:
            result[level].append({
                'id': str(doc['_id']),
                'keyword': doc.get('keyword', ''),
                'enabled': doc.get('enabled', True),
                'match_count': doc.get('match_count', 0),
            })
    return result


def get_enabled_tg_keywords() -> List[Dict[str, Any]]:
    """获取所有启用的关键词（用于匹配）"""
    collection = get_telegram_keywords_collection()
    results = []
    for doc in collection.find({'enabled': True}):
        results.append({
            'keyword': doc.get('keyword', ''),
            'level': doc.get('level', 'low'),
        })
    return results


def add_tg_keyword(keyword: str, level: str) -> Dict[str, Any]:
    """添加 Telegram 关键词"""
    collection = get_telegram_keywords_collection()

    if collection.find_one({'keyword': keyword}):
        raise ValueError(f'关键词 "{keyword}" 已存在')

    if level not in ['high', 'medium', 'low']:
        raise ValueError('等级必须是 high、medium 或 low')

    doc = {
        'keyword': keyword.strip(),
        'level': level,
        'enabled': True,
        'match_count': 0,
        'created_at': datetime.now()
    }
    result = collection.insert_one(doc)
    doc['id'] = str(result.inserted_id)
    return doc


def update_tg_keyword(keyword_id: str, keyword: str = None, level: str = None, enabled: bool = None) -> bool:
    """更新 Telegram 关键词"""
    collection = get_telegram_keywords_collection()
    update_fields: Dict[str, Any] = {}

    if keyword is not None:
        existing = collection.find_one({'keyword': keyword, '_id': {'$ne': ObjectId(keyword_id)}})
        if existing:
            raise ValueError(f'关键词 "{keyword}" 已存在')
        update_fields['keyword'] = keyword.strip()

    if level is not None:
        if level not in ['high', 'medium', 'low']:
            raise ValueError('等级必须是 high、medium 或 low')
        update_fields['level'] = level

    if enabled is not None:
        update_fields['enabled'] = enabled

    if not update_fields:
        return False

    result = collection.update_one(
        {'_id': ObjectId(keyword_id)},
        {'$set': update_fields}
    )
    return result.modified_count > 0


def delete_tg_keyword(keyword_id: str) -> bool:
    """删除 Telegram 关键词"""
    collection = get_telegram_keywords_collection()
    result = collection.delete_one({'_id': ObjectId(keyword_id)})
    return result.deleted_count > 0


def increment_keyword_match(keyword: str):
    """增加关键词匹配计数"""
    collection = get_telegram_keywords_collection()
    collection.update_one(
        {'keyword': keyword},
        {'$inc': {'match_count': 1}}
    )


# ==================== 关键词匹配 ====================

def match_keywords(text: str) -> List[Dict[str, Any]]:
    """
    对文本进行关键词匹配
    返回：匹配到的关键词列表 [{'keyword': '...', 'level': '...'}]
    """
    if not text:
        return []

    keywords = get_enabled_tg_keywords()
    matched = []

    for kw_item in keywords:
        keyword = kw_item['keyword']
        if re.search(re.escape(keyword), text, re.IGNORECASE):
            matched.append(kw_item)
            # 增加匹配计数
            increment_keyword_match(keyword)

    return matched


def get_highest_level(matched_keywords: List[Dict[str, Any]]) -> str:
    """从匹配结果中获取最高等级"""
    level_priority = {'high': 3, 'medium': 2, 'low': 1}
    highest = 'low'
    for kw in matched_keywords:
        if level_priority.get(kw.get('level', 'low'), 0) > level_priority.get(highest, 0):
            highest = kw['level']
    return highest


# ==================== 消息管理 ====================

def save_message(group_id: int, group_title: str, message_id: int,
                 sender_name: str, sender_username: str, content: str,
                 timestamp: datetime, is_alert: bool = False,
                 matched_keywords: List[str] = None) -> Optional[str]:
    """
    保存 Telegram 消息
    返回：消息的数据库 ID，如果重复则返回 None
    """
    collection = get_telegram_messages_collection()

    try:
        doc = {
            'group_id': group_id,
            'group_title': group_title,
            'message_id': message_id,
            'sender_name': sender_name,
            'sender_username': sender_username or '',
            'content': content,
            'timestamp': timestamp,
            'is_alert': is_alert,
            'matched_keywords': matched_keywords or [],
        }
        result = collection.insert_one(doc)
        return str(result.inserted_id)
    except Exception:
        # 重复消息（唯一索引冲突）
        return None


def get_messages(group_id: int = None, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """获取消息历史"""
    collection = get_telegram_messages_collection()
    query: Dict[str, Any] = {}
    if group_id:
        query['group_id'] = group_id

    total = collection.count_documents(query)
    skip = (page - 1) * page_size
    cursor = collection.find(query).sort('timestamp', -1).skip(skip).limit(page_size)

    items = []
    for doc in cursor:
        ts = doc.get('timestamp')
        items.append({
            'id': str(doc['_id']),
            'group_id': doc.get('group_id', 0),
            'group_title': doc.get('group_title', ''),
            'message_id': doc.get('message_id', 0),
            'sender_name': doc.get('sender_name', ''),
            'sender_username': doc.get('sender_username', ''),
            'content': doc.get('content', ''),
            'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S') if isinstance(ts, datetime) else str(ts),
            'is_alert': doc.get('is_alert', False),
            'matched_keywords': doc.get('matched_keywords', []),
        })

    return {
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size
    }


# ==================== 报警管理 ====================

def save_alert(group_id: int, group_title: str, group_link: str,
               sender_name: str, content: str, matched_keywords: List[str],
               highest_level: str, timestamp: datetime,
               webhook_sent: bool = False) -> str:
    """保存报警记录"""
    collection = get_telegram_alerts_collection()

    doc = {
        'group_id': group_id,
        'group_title': group_title,
        'group_link': group_link,
        'sender_name': sender_name,
        'content': content,
        'matched_keywords': matched_keywords,
        'highest_level': highest_level,
        'timestamp': timestamp,
        'is_read': False,
        'webhook_sent': webhook_sent,
    }
    result = collection.insert_one(doc)
    return str(result.inserted_id)


def get_alerts(page: int = 1, page_size: int = 20, unread_only: bool = False,
               group_id: int = None, level: str = None) -> Dict[str, Any]:
    """获取报警列表"""
    collection = get_telegram_alerts_collection()
    query: Dict[str, Any] = {}

    if unread_only:
        query['is_read'] = False
    if group_id:
        query['group_id'] = group_id
    if level:
        query['highest_level'] = level

    total = collection.count_documents(query)
    skip = (page - 1) * page_size
    cursor = collection.find(query).sort('timestamp', -1).skip(skip).limit(page_size)

    items = []
    for doc in cursor:
        ts = doc.get('timestamp')
        items.append({
            'id': str(doc['_id']),
            'group_id': doc.get('group_id', 0),
            'group_title': doc.get('group_title', ''),
            'group_link': doc.get('group_link', ''),
            'sender_name': doc.get('sender_name', ''),
            'content': doc.get('content', ''),
            'matched_keywords': doc.get('matched_keywords', []),
            'highest_level': doc.get('highest_level', 'low'),
            'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S') if isinstance(ts, datetime) else str(ts),
            'is_read': doc.get('is_read', False),
            'webhook_sent': doc.get('webhook_sent', False),
        })

    return {
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size
    }


def mark_alert_read(alert_id: str) -> bool:
    """标记报警已读"""
    collection = get_telegram_alerts_collection()
    result = collection.update_one(
        {'_id': ObjectId(alert_id)},
        {'$set': {'is_read': True, 'read_at': datetime.now()}}
    )
    return result.modified_count > 0


# ==================== 统计分析 ====================

def get_overview_stats() -> Dict[str, Any]:
    """获取 Telegram 概览统计"""
    alerts_col = get_telegram_alerts_collection()
    messages_col = get_telegram_messages_collection()
    groups_col = get_telegram_groups_collection()

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    today_alerts = alerts_col.count_documents({'timestamp': {'$gte': today_start}})
    unread_alerts = alerts_col.count_documents({'is_read': False})
    total_groups = groups_col.count_documents({'enabled': True})
    total_messages = messages_col.count_documents({})
    today_messages = messages_col.count_documents({'timestamp': {'$gte': today_start}})

    return {
        'today_alerts': today_alerts,
        'unread_alerts': unread_alerts,
        'total_groups': total_groups,
        'total_messages': total_messages,
        'today_messages': today_messages,
    }


def get_alert_trend(days: int = 7) -> List[Dict[str, Any]]:
    """获取报警趋势（按天）"""
    collection = get_telegram_alerts_collection()
    start_date = datetime.now() - timedelta(days=days)

    pipeline = [
        {'$match': {'timestamp': {'$gte': start_date}}},
        {'$group': {
            '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$timestamp'}},
            'count': {'$sum': 1},
            'high': {'$sum': {'$cond': [{'$eq': ['$highest_level', 'high']}, 1, 0]}},
            'medium': {'$sum': {'$cond': [{'$eq': ['$highest_level', 'medium']}, 1, 0]}},
            'low': {'$sum': {'$cond': [{'$eq': ['$highest_level', 'low']}, 1, 0]}},
        }},
        {'$sort': {'_id': 1}},
        {'$project': {
            '_id': 0,
            'date': '$_id',
            'count': 1,
            'high': 1,
            'medium': 1,
            'low': 1,
        }}
    ]
    return list(collection.aggregate(pipeline))


def get_keyword_hotness(limit: int = 20) -> List[Dict[str, Any]]:
    """获取关键词热度排行"""
    collection = get_telegram_keywords_collection()
    results = []
    for doc in collection.find({'enabled': True}).sort('match_count', -1).limit(limit):
        results.append({
            'keyword': doc.get('keyword', ''),
            'level': doc.get('level', 'low'),
            'match_count': doc.get('match_count', 0),
        })
    return results


def get_group_activity(days: int = 7) -> List[Dict[str, Any]]:
    """获取群组活跃度统计"""
    collection = get_telegram_messages_collection()
    start_date = datetime.now() - timedelta(days=days)

    pipeline = [
        {'$match': {'timestamp': {'$gte': start_date}}},
        {'$group': {
            '_id': '$group_title',
            'message_count': {'$sum': 1},
            'alert_count': {'$sum': {'$cond': ['$is_alert', 1, 0]}},
        }},
        {'$sort': {'message_count': -1}},
        {'$project': {
            '_id': 0,
            'group_title': '$_id',
            'message_count': 1,
            'alert_count': 1,
        }}
    ]
    return list(collection.aggregate(pipeline))
