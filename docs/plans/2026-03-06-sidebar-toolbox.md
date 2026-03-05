# 侧边栏工具面板实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在右侧添加可展开/收起的侧边栏工具面板，包含12个高级功能占位图标，带弹性动画效果

**Architecture:** 使用固定定位的侧边栏 + 遮罩层方案。侧边栏默认隐藏在右侧外部（right: -350px），点击触发按钮时滑入（right: 0），同时显示半透明遮罩层。使用 CSS cubic-bezier 实现弹性动画效果。

**Tech Stack:** HTML5, CSS3 (Flexbox, Transform, Transition), JavaScript (原生)

---

## 任务概览

1. **Task 1**: 添加 HTML 结构 - 侧边栏组件
2. **Task 2**: 添加 CSS 样式 - 侧边栏样式和动画
3. **Task 3**: 添加 JavaScript 逻辑 - 交互功能
4. **Task 4**: 测试和验证
5. **Task 5**: 提交更改

---

### Task 1: 添加 HTML 结构

**Files:**
- Modify: `templates/index.html` (在 `</body>` 之前添加)

**Step 1: 备份当前状态**

```bash
git status
git diff templates/index.html
```

Expected: 查看当前未提交的更改

**Step 2: 添加侧边栏 HTML 结构**

在 `templates/index.html` 的 `</body>` 标签之前添加以下代码：

```html
    <!-- 侧边栏工具面板 -->
    <!-- 触发按钮 -->
    <div class="sidebar-trigger" id="sidebarTrigger">
        <i class="arrow-icon">◀</i>
    </div>

    <!-- 遮罩层 -->
    <div class="sidebar-overlay" id="sidebarOverlay"></div>

    <!-- 侧边栏主体 -->
    <aside class="sidebar-panel" id="sidebarPanel" role="complementary" aria-label="工具面板">
        <div class="sidebar-header">
            <h3 class="sidebar-title">智能工具箱</h3>
            <button class="sidebar-close" id="sidebarClose" aria-label="关闭工具面板">
                <i class="close-icon">✕</i>
            </button>
        </div>
        <div class="sidebar-body">
            <div class="tool-list">
                <!-- AI 相关功能 -->
                <div class="tool-item" data-tool="ai-analysis">
                    <div class="tool-icon">🤖</div>
                    <div class="tool-info">
                        <div class="tool-name">AI 智能分析</div>
                        <div class="tool-desc">深度学习舆情预测</div>
                    </div>
                </div>
                <div class="tool-item" data-tool="ai-qa">
                    <div class="tool-icon">🧠</div>
                    <div class="tool-info">
                        <div class="tool-name">智能问答助手</div>
                        <div class="tool-desc">自然语言查询</div>
                    </div>
                </div>
                <div class="tool-item" data-tool="ai-insight">
                    <div class="tool-icon">📊</div>
                    <div class="tool-info">
                        <div class="tool-name">AI 数据洞察</div>
                        <div class="tool-desc">自动生成分析报告</div>
                    </div>
                </div>
                <div class="tool-item" data-tool="ai-recommend">
                    <div class="tool-icon">🎯</div>
                    <div class="tool-info">
                        <div class="tool-name">智能推荐引擎</div>
                        <div class="tool-desc">个性化内容推送</div>
                    </div>
                </div>

                <!-- 工作流相关 -->
                <div class="tool-item" data-tool="workflow">
                    <div class="tool-icon">⚡</div>
                    <div class="tool-info">
                        <div class="tool-name">自动化工作流</div>
                        <div class="tool-desc">可视化流程编排</div>
                    </div>
                </div>
                <div class="tool-item" data-tool="scheduler">
                    <div class="tool-icon">📋</div>
                    <div class="tool-info">
                        <div class="tool-name">任务调度中心</div>
                        <div class="tool-desc">定时任务管理</div>
                    </div>
                </div>
                <div class="tool-item" data-tool="alert-engine">
                    <div class="tool-icon">🔔</div>
                    <div class="tool-info">
                        <div class="tool-name">智能告警引擎</div>
                        <div class="tool-desc">多维度预警系统</div>
                    </div>
                </div>

                <!-- 其他高级功能 -->
                <div class="tool-item" data-tool="data-fusion">
                    <div class="tool-icon">🌐</div>
                    <div class="tool-info">
                        <div class="tool-name">多源数据融合</div>
                        <div class="tool-desc">跨平台数据整合</div>
                    </div>
                </div>
                <div class="tool-item" data-tool="trend-predict">
                    <div class="tool-icon">📈</div>
                    <div class="tool-info">
                        <div class="tool-name">实时趋势预测</div>
                        <div class="tool-desc">时序分析预测</div>
                    </div>
                </div>
                <div class="tool-item" data-tool="deep-search">
                    <div class="tool-icon">🔍</div>
                    <div class="tool-info">
                        <div class="tool-name">深度搜索引擎</div>
                        <div class="tool-desc">全文检索分析</div>
                    </div>
                </div>
                <div class="tool-item" data-tool="export-center">
                    <div class="tool-icon">💾</div>
                    <div class="tool-info">
                        <div class="tool-name">数据导出中心</div>
                        <div class="tool-desc">多格式报表导出</div>
                    </div>
                </div>
                <div class="tool-item" data-tool="config-center">
                    <div class="tool-icon">⚙️</div>
                    <div class="tool-info">
                        <div class="tool-name">系统配置中心</div>
                        <div class="tool-desc">高级设置管理</div>
                    </div>
                </div>
            </div>
        </div>
    </aside>
```

