# 仪表盘布局优化实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 合并实时数据概览和新闻源文章分布到一个紧凑卡片，为最新获取文章腾出70%的左侧面板空间

**Architecture:** 将两个独立的 section 元素合并为一个，使用 flexbox 垂直布局，顶部显示2个紧凑统计指标，底部显示缩小的图表。通过 CSS 固定合并卡片高度为290px，让文章列表使用 flex:1 占据剩余空间。

**Tech Stack:** HTML5, CSS3 (Flexbox), JavaScript (原生), ECharts 5.4.3

---

## 任务概览

1. **Task 1**: 修改 HTML 结构 - 合并两个 section
2. **Task 2**: 添加 CSS 样式 - 紧凑布局样式
3. **Task 3**: 更新 JavaScript - 调整统计数据和图表逻辑
4. **Task 4**: 测试和验证
5. **Task 5**: 最终提交

---

### Task 1: 修改 HTML 结构

**Files:**
- Modify: `templates/index.html:41-77`

**Step 1: 备份当前状态**

```bash
git status
git diff templates/index.html
```

Expected: 查看当前未提交的更改

**Step 2: 删除旧的两个 section，添加新的合并 section**

在 `templates/index.html` 中，找到第41-77行（实时统计 + 新闻源分布），替换为：

```html
            <!-- 数据概览与分布 -->
            <section class="card stats-chart-card" data-layout-id="stats-and-chart">
                <div class="card-header">
                    <span class="card-title">数据概览与分布</span>
                    <span class="refresh-indicator" id="refreshIndicator"></span>
                </div>
                <div class="card-body">
                    <!-- 紧凑统计区 -->
                    <div class="stats-compact">
                        <div class="stat-item-compact">
                            <div class="stat-value-compact" id="todayCount">--</div>
                            <div class="stat-label-compact">今日新增</div>
                        </div>
                        <div class="stat-item-compact">
                            <div class="stat-value-compact" id="totalArticles">--</div>
                            <div class="stat-label-compact">文章总数</div>
                        </div>
                    </div>
                    <!-- 图表区 -->
                    <div id="sourceChart" class="chart-container-compact"></div>
                </div>
            </section>
```

**注意事项：**
- 保留 `refresh-indicator`，它用于显示刷新状态
- 保留 `id="todayCount"` 和 `id="totalArticles"`，JavaScript 会更新这些元素
- 保留 `id="sourceChart"`，ECharts 会在这个容器中渲染图表
- 移除 `id="weekCount"` 和 `id="activeSources"`（不再需要）

**Step 3: 验证 HTML 语法**

```bash
# 检查文件是否有语法错误
python -c "from html.parser import HTMLParser; HTMLParser().feed(open('templates/index.html', encoding='utf-8').read())"
```

Expected: 无输出表示语法正确

**Step 4: 提交 HTML 结构更改**

```bash
git add templates/index.html
git commit -m "refactor: 合并实时数据概览和新闻源分布到一个卡片"
```

---

### Task 2: 添加 CSS 样式

**Files:**
- Modify: `static/css/dashboard.css` (在合适位置添加新样式)

**Step 1: 找到插入位置**

在 `dashboard.css` 中找到 `.stats-grid` 样式定义后（约252行），在其后添加新样式。

**Step 2: 添加合并卡片样式**

在 `.stats-grid` 相关样式后添加：

