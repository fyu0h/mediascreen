# -*- coding: utf-8 -*-
"""
models 模块：数据库连接与查询封装
"""

from .mongo import get_db, close_db

__all__ = ['get_db', 'close_db']
