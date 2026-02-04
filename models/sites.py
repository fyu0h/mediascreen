# -*- coding: utf-8 -*-
"""
网站订阅管理模块
使用 MongoDB 存储站点数据
"""

import json
import os
import re
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from urllib.parse import urlparse, urljoin
import xml.etree.ElementTree as ET
from bson import ObjectId

from config import Config

# 旧版 sites.json 文件路径（用于数据迁移）
SITES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sites.json')

# 常见 sitemap 路径
SITEMAP_PATHS = [
    '/sitemap.xml',
    '/sitemap_index.xml',
    '/sitemap-index.xml',
    '/sitemaps.xml',
    '/sitemap/sitemap.xml',
    '/news-sitemap.xml',
    '/sitemap-news.xml',
    '/post-sitemap.xml',
    '/page-sitemap.xml',
]

# 国家/地区匹配规则（域名后缀 -> 国家代码）
DOMAIN_COUNTRY_MAP = {
    '.cn': 'CN',
    '.com.cn': 'CN',
    '.gov.cn': 'CN',
    '.hk': 'HK',
    '.com.hk': 'HK',
    '.tw': 'TW',
    '.jp': 'JP',
    '.co.jp': 'JP',
    '.kr': 'KR',
    '.co.kr': 'KR',
    '.uk': 'GB',
    '.co.uk': 'GB',
    '.de': 'DE',
    '.fr': 'FR',
    '.ru': 'RU',
    '.in': 'IN',
    '.au': 'AU',
    '.com.au': 'AU',
    '.br': 'BR',
    '.com.br': 'BR',
    '.ca': 'CA',
    '.mx': 'MX',
    '.ar': 'AR',
    '.com.ar': 'AR',
    '.il': 'IL',
    '.pk': 'PK',
    '.kz': 'KZ',
    '.tm': 'TM',
}

# 特定域名 -> 国家代码（优先级更高）
KNOWN_DOMAINS = {
    'apnews.com': 'US',
    'reuters.com': 'GB',
    'bbc.com': 'GB',
    'bbc.co.uk': 'GB',
    'nytimes.com': 'US',
    'washingtonpost.com': 'US',
    'foxnews.com': 'US',
    'cnn.com': 'US',
    'theguardian.com': 'GB',
    'thetimes.co.uk': 'GB',
    'nhk.or.jp': 'JP',
    'kyodonews.jp': 'JP',
    'xinhuanet.com': 'CN',
    'people.com.cn': 'CN',
    'chinadaily.com.cn': 'CN',
    'takungpao.com': 'HK',
    'scmp.com': 'HK',
    'jpost.com': 'IL',
    'infobae.com': 'AR',
    'app.com.pk': 'PK',
}

# 国家代码 -> 首都坐标 [经度, 纬度]
COUNTRY_COORDS = {
    'US': [-77.0369, 38.9072],      # 华盛顿
    'GB': [-0.1276, 51.5074],       # 伦敦
    'CN': [116.4074, 39.9042],      # 北京
    'HK': [114.1694, 22.3193],      # 香港
    'TW': [121.5654, 25.0330],      # 台北
    'JP': [139.6917, 35.6895],      # 东京
    'KR': [126.9780, 37.5665],      # 首尔
    'DE': [13.4050, 52.5200],       # 柏林
    'FR': [2.3522, 48.8566],        # 巴黎
    'RU': [37.6173, 55.7558],       # 莫斯科
    'IN': [77.2090, 28.6139],       # 新德里
    'AU': [149.1300, -35.2809],     # 堪培拉
    'BR': [-47.8825, -15.7942],     # 巴西利亚
    'CA': [-75.6972, 45.4215],      # 渥太华
    'MX': [-99.1332, 19.4326],      # 墨西哥城
    'AR': [-58.3816, -34.6037],     # 布宜诺斯艾利斯
    'IL': [35.2137, 31.7683],       # 耶路撒冷
    'PK': [73.0479, 33.6844],       # 伊斯兰堡
    'KZ': [71.4491, 51.1801],       # 努尔苏丹
    'TM': [58.3833, 37.9601],       # 阿什哈巴德
}


def get_sites_collection():
    """获取站点集合"""
    from models.mongo import get_db
    return get_db()[Config.COLLECTION_SITES]


def _format_site(doc: Dict[str, Any]) -> Dict[str, Any]:
    """格式化站点文档，将 MongoDB _id 转换为 id 字符串"""
    if doc is None:
        return None
    site = dict(doc)
    if '_id' in site:
        site['id'] = str(site.pop('_id'))
    # 格式化日期字段
    for field in ['created_at', 'updated_at']:
        if field in site and isinstance(site[field], datetime):
            site[field] = site[field].strftime('%Y-%m-%d %H:%M:%S')
    return site


def load_sites() -> List[Dict[str, Any]]:
    """加载所有站点"""
    collection = get_sites_collection()
    sites = []
    for doc in collection.find().sort('created_at', -1):
        sites.append(_format_site(doc))
    return sites


def generate_site_id() -> str:
    """生成站点 ID（兼容旧接口，实际使用 MongoDB ObjectId）"""
    return str(ObjectId())


