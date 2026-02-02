# -*- coding: utf-8 -*-
"""
routes 模块：Flask 路由蓝图
"""

from .api import api_bp
from .views import views_bp

__all__ = ['api_bp', 'views_bp']
