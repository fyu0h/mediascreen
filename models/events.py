# -*- coding: utf-8 -*-
"""
全球事件链数据模型
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

        # 添加更新时间
        event_data['updated_at'] = datetime.now()

        # 使用 upsert 更新或插入
        collection.update_one(
            {'event_id': event_id},
            {'$set': event_data},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"保存事件失败: {e}")
        return False


def get_all_events(skip: int = 0, limit: int = 20) -> List[Dict]:
    """获取所有事件（按时间排序）"""
    collection = get_events_collection()
    cursor = collection.find().sort('timestamp_sort', -1).skip(skip).limit(limit)
    return list(cursor)


def get_events_count() -> int:
    """获取事件总数"""
    collection = get_events_collection()
    return collection.count_documents({})


def get_untranslated_events(limit: int = 10) -> List[Dict]:
    """获取未翻译的事件"""
    collection = get_events_collection()
    cursor = collection.find({
        '$or': [
            {'title_cn': {'$exists': False}},
            {'title_cn': ''},
            {'description_cn': {'$exists': False}},
            {'description_cn': ''}
        ]
    }).limit(limit)
    return list(cursor)


def mark_event_translated(event_id: str, title_cn: str, description_cn: str, location_cn: str) -> bool:
    """标记事件已翻译"""
    try:
        collection = get_events_collection()
        collection.update_one(
            {'event_id': event_id},
            {
                '$set': {
                    'title_cn': title_cn,
                    'description_cn': description_cn,
                    'location_cn': location_cn,
                    'translated_at': datetime.now()
                }
            }
        )
        return True
    except Exception as e:
        print(f"标记翻译失败: {e}")
        return False


def delete_old_events(days: int = 30) -> int:
    """删除旧事件"""
    try:
        collection = get_events_collection()
        cutoff_date = datetime.now().timestamp() - (days * 24 * 3600)
        result = collection.delete_many({'timestamp_sort': {'$lt': cutoff_date}})
        return result.deleted_count
    except Exception as e:
        print(f"删除旧事件失败: {e}")
        return 0
