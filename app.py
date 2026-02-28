# -*- coding: utf-8 -*-
"""
Flask 应用入口
启动方式: python app.py
访问地址: http://localhost:5000
"""

import os
import time
from datetime import timedelta
from flask import Flask, request, g
from flask_cors import CORS

from config import Config
from routes import api_bp, views_bp
from models import close_db
from models.logger import log_system, log_request


def create_app() -> Flask:
    """创建 Flask 应用实例"""
    app = Flask(__name__)

    # 加载配置
    app.config.from_object(Config)
    app.permanent_session_lifetime = timedelta(hours=12)

    # CORS 配置（限制跨域来源）
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:5000", "http://127.0.0.1:5000", "http://home.iinin.me:9906"],
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["Content-Type"],
            "supports_credentials": True
        }
    })

    # 注册蓝图
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    # ========== 请求日志中间件 ==========
    @app.before_request
    def before_request_logging():
        """请求开始前记录"""
        g.request_start_time = time.time()
        # 保存原始请求数据
        g.request_data = {
            'method': request.method,
            'url': request.url,
            'path': request.path,
            'query_string': request.query_string.decode('utf-8', errors='ignore'),
            'headers': dict(request.headers),
            'remote_addr': request.remote_addr
        }
        # 保存请求体（仅对 POST/PUT/PATCH），并对敏感字段脱敏
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if request.is_json:
                    body = request.get_json(silent=True)
                    g.request_data['body'] = _filter_sensitive_body(body)
                elif request.form:
                    body = dict(request.form)
                    g.request_data['body'] = _filter_sensitive_body(body)
                else:
                    # 尝试获取原始数据（限制大小）
                    raw_data = request.get_data(as_text=True)
                    if len(raw_data) > 10000:
                        g.request_data['body'] = raw_data[:10000] + '... [截断]'
                    else:
                        g.request_data['body'] = raw_data
            except Exception:
                g.request_data['body'] = '<无法解析请求体>'

    @app.after_request
    def after_request_logging(response):
        """请求完成后记录日志"""
        # 跳过静态资源和健康检查
        if request.path.startswith('/static') or request.path == '/favicon.ico':
            return response

        # 计算耗时
        duration_ms = None
        if hasattr(g, 'request_start_time'):
            duration_ms = (time.time() - g.request_start_time) * 1000

        # 获取响应体
        response_body = None
        try:
            if response.content_type and 'application/json' in response.content_type:
                response_body = response.get_json(silent=True)
            elif response.content_type and 'text/' in response.content_type:
                data = response.get_data(as_text=True)
                if len(data) > 5000:
                    response_body = data[:5000] + '... [截断]'
                else:
                    response_body = data
        except Exception:
            response_body = '<无法解析响应体>'

        # 确定日志状态
        if response.status_code >= 500:
            status = 'error'
        elif response.status_code >= 400:
            status = 'warning'
        else:
            status = 'info'

        # 构建请求信息
        req_data = getattr(g, 'request_data', {})

        # 过滤敏感信息（如 API Key）
        filtered_headers = _filter_sensitive_headers(req_data.get('headers', {}))
        req_data['headers'] = filtered_headers

        # 记录日志
        log_request(
            action=f'{request.method} {request.path}',
            url=request.url,
            method=request.method,
            request_headers=filtered_headers,
            request_body=req_data.get('body'),
            response_status=response.status_code,
            response_headers=dict(response.headers),
            response_body=response_body,
            duration_ms=round(duration_ms, 2) if duration_ms else None,
            status=status
        )

        return response

    # 应用关闭时关闭数据库连接
    @app.teardown_appcontext
    def shutdown_db(exception=None):
        pass  # 使用单例模式，不需要每次请求都关闭

    return app


def _filter_sensitive_headers(headers: dict) -> dict:
    """过滤敏感头信息"""
    sensitive_keys = ['authorization', 'cookie', 'x-api-key', 'api-key', 'token']
    filtered = {}
    for key, value in headers.items():
        if key.lower() in sensitive_keys:
            filtered[key] = '***已隐藏***'
        else:
            filtered[key] = value
    return filtered


def _filter_sensitive_body(body) -> any:
    """过滤请求体中的敏感字段（如密码、API 密钥等）"""
    if not isinstance(body, dict):
        # 非字典类型直接返回原值
        return body

    # 敏感字段关键词列表
    sensitive_keywords = ['password', 'api_key', 'secret', 'token', 'apikey', 'api_secret']
    filtered = {}
    for key, value in body.items():
        # 递归处理嵌套字典
        if isinstance(value, dict):
            filtered[key] = _filter_sensitive_body(value)
        elif any(keyword in key.lower() for keyword in sensitive_keywords):
            # 键名包含敏感关键词，隐藏值
            filtered[key] = '***已隐藏***'
        else:
            filtered[key] = value
    return filtered


