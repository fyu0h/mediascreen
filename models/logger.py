# -*- coding: utf-8 -*-
"""
后台日志模块
记录所有操作、网络请求和响应
"""

import os
import json
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import deque
import uuid
import traceback


class LogEntry:
    """日志条目"""

    def __init__(self, log_type: str, action: str, details: Dict[str, Any] = None,
                 request_data: Dict[str, Any] = None, response_data: Dict[str, Any] = None,
                 status: str = 'info', error: str = None):
        self.id = str(uuid.uuid4())[:8]
        self.timestamp = datetime.now()
        self.log_type = log_type  # operation, request, system
        self.action = action
        self.details = details or {}
        self.request_data = request_data  # 请求原始数据
        self.response_data = response_data  # 响应原始数据
        self.status = status  # info, success, warning, error
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'log_type': self.log_type,
            'action': self.action,
            'details': self.details,
            'request_data': self.request_data,
            'response_data': self.response_data,
            'status': self.status,
            'error': self.error
        }


class BackendLogger:
    """后台日志记录器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_entries: int = 1000):
        if self._initialized:
            return

        self.max_entries = max_entries
        self.logs: deque = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._initialized = True

    def log(self, log_type: str, action: str, details: Dict[str, Any] = None,
            request_data: Dict[str, Any] = None, response_data: Dict[str, Any] = None,
            status: str = 'info', error: str = None) -> LogEntry:
        """记录日志"""
        entry = LogEntry(
            log_type=log_type,
            action=action,
            details=details,
            request_data=request_data,
            response_data=response_data,
            status=status,
            error=error
        )

        with self._lock:
            self.logs.appendleft(entry)

        return entry

    def log_operation(self, action: str, details: Dict[str, Any] = None,
                      status: str = 'info', error: str = None) -> LogEntry:
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
                    status: str = 'info', error: str = None) -> LogEntry:
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
                   status: str = 'info', error: str = None) -> LogEntry:
        """记录系统日志"""
        return self.log(
            log_type='system',
            action=action,
            details=details,
            status=status,
            error=error
        )

    def log_error(self, action: str, error: Exception,
                  details: Dict[str, Any] = None) -> LogEntry:
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
                 search: str = None) -> List[Dict[str, Any]]:
        """获取日志列表"""
        with self._lock:
            logs = list(self.logs)

        # 过滤
        if log_type:
            logs = [l for l in logs if l.log_type == log_type]

        if status:
            logs = [l for l in logs if l.status == status]

        if search:
            search_lower = search.lower()
            logs = [l for l in logs if (
                search_lower in l.action.lower() or
                search_lower in str(l.details).lower() or
                (l.error and search_lower in l.error.lower())
            )]

        # 分页
        total = len(logs)
        logs = logs[offset:offset + limit]

        return {
            'items': [l.to_dict() for l in logs],
            'total': total,
            'limit': limit,
            'offset': offset
        }

    def get_log_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取单条日志"""
        with self._lock:
            for log in self.logs:
                if log.id == log_id:
                    return log.to_dict()
        return None

    def clear_logs(self) -> int:
        """清空日志"""
        with self._lock:
            count = len(self.logs)
            self.logs.clear()
        return count

    def get_stats(self) -> Dict[str, Any]:
        """获取日志统计"""
        with self._lock:
            logs = list(self.logs)

        stats = {
            'total': len(logs),
            'by_type': {},
            'by_status': {},
            'recent_errors': []
        }

        for log in logs:
            # 按类型统计
            if log.log_type not in stats['by_type']:
                stats['by_type'][log.log_type] = 0
            stats['by_type'][log.log_type] += 1

            # 按状态统计
            if log.status not in stats['by_status']:
                stats['by_status'][log.status] = 0
            stats['by_status'][log.status] += 1

            # 最近错误
            if log.status == 'error' and len(stats['recent_errors']) < 5:
                stats['recent_errors'].append({
                    'id': log.id,
                    'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'action': log.action,
                    'error': log.error
                })

        return stats

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
                except:
                    return f'<binary data: {len(data)} bytes>'
            elif isinstance(data, str):
                return data
            else:
                return str(data)
        except:
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
                  status: str = 'info', error: str = None) -> LogEntry:
    """记录操作日志"""
    return logger.log_operation(action, details, status, error)


def log_request(action: str, url: str, method: str = 'GET',
                request_headers: Dict = None, request_body: Any = None,
                response_status: int = None, response_headers: Dict = None,
                response_body: Any = None, duration_ms: float = None,
                status: str = 'info', error: str = None) -> LogEntry:
    """记录网络请求日志"""
    return logger.log_request(
        action=action, url=url, method=method,
        request_headers=request_headers, request_body=request_body,
        response_status=response_status, response_headers=response_headers,
        response_body=response_body, duration_ms=duration_ms,
        status=status, error=error
    )


def log_system(action: str, details: Dict[str, Any] = None,
               status: str = 'info', error: str = None) -> LogEntry:
    """记录系统日志"""
    return logger.log_system(action, details, status, error)


def log_error(action: str, error: Exception,
              details: Dict[str, Any] = None) -> LogEntry:
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
