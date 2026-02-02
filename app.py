# -*- coding: utf-8 -*-
"""
Flask 应用入口
启动方式: python app.py
访问地址: http://localhost:5000
"""

from flask import Flask
from flask_cors import CORS

from config import Config
from routes import api_bp, views_bp
from models import close_db
from models.logger import log_system


def create_app() -> Flask:
    """创建 Flask 应用实例"""
    app = Flask(__name__)

    # 加载配置
    app.config.from_object(Config)

    # 启用 CORS（允许前端开发调试）
    CORS(app)

    # 注册蓝图
    app.register_blueprint(api_bp)
    app.register_blueprint(views_bp)

    # 应用关闭时关闭数据库连接
    @app.teardown_appcontext
    def shutdown_db(exception=None):
        pass  # 使用单例模式，不需要每次请求都关闭

    return app


# 创建应用实例
app = create_app()


if __name__ == '__main__':
    print("=" * 50)
    print("新闻态势感知仪表盘")
    print("=" * 50)
    print(f"访问地址: http://localhost:5000")
    print(f"MongoDB: {Config.MONGO_HOST}:{Config.MONGO_PORT}/{Config.MONGO_DB}")
    print("=" * 50)
    print("按 Ctrl+C 停止服务器")
    print()

    # 记录系统启动日志
    log_system(
        action='系统启动',
        details={
            'host': '0.0.0.0',
            'port': 5000,
            'debug': Config.DEBUG,
            'mongo': f'{Config.MONGO_HOST}:{Config.MONGO_PORT}/{Config.MONGO_DB}'
        },
        status='success'
    )

    # 启动 Flask 开发服务器
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=Config.DEBUG
    )
