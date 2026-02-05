# -*- coding: utf-8 -*-
"""
全量爬取定时调度器
支持在前端配置启用/禁用和爬取间隔
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed


class CrawlScheduler:
    """
    全量爬取定时调度器
    按配置间隔自动触发所有启用站点的爬取
    """

    def __init__(self):
        self.enabled = False
        self.interval = 1800  # 秒（默认30分钟）
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.last_crawl_time: Optional[datetime] = None
        self.next_crawl_time: Optional[datetime] = None
        self._lock = threading.Lock()
        self.stats = {
            'total_runs': 0,
            'total_saved': 0,
            'last_error': None,
        }

    def start(self):
        """根据设置启动定时全量爬取"""
        from models.settings import get_setting

        self.enabled = get_setting('crawler.auto_crawl_enabled', False)
        interval_minutes = get_setting('crawler.auto_crawl_interval', 30)
        self.interval = max(interval_minutes, 5) * 60  # 最少5分钟

        if not self.enabled:
            print("[CrawlScheduler] 定时全量爬取未启用")
            return

        if self.running:
            print("[CrawlScheduler] 调度器已在运行中")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print(f"[CrawlScheduler] 定时全量爬取已启动，间隔 {interval_minutes} 分钟")

    def stop(self):
        """停止定时全量爬取"""
        self.running = False
        self.enabled = False
        if self.thread:
            self.thread.join(timeout=5)
        self.next_crawl_time = None
        print("[CrawlScheduler] 定时全量爬取已停止")

    def update_settings(self, enabled: bool, interval_minutes: int):
        """
        更新配置并重启/停止调度器

        Args:
            enabled: 是否启用
            interval_minutes: 间隔（分钟）
        """
        from models.settings import set_setting

        # 保存到设置文件
        set_setting('crawler.auto_crawl_enabled', enabled)
        set_setting('crawler.auto_crawl_interval', interval_minutes)

        with self._lock:
            old_enabled = self.enabled
            old_interval = self.interval

            self.enabled = enabled
            self.interval = max(interval_minutes, 5) * 60

            if enabled and not old_enabled:
                # 从禁用变为启用
                if not self.running:
                    self.running = True
                    self.thread = threading.Thread(target=self._run_loop, daemon=True)
                    self.thread.start()
                    print(f"[CrawlScheduler] 定时全量爬取已启动，间隔 {interval_minutes} 分钟")
            elif not enabled and old_enabled:
                # 从启用变为禁用
                self.running = False
                self.next_crawl_time = None
                print("[CrawlScheduler] 定时全量爬取已停止")
            elif enabled and self.interval != old_interval:
                # 间隔变更，更新下次执行时间
                if self.last_crawl_time:
                    self.next_crawl_time = self.last_crawl_time + timedelta(seconds=self.interval)
                print(f"[CrawlScheduler] 更新间隔为 {interval_minutes} 分钟")

    def _run_loop(self):
        """后台运行循环"""
        # 首次启动延迟120秒，等待系统完全启动
        startup_delay = 120
        print(f"[CrawlScheduler] 等待 {startup_delay} 秒后开始首次全量爬取...")
        for _ in range(startup_delay):
            if not self.running:
                return
            time.sleep(1)

        while self.running:
            if not self.enabled:
                time.sleep(5)
                continue

            try:
                self._do_crawl()
            except Exception as e:
                self.stats['last_error'] = str(e)
                print(f"[CrawlScheduler] 全量爬取出错: {e}")

            # 计算下次执行时间
            self.last_crawl_time = datetime.now()
            self.next_crawl_time = self.last_crawl_time + timedelta(seconds=self.interval)

            # 等待下一次
            for _ in range(self.interval):
                if not self.running or not self.enabled:
                    break
                time.sleep(1)

    def _do_crawl(self):
        """执行一次全量爬取"""
        print(f"[CrawlScheduler] 开始全量爬取 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        result = execute_full_crawl(source='auto_scheduler')

        self.stats['total_runs'] += 1
        self.stats['total_saved'] += result.get('total_saved', 0)

        print(f"[CrawlScheduler] 全量爬取完成: "
              f"{result.get('success_count', 0)}成功, "
              f"{result.get('failed_count', 0)}失败, "
              f"保存{result.get('total_saved', 0)}篇")

    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        return {
            'enabled': self.enabled,
            'running': self.running,
            'interval_minutes': self.interval // 60,
            'last_crawl_time': self.last_crawl_time.isoformat() if self.last_crawl_time else None,
            'next_crawl_time': self.next_crawl_time.isoformat() if self.next_crawl_time else None,
            'stats': self.stats
        }


def execute_full_crawl(source: str = 'manual') -> Dict[str, Any]:
    """
    执行全量爬取核心逻辑（可被API端点和调度器复用）

    Args:
        source: 触发来源 ('manual', 'auto_scheduler')

    Returns:
        爬取结果字典
    """
    from models.plugins import get_enabled_sites
    from plugins.crawler import get_crawler
    from models.mongo import save_articles
    from models.tasks import (
        create_task, update_task, register_running_task,
        unregister_task, is_cancelled
    )
    from models.logger import log_operation

    sites = get_enabled_sites()
    if not sites:
        return {
            'task_id': None,
            'success_count': 0,
            'failed_count': 0,
            'skipped_count': 0,
            'total_articles': 0,
            'total_saved': 0,
            'message': '没有启用的站点'
        }

    # 创建任务记录
    task_id = create_task(task_type='crawl', sites=sites)

    try:
        update_task(task_id, {
            'status': 'running',
            'started_at': datetime.now(),
            'message': f'正在初始化... (来源: {source})'
        })

        total = len(sites)
        completed = 0
        success_count = 0
        failed_count = 0
        skipped_count = 0
        total_articles = 0
        total_saved = 0
        sites_status = {}

        def crawl_single_site(site, index):
            """爬取单个站点"""
            if is_cancelled(task_id):
                return None

            site_id = site.get('id')
            site_name = site.get('name', '')

            update_task(task_id, {
                'current_site': site_name,
                'message': f'正在获取: {site_name} ({index + 1}/{total})'
            })

            try:
                crawler = get_crawler()
                result = crawler.crawl_site(site, max_articles=100)

                if result['success']:
                    articles = result.get('articles', [])
                    saved_count = save_articles(articles) if articles else 0
                    return {
                        'site_id': site_id,
                        'site_name': site_name,
                        'success': True,
                        'skipped': False,
                        'articles': len(articles),
                        'saved': saved_count,
                        'error': None
                    }
                else:
                    is_skipped = result.get('skipped', False)
                    return {
                        'site_id': site_id,
                        'site_name': site_name,
                        'success': False,
                        'skipped': is_skipped,
                        'articles': 0,
                        'saved': 0,
                        'error': result.get('error', '爬取失败')[:100]
                    }
            except Exception as e:
                error_msg = str(e)
                is_timeout = 'timeout' in error_msg.lower()
                return {
                    'site_id': site_id,
                    'site_name': site_name,
                    'success': False,
                    'skipped': is_timeout,
                    'articles': 0,
                    'saved': 0,
                    'error': ('超时跳过' if is_timeout else error_msg)[:100]
                }

        # 并发爬取
        max_workers = min(5, total)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_site = {
                executor.submit(crawl_single_site, site, i): site
                for i, site in enumerate(sites)
            }

            for future in as_completed(future_to_site):
                if is_cancelled(task_id):
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

                result = future.result()
                if result is None:
                    continue

                completed += 1
                site_id = result['site_id']
                sites_status[site_id] = result

                if result['success']:
                    success_count += 1
                    total_articles += result['articles']
                    total_saved += result['saved']
                elif result.get('skipped', False):
                    skipped_count += 1
                else:
                    failed_count += 1

                progress = int((completed / total) * 100)
                update_task(task_id, {
                    'progress': progress,
                    'completed_sites': completed,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'skipped_count': skipped_count,
                    'total_articles': total_articles,
                    'total_saved': total_saved,
                    'current_site': result['site_name'],
                    'sites_status': sites_status,
                    'message': f'已完成 {completed}/{total}'
                })

        # 最终状态
        if not is_cancelled(task_id):
            msg_parts = [f'{success_count}成功']
            if skipped_count > 0:
                msg_parts.append(f'{skipped_count}跳过')
            if failed_count > 0:
                msg_parts.append(f'{failed_count}失败')
            msg_parts.append(f'保存{total_saved}篇')

            update_task(task_id, {
                'status': 'completed',
                'progress': 100,
                'skipped_count': skipped_count,
                'finished_at': datetime.now(),
                'message': f'完成: {", ".join(msg_parts)}'
            })

            log_operation(
                action='文章更新完成',
                details={
                    'task_id': task_id,
                    'source': source,
                    'success_count': success_count,
                    'failed_count': failed_count,
                    'total_articles': total_articles,
                    'total_saved': total_saved
                },
                status='success' if failed_count == 0 else 'warning'
            )

        return {
            'task_id': task_id,
            'success_count': success_count,
            'failed_count': failed_count,
            'skipped_count': skipped_count,
            'total_articles': total_articles,
            'total_saved': total_saved,
            'message': f'{success_count}成功, {failed_count}失败, 保存{total_saved}篇'
        }

    except Exception as e:
        update_task(task_id, {
            'status': 'failed',
            'finished_at': datetime.now(),
            'error': str(e)[:200],
            'message': f'任务失败: {str(e)[:50]}'
        })
        from models.logger import log_operation
        log_operation(
            action='文章更新失败',
            details={'task_id': task_id, 'source': source, 'error': str(e)},
            status='error'
        )
        return {
            'task_id': task_id,
            'success_count': 0,
            'failed_count': 0,
            'skipped_count': 0,
            'total_articles': 0,
            'total_saved': 0,
            'message': f'失败: {str(e)[:100]}'
        }
    finally:
        unregister_task(task_id)


# 全局调度器实例
_crawl_scheduler_instance: Optional[CrawlScheduler] = None


def get_crawl_scheduler() -> CrawlScheduler:
    """获取全量爬取调度器单例"""
    global _crawl_scheduler_instance
    if _crawl_scheduler_instance is None:
        _crawl_scheduler_instance = CrawlScheduler()
    return _crawl_scheduler_instance


def init_crawl_scheduler():
    """初始化全量爬取调度器（app启动时调用）"""
    scheduler = get_crawl_scheduler()
    scheduler.start()
