# 代理 IP 集成实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为爬虫系统集成 GeoNode 住宅代理，支持全局代理配置和站点级别代理开关，防止被新闻站点封禁。

**Architecture:** 代理地址/密码存储在 settings.json 的 `crawler.proxy` 节，站点级 `use_proxy` 开关存储在 MongoDB `plugin_subscriptions` 集合。爬虫引擎（crawl4ai + requests）在发起请求前检查全局开关和站点开关，两者均开启时注入代理。

**Tech Stack:** Python Flask / MongoDB / crawl4ai / requests / 原生 JS 前端

---

### Task 1: 后端 — settings.py 添加代理默认配置

**Files:**
- Modify: `models/settings.py:16-68` (DEFAULT_SETTINGS 的 crawler 节)

**Step 1: 在 DEFAULT_SETTINGS['crawler'] 中添加 proxy 默认值**

在 `models/settings.py` 第 63 行 `'auto_crawl_interval': 30` 之后添加 proxy 子节：

```python
'crawler': {
    'timeout': 30,
    'max_articles': 500,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'auto_crawl_enabled': False,
    'auto_crawl_interval': 30,
    'proxy': {
        'enabled': False,
        'host': '',
        'port': 9000,
        'username': '',
        'password': '',
        'protocol': 'http'
    }
},
```

**Step 2: 提交**

```bash
git add models/settings.py
git commit -m "feat: settings.py 添加代理默认配置"
```

---

### Task 2: 后端 — crawler.py 代理注入

**Files:**
- Modify: `plugins/crawler.py:51-54` (BrowserConfig 初始化)
- Modify: `plugins/crawler.py:79-129` (fetch_page 方法)
- Modify: `plugins/crawler.py:131-140` (fetch_url_simple 方法)
- Modify: `plugins/crawler.py:218-287` (crawl_site_async 方法)

**Step 1: 添加代理辅助方法到 PluginCrawler 类**

在 `PluginCrawler` 类中（`__init__` 之后，`fetch_page` 之前）添加：

```python
def _build_proxy_url(self) -> str:
    """根据 settings.json 构造代理 URL，配置不完整返回空串"""
    from models.settings import load_settings
    settings = load_settings()
    proxy_cfg = settings.get('crawler', {}).get('proxy', {})

    if not proxy_cfg.get('enabled'):
        return ''

    host = proxy_cfg.get('host', '')
    port = proxy_cfg.get('port', 9000)
    username = proxy_cfg.get('username', '')
    password = proxy_cfg.get('password', '')
    protocol = proxy_cfg.get('protocol', 'http')

    if not host:
        return ''

    if username and password:
        return f"{protocol}://{username}:{password}@{host}:{port}"
    return f"{protocol}://{host}:{port}"

def _should_use_proxy(self, site: dict) -> bool:
    """判断该站点是否应使用代理（全局开关 + 站点开关均为 True）"""
    from models.settings import load_settings
    settings = load_settings()
    proxy_cfg = settings.get('crawler', {}).get('proxy', {})

    if not proxy_cfg.get('enabled'):
        return False

    # 查询站点级别的 use_proxy 开关
    from models.plugins import get_subscription
    plugin_id = site.get('plugin_id', '')
    site_id = site.get('id', '')
    if plugin_id and site_id:
        sub = get_subscription(plugin_id, site_id)
        if sub and sub.get('use_proxy'):
            return True
    return False
```

**Step 2: 修改 fetch_page 方法，接收可选 proxy_url 参数**

原代码（第 79 行）：
```python
async def fetch_page(self, url: str, timeout: int = None) -> str:
```

改为：
```python
async def fetch_page(self, url: str, timeout: int = None, proxy_url: str = '') -> str:
```

在 `fetch_page` 方法的重试循环内，创建 `AsyncWebCrawler` 之前，根据 proxy_url 动态构造 browser_config：

