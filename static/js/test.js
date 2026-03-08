/**
 * 重构版主页 - 前端逻辑
 * 复用现有 API，精简数据加载
 */

// ==================== 配置 ====================
const CONFIG = {
    refreshInterval: 30000,
    pmtilesUrl: 'https://build.protomaps.com/20250305.pmtiles'
};

// 全局变量
let sourceChart = null;
let keywordChart = null;
let worldMap = null;
let currentTileLayer = null;
let refreshTimer = null;

// 地图源定义（复用现有逻辑）
const MAP_TILE_SOURCES = {
    'carto-dark': {
        name: 'CartoDB 暗色',
        type: 'raster',
        url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?language=zh',
        options: { maxZoom: 19, subdomains: 'abcd' }
    },
    'pmtiles': {
        name: 'Protomaps 矢量暗色',
        type: 'pmtiles',
        url: CONFIG.pmtilesUrl,
        options: { flavor: 'dark', language: 'zh' }
    },
    'osm-dark': {
        name: 'OpenStreetMap 暗色',
        type: 'raster',
        url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        options: { maxZoom: 19, className: 'dark-tiles-invert' }
    },
    'gaode-vec': {
        name: '高德矢量',
        type: 'raster',
        url: 'https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=7',
        options: { maxZoom: 18, subdomains: '1234', className: 'dark-tiles-invert' }
    },
    'gaode-sat': {
        name: '高德卫星',
        type: 'raster',
        url: 'https://webst0{s}.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}',
        options: { maxZoom: 18, subdomains: '1234' }
    },
    'gaode-dark': {
        name: '高德暗色',
        type: 'raster',
        url: 'https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=8&ltype=11',
        options: { maxZoom: 18, subdomains: '1234', className: 'dark-tiles-invert' }
    }
};

// ==================== API 工具 ====================

async function fetchAPI(endpoint) {
    try {
        const response = await fetch(`/api${endpoint}`);
        if (response.status === 401) {
            window.location.href = '/login';
            return null;
        }
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

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function timeAgo(dateStr) {
    if (!dateStr) return '';
    const now = new Date();
    const date = new Date(dateStr);
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return '刚刚';
    if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
    if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
    if (diff < 604800) return Math.floor(diff / 86400) + '天前';
    return date.toLocaleDateString('zh-CN');
}

// ==================== 时钟 ====================

function updateClock() {
    const el = document.getElementById('datetime');
    if (!el) return;
    const now = new Date();
    const weekDays = ['日', '一', '二', '三', '四', '五', '六'];
    el.textContent = now.getFullYear() + '年'
        + (now.getMonth() + 1) + '月' + now.getDate() + '日 '
        + '星期' + weekDays[now.getDay()] + ' '
        + now.toTimeString().slice(0, 8);
}

// ==================== 统计概览 ====================

async function loadOverviewStats() {
    const [overview, realtime] = await Promise.all([
        fetchAPI('/stats/overview'),
        fetchAPI('/stats/realtime')
    ]);

    if (overview) {
        document.getElementById('totalCount').textContent = formatNumber(overview.total_articles);
        document.getElementById('sourceCount').textContent = overview.total_sources;
        document.getElementById('countryCount').textContent = overview.total_countries;
    }

    if (realtime) {
        document.getElementById('todayCount').textContent = formatNumber(realtime.today_count);
    }
}

// ==================== 世界地图 ====================

function applyTileSource(map, sourceId) {
    const src = MAP_TILE_SOURCES[sourceId];
    if (!src) return;

    // 移除旧图层
    if (currentTileLayer) {
        map.removeLayer(currentTileLayer);
        currentTileLayer = null;
    }

    if (src.type === 'pmtiles') {
        try {
            currentTileLayer = protomapsL.leafletLayer({
                url: src.url,
                flavor: src.options.flavor || 'dark',
                language: src.options.language || 'zh'
            });
            currentTileLayer.addTo(map);
        } catch (e) {
            console.warn('PMTiles 加载失败，回退到 CartoDB');
            applyTileSource(map, 'carto-dark');
        }
    } else {
        currentTileLayer = L.tileLayer(src.url, src.options);
        currentTileLayer.addTo(map);
    }

    localStorage.setItem('mapTileSource', sourceId);
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
            zoomControl: true,
            attributionControl: false
        });

        // 加载地图瓦片
        const savedSource = localStorage.getItem('mapTileSource');
        applyTileSource(worldMap, savedSource && MAP_TILE_SOURCES[savedSource] ? savedSource : 'carto-dark');

        // 地图源选择器
        const select = document.getElementById('mapSourceSelect');
        if (select) {
            if (savedSource && select.querySelector(`option[value="${savedSource}"]`)) {
                select.value = savedSource;
            }
            select.addEventListener('change', function () {
                applyTileSource(worldMap, this.value);
            });
        }
    }

    // 清除现有标记
    worldMap.eachLayer(layer => {
        if (layer instanceof L.CircleMarker) {
            worldMap.removeLayer(layer);
        }
    });

    // 计算活跃度阈值
    const counts = data.map(item => item.count).sort((a, b) => a - b);
    const highThreshold = counts[Math.floor(counts.length * 0.7)] || 100;
    const medThreshold = counts[Math.floor(counts.length * 0.3)] || 20;

    data.forEach(item => {
        if (!item.coords || item.coords.length < 2) return;

        let radius, color;
        if (item.count > highThreshold) {
            radius = 7; color = '#06b6d4';
        } else if (item.count > medThreshold) {
            radius = 5; color = '#8b5cf6';
        } else {
            radius = 3.5; color = '#64748b';
        }

        const marker = L.circleMarker([item.coords[0], item.coords[1]], {
            radius: radius,
            fillColor: color,
            fillOpacity: 0.7,
            color: color,
            weight: 1,
            opacity: 0.9
        }).addTo(worldMap);

        const popupContent = `
            <div style="min-width:120px">
                <div style="font-weight:600;margin-bottom:4px">${escapeHtml(item.name)}</div>
                <div style="font-size:12px;color:#94a3b8">
                    文章数: <span style="color:#06b6d4;font-weight:600">${item.count}</span>
                </div>
                ${item.country ? `<div style="font-size:12px;color:#94a3b8">国家: ${escapeHtml(item.country)}</div>` : ''}
            </div>`;
        marker.bindPopup(popupContent);
    });
}

