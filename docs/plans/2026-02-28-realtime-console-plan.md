# 实时控制台输出 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有"后台日志"弹窗中新增"控制台"选项卡，通过 SSE 实时显示 Python 进程的全部 stdout/stderr 输出。

**Architecture:** Python 层拦截 `sys.stdout`/`sys.stderr`，写入线程安全的环形缓冲区（`collections.deque`），Flask SSE 端点从缓冲区读取新行推送给前端 `EventSource`。前端在现有日志弹窗中新增 Tab 切换，控制台 Tab 以终端风格渲染实时日志流。

**Tech Stack:** Python (threading, collections.deque), Flask SSE (generator + `text/event-stream`), 原生 JS EventSource

**Note:** 本项目无自动化测试框架，跳过 TDD 步骤，每个任务完成后手动验证。

---

### Task 1: 创建 ConsoleLogManager 后端模块

**Files:**
- Create: `models/console_log.py`

**Step 1: 创建 `models/console_log.py`**

编写完整代码：

```python
# -*- coding: utf-8 -*-
"""
实时控制台日志模块
拦截 sys.stdout/sys.stderr，写入环形缓冲区，通过 SSE 推送给前端
"""

import sys
import threading
from collections import deque
from datetime import datetime
from typing import List, Dict, Any, Optional


class StreamInterceptor:
    """
    流拦截器：替换 sys.stdout / sys.stderr
    同时写入原始流和 ConsoleLogManager 缓冲区
    """

    def __init__(self, original_stream, stream_name: str, manager: 'ConsoleLogManager'):
        self._original = original_stream
        self._stream_name = stream_name  # "stdout" 或 "stderr"
        self._manager = manager
        # 保留原始流的属性，避免兼容性问题
        self.encoding = getattr(original_stream, 'encoding', 'utf-8')

    def write(self, text: str) -> int:
        """拦截 write 调用"""
        # 始终先写入原始流
        try:
            result = self._original.write(text)
        except Exception:
            result = 0

        # 写入缓冲区（忽略空字符串和纯换行）
        try:
            if text and text.strip():
                self._manager.add_line(text.rstrip('\n'), self._stream_name)
        except Exception:
            pass  # 绝不影响原始输出

        return result

    def flush(self):
        """传递 flush 调用"""
        try:
            self._original.flush()
        except Exception:
            pass

    def fileno(self):
        """传递 fileno 调用"""
        return self._original.fileno()

    def isatty(self):
        """传递 isatty 调用"""
        return self._original.isatty()

    def __getattr__(self, name):
        """其他属性代理到原始流"""
        return getattr(self._original, name)


class ConsoleLogManager:
    """
    控制台日志管理器（单例）
    维护环形缓冲区，支持 SSE 增量推送
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._buffer: deque = deque(maxlen=2000)
        self._line_id: int = 0
        self._buffer_lock = threading.Lock()
        self._new_line_event = threading.Event()
        self._installed = False
        self._original_stdout = None
        self._original_stderr = None
        self._initialized = True

    def install(self):
        """安装 stdout/stderr 拦截器"""
        if self._installed:
            return

        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

        sys.stdout = StreamInterceptor(self._original_stdout, 'stdout', self)
        sys.stderr = StreamInterceptor(self._original_stderr, 'stderr', self)

        self._installed = True

    def uninstall(self):
        """卸载拦截器，恢复原始流"""
        if not self._installed:
            return

        if self._original_stdout:
            sys.stdout = self._original_stdout
        if self._original_stderr:
            sys.stderr = self._original_stderr

        self._installed = False

    def add_line(self, text: str, stream: str = 'stdout'):
        """添加一行到缓冲区"""
        with self._buffer_lock:
            self._line_id += 1
            entry = {
                'id': self._line_id,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                'stream': stream,
                'text': text
            }
            self._buffer.append(entry)

        # 通知所有等待的 SSE 连接
        self._new_line_event.set()
        self._new_line_event.clear()

    def get_lines_after(self, last_id: int = 0) -> List[Dict[str, Any]]:
        """获取指定 ID 之后的所有行"""
        with self._buffer_lock:
            return [line for line in self._buffer if line['id'] > last_id]

    def get_history(self, lines: int = 200) -> List[Dict[str, Any]]:
        """获取最近 N 行历史"""
        with self._buffer_lock:
            items = list(self._buffer)
            return items[-lines:] if len(items) > lines else items

    def get_latest_id(self) -> int:
        """获取当前最新行 ID"""
        with self._buffer_lock:
            return self._line_id

    def clear(self):
        """清空缓冲区"""
        with self._buffer_lock:
            self._buffer.clear()
            # 不重置 line_id，避免 SSE 客户端混淆

    def wait_for_new_line(self, timeout: float = 15.0) -> bool:
        """等待新行到达，返回是否有新行"""
        return self._new_line_event.wait(timeout=timeout)


# 全局单例
console_manager = ConsoleLogManager()
```