```python
# 在 for attempt in range(self.MAX_RETRIES + 1): 循环内、try 块开头
if proxy_url:
    browser_cfg = BrowserConfig(headless=True, verbose=False, proxy=proxy_url)
else:
    browser_cfg = self.browser_config

config = CrawlerRunConfig(
    wait_until="domcontentloaded",
    page_timeout=timeout_ms,
    cache_mode=CacheMode.BYPASS
)
async with AsyncWebCrawler(config=browser_cfg) as crawler:
    result = await crawler.arun(url, config=config)
```

**Step 3: 修改 fetch_url_simple，接收可选 proxy_url 参数**

原代码（第 131 行）：
```python
def fetch_url_simple(self, url: str, timeout: int = 30) -> str:
```

改为：
```python
def fetch_url_simple(self, url: str, timeout: int = 30, proxy_url: str = '') -> str:
```

在 `requests.get` 调用中注入代理：

```python
proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, proxies=proxies)
```

**Step 4: 修改 crawl_site_async，在爬取前判断代理**

在 `crawl_site_async` 方法（第 218 行）中，`html = await self.fetch_page(url)` 调用之前，添加代理判断：

```python
# 判断是否使用代理
proxy_url = ''
if self._should_use_proxy(site):
    proxy_url = self._build_proxy_url()
    if proxy_url:
        print(f"[PluginCrawler] 🔒 {name} 使用代理: {site.get('domain', '')}")

# 获取页面（传入代理参数）
html = await self.fetch_page(url, proxy_url=proxy_url)
```

**Step 5: 提交**

```bash
git add plugins/crawler.py
git commit -m "feat: crawler.py 支持代理注入（crawl4ai + requests）"
```

---

### Task 3: 后端 — plugins.py 支持 use_proxy 字段

**Files:**
- Modify: `models/plugins.py:39-77` (set_subscription 函数)
- Modify: `models/plugins.py:263-315` (get_plugins_with_status 函数)

**Step 1: set_subscription 函数增加 use_proxy 参数**

原函数签名（第 39 行）：
```python
def set_subscription(plugin_id: str, site_id: str, enabled: bool,
                     fetch_method_override: Optional[str] = None,
                     auto_update: bool = False,
                     update_interval: int = 300) -> Dict[str, Any]:
```

改为：
```python
def set_subscription(plugin_id: str, site_id: str, enabled: bool,
                     fetch_method_override: Optional[str] = None,
                     auto_update: bool = False,
                     update_interval: int = 300,
                     use_proxy: bool = None) -> Dict[str, Any]:
```

在 doc 字典构造中添加 `use_proxy` 字段（仅当显式传入时才写入）：

```python
doc = {
    "plugin_id": plugin_id,
    "site_id": site_id,
    "enabled": enabled,
    "fetch_method_override": fetch_method_override,
    "auto_update": auto_update,
    "update_interval": update_interval,
    "updated_at": now
}
if use_proxy is not None:
    doc["use_proxy"] = use_proxy
```

**Step 2: get_plugins_with_status 函数返回 use_proxy 状态**

在 `get_plugins_with_status` 函数中，构建站点信息的位置（约第 290-300 行），添加 `use_proxy` 字段到返回的站点字典中：

```python
# 在 site_info 字典中添加（与 auto_update、update_interval 同级）
'use_proxy': sub.get('use_proxy', False) if sub else False,
```

**Step 3: 添加 set_use_proxy 独立更新函数**

在 `models/plugins.py` 中添加：

```python
def set_use_proxy(plugin_id: str, site_id: str, use_proxy: bool) -> Optional[Dict[str, Any]]:
    """设置站点是否使用代理"""
    collection = get_subscriptions_collection()
    result = collection.find_one_and_update(
        {"plugin_id": plugin_id, "site_id": site_id},
        {"$set": {"use_proxy": use_proxy, "updated_at": datetime.now()}},
        return_document=True
    )
    return result
```

**Step 4: 提交**

```bash
git add models/plugins.py
git commit -m "feat: plugins.py 支持站点级 use_proxy 字段"
```

---

