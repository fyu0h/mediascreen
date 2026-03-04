# -*- coding: utf-8 -*-
"""
全球事件链后台服务
负责定时获取、缓存和翻译事件
"""

import time
import threading
from datetime import datetime
from typing import List, Dict
from models.events import (
    get_event_by_id, save_event, get_untranslated_events,
    mark_event_translated, delete_old_events, get_events_count
)
from models.settings import get_translation_config
from models.logger import log_system, log_error


class EventsBackgroundService:
    """事件后台服务"""

    def __init__(self):
        self.running = False
        self.fetch_thread = None
        self.translate_thread = None
        self.fetch_interval = 300  # 5分钟获取一次
        self.translate_interval = 10  # 10秒翻译一次

    def start(self):
        """启动后台服务"""
        if self.running:
            log_system("事件后台服务已在运行")
            return

        self.running = True

        # 启动获取线程
        self.fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self.fetch_thread.start()

        # 启动翻译线程
        self.translate_thread = threading.Thread(target=self._translate_loop, daemon=True)
        self.translate_thread.start()

        log_system("事件后台服务已启动")

    def stop(self):
        """停止后台服务"""
        self.running = False
        log_system("事件后台服务已停止")

    def _fetch_loop(self):
        """获取事件循环"""
        while self.running:
            try:
                log_system("开始获取全球事件...")
                self._fetch_and_cache_events()
                log_system(f"事件获取完成，等待 {self.fetch_interval} 秒")
            except Exception as e:
                log_error("获取事件失败", str(e))

            # 等待下一次执行
            time.sleep(self.fetch_interval)

    def _translate_loop(self):
        """翻译事件循环"""
        # 启动时等待5秒，让获取先执行
        time.sleep(5)

        while self.running:
            try:
                # 获取未翻译的事件
                untranslated = get_untranslated_events(limit=5)

                if untranslated:
                    log_system(f"发现 {len(untranslated)} 个未翻译事件，开始翻译...")
                    for event in untranslated:
                        if not self.running:
                            break
                        self._translate_event(event)
                else:
                    log_system("没有待翻译的事件")

            except Exception as e:
                log_error("翻译事件失败", str(e))

            # 等待下一次执行
            time.sleep(self.translate_interval)

    def _fetch_and_cache_events(self):
        """获取并缓存事件"""
        try:
            import requests
            import urllib3
            urllib3.disable_warnings()

            headers = {
                'accept': '*/*',
                'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'referer': 'https://world-monitor.com/',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            resp = requests.get(
                'https://world-monitor.com/api/signal-markers',
                headers=headers,
                timeout=15,
                verify=False
            )
            resp.raise_for_status()
            data = resp.json()

            locations = data.get('locations', [])
            log_system(f"获取到 {len(locations)} 个事件")

            new_count = 0
            updated_count = 0

            for location in locations:
                try:
                    # 使用 location id 作为唯一标识
                    event_id = location.get('id', '')
                    if not event_id:
                        continue

                    # 检查是否已存在
                    existing = get_event_by_id(event_id)

                    # 提取事件信息
                    location_name = location.get('location_name', '')
                    country = location.get('country', '')
                    summary = location.get('summary', '')
                    key_points = location.get('key_points', [])

                    # 确定严重程度
                    severity = 'medium'
                    summary_lower = summary.lower()
                    if any(word in summary_lower for word in ['war', 'nuclear', 'attack', 'strike', 'military', 'conflict']):
                        severity = 'high'
                    elif any(word in summary_lower for word in ['tension', 'dispute', 'concern', 'warning']):
                        severity = 'medium'
                    else:
                        severity = 'low'

                    # 提取时间戳
                    timestamp = None
                    timestamp_sort = 0

                    if key_points and len(key_points) > 0:
                        first_point = key_points[0]
                        date_str = first_point.get('date', '')
                        if date_str:
                            try:
                                from dateutil import parser as date_parser
                                parsed_date = date_parser.parse(date_str)
                                timestamp = parsed_date.isoformat()
                                timestamp_sort = parsed_date.timestamp()
                            except:
                                timestamp = datetime.now().isoformat()
                                timestamp_sort = datetime.now().timestamp()
                        else:
                            timestamp = datetime.now().isoformat()
                            timestamp_sort = datetime.now().timestamp()
                    else:
                        timestamp = datetime.now().isoformat()
                        timestamp_sort = datetime.now().timestamp()

                    # 构建事件数据
                    event_data = {
                        'event_id': event_id,
                        'title': location_name,
                        'description': summary[:500] if len(summary) > 500 else summary,  # 限制长度
                        'summary': summary,  # 保存完整摘要
                        'location': country,
                        'timestamp': timestamp,
                        'timestamp_sort': timestamp_sort,
                        'severity': severity,
                        'key_points': key_points,  # 保存关键点
                        'fetched_at': datetime.now()
                    }

                    # 如果已存在且已翻译，保留翻译
                    if existing:
                        if existing.get('title_cn'):
                            event_data['title_cn'] = existing['title_cn']
                        if existing.get('description_cn'):
                            event_data['description_cn'] = existing['description_cn']
                        if existing.get('location_cn'):
                            event_data['location_cn'] = existing['location_cn']
                        if existing.get('translated_at'):
                            event_data['translated_at'] = existing['translated_at']
                        updated_count += 1
                    else:
                        new_count += 1

                    # 保存到数据库
                    save_event(event_data)

                except Exception as e:
                    log_error(f"处理事件失败: {location.get('id', 'unknown')}", str(e))

            log_system(f"事件缓存完成: 新增 {new_count}, 更新 {updated_count}")

            # 清理30天前的旧事件
            deleted = delete_old_events(30)
            if deleted > 0:
                log_system(f"清理了 {deleted} 个旧事件")

        except Exception as e:
            log_error("获取和缓存事件失败", str(e))

    def _translate_event(self, event: Dict):
        """翻译单个事件"""
        try:
            event_id = event.get('event_id')
            title = event.get('title', '')
            description = event.get('description', '')
            location = event.get('location', '')

            log_system(f"开始翻译事件: {event_id} - {title[:30]}...")

            # 获取翻译配置
            config = get_translation_config()

            # 翻译标题
            title_cn = self._translate_text(title, config) if title else title

            # 翻译描述
            description_cn = self._translate_text(description, config) if description else description

            # 翻译地点
            location_cn = self._translate_text(location, config) if location else location

            # 保存翻译结果
            mark_event_translated(event_id, title_cn, description_cn, location_cn)

            log_system(f"事件翻译完成: {event_id}")

        except Exception as e:
            log_error(f"翻译事件失败: {event.get('event_id', 'unknown')}", str(e))

    def _translate_text(self, text: str, config: dict) -> str:
        """翻译文本"""
        if not text or not text.strip():
            return text

        try:
            import requests
            import urllib3
            urllib3.disable_warnings()

            api_key = config.get('api_key', '')
            model = config.get('model', 'gpt-4o')
            api_url = config.get('api_url', '')

            if not api_key or not api_url:
                return text

            prompt = f"请将以下英文翻译成简体中文，只返回翻译结果，不要添加任何解释：\n\n{text}"

            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                'model': model,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'max_tokens': 1000
            }

            resp = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=30,
                verify=False
            )

            if resp.status_code == 200:
                result = resp.json()
                translated = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                return translated if translated else text
            else:
                return text

        except Exception as e:
            log_error("翻译文本失败", str(e))
            return text


# 全局服务实例
_events_service = None


def get_events_service() -> EventsBackgroundService:
    """获取事件服务单例"""
    global _events_service
    if _events_service is None:
        _events_service = EventsBackgroundService()
    return _events_service


def start_events_service():
    """启动事件服务"""
    service = get_events_service()
    service.start()


def stop_events_service():
    """停止事件服务"""
    service = get_events_service()
    service.stop()
