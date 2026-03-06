# 删除成果展示功能 - 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 完全移除成果展示功能，包括后端模型、API 路由、前端界面、数据文件和相关文档

**架构：** 成果展示是独立功能模块，使用 JSON 文件存储数据，无数据库依赖，无其他模块依赖。删除操作包括：删除完整的后端模型文件、从 API 路由中移除 6 个端点、从前端移除卡片 UI 和相关 JS/CSS、清理数据文件和上传目录。

**技术栈：** Python/Flask (后端)、原生 HTML/CSS/JS (前端)、文件系统操作

---

## Task 1: 删除后端模型文件

**文件：**
- Delete: `models/achievements.py`

**Step 1: 删除模型文件**

```bash
rm models/achievements.py
```

**Step 2: 验证文件已删除**

```bash
ls models/achievements.py
```

预期输出：`No such file or directory`

**Step 3: 提交更改**

```bash
git add models/achievements.py
git commit -m "refactor: 删除成果展示模型文件"
```

---

## Task 2: 从 API 路由中删除导入语句

**文件：**
- Modify: `routes/api.py:2182-2191`

**Step 1: 读取文件确认导入位置**

使用 Read 工具读取 `routes/api.py` 第 2180-2195 行，确认导入语句的准确位置。

**Step 2: 删除导入语句**

删除以下代码块（第 2182-2191 行）：

```python
from models.achievements import (
    get_all_achievements,
    add_achievement,
    update_achievement,
    delete_achievement,
    fetch_page_title,
    save_uploaded_image,
    delete_image
)
```

使用 Edit 工具删除这 10 行代码。

**Step 3: 验证语法**

```bash
python -m py_compile routes/api.py
```

预期：无输出表示语法正确

**Step 4: 提交更改**

```bash
git add routes/api.py
git commit -m "refactor: 从 API 路由中删除成果展示导入"
```

---

## Task 3: 删除成果列表 API 端点

**文件：**
- Modify: `routes/api.py:2194-2203`

**Step 1: 读取并确认端点代码**

使用 Read 工具读取 `routes/api.py` 第 2194-2203 行。

**Step 2: 删除 GET /api/achievements 端点**

删除以下代码块：

```python
@api_bp.route('/achievements', methods=['GET'])
def achievements_list():
    """获取成果列表"""
    try:
        data = get_all_achievements()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Step 3: 验证语法**

```bash
python -m py_compile routes/api.py
```

**Step 4: 提交更改**

```bash
git add routes/api.py
git commit -m "refactor: 删除成果列表 API 端点"
```

---

## Task 4: 删除添加成果 API 端点

**文件：**
- Modify: `routes/api.py:2205-2277`

**Step 1: 读取并确认端点代码**

使用 Read 工具读取 `routes/api.py` 第 2205-2277 行（约 73 行代码，包含图片上传逻辑）。

**Step 2: 删除 POST /api/achievements 端点**

删除整个函数定义，包括：
- 路由装饰器 `@api_bp.route('/achievements', methods=['POST'])`
- 函数定义 `def achievements_add():`
- 所有函数体代码（表单数据处理、图片上传、调用 add_achievement 等）

**Step 3: 验证语法**

```bash
python -m py_compile routes/api.py
```

**Step 4: 提交更改**

```bash
git add routes/api.py
git commit -m "refactor: 删除添加成果 API 端点"
```

---

## Task 5: 删除更新成果 API 端点

**文件：**
- Modify: `routes/api.py:2279-2317`

**Step 1: 读取并确认端点代码**

使用 Read 工具读取 `routes/api.py` 第 2279-2317 行。

**Step 2: 删除 PUT /api/achievements/<id> 端点**

删除整个函数定义：

```python
@api_bp.route('/achievements/<achievement_id>', methods=['PUT'])
def achievements_update(achievement_id: str):
    # ... 函数体 ...
```

**Step 3: 验证语法**

```bash
python -m py_compile routes/api.py
```

**Step 4: 提交更改**

```bash
git add routes/api.py
git commit -m "refactor: 删除更新成果 API 端点"
```

---

## Task 6: 删除删除成果 API 端点

**文件：**
- Modify: `routes/api.py:2319-2335`

**Step 1: 读取并确认端点代码**

使用 Read 工具读取 `routes/api.py` 第 2319-2335 行。

**Step 2: 删除 DELETE /api/achievements/<id> 端点**

删除整个函数定义：

```python
@api_bp.route('/achievements/<achievement_id>', methods=['DELETE'])
def achievements_delete(achievement_id: str):
    # ... 函数体 ...
