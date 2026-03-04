#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化事件数据"""

import sys
sys.path.insert(0, '.')

from services.events_service import get_events_service
from models.events import get_events_count

print("=" * 50)
print("初始化事件数据")
print("=" * 50)

# 获取服务实例
service = get_events_service()

# 手动触发获取
print("\n正在从 world-monitor.com 获取事件...")
try:
    service._fetch_and_cache_events()
    print("✓ 事件获取成功")
except Exception as e:
    print(f"✗ 获取失败: {e}")
    sys.exit(1)

# 检查结果
count = get_events_count()
print(f"\n数据库中的事件数量: {count}")

if count > 0:
    print("✓ 初始化成功！")
else:
    print("✗ 初始化失败，数据库中没有事件")
    sys.exit(1)

print("\n" + "=" * 50)
