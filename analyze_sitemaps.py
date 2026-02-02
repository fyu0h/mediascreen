import json
import sys
import io
import re
import urllib.request
import urllib.error
import ssl
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/xml,application/xml,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
    "image": "http://www.google.com/schemas/sitemap-image/1.1",
    "video": "http://www.google.com/schemas/sitemap-video/1.1",
}


def fetch_and_analyze(url):
    """抓取一个sitemap URL并分析其结构"""
    result = {
        "url": url,
        "status": "unknown",
        "type": None,          # "sitemapindex" or "urlset"
        "count": 0,            # 子sitemap数量或URL数量
        "has_lastmod": False,
        "has_news_tags": False,
        "has_image_tags": False,
        "has_video_tags": False,
        "sample_urls": [],     # 前3个URL示例
        "sub_sitemaps": [],    # 如果是index，列出子sitemap
        "error": None,
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            body = resp.read()

        # 尝试解析XML
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            # 可能是HTML或无效XML
            text = body.decode('utf-8', errors='replace')[:500]
            if '<html' in text.lower():
                result["status"] = "html_not_xml"
                result["error"] = "返回HTML而非XML"
            else:
                result["status"] = "parse_error"
                result["error"] = "XML解析失败"
            return result

        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        if tag == "sitemapindex":
            result["type"] = "sitemapindex"
            result["status"] = "success"
            sitemaps = root.findall("sm:sitemap", NS)
            result["count"] = len(sitemaps)
            for sm in sitemaps[:10]:  # 最多记录10个子sitemap
                loc = sm.find("sm:loc", NS)
                lastmod = sm.find("sm:lastmod", NS)
                entry = {"loc": loc.text.strip() if loc is not None else None}
                if lastmod is not None:
                    entry["lastmod"] = lastmod.text.strip()
                    result["has_lastmod"] = True
                result["sub_sitemaps"].append(entry)

        elif tag == "urlset":
            result["type"] = "urlset"
            result["status"] = "success"
            urls = root.findall("sm:url", NS)
            result["count"] = len(urls)

            # 检查特殊标签
            for u in urls[:20]:
                if u.find("sm:lastmod", NS) is not None:
                    result["has_lastmod"] = True
                if u.find("news:news", NS) is not None:
                    result["has_news_tags"] = True
                if u.find("image:image", NS) is not None:
                    result["has_image_tags"] = True
                if u.find("video:video", NS) is not None:
                    result["has_video_tags"] = True

            # 取样
            for u in urls[:3]:
                loc = u.find("sm:loc", NS)
                if loc is not None:
                    result["sample_urls"].append(loc.text.strip())
        else:
            result["status"] = "unknown_root"
            result["error"] = f"未知根元素: {tag}"

    except urllib.error.HTTPError as e:
        result["status"] = "http_error"
        result["error"] = f"HTTP {e.code}"
    except urllib.error.URLError as e:
        result["status"] = "url_error"
        result["error"] = str(e.reason)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


# 读取之前的结果
with open("sitemaps_result.json", "r", encoding="utf-8") as f:
    sites = json.load(f)

# 只处理有sitemap的站点
sites_with_sitemaps = [s for s in sites if s["sitemaps"]]

print(f"共 {len(sites_with_sitemaps)} 个站点有 sitemap，开始分析结构...\n")

all_results = []

for site in sites_with_sitemaps:
    name = site["name"]
    print(f"{'='*60}")
    print(f"[{name}]")

    site_result = {
        "name": name,
        "site_url": site["site_url"],
        "sitemap_analysis": [],
    }

    # 并发抓取该站点的所有sitemap入口
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(fetch_and_analyze, url): url for url in site["sitemaps"]}
        for future in as_completed(future_map):
            url = future_map[future]
            res = future.result()
            site_result["sitemap_analysis"].append(res)

            short_url = url.split("//", 1)[-1]
            if res["status"] == "success":
                if res["type"] == "sitemapindex":
                    print(f"  [INDEX] {short_url} -> {res['count']} 个子sitemap")
                    if res["has_lastmod"]:
                        latest = next((s.get("lastmod") for s in res["sub_sitemaps"] if s.get("lastmod")), None)
                        if latest:
                            print(f"          最新: {latest}")
                    for s in res["sub_sitemaps"][:3]:
                        print(f"          - {s['loc']}")
                    if res["count"] > 3:
                        print(f"          ... 共 {res['count']} 个")
                else:
                    extras = []
                    if res["has_news_tags"]:
                        extras.append("news")
                    if res["has_image_tags"]:
                        extras.append("image")
                    if res["has_video_tags"]:
                        extras.append("video")
                    if res["has_lastmod"]:
                        extras.append("lastmod")
                    tag_str = f" [{', '.join(extras)}]" if extras else ""
                    print(f"  [URLSET] {short_url} -> {res['count']} 个URL{tag_str}")
                    for s in res["sample_urls"][:2]:
                        print(f"           - {s}")
            else:
                print(f"  [FAIL] {short_url} -> {res['error']}")

    all_results.append(site_result)

# 保存详细结果
output_file = "sitemap_structure.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"结构分析结果已保存到 {output_file}")
