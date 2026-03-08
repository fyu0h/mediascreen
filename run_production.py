# -*- coding: utf-8 -*-
"""
生产环境启动脚本
使用 Waitress 作为 WSGI 服务器（支持 Windows）

启动方式: python run_production.py
"""

import sys

def check_dependencies():
    """检查并安装必要依赖"""
    try:
        import waitress
    except ImportError:
        print("[提示] 正在安装 waitress...")
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'waitress'])
        print("[提示] waitress 安装完成")


def main():
    check_dependencies()

    from waitress import serve
    from app import app, init_database, init_plugins, init_schedulers, init_telegram, init_events_service
    from config import Config
    from models.logger import log_system

    # 生产环境配置
    # 修改说明: 将 '127.0.0.1' 改为 '0.0.0.0' 以允许局域网或外网访问
    HOST = '0.0.0.0'
    PORT = 5000
    THREADS = 8         # 工作线程数（小型应用 4-8 足够）

    print("=" * 50)
    print("皇岗边检站全球舆情态势感知平台")
    print("=" * 50)
    print(f"运行模式: 生产环境 (Waitress)")
    print(f"监听地址: http://{HOST}:{PORT} (允许外部访问)")
    print(f"工作线程: {THREADS}")
    print(f"MongoDB: {Config.MONGO_HOST}:{Config.MONGO_PORT}/{Config.MONGO_DB}")
    print("=" * 50)

    # 初始化数据库、插件、调度器、Telegram 监控、事件链
    init_database()
    init_plugins()
    init_schedulers()
    init_telegram()
    init_events_service()

    # 记录启动日志
    log_system(
        action='系统启动（生产模式）',
        details={
            'server': 'waitress',
            'host': HOST,
            'port': PORT,
            'threads': THREADS
        },
        status='success'
    )

    print(f"\n服务已启动，按 Ctrl+C 停止")
    print(f"提示: 请配置 Nginx 反向代理或直接访问 http://服务器IP:{PORT}\n")

    # 启动 Waitress 服务器
    serve(
        app,
        host=HOST,
        port=PORT,
        threads=THREADS,
        url_scheme='http',
        ident='SituationAwareness'  # 服务器标识
    )


if __name__ == '__main__':
    main()