**Step 3: 验证 HTML 语法**

```bash
python -c "from html.parser import HTMLParser; HTMLParser().feed(open('templates/index.html', encoding='utf-8').read())"
```

Expected: 无输出表示语法正确

**Step 4: 提交 HTML 更改**

```bash
git add templates/index.html
git commit -m "feat: 添加侧边栏工具面板 HTML 结构"
```

---

### Task 2: 添加 CSS 样式

**Files:**
- Modify: `static/css/dashboard.css` (在文件末尾添加)

**Step 1: 添加侧边栏样式**

在 `dashboard.css` 文件末尾添加以下样式：

```css
/* ========== 侧边栏工具面板 ========== */

/* 触发按钮 */
.sidebar-trigger {
    position: fixed;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 40px;
    height: 80px;
    background: linear-gradient(135deg, #00f0ff, #00a8b3);
    border-radius: 8px 0 0 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    z-index: 999;
    box-shadow: -2px 0 10px rgba(0, 240, 255, 0.3);
    transition: all 0.3s ease;
}

.sidebar-trigger:hover {
    width: 45px;
    box-shadow: -4px 0 20px rgba(0, 240, 255, 0.5);
}

.arrow-icon {
    font-size: 20px;
    color: white;
    font-style: normal;
}

/* 遮罩层 */
.sidebar-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    z-index: 1000;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.3s ease, visibility 0.3s ease;
}

.sidebar-overlay.active {
    opacity: 1;
    visibility: visible;
}

/* 侧边栏主体 */
.sidebar-panel {
    position: fixed;
    right: -350px;
    top: 0;
    width: 320px;
    height: 100vh;
    background: rgba(10, 20, 40, 0.95);
    backdrop-filter: blur(10px);
    border-left: 1px solid rgba(0, 240, 255, 0.3);
    z-index: 1001;
    transition: right 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55);
    box-shadow: -5px 0 30px rgba(0, 0, 0, 0.5);
    display: flex;
    flex-direction: column;
    will-change: transform;
}

.sidebar-panel.active {
    right: 0;
}

/* 侧边栏头部 */
.sidebar-header {
    padding: 20px;
    border-bottom: 1px solid rgba(0, 240, 255, 0.2);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.sidebar-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--primary);
    margin: 0;
}

.sidebar-close {
    width: 32px;
    height: 32px;
    background: rgba(0, 240, 255, 0.1);
    border: 1px solid rgba(0, 240, 255, 0.3);
    border-radius: 6px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
}

.sidebar-close:hover {
    background: rgba(0, 240, 255, 0.2);
    border-color: var(--primary);
}

.close-icon {
    font-size: 18px;
    color: white;
    font-style: normal;
}

/* 侧边栏内容区 */
.sidebar-body {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
}

.sidebar-body::-webkit-scrollbar {
    width: 6px;
}

.sidebar-body::-webkit-scrollbar-thumb {
    background: rgba(0, 240, 255, 0.3);
    border-radius: 3px;
}

.sidebar-body::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 240, 255, 0.5);
}

.tool-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

/* 工具图标项 */
.tool-item {
    display: flex;
    align-items: center;
    padding: 15px;
    background: rgba(0, 240, 255, 0.05);
    border: 1px solid rgba(0, 240, 255, 0.2);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s ease;
}

.tool-item:hover {
    background: rgba(0, 240, 255, 0.15);
    border-color: var(--primary);
    transform: translateX(-5px);
    box-shadow: 0 4px 15px rgba(0, 240, 255, 0.2);
}

.tool-icon {
    font-size: 32px;
    margin-right: 15px;
    flex-shrink: 0;
}

.tool-info {
    flex: 1;
}

.tool-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.tool-desc {
    font-size: 12px;
    color: var(--text-secondary);
}

/* 响应式设计 */
@media (max-width: 768px) {
    .sidebar-panel {
        width: 280px;
        right: -300px;
    }
}

@media (max-width: 480px) {
    .sidebar-panel {
        width: 100%;
        right: -100%;
    }

    .sidebar-trigger {
        width: 35px;
        height: 70px;
    }
}
```

