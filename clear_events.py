#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""清理事件缓存"""

import sys
sys.path.insert(0, '.')

from models.events import get_events_collection, get_events_count

print("=" * 50)
print("清理事件缓存")
print("=" * 50)

# 获取当前事件数量
count = get_events_count()
print(f"\n当前事件数量: {count}")

if count == 0:
    print("数据库中没有事件，无需清理")
    sys.exit(0)

# 确认清理
print("\n⚠️  警告：此操作将删除所有事件数据！")
confirm = input("确认清理？(yes/no): ")

if confirm.lower() != 'yes':
    print("已取消清理")
    sys.exit(0)

# 清理数据
try:
    collection = get_events_collection()
    result = collection.delete_many({})
    print(f"\n✓ 已删除 {result.deleted_count} 个事件")
    print("✓ 清理完成！")
except Exception as e:
    print(f"\n✗ 清理失败: {e}")
    sys.exit(1)

print("\n" + "=" * 50)
