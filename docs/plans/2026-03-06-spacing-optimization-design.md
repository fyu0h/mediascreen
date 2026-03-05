# 合并卡片间距优化设计方案

**日期**: 2026-03-06
**目标**: 缩小合并卡片（数据概览与分布）的内部间距，减少留白

---

## 需求概述

### 当前问题
合并卡片内部存在较多留白：
- 卡片内部 padding 为 15px
- 统计区和图表之间 gap 为 10px
- 统计项内部 padding 为 8px

### 优化目标
轻微缩小间距，使布局更紧凑：
- 卡片内部 padding: 15px → 12px
- 统计区和图表之间 gap: 10px → 8px
- 统计项内部 padding: 8px → 7px

---

## 设计方案

### 方案选择
**采用方案A：只调整合并卡片的间距**

**理由**：
- 针对性强，只优化合并卡片
- 不影响其他卡片的布局
- 改动最小，风险低
- 符合轻微缩小的需求

---

## 技术实现

### CSS 修改

**文件**: `static/css/dashboard.css`

#### 1. 卡片内部间距（第309-314行）

**修改前：**
```css
.stats-chart-card .card-body {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 15px;
}
```

**修改后：**
```css
.stats-chart-card .card-body {
    display: flex;
    flex-direction: column;
    gap: 8px;           /* 减少 2px */
    padding: 12px;      /* 减少 3px */
}
```

#### 2. 统计项内部间距（第323-331行）

**修改前：**
```css
.stat-item-compact {
    flex: 1;
    text-align: center;
    padding: 8px;
    background: rgba(0, 240, 255, 0.05);
    border-radius: 6px;
    border: 1px solid rgba(0, 240, 255, 0.1);
    transition: all 0.3s ease;
}
```

**修改后：**
```css
.stat-item-compact {
    flex: 1;
    text-align: center;
    padding: 7px;       /* 减少 1px */
    background: rgba(0, 240, 255, 0.05);
    border-radius: 6px;
    border: 1px solid rgba(0, 240, 255, 0.1);
    transition: all 0.3s ease;
}
```

---

## 实施步骤

### 1. 修改 CSS 文件
- 找到 `.stats-chart-card .card-body` 样式
- 修改 `padding: 15px` → `padding: 12px`
- 修改 `gap: 10px` → `gap: 8px`
- 找到 `.stat-item-compact` 样式
- 修改 `padding: 8px` → `padding: 7px`

### 2. 浏览器测试
- 刷新页面查看效果
- 检查统计数据和图表之间的间距
- 确认整体视觉效果
- 验证图表显示正常

### 3. 提交更改
```bash
git add static/css/dashboard.css
git commit -m "style: 缩小合并卡片的内部间距"
git push origin main
```

---

## 预期效果

### 间距变化
- 卡片内部 padding: 15px → 12px（减少 20%）
- 统计区和图表 gap: 10px → 8px（减少 20%）
- 统计项 padding: 8px → 7px（减少 12.5%）

### 视觉效果
- 合并卡片整体更紧凑
- 统计数据和图表之间的留白减少
- 图表区域获得更多显示空间（约增加 5px）
- 视觉上更加协调

---

## 影响范围

### 影响的组件
- ✅ 合并卡片（数据概览与分布）

### 不影响的组件
- ❌ 其他卡片（最新获取文章、地图等）
- ❌ 响应式布局
- ❌ 其他页面

---

## 验收标准

完成后，确保以下所有项目都通过：

1. ✅ 卡片内部 padding 为 12px
2. ✅ 统计区和图表之间 gap 为 8px
3. ✅ 统计项 padding 为 7px
4. ✅ 图表显示正常，无布局错乱
5. ✅ 统计数据显示正常
6. ✅ 整体布局更紧凑
7. ✅ 不影响其他卡片
8. ✅ 响应式布局正常工作

---

## 回滚计划

如果需要回滚更改：

```bash
# 查看提交历史
git log --oneline

# 回滚到修改前的提交
git revert <commit-hash> --no-edit

# 或者手动恢复原值
# padding: 12px → 15px
# gap: 8px → 10px
# padding: 7px → 8px
```

---

## 注意事项

1. **视觉平衡**：间距缩小后需要确认视觉效果是否协调
2. **图表可读性**：确保图表有足够的显示空间
3. **统计数据可读性**：确认统计项不会显得过于拥挤
4. **浏览器兼容性**：在主流浏览器中测试效果

---

## 后续优化建议

如果需要进一步优化：

1. 考虑调整统计项之间的 gap（当前 10px）
2. 考虑调整统计数据的字体大小
3. 考虑在小屏幕上进一步缩小间距
4. 考虑统一调整其他卡片的间距
