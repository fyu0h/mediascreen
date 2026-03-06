# -*- coding: utf-8 -*-
"""
全球事件链后台服务
从 world-monitor.com/api/signal-markers 获取事件，缓存到 MongoDB，异步翻译
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
        self.translate_interval = 15  # 15秒翻译一批

    def start(self):
        """启动后台服务"""
        if self.running:
            log_system("事件后台服务已在运行")
            return

        self.running = True

        self.fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self.fetch_thread.start()

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
            time.sleep(self.fetch_interval)

    def _translate_loop(self):
        """翻译事件循环"""
        time.sleep(10)  # 启动后等待获取先执行

        while self.running:
            try:
                untranslated = get_untranslated_events(limit=3)
                if untranslated:
                    log_system(f"发现 {len(untranslated)} 个未翻译事件，开始翻译...")
                    for event in untranslated:
                        if not self.running:
                            break
                        self._translate_event(event)
            except Exception as e:
                log_error("翻译事件失败", str(e))
            time.sleep(self.translate_interval)

    def _fetch_and_cache_events(self):
        """从 world-monitor.com/api/signal-markers 获取并缓存事件"""
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
                timeout=30,
                verify=False
            )
            resp.raise_for_status()
            data = resp.json()

            locations = data.get('locations', [])
            log_system(f"获取到 {len(locations)} 个事件位置")

            new_count = 0
            updated_count = 0

            for loc in locations:
                try:
                    event_id = loc.get('id', '')
                    if not event_id:
                        continue

                    existing = get_event_by_id(event_id)

                    # 解析最近提及时间用于排序
                    last_mentioned = loc.get('last_mentioned_at', '')
                    last_mentioned_sort = 0
                    if last_mentioned:
                        try:
                            from dateutil import parser as date_parser
                            last_mentioned_sort = date_parser.parse(last_mentioned).timestamp()
                        except Exception:
                            last_mentioned_sort = datetime.now().timestamp()

                    # 截取最近的 key_points（最多保留50条）
                    key_points = loc.get('key_points', [])
                    if len(key_points) > 50:
                        key_points = key_points[-50:]

                    event_data = {
                        'event_id': event_id,
                        'location_name': loc.get('location_name', ''),
                        'country': loc.get('country', ''),
                        'lat': loc.get('lat', 0),
                        'lng': loc.get('lng', 0),
                        'summary': loc.get('summary', ''),
                        'analysis': loc.get('analysis', ''),
                        'key_points': key_points,
                        'intensity': loc.get('intensity', 1),
                        'mention_count': loc.get('mention_count', 0),
                        'source_tweets': loc.get('source_tweets', [])[:10],  # 最多保留10条推文
                        'first_seen_at': loc.get('first_seen_at', ''),
                        'last_mentioned_at': last_mentioned,
                        'last_mentioned_sort': last_mentioned_sort,
                        'fetched_at': datetime.now()
                    }

                    # 保留已有翻译
                    if existing:
                        for cn_field in ['summary_cn', 'location_name_cn', 'country_cn',
                                         'key_points_cn', 'translated_at']:
                            if existing.get(cn_field):
                                event_data[cn_field] = existing[cn_field]
                        updated_count += 1
                    else:
                        new_count += 1

                    save_event(event_data)

                except Exception as e:
                    log_error(f"处理事件失败: {loc.get('id', 'unknown')}", str(e))

            log_system(f"事件缓存完成: 新增 {new_count}, 更新 {updated_count}, 总计 {get_events_count()}")

            deleted = delete_old_events(30)
            if deleted > 0:
                log_system(f"清理了 {deleted} 个旧事件")

        except Exception as e:
            log_error("获取和缓存事件失败", str(e))

    def _translate_event(self, event: Dict):
        """翻译单个事件的 summary + location_name + country"""
        try:
            event_id = event.get('event_id')
            summary = event.get('summary', '')
            location_name = event.get('location_name', '')
            country = event.get('country', '')

            log_system(f"开始翻译事件: {event_id} - {location_name[:40]}...")

            config = get_translation_config()
            translated_fields = {}

            # 翻译 summary（最重要）
            if summary:
                summary_cn = self._translate_text(summary, config)
                if summary_cn:
                    translated_fields['summary_cn'] = summary_cn

            # 翻译 location_name + country（合并为一次请求）
            if location_name or country:
                loc_parts = []
                if location_name:
                    loc_parts.append(f"[1] {location_name}")
                if country:
                    loc_parts.append(f"[2] {country}")

                if len(loc_parts) == 2:
                    combined = "\n".join(loc_parts)
                    prompt = f"请将以下编号文本翻译成简体中文，保持编号格式，只返回翻译结果：\n\n{combined}"
                    result = self._translate_text_with_prompt(prompt, config)
                    if result:
                        import re
                        lines = result.strip().split('\n')
                        for line in lines:
                            line = line.strip()
                            if line.startswith('[1]'):
                                translated_fields['location_name_cn'] = re.sub(r'^\[\d+\]\s*', '', line)
                            elif line.startswith('[2]'):
                                translated_fields['country_cn'] = re.sub(r'^\[\d+\]\s*', '', line)
                elif location_name:
                    cn = self._translate_text(location_name, config)
                    if cn:
                        translated_fields['location_name_cn'] = cn
                elif country:
                    cn = self._translate_text(country, config)
                    if cn:
                        translated_fields['country_cn'] = cn

            # 翻译最近5个 key_points
            key_points = event.get('key_points', [])
            if key_points:
                recent_points = key_points[-5:]
                points_text = "\n".join([f"[{i+1}] {p.get('point', '')}" for i, p in enumerate(recent_points)])
                prompt = f"请将以下编号文本翻译成简体中文，保持编号格式，只返回翻译结果：\n\n{points_text}"
                result = self._translate_text_with_prompt(prompt, config)
                if result:
                    import re
                    translated_points = []
                    lines = result.strip().split('\n')
                    for line in lines:
                        line = line.strip()
                        cleaned = re.sub(r'^\[\d+\]\s*', '', line)
                        if cleaned:
                            translated_points.append(cleaned)
                    # 存储翻译后的 key_points（最近5条）
                    kp_cn = []
                    for i, p in enumerate(recent_points):
                        kp_cn.append({
                            'date': p.get('date', ''),
                            'point': translated_points[i] if i < len(translated_points) else p.get('point', '')
                        })
                    translated_fields['key_points_cn'] = kp_cn

            if translated_fields:
                mark_event_translated(event_id, translated_fields)
                log_system(f"事件翻译完成: {event_id}")
            else:
                # 标记为已翻译避免反复尝试
                mark_event_translated(event_id, {'summary_cn': summary or ''})

        except Exception as e:
            log_error(f"翻译事件失败: {event.get('event_id', 'unknown')}", str(e))

    def _translate_text(self, text: str, config: dict) -> str:
        """翻译单段文本"""
        if not text or not text.strip():
            return ''
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
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.3,
                'max_tokens': 2000
            }

            resp = requests.post(api_url, headers=headers, json=payload, timeout=30, verify=False)

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
