# 合并卡片间距优化实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 缩小合并卡片的内部间距，减少留白，使布局更紧凑

**Architecture:** 通过修改 CSS 样式文件中的 padding 和 gap 属性，轻微缩小合并卡片的内部间距。只调整 `.stats-chart-card .card-body` 和 `.stat-item-compact` 两个样式类，不影响其他组件。

**Tech Stack:** CSS3

---

## 任务概览

1. **Task 1**: 修改 CSS 样式 - 缩小间距
2. **Task 2**: 浏览器测试验证
3. **Task 3**: 提交更改

---

### Task 1: 修改 CSS 样式

**Files:**
- Modify: `static/css/dashboard.css:309-314` (卡片内部间距)
- Modify: `static/css/dashboard.css:323-331` (统计项间距)

**Step 1: 备份当前状态**

```bash
git status
git diff static/css/dashboard.css
```

Expected: 查看当前未提交的更改

**Step 2: 修改卡片内部间距**

在 `static/css/dashboard.css` 中，找到第309-314行的 `.stats-chart-card .card-body` 样式：

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
    gap: 8px;           /* 从 10px 改为 8px */
    padding: 12px;      /* 从 15px 改为 12px */
}
```

**Step 3: 修改统计项内部间距**

在同一文件中，找到第323-331行的 `.stat-item-compact` 样式：

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
    padding: 7px;       /* 从 8px 改为 7px */
    background: rgba(0, 240, 255, 0.05);
    border-radius: 6px;
    border: 1px solid rgba(0, 240, 255, 0.1);
    transition: all 0.3s ease;
}
```

**Step 4: 验证 CSS 语法**

```bash
# 检查文件是否能正常读取
python -c "open('static/css/dashboard.css', encoding='utf-8').read()"
```

Expected: 无错误输出

**Step 5: 提交 CSS 更改**

```bash
git add static/css/dashboard.css
git commit -m "style: 缩小合并卡片的内部间距"
```

---

### Task 2: 浏览器测试验证

**Files:**
- Test: 浏览器测试

**Step 1: 启动开发服务器**

```bash
python app.py
```

Expected: 服务器在 http://localhost:5000 启动

**Step 2: 浏览器视觉检查**

打开 http://localhost:5000，验证以下内容：

1. ✅ 合并卡片内部间距明显缩小
2. ✅ 统计数据和图表之间的间距减少
3. ✅ 统计项内部间距缩小但不拥挤
4. ✅ 图表显示正常，无布局错乱
5. ✅ 统计数据显示正常，文字清晰
6. ✅ 整体视觉效果更紧凑协调
7. ✅ 其他卡片不受影响
8. ✅ 响应式布局正常

**Step 3: 开发者工具测量**

使用浏览器开发者工具（F12）：
- Elements 标签：选中 `.stats-chart-card .card-body`
- 查看 Computed 样式
- 确认 padding 为 12px
- 确认 gap 为 8px
- 选中 `.stat-item-compact`
- 确认 padding 为 7px

**Step 4: 记录测试结果**

如果所有项目通过，继续下一步。
如果发现问题，记录并调整 CSS 值。

---

### Task 3: 提交更改

**Files:**
- All modified files

**Step 1: 查看所有更改**

```bash
git status
git log --oneline -3
```

Expected: 看到1个提交（CSS 修改）

**Step 2: 推送到远程仓库**

```bash
git push origin main
```

Expected: 成功推送

**Step 3: 更新设计文档状态**

在 `docs/plans/2026-03-06-spacing-optimization-design.md` 末尾添加：

```markdown

---

## 实施状态

✅ **已完成** - 2026-03-06

**提交记录：**
- style: 缩小合并卡片的内部间距

**验收结果：** 所有验收标准已通过

**修改内容：**
- `.stats-chart-card .card-body` padding: 15px → 12px
- `.stats-chart-card .card-body` gap: 10px → 8px
- `.stat-item-compact` padding: 8px → 7px
```

**Step 4: 提交文档更新**

```bash
git add docs/plans/2026-03-06-spacing-optimization-design.md
git commit -m "docs: 更新间距优化设计文档实施状态"
git push origin main
```

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
9. ✅ 所有更改已提交并推送

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

git push origin main
```

---

## 注意事项

1. **视觉平衡**：间距缩小后需要确认视觉效果是否协调
2. **图表可读性**：确保图表有足够的显示空间
3. **统计数据可读性**：确认统计项不会显得过于拥挤
4. **浏览器缓存**：测试时使用硬刷新（Ctrl+Shift+R）清除缓存
5. **多浏览器测试**：在 Chrome、Firefox、Edge 中测试

---

## 后续优化建议

如果需要进一步优化：

1. 调整统计项之间的 gap（当前 10px）
2. 调整统计数据的字体大小
3. 在小屏幕上进一步缩小间距
4. 统一调整其他卡片的间距