**Step 2: 验证模块可导入**

Run: `cd "D:/code/态势感知" && python -c "from models.console_log import console_manager; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add models/console_log.py
git commit -m "feat: 新增控制台日志管理器（stdout/stderr 拦截 + 环形缓冲区）"
```

---

### Task 2: 添加控制台 API 端点（含 SSE 流）

**Files:**
- Modify: `routes/api.py` — 在日志接口区块(line 1878)之后插入 3 个新端点

**Step 1: 在 `routes/api.py` 中添加控制台 API**

在 `logs_clear()` 函数（line 1878）和 `# ==================== 成果展示接口 ====================`（line 1881）之间插入以下代码：

```python
# ==================== 控制台实时输出接口 ====================

from flask import Response, stream_with_context
import json as json_module

@api_bp.route('/console/stream', methods=['GET'])
def console_stream():
    """
    SSE 实时控制台输出流
    参数：last_id - 从该 ID 之后开始推送（默认 0，推送全部缓冲区）
    """
    from models.console_log import console_manager

    last_id = request.args.get('last_id', 0, type=int)

    def generate():
        nonlocal last_id
        while True:
            # 获取新行
            lines = console_manager.get_lines_after(last_id)
            if lines:
                for line in lines:
                    last_id = line['id']
                    yield f"id: {line['id']}\nevent: log\ndata: {json_module.dumps(line, ensure_ascii=False)}\n\n"
            else:
                # 无新行，发送心跳保活
                yield f"event: heartbeat\ndata: {{}}\n\n"
                # 等待新行到达（最多等 15 秒）
                console_manager.wait_for_new_line(timeout=15.0)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@api_bp.route('/console/history', methods=['GET'])
def console_history():
    """
    获取控制台历史输出
    参数：lines - 返回最近 N 行（默认 200，最大 2000）
    """
    from models.console_log import console_manager

    try:
        lines = request.args.get('lines', 200, type=int)
        lines = min(lines, 2000)
        data = console_manager.get_history(lines)
        return success_response({
            'items': data,
            'latest_id': console_manager.get_latest_id()
        })
    except Exception as e:
        log_error(action='获取控制台历史失败', error=str(e))
        return error_response('获取控制台历史失败', 500)


@api_bp.route('/console/clear', methods=['POST'])
def console_clear():
    """清空控制台缓冲区"""
    from models.console_log import console_manager

    try:
        console_manager.clear()
        return success_response({'message': '控制台已清空'})
    except Exception as e:
        log_error(action='清空控制台失败', error=str(e))
        return error_response('清空控制台失败', 500)
```

**注意事项：**
- `console/stream` 端点**不做** session 认证检查（SSE 长连接不适合 session 验证，且此端点无敏感数据）
- 使用 `json_module` 避免与已有导入冲突（检查 api.py 顶部是否已有 `import json`，如有直接用 `json`）
- `stream_with_context` 确保 Flask 的请求上下文在 generator 中可用

**Step 2: 检查是否需要添加 import**

检查 `routes/api.py` 顶部是否已有 `from flask import Response`。如果没有，在 line 12 的 `from flask import Blueprint, request, jsonify, session` 中追加 `Response, stream_with_context`。

