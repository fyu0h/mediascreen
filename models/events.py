# -*- coding: utf-8 -*-
"""
全球事件链数据模型
适配 world-monitor.com/api/signal-markers 的 locations 数据结构
"""

from datetime import datetime
from typing import List, Dict, Optional
from models.mongo import get_db


def get_events_collection():
    """获取事件集合"""
    db = get_db()
    return db['global_events']


def get_event_by_id(event_id: str) -> Optional[Dict]:
    """根据 ID 获取事件"""
    collection = get_events_collection()
    return collection.find_one({'event_id': event_id})


def save_event(event_data: Dict) -> bool:
    """保存或更新事件"""
    try:
        collection = get_events_collection()
        event_id = event_data.get('event_id')

        if not event_id:
            return False

        event_data['updated_at'] = datetime.now()

        collection.update_one(
            {'event_id': event_id},
            {'$set': event_data},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"保存事件失败: {e}")
        return False


def get_all_events(skip: int = 0, limit: int = 0, intensity: int = None) -> List[Dict]:
    """获取所有事件（按 intensity 降序 + mention_count 降序）"""
    collection = get_events_collection()
    query = {}
    if intensity is not None:
        query['intensity'] = intensity

    cursor = collection.find(query).sort([('intensity', -1), ('mention_count', -1)])
    if skip > 0:
        cursor = cursor.skip(skip)
    if limit > 0:
        cursor = cursor.limit(limit)
    return list(cursor)


def get_events_count(intensity: int = None) -> int:
    """获取事件总数"""
    collection = get_events_collection()
    query = {}
    if intensity is not None:
        query['intensity'] = intensity
    return collection.count_documents(query)


def get_untranslated_events(limit: int = 10) -> List[Dict]:
    """获取未翻译的事件（summary_cn 不存在）"""
    collection = get_events_collection()
    cursor = collection.find({
        '$or': [
            {'summary_cn': {'$exists': False}},
            {'summary_cn': None},
            {'summary_cn': ''}
        ]
    }).sort([('intensity', -1), ('mention_count', -1)]).limit(limit)
    return list(cursor)


def mark_event_translated(event_id: str, translated_fields: Dict) -> bool:
    """标记事件已翻译，保存翻译字段"""
    try:
        collection = get_events_collection()
        translated_fields['translated_at'] = datetime.now()
        collection.update_one(
            {'event_id': event_id},
            {'$set': translated_fields}
        )
        return True
    except Exception as e:
        print(f"标记翻译失败: {e}")
        return False


def delete_old_events(days: int = 30) -> int:
    """删除旧事件"""
    try:
        collection = get_events_collection()
        cutoff = datetime.now().timestamp() - (days * 24 * 3600)
        result = collection.delete_many({'last_mentioned_sort': {'$lt': cutoff}})
        return result.deleted_count
    except Exception as e:
        print(f"删除旧事件失败: {e}")
        return 0


def clear_all_events() -> int:
    """清空所有事件"""
    try:
        collection = get_events_collection()
        result = collection.delete_many({})
        return result.deleted_count
    except Exception as e:
        print(f"清空事件失败: {e}")
        return 0
