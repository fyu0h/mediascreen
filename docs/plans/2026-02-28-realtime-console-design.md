# 实时控制台输出设计方案

> 日期: 2026-02-28
> 状态: 已批准

## 目标

在现有"后台日志"弹窗中新增"控制台"选项卡，实时显示 Python 进程的 stdout/stderr 输出，类似终端视图。

## 技术方案

**方案 A：Python 层 stdout/stderr 重定向 + 环形缓冲区 + SSE 推送**

### 后端架构

#### 新模块 `models/console_log.py`

- **StreamInterceptor**: 替换 `sys.stdout` / `sys.stderr`，拦截所有 write() 调用
  - 保留原始流输出（终端不受影响）
  - 同时将文本写入 ConsoleLogManager 的环形缓冲区
- **ConsoleLogManager（单例）**:
  - 环形缓冲区 `collections.deque(maxlen=2000)`，内存约 1-2MB
  - 每行记录: `{id: 自增序号, timestamp: ISO时间, stream: "stdout"|"stderr", text: "..."}`
  - `threading.Event` 通知 SSE 端点新行到达
  - 线程安全（threading.Lock 保护写入）

#### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/console/stream` | GET | SSE 实时流，支持 `?last_id=N` 增量推送 |
| `/api/console/history` | GET | 获取缓冲区历史，支持 `?lines=200` |
| `/api/console/clear` | POST | 清空缓冲区 |

#### SSE 协议

- `event: log` — 日志行数据 (JSON)
- `event: heartbeat` — 每 15 秒心跳保活
- `id: {行号}` — 支持断线续传 (Last-Event-ID)

#### 初始化位置

在 `app.py` 的 `create_app()` 中调用 `ConsoleLogManager.install()` 安装拦截器。

### 前端设计

#### Tab 切换

在现有"后台日志"弹窗顶部增加两个选项卡：
- **结构日志** — 现有功能不变
- **控制台** — 新增实时控制台视图

#### 控制台视图

- 深色背景 + 等宽字体（终端风格）
- 工具栏: [自动滚动 ✓] [清空] [暂停/继续]
- 每行显示: `时间戳 [OUT/ERR] 文本内容`
- stderr 行用红色高亮
- 自动滚动到底部（可关闭）

#### SSE 连接管理

- 切换到"控制台"Tab 时建立 EventSource 连接
- 切回"结构日志"或关闭弹窗时断开连接
- 断线自动重连（3 秒延迟），携带 last_id 续传
- 暂停时缓存消息但不渲染，继续时批量追加

### 数据流

```
print("xxx") → sys.stdout.write()
    → StreamInterceptor.write()
        → 原始终端输出（不变）
        → ConsoleLogManager.add_line()
            → deque 追加 {id, timestamp, stream, text}
            → threading.Event.set() 通知 SSE
                → SSE 端点 yield → 浏览器 EventSource
                    → 前端追加 DOM 元素
```

### 错误处理

- SSE 断开: 前端 EventSource.onerror 自动重连
- 缓冲区溢出: deque 自动淘汰最旧行
- 多用户连接: 每个 SSE 连接独立维护 last_id
- 拦截器异常: write() 方法 try-except，不影响原始输出

### 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `models/console_log.py` | 新建 | StreamInterceptor + ConsoleLogManager |
| `routes/api.py` | 修改 | 添加 3 个 console API 端点 |
| `app.py` | 修改 | create_app() 中初始化控制台捕获 |
| `templates/index.html` | 修改 | 日志弹窗增加 Tab 切换和控制台 DOM |
| `static/js/dashboard.js` | 修改 | 控制台前端逻辑（SSE、渲染、控件） |
| `static/css/dashboard.css` | 修改 | 控制台终端样式 |
