# 新闻预览系统问题研究与正反方辩论报告

> 日期：2026-03-01
> 环境：Oracle Cloud ARM64 (Ubuntu 20.04, 4核 Neoverse-N1, 24GB RAM)
> 问题：预览经常无法正常获取 + crawl4ai 在 ARM64 上无法工作

---

## 一、现状诊断

### 预览回退链架构（routes/api.py 第4032行）

```
请求到达
  │
  ├─ URL合法性校验 + SSRF防护 + Google News跳转解析
  │
  ├─▶ Level 1: requests.get (timeout=15s) + BeautifulSoup 正文提取
  │     ├─ 命中 Cloudflare 标记 → 跳过
  │     ├─ 质量检查通过（≥3文本块, ≥100字符）→ 返回 type='content'
  │     └─ 失败/质量不足 → 下沉
  │
  ├─▶ Level 2: crawl4ai 无头浏览器 (timeout=20s) + 正文提取
  │     ├─ ⚠️ 代理模式 → 跳过整个 Level 2
  │     ├─ ⚠️ ARM64 上 crawl4ai 不可用 → 跳过
  │     └─ 质量检查通过 → 返回 type='content'
  │
  ├─▶ Level 3: Playwright + stealth 全页截图 (timeout=25s+15s)
  │     ├─ ⚠️ 代理模式 → 跳过整个 Level 3
  │     ├─ ⚠️ ARM64 上 Playwright 不可用 → 跳过
  │     └─ 截图成功 → 返回 type='screenshot'
  │
  ├─▶ Level 4: MongoDB 缓存摘要查询
  │     ├─ 命中 → 返回 type='cached'（仅标题/来源/日期）
  │     └─ 未命中 → 502 错误
  │
  └─ 所有级别异常统一 → 502
```

### 四个致命瓶颈

| # | 瓶颈 | 影响 |
|---|------|------|
| 1 | **代理模式下回退链被"腰斩"** — `if not proxy_url:` 导致 Level 2/3 完全跳过 | 代理场景下4级回退退化为2级 |
| 2 | **crawl4ai 在 ARM64 上不可用** — Playwright 无 ARM64 Chromium 二进制 | Level 2 形同虚设 |
| 3 | **requests 层反爬能力极弱** — 固定 UA、无 Session 复用、无 HTTP/2、无 TLS 指纹伪装 | Cloudflare/Akamai 一眼识别 |
| 4 | **正文提取门槛偏高** — 至少3块100字，快讯类新闻被误杀 | 即使拿到 HTML 也可能判定为"质量不达标" |

---

## 二、正反方辩论全记录

### 第一轮交锋：ARM64 浏览器方案

