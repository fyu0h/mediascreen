"""
从sitemap递归抓取新闻URL
策略：
- news类urlset: 直接提取
- sitemapindex: 递归抓取子sitemap（限制最新N个）
- 跳过失败站点（RFI、财联社）
"""
import json
import sys
import io
import time
import urllib.request
import urllib.error
import ssl
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/xml,application/xml,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
    "image": "http://www.google.com/schemas/sitemap-image/1.1",
}

# 抓取计划：每个站点选择最有价值的sitemap入口
# max_sub: 对index类型最多递归多少个子sitemap
CRAWL_PLAN = [
    {
        "name": "美联社",
        "sitemaps": [
            "https://apnews.com/news-sitemap-content.xml",
        ],
        "max_sub": 5,
    },
    {
        "name": "美国福克斯新闻",
        "sitemaps": [
            "https://www.foxnews.com/sitemap.xml?type=news",
        ],
        "max_sub": 5,
    },
    {
        "name": "泰晤士报",
        "sitemaps": [
            "https://www.thetimes.com/sitemaps/news",
        ],
        "max_sub": 5,
    },
    {
        "name": "infobae",
        "sitemaps": [
            "https://www.infobae.com/arc/outboundfeeds/news-sitemap2/",
            "https://www.infobae.com/arc/outboundfeeds/news-sitemap2/category/america/",
        ],
        "max_sub": 5,
    },
    {
        "name": "哈萨克斯坦国际通讯社",
        "sitemaps": [
            "https://cn.inform.kz/sitemaps/google-news_cn.xml",
            "https://cn.inform.kz/sitemaps/sitemap-last-news-300_cn.xml",
        ],
        "max_sub": 5,
    },
    {
        "name": "BBC",
        "sitemaps": [
            "https://www.bbc.com/sitemaps/https-index-com-news.xml",  # index -> 4 sub
            "https://www.bbc.com/zhongwen/simp/sitemap.xml",
        ],
        "max_sub": 4,
    },
    {
        "name": "美国国务院新闻",
        "sitemaps": [
            "https://www.state.gov/sitemap_index.xml",
        ],
        "max_sub": 3,  # 只取前3个子sitemap
    },
    {
        "name": "明报",
        "sitemaps": [
            "https://news.mingpao.com/sitemap/ins.xml",
        ],
        "max_sub": 3,  # 最近3天
    },
    {
        "name": "首尔经济日报",
        "sitemaps": [
            "https://money.udn.com/sitemap/gnews/1001",
        ],
        "max_sub": 3,
    },
    {
        "name": "乌克兰情报官网",
        "sitemaps": [
            "https://lb.ua/sitemap.xml",
        ],
        "max_sub": 2,
    },
    {
        "name": "日本放送协会",
        "sitemaps": [
            "https://news.web.nhk/sitemap.xml",
        ],
        "max_sub": 3,
    },
    {
        "name": "NHK World",
        "sitemaps": [
            "https://www3.nhk.or.jp/nhkworld/sitemap.xml",
        ],
        "max_sub": 3,
    },
    {
        "name": "南华早报",
        "sitemaps": [
            "https://www.scmp.com/sitemap/archives-0.xml",
        ],
        "max_sub": 2,  # 只取最近2个月
    },
    {
        "name": "福克斯新闻(全量索引)",
        "sitemaps": [
            "https://www.foxnews.com/sitemap.xml",
        ],
        "max_sub": 3,
    },
]


def fetch_xml(url, retries=2):
    """抓取并解析XML，返回 ElementTree root 或 None"""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                body = resp.read()
            root = ET.fromstring(body)
            return root
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                return None


def extract_urls_from_urlset(root):
    """从urlset中提取所有URL信息"""
    urls = []
    for u in root.findall("sm:url", NS):
        loc_el = u.find("sm:loc", NS)
        if loc_el is None:
            continue
        entry = {"loc": loc_el.text.strip()}

        lastmod_el = u.find("sm:lastmod", NS)
        if lastmod_el is not None and lastmod_el.text:
            entry["lastmod"] = lastmod_el.text.strip()

        # Google News 扩展
        news_el = u.find("news:news", NS)
        if news_el is not None:
            title_el = news_el.find("news:title", NS)
            pub_date_el = news_el.find("news:publication_date", NS)
            pub_el = news_el.find("news:publication", NS)
            if title_el is not None and title_el.text:
                entry["title"] = title_el.text.strip()
            if pub_date_el is not None and pub_date_el.text:
                entry["pub_date"] = pub_date_el.text.strip()
            if pub_el is not None:
                name_el = pub_el.find("news:name", NS)
                if name_el is not None and name_el.text:
                    entry["publisher"] = name_el.text.strip()

        urls.append(entry)
    return urls


def crawl_sitemap(url, max_sub=5, depth=0, max_depth=2):
    """递归抓取sitemap，返回URL列表"""
    if depth > max_depth:
        return []

    root = fetch_xml(url)
    if root is None:
        print(f"    {'  '*depth}[FAIL] {url}")
        return []

    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    if tag == "urlset":
        urls = extract_urls_from_urlset(root)
        print(f"    {'  '*depth}[URLSET] {url} -> {len(urls)} URLs")
        return urls

    elif tag == "sitemapindex":
        sitemaps = root.findall("sm:sitemap", NS)
        print(f"    {'  '*depth}[INDEX] {url} -> {len(sitemaps)} 子sitemaps (取前{max_sub}个)")
        all_urls = []

        # 只取前 max_sub 个
        sub_urls = []
        for sm in sitemaps[:max_sub]:
            loc_el = sm.find("sm:loc", NS)
            if loc_el is not None:
                sub_urls.append(loc_el.text.strip())

        # 并发抓取子sitemap
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(crawl_sitemap, su, max_sub, depth + 1, max_depth): su
                for su in sub_urls
            }
            for future in as_completed(futures):
                result = future.result()
                all_urls.extend(result)

        return all_urls
    else:
        print(f"    {'  '*depth}[UNKNOWN] {url} -> 根元素: {tag}")
        return []


# ========== 主流程 ==========
print("开始递归抓取新闻URL...\n")

all_results = []

for plan in CRAWL_PLAN:
    name = plan["name"]
    max_sub = plan["max_sub"]
    print(f"{'='*60}")
    print(f"[{name}]")

    site_urls = []
    for sm_url in plan["sitemaps"]:
        urls = crawl_sitemap(sm_url, max_sub=max_sub)
        site_urls.extend(urls)

    # 去重（按loc）
    seen = set()
    unique_urls = []
    for u in site_urls:
        if u["loc"] not in seen:
            seen.add(u["loc"])
            unique_urls.append(u)

    print(f"  => 共获取 {len(unique_urls)} 个唯一URL\n")

    all_results.append({
        "name": name,
        "url_count": len(unique_urls),
        "urls": unique_urls,
    })

# 保存结果
output_file = "news_urls.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

total = sum(r["url_count"] for r in all_results)
print(f"{'='*60}")
print(f"抓取完成！总计 {total} 个新闻URL")
print(f"结果已保存到 {output_file}")
print()
for r in all_results:
    print(f"  {r['name']}: {r['url_count']} URLs")