// ==================== 来源分布图 ====================

async function loadSourceChart() {
    const data = await fetchAPI('/stats/sources');
    if (!data || data.length === 0) return;

    const chartDom = document.getElementById('sourceChart');
    if (!sourceChart) {
        sourceChart = echarts.init(chartDom);
    }

    // 按数量排序取前15
    const sortedData = data.sort((a, b) => b.count - a.count).slice(0, 15).reverse();
    const sources = sortedData.map(item => item.source || '未知');
    const counts = sortedData.map(item => item.count);

    sourceChart.setOption({
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            borderColor: 'rgba(148, 163, 184, 0.1)',
            textStyle: { color: '#f1f5f9', fontSize: 12 }
        },
        grid: {
            left: '3%', right: '6%', top: '4%', bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'value',
            axisLabel: { color: '#64748b', fontSize: 10 },
            axisLine: { show: false },
            splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.06)' } }
        },
        yAxis: {
            type: 'category',
            data: sources,
            axisLabel: {
                color: '#94a3b8',
                fontSize: 11,
                width: 80,
                overflow: 'truncate'
            },
            axisLine: { show: false },
            axisTick: { show: false }
        },
        series: [{
            type: 'bar',
            data: counts,
            barWidth: '60%',
            itemStyle: {
                borderRadius: [0, 4, 4, 0],
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                    { offset: 0, color: 'rgba(6, 182, 212, 0.3)' },
                    { offset: 1, color: 'rgba(6, 182, 212, 0.8)' }
                ])
            },
            emphasis: {
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                        { offset: 0, color: 'rgba(6, 182, 212, 0.5)' },
                        { offset: 1, color: '#06b6d4' }
                    ])
                }
            }
        }]
    });
}

// ==================== 最新文章 ====================

async function loadArticles() {
    const data = await fetchAPI('/articles?page=1&page_size=30');
    const listEl = document.getElementById('articleList');
    const countEl = document.getElementById('articleCount');

    if (!data || !data.items || data.items.length === 0) {
        listEl.innerHTML = '<div class="empty-state">暂无文章</div>';
        if (countEl) countEl.textContent = '';
        return;
    }

    if (countEl) countEl.textContent = `共 ${formatNumber(data.total)} 篇`;

    let html = '';
    data.items.forEach(item => {
        const title = escapeHtml(item.title_zh || item.title || '无标题');
        const source = escapeHtml(item.source_name || item.source || '');
        const time = timeAgo(item.pub_date || item.created_at);
        const url = escapeHtml(item.loc || '#');

        html += `
            <a class="article-item" href="${url}" target="_blank" rel="noopener">
                <div class="article-source-badge"></div>
                <div class="article-content">
                    <div class="article-title">${title}</div>
                    <div class="article-meta">
                        <span class="article-source-name">${source}</span>
                        <span>${time}</span>
                    </div>
                </div>
            </a>`;
    });

    listEl.innerHTML = html;
}

