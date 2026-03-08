# -*- coding: utf-8 -*-
"""
全球事件链后台服务
从 world-monitor.com/api/signal-markers 获取事件，缓存到 MongoDB，异步翻译
"""

import time
import threading
import traceback
from datetime import datetime
from typing import Dict
from models.events import (
    get_event_by_id, save_event, get_untranslated_events,
    mark_event_translated, delete_old_events, get_events_count
)
from models.settings import get_translation_config
from models.logger import log_system, log_error


def _print(msg: str):
    """带时间戳的 print，确保立即刷新到终端"""
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[事件链 {ts}] {msg}", flush=True)


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
            _print("后台服务已在运行，跳过重复启动")
            log_system("事件后台服务已在运行")
            return

        self.running = True

        self.fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self.fetch_thread.start()

        self.translate_thread = threading.Thread(target=self._translate_loop, daemon=True)
        self.translate_thread.start()

        _print("✓ 后台服务已启动（获取间隔 {}秒，翻译间隔 {}秒）".format(self.fetch_interval, self.translate_interval))
        log_system("事件后台服务已启动")

    def stop(self):
        """停止后台服务"""
        self.running = False
        _print("后台服务已停止")
        log_system("事件后台服务已停止")

    def _fetch_loop(self):
        """获取事件循环"""
        _print("获取线程启动")
        while self.running:
            try:
                _print("开始获取全球事件...")
                self._fetch_and_cache_events()
            except Exception as e:
                _print(f"✗ 获取事件异常: {e}")
                _print(traceback.format_exc())
                log_error("获取事件失败", str(e))
            _print(f"等待 {self.fetch_interval} 秒后再次获取...")
            time.sleep(self.fetch_interval)

    def _translate_loop(self):
        """翻译事件循环"""
        _print("翻译线程启动，等待 10 秒让获取先执行...")
        time.sleep(10)

        while self.running:
            try:
                untranslated = get_untranslated_events(limit=3)
                if untranslated:
                    _print(f"发现 {len(untranslated)} 个未翻译事件")
                    for event in untranslated:
                        if not self.running:
                            break
                        self._translate_event(event)
                else:
                    _print("暂无未翻译事件")
            except Exception as e:
                _print(f"✗ 翻译循环异常: {e}")
                _print(traceback.format_exc())
                log_error("翻译事件失败", str(e))
            time.sleep(self.translate_interval)

    def _fetch_and_cache_events(self):
        """从 world-monitor.com/api/signal-markers 获取并缓存事件"""
        try:
            import requests
            import urllib3
            urllib3.disable_warnings()

            url = 'https://world-monitor.com/api/signal-markers'
            headers = {
                'accept': '*/*',
                'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'referer': 'https://world-monitor.com/',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            _print(f"正在请求 {url} ...")
            resp = requests.get(url, headers=headers, timeout=30, verify=False)
            _print(f"HTTP 响应: {resp.status_code}, 内容长度: {len(resp.content)} 字节")
            resp.raise_for_status()

            data = resp.json()
            locations = data.get('locations', [])
            _print(f"API 返回 {len(locations)} 个事件位置")

            if len(locations) == 0:
                _print("⚠ API 返回空列表，跳过处理")
                return

            # 打印前3条数据的关键字段，用于调试
            for i, loc in enumerate(locations[:3]):
                _print(f"  样本[{i}]: id={loc.get('id','?')}, name={loc.get('location_name','?')[:40]}, "
                       f"country={loc.get('country','?')}, intensity={loc.get('intensity','?')}, "
                       f"summary长度={len(loc.get('summary',''))}")

            new_count = 0
            updated_count = 0
            error_count = 0

            for loc in locations:
                try:
                    event_id = loc.get('id', '')
                    if not event_id:
                        _print(f"  ⚠ 跳过无 id 的事件: {str(loc)[:100]}")
                        continue

                    existing = get_event_by_id(event_id)

                    # 解析最近提及时间用于排序
                    last_mentioned = loc.get('last_mentioned_at', '')
                    last_mentioned_sort = 0
                    if last_mentioned:
                        try:
                            from dateutil import parser as date_parser
                            last_mentioned_sort = date_parser.parse(last_mentioned).timestamp()
                        except Exception as e:
                            _print(f"  ⚠ 解析时间失败 ({last_mentioned}): {e}")
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
                        'source_tweets': loc.get('source_tweets', [])[:10],
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

                    result = save_event(event_data)
                    if not result:
                        _print(f"  ✗ 保存事件失败: {event_id}")
                        error_count += 1

                except Exception as e:
                    error_count += 1
                    _print(f"  ✗ 处理事件异常: {loc.get('id', '?')} - {e}")
                    log_error(f"处理事件失败: {loc.get('id', 'unknown')}", str(e))

            total = get_events_count()
            _print(f"✓ 缓存完成: 新增 {new_count}, 更新 {updated_count}, 失败 {error_count}, 数据库总计 {total}")
            log_system(f"事件缓存完成: 新增 {new_count}, 更新 {updated_count}, 总计 {total}")

            deleted = delete_old_events(30)
            if deleted > 0:
                _print(f"清理了 {deleted} 个旧事件")
                log_system(f"清理了 {deleted} 个旧事件")

        except requests.exceptions.RequestException as e:
            _print(f"✗ 网络请求失败: {e}")
            _print(traceback.format_exc())
            log_error("获取和缓存事件失败", str(e))
        except Exception as e:
            _print(f"✗ 获取和缓存事件失败: {e}")
            _print(traceback.format_exc())
            log_error("获取和缓存事件失败", str(e))

    def _translate_event(self, event: Dict):
        """翻译单个事件的 summary + location_name + country"""
        try:
            event_id = event.get('event_id')
            summary = event.get('summary', '')
            location_name = event.get('location_name', '')
            country = event.get('country', '')

            _print(f"翻译事件: {event_id} | {location_name[:40]} | {country}")

            config = get_translation_config()
            _print(f"  翻译配置: api_url={config.get('api_url', '未设置')}, model={config.get('model', '未设置')}, "
                   f"api_key={'已设置' if config.get('api_key') else '未设置'}")

            if not config.get('api_key') or not config.get('api_url'):
                _print(f"  ⚠ 翻译配置不完整，跳过翻译（标记为已翻译避免重试）")
                mark_event_translated(event_id, {'summary_cn': summary or ''})
                return

            translated_fields = {}

            # 翻译 summary
            if summary:
                _print(f"  翻译 summary（{len(summary)} 字符）...")
                summary_cn = self._translate_text(summary, config)
                if summary_cn:
                    translated_fields['summary_cn'] = summary_cn
                    _print(f"  ✓ summary 翻译完成: {summary_cn[:60]}...")
                else:
                    _print(f"  ✗ summary 翻译失败（返回空）")

            # 翻译 location_name + country
            if location_name or country:
                loc_parts = []
                if location_name:
                    loc_parts.append(f"[1] {location_name}")
                if country:
                    loc_parts.append(f"[2] {country}")

                if len(loc_parts) == 2:
                    combined = "\n".join(loc_parts)
                    prompt = f"请将以下编号文本翻译成简体中文，保持编号格式，只返回翻译结果：\n\n{combined}"
                    _print(f"  翻译地名+国家...")
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
                        _print(f"  ✓ 地名: {translated_fields.get('location_name_cn', '?')}, 国家: {translated_fields.get('country_cn', '?')}")
                    else:
                        _print(f"  ✗ 地名+国家翻译失败")
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
                _print(f"  翻译 {len(recent_points)} 条 key_points...")
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
                    kp_cn = []
                    for i, p in enumerate(recent_points):
                        kp_cn.append({
                            'date': p.get('date', ''),
                            'point': translated_points[i] if i < len(translated_points) else p.get('point', '')
                        })
                    translated_fields['key_points_cn'] = kp_cn
                    _print(f"  ✓ key_points 翻译完成（{len(translated_points)} 条）")
                else:
                    _print(f"  ✗ key_points 翻译失败")

            if translated_fields:
                mark_event_translated(event_id, translated_fields)
                _print(f"✓ 事件翻译完成: {event_id}，翻译字段: {list(translated_fields.keys())}")
                log_system(f"事件翻译完成: {event_id}")
            else:
                mark_event_translated(event_id, {'summary_cn': summary or ''})
                _print(f"⚠ 事件翻译无结果，标记跳过: {event_id}")

        except Exception as e:
            _print(f"✗ 翻译事件异常: {event.get('event_id', '?')} - {e}")
            _print(traceback.format_exc())
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
                _print(f"  ⚠ LLM 配置缺失: api_url={'有' if api_url else '无'}, api_key={'有' if api_key else '无'}")
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
                _print(f"  ✗ 翻译API错误: HTTP {resp.status_code}, 响应: {resp.text[:200]}")
                log_error("翻译 API 返回错误", f"状态码: {resp.status_code}")
                return ''

        except Exception as e:
            _print(f"  ✗ 翻译请求异常: {e}")
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