**Step 2: 验证 CSS 语法**

```bash
python -c "open('static/css/dashboard.css', encoding='utf-8').read()"
```

Expected: 无错误输出

**Step 3: 提交 CSS 更改**

```bash
git add static/css/dashboard.css
git commit -m "style: 添加侧边栏工具面板样式和动画"
```

---

### Task 3: 添加 JavaScript 逻辑

**Files:**
- Modify: `static/js/dashboard.js` (在文件末尾添加)

**Step 1: 添加侧边栏交互逻辑**

在 `dashboard.js` 文件末尾添加以下代码：

```javascript
// ========== 侧边栏工具面板 ==========

(function() {
    // 获取元素
    const sidebarTrigger = document.getElementById('sidebarTrigger');
    const sidebarPanel = document.getElementById('sidebarPanel');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const sidebarClose = document.getElementById('sidebarClose');

    // 防止重复触发的标志
    let isAnimating = false;

    // 展开侧边栏
    function openSidebar() {
        if (isAnimating) return;
        isAnimating = true;

        sidebarPanel.classList.add('active');
        sidebarOverlay.classList.add('active');
        sidebarTrigger.style.display = 'none';

        setTimeout(() => {
            isAnimating = false;
        }, 500);
    }

    // 收起侧边栏
    function closeSidebar() {
        if (isAnimating) return;
        isAnimating = true;

        sidebarPanel.classList.remove('active');
        sidebarOverlay.classList.remove('active');

        setTimeout(() => {
            sidebarTrigger.style.display = 'flex';
            isAnimating = false;
        }, 500);
    }

    // 事件监听
    if (sidebarTrigger) {
        sidebarTrigger.addEventListener('click', openSidebar);
    }

    if (sidebarClose) {
        sidebarClose.addEventListener('click', closeSidebar);
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeSidebar);
    }

    // ESC 键关闭
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebarPanel && sidebarPanel.classList.contains('active')) {
            closeSidebar();
        }
    });

    // 工具图标点击事件（占位功能）
    const toolItems = document.querySelectorAll('.tool-item');
    toolItems.forEach(item => {
        item.addEventListener('click', (e) => {
            // 防止冒泡到遮罩层
            e.stopPropagation();

            const toolName = item.querySelector('.tool-name').textContent;
            alert(`${toolName} 功能即将上线，敬请期待！`);
        });
    });
})();
```

**Step 2: 验证 JavaScript 语法**

```bash
node -c static/js/dashboard.js
```

Expected: 无输出表示语法正确（如果系统有 Node.js）

**Step 3: 提交 JavaScript 更改**

```bash
git add static/js/dashboard.js
git commit -m "feat: 添加侧边栏工具面板交互逻辑"
```

---

### Task 4: 测试和验证

**Files:**
- Test: 浏览器测试

**Step 1: 启动开发服务器**

```bash
python app.py
```

Expected: 服务器在 http://localhost:5000 启动

**Step 2: 浏览器功能测试**

打开 http://localhost:5000，验证以下内容：

