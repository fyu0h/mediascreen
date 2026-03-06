# -*- coding: utf-8 -*-
"""
全球事件链后台服务
从 world-monitor.com/api/events 获取事件，缓存到 MongoDB，异步翻译
"""

import time
import threading
from datetime import datetime
from typing import Dict
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
        # 启动时等待10秒，让获取先执行
        time.sleep(10)

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

            except Exception as e:
                log_error("翻译事件失败", str(e))

            # 等待下一次执行
            time.sleep(self.translate_interval)

    def _fetch_and_cache_events(self):
        """从 world-monitor.com/api/events 获取并缓存事件到 MongoDB"""
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
                'https://world-monitor.com/api/events',
                headers=headers,
                timeout=30,
                verify=False
            )
            resp.raise_for_status()
            data = resp.json()

            markers = data.get('markers', [])
            log_system(f"获取到 {len(markers)} 个事件")

            new_count = 0
            updated_count = 0

            for marker in markers:
                try:
                    event_id = marker.get('id', '')
                    if not event_id:
                        continue

                    # 检查是否已存在（保留已有翻译）
                    existing = get_event_by_id(event_id)

                    # 解析时间戳
                    timestamp = marker.get('timestamp', '')
                    timestamp_sort = 0
                    if timestamp:
                        try:
                            from dateutil import parser as date_parser
                            parsed_date = date_parser.parse(timestamp)
                            timestamp_sort = parsed_date.timestamp()
                        except Exception:
                            timestamp_sort = datetime.now().timestamp()
                    else:
                        timestamp_sort = datetime.now().timestamp()

                    # 构建事件数据（完整保留 API 原始字段）
                    event_data = {
                        'event_id': event_id,
                        'actor1': marker.get('actor1', ''),
                        'actor2': marker.get('actor2', ''),
                        'country': marker.get('country', ''),
                        'headline': marker.get('headline', ''),
                        'location': marker.get('location', ''),
                        'notes': marker.get('notes', ''),
                        'position': marker.get('position', []),
                        'relevance_score': marker.get('relevanceScore', 0),
                        'severity': marker.get('severity', 1),
                        'source': marker.get('source', ''),
                        'source_url': marker.get('sourceUrl', ''),
                        'sub_event_type': marker.get('subEventType', ''),
                        'timestamp': timestamp,
                        'timestamp_sort': timestamp_sort,
                        'title': marker.get('title', ''),
                        'type': marker.get('type', ''),
                        'fetched_at': datetime.now()
                    }

                    # 如果已存在且已翻译，保留翻译字段
                    if existing:
                        for cn_field in ['headline_cn', 'notes_cn', 'country_cn',
                                         'location_cn', 'sub_event_type_cn', 'translated_at']:
                            if existing.get(cn_field):
                                event_data[cn_field] = existing[cn_field]
                        updated_count += 1
                    else:
                        new_count += 1

                    # 保存到数据库
                    save_event(event_data)

                except Exception as e:
                    log_error(f"处理事件失败: {marker.get('id', 'unknown')}", str(e))

            log_system(f"事件缓存完成: 新增 {new_count}, 更新 {updated_count}, 总计 {get_events_count()}")

            # 清理30天前的旧事件
            deleted = delete_old_events(30)
            if deleted > 0:
                log_system(f"清理了 {deleted} 个旧事件")

        except Exception as e:
            log_error("获取和缓存事件失败", str(e))

    def _translate_event(self, event: Dict):
        """翻译单个事件的关键字段"""
        try:
            event_id = event.get('event_id')
            headline = event.get('headline', '')
            notes = event.get('notes', '')
            country = event.get('country', '')
            location = event.get('location', '')
            sub_event_type = event.get('sub_event_type', '')

            log_system(f"开始翻译事件: {event_id} - {headline[:50]}...")

            # 获取翻译配置
            config = get_translation_config()

            # 批量翻译：将多个字段合并为一次请求以节省 API 调用
            fields_to_translate = {}
            if headline:
                fields_to_translate['headline'] = headline
            if notes and notes != headline:
                fields_to_translate['notes'] = notes
            if sub_event_type:
                fields_to_translate['sub_event_type'] = sub_event_type

            translated_fields = {}

            # 合并翻译（headline + notes + sub_event_type 一次翻译）
            if fields_to_translate:
                batch_result = self._translate_batch(fields_to_translate, config)
                for key, cn_text in batch_result.items():
                    translated_fields[f'{key}_cn'] = cn_text

            # 国家和地点单独处理（通常较短，可以合并翻译）
            location_fields = {}
            if country:
                location_fields['country'] = country
            if location:
                location_fields['location'] = location

            if location_fields:
                loc_result = self._translate_batch(location_fields, config)
                for key, cn_text in loc_result.items():
                    translated_fields[f'{key}_cn'] = cn_text

            # 保存翻译结果
            if translated_fields:
                mark_event_translated(event_id, translated_fields)
                log_system(f"事件翻译完成: {event_id}")
            else:
                # 即使没有可翻译字段，也标记为已翻译，避免反复尝试
                mark_event_translated(event_id, {'headline_cn': headline or ''})

        except Exception as e:
            log_error(f"翻译事件失败: {event.get('event_id', 'unknown')}", str(e))

    def _translate_batch(self, fields: Dict[str, str], config: dict) -> Dict[str, str]:
        """批量翻译多个字段（合并为一次 API 调用）"""
        if not fields:
            return {}

        # 如果只有一个字段，直接翻译
        if len(fields) == 1:
            key = list(fields.keys())[0]
            text = fields[key]
            translated = self._translate_text(text, config)
            return {key: translated}

        # 多个字段合并翻译
        lines = []
        keys = list(fields.keys())
        for i, key in enumerate(keys):
            lines.append(f"[{i+1}] {fields[key]}")

        combined_text = "\n".join(lines)
        prompt = (
            f"请将以下编号文本翻译成简体中文，保持编号格式，只返回翻译结果：\n\n"
            f"{combined_text}"
        )

        translated_text = self._translate_text_with_prompt(prompt, config)

        # 解析结果
        result = {}
        if translated_text:
            translated_lines = translated_text.strip().split('\n')
            for i, key in enumerate(keys):
                if i < len(translated_lines):
                    line = translated_lines[i].strip()
                    # 移除编号前缀 [1] [2] 等
                    import re
                    line = re.sub(r'^\[\d+\]\s*', '', line)
                    result[key] = line if line else fields[key]
                else:
                    result[key] = fields[key]
        else:
            # 翻译失败，返回原文
            result = dict(fields)

        return result

    def _translate_text(self, text: str, config: dict) -> str:
        """翻译单段文本"""
        if not text or not text.strip():
            return text

        prompt = f"请将以下英文翻译成简体中文，只返回翻译结果，不要添加任何解释：\n\n{text}"
        return self._translate_text_with_prompt(prompt, config)

    def _translate_text_with_prompt(self, prompt: str, config: dict) -> str:
        """使用自定义提示词调用 LLM 翻译"""
        try:
            import requests
            import urllib3
            urllib3.disable_warnings()

            api_key = config.get('api_key', '')
            model = config.get('model', 'gpt-4o')
            api_url = config.get('api_url', '')

            if not api_key or not api_url:
                return ''

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
                'max_tokens': 2000
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
                return translated if translated else ''
            else:
                log_error("翻译 API 返回错误", f"状态码: {resp.status_code}")
                return ''

        except Exception as e:
            log_error("翻译文本失败", str(e))
            return ''


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
