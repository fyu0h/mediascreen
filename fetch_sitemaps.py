import json
import re
import sys
import io
import urllib.request
import urllib.error
import ssl
from urllib.parse import urlparse

# 修复Windows控制台编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 忽略SSL证书验证
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 读取sites.json
with open("sites.json", "r", encoding="utf-8") as f:
    sites = json.load(f)

# 提取根域名
def get_robots_url(site_url):
    parsed = urlparse(site_url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/plain,text/html,*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

results = []

for site in sites:
    name = site["name"]
    url = site["url"]
    robots_url = get_robots_url(url)
    entry = {
        "name": name,
        "site_url": url,
        "robots_url": robots_url,
        "status": "unknown",
        "sitemaps": [],
        "error": None,
    }

    print(f"[*] 正在抓取: {name} -> {robots_url}")

    try:
        req = urllib.request.Request(robots_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode("utf-8", errors="replace")

            # 检查是否返回了HTML而非纯文本(WAF拦截等)
            if "<html" in body.lower()[:500] and "robots" not in body.lower()[:200]:
                entry["status"] = "blocked_or_html"
                entry["error"] = "返回HTML而非robots.txt，可能被WAF拦截或不存在"
            else:
                entry["status"] = "success"
                # 提取Sitemap行
                for line in body.splitlines():
                    line = line.strip()
                    match = re.match(r"^[Ss]itemap:\s*(.+)$", line)
                    if match:
                        entry["sitemaps"].append(match.group(1).strip())

                if not entry["sitemaps"]:
                    entry["status"] = "success_no_sitemap"

    except urllib.error.HTTPError as e:
        entry["status"] = "http_error"
        entry["error"] = f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        entry["status"] = "url_error"
        entry["error"] = str(e.reason)
    except Exception as e:
        entry["status"] = "error"
        entry["error"] = str(e)

    if entry["sitemaps"]:
        print(f"    ✓ 找到 {len(entry['sitemaps'])} 个sitemap")
        for sm in entry["sitemaps"]:
            print(f"      - {sm}")
    elif entry["status"].startswith("success"):
        print(f"    ✗ robots.txt中未找到sitemap")
    else:
        print(f"    ✗ 失败: {entry['error']}")

    results.append(entry)

# 输出JSON
output_file = "sitemaps_result.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"结果已保存到 {output_file}")
print(f"总计: {len(results)} 个站点")
print(f"找到sitemap: {sum(1 for r in results if r['sitemaps'])} 个")
print(f"无sitemap: {sum(1 for r in results if r['status'] == 'success_no_sitemap')} 个")
print(f"失败: {sum(1 for r in results if 'error' in r['status'] or r['status'] == 'blocked_or_html')} 个")