```

**Step 3: 验证语法**

```bash
python -m py_compile routes/api.py
```

**Step 4: 提交更改**

```bash
git add routes/api.py
git commit -m "refactor: 删除删除成果 API 端点"
```

---

## Task 7: 删除抓取标题 API 端点

**文件：**
- Modify: `routes/api.py:2337-2354`

**Step 1: 读取并确认端点代码**

使用 Read 工具读取 `routes/api.py` 第 2337-2354 行。

**Step 2: 删除 POST /api/achievements/fetch-title 端点**

删除整个函数定义：

```python
@api_bp.route('/achievements/fetch-title', methods=['POST'])
def achievements_fetch_title():
    # ... 函数体 ...
```

**Step 3: 验证语法**

```bash
python -m py_compile routes/api.py
```

**Step 4: 提交更改**

```bash
git add routes/api.py
git commit -m "refactor: 删除抓取标题 API 端点"
```

---

## Task 8: 从前端 HTML 中删除成果展示卡片

**文件：**
- Modify: `templates/index.html:95-112`

**Step 1: 读取并确认 HTML 结构**

使用 Read 工具读取 `templates/index.html` 第 95-112 行。

**Step 2: 删除成果展示卡片**

删除以下完整的 HTML 区块（第 95-112 行）：

```html
<!-- 成果展示 -->
<div class="card achievements-card achievements-card-compact" data-layout-id="achievements">
    <div class="card-header">
        <span class="card-title">成果展示</span>
        <button class="btn-manage" onclick="openAchievementModal()" title="添加成果">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="16"></line>
                <line x1="8" y1="12" x2="16" y2="12"></line>
            </svg>
        </button>
    </div>
    <div class="card-body achievements-body">
        <div class="achievements-list" id="achievementsList">
            <div class="loading-text">加载中...</div>
        </div>
    </div>
</div>
```

**Step 3: 验证 HTML 语法**

在浏览器中打开页面，检查开发者工具控制台是否有 HTML 解析错误。

**Step 4: 提交更改**

```bash
git add templates/index.html
git commit -m "refactor: 从前端删除成果展示卡片"
```

---

## Task 9: 从前端 HTML 中删除成果弹窗

**文件：**
- Modify: `templates/index.html:1072-1127`

**Step 1: 读取并确认弹窗 HTML**

使用 Read 工具读取 `templates/index.html` 第 1072-1127 行。

**Step 2: 删除成果弹窗**

删除整个弹窗 HTML 结构（第 1072-1127 行），包括：
- `<div class="modal-overlay" id="achievementModal">` 及其所有子元素
- 表单输入字段、图片上传区域、按钮等

**Step 3: 提交更改**

```bash
git add templates/index.html
git commit -m "refactor: 从前端删除成果弹窗"
```

---

## Task 10: 从 JavaScript 中删除成果展示功能

**文件：**
- Modify: `static/js/dashboard.js:4486-4798`

**Step 1: 读取并确认 JS 代码范围**

使用 Read 工具读取 `static/js/dashboard.js` 第 4486-4798 行。

**Step 2: 删除成果展示 JS 代码块**

删除以下完整代码块（第 4486-4798 行，约 313 行）：

```javascript
// ==================== 成果展示功能 ====================

let achievementsData = [];
let editingAchievementId = null;
let selectedImageFile = null;

// 加载成果列表
async function loadAchievements() { ... }

// 渲染成果列表
function renderAchievements() { ... }

// 打开成果链接
function openAchievementLink(url) { ... }

// 打开添加成果弹窗
function openAchievementModal() { ... }

// 编辑成果
function editAchievement(id) { ... }

// 关闭成果弹窗
function closeAchievementModal() { ... }

// 触发图片上传
function triggerImageUpload() { ... }

// 预览上传的图片
function previewAchievementImage(input) { ... }

// 移除图片
function removeAchievementImage(event) { ... }

// 抓取标题
async function fetchAchievementTitle() { ... }

// 保存成果
async function saveAchievement() { ... }