同样检查 `import json`，如果顶部已有则在上面代码中用 `json` 替换 `json_module`。

**Step 3: 手动验证**

Run: `cd "D:/code/态势感知" && python -c "from routes.api import api_bp; print('API routes OK')"`
Expected: `API routes OK`

**Step 4: Commit**

```bash
git add routes/api.py
git commit -m "feat: 添加控制台实时输出 API（SSE 流 + 历史 + 清空）"
```

---

### Task 3: 在 app.py 中初始化控制台拦截

**Files:**
- Modify: `app.py` — 在 `create_app()` 函数中安装拦截器

**Step 1: 修改 `app.py`**

在 `app.py` 的 `create_app()` 函数中，在"注册蓝图"（line 39-40）之后、"请求日志中间件"（line 42）之前，添加：

```python
    # 安装控制台输出拦截器
    from models.console_log import console_manager
    console_manager.install()
```

即在 line 40 `app.register_blueprint(views_bp)` 之后插入上面两行。

**Step 2: 手动验证**

Run: `cd "D:/code/态势感知" && python -c "from app import app; print('App创建成功，拦截器已安装')"`
Expected: 输出中包含 `App创建成功，拦截器已安装`

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: 在 create_app 中安装控制台输出拦截器"
```

---

### Task 4: 修改前端 HTML — 日志弹窗增加 Tab 切换和控制台面板

**Files:**
- Modify: `templates/index.html` — lines 755-831（后台日志弹窗区域）

**Step 1: 修改日志弹窗 HTML**

将 `templates/index.html` 中 line 755-831 的后台日志弹窗替换为带 Tab 切换的版本。

**具体修改：**

1. 在 `<h3 class="modal-title">后台日志</h3>`（line 759）和 `<button class="modal-close" ...>`（line 760）之间不变。

2. 在 `<div class="modal-body">`（line 762）之后、`<!-- 日志统计 -->`（line 763）之前，插入 Tab 切换栏：

```html
                <!-- Tab 切换栏 -->
                <div class="logs-tab-bar">
                    <button class="logs-tab active" data-tab="structured" onclick="switchLogsTab('structured')">结构日志</button>
                    <button class="logs-tab" data-tab="console" onclick="switchLogsTab('console')">控制台</button>
                </div>
```

3. 将现有的日志统计、工具栏、列表、分页区域（line 763-829）用一个 `<div id="structuredLogsPanel">` 包裹起来：

```html
                <!-- 结构日志面板 -->
                <div id="structuredLogsPanel" class="logs-panel active">
                    <!-- 原有的日志统计 -->
                    <div class="logs-stats" id="logsStats">
                        ...（保持原有内容完全不变）
                    </div>
                    <!-- 原有的日志工具栏 -->
                    ...（保持原有内容完全不变）
                    <!-- 原有的日志列表 -->
                    ...（保持原有内容完全不变）
                    <!-- 原有的分页 -->
                    ...（保持原有内容完全不变）
                </div>
```

4. 在 `</div><!-- structuredLogsPanel -->` 之后、`</div><!-- modal-body -->` 之前，插入控制台面板：

```html
                <!-- 控制台面板 -->
                <div id="consoleLogsPanel" class="logs-panel">
                    <div class="console-toolbar">
                        <div class="toolbar-left">
                            <label class="console-checkbox">
                                <input type="checkbox" id="consoleAutoScroll" checked onchange="toggleConsoleAutoScroll()">
                                <span>自动滚动</span>
                            </label>
                        </div>
                        <div class="toolbar-right">
                            <span class="console-status" id="consoleStatus">未连接</span>
                            <button class="btn btn-outline btn-sm" id="consolePauseBtn" onclick="toggleConsolePause()">暂停</button>
                            <button class="btn btn-outline btn-sm btn-danger" onclick="clearConsole()">清空</button>
                        </div>
                    </div>
                    <div class="console-output" id="consoleOutput">
                        <div class="console-welcome">等待连接...</div>
                    </div>
                    <div class="console-footer">
                        <span id="consoleLineCount">0 行</span>
                    </div>
                </div>
