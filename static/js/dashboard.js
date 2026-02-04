/**
 * 全球新闻态势感知平台 - 大屏前端主逻辑
 * 科技风格 / 自动刷新 / 风控监控
 */

// ==================== 全局配置 ====================
const CONFIG = {
    refreshInterval: 60000,  // 自动刷新间隔（毫秒）
    trendDays: 7,           // 趋势图天数
    alertLimit: 30          // 告警列表数量
};

// 全局变量
let sourceChart = null;
let trendChart = null;
let keywordChart = null;
let worldMap = null;
let refreshTimer = null;

// 风控告警筛选相关
let allAlertsData = [];           // 存储所有告警数据
let currentFilterKeyword = null;  // 当前筛选的关键词
let keywordChartData = [];        // 关键词图表数据

// 国家代码映射
const COUNTRY_NAMES = {
    'US': '美国', 'GB': '英国', 'CN': '中国', 'HK': '香港',
    'JP': '日本', 'KZ': '哈萨克斯坦', 'PK': '巴基斯坦',
    'AR': '阿根廷', 'IL': '以色列', 'TM': '土库曼斯坦'
};

// ECharts 科技风格主题配置
const CHART_THEME = {
    color: ['#00f0ff', '#00ff88', '#7b68ee', '#ffa502', '#ff4757'],
    backgroundColor: 'transparent',
    textStyle: { color: 'rgba(255,255,255,0.7)' },
    axisLine: { lineStyle: { color: 'rgba(0,240,255,0.3)' } },
    splitLine: { lineStyle: { color: 'rgba(0,240,255,0.1)' } }
};

// ==================== 工具函数 ====================

async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`/api${endpoint}`);
        const data = await response.json();
        return data.success ? data.data : null;
    } catch (error) {
        console.error('API请求失败:', error);
        return null;
    }
}

function formatNumber(num) {
    if (num === null || num === undefined) return '--';
    if (num >= 10000) return (num / 10000).toFixed(1) + '万';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function formatCompactNumber(num) {
    if (num >= 10000) return (num / 10000).toFixed(1) + 'w';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return num;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateDateTime() {
    const now = new Date();
    const dateStr = now.toLocaleDateString('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit'
    });
    const timeStr = now.toLocaleTimeString('zh-CN', {
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
    document.getElementById('datetime').textContent = `${dateStr} ${timeStr}`;
}

function showRefreshIndicator() {
    const indicator = document.getElementById('refreshIndicator');
    indicator.style.animation = 'none';
    indicator.offsetHeight; // 触发重绘
    indicator.style.animation = 'refreshPulse 1s ease-in-out';
}

// ==================== 数据加载函数 ====================

async function loadOverviewStats() {
    const [overview, realtime] = await Promise.all([
        fetchAPI('/stats/overview'),
        fetchAPI('/stats/realtime')
    ]);

    if (overview) {
        document.getElementById('totalArticles').textContent = formatNumber(overview.total_articles);
        document.getElementById('totalSources').textContent = overview.total_sources;
        document.getElementById('totalCountries').textContent = overview.total_countries;
    }

    if (realtime) {
        document.getElementById('todayCount').textContent = formatNumber(realtime.today_count);
        document.getElementById('weekCount').textContent = formatNumber(realtime.week_count);
        document.getElementById('activeSources').textContent = realtime.active_sources;
        document.getElementById('updateTime').textContent = realtime.update_time;

        // 环比变化
        const changeEl = document.getElementById('changeRate');
        if (realtime.change_rate !== 0) {
            const isUp = realtime.change_rate > 0;
            changeEl.textContent = `${isUp ? '↑' : '↓'} ${Math.abs(realtime.change_rate)}%`;
            changeEl.className = `stat-change ${isUp ? 'up' : 'down'}`;
        } else {
            changeEl.textContent = '-- 持平';
            changeEl.className = 'stat-change';
        }
    }
}

async function loadSourceChart() {
    const data = await fetchAPI('/stats/sources');
    if (!data || data.length === 0) return;

    const chartDom = document.getElementById('sourceChart');
    if (!sourceChart) {
        sourceChart = echarts.init(chartDom);

        // 添加点击事件 - 点击柱子查看该新闻源的文章
        sourceChart.on('click', (params) => {
            if (params.componentType === 'series') {
                const sourceName = params.name;
                openSourceArticlesModal(sourceName);
            }
        });
    }

    // 取前10个源
    const topData = data.slice(0, 10).reverse();
    const sources = topData.map(item => item.source || '未知');
    const counts = topData.map(item => item.count);

    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            backgroundColor: 'rgba(10,20,40,0.9)',
            borderColor: 'rgba(0,240,255,0.3)',
            textStyle: { color: '#fff' },
            formatter: (params) => `${params[0].name}: ${params[0].value} 篇<br/><span style="color:#00f0ff;font-size:10px;">点击查看文章</span>`
        },
        grid: {
            left: '3%', right: '15%', top: '5%', bottom: '5%',
            containLabel: true
        },
        xAxis: {
            type: 'value',
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: { color: 'rgba(255,255,255,0.5)', fontSize: 10 },
            splitLine: { lineStyle: { color: 'rgba(0,240,255,0.1)' } }
        },
        yAxis: {
            type: 'category',
            data: sources,
            axisLine: { lineStyle: { color: 'rgba(0,240,255,0.3)' } },
            axisTick: { show: false },
            axisLabel: {
                color: 'rgba(255,255,255,0.7)',
                fontSize: 11,
                formatter: (val) => val.length > 8 ? val.slice(0, 8) + '...' : val
            },
            triggerEvent: true  // 允许Y轴标签触发事件
        },
        series: [{
            type: 'bar',
            data: counts,
            barWidth: '60%',
            itemStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                    { offset: 0, color: 'rgba(0,240,255,0.8)' },
                    { offset: 1, color: 'rgba(0,255,136,0.8)' }
                ]),
                borderRadius: [0, 4, 4, 0],
                cursor: 'pointer'
            },
            label: {
                show: true,
                position: 'right',
                color: '#00f0ff',
                fontSize: 10,
                formatter: (p) => formatCompactNumber(p.value)
            },
            emphasis: {
                itemStyle: {
                    shadowBlur: 10,
                    shadowColor: 'rgba(0, 240, 255, 0.5)'
                }
            }
        }]
    };

    sourceChart.setOption(option);

    // Y轴标签点击事件
    sourceChart.getZr().off('click');  // 先移除旧的事件避免重复绑定
    sourceChart.getZr().on('click', (params) => {
        const pointInPixel = [params.offsetX, params.offsetY];
        if (sourceChart.containPixel('grid', pointInPixel)) {
            const yIndex = sourceChart.convertFromPixel({ seriesIndex: 0 }, pointInPixel)[1];
            if (yIndex >= 0 && yIndex < sources.length) {
                const sourceName = sources[Math.round(yIndex)];
                openSourceArticlesModal(sourceName);
            }
        }
    });
}

async function loadTrendChart() {
    const data = await fetchAPI(`/stats/trend?days=${CONFIG.trendDays}`);

    const chartDom = document.getElementById('trendChart');
    if (!trendChart) {
        trendChart = echarts.init(chartDom);
    }

    if (!data || data.length === 0) {
        trendChart.setOption({
            graphic: {
                type: 'text',
                left: 'center', top: 'center',
                style: { text: '暂无趋势数据', fill: 'rgba(255,255,255,0.3)', fontSize: 14 }
            }
        });
        return;
    }

    const dates = data.map(item => item.date.slice(5)); // MM-DD
    const counts = data.map(item => item.count);

    const option = {
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(10,20,40,0.9)',
            borderColor: 'rgba(0,240,255,0.3)',
            textStyle: { color: '#fff' }
        },
        grid: {
            left: '3%', right: '4%', top: '10%', bottom: '15%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: dates,
            boundaryGap: false,
            axisLine: { lineStyle: { color: 'rgba(0,240,255,0.3)' } },
            axisTick: { show: false },
            axisLabel: { color: 'rgba(255,255,255,0.5)', fontSize: 10, rotate: 0 }
        },
        yAxis: {
            type: 'value',
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: { color: 'rgba(255,255,255,0.5)', fontSize: 10 },
            splitLine: { lineStyle: { color: 'rgba(0,240,255,0.1)' } }
        },
        series: [{
            type: 'line',
            data: counts,
            smooth: true,
            symbol: 'circle',
            symbolSize: 6,
            lineStyle: { width: 2, color: '#00f0ff' },
            itemStyle: { color: '#00f0ff', borderColor: '#00f0ff' },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(0,240,255,0.4)' },
                    { offset: 1, color: 'rgba(0,240,255,0.02)' }
                ])
            }
        }]
    };

    trendChart.setOption(option);
}

async function loadWorldMap() {
    const data = await fetchAPI('/map/markers');
    if (!data) return;

    if (!worldMap) {
        worldMap = L.map('worldMap', {
            center: [25, 20],
            zoom: 2,
            minZoom: 1,
            maxZoom: 6,
            zoomControl: false,
            attributionControl: false
        });

        // 使用深色地图图层
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            maxZoom: 19
        }).addTo(worldMap);
    }

    // 清除现有标记
    worldMap.eachLayer(layer => {
        if (layer instanceof L.CircleMarker) {
            worldMap.removeLayer(layer);
        }
    });

    // 添加气泡标记
    data.forEach(item => {
        if (!item.coords || item.coords.length !== 2) return;

        const lat = item.coords[1];
        const lng = item.coords[0];
        const size = Math.max(8, Math.min(30, 5 + Math.log10(item.count + 1) * 10));

        const marker = L.circleMarker([lat, lng], {
            radius: size,
            fillColor: '#00f0ff',
            fillOpacity: 0.6,
            color: '#00f0ff',
            weight: 2,
            opacity: 0.8
        }).addTo(worldMap);

        marker.bindPopup(`
            <div style="font-family: 'Microsoft YaHei'; min-width: 120px;">
                <div style="font-weight: bold; color: #00f0ff; margin-bottom: 5px;">${item.source || '未知'}</div>
                <div style="color: rgba(255,255,255,0.7); font-size: 12px;">
                    国家: ${COUNTRY_NAMES[item.country] || item.country || '-'}<br/>
                    文章: ${formatNumber(item.count)} 篇
                </div>
            </div>
        `, {
            className: 'custom-popup'
        });
    });
}

// ==================== 风控监控 ====================

async function loadRiskStats() {
    const data = await fetchAPI('/risk/stats?days=7');
    if (!data) return;

    const { summary } = data;
    document.getElementById('riskHigh').textContent = formatNumber(summary.high_total);
    document.getElementById('riskMedium').textContent = formatNumber(summary.medium_total);
    document.getElementById('riskLow').textContent = formatNumber(summary.low_total);

    // 更新关键词热度图
    loadKeywordChart(data.stats);
}

