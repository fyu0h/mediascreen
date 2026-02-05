# -*- coding: utf-8 -*-
"""
Telegram 后台监控服务
使用 Telethon 客户端连接 Telegram，监听群组消息，
匹配关键词触发报警，通过企业微信 Webhook 推送通知
"""

import asyncio
import threading
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

import aiohttp

from models.settings import get_setting


class TelegramMonitor:
    """Telegram 群组监控服务"""

    def __init__(self):
        self._clients: Dict[str, Any] = {}  # account_id -> TelegramClient
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        # 登录验证相关
        self._pending_auth: Dict[str, Dict[str, Any]] = {}  # account_id -> auth state

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> Dict[str, Any]:
        """获取监控服务状态"""
        connected_accounts = []
        for acc_id, client in self._clients.items():
            try:
                is_connected = client.is_connected() if client else False
            except Exception:
                is_connected = False
            connected_accounts.append({
                'account_id': acc_id,
                'connected': is_connected,
            })

        return {
            'running': self._running,
            'connected_accounts': connected_accounts,
            'total_clients': len(self._clients),
        }

    # ==================== 启停控制 ====================

    def start(self):
        """启动监控服务（在后台线程运行事件循环）"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()
        print("[Telegram] 监控服务已启动")

    def stop(self):
        """停止监控服务"""
        self._running = False

        # 断开所有客户端
        if self._loop and self._loop.is_running():
            for acc_id in list(self._clients.keys()):
                asyncio.run_coroutine_threadsafe(
                    self._disconnect_client(acc_id), self._loop
                )

        self._clients.clear()
        print("[Telegram] 监控服务已停止")

    def _run_event_loop(self):
        """在后台线程中运行异步事件循环"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._main_loop())
        except Exception as e:
            print(f"[Telegram] 事件循环异常: {e}")
        finally:
            self._loop.close()
            self._running = False

    async def _main_loop(self):
        """主事件循环：自动连接已有活跃账号"""
        from models.telegram import get_all_accounts, get_enabled_group_ids

        # 自动连接已有 session 的账号
        accounts = get_all_accounts()
        for acc in accounts:
            if acc.get('status') == 'active':
                try:
                    await self._connect_account(acc['id'])
                except Exception as e:
                    print(f"[Telegram] 自动连接账号 {acc['name']} 失败: {e}")

        # 保持运行
        while self._running:
            await asyncio.sleep(1)

    # ==================== 账号连接 ====================

    async def _connect_account(self, account_id: str):
        """连接 Telegram 账号"""
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        from models.telegram import get_account_by_id, update_account_status

        account = get_account_by_id(account_id)
        if not account:
            raise ValueError(f'账号 {account_id} 不存在')

        api_id = int(account['api_id'])
        api_hash = account['api_hash']
        session_string = account.get('session_string', '')

        client = TelegramClient(
            StringSession(session_string),
            api_id,
            api_hash
        )

        await client.connect()

        if await client.is_user_authorized():
            # 已授权，保存 session 并注册消息监听
            new_session = client.session.save()
            update_account_status(account_id, 'active', new_session)
            self._clients[account_id] = client
            await self._register_handlers(account_id, client)
            print(f"[Telegram] 账号 {account['name']} 已连接")
        else:
            # 需要验证
            self._clients[account_id] = client
            update_account_status(account_id, 'pending_auth')

    async def _disconnect_client(self, account_id: str):
        """断开客户端连接"""
        client = self._clients.get(account_id)
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass

    def connect_account(self, account_id: str) -> Dict[str, Any]:
        """同步接口：发起账号连接/登录"""
        if not self._running or not self._loop:
            return {'success': False, 'error': '监控服务未运行'}

        future = asyncio.run_coroutine_threadsafe(
            self._async_connect_and_send_code(account_id), self._loop
        )
        try:
            result = future.result(timeout=30)
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _async_connect_and_send_code(self, account_id: str) -> Dict[str, Any]:
        """异步连接账号并发送验证码"""
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        from models.telegram import get_account_by_id, update_account_status

        try:
            account = get_account_by_id(account_id)
            if not account:
                return {'success': False, 'error': '账号不存在'}

            api_id = int(account['api_id'])
            api_hash = account['api_hash']
            phone = account['phone']
            session_string = account.get('session_string', '')

            client = TelegramClient(
                StringSession(session_string),
                api_id,
                api_hash
            )

            await client.connect()

            if await client.is_user_authorized():
                # 已登录
                new_session = client.session.save()
                update_account_status(account_id, 'active', new_session)
                self._clients[account_id] = client
                await self._register_handlers(account_id, client)
                return {'success': True, 'status': 'active', 'message': '已登录'}
            else:
                # 发送验证码
                sent = await client.send_code_request(phone)
                self._clients[account_id] = client
                self._pending_auth[account_id] = {
                    'phone': phone,
                    'phone_code_hash': sent.phone_code_hash,
                }
                update_account_status(account_id, 'pending_auth')
                return {'success': True, 'status': 'pending_auth', 'message': '验证码已发送'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def verify_code(self, account_id: str, code: str, password: str = None) -> Dict[str, Any]:
        """同步接口：验证登录码"""
        if not self._running or not self._loop:
            return {'success': False, 'error': '监控服务未运行'}

        future = asyncio.run_coroutine_threadsafe(
            self._async_verify_code(account_id, code, password), self._loop
        )
        try:
            result = future.result(timeout=30)
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _async_verify_code(self, account_id: str, code: str, password: str = None) -> Dict[str, Any]:
        """异步验证登录码"""
        from telethon.errors import SessionPasswordNeededError
        from models.telegram import get_account_by_id, update_account_status

        try:
            client = self._clients.get(account_id)
            if not client:
                return {'success': False, 'error': '客户端未连接'}

            auth_state = self._pending_auth.get(account_id, {})
            phone = auth_state.get('phone', '')
            phone_code_hash = auth_state.get('phone_code_hash', '')

            try:
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if password:
                    await client.sign_in(password=password)
                else:
                    return {'success': False, 'status': 'need_password', 'message': '需要两步验证密码'}

            # 登录成功
            new_session = client.session.save()
            update_account_status(account_id, 'active', new_session)
            await self._register_handlers(account_id, client)
            self._pending_auth.pop(account_id, None)

            return {'success': True, 'status': 'active', 'message': '登录成功'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==================== 消息监听 ====================

    async def _register_handlers(self, account_id: str, client):
        """注册消息监听器"""
        from telethon import events
        from models.telegram import (
            get_enabled_group_ids, save_message, match_keywords,
            get_highest_level, save_alert, increment_group_stats,
            get_all_groups
        )

        # 获取群组标题映射
        groups = get_all_groups(account_id)
        group_info: Dict[int, Dict[str, str]] = {}
        for g in groups:
            group_info[g['group_id']] = {
                'title': g['group_title'],
                'link': g.get('group_link', ''),
            }

        @client.on(events.NewMessage())
        async def handler(event):
            """处理新消息"""
            try:
                chat = await event.get_chat()
                chat_id = event.chat_id

                # 只处理已启用的群组消息
                enabled_ids = get_enabled_group_ids()
                if chat_id not in enabled_ids:
                    return

                # 获取发送者信息
                sender = await event.get_sender()
                sender_name = ''
                sender_username = ''
                if sender:
                    sender_name = getattr(sender, 'first_name', '') or ''
                    last_name = getattr(sender, 'last_name', '') or ''
                    if last_name:
                        sender_name = f"{sender_name} {last_name}"
                    sender_username = getattr(sender, 'username', '') or ''

                content = event.message.text or ''
                if not content:
                    return

                group_title = getattr(chat, 'title', '') or str(chat_id)
                timestamp = event.message.date.replace(tzinfo=None) if event.message.date else datetime.now()

                # 关键词匹配
                matched = match_keywords(content)
                is_alert = len(matched) > 0
                matched_kw_names = [m['keyword'] for m in matched]

                # 保存消息
                save_message(
                    group_id=chat_id,
                    group_title=group_title,
                    message_id=event.message.id,
                    sender_name=sender_name,
                    sender_username=sender_username,
                    content=content,
                    timestamp=timestamp,
                    is_alert=is_alert,
                    matched_keywords=matched_kw_names,
                )

                # 更新群组统计
                increment_group_stats(chat_id, is_alert)

                # 如果匹配到关键词，创建报警
                if is_alert:
                    highest = get_highest_level(matched)
                    ginfo = group_info.get(chat_id, {})
                    group_link = ginfo.get('link', '')

                    # 发送 Webhook
                    webhook_sent = await self._send_webhook(
                        group_title=group_title,
                        sender_name=sender_name,
                        content=content,
                        matched_keywords=matched_kw_names,
                        highest_level=highest,
                        group_link=group_link,
                    )

                    save_alert(
                        group_id=chat_id,
                        group_title=group_title,
                        group_link=group_link,
                        sender_name=sender_name,
                        content=content,
                        matched_keywords=matched_kw_names,
                        highest_level=highest,
                        timestamp=timestamp,
                        webhook_sent=webhook_sent,
                    )

            except Exception as e:
                print(f"[Telegram] 消息处理异常: {e}")

    # ==================== 群组搜索 ====================

    def search_groups(self, account_id: str, query: str) -> Dict[str, Any]:
        """同步接口：搜索群组"""
        if not self._running or not self._loop:
            return {'success': False, 'error': '监控服务未运行'}

        future = asyncio.run_coroutine_threadsafe(
            self._async_search_groups(account_id, query), self._loop
        )
        try:
            result = future.result(timeout=30)
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _async_search_groups(self, account_id: str, query: str) -> Dict[str, Any]:
        """异步搜索群组"""
        try:
            client = self._clients.get(account_id)
            if not client:
                return {'success': False, 'error': '账号未连接'}

            if not await client.is_user_authorized():
                return {'success': False, 'error': '账号未登录'}

            results = []

            # 搜索公开群组/频道
            try:
                from telethon.tl.functions.contacts import SearchRequest
                search_result = await client(SearchRequest(q=query, limit=20))
                for chat in search_result.chats:
                    chat_title = getattr(chat, 'title', '') or ''
                    chat_username = getattr(chat, 'username', '') or ''
                    chat_link = f"https://t.me/{chat_username}" if chat_username else ''
                    results.append({
                        'group_id': chat.id,
                        'group_title': chat_title,
                        'group_link': chat_link,
                        'username': chat_username,
                    })
            except Exception as e:
                print(f"[Telegram] 搜索异常: {e}")

            # 也搜索已加入的对话
            try:
                from telethon.tl.types import Channel, Chat
                async for dialog in client.iter_dialogs(limit=100):
                    entity = dialog.entity
                    if isinstance(entity, (Channel, Chat)):
                        title = dialog.title or ''
                        if query.lower() in title.lower():
                            username = getattr(entity, 'username', '') or ''
                            link = f"https://t.me/{username}" if username else ''
                            # 避免重复
                            if not any(r['group_id'] == entity.id for r in results):
                                results.append({
                                    'group_id': entity.id,
                                    'group_title': title,
                                    'group_link': link,
                                    'username': username,
                                })
            except Exception as e:
                print(f"[Telegram] 搜索对话异常: {e}")

            return {'success': True, 'groups': results}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==================== Webhook 推送 ====================

    async def _send_webhook(self, group_title: str, sender_name: str,
                            content: str, matched_keywords: List[str],
                            highest_level: str, group_link: str = '') -> bool:
        """发送企业微信 Webhook 通知"""
        webhook_url = get_setting('telegram.webhook_url', '')
        webhook_enabled = get_setting('telegram.webhook_enabled', False)

        if not webhook_enabled or not webhook_url:
            return False

        try:
            level_text = {'high': '高风险', 'medium': '中风险', 'low': '关注'}.get(highest_level, '未知')
            level_color = {'high': 'warning', 'medium': 'comment', 'low': 'info'}.get(highest_level, 'info')

            # 构建 markdown 消息
            markdown_content = (
                f"## Telegram 报警通知\n"
                f"**等级**: <font color=\"{level_color}\">{level_text}</font>\n"
                f"**群组**: {group_title}\n"
                f"**发言人**: {sender_name}\n"
                f"**触发词**: {', '.join(matched_keywords)}\n"
                f"**内容**: {content[:200]}\n"
            )
            if group_link:
                markdown_content += f"**群组链接**: [{group_link}]({group_link})\n"

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": markdown_content
                }
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        return True
                    else:
                        print(f"[Telegram] Webhook 发送失败: {resp.status}")
                        return False

        except Exception as e:
            print(f"[Telegram] Webhook 异常: {e}")
            return False

    def test_webhook(self, webhook_url: str = None) -> Dict[str, Any]:
        """测试 Webhook 推送"""
        if not webhook_url:
            webhook_url = get_setting('telegram.webhook_url', '')

        if not webhook_url:
            return {'success': False, 'error': 'Webhook URL 未配置'}

        import requests
        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": (
                        "## Telegram 监控测试\n"
                        "这是一条测试消息，用于验证企业微信 Webhook 配置是否正确。\n"
                        f"**发送时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                }
            }
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                result_data = resp.json()
                if result_data.get('errcode', 0) == 0:
                    return {'success': True, 'message': '推送成功'}
                else:
                    return {'success': False, 'error': f"企业微信返回错误: {result_data.get('errmsg', '')}"}
            else:
                return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# 全局单例
telegram_monitor = TelegramMonitor()