```

**Step 2: 验证 HTML 结构完好**

打开浏览器访问首页，打开后台日志弹窗，应看到两个 Tab 选项卡，点击切换不报错（JS 功能在下一步实现）。

**Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: 后台日志弹窗增加控制台 Tab 和面板 HTML 结构"
```

---

### Task 5: 添加控制台面板 CSS 样式

**Files:**
- Modify: `static/css/dashboard.css` — 在现有 `.logs-pagination`（约 line 3653-3665）样式之后插入

**Step 1: 添加控制台相关 CSS**

在 `.logs-pagination` 样式块之后插入以下 CSS：

```css
/* ========== 日志 Tab 切换 ========== */
.logs-tab-bar {
    display: flex;
    gap: 0;
    margin-bottom: 16px;
    border-bottom: 1px solid rgba(0, 243, 255, 0.15);
}

.logs-tab {
    padding: 8px 20px;
    background: transparent;
    border: none;
    color: rgba(224, 224, 224, 0.6);
    font-size: 13px;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: all 0.3s ease;
}

.logs-tab:hover {
    color: rgba(224, 224, 224, 0.9);
}

.logs-tab.active {
    color: #00f3ff;
    border-bottom-color: #00f3ff;
}

.logs-panel {
    display: none;
}

.logs-panel.active {
    display: block;
}

/* ========== 控制台面板 ========== */
.console-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    margin-bottom: 8px;
    background: rgba(0, 0, 0, 0.2);
    border-radius: 6px;
}

.console-toolbar .toolbar-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.console-toolbar .toolbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
}

.console-checkbox {
    display: flex;
    align-items: center;
    gap: 6px;
    color: rgba(224, 224, 224, 0.7);
    font-size: 12px;
    cursor: pointer;
}

.console-checkbox input[type="checkbox"] {
    accent-color: #00f3ff;
}

.console-status {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.1);
    color: rgba(224, 224, 224, 0.5);
}

.console-status.connected {
    background: rgba(0, 200, 83, 0.2);
    color: #00c853;
}

.console-status.paused {
    background: rgba(255, 193, 7, 0.2);
    color: #ffc107;
}

.console-output {
    background: #0a0e14;
    border: 1px solid rgba(0, 243, 255, 0.1);
    border-radius: 6px;
    padding: 12px;
    height: 450px;
    overflow-y: auto;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 12px;
    line-height: 1.6;
    color: #b0bec5;
}

.console-output::-webkit-scrollbar {
    width: 6px;
}

.console-output::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.3);
}

.console-output::-webkit-scrollbar-thumb {
    background: rgba(0, 243, 255, 0.2);
    border-radius: 3px;
}

.console-line {
    white-space: pre-wrap;
    word-break: break-all;
    padding: 1px 0;
}

.console-line .console-time {
    color: rgba(0, 243, 255, 0.5);
    margin-right: 8px;
    user-select: none;
}

.console-line .console-tag {
    margin-right: 8px;
    font-weight: bold;
    user-select: none;
}

.console-line .console-tag.stdout {
    color: #4caf50;
}

.console-line .console-tag.stderr {
    color: #ff5252;
}

.console-line.stderr {
    color: #ff8a80;
    background: rgba(255, 82, 82, 0.05);
}

.console-welcome {
    color: rgba(224, 224, 224, 0.3);
    text-align: center;
    padding: 40px 0;
    font-style: italic;
}

.console-footer {
    display: flex;
    justify-content: flex-end;
    padding: 6px 0;
    font-size: 11px;
    color: rgba(224, 224, 224, 0.4);
}
```

**Step 2: 验证样式无语法错误**

刷新浏览器，检查日志弹窗样式正常渲染。

**Step 3: Commit**

```bash
git add static/css/dashboard.css
git commit -m "feat: 添加控制台面板终端风格 CSS 样式"
```

---

### Task 6: 实现控制台前端 JS 逻辑

**Files:**
- Modify: `static/js/dashboard.js` — 在现有后台日志功能区块末尾（约 line 3689 `renderLogDetail` 函数结束后）插入