function loadKeywordChart(stats) {
    const chartDom = document.getElementById('keywordChart');
    if (!keywordChart) {
        keywordChart = echarts.init(chartDom);

        // 添加点击事件
        keywordChart.on('click', (params) => {
            if (params.componentType === 'series') {
                const keyword = params.name;
                filterAlertsByKeyword(keyword);
            }
        });

        // Y轴标签也可点击
        keywordChart.getZr().on('click', (params) => {
            const pointInPixel = [params.offsetX, params.offsetY];
            if (keywordChart.containPixel('grid', pointInPixel)) {
                const yIndex = keywordChart.convertFromPixel({ seriesIndex: 0 }, pointInPixel)[1];
                const reversedData = [...keywordChartData].reverse();
                if (yIndex >= 0 && yIndex < reversedData.length) {
                    const keyword = reversedData[Math.round(yIndex)].keyword;
                    filterAlertsByKeyword(keyword);
                }
            }
        });
    }

    // 合并所有关键词并排序取前8
    const allKeywords = [];
    const levelColors = {
        high: '#ff4757',
        medium: '#ffa502',
        low: '#2ed573'
    };

    for (const [level, items] of Object.entries(stats)) {
        items.forEach(item => {
            allKeywords.push({
                keyword: item.keyword,
                count: item.count,
                level: level,
                color: levelColors[level]
            });
        });
    }

    const topKeywords = allKeywords
        .sort((a, b) => b.count - a.count)
        .slice(0, 8);

    // 保存到全局变量
    keywordChartData = topKeywords;

    if (topKeywords.length === 0) {
        keywordChart.setOption({
            graphic: {
                type: 'text',
                left: 'center', top: 'center',
                style: { text: '暂无风控数据', fill: 'rgba(255,255,255,0.3)', fontSize: 12 }
            }
        });
        return;
    }

    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            backgroundColor: 'rgba(10,20,40,0.9)',
            borderColor: 'rgba(0,240,255,0.3)',
            textStyle: { color: '#fff', fontSize: 11 },
            formatter: (params) => {
                return `${params[0].name}: ${params[0].value} 篇<br/><span style="color:#00f0ff;font-size:10px;">点击筛选告警</span>`;
            }
        },
        grid: {
            left: '3%', right: '10%', top: '5%', bottom: '5%',
            containLabel: true
        },
        xAxis: {
            type: 'value',
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: { show: false },
            splitLine: { show: false }
        },
        yAxis: {
            type: 'category',
            data: topKeywords.map(k => k.keyword).reverse(),
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: {
                color: 'rgba(255,255,255,0.7)',
                fontSize: 10,
                formatter: (val) => val.length > 6 ? val.slice(0, 6) + '..' : val
            },
            triggerEvent: true  // 允许Y轴标签触发事件
        },
        series: [{
            type: 'bar',
            data: topKeywords.map(k => ({
                value: k.count,
                itemStyle: { color: k.color },
                name: k.keyword  // 保存关键词名称
            })).reverse(),
            barWidth: '50%',
            itemStyle: { borderRadius: [0, 3, 3, 0], cursor: 'pointer' },
            label: {
                show: true,
                position: 'right',
                color: 'rgba(255,255,255,0.6)',
                fontSize: 9,
                formatter: (p) => p.value
            },
            emphasis: {
                itemStyle: {
                    shadowBlur: 10,
                    shadowColor: 'rgba(0, 240, 255, 0.5)'
                }
            }
        }]
    };

    keywordChart.setOption(option);
}

// 按关键词筛选告警
function filterAlertsByKeyword(keyword) {
    if (currentFilterKeyword === keyword) {
        // 再次点击同一关键词，清除筛选
        clearAlertFilter();
        return;
    }

    currentFilterKeyword = keyword;
    renderFilteredAlerts();
    showToast(`已筛选: ${keyword}`, 'success');
}

// 清除告警筛选
function clearAlertFilter() {
    currentFilterKeyword = null;
    renderFilteredAlerts();
}

// 渲染筛选后的告警列表
function renderFilteredAlerts() {
    const alertList = document.getElementById('alertList');
    const alertCount = document.getElementById('alertCount');
    const filterInfo = document.getElementById('alertFilterInfo');

    let filteredData = allAlertsData;

    // 更新筛选状态显示
    if (currentFilterKeyword) {
        filteredData = allAlertsData.filter(alert => {
            // 检查标题或匹配关键词中是否包含筛选词
            const titleMatch = alert.title.toLowerCase().includes(currentFilterKeyword.toLowerCase());
            const keywordMatch = alert.matched_keywords.some(
                kw => kw.toLowerCase().includes(currentFilterKeyword.toLowerCase())
            );
            return titleMatch || keywordMatch;
        });

        // 显示筛选标签
        if (filterInfo) {
            filterInfo.style.display = 'flex';
            filterInfo.querySelector('.filter-keyword').textContent = currentFilterKeyword;
        }
    } else {
        // 隐藏筛选标签
        if (filterInfo) {
            filterInfo.style.display = 'none';
        }
    }

    alertCount.textContent = filteredData.length;

    if (filteredData.length === 0) {
        alertList.innerHTML = `<div class="loading-text">${currentFilterKeyword ? '无匹配告警' : '暂无风控告警'}</div>`;
        return;
    }

    alertList.innerHTML = filteredData.map(alert => `
        <div class="alert-item ${alert.risk_level}" onclick="window.open('${escapeHtml(alert.url)}', '_blank')">
            <div class="alert-title">${highlightKeyword(escapeHtml(alert.title), currentFilterKeyword)}</div>
            <div class="alert-meta">
                <span class="alert-source">
                    <span>${escapeHtml(alert.source)}</span>
                    <span>${alert.pub_date || ''}</span>
                </span>
                <div class="alert-keywords">
                    ${alert.matched_keywords.slice(0, 2).map(kw =>
                        `<span class="keyword-tag ${alert.risk_level} ${currentFilterKeyword && kw.toLowerCase().includes(currentFilterKeyword.toLowerCase()) ? 'active' : ''}">${escapeHtml(kw)}</span>`
                    ).join('')}
                </div>
            </div>
        </div>
    `).join('');
}

// 高亮关键词
function highlightKeyword(text, keyword) {
    if (!keyword) return text;
    const regex = new RegExp(`(${escapeRegExp(keyword)})`, 'gi');
    return text.replace(regex, '<span class="highlight">$1</span>');
}

// 转义正则特殊字符
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function loadRiskAlerts() {
    const data = await fetchAPI(`/risk/alerts?limit=${CONFIG.alertLimit}`);
    const alertList = document.getElementById('alertList');
    const alertCount = document.getElementById('alertCount');

    if (!data || data.length === 0) {
        allAlertsData = [];
        alertList.innerHTML = '<div class="loading-text">暂无风控告警</div>';
        alertCount.textContent = '0';
        return;
    }

    // 保存到全局变量
    allAlertsData = data;

    // 渲染（考虑当前筛选状态）
    renderFilteredAlerts();
}

// ==================== 初始化与刷新 ====================

async function loadAllData() {
    showRefreshIndicator();

    await Promise.all([
        loadOverviewStats(),
        loadSourceChart(),
        loadTrendChart(),
        loadWorldMap(),
        loadRiskStats(),
        loadRiskAlerts(),
        loadAchievements(),
        loadDutyInfo()
    ]);
}

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(loadAllData, CONFIG.refreshInterval);
}

function handleResize() {
    if (sourceChart) sourceChart.resize();
    if (trendChart) trendChart.resize();
    if (keywordChart) keywordChart.resize();
    if (worldMap) worldMap.invalidateSize();
}

// 页面初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 更新时间
    updateDateTime();
    setInterval(updateDateTime, 1000);

    // 加载数据
    await loadAllData();

    // 启动自动刷新
    startAutoRefresh();

    // 窗口大小变化
    window.addEventListener('resize', handleResize);

    // ESC 关闭弹窗
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeKeywordModal();
            closeEditModal();
            closeSitesModal();
            closeEditSiteModal();
            closeBatchImportModal();
            closeAllAlertsModal();
            closeCrawlModal();
            closeSettingsModal();
            closeCalendar();
            closeSourceArticlesModal();
            closeArticleCalendar();
            closeAchievementModal();
            closeDutyModal();
        }
    });

    // 点击外部关闭日历
    document.addEventListener('click', (e) => {
        const calendarDropdown = document.getElementById('calendarDropdown');
        const datePickerBtn = document.getElementById('datePickerBtn');
        if (calendarDropdown && datePickerBtn) {
            if (!calendarDropdown.contains(e.target) && !datePickerBtn.contains(e.target)) {
                closeCalendar();
            }
        }
    });
});


// ==================== 关键词管理 ====================

let keywordsData = { high: [], medium: [], low: [] };
let currentTab = 'high';

function openKeywordModal() {
    document.getElementById('keywordModal').classList.add('active');
    loadKeywords();
}

function closeKeywordModal() {
    document.getElementById('keywordModal').classList.remove('active');
}

function openEditModal(id, keyword, level) {
    document.getElementById('editKeywordId').value = id;
    document.getElementById('editKeywordText').value = keyword;
    document.getElementById('editKeywordLevel').value = level;
    document.getElementById('editModal').classList.add('active');
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
}

async function loadKeywords() {
    const keywordList = document.getElementById('keywordList');
    keywordList.innerHTML = '<div class="loading-text">加载中...</div>';

    const data = await fetchAPI('/risk/keywords');
    if (data) {
        keywordsData = data;
        updateTabCounts();
        renderKeywords(currentTab);
    } else {
        keywordList.innerHTML = '<div class="loading-text">加载失败</div>';
    }
}

function updateTabCounts() {
    document.getElementById('tabCountHigh').textContent = keywordsData.high.length;
    document.getElementById('tabCountMedium').textContent = keywordsData.medium.length;
    document.getElementById('tabCountLow').textContent = keywordsData.low.length;
}

function switchTab(level) {
    currentTab = level;

    // 更新标签页样式
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.level === level);
    });

    renderKeywords(level);
}