### Task 4: 后端 — api.py 代理设置端点

**Files:**
- Modify: `routes/api.py:910-957` (GET /api/settings)
- Modify: `routes/api.py:960-1032` (PUT /api/settings)
- Add endpoint: POST /api/settings/test-proxy
- Add endpoint: PUT /api/plugins/<plugin_id>/sites/<site_id>/proxy

**Step 1: GET /api/settings 端点遮蔽代理密码**

在 `get_settings()` 函数中（约第 955 行，`return success_response(settings)` 之前），添加代理密码遮蔽：

```python
# 遮蔽代理密码
proxy_cfg = settings.get('crawler', {}).get('proxy', {})
if proxy_cfg.get('password'):
    proxy_cfg['password_masked'] = mask_api_key(proxy_cfg['password'])
    proxy_cfg['password_set'] = True
    proxy_cfg['password'] = ''
else:
    proxy_cfg['password_masked'] = ''
    proxy_cfg['password_set'] = False
if proxy_cfg.get('username'):
    proxy_cfg['username_masked'] = mask_api_key(proxy_cfg['username'])
    proxy_cfg['username_set'] = True
    proxy_cfg['username'] = ''
else:
    proxy_cfg['username_masked'] = ''
    proxy_cfg['username_set'] = False
```

**Step 2: PUT /api/settings 端点支持代理配置更新**

在 `update_settings()` 函数中，`# 更新爬虫设置` 部分（约第 1010 行），添加代理配置处理：

```python
# 更新爬虫设置
if 'crawler' in data:
    cr = data['crawler']
    if 'timeout' in cr:
        current_settings['crawler']['timeout'] = int(cr['timeout'])
    if 'max_articles' in cr:
        current_settings['crawler']['max_articles'] = int(cr['max_articles'])

    # 更新代理设置
    if 'proxy' in cr:
        proxy = cr['proxy']
        if 'proxy' not in current_settings['crawler']:
            current_settings['crawler']['proxy'] = {}
        proxy_cfg = current_settings['crawler']['proxy']

        if 'enabled' in proxy:
            proxy_cfg['enabled'] = bool(proxy['enabled'])
        if 'host' in proxy:
            proxy_cfg['host'] = proxy['host'].strip()
        if 'port' in proxy:
            proxy_cfg['port'] = int(proxy['port'])
        if 'protocol' in proxy:
            proxy_cfg['protocol'] = proxy['protocol'].strip()
        # 用户名和密码只在非空时才更新（避免清空已配置的值）
        if 'username' in proxy and proxy['username']:
            proxy_cfg['username'] = proxy['username'].strip()
        if 'password' in proxy and proxy['password']:
            proxy_cfg['password'] = proxy['password'].strip()
```

**Step 3: 添加代理连接测试端点**

在 `routes/api.py` 中（`test-api` 端点附近）添加：

```python
@api_bp.route('/settings/test-proxy', methods=['POST'])
def test_proxy_connection():
    """测试代理连接"""
    try:
        from models.settings import load_settings
        settings = load_settings()
        proxy_cfg = settings.get('crawler', {}).get('proxy', {})

        host = proxy_cfg.get('host', '')
        port = proxy_cfg.get('port', 9000)
        username = proxy_cfg.get('username', '')
        password = proxy_cfg.get('password', '')
        protocol = proxy_cfg.get('protocol', 'http')

        if not host:
            return error_response('未配置代理地址', 400)

        if username and password:
            proxy_url = f"{protocol}://{username}:{password}@{host}:{port}"
        else:
            proxy_url = f"{protocol}://{host}:{port}"

        proxies = {"http": proxy_url, "https": proxy_url}

        # 用 httpbin 测试代理是否可用
        import requests as http_requests
        resp = http_requests.get(
            'https://httpbin.org/ip',
            proxies=proxies,
            timeout=15
        )

        if resp.status_code == 200:
            ip_info = resp.json()
            return success_response({
                'message': '代理连接成功',
                'origin_ip': ip_info.get('origin', '未知')
            })
        else:
            return error_response(f'代理返回状态码 {resp.status_code}', 502)

    except http_requests.exceptions.ProxyError as e:
        return error_response(f'代理连接失败: 认证错误或代理不可用', 502)
    except http_requests.exceptions.ConnectTimeout:
        return error_response('代理连接超时', 504)
    except Exception as e:
        return error_response(f'代理测试失败: {str(e)}', 500)
```

