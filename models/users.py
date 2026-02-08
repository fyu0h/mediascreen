# -*- coding: utf-8 -*-
"""
用户管理模块
提供用户注册、验证、密码管理等功能
"""

from datetime import datetime
from typing import Optional, Dict, Any

from werkzeug.security import generate_password_hash, check_password_hash

from models import get_db


# 集合名称
COLLECTION_USERS = 'users'


def get_users_collection():
    """获取用户集合"""
    db = get_db()
    return db[COLLECTION_USERS]


def ensure_user_indexes():
    """确保用户集合索引存在"""
    collection = get_users_collection()
    collection.create_index('username', unique=True)


def create_user(username: str, password: str, role: str = 'admin') -> Optional[str]:
    """
    创建用户

    参数:
        username: 用户名
        password: 明文密码
        role: 角色（admin/viewer）

    返回:
        用户ID字符串，失败返回 None
    """
    collection = get_users_collection()

    # 检查用户名是否已存在
    if collection.find_one({'username': username}):
        return None

    user_doc = {
        'username': username,
        'password_hash': generate_password_hash(password),
        'role': role,
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'last_login': None
    }

    result = collection.insert_one(user_doc)
    return str(result.inserted_id)


def verify_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    验证用户登录

    参数:
        username: 用户名
        password: 明文密码

    返回:
        验证成功返回用户信息字典，失败返回 None
    """
    collection = get_users_collection()
    user = collection.find_one({'username': username})

    if not user:
        return None

    if not check_password_hash(user['password_hash'], password):
        return None

    # 更新最后登录时间
    collection.update_one(
        {'_id': user['_id']},
        {'$set': {'last_login': datetime.now()}}
    )

    return {
        'id': str(user['_id']),
        'username': user['username'],
        'role': user.get('role', 'admin')
    }


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """
    修改密码

    参数:
        username: 用户名
        old_password: 旧密码
        new_password: 新密码

    返回:
        修改成功返回 True
    """
    collection = get_users_collection()
    user = collection.find_one({'username': username})

    if not user:
        return False

    if not check_password_hash(user['password_hash'], old_password):
        return False

    collection.update_one(
        {'_id': user['_id']},
        {'$set': {
            'password_hash': generate_password_hash(new_password),
            'updated_at': datetime.now()
        }}
    )
    return True


def get_user(username: str) -> Optional[Dict[str, Any]]:
    """获取用户信息（不含密码哈希）"""
    collection = get_users_collection()
    user = collection.find_one({'username': username})

    if not user:
        return None

    return {
        'id': str(user['_id']),
        'username': user['username'],
        'role': user.get('role', 'admin'),
        'created_at': user.get('created_at'),
        'last_login': user.get('last_login')
    }


def ensure_admin_user():
    """
    确保默认管理员账号存在
    首次启动时自动创建 admin/admin123
    """
    collection = get_users_collection()

    # 确保索引
    ensure_user_indexes()

    # 检查是否已有用户
    if collection.count_documents({}) == 0:
        create_user('admin', 'admin123', 'admin')
        print("[用户系统] 已创建默认管理员账号 admin（请登录后修改密码）")