function renderKeywords(level) {
    const keywordList = document.getElementById('keywordList');
    const keywords = keywordsData[level] || [];

    if (keywords.length === 0) {
        keywordList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">-</div>
                <div>暂无关键词</div>
            </div>
        `;
        return;
    }

    keywordList.innerHTML = keywords.map(kw => `
        <div class="keyword-item ${level}">
            <span class="keyword-text">${escapeHtml(kw.keyword)}</span>
            <div class="keyword-actions">
                <button class="btn-icon edit" onclick="openEditModal('${kw.id}', '${escapeHtml(kw.keyword)}', '${level}')" title="编辑">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
                <button class="btn-icon delete" onclick="deleteKeyword('${kw.id}')" title="删除">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>
            </div>
        </div>
    `).join('');
}

async function addKeyword() {
    const keywordInput = document.getElementById('newKeyword');
    const levelSelect = document.getElementById('newKeywordLevel');

    const keyword = keywordInput.value.trim();
    const level = levelSelect.value;

    if (!keyword) {
        showToast('请输入关键词', 'error');
        return;
    }

    try {
        const response = await fetch('/api/risk/keywords', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword, level })
        });

        const data = await response.json();

        if (data.success) {
            showToast('添加成功', 'success');
            keywordInput.value = '';
            loadKeywords();
            // 刷新风控数据
            loadRiskStats();
            loadRiskAlerts();
        } else {
            showToast(data.error || '添加失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

async function saveKeyword() {
    const id = document.getElementById('editKeywordId').value;
    const keyword = document.getElementById('editKeywordText').value.trim();
    const level = document.getElementById('editKeywordLevel').value;

    if (!keyword) {
        showToast('关键词不能为空', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/risk/keywords/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword, level })
        });

        const data = await response.json();

        if (data.success) {
            showToast('保存成功', 'success');
            closeEditModal();
            loadKeywords();
            // 刷新风控数据
            loadRiskStats();
            loadRiskAlerts();
        } else {
            showToast(data.error || '保存失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

async function deleteKeyword(id) {
    if (!confirm('确定要删除这个关键词吗？')) {
        return;
    }

    try {
        const response = await fetch(`/api/risk/keywords/${id}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showToast('删除成功', 'success');
            loadKeywords();
            // 刷新风控数据
            loadRiskStats();
            loadRiskAlerts();
        } else {
            showToast(data.error || '删除失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}


// ==================== 订阅管理 ====================

let sitesData = [];

function openSitesModal() {
    document.getElementById('sitesModal').classList.add('active');
    loadSites();
}

function closeSitesModal() {
    document.getElementById('sitesModal').classList.remove('active');
}

function openEditSiteModal(id, name, url, countryCode, fetchMethod) {
    document.getElementById('editSiteId').value = id;
    document.getElementById('editSiteName').value = name;
    document.getElementById('editSiteUrl').value = url;
    document.getElementById('editSiteCountry').value = countryCode || '';
    document.getElementById('editSiteMethod').value = fetchMethod || 'sitemap';
    document.getElementById('editSiteModal').classList.add('active');
}

function closeEditSiteModal() {
    document.getElementById('editSiteModal').classList.remove('active');
}

async function loadSites() {
    const siteList = document.getElementById('siteList');
    siteList.innerHTML = '<div class="loading-text">加载中...</div>';

    const data = await fetchAPI('/sites');
    if (data) {
        sitesData = data;
        renderSites();
        updateSiteStats();
    } else {
        siteList.innerHTML = '<div class="loading-text">加载失败</div>';
    }
}

function updateSiteStats() {
    const sitemapCount = sitesData.filter(s => s.fetch_method === 'sitemap').length;
    const crawlerCount = sitesData.filter(s => s.fetch_method === 'crawler').length;
    const unknownCount = sitesData.filter(s => !s.fetch_method || s.fetch_method === 'unknown').length;

    document.getElementById('sitemapCount').textContent = sitemapCount;
    document.getElementById('crawlerCount').textContent = crawlerCount;
    document.getElementById('unknownCount').textContent = unknownCount;
    document.getElementById('siteTotalCount').textContent = sitesData.length;
}

function renderSites() {
    const siteList = document.getElementById('siteList');

    if (sitesData.length === 0) {
        siteList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">+</div>
                <div>暂无订阅站点，请添加</div>
            </div>
        `;
        return;
    }

    siteList.innerHTML = sitesData.map(site => {
        const methodClass = site.fetch_method === 'sitemap' ? 'sitemap' : (site.fetch_method === 'crawler' ? 'crawler' : 'unknown');
        const methodText = site.fetch_method === 'sitemap' ? 'Sitemap' : (site.fetch_method === 'crawler' ? '爬虫' : '未知');
        return `
        <div class="site-item ${methodClass}">
            <div class="site-info">
                <div class="site-name">${escapeHtml(site.name)}</div>
                <div class="site-url">${escapeHtml(site.url)}</div>
            </div>
            <div class="site-meta">
                <span class="site-country">${site.country_code || '未知'}</span>
                <span class="site-method ${methodClass}">
                    ${methodText}
                </span>
            </div>
            <div class="site-actions">
                <button class="btn-icon recheck" onclick="recheckSitemap('${site.id}')" title="重新检测">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="23 4 23 10 17 10"></polyline>
                        <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                    </svg>
                </button>
                <button class="btn-icon edit" onclick="openEditSiteModal('${site.id}', '${escapeHtml(site.name)}', '${escapeHtml(site.url)}', '${site.country_code || ''}', '${site.fetch_method || 'sitemap'}')" title="编辑">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
                <button class="btn-icon delete" onclick="deleteSite('${site.id}')" title="删除">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>
            </div>
        </div>
    `;
    }).join('');
}

async function addSite() {
    const nameInput = document.getElementById('newSiteName');
    const urlInput = document.getElementById('newSiteUrl');
    const addBtn = document.getElementById('btnAddSite');
    const btnText = addBtn.querySelector('.btn-text');
    const btnLoading = addBtn.querySelector('.btn-loading');

    const name = nameInput.value.trim();
    let url = urlInput.value.trim();

    if (!name) {
        showToast('请输入站点名称', 'error');
        return;
    }

    if (!url) {
        showToast('请输入站点 URL', 'error');
        return;
    }

    // 添加 https 前缀
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url;
    }

    // 显示加载状态
    addBtn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';

    try {
        const response = await fetch('/api/sites', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, url, auto_detect: true })
        });

        const data = await response.json();

        if (data.success) {
            const site = data.data;
            const methodText = site.fetch_method === 'sitemap' ? 'Sitemap' : '爬虫';
            showToast(`添加成功，获取方式: ${methodText}`, 'success');
            nameInput.value = '';
            urlInput.value = '';
            loadSites();
        } else {
            showToast(data.error || '添加失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        // 恢复按钮状态
        addBtn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

async function saveSite() {
    const id = document.getElementById('editSiteId').value;
    const name = document.getElementById('editSiteName').value.trim();
    const url = document.getElementById('editSiteUrl').value.trim();
    const countryCode = document.getElementById('editSiteCountry').value;
    const fetchMethod = document.getElementById('editSiteMethod').value;

    if (!name) {
        showToast('站点名称不能为空', 'error');
        return;
    }

    if (!url) {
        showToast('站点 URL 不能为空', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/sites/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                url,
                country_code: countryCode || null,
                fetch_method: fetchMethod
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('保存成功', 'success');
            closeEditSiteModal();
            loadSites();
        } else {
            showToast(data.error || '保存失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

async function deleteSite(id) {
    if (!confirm('确定要删除这个站点吗？')) {
        return;
    }

    try {
        const response = await fetch(`/api/sites/${id}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showToast('删除成功', 'success');
            loadSites();
        } else {
            showToast(data.error || '删除失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

async function recheckSitemap(id) {
    showToast('正在检测...', 'info');

    try {
        const response = await fetch(`/api/sites/${id}/recheck`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            const result = data.data;
            const site = result.site;
            const methodText = site.fetch_method === 'sitemap' ? 'Sitemap' : '爬虫';
            showToast(`检测完成，获取方式: ${methodText}`, 'success');
            loadSites();
        } else {
            showToast(data.error || '检测失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}


// ==================== 批量导入 ====================

function openBatchImportModal() {
    document.getElementById('batchImportModal').classList.add('active');
    document.getElementById('batchImportText').value = '';
    document.getElementById('batchAutoDetect').checked = false;
}

function closeBatchImportModal() {
    document.getElementById('batchImportModal').classList.remove('active');
}

function parseBatchInput(text) {
    const lines = text.split('\n');
    const sites = [];

    for (let line of lines) {
        line = line.trim();
        if (!line) continue;

        let name, url;

        // 尝试用逗号分割
        if (line.includes(',')) {
            const parts = line.split(',');
            name = parts[0].trim();
            url = parts.slice(1).join(',').trim();
        }
        // 尝试用空格/制表符分割
        else {
            const match = line.match(/^(.+?)\s+(https?:\/\/.+)$/i);
            if (match) {
                name = match[1].trim();
                url = match[2].trim();
            } else {
                // 尝试用最后一个空格分割
                const lastSpaceIdx = line.lastIndexOf(' ');
                if (lastSpaceIdx > 0) {
                    name = line.slice(0, lastSpaceIdx).trim();
                    url = line.slice(lastSpaceIdx + 1).trim();
                } else {
                    // 无法解析，跳过
                    continue;
                }
            }
        }

        if (name && url) {
            // 自动添加 https
            if (!url.startsWith('http://') && !url.startsWith('https://')) {
                url = 'https://' + url;
            }
            sites.push({ name, url });
        }
    }

    return sites;
}

async function doBatchImport() {
    const textInput = document.getElementById('batchImportText');
    const autoDetect = document.getElementById('batchAutoDetect').checked;
    const btn = document.getElementById('btnDoBatchImport');
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');

    const text = textInput.value.trim();
    if (!text) {
        showToast('请输入站点列表', 'error');
        return;
    }

    const sites = parseBatchInput(text);
    if (sites.length === 0) {
        showToast('未能解析出有效的站点', 'error');
        return;
    }

    // 显示加载状态
    btn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';

    try {
        const response = await fetch('/api/sites/batch-import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sites, auto_detect: autoDetect })
        });

        const data = await response.json();

        if (data.success) {
            const result = data.data;
            const successCount = result.success.length;
            const failedCount = result.failed.length;

            if (failedCount > 0) {
                const failedNames = result.failed.map(f => f.name).join(', ');
                showToast(`导入完成: ${successCount} 成功, ${failedCount} 失败 (${failedNames})`, 'info');
            } else {
                showToast(`成功导入 ${successCount} 个站点`, 'success');
            }

            closeBatchImportModal();
            loadSites();
        } else {
            showToast(data.error || '导入失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        btn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}


// ==================== 一键检测 ====================

// ==================== 全部告警与日历筛选 ====================

let fullAlertsData = [];
let currentDateFilter = null;
let currentKeywordFilter = null;

// 日历相关
let calendarYear = new Date().getFullYear();
let calendarMonth = new Date().getMonth() + 1;
let calendarData = {};  // 存储每天的告警数量

function openAllAlertsModal() {
    document.getElementById('allAlertsModal').classList.add('active');
    // 初始化日期
    currentDateFilter = null;
    currentKeywordFilter = null;
    document.getElementById('datePickerText').textContent = '选择日期';
    // 初始化日历为当前月份
    calendarYear = new Date().getFullYear();
    calendarMonth = new Date().getMonth() + 1;
    // 加载关键词下拉列表
    loadKeywordFilterOptions();
    // 加载日历数据
    loadCalendarData();
    // 加载全部告警
    loadFullAlerts();
}

function closeAllAlertsModal() {
    document.getElementById('allAlertsModal').classList.remove('active');
    closeCalendar();
}

async function loadKeywordFilterOptions() {
    const select = document.getElementById('alertKeywordFilter');
    const data = await fetchAPI('/risk/keywords');

    // 清空并重建选项
    select.innerHTML = '<option value="">全部关键词</option>';

    if (data) {
        const allKeywords = [];
        for (const [level, keywords] of Object.entries(data)) {
            keywords.forEach(kw => {
                allKeywords.push({ keyword: kw.keyword, level });
            });
        }
        // 按等级排序：high -> medium -> low
        const levelOrder = { high: 0, medium: 1, low: 2 };
        allKeywords.sort((a, b) => levelOrder[a.level] - levelOrder[b.level]);

        allKeywords.forEach(item => {
            const option = document.createElement('option');
            option.value = item.keyword;
            const levelText = { high: '高', medium: '中', low: '低' }[item.level];
            option.textContent = `[${levelText}] ${item.keyword}`;
            select.appendChild(option);
        });
    }
}

async function loadFullAlerts() {
    const alertList = document.getElementById('fullAlertList');
    const alertCount = document.getElementById('fullAlertCount');

    alertList.innerHTML = '<div class="loading-text">加载中...</div>';

    // 构建查询参数
    let url = '/risk/alerts?limit=500';
    if (currentDateFilter) {
        url += `&date=${currentDateFilter}`;
    }
    if (currentKeywordFilter) {
        url += `&keyword=${encodeURIComponent(currentKeywordFilter)}`;
    }

    const data = await fetchAPI(url);

    if (!data || data.length === 0) {
        fullAlertsData = [];
        alertList.innerHTML = '<div class="loading-text">暂无告警数据</div>';
        alertCount.textContent = '0';
        return;
    }

    fullAlertsData = data;
    alertCount.textContent = data.length;

    renderFullAlerts();
}

function renderFullAlerts() {
    const alertList = document.getElementById('fullAlertList');

    if (fullAlertsData.length === 0) {
        alertList.innerHTML = '<div class="loading-text">暂无告警数据</div>';
        return;
    }

    alertList.innerHTML = fullAlertsData.map(alert => {
        // 解析日期
        let dateStr = '', timeStr = '';
        if (alert.pub_date) {
            const parts = alert.pub_date.split(' ');
            dateStr = parts[0] || '';
            timeStr = parts[1] || '';
        }

        const riskText = { high: '高风险', medium: '中风险', low: '关注' }[alert.risk_level] || '未知';

        return `
        <div class="full-alert-item ${alert.risk_level}" onclick="window.open('${escapeHtml(alert.url)}', '_blank')">
            <div class="alert-date">
                <span class="date">${dateStr}</span>
                <span class="time">${timeStr}</span>
            </div>
            <div class="alert-content">
                <div class="alert-title">${escapeHtml(alert.title)}</div>
                <div class="alert-meta">
                    <span class="alert-source-tag">${escapeHtml(alert.source)}</span>
                    <span class="alert-risk-tag ${alert.risk_level}">${riskText}</span>
                    ${alert.matched_keywords.map(kw =>
                        `<span class="keyword-tag ${alert.risk_level}">${escapeHtml(kw)}</span>`
                    ).join('')}
                </div>
            </div>
        </div>
    `;
    }).join('');
}

// ==================== 自定义日历组件 ====================

function toggleCalendar() {
    const dropdown = document.getElementById('calendarDropdown');
    const btn = document.getElementById('datePickerBtn');

    if (dropdown.classList.contains('show')) {
        closeCalendar();
    } else {
        dropdown.classList.add('show');
        btn.classList.add('active');
        loadCalendarData();
    }
}

function closeCalendar() {
    const dropdown = document.getElementById('calendarDropdown');
    const btn = document.getElementById('datePickerBtn');
    if (dropdown) dropdown.classList.remove('show');
    if (btn) btn.classList.remove('active');
}

async function loadCalendarData() {
    const data = await fetchAPI(`/risk/alerts/calendar?year=${calendarYear}&month=${calendarMonth}`);
    calendarData = data || {};
    renderCalendar();
}

function renderCalendar() {
    const title = document.getElementById('calendarTitle');
    const daysContainer = document.getElementById('calendarDays');

    title.textContent = `${calendarYear}年${calendarMonth}月`;

    // 计算这个月的第一天是星期几
    const firstDay = new Date(calendarYear, calendarMonth - 1, 1);
    const startWeekday = firstDay.getDay();

    // 计算这个月有多少天
    const daysInMonth = new Date(calendarYear, calendarMonth, 0).getDate();

    // 计算上个月的天数（用于填充）
    const prevMonthDays = new Date(calendarYear, calendarMonth - 1, 0).getDate();

    // 今天的日期
    const today = new Date();
    const todayStr = formatDateValue(today);

    let html = '';

    // 填充上个月的日期
    for (let i = startWeekday - 1; i >= 0; i--) {
        const day = prevMonthDays - i;
        html += `<div class="calendar-day other-month"><span class="day-number">${day}</span></div>`;
    }

    // 填充当前月的日期
    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${calendarYear}-${String(calendarMonth).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const count = calendarData[dateStr] || 0;
        const isToday = dateStr === todayStr;
        const isSelected = dateStr === currentDateFilter;

        let levelClass = '';
        let countClass = '';
        if (count > 0) {
            if (count >= 10) {
                levelClass = 'alert-level-high has-alerts';
                countClass = '';
            } else if (count >= 5) {
                levelClass = 'alert-level-medium has-alerts';
                countClass = 'medium';
            } else {
                levelClass = 'alert-level-low has-alerts';
                countClass = 'low';
            }
        }

        const classes = [
            'calendar-day',
            isToday ? 'today' : '',
            isSelected ? 'selected' : '',
            levelClass
        ].filter(c => c).join(' ');

        html += `
            <div class="${classes}" onclick="selectDate('${dateStr}')">
                <span class="day-number">${day}</span>
                ${count > 0 ? `<span class="day-count ${countClass}">${count}</span>` : ''}
            </div>
        `;
    }

    // 填充下个月的日期
    const totalCells = startWeekday + daysInMonth;
    const remainingCells = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    for (let i = 1; i <= remainingCells; i++) {
        html += `<div class="calendar-day other-month"><span class="day-number">${i}</span></div>`;
    }

    daysContainer.innerHTML = html;
}

function changeMonth(delta) {
    calendarMonth += delta;

    if (calendarMonth > 12) {
        calendarMonth = 1;
        calendarYear++;
    } else if (calendarMonth < 1) {
        calendarMonth = 12;
        calendarYear--;
    }

    loadCalendarData();
}

function selectDate(dateStr) {
    currentDateFilter = dateStr;

    // 更新按钮显示
    const parts = dateStr.split('-');
    document.getElementById('datePickerText').textContent = `${parts[1]}月${parts[2]}日`;

    // 清除快捷日期按钮状态
    document.querySelectorAll('.btn-quick-date').forEach(btn => btn.classList.remove('active'));

    // 关闭日历
    closeCalendar();

    // 刷新日历显示选中状态
    renderCalendar();

    // 加载数据
    loadFullAlerts();
}

function clearDateFilter() {
    currentDateFilter = null;
    document.getElementById('datePickerText').textContent = '选择日期';
    // 清除快捷日期按钮的激活状态
    document.querySelectorAll('.btn-quick-date').forEach(btn => btn.classList.remove('active'));
    renderCalendar();
    loadFullAlerts();
}

function onKeywordFilterChange() {
    const select = document.getElementById('alertKeywordFilter');
    currentKeywordFilter = select.value || null;
    loadFullAlerts();
}

function setQuickDate(type) {
    const today = new Date();
    let targetDate;

    // 更新按钮状态
    document.querySelectorAll('.btn-quick-date').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    if (type === 'today') {
        targetDate = today;
        currentDateFilter = formatDateValue(targetDate);
        const parts = currentDateFilter.split('-');
        document.getElementById('datePickerText').textContent = `${parts[1]}月${parts[2]}日`;
        loadFullAlerts();
    } else if (type === 'yesterday') {
        targetDate = new Date(today);
        targetDate.setDate(targetDate.getDate() - 1);
        currentDateFilter = formatDateValue(targetDate);
        const parts = currentDateFilter.split('-');
        document.getElementById('datePickerText').textContent = `${parts[1]}月${parts[2]}日`;
        loadFullAlerts();
    } else if (type === 'week') {
        // 近7天需要特殊处理，清除日期筛选让后端返回最近的数据
        currentDateFilter = null;
        document.getElementById('datePickerText').textContent = '近7天';
        loadFullAlerts();
    }

    // 更新日历月份到选中日期所在月
    if (targetDate) {
        calendarYear = targetDate.getFullYear();
        calendarMonth = targetDate.getMonth() + 1;
    }
    renderCalendar();
}

function formatDateValue(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function refreshFullAlerts() {
    loadCalendarData();
    loadFullAlerts();
    showToast('已刷新', 'success');
}


async function batchCheckAll() {
    if (sitesData.length === 0) {
        showToast('没有可检测的站点', 'error');
        return;
    }

    const btn = document.getElementById('btnBatchCheck');
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');

    // 显示加载状态
    btn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';
    btnLoading.textContent = `检测中 (0/${sitesData.length})...`;

    showToast(`开始检测 ${sitesData.length} 个站点，请稍候...`, 'info');

    try {
        const response = await fetch('/api/sites/batch-check', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            const result = data.data;
            showToast(`检测完成: ${result.sitemap} 个支持 Sitemap, ${result.crawler} 个使用爬虫`, 'success');
            loadSites();
        } else {
            showToast(data.error || '检测失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        btn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}


// ==================== 更新文章功能 ====================

let currentCrawlMethod = 'auto';
let crawlSitesData = [];
let crawlEventSource = null;  // SSE 连接
let isCrawling = false;       // 是否正在爬取

function openCrawlModal() {
    document.getElementById('crawlModal').classList.add('active');
    currentCrawlMethod = 'auto';
    updateCrawlMethodUI();
    loadCrawlSites();
    hideCrawlResult();
    hideCrawlProgress();
}

function closeCrawlModal() {
    // 如果正在爬取，先停止
    if (crawlEventSource) {
        crawlEventSource.close();
        crawlEventSource = null;
    }
    isCrawling = false;
    resetCrawlUI();
    document.getElementById('crawlModal').classList.remove('active');
}

function selectCrawlMethod(method) {
    currentCrawlMethod = method;
    updateCrawlMethodUI();
}

function updateCrawlMethodUI() {
    // 更新按钮状态
    document.querySelectorAll('.option-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.method === currentCrawlMethod);
    });

    // 更新描述
    const descEl = document.getElementById('crawlMethodDesc');
    const descriptions = {
        'auto': '根据站点配置自动选择：支持 Sitemap 的使用 Sitemap，否则使用 AI 分析',
        'sitemap': '从网站的 sitemap.xml 获取文章列表，速度快，适合支持 Sitemap 的网站',
        'ai': '使用 Crawl4AI 爬取网页内容，通过 DeepSeek 分析提取文章信息（需配置 API Key）'
    };
    descEl.textContent = descriptions[currentCrawlMethod];
}

async function loadCrawlSites() {
    const listEl = document.getElementById('crawlSiteList');
    listEl.innerHTML = '<div class="loading-text">加载中...</div>';

    const data = await fetchAPI('/sites');
    if (data) {
        crawlSitesData = data;
        renderCrawlSites();
    } else {
        listEl.innerHTML = '<div class="loading-text">加载失败</div>';
    }
}

function renderCrawlSites() {
    const listEl = document.getElementById('crawlSiteList');

    if (crawlSitesData.length === 0) {
        listEl.innerHTML = '<div class="loading-text">暂无站点</div>';
        return;
    }

    listEl.innerHTML = crawlSitesData.map(site => {
        const methodClass = site.fetch_method === 'sitemap' ? 'sitemap' : 'crawler';
        const methodText = site.fetch_method === 'sitemap' ? 'Sitemap' : 'AI爬取';
        return `
        <div class="crawl-site-item" id="crawl-site-${site.id}">
            <div class="crawl-site-info">
                <div class="crawl-site-name">${escapeHtml(site.name)}</div>
                <div class="crawl-site-meta">
                    <span>${site.country_code || '未知'}</span>
                    <span class="crawl-site-method ${methodClass}">${methodText}</span>
                </div>
            </div>
            <div class="crawl-site-actions">
                <button class="btn-crawl" onclick="crawlSingleSite('${site.id}')" id="btn-crawl-${site.id}">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="5 3 19 12 5 21 5 3"></polygon>
                    </svg>
                    更新
                </button>
            </div>
        </div>
    `;
    }).join('');
}

async function crawlSingleSite(siteId) {
    const btn = document.getElementById(`btn-crawl-${siteId}`);
    const siteItem = document.getElementById(`crawl-site-${siteId}`);
    const site = crawlSitesData.find(s => s.id === siteId);

    if (!site) return;

    // 确定爬取方式
    let method = currentCrawlMethod;
    if (method === 'auto') {
        method = site.fetch_method === 'sitemap' && site.sitemap_url ? 'sitemap' : 'ai';
    }

    // 显示加载状态
    btn.disabled = true;
    btn.innerHTML = `<span class="btn-loading">更新中...</span>`;

    try {
        const response = await fetch(`/api/crawl/${method}/${siteId}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            const result = data.data;
            // 显示成功状态
            btn.outerHTML = `<span class="crawl-status success">+${result.saved} 篇</span>`;
            showToast(`${site.name}: 获取 ${result.fetched} 篇，新增 ${result.saved} 篇`, 'success');
        } else {
            btn.outerHTML = `<span class="crawl-status error">失败</span>`;
            showToast(`${site.name}: ${data.error}`, 'error');
        }
    } catch (error) {
        btn.outerHTML = `<span class="crawl-status error">错误</span>`;
        showToast('网络错误', 'error');
    }
}

async function crawlAllSites() {
    if (crawlSitesData.length === 0) {
        showToast('没有可更新的站点', 'error');
        return;
    }

    const btn = document.getElementById('btnCrawlAll');
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');

    // 显示加载状态
    btn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';

    showToast(`开始更新 ${crawlSitesData.length} 个站点，请稍候...`, 'info');

    try {
        const response = await fetch('/api/crawl/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ method: currentCrawlMethod })
        });

        const data = await response.json();

        if (data.success) {
            const result = data.data;
            showCrawlResult(result);
            showToast(`更新完成: 成功 ${result.success} 个，共获取 ${result.total_articles} 篇文章`, 'success');
            // 刷新主页面数据
            loadAllData();
        } else {
            showToast(data.error || '更新失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        btn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        // 重新加载站点列表
        loadCrawlSites();
    }
}

// 带进度显示的批量更新
function crawlAllSitesWithProgress() {
    if (crawlSitesData.length === 0) {
        showToast('没有可更新的站点', 'error');
        return;
    }

    if (isCrawling) {
        showToast('正在更新中，请稍候...', 'info');
        return;
    }

    isCrawling = true;

    // 更新 UI 状态
    const btn = document.getElementById('btnCrawlAll');
    const btnStop = document.getElementById('btnCrawlStop');
    const hint = document.getElementById('crawlHint');

    btn.style.display = 'none';
    btnStop.style.display = 'inline-flex';
    hint.style.display = 'none';

    // 显示进度面板
    showCrawlProgress();

    // 隐藏站点列表（可选，保持简洁）
    // document.getElementById('crawlSiteList').style.display = 'none';

    // 开始 SSE 连接
    const url = `/api/crawl/batch/stream?method=${encodeURIComponent(currentCrawlMethod)}`;
    crawlEventSource = new EventSource(url);

    crawlEventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleCrawlEvent(data);
        } catch (e) {
            console.error('解析 SSE 数据失败:', e);
        }
    };

    crawlEventSource.onerror = function(event) {
        console.error('SSE 连接错误:', event);
        if (crawlEventSource) {
            crawlEventSource.close();
            crawlEventSource = null;
        }
        if (isCrawling) {
            isCrawling = false;
            resetCrawlUI();
            showToast('连接中断，请重试', 'error');
        }
    };
}

// 停止爬取进度
function stopCrawlProgress() {
    if (crawlEventSource) {
        crawlEventSource.close();
        crawlEventSource = null;
    }
    isCrawling = false;
    resetCrawlUI();
    addCrawlLog('已手动停止更新', 'error');
    showToast('已停止更新', 'info');
}

// 处理 SSE 事件
function handleCrawlEvent(data) {
    switch (data.type) {
        case 'init':
            // 初始化
            document.getElementById('liveTotal').textContent = data.total;
            document.getElementById('liveProcessed').textContent = '0';
            document.getElementById('liveSuccess').textContent = '0';
            document.getElementById('liveFailed').textContent = '0';
            document.getElementById('liveArticles').textContent = '0';
            document.getElementById('crawlProgressBarFill').style.width = '0%';
            document.getElementById('crawlProgressPercent').textContent = '0%';
            document.getElementById('crawlProgressText').textContent = `准备更新 ${data.total} 个站点...`;
            clearCrawlLog();
            addCrawlLog(`开始更新 ${data.total} 个站点`, 'info');
            break;

        case 'progress':
            // 正在处理某站点
            document.getElementById('currentSiteName').textContent = data.site_name;
            document.getElementById('currentSiteStatus').className = 'current-site-status';
            document.getElementById('currentSiteStatus').innerHTML = `
                <span class="status-spinner"></span>
                <span class="status-text">获取中...</span>
            `;

            const progressPercent = Math.round((data.current - 1) / data.total * 100);
            document.getElementById('crawlProgressBarFill').style.width = `${progressPercent}%`;
            document.getElementById('crawlProgressPercent').textContent = `${progressPercent}%`;
            document.getElementById('crawlProgressText').textContent = `正在处理 ${data.current}/${data.total}`;

            addCrawlLog(`正在获取: ${data.site_name}`, 'info');

            // 更新站点列表中对应项的状态
            updateSiteItemStatus(data.site_id, 'processing');
            break;

        case 'site_done':
            // 单个站点完成
            document.getElementById('liveProcessed').textContent = data.current;
            document.getElementById('liveSuccess').textContent = data.success_count;
            document.getElementById('liveFailed').textContent = data.failed_count;
            document.getElementById('liveArticles').textContent = data.total_articles;

            const donePercent = Math.round(data.current / data.total * 100);
            document.getElementById('crawlProgressBarFill').style.width = `${donePercent}%`;
            document.getElementById('crawlProgressPercent').textContent = `${donePercent}%`;
            document.getElementById('crawlProgressText').textContent = `已完成 ${data.current}/${data.total}`;

            if (data.success) {
                document.getElementById('currentSiteStatus').className = 'current-site-status done';
                document.getElementById('currentSiteStatus').innerHTML = `
                    <span class="status-text">+${data.saved} 篇</span>
                `;
                addCrawlLog(`✓ ${data.site_name}: 获取 ${data.fetched} 篇，新增 ${data.saved} 篇`, 'success');
                updateSiteItemStatus(data.site_id, 'success', data.saved);
            } else {
                document.getElementById('currentSiteStatus').className = 'current-site-status error';
                document.getElementById('currentSiteStatus').innerHTML = `
                    <span class="status-text">失败</span>
                `;
                addCrawlLog(`✗ ${data.site_name}: ${data.error || '失败'}`, 'error');
                updateSiteItemStatus(data.site_id, 'error', data.error);
            }
            break;

        case 'complete':
            // 全部完成
            isCrawling = false;

            if (crawlEventSource) {
                crawlEventSource.close();
                crawlEventSource = null;
            }

            document.getElementById('crawlProgressBarFill').style.width = '100%';
            document.getElementById('crawlProgressPercent').textContent = '100%';
            document.getElementById('crawlProgressText').textContent = '更新完成';
            document.getElementById('currentSiteName').textContent = '-';
            document.getElementById('currentSiteStatus').className = 'current-site-status';
            document.getElementById('currentSiteStatus').innerHTML = `
                <span class="status-text">已完成</span>
            `;

            // 添加完成样式
            const progressPanel = document.getElementById('crawlProgressPanel');
            if (data.failed > 0) {
                progressPanel.classList.add('has-errors');
            } else {
                progressPanel.classList.add('completed');
            }

            addCrawlLog(`更新完成: 成功 ${data.success} 个, 失败 ${data.failed} 个, 新增 ${data.total_articles} 篇文章`, 'info');

            // 恢复 UI
            resetCrawlUI();

            // 刷新主页面数据
            loadAllData();

            // 显示完成提示
            if (data.failed > 0) {
                showToast(`更新完成: 成功 ${data.success} 个, 失败 ${data.failed} 个`, 'info');
            } else {
                showToast(`更新完成: 成功 ${data.success} 个, 新增 ${data.total_articles} 篇文章`, 'success');
            }
            break;
    }
}

// 显示进度面板
function showCrawlProgress() {
    const panel = document.getElementById('crawlProgressPanel');
    panel.style.display = 'block';
    panel.classList.remove('completed', 'has-errors');
}

// 隐藏进度面板
function hideCrawlProgress() {
    document.getElementById('crawlProgressPanel').style.display = 'none';
}

// 重置爬取 UI
function resetCrawlUI() {
    const btn = document.getElementById('btnCrawlAll');
    const btnStop = document.getElementById('btnCrawlStop');
    const hint = document.getElementById('crawlHint');

    btn.style.display = 'inline-flex';
    btnStop.style.display = 'none';
    hint.style.display = 'inline';
}

// 清空日志
function clearCrawlLog() {
    document.getElementById('crawlLiveLog').innerHTML = '';
}

// 添加日志条目
function addCrawlLog(message, type = 'info') {
    const logContainer = document.getElementById('crawlLiveLog');

    // 移除占位符
    const placeholder = logContainer.querySelector('.log-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    const now = new Date();
    const timeStr = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `
        <span class="log-time">${timeStr}</span>
        <span class="log-message">${escapeHtml(message)}</span>
    `;

    logContainer.appendChild(entry);

    // 自动滚动到底部
    logContainer.scrollTop = logContainer.scrollHeight;
}

// 更新站点列表中的状态
function updateSiteItemStatus(siteId, status, extra = null) {
    const siteItem = document.getElementById(`crawl-site-${siteId}`);
    if (!siteItem) return;

    const actionsDiv = siteItem.querySelector('.crawl-site-actions');
    if (!actionsDiv) return;

    if (status === 'processing') {
        actionsDiv.innerHTML = `<span class="crawl-status">处理中...</span>`;
    } else if (status === 'success') {
        actionsDiv.innerHTML = `<span class="crawl-status success">+${extra} 篇</span>`;
    } else if (status === 'error') {
        actionsDiv.innerHTML = `<span class="crawl-status error">失败</span>`;
    }
}

function showCrawlResult(result) {
    const resultEl = document.getElementById('crawlResult');
    const bodyEl = document.getElementById('crawlResultBody');

    let detailsHtml = '';
    if (result.details && result.details.length > 0) {
        detailsHtml = result.details.map(d => {
            if (d.success) {
                return `<div style="margin-bottom:5px;"><span style="color:var(--risk-low);">✓</span> ${escapeHtml(d.name)}: +${d.saved} 篇</div>`;
            } else {
                return `<div style="margin-bottom:5px;"><span style="color:var(--risk-high);">✗</span> ${escapeHtml(d.name)}: ${escapeHtml(d.error || '失败')}</div>`;
            }
        }).join('');
    }

    bodyEl.innerHTML = `
        <div class="result-summary">
            <div class="result-stat">
                <span class="label">总站点:</span>
                <span class="value">${result.total}</span>
            </div>
            <div class="result-stat">
                <span class="label">成功:</span>
                <span class="value success">${result.success}</span>
            </div>
            <div class="result-stat">
                <span class="label">失败:</span>
                <span class="value error">${result.failed}</span>
            </div>
            <div class="result-stat">
                <span class="label">新增文章:</span>
                <span class="value">${result.total_articles}</span>
            </div>
        </div>
        ${detailsHtml}
    `;

    resultEl.style.display = 'block';
}

function hideCrawlResult() {
    document.getElementById('crawlResult').style.display = 'none';
}

function closeCrawlResult() {
    hideCrawlResult();
}


// ==================== 系统设置 ====================

let providersData = {};

function openSettingsModal() {
    document.getElementById('settingsModal').classList.add('active');
    loadSettings();
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.remove('active');
}

async function loadSettings() {
    const data = await fetchAPI('/settings');
    if (!data) return;

    // 保存提供商数据
    providersData = data.providers || {};

    // LLM 设置
    if (data.llm) {
        const provider = data.llm.provider || 'siliconflow';
        document.getElementById('llmProvider').value = provider;
        document.getElementById('llmApiUrl').value = data.llm.api_url || '';
        document.getElementById('llmApiKey').value = '';
        document.getElementById('llmApiKey').placeholder = data.llm.api_key_set ? '已配置（输入新值覆盖）' : 'sk-...';

        // 更新模型列表
        updateModelOptions(provider, data.llm.model);

        // 更新状态
        const statusEl = document.getElementById('llmStatus');
        if (data.llm.api_key_set) {
            statusEl.textContent = '已配置';
            statusEl.className = 'section-status configured';
        } else {
            statusEl.textContent = '未配置';
            statusEl.className = 'section-status not-configured';
        }

        // 显示遮蔽的 Key
        const hintEl = document.getElementById('llmKeyHint');
        if (data.llm.api_key_masked) {
            hintEl.textContent = `当前: ${data.llm.api_key_masked}`;
        } else {
            hintEl.textContent = '';
        }
    }
}

function onProviderChange() {
    const provider = document.getElementById('llmProvider').value;
    const providerConfig = providersData[provider];

    if (providerConfig) {
        // 更新 API URL
        if (providerConfig.api_url) {
            document.getElementById('llmApiUrl').value = providerConfig.api_url;
        }

        // 更新模型列表
        updateModelOptions(provider);
    }
}

function updateModelOptions(provider, selectedModel = null) {
    const modelSelect = document.getElementById('llmModel');
    const providerConfig = providersData[provider];

    modelSelect.innerHTML = '';

    if (providerConfig && providerConfig.models && providerConfig.models.length > 0) {
        providerConfig.models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            modelSelect.appendChild(option);
        });
    } else {
        // 自定义提供商，允许自由输入
        const option = document.createElement('option');
        option.value = selectedModel || '';
        option.textContent = selectedModel || '请输入模型名称';
        modelSelect.appendChild(option);
    }

    // 设置选中的模型
    if (selectedModel) {
        modelSelect.value = selectedModel;
    }
}

async function saveSettings() {
    const settings = {
        llm: {
            provider: document.getElementById('llmProvider').value,
            api_url: document.getElementById('llmApiUrl').value.trim(),
            model: document.getElementById('llmModel').value
        }
    };

    // 只有输入了新的 API Key 才更新
    const apiKey = document.getElementById('llmApiKey').value.trim();
    if (apiKey) {
        settings.llm.api_key = apiKey;
    }

    try {
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        const data = await response.json();

        if (data.success) {
            showToast('设置已保存', 'success');
            closeSettingsModal();
        } else {
            showToast(data.error || '保存失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

async function testLLMConnection() {
    const btn = document.getElementById('btnTestLLM');
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');

    const apiUrl = document.getElementById('llmApiUrl').value.trim();
    const apiKey = document.getElementById('llmApiKey').value.trim();
    const model = document.getElementById('llmModel').value;

    if (!apiUrl) {
        showToast('请输入 API URL', 'error');
        return;
    }

    // 显示加载状态
    btn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';

    try {
        const response = await fetch('/api/settings/test-api', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                api_url: apiUrl,
                api_key: apiKey,
                model: model,
                use_saved: !apiKey
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('连接成功！', 'success');
        } else {
            showToast(data.error || '连接失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        btn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    input.type = input.type === 'password' ? 'text' : 'password';
}

function toggleSettingsSection(header) {
    const section = header.closest('.settings-section');
    section.classList.toggle('collapsed');
}


// ==================== 后台日志功能 ====================

let logsCurrentPage = 1;
let logsPageSize = 50;
let logsTotal = 0;
let logsFilterDebounceTimer = null;

function openLogsModal() {
    document.getElementById('logsModal').classList.add('active');
    logsCurrentPage = 1;
    loadLogsStats();
    loadLogs();
}

function closeLogsModal() {
    document.getElementById('logsModal').classList.remove('active');
}

async function loadLogsStats() {
    const data = await fetchAPI('/logs/stats');
    if (!data) return;

    document.getElementById('logsTotalCount').textContent = data.total || 0;
    document.getElementById('logsOperationCount').textContent = data.by_type?.operation || 0;
    document.getElementById('logsRequestCount').textContent = data.by_type?.request || 0;
    document.getElementById('logsErrorCount').textContent = data.by_status?.error || 0;
}

async function loadLogs() {
    const listEl = document.getElementById('logsList');
    listEl.innerHTML = '<div class="loading-text">加载中...</div>';

    const logType = document.getElementById('logTypeFilter').value;
    const status = document.getElementById('logStatusFilter').value;
    const search = document.getElementById('logSearchInput').value.trim();

    const offset = (logsCurrentPage - 1) * logsPageSize;
    let url = `/logs?limit=${logsPageSize}&offset=${offset}`;
    if (logType) url += `&type=${encodeURIComponent(logType)}`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;

    const data = await fetchAPI(url);
    if (!data) {
        listEl.innerHTML = '<div class="loading-text">加载失败</div>';
        return;
    }

    logsTotal = data.total || 0;

    if (!data.items || data.items.length === 0) {
        listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div>暂无日志</div>';
        updateLogsPagination();
        return;
    }

    listEl.innerHTML = data.items.map(log => renderLogItem(log)).join('');
    updateLogsPagination();
}

function renderLogItem(log) {
    const typeLabels = {
        'operation': '操作',
        'request': '请求',
        'system': '系统'
    };

    const statusLabels = {
        'info': '信息',
        'success': '成功',
        'warning': '警告',
        'error': '错误'
    };

    let extraInfo = '';
    if (log.log_type === 'request' && log.details) {
        const url = log.details.url || '';
        const duration = log.details.duration_ms ? `${Math.round(log.details.duration_ms)}ms` : '';
        const statusCode = log.details.response_status || '';

        if (url) {
            extraInfo += `<div class="log-url">${log.details.method || 'GET'} ${escapeHtml(url.length > 80 ? url.substring(0, 80) + '...' : url)}</div>`;
        }
        if (statusCode || duration) {
            extraInfo += `<div class="log-body" style="margin-top:4px;">`;
            if (statusCode) extraInfo += `<span>状态: ${statusCode}</span> `;
            if (duration) extraInfo += `<span class="log-duration">${duration}</span>`;
            extraInfo += `</div>`;
        }
    }

    if (log.error) {
        extraInfo += `<div class="log-error">${escapeHtml(log.error.substring(0, 200))}</div>`;
    }

    return `
        <div class="log-item ${log.status}" onclick="openLogDetail('${log.id}')">
            <div class="log-header">
                <span class="log-time">${log.timestamp}</span>
                <span class="log-type-badge ${log.log_type}">${typeLabels[log.log_type] || log.log_type}</span>
                <span class="log-status-badge ${log.status}">${statusLabels[log.status] || log.status}</span>
                <span class="log-action">${escapeHtml(log.action)}</span>
                <span class="log-expand-icon">▼</span>
            </div>
            ${extraInfo}
        </div>
    `;
}

function updateLogsPagination() {
    const totalPages = Math.ceil(logsTotal / logsPageSize);

    document.getElementById('logsCurrentPageNum').textContent = logsCurrentPage;
    document.getElementById('logsPrevBtn').disabled = logsCurrentPage <= 1;
    document.getElementById('logsNextBtn').disabled = logsCurrentPage >= totalPages;
}

function loadLogsPage(page) {
    if (page < 1) page = 1;
    const totalPages = Math.ceil(logsTotal / logsPageSize);
    if (page > totalPages && totalPages > 0) page = totalPages;

    logsCurrentPage = page;
    loadLogs();
}

function filterLogs() {
    logsCurrentPage = 1;
    loadLogs();
}

function debounceFilterLogs() {
    if (logsFilterDebounceTimer) {
        clearTimeout(logsFilterDebounceTimer);
    }
    logsFilterDebounceTimer = setTimeout(() => {
        filterLogs();
    }, 300);
}

function refreshLogs() {
    loadLogsStats();
    loadLogs();
    showToast('日志已刷新', 'success');
}

async function clearAllLogs() {
    if (!confirm('确定要清空所有日志吗？此操作不可恢复。')) {
        return;
    }

    try {
        const response = await fetch('/api/logs', {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showToast(`已清空 ${data.data.count} 条日志`, 'success');
            loadLogsStats();
            loadLogs();
        } else {
            showToast(data.error || '清空失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

async function openLogDetail(logId) {
    document.getElementById('logDetailModal').classList.add('active');
    const contentEl = document.getElementById('logDetailContent');
    contentEl.innerHTML = '<div class="loading-text">加载中...</div>';

    const data = await fetchAPI(`/logs/${logId}`);
    if (!data) {
        contentEl.innerHTML = '<div class="loading-text">加载失败</div>';
        return;
    }

    contentEl.innerHTML = renderLogDetail(data);
}

function closeLogDetailModal() {
    document.getElementById('logDetailModal').classList.remove('active');
}

function renderLogDetail(log) {
    const typeLabels = {
        'operation': '操作日志',
        'request': '网络请求',
        'system': '系统日志'
    };

    const statusLabels = {
        'info': '信息',
        'success': '成功',
        'warning': '警告',
        'error': '错误'
    };

    let html = `
        <div class="log-detail-section">
            <div class="log-detail-section-title">基本信息</div>
            <div class="log-detail-row">
                <span class="log-detail-label">ID</span>
                <span class="log-detail-value">${log.id}</span>
            </div>
            <div class="log-detail-row">
                <span class="log-detail-label">时间</span>
                <span class="log-detail-value">${log.timestamp}</span>
            </div>
            <div class="log-detail-row">
                <span class="log-detail-label">类型</span>
                <span class="log-detail-value">${typeLabels[log.log_type] || log.log_type}</span>
            </div>
            <div class="log-detail-row">
                <span class="log-detail-label">状态</span>
                <span class="log-detail-value">${statusLabels[log.status] || log.status}</span>
            </div>
            <div class="log-detail-row">
                <span class="log-detail-label">操作</span>
                <span class="log-detail-value">${escapeHtml(log.action)}</span>
            </div>
        </div>
    `;

    // 详情信息
    if (log.details && Object.keys(log.details).length > 0) {
        html += `
            <div class="log-detail-section">
                <div class="log-detail-section-title">详细信息</div>
                <div class="log-detail-code">${JSON.stringify(log.details, null, 2)}</div>
            </div>
        `;
    }

    // 错误信息
    if (log.error) {
        html += `
            <div class="log-detail-section">
                <div class="log-detail-section-title">错误信息</div>
                <div class="log-detail-code" style="color: var(--risk-high);">${escapeHtml(log.error)}</div>
            </div>
        `;
    }

    // 请求数据
    if (log.request_data) {
        html += `
            <div class="log-detail-section">
                <div class="log-detail-section-title">请求数据</div>
                <div class="log-detail-code">${JSON.stringify(log.request_data, null, 2)}</div>
            </div>
        `;
    }

    // 响应数据
    if (log.response_data) {
        html += `
            <div class="log-detail-section">
                <div class="log-detail-section-title">响应数据</div>
                <div class="log-detail-code">${JSON.stringify(log.response_data, null, 2)}</div>
            </div>
        `;
    }

    return html;
}


// ==================== 新闻源文章列表功能 ====================

let currentSourceName = null;          // 当前选中的新闻源
let articlesData = [];                 // 文章列表数据
let articlesCurrentPage = 1;           // 当前页码
let articlesPageSize = 20;             // 每页数量
let articlesTotal = 0;                 // 总数
let articleDateFilter = null;          // 日期筛选
let articleSearchKeyword = '';         // 搜索关键词
let articleSearchDebounceTimer = null; // 搜索防抖定时器

// 文章日历相关
let articleCalendarYear = new Date().getFullYear();
let articleCalendarMonth = new Date().getMonth() + 1;

// 打开新闻源文章列表弹窗
function openSourceArticlesModal(sourceName) {
    currentSourceName = sourceName;
    articlesCurrentPage = 1;
    articleDateFilter = null;
    articleSearchKeyword = '';

    // 更新标题
    document.getElementById('sourceArticlesTitle').textContent = sourceName;
    document.getElementById('sourceArticlesSubtitle').textContent = '- 文章列表';

    // 重置筛选UI
    document.getElementById('articleDatePickerText').textContent = '选择日期';
    document.getElementById('articleSearchInput').value = '';
    document.querySelectorAll('#sourceArticlesModal .btn-quick-date').forEach(btn => btn.classList.remove('active'));

    // 初始化日历
    articleCalendarYear = new Date().getFullYear();
    articleCalendarMonth = new Date().getMonth() + 1;

    // 显示弹窗
    document.getElementById('sourceArticlesModal').classList.add('active');

    // 加载文章
    loadSourceArticles();
}

// 关闭新闻源文章列表弹窗
function closeSourceArticlesModal() {
    document.getElementById('sourceArticlesModal').classList.remove('active');
    closeArticleCalendar();
}

// 加载新闻源文章
async function loadSourceArticles() {
    const listEl = document.getElementById('sourceArticleList');
    const countEl = document.getElementById('sourceArticleCount');

    listEl.innerHTML = '<div class="loading-text">加载中...</div>';

    // 构建查询参数
    let url = `/articles?source=${encodeURIComponent(currentSourceName)}&page=${articlesCurrentPage}&page_size=${articlesPageSize}`;

    if (articleSearchKeyword) {
        url += `&keyword=${encodeURIComponent(articleSearchKeyword)}`;
    }

    if (articleDateFilter) {
        // 如果是单日筛选
        url += `&start_date=${articleDateFilter}&end_date=${articleDateFilter}`;
    }

    const data = await fetchAPI(url);

    if (!data) {
        listEl.innerHTML = '<div class="loading-text">加载失败</div>';
        countEl.textContent = '0';
        return;
    }

    articlesData = data.items || [];
    articlesTotal = data.total || 0;

    countEl.textContent = articlesTotal;

    if (articlesData.length === 0) {
        listEl.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📰</div>暂无文章数据</div>';
        updateArticlesPagination();
        return;
    }

    renderSourceArticles();
    updateArticlesPagination();
}

// 渲染文章列表
function renderSourceArticles() {
    const listEl = document.getElementById('sourceArticleList');

    listEl.innerHTML = articlesData.map(article => {
        // 解析日期
        let dateStr = '', timeStr = '';
        if (article.pub_date) {
            // 尝试解析日期
            const pubDate = article.pub_date;
            if (pubDate.includes(' ')) {
                const parts = pubDate.split(' ');
                dateStr = parts[0] || '';
                timeStr = parts[1] || '';
            } else if (pubDate.includes('T')) {
                const parts = pubDate.split('T');
                dateStr = parts[0] || '';
                timeStr = parts[1] ? parts[1].slice(0, 5) : '';
            } else {
                dateStr = pubDate;
            }
        }

        // 标题高亮搜索关键词
        let titleHtml = escapeHtml(article.title || '无标题');
        if (articleSearchKeyword) {
            titleHtml = highlightKeyword(titleHtml, articleSearchKeyword);
        }

        // URL 截断显示
        const urlDisplay = article.url ? (article.url.length > 80 ? article.url.substring(0, 80) + '...' : article.url) : '';

        return `
            <div class="source-article-item" onclick="window.open('${escapeHtml(article.url || '')}', '_blank')">
                <div class="article-date">
                    <span class="date">${dateStr}</span>
                    <span class="time">${timeStr}</span>
                </div>
                <div class="article-content">
                    <div class="article-title">${titleHtml}</div>
                    <div class="article-url">${escapeHtml(urlDisplay)}</div>
                </div>
            </div>
        `;
    }).join('');
}

// 更新文章分页
function updateArticlesPagination() {
    const totalPages = Math.ceil(articlesTotal / articlesPageSize);

    document.getElementById('articlesCurrentPageNum').textContent = articlesCurrentPage;
    document.getElementById('articlesTotalPages').textContent = totalPages || 1;
    document.getElementById('articlesPrevBtn').disabled = articlesCurrentPage <= 1;
    document.getElementById('articlesNextBtn').disabled = articlesCurrentPage >= totalPages;
}

// 翻页
function loadArticlesPage(page) {
    if (page < 1) page = 1;
    const totalPages = Math.ceil(articlesTotal / articlesPageSize);
    if (page > totalPages && totalPages > 0) page = totalPages;

    articlesCurrentPage = page;
    loadSourceArticles();
}

// 刷新文章列表
function refreshSourceArticles() {
    loadSourceArticles();
    showToast('已刷新', 'success');
}

// ==================== 文章日期筛选 ====================

function toggleArticleCalendar() {
    const dropdown = document.getElementById('articleCalendarDropdown');
    const btn = document.getElementById('articleDatePickerBtn');

    if (dropdown.classList.contains('show')) {
        closeArticleCalendar();
    } else {
        dropdown.classList.add('show');
        btn.classList.add('active');
        renderArticleCalendar();
    }
}

function closeArticleCalendar() {
    const dropdown = document.getElementById('articleCalendarDropdown');
    const btn = document.getElementById('articleDatePickerBtn');
    if (dropdown) dropdown.classList.remove('show');
    if (btn) btn.classList.remove('active');
}

function renderArticleCalendar() {
    const title = document.getElementById('articleCalendarTitle');
    const daysContainer = document.getElementById('articleCalendarDays');

    title.textContent = `${articleCalendarYear}年${articleCalendarMonth}月`;

    // 计算这个月的第一天是星期几
    const firstDay = new Date(articleCalendarYear, articleCalendarMonth - 1, 1);
    const startWeekday = firstDay.getDay();

    // 计算这个月有多少天
    const daysInMonth = new Date(articleCalendarYear, articleCalendarMonth, 0).getDate();

    // 计算上个月的天数（用于填充）
    const prevMonthDays = new Date(articleCalendarYear, articleCalendarMonth - 1, 0).getDate();

    // 今天的日期
    const today = new Date();
    const todayStr = formatDateValue(today);

    let html = '';

    // 填充上个月的日期
    for (let i = startWeekday - 1; i >= 0; i--) {
        const day = prevMonthDays - i;
        html += `<div class="calendar-day other-month"><span class="day-number">${day}</span></div>`;
    }

    // 填充当前月的日期
    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${articleCalendarYear}-${String(articleCalendarMonth).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const isToday = dateStr === todayStr;
        const isSelected = dateStr === articleDateFilter;

        const classes = [
            'calendar-day',
            isToday ? 'today' : '',
            isSelected ? 'selected' : ''
        ].filter(c => c).join(' ');

        html += `
            <div class="${classes}" onclick="selectArticleDate('${dateStr}')">
                <span class="day-number">${day}</span>
            </div>
        `;
    }

    // 填充下个月的日期
    const totalCells = startWeekday + daysInMonth;
    const remainingCells = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
    for (let i = 1; i <= remainingCells; i++) {
        html += `<div class="calendar-day other-month"><span class="day-number">${i}</span></div>`;
    }

    daysContainer.innerHTML = html;
}

function changeArticleMonth(delta) {
    articleCalendarMonth += delta;

    if (articleCalendarMonth > 12) {
        articleCalendarMonth = 1;
        articleCalendarYear++;
    } else if (articleCalendarMonth < 1) {
        articleCalendarMonth = 12;
        articleCalendarYear--;
    }

    renderArticleCalendar();
}

function selectArticleDate(dateStr) {
    articleDateFilter = dateStr;
    articlesCurrentPage = 1;

    // 更新按钮显示
    const parts = dateStr.split('-');
    document.getElementById('articleDatePickerText').textContent = `${parts[1]}月${parts[2]}日`;

    // 清除快捷日期按钮状态
    document.querySelectorAll('#sourceArticlesModal .btn-quick-date').forEach(btn => btn.classList.remove('active'));

    // 关闭日历
    closeArticleCalendar();

    // 刷新日历选中状态
    renderArticleCalendar();

    // 加载数据
    loadSourceArticles();
}

function clearArticleDateFilter() {
    articleDateFilter = null;
    articlesCurrentPage = 1;
    document.getElementById('articleDatePickerText').textContent = '选择日期';
    document.querySelectorAll('#sourceArticlesModal .btn-quick-date').forEach(btn => btn.classList.remove('active'));
    renderArticleCalendar();
    loadSourceArticles();
}

function setArticleQuickDate(type) {
    const today = new Date();

    // 更新按钮状态
    document.querySelectorAll('#sourceArticlesModal .btn-quick-date').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    articlesCurrentPage = 1;

    if (type === 'today') {
        articleDateFilter = formatDateValue(today);
        const parts = articleDateFilter.split('-');
        document.getElementById('articleDatePickerText').textContent = `${parts[1]}月${parts[2]}日`;
    } else if (type === 'week') {
        // 近7天 - 清除日期筛选，让后端返回最新数据
        articleDateFilter = null;
        document.getElementById('articleDatePickerText').textContent = '近7天';
    } else if (type === 'month') {
        // 近30天
        articleDateFilter = null;
        document.getElementById('articleDatePickerText').textContent = '近30天';
    }

    // 更新日历月份
    articleCalendarYear = today.getFullYear();
    articleCalendarMonth = today.getMonth() + 1;
    renderArticleCalendar();

    loadSourceArticles();
}

// ==================== 文章搜索 ====================

function debounceArticleSearch() {
    if (articleSearchDebounceTimer) {
        clearTimeout(articleSearchDebounceTimer);
    }
    articleSearchDebounceTimer = setTimeout(() => {
        articleSearchKeyword = document.getElementById('articleSearchInput').value.trim();
        articlesCurrentPage = 1;
        loadSourceArticles();
    }, 300);
}

function clearArticleSearch() {
    document.getElementById('articleSearchInput').value = '';
    articleSearchKeyword = '';
    articlesCurrentPage = 1;
    loadSourceArticles();
}

// 关闭弹窗时也关闭文章日历
document.addEventListener('click', (e) => {
    const articleCalendarDropdown = document.getElementById('articleCalendarDropdown');
    const articleDatePickerBtn = document.getElementById('articleDatePickerBtn');
    if (articleCalendarDropdown && articleDatePickerBtn) {
        if (!articleCalendarDropdown.contains(e.target) && !articleDatePickerBtn.contains(e.target)) {
            closeArticleCalendar();
        }
    }
});


// ==================== 成果展示功能 ====================

let achievementsData = [];
let editingAchievementId = null;
let selectedImageFile = null;

// 加载成果列表
async function loadAchievements() {
    const listEl = document.getElementById('achievementsList');

    const data = await fetchAPI('/achievements');

    if (!data || data.length === 0) {
        achievementsData = [];
        listEl.innerHTML = `
            <div class="achievements-empty">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path>
                </svg>
                <span>暂无成果，点击右上角添加</span>
            </div>
        `;
        return;
    }

    achievementsData = data;
    renderAchievements();
}

// 渲染成果列表
function renderAchievements() {
    const listEl = document.getElementById('achievementsList');

    if (achievementsData.length === 0) {
        listEl.innerHTML = `
            <div class="achievements-empty">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path>
                </svg>
                <span>暂无成果，点击右上角添加</span>
            </div>
        `;
        return;
    }

    listEl.innerHTML = achievementsData.map(item => {
        // 解析日期
        const dateStr = item.created_at ? item.created_at.split(' ')[0] : '';

        // 图片显示
        let imageHtml = '';
        if (item.image) {
            imageHtml = `<img src="/static/uploads/achievements/${item.image}" alt="${escapeHtml(item.title)}">`;
        } else {
            imageHtml = `
                <svg class="placeholder-icon" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                    <circle cx="8.5" cy="8.5" r="1.5"></circle>
                    <polyline points="21 15 16 10 5 21"></polyline>
                </svg>
            `;
        }

        return `
            <div class="achievement-item" onclick="openAchievementLink('${escapeHtml(item.url)}')">
                <div class="achievement-actions" onclick="event.stopPropagation()">
                    <button class="btn-icon-sm edit" onclick="editAchievement('${item.id}')" title="编辑">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                        </svg>
                    </button>
                    <button class="btn-icon-sm delete" onclick="deleteAchievement('${item.id}')" title="删除">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                    </button>
                </div>
                <div class="achievement-image">
                    ${imageHtml}
                </div>
                <div class="achievement-info">
                    <div class="achievement-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>
                    <div class="achievement-date">${dateStr}</div>
                </div>
            </div>
        `;
    }).join('');
}

// 打开成果链接
function openAchievementLink(url) {
    if (url) {
        window.open(url, '_blank');
    }
}

// 打开添加成果弹窗
function openAchievementModal() {
    editingAchievementId = null;
    selectedImageFile = null;

    document.getElementById('achievementModalTitle').textContent = '添加成果';
    document.getElementById('editAchievementId').value = '';
    document.getElementById('achievementUrl').value = '';
    document.getElementById('achievementTitle').value = '';
    document.getElementById('achievementDesc').value = '';

    // 重置图片上传区域
    document.getElementById('uploadPlaceholder').style.display = 'flex';
    document.getElementById('imagePreview').style.display = 'none';
    document.getElementById('btnRemoveImage').style.display = 'none';
    document.getElementById('achievementImage').value = '';

    document.getElementById('achievementModal').classList.add('active');
}

// 编辑成果
function editAchievement(id) {
    const item = achievementsData.find(a => a.id === id);
    if (!item) return;

    editingAchievementId = id;
    selectedImageFile = null;

    document.getElementById('achievementModalTitle').textContent = '编辑成果';
    document.getElementById('editAchievementId').value = id;
    document.getElementById('achievementUrl').value = item.url || '';
    document.getElementById('achievementTitle').value = item.title || '';
    document.getElementById('achievementDesc').value = item.description || '';

    // 显示已有图片
    if (item.image) {
        document.getElementById('uploadPlaceholder').style.display = 'none';
        const preview = document.getElementById('imagePreview');
        preview.src = `/static/uploads/achievements/${item.image}`;
        preview.style.display = 'block';
        document.getElementById('btnRemoveImage').style.display = 'flex';
    } else {
        document.getElementById('uploadPlaceholder').style.display = 'flex';
        document.getElementById('imagePreview').style.display = 'none';
        document.getElementById('btnRemoveImage').style.display = 'none';
    }

    document.getElementById('achievementImage').value = '';
    document.getElementById('achievementModal').classList.add('active');
}

// 关闭成果弹窗
function closeAchievementModal() {
    document.getElementById('achievementModal').classList.remove('active');
    editingAchievementId = null;
    selectedImageFile = null;
}

// 触发图片上传
function triggerImageUpload() {
    document.getElementById('achievementImage').click();
}

// 预览上传的图片
function previewAchievementImage(input) {
    if (input.files && input.files[0]) {
        selectedImageFile = input.files[0];

        const reader = new FileReader();
        reader.onload = function(e) {
            document.getElementById('uploadPlaceholder').style.display = 'none';
            const preview = document.getElementById('imagePreview');
            preview.src = e.target.result;
            preview.style.display = 'block';
            document.getElementById('btnRemoveImage').style.display = 'flex';
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// 移除图片
function removeAchievementImage(event) {
    event.stopPropagation();

    selectedImageFile = null;
    document.getElementById('achievementImage').value = '';
    document.getElementById('uploadPlaceholder').style.display = 'flex';
    document.getElementById('imagePreview').style.display = 'none';
    document.getElementById('btnRemoveImage').style.display = 'none';
}

// 抓取标题
async function fetchAchievementTitle() {
    const url = document.getElementById('achievementUrl').value.trim();
    if (!url) {
        showToast('请先输入链接', 'error');
        return;
    }

    const btn = document.getElementById('btnFetchTitle');
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');

    btn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';

    try {
        const response = await fetch('/api/achievements/fetch-title', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });

        const data = await response.json();

        if (data.success) {
            document.getElementById('achievementTitle').value = data.data.title;
            showToast('标题抓取成功', 'success');
        } else {
            showToast(data.error || '抓取失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        btn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

// 保存成果
async function saveAchievement() {
    const url = document.getElementById('achievementUrl').value.trim();
    const title = document.getElementById('achievementTitle').value.trim();
    const description = document.getElementById('achievementDesc').value.trim();

    if (!url) {
        showToast('请输入引用链接', 'error');
        return;
    }

    const btn = document.getElementById('btnSaveAchievement');
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');

    btn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';

    try {
        const formData = new FormData();
        formData.append('url', url);
        if (title) formData.append('title', title);
        if (description) formData.append('description', description);

        // 添加图片
        if (selectedImageFile) {
            formData.append('image', selectedImageFile);
        }

        let apiUrl = '/api/achievements';
        let method = 'POST';

        if (editingAchievementId) {
            apiUrl = `/api/achievements/${editingAchievementId}`;
            method = 'PUT';
        }

        const response = await fetch(apiUrl, {
            method: method,
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            showToast(editingAchievementId ? '更新成功' : '添加成功', 'success');
            closeAchievementModal();
            loadAchievements();
        } else {
            showToast(data.error || '保存失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    } finally {
        btn.disabled = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
    }
}

// 删除成果
async function deleteAchievement(id) {
    if (!confirm('确定要删除这个成果吗？')) {
        return;
    }

    try {
        const response = await fetch(`/api/achievements/${id}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showToast('删除成功', 'success');
            loadAchievements();
        } else {
            showToast(data.error || '删除失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}


// ==================== 今日值班功能 ====================

// 值班人员临时数据
let tempDutyLeaders = [];
let tempDutyOfficers = [];

// 加载值班人员信息
async function loadDutyInfo() {
    const data = await fetchAPI('/duty');

    if (data) {
        const leadersEl = document.getElementById('dutyLeaders');
        const officersEl = document.getElementById('dutyOfficers');
        const dateEl = document.getElementById('dutyDate');

        // 显示值班领导
        if (data.leaders && data.leaders.length > 0) {
            leadersEl.innerHTML = data.leaders.map(name =>
                `<span class="duty-name-tag">${escapeHtml(name)}</span>`
            ).join('');
        } else {
            leadersEl.innerHTML = '<span class="duty-empty">未设置</span>';
        }

        // 显示值班员
        if (data.officers && data.officers.length > 0) {
            officersEl.innerHTML = data.officers.map(name =>
                `<span class="duty-name-tag">${escapeHtml(name)}</span>`
            ).join('');
        } else {
            officersEl.innerHTML = '<span class="duty-empty">未设置</span>';
        }

        // 显示今日日期
        const today = new Date();
        const dateStr = today.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            weekday: 'long'
        });
        dateEl.textContent = dateStr;
    }
}

// 打开值班设置弹窗
async function openDutyModal() {
    // 获取当前值班人员
    const data = await fetchAPI('/duty');

    if (data) {
        tempDutyLeaders = data.leaders || [];
        tempDutyOfficers = data.officers || [];
    } else {
        tempDutyLeaders = [];
        tempDutyOfficers = [];
    }

    // 清空输入框
    document.getElementById('leaderNameInput').value = '';
    document.getElementById('officerNameInput').value = '';

    // 渲染标签
    renderDutyTags();

    document.getElementById('dutyModal').classList.add('active');

    // 绑定回车事件
    document.getElementById('leaderNameInput').onkeypress = function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addDutyPerson('leader');
        }
    };
    document.getElementById('officerNameInput').onkeypress = function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            addDutyPerson('officer');
        }
    };
}

// 关闭值班设置弹窗
function closeDutyModal() {
    document.getElementById('dutyModal').classList.remove('active');
}

// 渲染值班人员标签
function renderDutyTags() {
    const leaderTagsEl = document.getElementById('leaderTags');
    const officerTagsEl = document.getElementById('officerTags');

    // 渲染值班领导标签
    if (tempDutyLeaders.length > 0) {
        leaderTagsEl.innerHTML = tempDutyLeaders.map((name, index) => `
            <span class="duty-tag">
                ${escapeHtml(name)}
                <button class="remove-btn" onclick="removeDutyPerson('leader', ${index})" title="移除">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </span>
        `).join('');
    } else {
        leaderTagsEl.innerHTML = '<span class="duty-tags-empty">暂无，请添加</span>';
    }

    // 渲染值班员标签
    if (tempDutyOfficers.length > 0) {
        officerTagsEl.innerHTML = tempDutyOfficers.map((name, index) => `
            <span class="duty-tag">
                ${escapeHtml(name)}
                <button class="remove-btn" onclick="removeDutyPerson('officer', ${index})" title="移除">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </span>
        `).join('');
    } else {
        officerTagsEl.innerHTML = '<span class="duty-tags-empty">暂无，请添加</span>';
    }
}

// 添加值班人员
function addDutyPerson(role) {
    const inputId = role === 'leader' ? 'leaderNameInput' : 'officerNameInput';
    const input = document.getElementById(inputId);
    const name = input.value.trim();

    if (!name) {
        showToast('请输入姓名', 'error');
        return;
    }

    if (role === 'leader') {
        if (tempDutyLeaders.includes(name)) {
            showToast('该人员已存在', 'error');
            return;
        }
        tempDutyLeaders.push(name);
    } else {
        if (tempDutyOfficers.includes(name)) {
            showToast('该人员已存在', 'error');
            return;
        }
        tempDutyOfficers.push(name);
    }

    input.value = '';
    renderDutyTags();
    input.focus();
}

// 移除值班人员
function removeDutyPerson(role, index) {
    if (role === 'leader') {
        tempDutyLeaders.splice(index, 1);
    } else {
        tempDutyOfficers.splice(index, 1);
    }
    renderDutyTags();
}

// 保存值班人员
async function saveDutyPersons() {
    try {
        const response = await fetch('/api/duty', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                leaders: tempDutyLeaders,
                officers: tempDutyOfficers
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('值班人员已更新', 'success');
            closeDutyModal();
            loadDutyInfo();
        } else {
            showToast(data.error || '保存失败', 'error');
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}
