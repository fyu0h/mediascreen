# 代理 IP 集成设计方案

日期：2026-03-01

## 背景

部分海外新闻源（如 Fox News、The Times 等）对来自中国大陆的直连请求存在限制或封禁风险。通过 GeoNode 住宅代理（Residential Proxy）转发请求可规避此问题。为节省代理流量，需要按站点粒度控制哪些站点走代理。

## 代理服务

- 提供商：GeoNode（app.geonode.com）
- 类型：住宅代理（Residential）
- 入口：`us.proxy.geonode.io:9000`
- 认证：用户名 + 密码
- 特性：同一入口，服务端自动轮换出口 IP，客户端无需管理 IP 池

## 设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 代理入口数量 | 单入口 | GeoNode 服务端自动轮换 IP，无需客户端维护多入口 |
| 开关粒度 | 站点级别 | 最灵活，按需为特定站点开启代理，节省流量 |
| 全局配置存储 | settings.json | 复用现有运行时配置机制 |
| 站点开关存储 | MongoDB plugin_subscriptions | 复用已有的 per-site 配置机制 |
| 前端入口 | 系统设置页 + 插件管理页 | 代理地址在设置页配，站点开关在插件管理页操作 |

## 配置结构

### settings.json 新增 `crawler.proxy` 节

```json
{
  "crawler": {
    "proxy": {
      "enabled": false,
      "host": "",
      "port": 9000,
      "username": "",
      "password": "",
      "protocol": "http"
    }
  }
}
```

- `enabled`：全局总开关，关闭后所有站点直连
- `protocol`：支持 `http` / `https` / `socks5`

### MongoDB `plugin_subscriptions` 新增字段

```json
{
  "plugin_id": "international_media",
  "site_id": "us_foxnews",
  "enabled": true,
  "use_proxy": false
}
```

`use_proxy` 默认 `false`，需手动为特定站点开启。

## 代理生效逻辑

```
爬取站点时：
  1. 读取 settings.json → crawler.proxy.enabled
  2. 查询 plugin_subscriptions → 该站点的 use_proxy
  3. 两者均为 true → 构造代理 URL 注入请求
  4. 否则 → 直连
```

代理 URL 构造：
```
{protocol}://{username}:{password}@{host}:{port}
```

## 后端改动

| 文件 | 改动内容 |
|---|---|
| `models/settings.py` | `DEFAULT_SETTINGS['crawler']` 增加 `proxy` 默认值 |
| `plugins/crawler.py` | `fetch_page()` — 向 `BrowserConfig` 传入 `proxy` 参数 |
| `plugins/crawler.py` | `fetch_url_simple()` — 向 `requests.get` 传入 `proxies=` 参数 |
| `plugins/crawler.py` | 新增 `_get_proxy_url(site)` 辅助函数，封装代理判断和 URL 构造 |
| `models/plugins.py` | 站点订阅读写支持 `use_proxy` 字段 |
| `routes/api.py` | 设置端点处理代理配置读写（密码遮蔽）|
| `routes/api.py` | 插件端点支持 `use_proxy` 开关切换 |
| `routes/api.py` | 新增代理连接测试端点 `POST /api/settings/test-proxy` |

## 前端改动

| 位置 | 内容 |
|---|---|
| 系统设置页 | 新增「代理设置」卡片：全局开关、协议选择、主机、端口、用户名、密码输入框、连接测试按钮 |
| 插件管理页 | 每个站点行新增代理开关图标（类似已有的启用/禁用开关样式）|

## 代理注入方式

### crawl4ai 浏览器爬取

```python
proxy_url = f"{protocol}://{username}:{password}@{host}:{port}"
self.browser_config = BrowserConfig(
    headless=True,
    verbose=False,
    proxy=proxy_url
)
```

### requests 简单 HTTP

```python
proxies = {
    "http": proxy_url,
    "https": proxy_url
}
requests.get(url, headers=headers, timeout=timeout, proxies=proxies)
```

## 安全考虑

- 代理密码在 API 响应中使用 `mask_api_key()` 遮蔽，与现有 API Key 处理一致
- 代理连接测试端点需要登录认证