#### 正方原始方案
> apt install chromium-browser + `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 指向系统 Chromium，零成本恢复 Level 2/3

#### 反方质疑
> **三重死路：**
> 1. Ubuntu 20.04 ARM64 的 `chromium-browser` 是 Snap 空壳包（deb 版停留在 Chrome 85，2020年）
> 2. Snap Chromium 在 ARM64 有已知启动失败（沙箱 + AppArmor 限制）
> 3. Playwright 与系统 Chromium 版本强绑定（CDP 协议版本匹配），随便指一个 Chromium 给 Playwright 用会协议握手失败

#### 技术验证事实（关键转折）
- **Playwright v1.40+（2023年11月）开始提供 ARM64 Chromium 实验性二进制**
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 是官方支持的机制
- crawl4ai GitHub issue #736/#801 确认 ARM64 问题，无官方解决方案
- firefox-esr 可通过 apt 安装，Playwright 支持 `executablePath` 指向

#### 正方修正立场
> 1. 放弃 apt install chromium-browser 路径
> 2. 直接使用 `playwright install chromium`（v1.40+ 自带 ARM64 二进制）
> 3. 备选：firefox-esr + executablePath
> 4. 放弃 Docker QEMU 模拟（认同反方 5-20x 性能损失判断）

#### 反方回应
> 1. Playwright ARM64 Chromium 标注"实验性"，需充分测试
> 2. 如果预算允许，**独立 x86 VPS（$3-5/月）做渲染代理最稳妥**
> 3. ARM64 上跑浏览器始终是在跟生态对抗

#### ✅ 达成共识
| 共识 | 态度 |
|------|------|
| 放弃 apt install chromium-browser | 完全一致 |
| 放弃 Docker QEMU 模拟 | 完全一致 |
| 首选：Playwright v1.40+ ARM64 Chromium（需部署前验证） | 正方主推，反方有条件接受 |
| 备选：firefox-esr + executablePath | 双方接受为 Plan B |
| 远期：x86 渲染代理 VPS | 反方主推，正方认可合理性 |
| crawl4ai 降级模式已存在，风险可控 | 完全一致 |

**结论：先试 Playwright ARM64 Chromium → 不行就 firefox-esr → 再不行就 x86 VPS。三级回退。**

---

### 第二轮交锋：HTTP 层反爬方案

#### 正方原始方案
> cloudscraper + httpx 组合使用，cloudscraper 专攻 Cloudflare，httpx 通用增强

#### 反方质疑
> 1. **cloudscraper 已过时** — 最后实质更新 2023 年初，对 Cloudflare Turnstile 和新版 JS Challenge 无效，GitHub Issues 充斥"不再工作"
> 2. **httpx HTTP/2 是幻觉** — 真正的 TLS 指纹检测（JA3/JA4）看的是 cipher suite 顺序、扩展列表，Python ssl 模块无论 requests 还是 httpx 都无法伪装
> 3. **推荐 curl_cffi** — 基于 curl-impersonate，可模拟真实浏览器 TLS 指纹，这才是反爬核心战场

#### 正方修正立场
> 1. 放弃 cloudscraper
> 2. 采纳 curl_cffi 作为反爬增强层
> 3. httpx 降为可选

#### ✅ 达成共识
| 共识 | 态度 |
|------|------|
| 放弃 cloudscraper | 完全一致 |
| 引入 curl_cffi 作为反爬增强 | 完全一致 |
| 三级分层：requests → curl_cffi → Playwright | 完全一致 |
| 大多数新闻站点不需要 TLS 指纹伪装 | 完全一致 |
| impersonate 参数写入 settings.json | 完全一致 |

**结论：requests 打底 → curl_cffi 对付反爬 → Playwright 处理 JS 渲染。站点级别可配置。**

---

### 第三轮交锋：正文提取优化

#### 正方原始方案
> 引入 trafilatura（F1=91.5%）替换自研 `_extract_content_blocks()`，降低质量门槛

#### 反方质疑
> 1. **方向错误** — 当前瓶颈不在"拿到 HTML 后提取不好"，而在"拿不到有效 HTML"
> 2. trafilatura/newspaper3k 底层也用 requests，对 Cloudflare 拦截、SPA 壳子、IP 封禁三种情况一个都解决不了
> 3. 降低质量门槛是**掩盖问题** — Cloudflare 挑战页的文字可能被当成"正文"返回

#### 正方修正立场
> 1. 承认 trafilatura 仅解决"提取不准"，不解决"拿不到 HTML"
> 2. trafilatura 作为 `_extract_content_blocks()` 的质量增强，不是回退链的新层级
> 3. **修复回退链截断 bug 才是更紧迫的问题**（正方认同反方核心论点）

#### ✅ 达成共识
| 共识 | 优先级 | 态度 |
|------|--------|------|
| 修复代理模式下回退链截断 bug | **P0 最高** | 完全一致 |
| 引入 trafilatura 作为首选提取器 | P1 | 完全一致 |
| 保留 BeautifulSoup 作为备选 | P1 | 完全一致 |
| 质量门槛可自适应降低，但前端必须标识内容完整度 | P2 | 完全一致 |
| 引入预览结果缓存 | P2 | 完全一致 |

**结论：先修 bug → 再升级工具 → 最后优化体验。**

---

### 第四轮交锋：架构改进

#### 正方方案
> HTTP 客户端抽象层 + 预览缓存（24h TTL）+ 站点健康度监控

#### 反方回应
> 1. HTTP 客户端抽象层：同意，但简单工厂函数即可，不要策略模式
> 2. 预览缓存 TTL 24h 太长，新闻类内容 6-12 小时更合适
> 3. 站点健康度监控：**强烈同意**，当前系统缺乏感知能力
> 4. Playwright ARM64 设 2 天验证期限，不通过立刻转 x86 VPS

#### ✅ 达成共识
| 共识 | 态度 |
|------|------|
| HTTP 客户端抽象层：工厂函数模式 | 完全一致 |
| 预览缓存 TTL 6-12 小时 | 完全一致 |
| 站点健康度监控与自动告警 | 完全一致 |
| Playwright ARM64 验证期限 2 天 | 双方接受 |

---

## 三、最终共识方案

### 第一阶段：修复与止血（1-2 天）

#### P0-1. 修复代理模式下预览回退链截断 bug

**这是零成本、最高收益的改进。**

- 文件：`routes/api.py` 中 `/api/news/preview` 端点
- 问题：`if not proxy_url:` 导致 Level 2/3 被完全跳过
- 修复思路：代理模式下用 curl_cffi/cloudscraper 替代 Playwright 完成 Level 2 的 JS 渲染获取；Level 3 截图需要浏览器方案确定后再修
- 验证：开启代理后测试多个站点，确认每级回退正常触发

#### P0-2. Playwright ARM64 Chromium 可行性验证

```bash
# 在 Oracle ARM64 服务器上执行
pip install playwright>=1.40
playwright install chromium