def extract_domain(url: str) -> str:
    """从 URL 提取域名"""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    domain = domain.lower()
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain


def guess_country_code(url: str) -> Optional[str]:
    """根据 URL 推断国家代码"""
    domain = extract_domain(url)

    # 先检查已知域名
    for known_domain, code in KNOWN_DOMAINS.items():
        if domain == known_domain or domain.endswith('.' + known_domain):
            return code

    # 再检查域名后缀
    for suffix, code in DOMAIN_COUNTRY_MAP.items():
        if domain.endswith(suffix):
            return code

    # 默认返回 US（大多数 .com 网站）
    if domain.endswith('.com') or domain.endswith('.org') or domain.endswith('.net'):
        return 'US'

    return None


def get_coords_by_country(country_code: Optional[str]) -> Optional[List[float]]:
    """根据国家代码获取坐标"""
    if country_code and country_code in COUNTRY_COORDS:
        return COUNTRY_COORDS[country_code]
    return None


def check_sitemap(site_url: str, timeout: int = 10) -> Dict[str, Any]:
    """
    检测网站是否支持 sitemap
    返回：{supported: bool, sitemap_url: str|None, error: str|None}
    """
    parsed = urlparse(site_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # 先尝试 robots.txt
    try:
        robots_url = urljoin(base_url, '/robots.txt')
        resp = requests.get(robots_url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            # 从 robots.txt 中查找 Sitemap
            for line in resp.text.split('\n'):
                line = line.strip()
                if line.lower().startswith('sitemap:'):
                    sitemap_url = line.split(':', 1)[1].strip()
                    # 验证 sitemap URL 是否可访问
                    if verify_sitemap(sitemap_url, headers, timeout):
                        return {
                            'supported': True,
                            'sitemap_url': sitemap_url,
                            'error': None
                        }
    except Exception:
        pass

    # 尝试常见 sitemap 路径
    for path in SITEMAP_PATHS:
        sitemap_url = urljoin(base_url, path)
        if verify_sitemap(sitemap_url, headers, timeout):
            return {
                'supported': True,
                'sitemap_url': sitemap_url,
                'error': None
            }

    return {
        'supported': False,
        'sitemap_url': None,
        'error': '未找到有效的 sitemap'
    }


def verify_sitemap(url: str, headers: dict, timeout: int) -> bool:
    """验证 sitemap URL 是否有效"""
    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            content_type = resp.headers.get('Content-Type', '').lower()
            content = resp.text[:1000]  # 只检查开头部分

            # 检查是否是 XML 格式
            if 'xml' in content_type or content.strip().startswith('<?xml') or '<urlset' in content or '<sitemapindex' in content:
                return True
    except Exception:
        pass
    return False


def add_site(name: str, site_url: str, auto_detect: bool = True) -> Dict[str, Any]:
    """
    添加新站点
    参数：
        name: 站点名称
        site_url: 站点 URL
        auto_detect: 是否自动检测 sitemap
    返回：新建的站点信息
    """
    collection = get_sites_collection()

    # 标准化 URL
    if not site_url.startswith(('http://', 'https://')):
        site_url = 'https://' + site_url

    # 检查是否已存在
    domain = extract_domain(site_url)
    existing = collection.find_one({'domain': domain})
    if existing:
        raise ValueError(f'站点 {domain} 已存在')

    # 推断国家和坐标
    country_code = guess_country_code(site_url)
    coords = get_coords_by_country(country_code)

    now = datetime.now()

    # 创建站点记录
    site = {
        'name': name.strip(),
        'url': site_url,
        'domain': domain,
        'country_code': country_code,
        'coords': coords,
        'sitemap_supported': None,
        'sitemap_url': None,
        'fetch_method': 'unknown',  # sitemap / crawler / unknown
        'created_at': now,
        'updated_at': now,
        'status': 'active'
    }

    # 自动检测 sitemap
    if auto_detect:
        try:
            result = check_sitemap(site_url)
            site['sitemap_supported'] = result['supported']
            site['sitemap_url'] = result['sitemap_url']
            site['fetch_method'] = 'sitemap' if result['supported'] else 'crawler'
        except Exception as e:
            site['sitemap_supported'] = False
            site['fetch_method'] = 'crawler'

    result = collection.insert_one(site)
    site['_id'] = result.inserted_id

    return _format_site(site)


def update_site(site_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    更新站点信息
    支持更新：name, url, country_code, status, fetch_method
    """
    collection = get_sites_collection()

    try:
        obj_id = ObjectId(site_id)
    except Exception:
        return None

    # 更新允许的字段
    allowed_fields = ['name', 'url', 'country_code', 'status', 'fetch_method']
    update_data = {}

    for field in allowed_fields:
        if field in kwargs and kwargs[field] is not None:
            update_data[field] = kwargs[field]

    # 如果更新了 URL，重新推断域名和坐标
    if 'url' in kwargs and kwargs['url']:
        update_data['domain'] = extract_domain(kwargs['url'])
        if 'country_code' not in kwargs:
            update_data['country_code'] = guess_country_code(kwargs['url'])
        update_data['coords'] = get_coords_by_country(update_data.get('country_code') or kwargs.get('country_code'))

    # 如果更新了国家代码，更新坐标
    if 'country_code' in kwargs:
        update_data['coords'] = get_coords_by_country(kwargs['country_code'])

    if not update_data:
        return None

    update_data['updated_at'] = datetime.now()

    result = collection.find_one_and_update(
        {'_id': obj_id},
        {'$set': update_data},
        return_document=True
    )

    return _format_site(result) if result else None


def delete_site(site_id: str) -> bool:
    """删除站点"""
    collection = get_sites_collection()

    try:
        obj_id = ObjectId(site_id)
    except Exception:
        return False

    result = collection.delete_one({'_id': obj_id})
    return result.deleted_count > 0


def get_site(site_id: str) -> Optional[Dict[str, Any]]:
    """获取单个站点"""
    collection = get_sites_collection()

    try:
        obj_id = ObjectId(site_id)
    except Exception:
        return None

    doc = collection.find_one({'_id': obj_id})
    return _format_site(doc) if doc else None


def get_all_sites() -> List[Dict[str, Any]]:
    """获取所有站点"""
    return load_sites()


def recheck_sitemap(site_id: str) -> Dict[str, Any]:
    """重新检测站点的 sitemap 支持"""
    collection = get_sites_collection()

    try:
        obj_id = ObjectId(site_id)
    except Exception:
        raise ValueError('无效的站点 ID')

    site = collection.find_one({'_id': obj_id})
    if not site:
        raise ValueError('站点不存在')

    url = site.get('url', '')
    if not url:
        raise ValueError('站点 URL 为空')

    result = check_sitemap(url)

    update_data = {
        'sitemap_supported': result['supported'],
        'sitemap_url': result['sitemap_url'],
        'fetch_method': 'sitemap' if result['supported'] else 'crawler',
        'updated_at': datetime.now()
    }

    updated_site = collection.find_one_and_update(
        {'_id': obj_id},
        {'$set': update_data},
        return_document=True
    )

    return {
        'site': _format_site(updated_site),
        'check_result': result
    }


def migrate_from_json() -> int:
    """
    从 sites.json 迁移数据到 MongoDB
    返回：迁移的站点数量
    """
    if not os.path.exists(SITES_FILE):
        return 0

    try:
        with open(SITES_FILE, 'r', encoding='utf-8') as f:
            sites_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return 0

    if not sites_data:
        return 0

    collection = get_sites_collection()
    migrated_count = 0

    for site in sites_data:
        # 检查是否已存在（通过域名判断）
        domain = site.get('domain') or extract_domain(site.get('url', ''))
        existing = collection.find_one({'domain': domain})
        if existing:
            continue

        # 准备文档
        doc = {
            'name': site.get('name', ''),
            'url': site.get('url', ''),
            'domain': domain,
            'country_code': site.get('country_code'),
            'coords': site.get('coords'),
            'sitemap_supported': site.get('sitemap_supported'),
            'sitemap_url': site.get('sitemap_url'),
            'fetch_method': site.get('fetch_method', 'unknown'),
            'status': site.get('status', 'active'),
        }

        # 处理日期字段
        for field in ['created_at', 'updated_at']:
            value = site.get(field)
            if value:
                if isinstance(value, str):
                    try:
                        doc[field] = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        doc[field] = datetime.now()
                elif isinstance(value, datetime):
                    doc[field] = value
            else:
                doc[field] = datetime.now()

        try:
            collection.insert_one(doc)
            migrated_count += 1
        except Exception as e:
            print(f"迁移站点失败: {domain}, 错误: {e}")

    # 迁移成功后，备份并清空 sites.json
    if migrated_count > 0:
        backup_file = SITES_FILE + '.bak'
        try:
            os.rename(SITES_FILE, backup_file)
            print(f"已将 sites.json 备份为 {backup_file}")
        except Exception:
            pass

    return migrated_count


def init_sites_from_news_sources() -> int:
    """
    从预设新闻源初始化站点（如果集合为空）
    返回：添加的站点数量
    """
    collection = get_sites_collection()

    # 如果已有数据则跳过
    if collection.count_documents({}) > 0:
        return 0

    # 创建索引
    collection.create_index('domain', unique=True)

    # 预设的网站列表
    preset_sites = [
        {'name': '美联社', 'url': 'https://apnews.com'},
        {'name': 'BBC', 'url': 'https://www.bbc.com'},
        {'name': '路透社', 'url': 'https://www.reuters.com'},
        {'name': 'NHK World', 'url': 'https://www3.nhk.or.jp/nhkworld/'},
        {'name': '日本共同社', 'url': 'https://www.kyodonews.jp'},
    ]

    count = 0
    for preset in preset_sites:
        try:
            add_site(preset['name'], preset['url'], auto_detect=False)
            count += 1
        except ValueError:
            pass  # 已存在

    return count


def ensure_indexes():
    """确保必要的索引存在"""
    collection = get_sites_collection()
    collection.create_index('domain', unique=True)
    collection.create_index('status')
    collection.create_index('created_at')
