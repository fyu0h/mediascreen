# -*- coding: utf-8 -*-
"""
数据导入脚本：将 news_urls.json 导入 MongoDB
运行方式：python import_to_mongo.py
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from dateutil import parser as date_parser

from config import Config, NEWS_SOURCE_METADATA


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    解析日期字符串为 datetime 对象
    支持 ISO 8601 格式（带时区）
    """
    if not date_str:
        return None
    try:
        return date_parser.parse(date_str)
    except (ValueError, TypeError):
        return None


def get_source_metadata(source_name: str) -> tuple:
    """
    获取新闻源的元数据（国家代码和坐标）
    处理特殊映射：如 "福克斯新闻(全量索引)" -> "美国福克斯新闻"
    """
    # 特殊名称映射
    name_mapping = {
        "福克斯新闻(全量索引)": "美国福克斯新闻"
    }
    display_name = name_mapping.get(source_name, source_name)

    if source_name in NEWS_SOURCE_METADATA:
        return NEWS_SOURCE_METADATA[source_name]
    if display_name in NEWS_SOURCE_METADATA:
        return NEWS_SOURCE_METADATA[display_name]

    # 默认返回空
    return (None, None)


def import_data(json_file: str = 'news_urls.json') -> Dict[str, int]:
    """
    执行数据导入
    返回导入统计信息
    """
    print(f"[INFO] 开始导入数据...")
    print(f"[INFO] 连接 MongoDB: {Config.MONGO_HOST}:{Config.MONGO_PORT}/{Config.MONGO_DB}")

    # 连接数据库
    client = MongoClient(Config.get_mongo_uri())
    db = client[Config.MONGO_DB]
    articles_collection = db[Config.COLLECTION_ARTICLES]
    sources_collection = db[Config.COLLECTION_SOURCES]

    # 读取 JSON 文件
    print(f"[INFO] 读取文件: {json_file}")
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[INFO] 发现 {len(data)} 个新闻源")

    # 统计信息
    stats = {
        'sources_imported': 0,
        'articles_imported': 0,
        'articles_skipped': 0,
        'articles_with_date': 0,
        'articles_without_date': 0
    }

    # 清空现有数据（可选，首次导入时使用）
    print("[INFO] 清空现有数据...")
    articles_collection.delete_many({})
    sources_collection.delete_many({})

    # 创建索引
    print("[INFO] 创建索引...")
    # 文章集合索引
    articles_collection.create_index('loc', unique=True)
    articles_collection.create_index('source_name')
    articles_collection.create_index([('pub_date', DESCENDING)])
    articles_collection.create_index('country_code')
    articles_collection.create_index([('source_name', ASCENDING), ('pub_date', DESCENDING)])
    # 新闻源集合索引
    sources_collection.create_index('name', unique=True)

    # 当前导入时间
    imported_at = datetime.now()

    # 遍历每个新闻源
    for source_data in data:
        source_name = source_data.get('name', '')
        urls = source_data.get('urls', [])

        if not source_name:
            continue

        # 获取源元数据
        country_code, coords = get_source_metadata(source_name)

        # 插入新闻源文档
        source_doc = {
            'name': source_name,
            'url': urls[0].get('loc', '') if urls else '',
            'country_code': country_code,
            'coords': coords
        }
        try:
            sources_collection.insert_one(source_doc)
            stats['sources_imported'] += 1
            print(f"[INFO] 导入新闻源: {source_name} ({len(urls)} 条URL)")
        except DuplicateKeyError:
            print(f"[WARN] 新闻源已存在: {source_name}")

        # 批量插入文章
        articles_batch: List[Dict[str, Any]] = []
        batch_size = 1000

        for url_data in urls:
            loc = url_data.get('loc', '')
            if not loc:
                stats['articles_skipped'] += 1
                continue

            # 解析日期
            pub_date = parse_date(url_data.get('pub_date'))
            lastmod = parse_date(url_data.get('lastmod'))

            if pub_date:
                stats['articles_with_date'] += 1
            else:
                stats['articles_without_date'] += 1

            article_doc = {
                'loc': loc,
                'title': url_data.get('title', ''),
                'source_name': source_name,
                'publisher': url_data.get('publisher', ''),
                'country_code': country_code,
                'coords': coords,
                'pub_date': pub_date,
                'lastmod': lastmod,
                'imported_at': imported_at
            }
            articles_batch.append(article_doc)

            # 批量插入
            if len(articles_batch) >= batch_size:
                try:
                    result = articles_collection.insert_many(articles_batch, ordered=False)
                    stats['articles_imported'] += len(result.inserted_ids)
                except Exception as e:
                    # 处理重复键错误，继续导入其他文档
                    if 'duplicate key error' in str(e).lower():
                        # 计算实际插入数量
                        stats['articles_imported'] += len(articles_batch) - str(e).count('duplicate key error')
                    else:
                        print(f"[ERROR] 批量插入错误: {e}")
                articles_batch = []

        # 插入剩余文章
        if articles_batch:
            try:
                result = articles_collection.insert_many(articles_batch, ordered=False)
                stats['articles_imported'] += len(result.inserted_ids)
            except Exception as e:
                if 'duplicate key error' not in str(e).lower():
                    print(f"[ERROR] 批量插入错误: {e}")

    # 关闭连接
    client.close()

    # 打印统计信息
    print("\n" + "=" * 50)
    print("导入完成！统计信息：")
    print("=" * 50)
    print(f"  新闻源数量: {stats['sources_imported']}")
    print(f"  文章总数: {stats['articles_imported']}")
    print(f"  有发布日期: {stats['articles_with_date']}")
    print(f"  无发布日期: {stats['articles_without_date']}")
    print(f"  跳过（无URL）: {stats['articles_skipped']}")
    print("=" * 50)

    return stats


if __name__ == '__main__':
    # 支持命令行参数指定 JSON 文件路径
    json_file = sys.argv[1] if len(sys.argv) > 1 else 'news_urls.json'
    import_data(json_file)
