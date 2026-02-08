# -*- coding: utf-8 -*-
"""
成果展示模块
管理用户上传的成果展示内容
"""

import os
import json
import uuid
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# 数据文件路径
DATA_DIR = os.path.dirname(os.path.dirname(__file__))
ACHIEVEMENTS_FILE = os.path.join(DATA_DIR, 'achievements.json')
UPLOAD_DIR = os.path.join(DATA_DIR, 'static', 'uploads', 'achievements')

# 确保上传目录存在
os.makedirs(UPLOAD_DIR, exist_ok=True)


def load_achievements() -> List[Dict[str, Any]]:
    """加载所有成果"""
    if not os.path.exists(ACHIEVEMENTS_FILE):
        return []

    try:
        with open(ACHIEVEMENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_achievements(achievements: List[Dict[str, Any]]) -> bool:
    """保存成果列表"""
    try:
        with open(ACHIEVEMENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(achievements, f, ensure_ascii=False, indent=2)
        return True
    except IOError as e:
        print(f"保存成果失败: {e}")
        return False


def _is_internal_url(url: str) -> bool:
    """检查 URL 是否指向内网地址（SSRF 防护）"""
    import ipaddress
    import socket

    parsed = urlparse(url)
    hostname = parsed.hostname

    if not hostname:
        return True

    # 检查常见内网主机名
    if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1'):
        return True

    try:
        # 解析域名为 IP 地址并检查是否为内网
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        return ip.is_private or ip.is_loopback or ip.is_reserved
    except (socket.gaierror, ValueError):
        return False


def fetch_page_title(url: str) -> Optional[str]:
    """
    从URL抓取页面标题

    Args:
        url: 网页链接

    Returns:
        页面标题，抓取失败返回 None
    """
    try:
        # SSRF 防护：拒绝内网地址
        if _is_internal_url(url):
            print(f"[安全] 拒绝请求内网地址: {url}")
            return None

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()

        # 尝试检测编码
        response.encoding = response.apparent_encoding or 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')

        # 优先获取 og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()

        # 其次获取 title 标签
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            return title_tag.string.strip()

        # 最后尝试 h1 标签
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text().strip()

        return None

    except requests.RequestException as e:
        print(f"抓取页面标题失败: {e}")
        return None
    except Exception as e:
        print(f"解析页面失败: {e}")
        return None


def add_achievement(
    title: str,
    url: str,
    image_filename: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    添加新成果

    Args:
        title: 成果标题
        url: 引用链接
        image_filename: 上传的图片文件名
        description: 描述（可选）

    Returns:
        新创建的成果对象
    """
    achievements = load_achievements()

    # 生成唯一 ID
    achievement_id = str(uuid.uuid4())[:8]

    new_achievement = {
        'id': achievement_id,
        'title': title,
        'url': url,
        'image': image_filename,
        'description': description,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # 添加到列表开头（最新的在前）
    achievements.insert(0, new_achievement)

    save_achievements(achievements)

    return new_achievement


def update_achievement(
    achievement_id: str,
    title: Optional[str] = None,
    url: Optional[str] = None,
    image_filename: Optional[str] = None,
    description: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """更新成果"""
    achievements = load_achievements()

    for achievement in achievements:
        if achievement['id'] == achievement_id:
            if title is not None:
                achievement['title'] = title
            if url is not None:
                achievement['url'] = url
            if image_filename is not None:
                achievement['image'] = image_filename
            if description is not None:
                achievement['description'] = description

            achievement['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            save_achievements(achievements)
            return achievement

    return None


def delete_achievement(achievement_id: str) -> bool:
    """删除成果"""
    achievements = load_achievements()

    for i, achievement in enumerate(achievements):
        if achievement['id'] == achievement_id:
            # 删除关联的图片文件
            if achievement.get('image'):
                image_path = os.path.join(UPLOAD_DIR, achievement['image'])
                if os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except OSError:
                        pass

            achievements.pop(i)
            save_achievements(achievements)
            return True

    return False


def get_achievement(achievement_id: str) -> Optional[Dict[str, Any]]:
    """获取单个成果"""
    achievements = load_achievements()

    for achievement in achievements:
        if achievement['id'] == achievement_id:
            return achievement

    return None


def get_all_achievements() -> List[Dict[str, Any]]:
    """获取所有成果"""
    return load_achievements()


def save_uploaded_image(file_data: bytes, original_filename: str) -> str:
    """
    保存上传的图片

    Args:
        file_data: 图片二进制数据
        original_filename: 原始文件名

    Returns:
        保存后的文件名
    """
    # 获取文件扩展名
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        ext = '.jpg'

    # 生成唯一文件名
    new_filename = f"{uuid.uuid4().hex[:12]}{ext}"

    # 保存文件
    file_path = os.path.join(UPLOAD_DIR, new_filename)
    with open(file_path, 'wb') as f:
        f.write(file_data)

    return new_filename


def delete_image(filename: str) -> bool:
    """删除图片文件"""
    if not filename:
        return False

    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return True
        except OSError:
            return False

    return False
