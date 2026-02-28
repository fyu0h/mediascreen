# -*- coding: utf-8 -*-
"""
后台任务管理模块
支持爬虫任务的异步执行、状态跟踪、取消操作
"""

import threading
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from config import Config

# 内存中的任务线程引用（用于取消）
_running_tasks: Dict[str, dict] = {}
_task_lock = threading.Lock()


def get_tasks_collection():
    """获取任务集合"""
    from models.mongo import get_db
    return get_db()['crawl_tasks']


def ensure_task_indexes() -> None:
    """
    创建 crawl_tasks 集合的索引
    在应用启动时调用，提升任务查询性能
    """
    collection = get_tasks_collection()

    try:
        # 获取现有索引名称
        existing_indexes = set(collection.index_information().keys())

        indexes_to_create = []

        # 1. task_id 唯一索引（任务唯一标识）
        if 'task_id_1' not in existing_indexes:
            from pymongo import IndexModel, ASCENDING
            indexes_to_create.append(IndexModel(
                [('task_id', ASCENDING)],
                unique=True,
                name='task_id_1'
            ))

        # 2. status 普通索引（按状态查询任务）
        if 'status_1' not in existing_indexes:
            from pymongo import IndexModel, ASCENDING
            indexes_to_create.append(IndexModel(
                [('status', ASCENDING)],
                name='status_1'
            ))

        # 批量创建索引
        if indexes_to_create:
            collection.create_indexes(indexes_to_create)
            print(f"[MongoDB] 已为 crawl_tasks 创建 {len(indexes_to_create)} 个索引")

    except Exception as e:
        print(f"[MongoDB] 创建 crawl_tasks 索引时出错: {e}")


def create_task(task_type: str = 'crawl', sites: List[dict] = None) -> str:
    """
    创建新任务
    返回 task_id
    """
    task_id = str(uuid.uuid4())[:8]  # 短ID便于显示

    task_doc = {
        'task_id': task_id,
        'type': task_type,
        'status': 'pending',  # pending, running, completed, failed, cancelled
        'progress': 0,
        'total_sites': len(sites) if sites else 0,
        'completed_sites': 0,
        'success_count': 0,
        'failed_count': 0,
        'skipped_count': 0,  # 超时跳过的站点数
        'total_articles': 0,
        'total_saved': 0,
        'current_site': '',
        'sites_status': {},  # site_id -> {status, articles, saved, error, skipped}
        'message': '等待开始...',
        'created_at': datetime.now(),
        'started_at': None,
        'finished_at': None,
        'error': None
    }

    get_tasks_collection().insert_one(task_doc)
    return task_id


def update_task(task_id: str, updates: dict):
    """更新任务状态"""
    get_tasks_collection().update_one(
        {'task_id': task_id},
        {'$set': updates}
    )


def get_task(task_id: str) -> Optional[dict]:
    """获取任务详情"""
    task = get_tasks_collection().find_one(
        {'task_id': task_id},
        {'_id': 0}
    )
    return task


def get_task_status(task_id: str) -> Optional[dict]:
    """获取任务状态（精简版，用于轮询）"""
    task = get_tasks_collection().find_one(
        {'task_id': task_id},
        {
            '_id': 0,
            'task_id': 1,
            'status': 1,
            'progress': 1,
            'total_sites': 1,
            'completed_sites': 1,
            'success_count': 1,
            'failed_count': 1,
            'skipped_count': 1,
            'total_articles': 1,
            'total_saved': 1,
            'current_site': 1,
            'message': 1,
            'error': 1
        }
    )
    return task


def is_task_cancelled(task_id: str) -> bool:
    """检查任务是否被取消"""
    task = get_tasks_collection().find_one(
        {'task_id': task_id},
        {'status': 1}
    )
    return task and task.get('status') == 'cancelled'


def cancel_task(task_id: str) -> bool:
    """
    取消任务
    返回是否成功
    """
    task = get_task(task_id)
    if not task:
        return False

    if task['status'] in ['completed', 'failed', 'cancelled']:
        return False  # 已结束的任务无法取消

    # 更新数据库状态
    update_task(task_id, {
        'status': 'cancelled',
        'message': '任务已取消',
        'finished_at': datetime.now()
    })

    # 设置内存中的取消标志
    with _task_lock:
        if task_id in _running_tasks:
            _running_tasks[task_id]['cancelled'] = True

    return True


def register_running_task(task_id: str, thread: threading.Thread):
    """注册正在运行的任务"""
    with _task_lock:
        _running_tasks[task_id] = {
            'thread': thread,
            'cancelled': False
        }


def unregister_task(task_id: str):
    """注销任务"""
    with _task_lock:
        if task_id in _running_tasks:
            del _running_tasks[task_id]


def is_cancelled(task_id: str) -> bool:
    """检查内存中的取消标志（线程内调用）"""
    with _task_lock:
        if task_id in _running_tasks:
            return _running_tasks[task_id].get('cancelled', False)
    # 如果内存中没有，查数据库
    return is_task_cancelled(task_id)


def get_recent_tasks(limit: int = 10) -> List[dict]:
    """获取最近的任务列表"""
    cursor = get_tasks_collection().find(
        {},
        {'_id': 0, 'sites_status': 0}
    ).sort('created_at', -1).limit(limit)
    return list(cursor)


def cleanup_old_tasks(days: int = 7):
    """清理旧任务记录"""
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=days)
    get_tasks_collection().delete_many({
        'created_at': {'$lt': cutoff}
    })


def has_running_task() -> bool:
    """检查是否有正在运行的爬虫任务"""
    # 先检查内存中的任务
    with _task_lock:
        if _running_tasks:
            return True
    # 再检查数据库中的任务状态
    count = get_tasks_collection().count_documents({
        'status': {'$in': ['pending', 'running']}
    })
    return count > 0


def get_running_task_id() -> Optional[str]:
    """获取正在运行的任务ID"""
    with _task_lock:
        for task_id in _running_tasks:
            return task_id
    # 查数据库
    task = get_tasks_collection().find_one(
        {'status': {'$in': ['pending', 'running']}},
        {'task_id': 1}
    )
    return task['task_id'] if task else None
