# 仪表盘布局优化设计方案

**日期**: 2026-03-06
**目标**: 合并实时数据概览和新闻源文章分布，缩小占地，为最新获取文章腾出更多空间

---

## 需求概述

### 当前问题
左侧面板包含3个独立组件，空间分配不够优化：
1. 实时数据概览 - 4个统计指标
2. 新闻源文章分布 - 图表展示
3. 最新获取文章 - 文章列表

### 优化目标
- 合并"实时数据概览"和"新闻源文章分布"到一个卡片
- 精简统计指标，缩小占地面积
- 让"最新获取文章"占据左侧面板60-70%的空间

---

## 设计方案

### 方案选择
**采用方案A：紧凑统计条 + 小图表**

**理由**：
- 平衡空间优化和信息保留
- 图表虽小但仍可提供数据分布概览
- 实现难度适中
- 符合"缩小占地"而非"完全移除"的需求

---

## 组件结构

### 变更前（3个独立卡片）
1. 实时数据概览 (`data-layout-id="stats-overview"`)
2. 新闻源文章分布 (`data-layout-id="source-chart"`)
3. 最新获取文章 (`data-layout-id="latest-articles"`)

### 变更后（2个卡片）
1. **数据概览与分布**（新卡片）
   - `data-layout-id="stats-and-chart"`
   - 包含：2个统计指标 + 新闻源分布图表
   - 固定高度约280-300px
2. **最新获取文章**（保持独立）
   - `data-layout-id="latest-articles"`
   - `flex: 1` 自适应剩余空间

### 保留的统计指标
- **今日新增**（主要指标）
- **文章总数**（次要指标）

### 移除的指标
- 本周新增
- 监控源

---

## 布局设计

### 合并卡片内部布局

```
┌─────────────────────────────────────┐
│ 数据概览与分布                        │
├─────────────────────────────────────┤
│ ┌──────────┐  ┌──────────┐          │ ← 统计区（高度约60px）
│ │ 今日新增  │  │ 文章总数  │          │   横向排列，紧凑样式
│ │   123    │  │  45678   │          │
│ └──────────┘  └──────────┘          │
├─────────────────────────────────────┤
│                                     │
│        新闻源分布图表                 │ ← 图表区（高度约220px）
│         (饼图/柱状图)                │   缩小但保持可读性
│                                     │
└─────────────────────────────────────┘
总高度：约280-300px
```

### 空间分配

**左侧面板（panel-left）垂直空间分配**：
- 合并卡片：固定高度 280-300px（约30%）
- 间距：15px
- 最新获取文章：`flex: 1`（约70%，自适应剩余空间）

---

## 技术实现

### HTML 结构

```html
<section class="card stats-chart-card" data-layout-id="stats-and-chart">
    <div class="card-header">
        <span class="card-title">数据概览与分布</span>
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

### CSS 样式调整

#### 1. 合并卡片样式
```css
.stats-chart-card {
    height: 290px;
    display: flex;
    flex-direction: column;
}

.stats-chart-card .card-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
}
```

#### 2. 紧凑统计区样式
```css
.stats-compact {
    display: flex;
    gap: 10px;
    padding: 10px 0;
}

.stat-item-compact {
    flex: 1;
    text-align: center;
    padding: 8px;
    background: rgba(0, 240, 255, 0.05);
    border-radius: 6px;
    border: 1px solid rgba(0, 240, 255, 0.1);
}

.stat-value-compact {
    font-size: 24px;
    font-weight: 700;
    color: var(--primary);
    font-family: 'Consolas', 'Monaco', monospace;
    text-shadow: 0 0 15px rgba(0, 240, 255, 0.5);
}

.stat-label-compact {
    font-size: 11px;
    color: var(--text-secondary);
    margin-top: 4px;
}
```

#### 3. 紧凑图表容器
```css
.chart-container-compact {
    height: 220px;
    width: 100%;
}
```

### JavaScript 调整

#### 1. 统计数据渲染（dashboard.js）
- 只更新 `todayCount` 和 `totalArticles` 两个元素
- 移除 `weekCount` 和 `activeSources` 的更新逻辑

#### 2. 图表配置调整
```javascript
// ECharts 配置优化
{
    grid: {
        top: 30,
        bottom: 20,
        left: 30,
        right: 30
    },
    legend: {
        top: 5,
        right: 10,
        textStyle: {
            fontSize: 10
        }
    },
    // 字体缩小
    textStyle: {
        fontSize: 10
    }
}
```

---

## 文件修改清单

### 1. templates/index.html
- 删除原 `stats-overview` section
- 删除原 `source-chart` section
- 新增合并后的 `stats-and-chart` section
- 保持 `latest-articles` section 不变

### 2. static/css/dashboard.css
- 新增 `.stats-chart-card` 样式
- 新增 `.stats-compact` 相关样式
- 新增 `.chart-container-compact` 样式
- 可选：调整响应式断点

### 3. static/js/dashboard.js
- 修改 `updateStats()` 函数，只更新2个指标
- 修改 `initSourceChart()` 函数，调整图表配置
- 更新图表容器选择器（如果ID有变化）

---

## 数据流

### API 端点
- **无需修改**，继续使用现有的 `/api/stats/overview` 和 `/api/stats/sources` 端点

### 前端逻辑
- 从 API 获取完整数据
- 前端选择性渲染需要的字段
- 图表数据处理逻辑保持不变

---

## 优势与权衡

### 优势
1. **空间优化**：最新获取文章从约33%提升到70%空间
2. **信息保留**：核心统计数据和分布图表都保留
3. **视觉简洁**：减少卡片数量，界面更清爽
4. **实现简单**：主要是布局调整，逻辑改动最小

### 权衡
1. 图表尺寸缩小，细节可能不如原来清晰
2. 移除了"本周新增"和"监控源"两个指标
3. 需要测试不同屏幕尺寸下的显示效果

---

## 后续优化建议

1. **响应式优化**：在小屏幕上可能需要调整布局
2. **图表交互**：考虑添加点击放大功能
3. **数据密度**：如果图表过小，可考虑添加悬浮提示增强可读性

---

## 验收标准

1. ✅ 左侧面板只有2个卡片
2. ✅ 合并卡片高度约280-300px
3. ✅ 只显示"今日新增"和"文章总数"两个统计指标
4. ✅ 新闻源分布图表正常显示且可交互
5. ✅ 最新获取文章占据约70%的垂直空间
6. ✅ 所有数据正常更新
7. ✅ 响应式布局正常工作
