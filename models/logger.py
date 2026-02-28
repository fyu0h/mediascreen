# -*- coding: utf-8 -*-
"""
后台日志模块
记录所有操作、网络请求和响应（持久化到 MongoDB）
"""

import json
import re
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid
import traceback


def get_logs_collection():
    """获取日志集合"""
    from models.mongo import get_db
    return get_db()['system_logs']


def ensure_indexes():
    """确保必要的索引存在"""
    collection = get_logs_collection()

    try:
        # 获取现有索引名称
        existing_indexes = set(collection.index_information().keys())

        indexes_to_create = []

        # 1. timestamp 降序索引（日志时间线查询）
        if 'timestamp_-1' not in existing_indexes:
            from pymongo import IndexModel, DESCENDING
            indexes_to_create.append(IndexModel(
                [('timestamp', DESCENDING)],
                name='timestamp_-1'
            ))

        # 2. log_type 索引（按日志类型筛选）
        if 'log_type_1' not in existing_indexes:
            from pymongo import IndexModel, ASCENDING
            indexes_to_create.append(IndexModel(
                [('log_type', ASCENDING)],
                name='log_type_1'
            ))

        # 3. status 索引（按状态筛选）
        if 'status_1' not in existing_indexes:
            from pymongo import IndexModel, ASCENDING
            indexes_to_create.append(IndexModel(
                [('status', ASCENDING)],
                name='status_1'
            ))

        # 4. timestamp TTL 索引（30天自动过期，清理旧日志）
        if 'timestamp_ttl' not in existing_indexes:
            from pymongo import IndexModel, ASCENDING
            indexes_to_create.append(IndexModel(
                [('timestamp', ASCENDING)],
                name='timestamp_ttl',
                expireAfterSeconds=30 * 24 * 3600  # 30天
            ))

        # 5. log_id 唯一索引（日志唯一标识，加速单条查询）
        if 'log_id_1' not in existing_indexes:
            from pymongo import IndexModel, ASCENDING
            indexes_to_create.append(IndexModel(
                [('log_id', ASCENDING)],
                unique=True,
                name='log_id_1'
            ))

        # 批量创建索引
        if indexes_to_create:
            collection.create_indexes(indexes_to_create)
            print(f"[MongoDB] 已为 system_logs 创建 {len(indexes_to_create)} 个索引")

    except Exception as e:
        print(f"[MongoDB] 创建 system_logs 索引时出错: {e}")