```css
/* ========== 合并卡片：数据概览与分布 ========== */
.stats-chart-card {
    height: 290px;
    display: flex;
    flex-direction: column;
}

.stats-chart-card .card-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 15px;
}

/* 紧凑统计区 */
.stats-compact {
    display: flex;
    gap: 10px;
    padding: 0;
}

.stat-item-compact {
    flex: 1;
    text-align: center;
    padding: 8px;
    background: rgba(0, 240, 255, 0.05);
    border-radius: 6px;
    border: 1px solid rgba(0, 240, 255, 0.1);
    transition: all 0.3s ease;
}

.stat-item-compact:hover {
    background: rgba(0, 240, 255, 0.1);
    border-color: var(--primary);
    transform: translateY(-2px);
}

.stat-value-compact {
    font-size: 24px;
    font-weight: 700;
    color: var(--primary);
    font-family: 'Consolas', 'Monaco', monospace;
    text-shadow: 0 0 15px rgba(0, 240, 255, 0.5);
    line-height: 1.2;
}

.stat-label-compact {
    font-size: 11px;
    color: var(--text-secondary);
    margin-top: 4px;
}

/* 紧凑图表容器 */
.chart-container-compact {
    flex: 1;
    min-height: 200px;
    width: 100%;
}
```

**Step 3: 验证 CSS 语法**

```bash
# 使用浏览器开发者工具或在线工具验证 CSS
# 或者简单检查文件是否能正常读取
python -c "open('static/css/dashboard.css', encoding='utf-8').read()"
```

Expected: 无错误输出

**Step 4: 提交 CSS 更改**

```bash
git add static/css/dashboard.css
git commit -m "style: 添加合并卡片的紧凑布局样式"
```

---

### Task 3: 更新 JavaScript 逻辑

**Files:**
- Modify: `static/js/dashboard.js`

**Step 1: 找到 updateStats 函数**

搜索 `function updateStats` 或 `updateStats =`，找到统计数据更新函数。

**Step 2: 修改 updateStats 函数**

找到更新 `weekCount` 和 `activeSources` 的代码行，注释掉或删除：

```javascript
// 原代码可能类似：
// document.getElementById('weekCount').textContent = data.week_count || 0;
// document.getElementById('activeSources').textContent = data.active_sources || 0;

// 修改为只更新两个指标：
function updateStats(data) {
    // 更新今日新增
    const todayCountEl = document.getElementById('todayCount');
    if (todayCountEl) {
        todayCountEl.textContent = (data.today_count || 0).toLocaleString();
    }

    // 更新文章总数
    const totalArticlesEl = document.getElementById('totalArticles');
    if (totalArticlesEl) {
        totalArticlesEl.textContent = (data.total_articles || 0).toLocaleString();
    }

    // 移除或注释掉本周新增和监控源的更新
    // const weekCountEl = document.getElementById('weekCount');
    // const activeSourcesEl = document.getElementById('activeSources');
    // ...
}
```

**注意：** 具体代码取决于现有实现，需要查看实际的 `dashboard.js` 文件。

**Step 3: 找到 initSourceChart 函数**

搜索 `initSourceChart` 或图表初始化相关代码。

**Step 4: 调整图表配置**

修改 ECharts 配置，缩小字体和调整布局：

```javascript
function initSourceChart() {
    const chartDom = document.getElementById('sourceChart');
    if (!chartDom) return;

    const myChart = echarts.init(chartDom);

    // ... 数据获取逻辑 ...

    const option = {
        // 缩小字体
        textStyle: {
            fontSize: 10
        },
        tooltip: {
            trigger: 'item',
            textStyle: {
                fontSize: 12
            }
        },
        legend: {
            top: 5,
            right: 10,
            textStyle: {
                fontSize: 10
            },
            itemWidth: 12,
            itemHeight: 12
        },
        grid: {
            top: 30,
            bottom: 20,
            left: 30,
            right: 30
        },
        // ... 其他配置保持不变 ...
    };

    myChart.setOption(option);

    // 响应式调整
    window.addEventListener('resize', () => {
        myChart.resize();
    });
}
```

**Step 5: 测试 JavaScript 语法**

```bash
# 检查 JavaScript 语法
node -c static/js/dashboard.js
```

Expected: 无输出表示语法正确（如果系统有 Node.js）

**Step 6: 提交 JavaScript 更改**