**Step 4: 添加站点代理开关端点**

在 `routes/api.py` 插件端点区域（`auto-update` 端点附近）添加：

```python
@api_bp.route('/plugins/<plugin_id>/sites/<site_id>/proxy', methods=['PUT'])
def plugins_set_proxy(plugin_id: str, site_id: str):
    """
    设置站点是否使用代理
    请求体：{use_proxy: true/false}
    """
    try:
        data = request.get_json()
        if data is None:
            return error_response('请求体不能为空', 400)

        use_proxy = data.get('use_proxy')
        if use_proxy is None:
            return error_response('缺少 use_proxy 参数', 400)

        from plugins.registry import plugin_registry
        site = plugin_registry.get_site(plugin_id, site_id)
        if not site:
            return error_response('站点不存在', 404)

        from models.plugins import set_use_proxy
        result = set_use_proxy(plugin_id, site_id, bool(use_proxy))

        log_operation(
            action=f'{"启用" if use_proxy else "禁用"}站点代理: {site.get("name")}',
            details={'plugin_id': plugin_id, 'site_id': site_id, 'use_proxy': use_proxy},
            status='success'
        )

        return success_response({
            'plugin_id': plugin_id,
            'site_id': site_id,
            'use_proxy': use_proxy,
            'message': f'站点代理已{"启用" if use_proxy else "禁用"}'
        })
    except Exception as e:
        log_error(action='设置站点代理失败', error=str(e))
        return error_response('设置站点代理失败，请稍后重试', 500)
```

**Step 5: 提交**

```bash
git add routes/api.py
git commit -m "feat: api.py 代理设置端点和站点代理开关端点"
```

---

### Task 5: 前端 — 系统设置页代理配置卡片

**Files:**
- Modify: `templates/index.html:512-677` (设置弹窗)
- Modify: `static/js/dashboard.js:2937-2986` (loadSettings)
- Modify: `static/js/dashboard.js:3102-3148` (saveSettings)

**Step 1: index.html 设置弹窗中添加代理设置 HTML**

在 `templates/index.html` 设置弹窗的 LLM API 配置 section 之后（AI总结提示词 section 之前），添加代理设置 section：

```html
<!-- 代理设置 -->
<div class="settings-section">
    <div class="settings-section-header">
        <span class="section-title">代理设置</span>
        <span class="section-status" id="proxyStatus"></span>
    </div>
    <div class="form-group">
        <label class="form-label">全局代理开关</label>
        <label class="toggle-switch">
            <input type="checkbox" id="proxyEnabled">
            <span class="toggle-slider"></span>
        </label>
        <div class="form-hint">开启后，勾选了「使用代理」的站点将通过代理抓取</div>
    </div>
    <div id="proxyFields">
        <div class="form-row">
            <div class="form-group" style="flex:1">
                <label class="form-label">协议</label>
                <select id="proxyProtocol" class="form-select">
                    <option value="http">HTTP</option>
                    <option value="https">HTTPS</option>
                    <option value="socks5">SOCKS5</option>
                </select>
            </div>
            <div class="form-group" style="flex:3">
                <label class="form-label">主机地址</label>
                <input type="text" id="proxyHost" class="form-input" placeholder="us.proxy.geonode.io">
            </div>
            <div class="form-group" style="flex:1">
                <label class="form-label">端口</label>
                <input type="number" id="proxyPort" class="form-input" placeholder="9000" value="9000">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group" style="flex:1">
                <label class="form-label">用户名</label>
                <input type="text" id="proxyUsername" class="form-input" placeholder="用户名（可选）">
                <div class="form-hint" id="proxyUsernameHint"></div>
            </div>
            <div class="form-group" style="flex:1">
                <label class="form-label">密码</label>
                <div class="input-with-btn">
                    <input type="password" id="proxyPassword" class="form-input" placeholder="密码（可选）">
                    <button class="btn-icon" onclick="togglePasswordVisibility('proxyPassword')" title="显示/隐藏">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                    </button>
                </div>
                <div class="form-hint" id="proxyPasswordHint"></div>
            </div>
        </div>
        <div class="form-group">
            <button class="btn btn-outline btn-sm" onclick="testProxyConnection()" id="btnTestProxy">
                <span class="btn-text">测试代理</span>
                <span class="btn-loading" style="display:none;">测试中...</span>
            </button>
        </div>
    </div>
</div>
```