// ==================== 风控告警 ====================

async function loadRiskStats() {
    const data = await fetchAPI('/risk/stats?days=3');
    if (!data) return;

    const { summary } = data;
    document.getElementById('riskHigh').textContent = formatNumber(summary.high_total);
    document.getElementById('riskMedium').textContent = formatNumber(summary.medium_total);
    document.getElementById('riskLow').textContent = formatNumber(summary.low_total);

    // 关键词图表
    loadKeywordChart(data.stats);
}

function loadKeywordChart(stats) {
    const chartDom = document.getElementById('keywordChart');
    if (!keywordChart) {
        keywordChart = echarts.init(chartDom);
    }

    if (!stats || stats.length === 0) {
        keywordChart.setOption({
            graphic: {
                type: 'text',
                left: 'center', top: 'center',
                style: { text: '暂无关键词数据', fill: '#64748b', fontSize: 13 }
            }
        });
        return;
    }

    // 取前10个关键词
    const top = stats.slice(0, 10).reverse();
    const keywords = top.map(item => item.keyword);
    const counts = top.map(item => item.count);
    const colors = top.map(item => {
        if (item.level === 'high') return '#ef4444';
        if (item.level === 'medium') return '#f59e0b';
        return '#10b981';
    });

    keywordChart.setOption({
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            borderColor: 'rgba(148, 163, 184, 0.1)',
            textStyle: { color: '#f1f5f9', fontSize: 12 }
        },
        grid: {
            left: '3%', right: '8%', top: '4%', bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'value',
            axisLabel: { color: '#64748b', fontSize: 10 },
            axisLine: { show: false },
            splitLine: { lineStyle: { color: 'rgba(148, 163, 184, 0.06)' } }
        },
        yAxis: {
            type: 'category',
            data: keywords,
            axisLabel: { color: '#94a3b8', fontSize: 11 },
            axisLine: { show: false },
            axisTick: { show: false }
        },
        series: [{
            type: 'bar',
            data: counts.map((val, idx) => ({
                value: val,
                itemStyle: {
                    borderRadius: [0, 4, 4, 0],
                    color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                        { offset: 0, color: colors[idx] + '40' },
                        { offset: 1, color: colors[idx] }
                    ])
                }
            })),
            barWidth: '55%'
        }]
    });
}

async function loadRiskAlerts() {
    const data = await fetchAPI('/risk/alerts?days=3');
    const listEl = document.getElementById('alertList');

    if (!data || data.length === 0) {
        listEl.innerHTML = '<div class="empty-state">暂无风控告警</div>';
        return;
    }

    let html = '';
    data.slice(0, 30).forEach(item => {
        const level = item.level || 'low';
        const keyword = escapeHtml(item.keyword || '');
        const title = escapeHtml(item.title_zh || item.title || '无标题');
        const time = timeAgo(item.pub_date || item.matched_at);
        const url = escapeHtml(item.loc || '#');

        html += `
            <a class="alert-item risk-${level}" href="${url}" target="_blank" rel="noopener">
                <span class="alert-keyword">${keyword}</span>
                <div class="alert-content">
                    <div class="alert-title">${title}</div>
                    <div class="alert-meta">${time}</div>
                </div>
            </a>`;
    });

    listEl.innerHTML = html;
}

// ==================== 初始化与刷新 ====================

async function refreshAll() {
    await Promise.all([
        loadOverviewStats(),
        loadArticles(),
        loadRiskAlerts()
    ]);

    await Promise.all([
        loadSourceChart(),
        loadWorldMap(),
        loadRiskStats()
    ]);
}

function handleResize() {
    if (sourceChart) sourceChart.resize();
    if (keywordChart) keywordChart.resize();
    if (worldMap) worldMap.invalidateSize();
}

// 页面初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 启动时钟
    updateClock();
    setInterval(updateClock, 1000);

    // 加载所有数据
    await refreshAll();

    // 自动刷新
    refreshTimer = setInterval(refreshAll, CONFIG.refreshInterval);

    // 窗口大小变化
    window.addEventListener('resize', handleResize);
});