// 删除成果
async function deleteAchievement(id) { ... }
```

**Step 3: 从初始化函数中移除 loadAchievements 调用**

在 `static/js/dashboard.js` 中搜索 `loadAchievements()` 调用（约在第 1372 行），删除该行：

```javascript
// 删除这一行
loadAchievements(),
```

**Step 4: 从 ESC 键处理中移除 closeAchievementModal**

在 `static/js/dashboard.js` 中搜索 `closeAchievementModal()` 调用（约在第 1467 行），删除该行：

```javascript
// 删除这一行
closeAchievementModal();
```

**Step 5: 验证 JS 语法**

在浏览器开发者工具中检查是否有 JavaScript 语法错误。

**Step 6: 提交更改**

```bash
git add static/js/dashboard.js
git commit -m "refactor: 从 JS 中删除成果展示功能"
```

---

## Task 11: 从 CSS 中删除成果展示样式

**文件：**
- Modify: `static/css/dashboard.css`

**Step 1: 搜索并定位成果展示样式**

使用 Grep 工具搜索 `achievement` 关键词，确认所有相关样式的行号。

**Step 2: 删除成果展示样式定义**

删除以下 CSS 类定义（根据 grep 结果，约在第 4134-4299 行和第 8429-9016 行）：

```css
.achievements-card { ... }
.achievements-card-compact { ... }
.achievements-card .card-header { ... }
.achievements-card .card-title { ... }
.achievements-card .card-title::before { ... }
.achievements-body { ... }
.achievements-list { ... }
.achievements-list::-webkit-scrollbar { ... }
.achievements-list::-webkit-scrollbar-track { ... }
.achievements-list::-webkit-scrollbar-thumb { ... }
.achievement-item { ... }
.achievement-item:hover { ... }
.achievement-image { ... }
.achievement-image img { ... }
.achievement-image .placeholder-icon { ... }
.achievement-info { ... }
.achievement-title { ... }
.achievement-date { ... }
.achievement-actions { ... }
.achievement-item:hover .achievement-actions { ... }
.achievement-actions .btn-icon-sm { ... }
.achievement-actions .btn-icon-sm:hover { ... }
.achievement-actions .btn-icon-sm.delete:hover { ... }
.achievements-empty { ... }
.achievements-empty svg { ... }
.achievements-empty span { ... }
```

**Step 3: 删除布局相关样式**

删除 `[data-layout-id="achievements"]` 相关的 order 定义（约在第 8429 行）：

```css
[data-layout-id="achievements"] { order: 9; }
```

**Step 4: 删除响应式样式**

删除媒体查询中的成果展示样式（约在第 8536-9016 行）。

**Step 5: 提交更改**

```bash
git add static/css/dashboard.css
git commit -m "refactor: 从 CSS 中删除成果展示样式"
```

---

## Task 12: 从布局配置中删除成果展示默认值

**文件：**
- Modify: `static/js/dashboard.js:6743`

**Step 1: 读取布局默认配置**

使用 Read 工具读取 `static/js/dashboard.js` 第 6733-6750 行。

**Step 2: 删除成果展示布局配置**

删除 `LAYOUT_DEFAULTS.cards` 对象中的 `achievements` 配置项（第 6743 行）：

```javascript
// 删除这一行
'achievements': { flex: '0 0 100px', height: null },
```

**Step 3: 提交更改**

```bash
git add static/js/dashboard.js
git commit -m "refactor: 从布局配置中删除成果展示"
```

---

## Task 13: 删除数据文件

**文件：**
- Delete: `achievements.json`

**Step 1: 检查文件是否存在**

```bash
ls -la achievements.json
```

**Step 2: 删除数据文件**

```bash
rm achievements.json
```

**Step 3: 验证文件已删除**

```bash
ls achievements.json
```

预期输出：`No such file or directory`

**Step 4: 提交更改**

```bash
git add achievements.json
git commit -m "refactor: 删除成果展示数据文件"
```

---

## Task 14: 删除上传目录

**文件：**
- Delete: `static/uploads/achievements/`

**Step 1: 检查目录是否存在**

```bash
ls -la static/uploads/achievements/
```

**Step 2: 删除整个目录及其内容**

```bash
rm -rf static/uploads/achievements/
```

**Step 3: 验证目录已删除**

```bash
ls static/uploads/achievements/
```

预期输出：`No such file or directory`

**Step 4: 提交更改**

```bash
git add static/uploads/achievements/
git commit -m "refactor: 删除成果展示上传目录"
```

---

## Task 15: 更新 CLAUDE.md 文档

**文件：**
- Modify: `CLAUDE.md`

**Step 1: 读取文档确认需要修改的位置**

使用 Grep 工具搜索 `achievements` 和 `成果展示` 关键词。

**Step 2: 从架构概览中删除 achievements.py**

在 `CLAUDE.md` 的架构概览部分，删除以下行：

```markdown
│   ├── achievements.py       # 成果展示（含图片上传）
```

**Step 3: 从 MongoDB 集合列表中删除 achievements**

在 `CLAUDE.md` 的 MongoDB 关键集合部分，删除以下行：

```markdown
- `achievements`：成果展示
```

**Step 4: 从 API 模块分区表中删除成果展示行**

在 `CLAUDE.md` 的 API 模块分区表中，删除以下行：

```markdown
| 成果展示 | `/api/achievements/*` | 成果CRUD、图片上传、URL标题抓取 |
```

**Step 5: 提交更改**

```bash
git add CLAUDE.md
git commit -m "docs: 从文档中删除成果展示相关描述"
```

---

## Task 16: 验证应用启动

**Step 1: 启动应用**

```bash
python app.py
```

预期输出：应用正常启动，无导入错误，监听在 `localhost:5000`

**Step 2: 检查启动日志**

确认日志中没有关于 `achievements` 的错误信息。

**Step 3: 停止应用**

按 `Ctrl+C` 停止应用。

---

## Task 17: 验证前端功能

**Step 1: 启动应用**

```bash
python app.py
```

**Step 2: 在浏览器中访问主页**

访问 `http://localhost:5000`，登录后检查：
- 主仪表盘正常加载
- 成果展示卡片已消失
- 其他模块正常显示

