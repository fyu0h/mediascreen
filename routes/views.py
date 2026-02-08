# -*- coding: utf-8 -*-
"""
页面视图路由
"""

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify

from models.users import verify_user

views_bp = Blueprint('views', __name__)


@views_bp.route('/')
def index():
    """首页 - 仪表盘（需要登录）"""
    if 'user' not in session:
        return redirect(url_for('views.login'))
    return render_template('index.html')


@views_bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'GET':
        # 已登录则直接跳转首页
        if 'user' in session:
            return redirect(url_for('views.index'))
        return render_template('login.html')

    # POST 请求 - 处理登录
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': '请求格式错误'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'error': '请输入用户名和密码'}), 400

    user = verify_user(username, password)
    if not user:
        return jsonify({'success': False, 'error': '用户名或密码错误'}), 401

    # 设置 session
    session['user'] = {
        'id': user['id'],
        'username': user['username'],
        'role': user['role']
    }
    session.permanent = True

    return jsonify({'success': True, 'data': {'username': user['username']}})


@views_bp.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    return redirect(url_for('views.login'))