**Step 1: 修改 `openLogsModal()` 和 `closeLogsModal()`**

修改 `static/js/dashboard.js` 中现有的 `openLogsModal()`（line 3497-3502）和 `closeLogsModal()`（line 3504-3506）：

**`openLogsModal` 修改为：**
```javascript
function openLogsModal() {
    document.getElementById('logsModal').classList.add('active');
    // 默认显示结构日志 Tab
    switchLogsTab('structured');
}
```

**`closeLogsModal` 修改为：**
```javascript
function closeLogsModal() {
    document.getElementById('logsModal').classList.remove('active');
    // 关闭弹窗时断开 SSE 连接
    disconnectConsoleSSE();
}
```

**Step 2: 在后台日志功能区块末尾插入控制台 JS 逻辑**

在 `renderLogDetail` 函数末尾（约 line 3689 后面的 `}` 闭合括号之后），插入以下完整代码：

```javascript
// ==================== 控制台实时输出功能 ====================

let consoleEventSource = null;
let consoleLastId = 0;
let consolePaused = false;
let consoleAutoScroll = true;
let consolePausedBuffer = [];
let consoleLineCount = 0;

function switchLogsTab(tabName) {
    // 更新 Tab 按钮状态
    document.querySelectorAll('.logs-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // 切换面板
    document.getElementById('structuredLogsPanel').classList.toggle('active', tabName === 'structured');
    document.getElementById('consoleLogsPanel').classList.toggle('active', tabName === 'console');

    if (tabName === 'structured') {
        // 切到结构日志时，断开 SSE 并加载结构日志
        disconnectConsoleSSE();
        logsCurrentPage = 1;
        loadLogsStats();
        loadLogs();
    } else if (tabName === 'console') {
        // 切到控制台时，加载历史并建立 SSE 连接
        loadConsoleHistory();
    }
}

async function loadConsoleHistory() {
    const outputEl = document.getElementById('consoleOutput');
    outputEl.innerHTML = '<div class="console-welcome">加载历史中...</div>';
    consoleLineCount = 0;

    try {
        const data = await fetchAPI('/console/history?lines=500');
        if (!data) {
            outputEl.innerHTML = '<div class="console-welcome">加载失败</div>';
            return;
        }

        outputEl.innerHTML = '';
        if (data.items && data.items.length > 0) {
            data.items.forEach(line => {
                appendConsoleLine(line);
            });
            consoleLastId = data.latest_id || 0;
        }

        // 加载完历史后建立 SSE 连接
        connectConsoleSSE();
    } catch (error) {
        outputEl.innerHTML = '<div class="console-welcome">加载失败</div>';
        console.error('加载控制台历史失败:', error);
    }
}

function connectConsoleSSE() {
    disconnectConsoleSSE();

    const url = `/api/console/stream?last_id=${consoleLastId}`;
    consoleEventSource = new EventSource(url);

    consoleEventSource.addEventListener('log', function(e) {
        try {
            const line = JSON.parse(e.data);
            consoleLastId = line.id;

            if (consolePaused) {
                consolePausedBuffer.push(line);
            } else {
                appendConsoleLine(line);
            }
        } catch (err) {
            // 忽略解析错误
        }
    });

    consoleEventSource.addEventListener('heartbeat', function(e) {
        // 心跳，无需处理
    });

    consoleEventSource.onopen = function() {
        updateConsoleStatus('connected', '已连接');
    };

    consoleEventSource.onerror = function() {
        updateConsoleStatus('', '重连中...');
        // EventSource 会自动重连，但我们需要用最新的 last_id
        // 3 秒后手动重连以确保 last_id 正确
        setTimeout(() => {
            if (consoleEventSource && consoleEventSource.readyState === EventSource.CLOSED) {
                connectConsoleSSE();
            }
        }, 3000);
    };
}

function disconnectConsoleSSE() {
    if (consoleEventSource) {
        consoleEventSource.close();
        consoleEventSource = null;
    }
    updateConsoleStatus('', '未连接');
}

function appendConsoleLine(line) {
    const outputEl = document.getElementById('consoleOutput');
    // 移除欢迎文字
    const welcomeEl = outputEl.querySelector('.console-welcome');
    if (welcomeEl) {
        welcomeEl.remove();
    }

    const lineEl = document.createElement('div');
    lineEl.className = `console-line ${line.stream}`;

    // 只显示时分秒毫秒
    const timePart = line.timestamp.split(' ')[1] || line.timestamp;
    const tag = line.stream === 'stderr' ? 'ERR' : 'OUT';

    lineEl.innerHTML =
        `<span class="console-time">${escapeHtml(timePart)}</span>` +
        `<span class="console-tag ${line.stream}">[${tag}]</span>` +
        `<span class="console-text">${escapeHtml(line.text)}</span>`;

    outputEl.appendChild(lineEl);

    // 限制 DOM 节点数量（最多保留 1000 行）
    while (outputEl.children.length > 1000) {
        outputEl.removeChild(outputEl.firstChild);
    }

    // 更新行计数
    consoleLineCount++;
    document.getElementById('consoleLineCount').textContent = `${consoleLineCount} 行`;

    // 自动滚动
    if (consoleAutoScroll) {
        outputEl.scrollTop = outputEl.scrollHeight;
    }
}

function toggleConsoleAutoScroll() {
    consoleAutoScroll = document.getElementById('consoleAutoScroll').checked;
}

function toggleConsolePause() {
    consolePaused = !consolePaused;
    const btn = document.getElementById('consolePauseBtn');

    if (consolePaused) {
        btn.textContent = '继续';
        updateConsoleStatus('paused', '已暂停');
    } else {
        btn.textContent = '暂停';
        updateConsoleStatus('connected', '已连接');

        // 批量追加暂停期间缓存的消息
        if (consolePausedBuffer.length > 0) {
            consolePausedBuffer.forEach(line => appendConsoleLine(line));
            consolePausedBuffer = [];
        }
    }
}

async function clearConsole() {
    try {
        const response = await fetch('/api/console/clear', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            document.getElementById('consoleOutput').innerHTML = '<div class="console-welcome">控制台已清空</div>';
            consoleLineCount = 0;
            document.getElementById('consoleLineCount').textContent = '0 行';
            showToast('控制台已清空', 'success');
        }
    } catch (error) {
        showToast('清空失败', 'error');
    }
}

function updateConsoleStatus(className, text) {
    const statusEl = document.getElementById('consoleStatus');
    if (statusEl) {
        statusEl.className = 'console-status ' + className;
        statusEl.textContent = text;
    }
}
```