**Step 3: 检查浏览器控制台**

打开浏览器开发者工具（F12），检查 Console 标签：
- 无 JavaScript 错误
- 无 404 错误（特别是 `/api/achievements` 相关请求）

**Step 4: 测试 API 端点已移除**

在浏览器控制台或使用 curl 测试：

```bash
curl http://localhost:5000/api/achievements
```

预期输出：404 Not Found

**Step 5: 停止应用**

---

## Task 18: 最终提交

**Step 1: 查看所有更改**

```bash
git status
git diff --cached
```

**Step 2: 确认所有文件已暂存**

确保以下文件已被 git 跟踪：
- `models/achievements.py` (deleted)
- `routes/api.py` (modified)
- `templates/index.html` (modified)
- `static/js/dashboard.js` (modified)
- `static/css/dashboard.css` (modified)
- `achievements.json` (deleted)
- `static/uploads/achievements/` (deleted)
- `CLAUDE.md` (modified)

**Step 3: 创建最终提交（如果有遗漏的文件）**

```bash
git add -A
git commit -m "refactor: 完全移除成果展示功能

- 删除后端模型文件 models/achievements.py
- 从 API 路由中删除 6 个端点
- 从前端删除卡片 UI 和弹窗
- 从 JS 中删除所有相关函数
- 从 CSS 中删除所有相关样式
- 删除数据文件和上传目录
- 更新文档移除相关描述"
```

**Step 4: 推送到远程仓库**

```bash
git push origin main
```

---

## 验证清单

完成所有任务后，确认以下检查项：

- [ ] `models/achievements.py` 文件已删除
- [ ] `routes/api.py` 中所有成果展示相关代码已删除
- [ ] `templates/index.html` 中成果展示卡片和弹窗已删除
- [ ] `static/js/dashboard.js` 中所有成果展示函数已删除
- [ ] `static/css/dashboard.css` 中所有成果展示样式已删除
- [ ] `achievements.json` 文件已删除
- [ ] `static/uploads/achievements/` 目录已删除
- [ ] `CLAUDE.md` 文档已更新
- [ ] 应用启动无错误
- [ ] 主页加载正常，无成果展示卡片
- [ ] 浏览器控制台无 JavaScript 错误
- [ ] `/api/achievements/*` 端点返回 404
- [ ] 所有更改已提交并推送到远程仓库

---

## 回滚方案

如需恢复功能，可通过以下命令回滚：

```bash
# 查看删除前的提交
git log --all --full-history -- models/achievements.py

# 回滚到删除前的提交
git revert <commit-hash>

# 或者硬重置（谨慎使用）
git reset --hard <commit-hash>
```
