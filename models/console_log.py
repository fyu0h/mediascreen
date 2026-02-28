# -*- coding: utf-8 -*-
"""
实时控制台日志模块
拦截 sys.stdout/sys.stderr，写入环形缓冲区，通过 SSE 推送给前端
"""

import sys
import threading
from collections import deque
from datetime import datetime
from typing import List, Dict, Any, Optional


class StreamInterceptor:
    """
    流拦截器：替换 sys.stdout / sys.stderr
    同时写入原始流和 ConsoleLogManager 缓冲区
    """

    def __init__(self, original_stream, stream_name: str, manager: 'ConsoleLogManager'):
        self._original = original_stream
        self._stream_name = stream_name  # "stdout" 或 "stderr"
        self._manager = manager
        self.encoding = getattr(original_stream, 'encoding', 'utf-8')

    def write(self, text: str) -> int:
        """拦截 write 调用"""
        try:
            result = self._original.write(text)
        except Exception:
            result = 0

        try:
            if text and text.strip():
                self._manager.add_line(text.rstrip('\n'), self._stream_name)
        except Exception:
            pass

        return result

    def flush(self):
        """传递 flush 调用"""
        try:
            self._original.flush()
        except Exception:
            pass

    def fileno(self):
        """传递 fileno 调用"""
        return self._original.fileno()

    def isatty(self):
        """传递 isatty 调用"""
        return self._original.isatty()

    def __getattr__(self, name):
        """其他属性代理到原始流"""
        return getattr(self._original, name)


class ConsoleLogManager:
    """
    控制台日志管理器（单例）
    维护环形缓冲区，支持 SSE 增量推送
    """

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
        self._buffer: deque = deque(maxlen=2000)
        self._line_id: int = 0
        self._buffer_lock = threading.Lock()
        self._new_line_event = threading.Event()
        self._installed = False
        self._original_stdout = None
        self._original_stderr = None
        self._initialized = True

    def install(self):
        """安装 stdout/stderr 拦截器"""
        if self._installed:
            return

        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

        sys.stdout = StreamInterceptor(self._original_stdout, 'stdout', self)
        sys.stderr = StreamInterceptor(self._original_stderr, 'stderr', self)

        self._installed = True

    def uninstall(self):
        """卸载拦截器，恢复原始流"""
        if not self._installed:
            return

        if self._original_stdout:
            sys.stdout = self._original_stdout
        if self._original_stderr:
            sys.stderr = self._original_stderr

        self._installed = False

    def add_line(self, text: str, stream: str = 'stdout'):
        """添加一行到缓冲区"""
        with self._buffer_lock:
            self._line_id += 1
            entry = {
                'id': self._line_id,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'stream': stream,
                'text': text
            }
            self._buffer.append(entry)

        self._new_line_event.set()
        self._new_line_event.clear()

    def get_lines_after(self, last_id: int = 0) -> List[Dict[str, Any]]:
        """获取指定 ID 之后的所有行"""
        with self._buffer_lock:
            return [line for line in self._buffer if line['id'] > last_id]

    def get_history(self, lines: int = 200) -> List[Dict[str, Any]]:
        """获取最近 N 行历史"""
        with self._buffer_lock:
            items = list(self._buffer)
            return items[-lines:] if len(items) > lines else items

    def get_latest_id(self) -> int:
        """获取当前最新行 ID"""
        with self._buffer_lock:
            return self._line_id

    def clear(self):
        """清空缓冲区"""
        with self._buffer_lock:
            self._buffer.clear()

    def wait_for_new_line(self, timeout: float = 15.0) -> bool:
        """等待新行到达，返回是否有新行"""
        return self._new_line_event.wait(timeout=timeout)


# 全局单例
console_manager = ConsoleLogManager()