def init_database():
    """初始化数据库（迁移和索引）"""
    from models.sites import migrate_from_json, ensure_indexes
    from models.users import ensure_admin_user
    from models.mongo import ensure_articles_indexes, ensure_alert_reads_indexes
    from models.tasks import ensure_task_indexes
    from models.logger import ensure_indexes as ensure_log_indexes

    # 迁移 sites.json 到 MongoDB（兼容旧数据）
    migrated = migrate_from_json()
    if migrated > 0:
        print(f"[数据迁移] 已从 sites.json 迁移 {migrated} 个站点到 MongoDB")

    # 确保索引存在
    ensure_indexes()

    # 确保文章集合索引存在（性能优化）
    ensure_articles_indexes()

    # 确保告警已读集合索引存在
    ensure_alert_reads_indexes()

    # 确保任务集合索引存在
    ensure_task_indexes()

    # 确保日志集合索引存在（含 TTL 自动过期）
    ensure_log_indexes()

    # 确保默认管理员账号存在
    ensure_admin_user()


def init_plugins():
    """初始化插件系统"""
    from plugins.registry import register_builtin_plugins
    from models.plugins import init_default_subscriptions, ensure_indexes as ensure_plugin_indexes

    # 注册内置插件
    register_builtin_plugins()

    # 确保插件订阅索引存在
    ensure_plugin_indexes()

    # 初始化默认订阅配置
    count = init_default_subscriptions()
    if count > 0:
        print(f"[插件系统] 已初始化 {count} 个站点的默认订阅配置")


def init_schedulers():
    """初始化定时任务调度器"""
    from plugins.scheduler import start_all_schedulers
    from plugins.crawl_scheduler import init_crawl_scheduler

    # 启动RSS调度器
    start_all_schedulers()
    print("[调度器] RSS定时任务已启动（每5分钟更新）")

    # 启动全量爬取调度器（根据设置决定是否激活）
    init_crawl_scheduler()
    print("[调度器] 全量爬取调度器已初始化")


def init_telegram():
    """初始化 Telegram 监控服务"""
    try:
        from models.telegram import ensure_telegram_indexes
        from models.settings import get_setting

        # 确保 Telegram 相关集合索引
        ensure_telegram_indexes()

        # 如果配置了自动启动，则启动监控
        monitor_enabled = get_setting('telegram.monitor_enabled', False)
        if monitor_enabled:
            from services.telegram_monitor import telegram_monitor
            telegram_monitor.start()
            print("[Telegram] 监控服务已自动启动")
        else:
            print("[Telegram] 监控服务未启用（可在设置中启动）")
    except Exception as e:
        print(f"[Telegram] 初始化失败: {e}")


# 创建应用实例
app = create_app()


if __name__ == '__main__':
    print("=" * 50)
    print("皇岗边检站全球舆情态势感知平台")
    print("=" * 50)
    flask_host = os.environ.get('FLASK_HOST', '127.0.0.1')
    print(f"访问地址: http://{flask_host}:5000")
    print(f"MongoDB: {Config.MONGO_HOST}:{Config.MONGO_PORT}/{Config.MONGO_DB}")
    print("=" * 50)

    # 初始化数据库（迁移和索引）
    init_database()

    # 初始化插件系统
    init_plugins()

    # 初始化定时调度器
    init_schedulers()

    # 初始化 Telegram 监控
    init_telegram()

    print("按 Ctrl+C 停止服务器")
    print()

    # 记录系统启动日志
    log_system(
        action='系统启动',
        details={
            'host': flask_host,
            'port': 5000,
            'debug': Config.DEBUG,
            'mongo': f'{Config.MONGO_HOST}:{Config.MONGO_PORT}/{Config.MONGO_DB}'
        },
        status='success'
    )

    # 启动 Flask 开发服务器
    # 启用多线程模式，确保爬虫任务不会阻塞前端请求
    # 注意：Windows 上 debug+threaded 模式下热重载可能报 socket 错误，不影响功能
    # 开发模式默认绑定 localhost，通过环境变量 FLASK_HOST 可覆盖
    app.run(
        host=flask_host,
        port=5000,
        debug=Config.DEBUG,
        threaded=True,           # 启用多线程处理请求
        use_reloader=False       # Windows 下禁用热重载，避免 socket 错误
    )