**Step 3: 验证完整功能**

1. 启动应用：`python app.py`
2. 浏览器访问 `http://localhost:5000`
3. 登录后点击底部"日志"按钮
4. 验证两个 Tab（结构日志 / 控制台）出现
5. 切换到"控制台"Tab，应看到启动日志输出
6. 执行一次爬虫任务，观察控制台实时更新
7. 测试暂停/继续、清空、自动滚动功能
8. 关闭弹窗再重新打开，确认 SSE 正确断开和重连

**Step 4: Commit**

```bash
git add static/js/dashboard.js
git commit -m "feat: 实现控制台前端逻辑（SSE 连接、实时渲染、暂停/清空控件）"
```

---

### Task 7: 端到端验证和最终提交

**Step 1: 完整功能测试清单**

- [ ] 启动应用后，终端输出不受影响（拦截器透传正常）
- [ ] 打开日志弹窗，Tab 切换正常
- [ ] 控制台 Tab 显示历史输出
- [ ] 新的 print() 输出实时出现在控制台
- [ ] stderr 输出用红色显示
- [ ] 暂停后消息缓存，继续后批量显示
- [ ] 清空按钮工作正常
- [ ] 关闭弹窗断开 SSE（浏览器 DevTools Network 确认）
- [ ] 重新打开弹窗重新连接
- [ ] 结构日志 Tab 功能不受影响

**Step 2: 最终提交**

如果有需要的修正，合并成最终提交：

```bash
git add -A
git commit -m "feat: 实时控制台输出 — 完整端到端功能验证"
git push
```