**Step 2: dashboard.js loadSettings 函数加载代理配置**

在 `loadSettings()` 函数中（加载翻译设置之前），添加代理配置加载：

```javascript
// 加载代理设置
const proxyCfg = data.crawler?.proxy || {};
document.getElementById('proxyEnabled').checked = proxyCfg.enabled || false;
document.getElementById('proxyProtocol').value = proxyCfg.protocol || 'http';
document.getElementById('proxyHost').value = proxyCfg.host || '';
document.getElementById('proxyPort').value = proxyCfg.port || 9000;
document.getElementById('proxyUsername').value = '';
document.getElementById('proxyUsername').placeholder = proxyCfg.username_set ? '已配置（输入新值覆盖）' : '用户名（可选）';
document.getElementById('proxyPassword').value = '';
document.getElementById('proxyPassword').placeholder = proxyCfg.password_set ? '已配置（输入新值覆盖）' : '密码（可选）';

const proxyUsernameHint = document.getElementById('proxyUsernameHint');
proxyUsernameHint.textContent = proxyCfg.username_masked ? `当前: ${proxyCfg.username_masked}` : '';
const proxyPasswordHint = document.getElementById('proxyPasswordHint');
proxyPasswordHint.textContent = proxyCfg.password_masked ? `当前: ${proxyCfg.password_masked}` : '';

const proxyStatus = document.getElementById('proxyStatus');
if (proxyCfg.enabled && proxyCfg.host) {
    proxyStatus.textContent = '已启用';
    proxyStatus.className = 'section-status configured';
} else if (proxyCfg.host) {
    proxyStatus.textContent = '已配置（未启用）';
    proxyStatus.className = 'section-status not-configured';
} else {
    proxyStatus.textContent = '未配置';
    proxyStatus.className = 'section-status not-configured';
}
```

**Step 3: dashboard.js saveSettings 函数保存代理配置**

在 `saveSettings()` 函数中，构造 settings 对象的位置，添加 crawler.proxy 节：

```javascript
const settings = {
    llm: { /* 现有逻辑不变 */ },
    crawler: {
        proxy: {
            enabled: document.getElementById('proxyEnabled').checked,
            protocol: document.getElementById('proxyProtocol').value,
            host: document.getElementById('proxyHost').value.trim(),
            port: parseInt(document.getElementById('proxyPort').value) || 9000
        }
    }
};

// 用户名和密码只在输入了新值时才提交
const proxyUsername = document.getElementById('proxyUsername').value.trim();
if (proxyUsername) settings.crawler.proxy.username = proxyUsername;
const proxyPassword = document.getElementById('proxyPassword').value.trim();
if (proxyPassword) settings.crawler.proxy.password = proxyPassword;
```

**Step 4: 添加 testProxyConnection 函数**

```javascript
async function testProxyConnection() {
    const btn = document.getElementById('btnTestProxy');
    btn.querySelector('.btn-text').style.display = 'none';
    btn.querySelector('.btn-loading').style.display = 'inline';
    btn.disabled = true;

    try {
        const response = await fetch('/api/settings/test-proxy', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            showToast(`代理连接成功，出口IP: ${data.data.origin_ip}`, 'success');
        } else {
            showToast(data.error || '代理连接失败', 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    } finally {
        btn.querySelector('.btn-text').style.display = 'inline';
        btn.querySelector('.btn-loading').style.display = 'none';
        btn.disabled = false;
    }
}
```