# 验证 Chromium 能否启动
python -c "
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
b = p.chromium.launch()
print('Chromium ARM64 启动成功')
b.close()
p.stop()
"
```

- 成功 → 配置 crawl4ai 或直接通过 Playwright API 使用
- 失败 → 进入 Plan B（firefox-esr）或 Plan C（x86 VPS）
- **验证期限：2 天**

### 第二阶段：HTTP 层强化（2-3 天）

#### P1-1. 引入 curl_cffi

```bash
pip install curl_cffi
```

封装 HTTP 客户端工厂函数：

```python
# plugins/http_client.py
def create_client(client_type: str = "requests", **kwargs):
    """
    工厂函数：根据站点配置返回对应的 HTTP 客户端
    client_type: "requests" | "curl_cffi" | "httpx"
    """
    if client_type == "curl_cffi":
        from curl_cffi import requests as curl_requests
        impersonate = kwargs.get("impersonate", "chrome120")
        session = curl_requests.Session(impersonate=impersonate)
        return session
    elif client_type == "httpx":
        import httpx
        return httpx.Client(http2=True, follow_redirects=True)
    else:
        import requests
        return requests.Session()
```

- settings.json 增加 curl_cffi 的 impersonate 参数
- 站点配置中增加 `http_client` 字段

#### P1-2. 引入 trafilatura

```bash
pip install trafilatura
```

```python
import trafilatura

def extract_with_trafilatura(html: str, url: str):
    """trafilatura 首选提取，失败回退 BeautifulSoup"""
    try:
        result = trafilatura.extract(
            html, url=url,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
            deduplicate=True,
        )
        if result and len(result) >= 50:
            blocks = [{'type': 'paragraph', 'text': p.strip()}
                      for p in result.split('\n\n') if p.strip()]
            return blocks
    except Exception:
        pass
    return None  # 回退到现有 _extract_content_blocks()
```

### 第三阶段：体验优化（3-5 天）

#### P2-1. 预览结果缓存

MongoDB 新集合 `preview_cache`，TTL 8 小时：

```python
db.preview_cache.create_index("cached_at", expireAfterSeconds=28800)

# 缓存结构
{
    "url": "https://...",
    "content": [...],
    "quality": "full|partial|cached",
    "cached_at": datetime.utcnow()
}
```

#### P2-2. 低质量内容标识

- 后端返回 `quality` 字段
- 前端根据 quality 展示提示：
  - `full` → 无提示
  - `partial` → "内容可能不完整"
  - `cached` → "仅显示摘要信息"

#### P2-3. 站点健康度监控

- 记录每个站点最近 N 次抓取成功/失败
- 连续失败超阈值自动告警
- 仪表盘展示健康度状态（绿/黄/红）

### 第四阶段：远期演进（按需）

#### P3-1. x86 渲染代理（仅 Playwright ARM64 验证失败时启动）

- 租用廉价 x86 VPS（Vultr/Hetzner，$3-5/月）
- 部署轻量渲染服务（Playwright + FastAPI）
- ARM64 主服务器通过 HTTP API 调用

#### P3-2. 持续维护

- curl_cffi 的 impersonate 参数半年更新一次
- 跟踪 Playwright ARM64 从"实验性"到"正式支持"

---

## 四、技术选型总结

| 领域 | ✅ 选定方案 | ❌ 淘汰方案 | 理由 |
|------|-----------|------------|------|
| 浏览器引擎 | Playwright ARM64 Chromium (v1.40+) | apt chromium-browser | Snap 空壳 + 版本绑定 |
| 浏览器备选 | firefox-esr + executablePath | Docker QEMU | QEMU 性能损失 5-20x |
| 浏览器终极 | x86 VPS 渲染代理 | — | Plan C |
| HTTP 反爬 | curl_cffi | cloudscraper | cloudscraper 已过时 |
| HTTP 通用 | requests（保持不变） | — | 大部分站点不需要反爬 |
| HTTP/2 | httpx（可选） | — | 仅特定站点 |
| 正文提取 | trafilatura + BeautifulSoup | 纯自研 | trafilatura 更健壮 |
| 缓存 | MongoDB TTL 集合 | — | 与现有技术栈一致 |

---

## 五、双方共同声明

> 本方案的核心原则是**分层回退、渐进增强**：每一层都有明确的回退路径，不存在单点依赖。
>
> **最紧迫的工作不是引入新技术，而是修复现有回退链的截断 bug** — 这是零成本、最高收益的改进。
>
> 新技术的引入（curl_cffi、trafilatura、Playwright ARM64）遵循"先验证、再集成"的原则，在 ARM64 环境下逐一确认可用后再纳入生产。
>
> 对于真正需要 JS 渲染的站点，如果 ARM64 浏览器方案全部失败，应果断转向 x86 VPS 渲染代理方案，不在 ARM64 浏览器生态上继续消耗时间。
