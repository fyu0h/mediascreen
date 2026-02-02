# -*- coding: utf-8 -*-
"""
配置文件：MongoDB 和 Flask 相关配置

MongoDB 配置方式：
1. 本地 MongoDB：确保 mongod 正在运行（默认端口 27017）
2. MongoDB Atlas：设置环境变量 MONGO_URI 为完整连接字符串
   例如：set MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/news_dashboard
"""

import os


class Config:
    """应用配置类"""

    # Flask 配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # MongoDB 配置
    # 优先使用完整 URI（支持 MongoDB Atlas）
    MONGO_URI = os.environ.get('MONGO_URI', None)

    # 本地 MongoDB 配置（当 MONGO_URI 未设置时使用）
    MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
    MONGO_PORT = int(os.environ.get('MONGO_PORT', 27017))
    MONGO_DB = os.environ.get('MONGO_DB', 'news_dashboard')
    MONGO_USERNAME = os.environ.get('MONGO_USERNAME', None)
    MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD', None)

    # 集合名称
    COLLECTION_ARTICLES = 'news_articles'
    COLLECTION_SOURCES = 'news_sources'

    # 分页默认值
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # DeepSeek API 配置
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
    DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')

    @classmethod
    def get_mongo_uri(cls) -> str:
        """获取 MongoDB 连接 URI"""
        # 优先使用完整 URI
        if cls.MONGO_URI:
            return cls.MONGO_URI
        # 构建本地连接 URI
        if cls.MONGO_USERNAME and cls.MONGO_PASSWORD:
            return f"mongodb://{cls.MONGO_USERNAME}:{cls.MONGO_PASSWORD}@{cls.MONGO_HOST}:{cls.MONGO_PORT}/{cls.MONGO_DB}"
        return f"mongodb://{cls.MONGO_HOST}:{cls.MONGO_PORT}/{cls.MONGO_DB}"


# 新闻源元数据：名称 -> (国家代码, 坐标 [经度, 纬度])
# 坐标格式为 [经度, 纬度]，在前端展示时需要翻转为 [纬度, 经度]
NEWS_SOURCE_METADATA = {
    "美联社": ("US", [-77.0369, 38.9072]),            # 华盛顿特区
    "哈萨克斯坦通讯社": ("KZ", [71.4491, 51.1801]),   # 努尔苏丹
    "泰晤士报": ("GB", [-0.1276, 51.5074]),           # 伦敦
    "infobae": ("AR", [-58.3816, -34.6037]),          # 布宜诺斯艾利斯
    "巴基斯坦联合通讯社": ("PK", [73.0479, 33.6844]), # 伊斯兰堡
    "BBC": ("GB", [-0.1276, 51.5074]),                # 伦敦
    "中国国务院新闻": ("CN", [116.4074, 39.9042]),    # 北京
    "大公": ("HK", [114.1694, 22.3193]),              # 香港
    "耶路撒冷邮报": ("IL", [35.2137, 31.7683]),       # 耶路撒冷
    "土库曼情报局新闻": ("TM", [58.3833, 37.9601]),   # 阿什哈巴德
    "日本共同社": ("JP", [139.6917, 35.6895]),        # 东京
    "NHK World": ("JP", [139.6917, 35.6895]),         # 东京
    "参考消息": ("CN", [116.4074, 39.9042]),          # 北京
    "福克斯新闻(全量索引)": ("US", [-73.9857, 40.7484]),  # 纽约
    "美国福克斯新闻": ("US", [-73.9857, 40.7484]),    # 纽约（映射名称）
}

# 风控关键词配置
# 分类：高风险（红色告警）、中风险（橙色告警）、关注（黄色提示）
RISK_KEYWORDS = {
    "high": [
        "战争", "军事冲突", "核武器", "恐怖袭击", "暴乱", "政变",
        "制裁", "封锁", "断交", "入侵", "空袭", "导弹",
        "war", "military conflict", "nuclear", "terrorist", "invasion"
    ],
    "medium": [
        "抗议", "示威", "罢工", "冲突", "紧张", "威胁",
        "贸易战", "关税", "制裁", "争端", "对抗", "摩擦",
        "protest", "strike", "conflict", "tension", "sanction"
    ],
    "low": [
        "谈判", "会谈", "协议", "合作", "访问", "峰会",
        "选举", "投票", "改革", "政策", "声明", "表态",
        "negotiation", "agreement", "summit", "election", "policy"
    ]
}

# 风控刷新间隔（秒）
RISK_REFRESH_INTERVAL = 60