**Step 5: 提交**

```bash
git add templates/index.html static/js/dashboard.js
git commit -m "feat: 前端系统设置页代理配置卡片"
```

---

### Task 6: 前端 — 插件管理页站点代理开关

**Files:**
- Modify: `static/js/dashboard.js:1720-1808` (renderPlugins 函数)
- Modify: `static/css/dashboard.css` (代理开关样式)

**Step 1: renderPlugins 中每个站点行添加代理开关**

在 `renderPlugins()` 函数中，每个站点行的 `site-auto-update` div 之后、`site-crawl-btn` div 之前，添加代理开关：

```javascript
<div class="site-proxy ${site.enabled ? '' : 'hidden'}">
    <label class="proxy-toggle-label" title="使用代理抓取">
        <input type="checkbox" ${site.use_proxy ? 'checked' : ''}
               onchange="toggleSiteProxy('${plugin.id}', '${site.id}', this.checked)"
               ${site.enabled ? '' : 'disabled'}>
        <span class="proxy-toggle-text">代理</span>
    </label>
</div>
```

**Step 2: 添加 toggleSiteProxy 函数**

```javascript
async function toggleSiteProxy(pluginId, siteId, useProxy) {
    try {
        const response = await fetch(`/api/plugins/${pluginId}/sites/${siteId}/proxy`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ use_proxy: useProxy })
        });
        const data = await response.json();
        if (data.success) {
            showToast(`站点代理已${useProxy ? '启用' : '禁用'}`, 'success');
        } else {
            showToast(data.error || '操作失败', 'error');
            await loadPlugins();
        }
    } catch (e) {
        showToast('网络错误', 'error');
        await loadPlugins();
    }
}
```

**Step 3: dashboard.css 添加代理开关样式**

```css
/* 站点代理开关 */
.site-proxy {
    display: flex;
    align-items: center;
    margin-right: 8px;
}

.proxy-toggle-label {
    display: flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    font-size: 12px;
    color: var(--text-secondary);
}

.proxy-toggle-label input[type="checkbox"] {
    accent-color: #f59e0b;
    width: 14px;
    height: 14px;
}

.proxy-toggle-label input[type="checkbox"]:checked + .proxy-toggle-text {
    color: #f59e0b;
}

.proxy-toggle-text {
    white-space: nowrap;
}

/* 设置弹窗表单行布局 */
.form-row {
    display: flex;
    gap: 12px;
}

.form-row .form-group {
    min-width: 0;
}
```

**Step 4: 提交**

```bash
git add static/js/dashboard.js static/css/dashboard.css
git commit -m "feat: 前端插件管理页站点代理开关"
```

---

### Task 7: 集成测试 — 手动验证

**Step 1: 验证设置页代理配置**

1. 启动应用 `python app.py`
2. 打开系统设置弹窗，确认出现「代理设置」卡片
3. 填入 GeoNode 代理信息：host=`us.proxy.geonode.io`, port=`9000`, username/password
4. 点击「测试代理」，确认返回出口 IP
5. 保存设置，重新打开确认配置已持久化（密码已遮蔽）

**Step 2: 验证站点代理开关**

1. 打开插件管理弹窗
2. 找到 Fox News 站点，勾选「代理」开关
3. 点击立即更新该站点，确认控制台日志输出 `🔒 福克斯新闻 使用代理`

**Step 3: 验证全局开关控制**

1. 在设置页关闭全局代理开关
2. 再次更新 Fox News，确认不走代理（控制台无代理日志）

**Step 4: 最终提交**

```bash
git add -A
git commit -m "feat: 代理 IP 集成完成 — 全局配置 + 站点级开关"
```