class BackendLogger:
    """后台日志记录器（MongoDB 持久化）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._lock = threading.Lock()
        self._initialized = True
        # 确保索引
        try:
            ensure_indexes()
        except Exception:
            pass  # 启动时可能数据库未连接

    def log(self, log_type: str, action: str, details: Dict[str, Any] = None,
            request_data: Dict[str, Any] = None, response_data: Dict[str, Any] = None,
            status: str = 'info', error: str = None) -> Dict[str, Any]:
        """记录日志到 MongoDB"""
        entry = {
            'log_id': str(uuid.uuid4())[:8],
            'timestamp': datetime.now(),
            'log_type': log_type,
            'action': action,
            'details': details or {},
            'request_data': request_data,
            'response_data': response_data,
            'status': status,
            'error': error
        }

        try:
            collection = get_logs_collection()
            collection.insert_one(entry)
        except Exception as e:
            print(f"[Logger] 写入日志失败: {e}")

        return entry

    def log_operation(self, action: str, details: Dict[str, Any] = None,
                      status: str = 'info', error: str = None) -> Dict[str, Any]:
        """记录操作日志"""
        return self.log(
            log_type='operation',
            action=action,
            details=details,
            status=status,
            error=error
        )

    def log_request(self, action: str, url: str, method: str = 'GET',
                    request_headers: Dict = None, request_body: Any = None,
                    response_status: int = None, response_headers: Dict = None,
                    response_body: Any = None, duration_ms: float = None,
                    status: str = 'info', error: str = None) -> Dict[str, Any]:
        """记录网络请求日志"""
        request_data = {
            'url': url,
            'method': method,
            'headers': self._safe_serialize(request_headers),
            'body': self._safe_serialize(request_body)
        }

        response_data = None
        if response_status is not None:
            response_data = {
                'status_code': response_status,
                'headers': self._safe_serialize(response_headers),
                'body': self._truncate_body(self._safe_serialize(response_body))
            }

        details = {
            'url': url,
            'method': method,
            'response_status': response_status,
            'duration_ms': duration_ms
        }

        return self.log(
            log_type='request',
            action=action,
            details=details,
            request_data=request_data,
            response_data=response_data,
            status=status,
            error=error
        )

    def log_system(self, action: str, details: Dict[str, Any] = None,
                   status: str = 'info', error: str = None) -> Dict[str, Any]:
        """记录系统日志"""
        return self.log(
            log_type='system',
            action=action,
            details=details,
            status=status,
            error=error
        )

    def log_error(self, action: str, error: Exception,
                  details: Dict[str, Any] = None) -> Dict[str, Any]:
        """记录错误日志"""
        error_details = details or {}
        error_details['traceback'] = traceback.format_exc()

        return self.log(
            log_type='system',
            action=action,
            details=error_details,
            status='error',
            error=str(error)
        )

    def get_logs(self, log_type: str = None, status: str = None,
                 limit: int = 100, offset: int = 0,
                 search: str = None) -> Dict[str, Any]:
        """获取日志列表"""
        try:
            collection = get_logs_collection()

            # 构建查询条件
            query = {}
            if log_type:
                query['log_type'] = log_type
            if status:
                query['status'] = status
            if search:
                # 转义用户输入的特殊正则字符，防止 ReDoS 攻击
                safe_search = re.escape(search)
                query['$or'] = [
                    {'action': {'$regex': safe_search, '$options': 'i'}},
                    {'error': {'$regex': safe_search, '$options': 'i'}}
                ]

            # 获取总数
            total = collection.count_documents(query)

            # 分页查询
            cursor = collection.find(query).sort('timestamp', -1).skip(offset).limit(limit)

            items = []
            for doc in cursor:
                items.append({
                    'id': doc.get('log_id', str(doc['_id'])),
                    'timestamp': doc['timestamp'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if isinstance(doc['timestamp'], datetime) else str(doc['timestamp']),
                    'log_type': doc.get('log_type'),
                    'action': doc.get('action'),
                    'details': doc.get('details'),
                    'request_data': doc.get('request_data'),
                    'response_data': doc.get('response_data'),
                    'status': doc.get('status'),
                    'error': doc.get('error')
                })

            return {
                'items': items,
                'total': total,
                'limit': limit,
                'offset': offset
            }
        except Exception as e:
            print(f"[Logger] 读取日志失败: {e}")
            return {'items': [], 'total': 0, 'limit': limit, 'offset': offset}

    def get_log_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取单条日志"""
        try:
            collection = get_logs_collection()
            doc = collection.find_one({'log_id': log_id})
            if doc:
                return {
                    'id': doc.get('log_id', str(doc['_id'])),
                    'timestamp': doc['timestamp'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if isinstance(doc['timestamp'], datetime) else str(doc['timestamp']),
                    'log_type': doc.get('log_type'),
                    'action': doc.get('action'),
                    'details': doc.get('details'),
                    'request_data': doc.get('request_data'),
                    'response_data': doc.get('response_data'),
                    'status': doc.get('status'),
                    'error': doc.get('error')
                }
        except Exception as e:
            print(f"[Logger] 获取日志详情失败: {e}")
        return None

    def clear_logs(self) -> int:
        """清空日志"""
        try:
            collection = get_logs_collection()
            result = collection.delete_many({})
            return result.deleted_count
        except Exception as e:
            print(f"[Logger] 清空日志失败: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """获取日志统计"""
        try:
            collection = get_logs_collection()

            total = collection.count_documents({})

            # 按类型统计
            by_type = {}
            for log_type in ['operation', 'request', 'system']:
                by_type[log_type] = collection.count_documents({'log_type': log_type})

            # 按状态统计
            by_status = {}
            for status in ['info', 'success', 'warning', 'error']:
                by_status[status] = collection.count_documents({'status': status})

            # 最近错误
            recent_errors = []
            for doc in collection.find({'status': 'error'}).sort('timestamp', -1).limit(5):
                recent_errors.append({
                    'id': doc.get('log_id', str(doc['_id'])),
                    'timestamp': doc['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(doc['timestamp'], datetime) else str(doc['timestamp']),
                    'action': doc.get('action'),
                    'error': doc.get('error')
                })

            return {
                'total': total,
                'by_type': by_type,
                'by_status': by_status,
                'recent_errors': recent_errors
            }
        except Exception as e:
            print(f"[Logger] 获取统计失败: {e}")
            return {
                'total': 0,
                'by_type': {},
                'by_status': {},
                'recent_errors': []
            }

    def _safe_serialize(self, data: Any) -> Any:
        """安全序列化数据"""
        if data is None:
            return None

        try:
            if isinstance(data, (dict, list)):
                return json.loads(json.dumps(data, default=str, ensure_ascii=False))
            elif isinstance(data, bytes):
                try:
                    return data.decode('utf-8')
                except Exception:
                    return f'<binary data: {len(data)} bytes>'
            elif isinstance(data, str):
                return data
            else:
                return str(data)
        except Exception:
            return f'<无法序列化: {type(data).__name__}>'

    def _truncate_body(self, body: Any, max_length: int = 10000) -> Any:
        """截断过长的响应体"""
        if body is None:
            return None

        if isinstance(body, str) and len(body) > max_length:
            return body[:max_length] + f'... [截断，共 {len(body)} 字符]'

        if isinstance(body, dict):
            body_str = json.dumps(body, ensure_ascii=False)
            if len(body_str) > max_length:
                return body_str[:max_length] + f'... [截断，共 {len(body_str)} 字符]'

        return body


# 全局日志实例
logger = BackendLogger()


# 便捷函数
def log_operation(action: str, details: Dict[str, Any] = None,
                  status: str = 'info', error: str = None) -> Dict[str, Any]:
    """记录操作日志"""
    return logger.log_operation(action, details, status, error)


def log_request(action: str, url: str, method: str = 'GET',
                request_headers: Dict = None, request_body: Any = None,
                response_status: int = None, response_headers: Dict = None,
                response_body: Any = None, duration_ms: float = None,
                status: str = 'info', error: str = None) -> Dict[str, Any]:
    """记录网络请求日志"""
    return logger.log_request(
        action=action, url=url, method=method,
        request_headers=request_headers, request_body=request_body,
        response_status=response_status, response_headers=response_headers,
        response_body=response_body, duration_ms=duration_ms,
        status=status, error=error
    )


def log_system(action: str, details: Dict[str, Any] = None,
               status: str = 'info', error: str = None) -> Dict[str, Any]:
    """记录系统日志"""
    return logger.log_system(action, details, status, error)


def log_error(action: str, error: Exception,
              details: Dict[str, Any] = None) -> Dict[str, Any]:
    """记录错误日志"""
    return logger.log_error(action, error, details)


def get_logs(**kwargs) -> Dict[str, Any]:
    """获取日志列表"""
    return logger.get_logs(**kwargs)


def get_log_by_id(log_id: str) -> Optional[Dict[str, Any]]:
    """根据 ID 获取单条日志"""
    return logger.get_log_by_id(log_id)


def clear_logs() -> int:
    """清空日志"""
    return logger.clear_logs()


def get_stats() -> Dict[str, Any]:
    """获取日志统计"""
    return logger.get_stats()