```bash
git add static/js/dashboard.js
git commit -m "refactor: 调整统计数据和图表逻辑以适配合并卡片"
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

**Step 2: 浏览器测试清单**

打开 http://localhost:5000，验证以下内容：

1. ✅ 左侧面板只有2个卡片（合并卡片 + 最新获取文章）
2. ✅ 合并卡片标题显示"数据概览与分布"
3. ✅ 合并卡片顶部显示2个统计指标（今日新增、文章总数）
4. ✅ 统计数据正确显示（不是 "--"）
5. ✅ 合并卡片底部显示新闻源分布图表
6. ✅ 图表可以正常交互（悬停显示提示）
7. ✅ 合并卡片高度约290px（使用开发者工具测量）
8. ✅ 最新获取文章占据大部分空间（约70%）
9. ✅ 刷新指示器正常工作
10. ✅ 响应式布局正常（缩小窗口测试）

**Step 3: 浏览器控制台检查**

打开浏览器开发者工具（F12），检查：
- Console 标签：无 JavaScript 错误
- Network 标签：API 请求正常（/api/stats/overview, /api/stats/sources）
- Elements 标签：检查 DOM 结构是否正确

**Step 4: 记录测试结果**

如果发现问题，记录下来并修复。常见问题：
- 图表不显示：检查 `sourceChart` ID 是否正确
- 统计数据不更新：检查 API 响应和 JavaScript 逻辑
- 样式不正确：检查 CSS 类名是否匹配

---

### Task 5: 最终提交和清理

**Files:**
- All modified files

**Step 1: 查看所有更改**

```bash
git status
git log --oneline -5
```

Expected: 看到3个提交（HTML、CSS、JS）

**Step 2: 运行最终检查**

```bash
# 确保没有未提交的更改
git status
```

Expected: `nothing to commit, working tree clean`

**Step 3: 推送到远程仓库**

```bash
git push origin main
```

Expected: 成功推送

**Step 4: 更新设计文档状态**

在 `docs/plans/2026-03-06-dashboard-layout-optimization-design.md` 末尾添加：

```markdown

---

## 实施状态

✅ **已完成** - 2026-03-06

**提交记录：**
- refactor: 合并实时数据概览和新闻源分布到一个卡片
- style: 添加合并卡片的紧凑布局样式
- refactor: 调整统计数据和图表逻辑以适配合并卡片

**验收结果：** 所有验收标准已通过
```

**Step 5: 提交文档更新**

```bash
git add docs/plans/2026-03-06-dashboard-layout-optimization-design.md
git commit -m "docs: 更新设计文档实施状态"
git push origin main
```

---

## 验收标准

完成后，确保以下所有项目都通过：

1. ✅ 左侧面板只有2个卡片
2. ✅ 合并卡片高度约280-300px
3. ✅ 只显示"今日新增"和"文章总数"两个统计指标
4. ✅ 新闻源分布图表正常显示且可交互
5. ✅ 最新获取文章占据约70%的垂直空间
6. ✅ 所有数据正常更新
7. ✅ 响应式布局正常工作
8. ✅ 无 JavaScript 控制台错误
9. ✅ 所有更改已提交并推送

---

## 回滚计划

如果需要回滚更改：

```bash
# 查看提交历史
git log --oneline

# 回滚到合并前的提交
git revert <commit-hash> --no-edit

# 或者硬重置（谨慎使用）
git reset --hard <commit-hash>
git push --force origin main
```

---

## 注意事项

1. **数据兼容性**：API 端点无需修改，前端只是选择性渲染数据
2. **布局持久化**：如果系统有布局保存功能，可能需要清除旧的布局配置
3. **浏览器缓存**：测试时使用硬刷新（Ctrl+Shift+R）清除缓存
4. **响应式测试**：在不同屏幕尺寸下测试（桌面、平板、手机）
5. **性能**：图表缩小后渲染性能应该更好

---

## 后续优化建议

实施完成后，可以考虑：

1. 添加图表点击放大功能
2. 优化移动端响应式布局
3. 添加统计数据的趋势指示器（上升/下降箭头）
4. 考虑添加图表类型切换（饼图/柱状图）