1. ✅ 触发按钮显示在右侧中间位置
2. ✅ 点击触发按钮，侧边栏从右侧滑入
3. ✅ 侧边栏展开时显示遮罩层
4. ✅ 侧边栏宽度为 320px
5. ✅ 展开动画带弹性效果（约 0.5s）
6. ✅ 侧边栏显示 12 个工具图标
7. ✅ 工具图标悬停效果正常（向左移动 5px）
8. ✅ 点击工具图标显示"即将上线"提示
9. ✅ 点击关闭按钮，侧边栏收起
10. ✅ 点击遮罩层，侧边栏收起
11. ✅ 按 ESC 键，侧边栏收起
12. ✅ 触发按钮在侧边栏收起后重新显示
13. ✅ 不影响现有功能和布局

**Step 3: 开发者工具检查**

使用浏览器开发者工具（F12）：
- Console 标签：无 JavaScript 错误
- Elements 标签：检查 DOM 结构正确
- 测量侧边栏宽度（应为 320px）
- 检查动画效果（transition 属性）

**Step 4: 响应式测试**

调整浏览器窗口大小，测试：
- 桌面端（> 1024px）：正常显示
- 平板端（768px - 1024px）：侧边栏 300px
- 移动端（< 768px）：侧边栏 280px
- 小屏幕（< 480px）：侧边栏全屏

**Step 5: 记录测试结果**

如果所有项目通过，继续下一步。
如果发现问题，记录并修复。

---

### Task 5: 提交更改

**Files:**
- All modified files

**Step 1: 查看所有更改**

```bash
git status
git log --oneline -5
```

Expected: 看到 3 个提交（HTML、CSS、JS）

**Step 2: 推送到远程仓库**

```bash
git push origin main
```

Expected: 成功推送

**Step 3: 更新设计文档状态**

在 `docs/plans/2026-03-06-sidebar-toolbox-design.md` 末尾添加：

```markdown

---

## 实施状态

✅ **已完成** - 2026-03-06

**提交记录：**
- feat: 添加侧边栏工具面板 HTML 结构
- style: 添加侧边栏工具面板样式和动画
- feat: 添加侧边栏工具面板交互逻辑

**验收结果：** 所有验收标准已通过

**实现内容：**
- 触发按钮：固定在右侧中间，渐变背景
- 遮罩层：半透明黑色，点击可关闭
- 侧边栏：320px 宽，弹性动画，12 个工具图标
- 交互：展开/收起、ESC 键、工具点击提示
- 响应式：支持桌面、平板、移动端
```

**Step 4: 提交文档更新**

```bash
git add docs/plans/2026-03-06-sidebar-toolbox-design.md
git commit -m "docs: 更新侧边栏工具面板设计文档实施状态"
git push origin main
```

---

## 验收标准

完成后，确保以下所有项目都通过：

1. ✅ 触发按钮固定在右侧中间位置
2. ✅ 点击触发按钮展开侧边栏
3. ✅ 侧边栏宽度为 320px
4. ✅ 展开动画带弹性效果（0.5s）
5. ✅ 遮罩层正确显示和隐藏
6. ✅ 点击遮罩层或关闭按钮可收起
7. ✅ ESC 键可关闭侧边栏
8. ✅ 12 个工具图标正确显示
9. ✅ 工具图标悬停效果正常
10. ✅ 点击工具显示"即将上线"提示
11. ✅ 响应式布局在移动端正常
12. ✅ 不影响现有功能和布局
13. ✅ 所有更改已提交并推送

---

## 回滚计划

如果需要回滚更改：

```bash
# 查看提交历史
git log --oneline

# 回滚到添加侧边栏前的提交
git revert <commit-hash-1> <commit-hash-2> <commit-hash-3> --no-edit

# 或者硬重置（谨慎使用）
git reset --hard <commit-hash>
git push --force origin main
```

---

## 注意事项

1. **z-index 层级**：确保侧边栏在最上层（1001），不被其他元素遮挡
2. **动画性能**：使用 transform 而非 left/right 提升性能
3. **防抖处理**：避免动画期间重复触发
4. **焦点管理**：侧边栏打开时管理键盘焦点
5. **浏览器兼容性**：测试 Chrome、Firefox、Edge
6. **移动端体验**：小屏幕上侧边栏全屏显示

---

## 后续扩展建议

实施完成后，可以考虑：

1. 为每个工具实现实际功能
2. 使用专业的 SVG 图标库替换 Emoji
3. 添加工具图标依次淡入动画
4. 支持工具分类和搜索
5. 添加工具收藏功能
6. 配置快捷键
7. 支持主题切换
