/**
 * 全球新闻态势感知平台 - 大屏前端主逻辑
 * 科技风格 / 自动刷新 / 风控监控
 */

// ==================== 全局配置 ====================
const CONFIG = {
    refreshInterval: 30000,  // 自动刷新间隔（毫秒）- 30秒
    alertLimit: 30           // 告警列表数量
};

// 全局变量
let sourceChart = null;
let keywordChart = null;
let worldMap = null;
let refreshTimer = null;
let articleRefreshTimer = null;  // 文章独立快速刷新定时器
let clockTimer = null;           // 顶部时钟定时器
let tgRefreshTimer = null;       // Telegram 模块刷新定时器
let articleRefreshing = false;   // 文章刷新防并发标记

// 风控告警筛选相关
let allAlertsData = [];           // 存储所有告警数据
let currentFilterKeyword = null;  // 当前筛选的关键词
let keywordChartData = [];        // 关键词图表数据

// 国家代码映射（扩展中文名称）
const COUNTRY_NAMES = {
    // 亚洲
    'CN': '中国', 'HK': '香港', 'TW': '台湾', 'MO': '澳门',
    'JP': '日本', 'KR': '韩国', 'KP': '朝鲜',
    'SG': '新加坡', 'MY': '马来西亚', 'TH': '泰国', 'VN': '越南',
    'PH': '菲律宾', 'ID': '印度尼西亚', 'MM': '缅甸', 'KH': '柬埔寨',
    'LA': '老挝', 'BD': '孟加拉国', 'NP': '尼泊尔', 'BT': '不丹',
    'IN': '印度', 'PK': '巴基斯坦', 'AF': '阿富汗', 'LK': '斯里兰卡',
    'KZ': '哈萨克斯坦', 'UZ': '乌兹别克斯坦', 'TM': '土库曼斯坦',
    'KG': '吉尔吉斯斯坦', 'TJ': '塔吉克斯坦', 'MN': '蒙古',
    // 中东
    'IL': '以色列', 'PS': '巴勒斯坦', 'LB': '黎巴嫩', 'SY': '叙利亚',
    'JO': '约旦', 'IQ': '伊拉克', 'IR': '伊朗', 'SA': '沙特阿拉伯',
    'AE': '阿联酋', 'QA': '卡塔尔', 'KW': '科威特', 'BH': '巴林',
    'OM': '阿曼', 'YE': '也门', 'TR': '土耳其',
    // 欧洲
    'GB': '英国', 'FR': '法国', 'DE': '德国', 'IT': '意大利',
    'ES': '西班牙', 'PT': '葡萄牙', 'NL': '荷兰', 'BE': '比利时',
    'CH': '瑞士', 'AT': '奥地利', 'PL': '波兰', 'CZ': '捷克',
    'SK': '斯洛伐克', 'HU': '匈牙利', 'RO': '罗马尼亚', 'BG': '保加利亚',
    'GR': '希腊', 'RS': '塞尔维亚', 'HR': '克罗地亚', 'SI': '斯洛文尼亚',
    'UA': '乌克兰', 'BY': '白俄罗斯', 'RU': '俄罗斯', 'MD': '摩尔多瓦',
    'SE': '瑞典', 'NO': '挪威', 'DK': '丹麦', 'FI': '芬兰',
    'IE': '爱尔兰', 'IS': '冰岛', 'EE': '爱沙尼亚', 'LV': '拉脱维亚',
    'LT': '立陶宛',
    // 北美
    'US': '美国', 'CA': '加拿大', 'MX': '墨西哥',
    // 南美
    'BR': '巴西', 'AR': '阿根廷', 'CL': '智利', 'PE': '秘鲁',
    'CO': '哥伦比亚', 'VE': '委内瑞拉', 'EC': '厄瓜多尔', 'BO': '玻利维亚',
    'PY': '巴拉圭', 'UY': '乌拉圭',
    // 大洋洲
    'AU': '澳大利亚', 'NZ': '新西兰',
    // 非洲
    'ZA': '南非', 'EG': '埃及', 'NG': '尼日利亚', 'KE': '肯尼亚',
    'ET': '埃塞俄比亚', 'MA': '摩洛哥', 'DZ': '阿尔及利亚', 'TN': '突尼斯',
    'LY': '利比亚', 'SD': '苏丹', 'GH': '加纳'
};

// ECharts 科技风格主题配置
const CHART_THEME = {
    color: ['#00f0ff', '#00ff88', '#7b68ee', '#ffa502', '#ff4757'],
    backgroundColor: 'transparent',
    textStyle: { color: 'rgba(255,255,255,0.7)' },
    axisLine: { lineStyle: { color: 'rgba(0,240,255,0.3)' } },
    splitLine: { lineStyle: { color: 'rgba(0,240,255,0.1)' } }
};

// ==================== 统一气泡管理器 ====================
const BubbleManager = {
    // 已注册的气泡配置
    bubbles: {
        'summary': {
            element: null,
            isRunning: false,  // 是否正在运行中（不能完全关闭）
        },
        'crawl': {
            element: null,
            isRunning: false,
        }
    },

    // 初始化
    init() {
        this.bubbles.summary.element = document.getElementById('summaryBubble');
        this.bubbles.crawl.element = document.getElementById('crawlBubble');
    },

    // 显示气泡
    show(bubbleId) {
        const bubble = this.bubbles[bubbleId];
        if (!bubble || !bubble.element) return;

        bubble.element.classList.add('show');
        bubble.element.classList.remove('minimized');
    },

    // 隐藏气泡
    hide(bubbleId) {
        const bubble = this.bubbles[bubbleId];
        if (!bubble || !bubble.element) return;

        bubble.element.classList.remove('show');
    },

    // 关闭气泡（运行中则最小化）
    close(bubbleId) {
        const bubble = this.bubbles[bubbleId];
        if (!bubble || !bubble.element) return;

        if (bubble.isRunning) {
            // 运行中只最小化
            bubble.element.classList.add('minimized');
        } else {
            this.hide(bubbleId);
        }
    },

    // 设置运行状态
    setRunning(bubbleId, isRunning) {
        const bubble = this.bubbles[bubbleId];
        if (bubble) {
            bubble.isRunning = isRunning;
        }
    },

    // 检查是否正在运行
    isRunning(bubbleId) {
        const bubble = this.bubbles[bubbleId];
        return bubble ? bubble.isRunning : false;
    }
};

// ==================== 工具函数 ====================

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

function formatCompactNumber(num) {
    if (num >= 10000) return (num / 10000).toFixed(1) + 'w';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'k';
    return num;
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// ==================== 新闻预览功能 ====================
let currentPreviewController = null;  // 用于取消未完成的请求

/**
 * 打开新闻预览 — 在点击的新闻条目下方展开预览区域
 * @param {string} url - 新闻原始链接
 * @param {HTMLElement} articleEl - 被点击的新闻条目 DOM 元素
 */
function openNewsPreview(url, articleEl) {
    if (!url) return;

    // 检查是否已有预览展开 — 如果点击的是同一条目，则收起
    const existingPreview = articleEl.nextElementSibling;
    if (existingPreview && existingPreview.classList.contains('news-preview-container')) {
        closeNewsPreview(existingPreview);
        return;
    }

    // 关闭其他已展开的预览
    document.querySelectorAll('.news-preview-container').forEach(el => {
        closeNewsPreview(el);
    });

    // 取消之前未完成的请求
    if (currentPreviewController) {
        currentPreviewController.abort();
    }
    currentPreviewController = new AbortController();

    // 创建预览容器
    const container = document.createElement('div');
    container.className = 'news-preview-container';
    container.innerHTML = `
        <div class="news-preview-toolbar">
            <button class="preview-btn preview-open-btn" onclick="window.open('${escapeHtml(url)}', '_blank'); event.stopPropagation();">
                &#128279; 访问原始链接
            </button>
            <button class="preview-btn preview-close-btn" onclick="closeNewsPreview(this.closest('.news-preview-container')); event.stopPropagation();">
                &#10005; 收起
            </button>
        </div>
        <div class="news-preview-loading">
            <div class="spinner"></div>
            正在加载预览...
        </div>
    `;

    // 插入到被点击条目之后
    articleEl.insertAdjacentElement('afterend', container);

    // 触发展开动画（需要延迟以触发 CSS transition）
    requestAnimationFrame(() => {
        container.classList.add('active');
    });

    // 发起 API 请求
    fetch(`/api/news/preview?url=${encodeURIComponent(url)}`, {
        signal: currentPreviewController.signal
    })
    .then(res => res.json())
    .then(data => {
        const loadingEl = container.querySelector('.news-preview-loading');
        if (!loadingEl) return; // 容器已被移除

        if (data.success) {
            loadingEl.outerHTML = `<iframe class="news-preview-iframe" sandbox="allow-same-origin" srcdoc="${escapeHtml(data.data.html)}"></iframe>`;
        } else {
            loadingEl.outerHTML = `
                <div class="news-preview-error">
                    <div class="error-icon">&#9888;</div>
                    <div>无法加载预览内容</div>
                    <div>请点击上方「访问原始链接」查看原文</div>
                </div>
            `;
        }
    })
    .catch(err => {
        if (err.name === 'AbortError') return; // 请求被取消，忽略
        const loadingEl = container.querySelector('.news-preview-loading');
        if (loadingEl) {
            loadingEl.outerHTML = `
                <div class="news-preview-error">
                    <div class="error-icon">&#9888;</div>
                    <div>无法加载预览内容</div>
                    <div>请点击上方「访问原始链接」查看原文</div>
                </div>
            `;
        }
    });
}

/**
 * 关闭预览区域（带动画）
 */
function closeNewsPreview(container) {
    if (!container) return;
    container.classList.remove('active');
    setTimeout(() => {
        container.remove();
    }, 300); // 等待收起动画完成
}

function updateDateTime() {
    const now = new Date();
    const weekDays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'];
    const year = now.getFullYear();
    const month = now.getMonth() + 1;
    const day = now.getDate();
    const weekDay = weekDays[now.getDay()];
    const timeStr = now.toLocaleTimeString('zh-CN', {
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
    document.getElementById('datetime').innerHTML = `${year}年${month}月${day}日${weekDay}<br class="mobile-br"> ${timeStr}`;
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
        // 活跃源使用监控的总新闻源数（与底部一致）
        document.getElementById('activeSources').textContent = overview.total_sources;
    }

    if (realtime) {
        document.getElementById('todayCount').textContent = formatNumber(realtime.today_count);
        document.getElementById('weekCount').textContent = formatNumber(realtime.week_count);
        // 更新时间由 updateRefreshTime() 处理

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

    // 显示所有新闻源（按数量倒序）
    const sortedData = data.sort((a, b) => b.count - a.count).reverse();
    const sources = sortedData.map(item => item.source || '未知');
    const counts = sortedData.map(item => item.count);

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
        dataZoom: [
            {
                type: 'slider',
                yAxisIndex: 0,
                right: 0,
                width: 15,
                start: sortedData.length > 15 ? 100 - (15 / sortedData.length * 100) : 0,
                end: 100,
                showDetail: false,
                borderColor: 'transparent',
                backgroundColor: 'rgba(255,255,255,0.05)',
                fillerColor: 'rgba(0,240,255,0.2)',
                handleStyle: { color: 'rgba(0,240,255,0.5)' }
            }
        ],
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

// ==================== 最新获取文章（无限滚动） ====================

let latestArticlesPage = 1;
let latestArticlesTotal = 0;
let latestArticlesLoading = false;
let latestArticlesHasMore = true;
let latestArticlesInitialized = false;

async function loadLatestArticles(append = false, silent = false) {
    if (latestArticlesLoading) return;

    const listEl = document.getElementById('latestArticlesList');
    const countEl = document.getElementById('latestArticleCount');

    if (!append) {
        latestArticlesPage = 1;
        latestArticlesHasMore = true;
        // 只在首次加载时显示加载提示，无感刷新时不显示
        if (!silent && !latestArticlesInitialized) {
            listEl.innerHTML = '<div class="loading-text">加载中...</div>';
        }
    }

    if (!latestArticlesHasMore) return;

    latestArticlesLoading = true;

    const data = await fetchAPI(`/articles?page=${latestArticlesPage}&page_size=20`);

    latestArticlesLoading = false;

    if (!data || !data.items) {
        if (!append && !latestArticlesInitialized) {
            listEl.innerHTML = '<div class="loading-text">暂无文章</div>';
            countEl.textContent = '0';
        }
        return;
    }

    latestArticlesTotal = data.total;
    countEl.textContent = data.total;

    const articlesHtml = data.items.map(article => {
        const timeStr = article.pub_date ? article.pub_date.split(' ')[1] || article.pub_date.split(' ')[0] : '';
        return `
        <div class="latest-article-item" onclick="openNewsPreview('${escapeHtml(article.url)}', this)">
            <div class="latest-article-title">${escapeHtml(article.title)}</div>
            <div class="latest-article-meta">
                <span class="latest-article-source">${escapeHtml(article.source)}</span>
                <span class="latest-article-time">${timeStr}</span>
            </div>
        </div>
    `}).join('');

    if (append) {
        // 移除加载提示
        const loadingEl = listEl.querySelector('.loading-more');
        if (loadingEl) loadingEl.remove();
        // 追加内容
        listEl.insertAdjacentHTML('beforeend', articlesHtml);
    } else {
        // 无感刷新时保持滚动位置
        const scrollTop = listEl.scrollTop;
        listEl.innerHTML = articlesHtml;
        if (silent && scrollTop > 0) {
            listEl.scrollTop = scrollTop;
        }
    }

    // 检查是否还有更多
    const loadedCount = latestArticlesPage * 20;
    latestArticlesHasMore = loadedCount < data.total;

    latestArticlesPage++;
    latestArticlesInitialized = true;
}

function initLatestArticlesScroll() {
    const listEl = document.getElementById('latestArticlesList');
    if (!listEl) return;

    listEl.addEventListener('scroll', () => {
        if (latestArticlesLoading || !latestArticlesHasMore) return;

        const scrollTop = listEl.scrollTop;
        const scrollHeight = listEl.scrollHeight;
        const clientHeight = listEl.clientHeight;

        // 滚动到底部附近时加载更多
        if (scrollTop + clientHeight >= scrollHeight - 50) {
            // 添加加载提示
            if (!listEl.querySelector('.loading-more')) {
                listEl.insertAdjacentHTML('beforeend', '<div class="loading-more">加载中...</div>');
            }
            loadLatestArticles(true);
        }
    });
}

async function loadWorldMap() {
    const data = await fetchAPI('/map/markers');
    if (!data) return;

    if (!worldMap) {
        const isMobile = window.innerWidth <= 768;
        worldMap = L.map('worldMap', {
            center: isMobile ? [20, 0] : [25, 20],
            zoom: isMobile ? 1 : 2,
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

    // 清除现有标记（包括自定义图层组）
    worldMap.eachLayer(layer => {
        if (layer instanceof L.Marker || layer instanceof L.CircleMarker) {
            worldMap.removeLayer(layer);
        }
    });

    // 计算活跃度阈值（基于数据分布，用于决定点的大小）
    const counts = data.map(item => item.count).sort((a, b) => a - b);
    const highThreshold = counts[Math.floor(counts.length * 0.7)] || 100;
    const medThreshold = counts[Math.floor(counts.length * 0.3)] || 20;

    // 默认颜色配置（非警告色，柔和的科技感配色）
    const normalConfig = {
        high: {
            color: '#7b68ee',      // 紫罗兰 - 高活跃
            glowColor: 'rgba(123, 104, 238, 0.5)',
            size: { min: 12, max: 24 },
            pulseSize: 2.2,
            animationDuration: '3s'
        },
        medium: {
            color: '#00d4aa',      // 青绿色 - 中活跃
            glowColor: 'rgba(0, 212, 170, 0.4)',
            size: { min: 9, max: 18 },
            pulseSize: 2,
            animationDuration: '3.5s'
        },
        low: {
            color: '#4a9eff',      // 天蓝色 - 低活跃
            glowColor: 'rgba(74, 158, 255, 0.35)',
            size: { min: 6, max: 12 },
            pulseSize: 1.8,
            animationDuration: '4s'
        }
    };

    // 风控警告色配置（仅当有风控匹配时使用）
    const riskConfig = {
        high: {
            color: '#ff4757',      // 红色 - 高风险
            glowColor: 'rgba(255, 71, 87, 0.6)',
            size: { min: 14, max: 28 },
            pulseSize: 2.5,
            animationDuration: '1.8s'
        },
        medium: {
            color: '#ffa502',      // 橙色 - 中风险
            glowColor: 'rgba(255, 165, 2, 0.5)',
            size: { min: 11, max: 22 },
            pulseSize: 2.2,
            animationDuration: '2.2s'
        },
        low: {
            color: '#ffd93d',      // 金黄色 - 低风险
            glowColor: 'rgba(255, 217, 61, 0.45)',
            size: { min: 8, max: 16 },
            pulseSize: 2,
            animationDuration: '2.5s'
        }
    };

    // 添加标记
    data.forEach(item => {
        if (!item.coords || item.coords.length !== 2) return;

        const lat = item.coords[1];
        const lng = item.coords[0];
        const count = item.count || 0;
        const riskLevel = item.risk_level;  // 风控等级：null, 'low', 'medium', 'high'
        const riskCount = item.risk_count || 0;

        // 确定活跃度等级（用于大小）
        let activityLevel = 'low';
        if (count >= highThreshold) {
            activityLevel = 'high';
        } else if (count >= medThreshold) {
            activityLevel = 'medium';
        }

        // 根据是否有风控警报决定使用哪套配色
        let config;
        let displayLevel;
        let hasRisk = riskLevel !== null && riskLevel !== undefined;

        if (hasRisk) {
            // 有风控警报，使用警告色，等级由风控等级决定
            config = riskConfig[riskLevel];
            displayLevel = riskLevel;
        } else {
            // 无风控警报，使用默认色，等级由活跃度决定
            config = normalConfig[activityLevel];
            displayLevel = activityLevel;
        }

        // 计算标记大小（在配置范围内根据数量缩放）
        const sizeRange = config.size.max - config.size.min;
        const normalizedCount = Math.min(1, Math.log10(count + 1) / 3);
        const size = config.size.min + sizeRange * normalizedCount;

        // 标记样式类名
        const markerClass = hasRisk ? `map-marker-risk map-marker-risk-${riskLevel}` : `map-marker map-marker-${activityLevel}`;

        // 创建自定义HTML标记（带动效）
        const markerHtml = `
            <div class="${markerClass}" style="--marker-color: ${config.color}; --glow-color: ${config.glowColor}; --pulse-size: ${config.pulseSize}; --animation-duration: ${config.animationDuration};">
                <div class="marker-pulse"></div>
                <div class="marker-core" style="width: ${size}px; height: ${size}px;"></div>
            </div>
        `;

        const icon = L.divIcon({
            html: markerHtml,
            className: 'map-marker-wrapper',
            iconSize: [size * config.pulseSize, size * config.pulseSize],
            iconAnchor: [size * config.pulseSize / 2, size * config.pulseSize / 2]
        });

        const marker = L.marker([lat, lng], { icon: icon }).addTo(worldMap);

        // 绑定弹窗
        const activityText = { high: '高活跃', medium: '中活跃', low: '低活跃' };
        const riskText = { high: '高风险', medium: '中风险', low: '低风险' };

        // 状态标签
        let statusHtml = '';
        if (hasRisk) {
            statusHtml = `<span class="popup-level popup-risk" style="background: ${config.color}20; color: ${config.color};">${riskText[riskLevel]} (${riskCount}条)</span>`;
        } else {
            statusHtml = `<span class="popup-level" style="background: ${config.color}20; color: ${config.color};">${activityText[activityLevel]}</span>`;
        }

        marker.bindPopup(`
            <div class="marker-popup">
                <div class="popup-header" style="border-left-color: ${config.color};">
                    <span class="popup-source">${item.source || '未知'}</span>
                    ${statusHtml}
                </div>
                <div class="popup-body">
                    <div class="popup-row">
                        <span class="popup-label">国家/地区</span>
                        <span class="popup-value">${COUNTRY_NAMES[item.country] || item.country || '-'}</span>
                    </div>
                    <div class="popup-row">
                        <span class="popup-label">文章总数</span>
                        <span class="popup-value popup-count">${formatNumber(count)} 篇</span>
                    </div>
                </div>
            </div>
        `, {
            className: 'custom-popup',
            maxWidth: 220,
            minWidth: 160
        });

        // 鼠标悬停效果
        marker.on('mouseover', function() {
            const el = this.getElement().querySelector('.map-marker, .map-marker-risk');
            if (el) el.classList.add('marker-hover');
        });
        marker.on('mouseout', function() {
            const el = this.getElement().querySelector('.map-marker, .map-marker-risk');
            if (el) el.classList.remove('marker-hover');
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

    // 合并所有关键词并排序（显示全部）
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

    // 显示所有关键词，按数量排序
    const sortedKeywords = allKeywords.sort((a, b) => b.count - a.count);

    // 保存到全局变量
    keywordChartData = sortedKeywords;

    if (sortedKeywords.length === 0) {
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
            left: '3%', right: '8%', top: '5%', bottom: '5%',
            containLabel: true
        },
        dataZoom: sortedKeywords.length > 10 ? [
            {
                type: 'slider',
                yAxisIndex: 0,
                right: 0,
                width: 12,
                start: 100 - (10 / sortedKeywords.length * 100),
                end: 100,
                showDetail: false,
                borderColor: 'transparent',
                backgroundColor: 'rgba(255,255,255,0.05)',
                fillerColor: 'rgba(0,240,255,0.2)',
                handleStyle: { color: 'rgba(0,240,255,0.5)' }
            }
        ] : [],
        xAxis: {
            type: 'value',
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: { show: false },
            splitLine: { show: false }
        },
        yAxis: {
            type: 'category',
            data: sortedKeywords.map(k => k.keyword).reverse(),
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
            data: sortedKeywords.map(k => ({
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

// 标记告警已读
async function markAlertAsRead(url, event) {
    // 阻止事件冒泡到父元素的 onclick
    if (event) {
        event.stopPropagation();
    }

    try {
        const response = await fetch('/api/risk/alerts/read', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: url,
                reader_name: '' // 可以扩展为获取当前值班员姓名
            })
        });

        const result = await response.json();

        if (result.success) {
            // 更新本地数据
            const alertIndex = allAlertsData.findIndex(a => a.url === url);
            if (alertIndex >= 0) {
                allAlertsData[alertIndex].is_read = true;
                allAlertsData[alertIndex].read_at = new Date().toLocaleString('zh-CN', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                }).replace(/\//g, '-');
            }

            // 重新渲染列表
            renderFilteredAlerts();

            // 打开预览
            const alertEl = document.querySelector(`.alert-item[data-url="${url}"]`);
            if (alertEl) {
                openNewsPreview(url, alertEl);
            } else {
                window.open(url, '_blank');
            }
        } else {
            console.error('标记已读失败:', result.error);
            // 即使标记失败也打开链接
            const alertEl = document.querySelector(`.alert-item[data-url="${url}"]`);
            if (alertEl) {
                openNewsPreview(url, alertEl);
            } else {
                window.open(url, '_blank');
            }
        }
    } catch (error) {
        console.error('标记已读请求失败:', error);
        // 即使请求失败也打开链接
        const alertEl = document.querySelector(`.alert-item[data-url="${url}"]`);
        if (alertEl) {
            openNewsPreview(url, alertEl);
        } else {
            window.open(url, '_blank');
        }
    }
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

    alertList.innerHTML = filteredData.map(alert => {
        const isRead = alert.is_read;
        const readClass = isRead ? 'is-read' : '';
        const readBadge = isRead
            ? `<span class="read-badge" title="已读于 ${alert.read_at || ''}">已读</span>`
            : `<span class="unread-badge">未读</span>`;

        return `
        <div class="alert-item ${alert.risk_level} ${readClass}" data-url="${escapeHtml(alert.url)}" onclick="markAlertAsRead('${escapeHtml(alert.url)}', event)">
            <div class="alert-title-row">
                <div class="alert-title">${highlightKeyword(escapeHtml(alert.title), currentFilterKeyword)}</div>
                ${readBadge}
            </div>
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
    `}).join('');
}

// highlightKeyword 定义在搜索模块中（第5015行附近），此处不再重复定义

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

// 上一次数据的摘要（用于检测变化）
let lastDataDigest = {
    totalArticles: 0,
    todayCount: 0,
    alertCount: 0
};

async function loadAllData(silent = false) {
    if (!silent) {
        showRefreshIndicator();
    }

    // 分批加载，避免同时发起太多请求导致卡顿
    // 第一批：关键数据
    await Promise.all([
        loadOverviewStats(),
        loadLatestArticles(false, silent),
        loadRiskAlerts()
    ]);

    // 第二批：图表和地图（稍微延迟以让UI先响应）
    await new Promise(resolve => setTimeout(resolve, 100));

    await Promise.all([
        loadSourceChart(),
        loadWorldMap(),
        loadRiskStats()
    ]);

    // 第三批：次要数据
    await Promise.all([
        loadAchievements(),
        loadDutyInfo()
    ]);

    // 更新刷新时间显示
    updateRefreshTime();
}

// 更新刷新时间
function updateRefreshTime() {
    const updateTimeEl = document.getElementById('updateTime');
    if (updateTimeEl) {
        const now = new Date();
        updateTimeEl.textContent = now.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
}

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    // 静默刷新（不显示加载指示器）
    refreshTimer = setInterval(() => loadAllData(true), CONFIG.refreshInterval);
}

// 文章独立快速刷新（10秒间隔，比全量刷新更频繁）
function startArticleAutoRefresh() {
    if (articleRefreshTimer) clearInterval(articleRefreshTimer);
    articleRefreshTimer = setInterval(() => {
        if (!articleRefreshing) {
            articleRefreshing = true;
            loadLatestArticles(false, true).finally(() => {
                articleRefreshing = false;
            });
        }
    }, 10000);  // 10秒
}

function handleResize() {
    if (sourceChart) sourceChart.resize();
    if (keywordChart) keywordChart.resize();
    if (worldMap) worldMap.invalidateSize();
}

// 页面初始化
document.addEventListener('DOMContentLoaded', async () => {
    // 初始化气泡管理器
    BubbleManager.init();

    // 更新顶部时间
    updateDateTime();
    clockTimer = setInterval(updateDateTime, 1000);

    // 初始化底部刷新时间
    updateRefreshTime();

    // 加载保存的布局配置
    await loadSavedLayout();

    // 加载数据（首次加载显示加载指示器）
    await loadAllData(false);

    // 初始化最新文章滚动加载
    initLatestArticlesScroll();

    // 检查今天是否已有AI总结
    checkTodaySummary();

    // 启动自动刷新
    startAutoRefresh();

    // 启动文章快速刷新（10秒独立刷新最新文章）
    startArticleAutoRefresh();

    // 窗口大小变化
    window.addEventListener('resize', handleResize);

    // 移动端延迟刷新地图尺寸（display:contents布局稳定后）
    setTimeout(() => {
        if (worldMap) worldMap.invalidateSize();
    }, 500);

    // ESC 关闭弹窗
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeKeywordModal();
            closeEditModal();
            closeSitesModal();
            closeAllAlertsModal();
            closeSettingsModal();
            closeCalendar();
            closeSourceArticlesModal();
            closeArticleCalendar();
            closeAchievementModal();
            closeDutyModal();
            closeSummaryModal();
            closeSummaryHistory();
            closeRefsModal();
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

    // 页面可见性变化：隐藏时暂停定时器，可见时恢复
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            // 页面隐藏，暂停所有定时器
            if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
            if (articleRefreshTimer) { clearInterval(articleRefreshTimer); articleRefreshTimer = null; }
            if (clockTimer) { clearInterval(clockTimer); clockTimer = null; }
            if (tgRefreshTimer) { clearInterval(tgRefreshTimer); tgRefreshTimer = null; }
        } else {
            // 页面恢复可见，重新启动定时器
            updateDateTime();
            clockTimer = setInterval(updateDateTime, 1000);
            startAutoRefresh();
            startArticleAutoRefresh();
            // 恢复后立即刷新一次数据
            loadAllData(true);
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


// ==================== 插件管理 ====================

let pluginsData = [];

function openSitesModal() {
    document.getElementById('sitesModal').classList.add('active');
    loadPlugins();
    loadCrawlSchedule();  // 加载定时爬取配置
}

function closeSitesModal() {
    document.getElementById('sitesModal').classList.remove('active');
}

async function loadPlugins() {
    const pluginList = document.getElementById('pluginList');
    pluginList.innerHTML = '<div class="loading-text">加载中...</div>';

    const data = await fetchAPI('/plugins');
    if (data) {
        pluginsData = data;
        renderPlugins();
        updatePluginStats();
    } else {
        pluginList.innerHTML = '<div class="loading-text">加载失败</div>';
    }
}

function updatePluginStats() {
    let enabledCount = 0;
    let totalCount = 0;

    pluginsData.forEach(plugin => {
        plugin.sites.forEach(site => {
            totalCount++;
            if (site.enabled) {
                enabledCount++;
            }
        });
    });

    document.getElementById('enabledCount').textContent = enabledCount;
    document.getElementById('siteTotalCount').textContent = totalCount;
}

function renderPlugins() {
    const pluginList = document.getElementById('pluginList');

    if (pluginsData.length === 0) {
        pluginList.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📦</div>
                <div>暂无可用插件</div>
            </div>
        `;
        return;
    }

    pluginList.innerHTML = pluginsData.map(plugin => {
        const sitesHtml = plugin.sites.map(site => {
            const enabledClass = site.enabled ? 'enabled' : 'disabled';
            const autoUpdateChecked = site.auto_update ? 'checked' : '';
            const intervalMinutes = Math.floor((site.update_interval || 300) / 60);

            return `
            <div class="plugin-site-item ${enabledClass}" data-site-id="${site.id}">
                <div class="site-toggle">
                    <label class="toggle-switch">
                        <input type="checkbox" ${site.enabled ? 'checked' : ''}
                               onchange="toggleSite('${plugin.id}', '${site.id}', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="site-info">
                    <div class="site-name">${escapeHtml(site.name)}</div>
                    <div class="site-url">${escapeHtml(site.url || '')}</div>
                </div>
                <div class="site-meta">
                    <span class="site-country">${site.country_code || '未知'}</span>
                </div>
                <div class="site-auto-update ${site.enabled ? '' : 'hidden'}">
                    <label class="auto-update-label" title="定时自动更新">
                        <input type="checkbox" ${autoUpdateChecked}
                               onchange="toggleAutoUpdate('${plugin.id}', '${site.id}', this.checked)"
                               ${site.enabled ? '' : 'disabled'}>
                        <span class="auto-update-text">定时</span>
                    </label>
                    <select class="interval-select ${site.auto_update ? '' : 'hidden'}"
                            onchange="setUpdateInterval('${plugin.id}', '${site.id}', this.value)"
                            ${site.enabled && site.auto_update ? '' : 'disabled'}>
                        <option value="5" ${intervalMinutes === 5 ? 'selected' : ''}>5分钟</option>
                        <option value="10" ${intervalMinutes === 10 ? 'selected' : ''}>10分钟</option>
                        <option value="15" ${intervalMinutes === 15 ? 'selected' : ''}>15分钟</option>
                        <option value="30" ${intervalMinutes === 30 ? 'selected' : ''}>30分钟</option>
                        <option value="60" ${intervalMinutes === 60 ? 'selected' : ''}>1小时</option>
                        <option value="120" ${intervalMinutes === 120 ? 'selected' : ''}>2小时</option>
                        <option value="360" ${intervalMinutes === 360 ? 'selected' : ''}>6小时</option>
                        <option value="720" ${intervalMinutes === 720 ? 'selected' : ''}>12小时</option>
                        <option value="1440" ${intervalMinutes === 1440 ? 'selected' : ''}>24小时</option>
                    </select>
                </div>
            </div>
            `;
        }).join('');

        return `
        <div class="plugin-card">
            <div class="plugin-header" onclick="togglePluginExpand('${plugin.id}')">
                <div class="plugin-icon">📦</div>
                <div class="plugin-info">
                    <div class="plugin-name">${escapeHtml(plugin.name)}</div>
                    <div class="plugin-desc">${escapeHtml(plugin.description || '')}</div>
                </div>
                <div class="plugin-stats">
                    <span class="enabled-count">${plugin.enabled_count}/${plugin.site_count}</span>
                </div>
                <div class="plugin-expand-icon" id="expand-icon-${plugin.id}">▼</div>
            </div>
            <div class="plugin-sites" id="plugin-sites-${plugin.id}" style="display: none;">
                ${sitesHtml}
            </div>
        </div>
        `;
    }).join('');
}

function togglePluginExpand(pluginId) {
    const sitesDiv = document.getElementById(`plugin-sites-${pluginId}`);
    const iconDiv = document.getElementById(`expand-icon-${pluginId}`);

    if (sitesDiv.style.display === 'none') {
        sitesDiv.style.display = 'block';
        iconDiv.textContent = '▲';
    } else {
        sitesDiv.style.display = 'none';
        iconDiv.textContent = '▼';
    }
}

async function toggleSite(pluginId, siteId, enabled) {
    try {
        const response = await fetch(`/api/plugins/${pluginId}/sites/${siteId}/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });

        const data = await response.json();

        if (data.success) {
            // 更新本地数据
            pluginsData.forEach(plugin => {
                if (plugin.id === pluginId) {
                    plugin.sites.forEach(site => {
                        if (site.id === siteId) {
                            site.enabled = enabled;
                            // 禁用站点时同时禁用定时更新
                            if (!enabled) {
                                site.auto_update = false;
                            }
                        }
                    });
                    // 重新计算启用数量
                    plugin.enabled_count = plugin.sites.filter(s => s.enabled).length;
                }
            });

            // 更新统计和UI
            updatePluginStats();

            // 重新渲染以更新定时更新控件状态
            renderPlugins();
            // 重新展开当前插件
            const sitesDiv = document.getElementById(`plugin-sites-${pluginId}`);
            if (sitesDiv) {
                sitesDiv.style.display = 'block';
                const iconDiv = document.getElementById(`expand-icon-${pluginId}`);
                if (iconDiv) iconDiv.textContent = '▲';
            }

            showToast(enabled ? '已启用' : '已禁用', 'success');
        } else {
            showToast(data.error || '操作失败', 'error');
            loadPlugins();
        }
    } catch (error) {
        showToast('网络错误', 'error');
        loadPlugins();
    }
}

async function toggleAutoUpdate(pluginId, siteId, autoUpdate) {
    try {
        const response = await fetch(`/api/plugins/${pluginId}/sites/${siteId}/auto-update`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ auto_update: autoUpdate })
        });

        const data = await response.json();

        if (data.success) {
            // 更新本地数据
            pluginsData.forEach(plugin => {
                if (plugin.id === pluginId) {
                    plugin.sites.forEach(site => {
                        if (site.id === siteId) {
                            site.auto_update = autoUpdate;
                            if (data.data && data.data.update_interval) {
                                site.update_interval = data.data.update_interval;
                            }
                        }
                    });
                }
            });

            // 更新间隔选择器的显示状态
            const siteItem = document.querySelector(`.plugin-site-item[data-site-id="${siteId}"]`);
            if (siteItem) {
                const intervalSelect = siteItem.querySelector('.interval-select');
                if (intervalSelect) {
                    if (autoUpdate) {
                        intervalSelect.classList.remove('hidden');
                        intervalSelect.disabled = false;
                    } else {
                        intervalSelect.classList.add('hidden');
                        intervalSelect.disabled = true;
                    }
                }
            }

            showToast(autoUpdate ? '定时更新已启用' : '定时更新已禁用', 'success');
        } else {
            showToast(data.error || '操作失败', 'error');
            loadPlugins();
        }
    } catch (error) {
        showToast('网络错误', 'error');
        loadPlugins();
    }
}

async function setUpdateInterval(pluginId, siteId, minutes) {
    const intervalSeconds = parseInt(minutes) * 60;

    try {
        const response = await fetch(`/api/plugins/${pluginId}/sites/${siteId}/auto-update`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                auto_update: true,
                update_interval: intervalSeconds
            })
        });

        const data = await response.json();

        if (data.success) {
            // 更新本地数据
            pluginsData.forEach(plugin => {
                if (plugin.id === pluginId) {
                    plugin.sites.forEach(site => {
                        if (site.id === siteId) {
                            site.update_interval = intervalSeconds;
                        }
                    });
                }
            });

            showToast(`更新间隔已设为 ${minutes} 分钟`, 'success');
        } else {
            showToast(data.error || '操作失败', 'error');
            loadPlugins();
        }
    } catch (error) {
        showToast('网络错误', 'error');
        loadPlugins();
    }
}


// ==================== 更新文章功能（后台任务 + 轮询进度） ====================

let crawlTaskId = null;
let crawlPollingTimer = null;
let crawlStats = { success: 0, failed: 0, skipped: 0, articles: 0, saved: 0 };

// 兼容旧代码的 crawlIsRunning 访问
Object.defineProperty(window, 'crawlIsRunning', {
    get: () => BubbleManager.isRunning('crawl'),
    set: (val) => BubbleManager.setRunning('crawl', val)
});

async function startCrawlUpdate() {
    if (BubbleManager.isRunning('crawl')) {
        showToast('更新正在进行中', 'warning');
        showCrawlBubble();
        return;
    }

    // 重置状态
    BubbleManager.setRunning('crawl', true);
    crawlTaskId = null;
    crawlStats = { success: 0, failed: 0, skipped: 0, articles: 0, saved: 0 };

    // 显示气泡
    showCrawlBubble();
    updateBubbleProgress(0, 0);
    updateBubbleStatus('正在启动任务...');
    updateBubbleCurrentSite('');
    document.getElementById('bubbleDetails').innerHTML = '';

    // 显示取消按钮
    showCancelButton(true);

    // 禁用按钮
    const btn = document.getElementById('btnStartCrawl');
    if (btn) {
        btn.querySelector('.btn-text').style.display = 'none';
        btn.querySelector('.btn-loading').style.display = 'inline';
        btn.disabled = true;
    }

    try {
        // 启动后台任务
        const response = await fetch('/api/crawl/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || '启动任务失败');
        }

        if (!result.data.task_id) {
            // 没有站点
            BubbleManager.setRunning('crawl', false);
            resetCrawlButton();
            updateBubbleStatus(result.data.message || '没有启用的站点', 'warning');
            showCancelButton(false);
            setTimeout(() => hideCrawlBubble(), 3000);
            return;
        }

        crawlTaskId = result.data.task_id;
        updateBubbleStatus(`任务已启动，共 ${result.data.total_sites} 个站点`);
        updateBubbleProgress(0, result.data.total_sites);

        // 开始轮询状态
        startPolling();

    } catch (error) {
        BubbleManager.setRunning('crawl', false);
        resetCrawlButton();
        showCancelButton(false);
        updateBubbleStatus(`启动失败: ${error.message}`, 'error');
        showToast(error.message, 'error');
    }
}

function startPolling() {
    // 每2秒轮询一次
    crawlPollingTimer = setInterval(pollCrawlStatus, 2000);
    // 立即执行一次
    pollCrawlStatus();
}

function stopPolling() {
    if (crawlPollingTimer) {
        clearInterval(crawlPollingTimer);
        crawlPollingTimer = null;
    }
}

async function pollCrawlStatus() {
    if (!crawlTaskId) return;

    try {
        const response = await fetch(`/api/crawl/status?task_id=${crawlTaskId}`);
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || '获取状态失败');
        }

        const status = result.data;
        handleStatusUpdate(status);

    } catch (error) {
        console.error('轮询状态失败:', error);
        // 不停止轮询，可能是临时网络问题
    }
}

function handleStatusUpdate(status) {
    // 更新进度
    updateBubbleProgress(status.completed_sites, status.total_sites);

    // 更新统计
    crawlStats.success = status.success_count;
    crawlStats.failed = status.failed_count;
    crawlStats.skipped = status.skipped_count || 0;
    crawlStats.articles = status.total_articles;
    crawlStats.saved = status.total_saved;

    // 显示当前正在爬取的站点
    if (status.status === 'running' && status.current_site) {
        updateBubbleCurrentSite(status.current_site);
    } else {
        updateBubbleCurrentSite('');
    }

    // 更新状态文本 - 显示详细统计
    if (status.status === 'running') {
        let parts = [`已完成 ${status.completed_sites}/${status.total_sites}`];
        if (status.success_count > 0) parts.push(`${status.success_count}成功`);
        if (status.skipped_count > 0) parts.push(`${status.skipped_count}跳过`);
        if (status.failed_count > 0) parts.push(`${status.failed_count}失败`);
        if (status.total_saved > 0) parts.push(`${status.total_saved}篇入库`);
        updateBubbleStatus(parts.join('  '));
    } else {
        updateBubbleStatus(status.message || '处理中...');
    }

    // 检查任务是否结束
    if (status.status === 'completed') {
        onCrawlComplete(status);
    } else if (status.status === 'failed') {
        onCrawlFailed(status);
    } else if (status.status === 'cancelled') {
        onCrawlCancelled(status);
    }
}

function onCrawlComplete(status) {
    stopPolling();
    BubbleManager.setRunning('crawl', false);
    resetCrawlButton();
    showCancelButton(false);
    updateBubbleCurrentSite('');

    updateBubbleProgress(status.total_sites, status.total_sites);

    // 构建完成消息
    let msgParts = [`${status.success_count}成功`];
    if (status.skipped_count > 0) {
        msgParts.push(`${status.skipped_count}跳过`);
    }
    if (status.failed_count > 0) {
        msgParts.push(`${status.failed_count}失败`);
    }
    msgParts.push(`保存${status.total_saved}篇`);

    updateBubbleStatus(
        `完成: ${msgParts.join(' ')}`,
        'success'
    );

    // 延迟刷新数据
    setTimeout(() => loadAllData(true), 500);

    // 5秒后自动隐藏气泡
    setTimeout(() => {
        if (!BubbleManager.isRunning('crawl')) {
            hideCrawlBubble();
        }
    }, 5000);

    showToast(`更新完成，保存了 ${status.total_saved} 篇文章`, 'success');
}

function onCrawlFailed(status) {
    stopPolling();
    BubbleManager.setRunning('crawl', false);
    resetCrawlButton();
    showCancelButton(false);
    updateBubbleCurrentSite('');

    updateBubbleStatus(`任务失败: ${status.error || '未知错误'}`, 'error');
    showToast('更新任务失败', 'error');
}

function onCrawlCancelled(status) {
    stopPolling();
    BubbleManager.setRunning('crawl', false);
    resetCrawlButton();
    showCancelButton(false);
    updateBubbleCurrentSite('');

    updateBubbleStatus('任务已取消', 'warning');
    showToast('更新任务已取消', 'info');

    // 3秒后隐藏气泡
    setTimeout(() => hideCrawlBubble(), 3000);
}

async function cancelCrawlTask() {
    if (!crawlTaskId || !BubbleManager.isRunning('crawl')) {
        return;
    }

    try {
        updateBubbleStatus('正在取消...');

        const response = await fetch('/api/crawl/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ task_id: crawlTaskId })
        });
        const result = await response.json();

        if (!result.success) {
            showToast(result.error || '取消失败', 'error');
        }
        // 状态更新会通过轮询自动处理

    } catch (error) {
        showToast('取消请求失败', 'error');
    }
}

function showCrawlBubble() {
    BubbleManager.show('crawl');
}

function hideCrawlBubble() {
    BubbleManager.hide('crawl');
}

function closeCrawlBubble() {
    BubbleManager.close('crawl');
}

function showCancelButton(show) {
    const footer = document.getElementById('bubbleFooter');
    if (footer) {
        footer.style.display = show ? 'block' : 'none';
    }
}

function updateBubbleCurrentSite(siteName) {
    const el = document.getElementById('bubbleCurrentSite');
    if (el) {
        el.textContent = siteName ? `正在获取: ${siteName}` : '';
    }
}

function updateBubbleProgress(completed, total) {
    const percent = total > 0 ? (completed / total) * 100 : 0;
    document.getElementById('bubbleProgressFill').style.width = `${percent}%`;
    document.getElementById('bubbleProgressText').textContent = `${completed}/${total}`;
}

function updateBubbleStatus(text, type = '') {
    const statusEl = document.getElementById('bubbleStatus');
    statusEl.textContent = text;
    statusEl.className = 'bubble-status' + (type ? ` ${type}` : '');
}

function addBubbleDetail(name, success, status) {
    const detailsEl = document.getElementById('bubbleDetails');
    const itemHtml = `
        <div class="bubble-detail-item ${success ? 'success' : 'failed'}">
            <span class="detail-name">${escapeHtml(name)}</span>
            <span class="detail-status">${escapeHtml(status)}</span>
        </div>
    `;

    // 插入到顶部
    detailsEl.insertAdjacentHTML('afterbegin', itemHtml);

    // 只保留最近10条
    const items = detailsEl.querySelectorAll('.bubble-detail-item');
    if (items.length > 10) {
        items[items.length - 1].remove();
    }
}

function resetCrawlButton() {
    const btn = document.getElementById('btnStartCrawl');
    if (btn) {
        btn.querySelector('.btn-text').style.display = 'inline';
        btn.querySelector('.btn-loading').style.display = 'none';
        btn.disabled = false;
    }
}

// ==================== 定时全量爬取设置 ====================

async function loadCrawlSchedule() {
    /**
     * 加载定时全量爬取配置并更新UI
     */
    try {
        const response = await fetch('/api/crawl/schedule');
        const result = await response.json();

        if (result.success && result.data) {
            const config = result.data.config || {};
            const enabled = config.enabled || false;
            const interval = config.interval_minutes || 30;

            // 更新开关状态
            const checkbox = document.getElementById('autoCrawlEnabled');
            if (checkbox) {
                checkbox.checked = enabled;
            }

            // 更新间隔选择
            const select = document.getElementById('autoCrawlInterval');
            if (select) {
                select.value = interval.toString();
                select.disabled = !enabled;
            }
        }
    } catch (error) {
        console.error('加载定时爬取配置失败:', error);
    }
}

async function toggleAutoCrawl() {
    /**
     * 切换定时爬取开关
     */
    const checkbox = document.getElementById('autoCrawlEnabled');
    const select = document.getElementById('autoCrawlInterval');
    const enabled = checkbox.checked;
    const interval = parseInt(select.value) || 30;

    // 更新间隔选择框状态
    select.disabled = !enabled;

    try {
        const response = await fetch('/api/crawl/schedule', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                enabled: enabled,
                interval_minutes: interval
            })
        });
        const result = await response.json();

        if (result.success) {
            showToast(result.data.message || (enabled ? '定时爬取已启用' : '定时爬取已禁用'), 'success');
        } else {
            throw new Error(result.error || '保存失败');
        }
    } catch (error) {
        // 回滚UI状态
        checkbox.checked = !enabled;
        select.disabled = enabled;
        showToast('保存定时设置失败: ' + error.message, 'error');
    }
}

async function saveAutoCrawlInterval() {
    /**
     * 保存定时爬取间隔
     */
    const checkbox = document.getElementById('autoCrawlEnabled');
    const select = document.getElementById('autoCrawlInterval');

    // 如果未启用，不需要保存
    if (!checkbox.checked) return;

    const interval = parseInt(select.value) || 30;

    try {
        const response = await fetch('/api/crawl/schedule', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                enabled: true,
                interval_minutes: interval
            })
        });
        const result = await response.json();

        if (result.success) {
            showToast(`定时爬取间隔已设为 ${interval} 分钟`, 'success');
        } else {
            throw new Error(result.error || '保存失败');
        }
    } catch (error) {
        showToast('保存间隔设置失败: ' + error.message, 'error');
    }
}

// 保留旧的弹窗函数以兼容（但不再使用）
function openCrawlProgressModal() {
    showCrawlBubble();
}

function closeCrawlProgressModal() {
    closeCrawlBubble();
}


// ==================== 一键检测（已废弃） ====================

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
        const isRead = alert.is_read;
        const readClass = isRead ? 'is-read' : '';
        const readBadge = isRead
            ? `<span class="read-badge" title="已读于 ${alert.read_at || ''}">已读</span>`
            : `<span class="unread-badge">未读</span>`;

        return `
        <div class="full-alert-item ${alert.risk_level} ${readClass}" data-url="${escapeHtml(alert.url)}" onclick="markFullAlertAsRead('${escapeHtml(alert.url)}', event)">
            <div class="alert-date">
                <span class="date">${dateStr}</span>
                <span class="time">${timeStr}</span>
            </div>
            <div class="alert-content">
                <div class="alert-title-row">
                    <div class="alert-title">${escapeHtml(alert.title)}</div>
                    ${readBadge}
                </div>
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

// 标记全部告警列表中的告警已读
async function markFullAlertAsRead(url, event) {
    if (event) {
        event.stopPropagation();
    }

    try {
        const response = await fetch('/api/risk/alerts/read', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                url: url,
                reader_name: ''
            })
        });

        const result = await response.json();

        if (result.success) {
            // 更新全部告警列表数据
            const alertIndex = fullAlertsData.findIndex(a => a.url === url);
            if (alertIndex >= 0) {
                fullAlertsData[alertIndex].is_read = true;
                fullAlertsData[alertIndex].read_at = new Date().toLocaleString('zh-CN', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                }).replace(/\//g, '-');
            }

            // 同步更新主页告警列表数据
            const mainAlertIndex = allAlertsData.findIndex(a => a.url === url);
            if (mainAlertIndex >= 0) {
                allAlertsData[mainAlertIndex].is_read = true;
                allAlertsData[mainAlertIndex].read_at = fullAlertsData[alertIndex]?.read_at || '';
            }

            // 重新渲染两个列表
            renderFullAlerts();
            renderFilteredAlerts();

            // 打开预览
            const alertEl2 = document.querySelector(`.full-alert-item[data-url="${url}"]`);
            if (alertEl2) {
                openNewsPreview(url, alertEl2);
            } else {
                window.open(url, '_blank');
            }
        } else {
            console.error('标记已读失败:', result.error);
            const alertEl2 = document.querySelector(`.full-alert-item[data-url="${url}"]`);
            if (alertEl2) {
                openNewsPreview(url, alertEl2);
            } else {
                window.open(url, '_blank');
            }
        }
    } catch (error) {
        console.error('标记已读请求失败:', error);
        const alertEl2 = document.querySelector(`.full-alert-item[data-url="${url}"]`);
        if (alertEl2) {
            openNewsPreview(url, alertEl2);
        } else {
            window.open(url, '_blank');
        }
    }
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


// ==================== 更新文章功能（已移除，由插件独立实现） ====================


// ==================== 系统设置 ====================

let providersData = {};

function openSettingsModal() {
    document.getElementById('settingsModal').classList.add('active');
    loadSettings();
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.remove('active');
}

// 修改密码
async function changePassword() {
    const oldPwd = document.getElementById('oldPassword').value;
    const newPwd = document.getElementById('newPassword').value;
    const confirmPwd = document.getElementById('confirmPassword').value;

    if (!oldPwd || !newPwd || !confirmPwd) {
        showToast('请填写所有密码字段', 'error');
        return;
    }
    if (newPwd.length < 6) {
        showToast('新密码长度至少6位', 'error');
        return;
    }
    if (newPwd !== confirmPwd) {
        showToast('两次输入的新密码不一致', 'error');
        return;
    }

    try {
        const response = await fetch('/api/auth/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_password: oldPwd, new_password: newPwd })
        });
        const result = await response.json();
        if (result.success) {
            showToast('密码修改成功', 'success');
            document.getElementById('oldPassword').value = '';
            document.getElementById('newPassword').value = '';
            document.getElementById('confirmPassword').value = '';
        } else {
            showToast(result.error || '密码修改失败', 'error');
        }
    } catch (e) {
        showToast('网络错误', 'error');
    }
}

// 保存各提供商的状态数据
let providersStatusData = {};

async function loadSettings() {
    const data = await fetchAPI('/settings');
    if (!data) return;

    // 保存提供商数据
    providersData = data.providers || {};

    // LLM 设置
    if (data.llm) {
        const provider = data.llm.provider || 'siliconflow';

        // 保存各提供商的状态
        providersStatusData = data.llm.providers_status || {};

        document.getElementById('llmProvider').value = provider;

        // 获取当前提供商的状态
        const providerStatus = providersStatusData[provider] || {};
        document.getElementById('llmApiUrl').value = providerStatus.api_url || data.llm.api_url || '';
        document.getElementById('llmApiKey').value = '';
        document.getElementById('llmApiKey').placeholder = providerStatus.api_key_set ? '已配置（输入新值覆盖）' : 'sk-...';

        // 更新模型列表
        updateModelOptions(provider, data.llm.model);

        // 更新状态
        const statusEl = document.getElementById('llmStatus');
        if (providerStatus.api_key_set) {
            statusEl.textContent = '已配置';
            statusEl.className = 'section-status configured';
        } else {
            statusEl.textContent = '未配置';
            statusEl.className = 'section-status not-configured';
        }

        // 显示遮蔽的 Key
        const hintEl = document.getElementById('llmKeyHint');
        if (providerStatus.api_key_masked) {
            hintEl.textContent = `当前: ${providerStatus.api_key_masked}`;
        } else {
            hintEl.textContent = '';
        }
    }

    // 加载 AI 总结提示词
    await loadSummaryPrompt();

    // 加载翻译设置
    await loadTranslationSettings();
}

// 加载 AI 总结提示词
async function loadSummaryPrompt() {
    try {
        const response = await fetch('/api/summary/prompt');
        const result = await response.json();

        if (result.success && result.data) {
            const textarea = document.getElementById('summaryPrompt');
            if (textarea) {
                // 显示当前提示词（自定义或默认）
                textarea.value = result.data.prompt || result.data.default_prompt || '';
                // 保存默认提示词以便恢复
                textarea.dataset.defaultPrompt = result.data.default_prompt || '';
            }
        }
    } catch (error) {
        console.error('加载提示词失败:', error);
    }
}

// 恢复默认提示词
async function resetPromptToDefault() {
    const textarea = document.getElementById('summaryPrompt');
    if (!textarea) return;

    // 如果已经有缓存的默认提示词，直接使用
    if (textarea.dataset.defaultPrompt) {
        textarea.value = textarea.dataset.defaultPrompt;
        showToast('已恢复默认提示词，请保存设置', 'info');
        return;
    }

    // 否则从服务器获取
    try {
        const response = await fetch('/api/summary/prompt');
        const result = await response.json();

        if (result.success && result.data && result.data.default_prompt) {
            textarea.value = result.data.default_prompt;
            textarea.dataset.defaultPrompt = result.data.default_prompt;
            showToast('已恢复默认提示词，请保存设置', 'info');
        } else {
            showToast('获取默认提示词失败', 'error');
        }
    } catch (error) {
        console.error('获取默认提示词失败:', error);
        showToast('获取默认提示词失败', 'error');
    }
}

function onProviderChange() {
    const provider = document.getElementById('llmProvider').value;
    const providerConfig = providersData[provider];
    const providerStatus = providersStatusData[provider] || {};

    // 更新 API URL（优先使用已保存的，否则使用默认）
    const apiUrl = providerStatus.api_url || (providerConfig ? providerConfig.api_url : '');
    document.getElementById('llmApiUrl').value = apiUrl;

    // 更新 API Key 提示
    document.getElementById('llmApiKey').value = '';
    document.getElementById('llmApiKey').placeholder = providerStatus.api_key_set ? '已配置（输入新值覆盖）' : 'sk-...';

    // 更新状态显示
    const statusEl = document.getElementById('llmStatus');
    if (providerStatus.api_key_set) {
        statusEl.textContent = '已配置';
        statusEl.className = 'section-status configured';
    } else {
        statusEl.textContent = '未配置';
        statusEl.className = 'section-status not-configured';
    }

    // 显示遮蔽的 Key
    const hintEl = document.getElementById('llmKeyHint');
    if (providerStatus.api_key_masked) {
        hintEl.textContent = `当前: ${providerStatus.api_key_masked}`;
    } else {
        hintEl.textContent = '';
    }

    // 更新模型列表
    if (providerConfig) {
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
        // 保存 LLM 设置
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        const data = await response.json();

        if (!data.success) {
            showToast(data.error || '保存LLM设置失败', 'error');
            return;
        }

        // 保存 AI 总结提示词
        const promptSaved = await saveSummaryPrompt();

        // 保存翻译设置
        const translationSaved = await saveTranslationSettings();

        // 保存翻译提示词
        const translationPromptSaved = await saveTranslationPrompt();

        if (promptSaved && translationSaved && translationPromptSaved) {
            showToast('设置已保存', 'success');
            closeSettingsModal();
        }
    } catch (error) {
        showToast('网络错误', 'error');
    }
}

// 保存 AI 总结提示词
async function saveSummaryPrompt() {
    const textarea = document.getElementById('summaryPrompt');
    if (!textarea) return true;

    const customPrompt = textarea.value.trim();
    const defaultPrompt = textarea.dataset.defaultPrompt || '';

    // 如果与默认相同，则清空自定义（使用默认）
    const promptToSave = customPrompt === defaultPrompt ? '' : customPrompt;

    try {
        const response = await fetch('/api/summary/prompt', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: promptToSave })
        });

        const data = await response.json();

        if (!data.success) {
            showToast(data.error || '保存提示词失败', 'error');
            return false;
        }

        return true;
    } catch (error) {
        console.error('保存提示词失败:', error);
        showToast('保存提示词失败', 'error');
        return false;
    }
}

async function testLLMConnection() {
    const btn = document.getElementById('btnTestLLM');
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');

    const provider = document.getElementById('llmProvider').value;
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
                provider: provider,
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


// ==================== 翻译设置 ====================

let translationProvidersStatusData = {};

// 加载翻译设置
async function loadTranslationSettings() {
    try {
        const response = await fetch('/api/translation/settings');
        const result = await response.json();

        if (!result.success || !result.data) return;

        const data = result.data;

        if (data.translation) {
            const provider = data.translation.provider || 'siliconflow';

            // 保存各提供商的状态
            translationProvidersStatusData = data.translation.providers_status || {};

            document.getElementById('translationProvider').value = provider;

            // 获取当前提供商的状态
            const providerStatus = translationProvidersStatusData[provider] || {};

            // 如果翻译没有配置URL，从LLM配置同步
            let apiUrl = providerStatus.api_url || data.translation.api_url || '';
            if (!apiUrl && providersData[provider]) {
                apiUrl = providersData[provider].api_url || '';
            }
            document.getElementById('translationApiUrl').value = apiUrl;

            document.getElementById('translationApiKey').value = '';
            document.getElementById('translationApiKey').placeholder = providerStatus.api_key_set ? '已配置（输入新值覆盖）' : 'sk-...';

            // 更新模型列表（使用全局的 providersData）
            updateTranslationModelOptions(provider, data.translation.model);

            // 更新状态
            const statusEl = document.getElementById('translationStatus');
            if (providerStatus.api_key_set) {
                statusEl.textContent = '已配置';
                statusEl.className = 'section-status configured';
            } else {
                statusEl.textContent = '未配置';
                statusEl.className = 'section-status not-configured';
            }

            // 显示遮蔽的 Key
            const hintEl = document.getElementById('translationKeyHint');
            if (providerStatus.api_key_masked) {
                hintEl.textContent = `当前: ${providerStatus.api_key_masked}`;
            } else {
                hintEl.textContent = '';
            }
        }

        // 加载翻译提示词
        await loadTranslationPrompt();
    } catch (error) {
        console.error('加载翻译设置失败:', error);
    }
}

// 加载翻译提示词
async function loadTranslationPrompt() {
    try {
        const response = await fetch('/api/translation/prompt');
        const result = await response.json();

        if (result.success && result.data) {
            const textarea = document.getElementById('translationPrompt');
            if (textarea) {
                textarea.value = result.data.prompt || result.data.default_prompt || '';
                textarea.dataset.defaultPrompt = result.data.default_prompt || '';
            }
        }
    } catch (error) {
        console.error('加载翻译提示词失败:', error);
    }
}

// 翻译提供商切换
function onTranslationProviderChange() {
    const provider = document.getElementById('translationProvider').value;

    // 获取该提供商已保存的配置
    const savedStatus = translationProvidersStatusData[provider] || {};

    // 更新 API URL（优先使用翻译配置，否则从LLM配置同步）
    if (savedStatus.api_url) {
        document.getElementById('translationApiUrl').value = savedStatus.api_url;
    } else if (providersData[provider]) {
        document.getElementById('translationApiUrl').value = providersData[provider].api_url || '';
    }

    // 更新 Key 提示
    document.getElementById('translationApiKey').value = '';
    document.getElementById('translationApiKey').placeholder = savedStatus.api_key_set ? '已配置（输入新值覆盖）' : 'sk-...';

    const hintEl = document.getElementById('translationKeyHint');
    if (savedStatus.api_key_masked) {
        hintEl.textContent = `当前: ${savedStatus.api_key_masked}`;
    } else {
        hintEl.textContent = '';
    }

    // 更新模型列表（使用全局的 providersData）
    updateTranslationModelOptions(provider);

    // 更新状态
    const statusEl = document.getElementById('translationStatus');
    if (savedStatus.api_key_set) {
        statusEl.textContent = '已配置';
        statusEl.className = 'section-status configured';
    } else {
        statusEl.textContent = '未配置';
        statusEl.className = 'section-status not-configured';
    }
}

// 更新翻译模型选项（使用全局 providersData）
function updateTranslationModelOptions(provider, selectedModel = null) {
    const modelSelect = document.getElementById('translationModel');
    modelSelect.innerHTML = '';

    // 使用全局的 providersData（与LLM配置共享）
    const providerInfo = providersData[provider];
    if (providerInfo && providerInfo.models && providerInfo.models.length > 0) {
        providerInfo.models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.id;
            option.textContent = model.name;
            modelSelect.appendChild(option);
        });
    } else if (provider === 'custom') {
        const option = document.createElement('option');
        option.value = selectedModel || '';
        option.textContent = selectedModel || '请输入模型名称';
        modelSelect.appendChild(option);
    }

    if (selectedModel) {
        modelSelect.value = selectedModel;
    }
}

// 保存翻译设置
async function saveTranslationSettings() {
    const settings = {
        translation: {
            provider: document.getElementById('translationProvider').value,
            api_url: document.getElementById('translationApiUrl').value.trim(),
            model: document.getElementById('translationModel').value
        }
    };

    const apiKey = document.getElementById('translationApiKey').value.trim();
    if (apiKey) {
        settings.translation.api_key = apiKey;
    }

    try {
        const response = await fetch('/api/translation/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        const data = await response.json();

        if (!data.success) {
            showToast(data.error || '保存翻译设置失败', 'error');
            return false;
        }

        return true;
    } catch (error) {
        console.error('保存翻译设置失败:', error);
        showToast('保存翻译设置失败', 'error');
        return false;
    }
}

// 保存翻译提示词
async function saveTranslationPrompt() {
    const textarea = document.getElementById('translationPrompt');
    if (!textarea) return true;

    const customPrompt = textarea.value.trim();
    const defaultPrompt = textarea.dataset.defaultPrompt || '';

    const promptToSave = customPrompt === defaultPrompt ? '' : customPrompt;

    try {
        const response = await fetch('/api/translation/prompt', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt: promptToSave })
        });

        const data = await response.json();

        if (!data.success) {
            showToast(data.error || '保存翻译提示词失败', 'error');
            return false;
        }

        return true;
    } catch (error) {
        console.error('保存翻译提示词失败:', error);
        showToast('保存翻译提示词失败', 'error');
        return false;
    }
}

// 恢复默认翻译提示词
async function resetTranslationPromptToDefault() {
    const textarea = document.getElementById('translationPrompt');
    if (!textarea) return;

    if (textarea.dataset.defaultPrompt) {
        textarea.value = textarea.dataset.defaultPrompt;
        showToast('已恢复默认翻译提示词，请保存设置', 'info');
        return;
    }

    try {
        const response = await fetch('/api/translation/prompt');
        const result = await response.json();

        if (result.success && result.data && result.data.default_prompt) {
            textarea.value = result.data.default_prompt;
            textarea.dataset.defaultPrompt = result.data.default_prompt;
            showToast('已恢复默认翻译提示词，请保存设置', 'info');
        } else {
            showToast('获取默认翻译提示词失败', 'error');
        }
    } catch (error) {
        console.error('获取默认翻译提示词失败:', error);
        showToast('获取默认翻译提示词失败', 'error');
    }
}

// 测试翻译API连接
async function testTranslationConnection() {
    const btn = document.getElementById('btnTestTranslation');
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');

    const provider = document.getElementById('translationProvider').value;
    const apiUrl = document.getElementById('translationApiUrl').value.trim();
    const apiKey = document.getElementById('translationApiKey').value.trim();
    const model = document.getElementById('translationModel').value;

    if (!apiUrl) {
        showToast('请输入 API URL', 'error');
        return;
    }

    btn.disabled = true;
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';

    try {
        const response = await fetch('/api/translation/test-api', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider: provider,
                api_url: apiUrl,
                api_key: apiKey,
                model: model,
                use_saved: !apiKey
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast(`翻译连接成功！响应: ${data.data.response || ''}`, 'success');
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
            <div class="source-article-item" onclick="openNewsPreview('${escapeHtml(article.url || '')}', this)">
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


// ==================== AI舆情总结功能 ====================

let summaryData = null;
let summaryProgressTimer = null;
let summaryGeneratedTime = null;  // 上次生成时间
let summaryTitleUrlMap = {};  // 标题->URL映射

// 兼容旧代码的 summaryGenerating 访问
Object.defineProperty(window, 'summaryGenerating', {
    get: () => BubbleManager.isRunning('summary'),
    set: (val) => BubbleManager.setRunning('summary', val)
});

// 页面加载时检查今天是否有已生成的总结
async function checkTodaySummary() {
    try {
        const response = await fetch('/api/summary/today');
        const result = await response.json();
        if (result.success && result.data) {
            summaryData = result.data;
            summaryTitleUrlMap = result.data.title_url_map || {};
            summaryStructuredRefs = result.data.structured_refs || {};
            summaryGeneratedTime = new Date(result.data.created_at);
        }
    } catch (error) {
        console.error('检查今日总结失败:', error);
    }
}

// 点击AI总结按钮
async function startSummaryGenerate() {
    if (BubbleManager.isRunning('summary')) {
        showToast('正在生成中，请稍候', 'warning');
        showSummaryBubble();
        return;
    }

    // 如果还没有加载过数据，先检查后端是否有今日总结
    if (!summaryData) {
        try {
            const response = await fetch('/api/summary/today');
            const result = await response.json();
            if (result.success && result.data) {
                summaryData = result.data;
                summaryTitleUrlMap = result.data.title_url_map || {};
                summaryStructuredRefs = result.data.structured_refs || {};
                summaryGeneratedTime = new Date(result.data.created_at);
            }
        } catch (error) {
            console.error('检查今日总结失败:', error);
        }
    }

    // 检查是否有上次生成的结果
    if (summaryData && summaryGeneratedTime) {
        const timeStr = summaryGeneratedTime.toLocaleString('zh-CN');
        showSummaryConfirm(timeStr);
        return;
    }

    // 开始生成
    doGenerateSummary();
}

// 显示确认对话框
function showSummaryConfirm(timeStr) {
    const modal = document.createElement('div');
    modal.className = 'confirm-modal';
    modal.id = 'summaryConfirmModal';
    modal.innerHTML = `
        <div class="confirm-content">
            <div class="confirm-title">已有舆情总结报告</div>
            <div class="confirm-text">上次生成时间：${timeStr}</div>
            <div class="confirm-buttons">
                <button class="btn btn-secondary" onclick="closeSummaryConfirm(); viewSummaryResult();">查看上次报告</button>
                <button class="btn btn-primary" onclick="closeSummaryConfirm(); doGenerateSummary();">重新生成</button>
                <button class="btn btn-outline" onclick="closeSummaryConfirm(); openSummaryHistory();">历史记录</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    setTimeout(() => modal.classList.add('show'), 10);
}

function closeSummaryConfirm() {
    const modal = document.getElementById('summaryConfirmModal');
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => modal.remove(), 300);
    }
}

function doGenerateSummary() {
    // 显示气泡
    showSummaryBubble();
    updateSummaryBubbleStatus('正在获取今日新闻...');
    updateSummaryProgress(10);

    BubbleManager.setRunning('summary', true);
    summaryData = null;
    summaryTitleUrlMap = {};

    // 启动伪进度
    startFakeProgress();

    // 异步生成
    generateSummaryAsync();
}

// 伪进度动画
function startFakeProgress() {
    let progress = 10;
    const maxProgress = 85;

    if (summaryProgressTimer) {
        clearInterval(summaryProgressTimer);
    }

    summaryProgressTimer = setInterval(() => {
        if (progress < maxProgress) {
            // 速度随进度递减
            const speed = Math.max(0.3, (maxProgress - progress) / 50);
            progress += speed;
            updateSummaryProgress(Math.min(progress, maxProgress));

            // 更新状态文字
            if (progress > 20 && progress < 40) {
                updateSummaryBubbleStatus('AI正在阅读新闻...');
            } else if (progress > 40 && progress < 60) {
                updateSummaryBubbleStatus('AI正在分析舆情态势...');
            } else if (progress > 60 && progress < 80) {
                updateSummaryBubbleStatus('AI正在识别风险隐患...');
            } else if (progress >= 80) {
                updateSummaryBubbleStatus('AI正在生成报告...');
            }
        }
    }, 200);
}

function stopFakeProgress() {
    if (summaryProgressTimer) {
        clearInterval(summaryProgressTimer);
        summaryProgressTimer = null;
    }
}

async function generateSummaryAsync() {
    try {
        const response = await fetch('/api/summary/daily', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        stopFakeProgress();

        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || '生成失败');
        }

        summaryData = result.data;
        summaryTitleUrlMap = result.data.title_url_map || {};
        summaryStructuredRefs = result.data.structured_refs || {};
        summaryGeneratedTime = new Date();

        updateSummaryProgress(100);
        updateSummaryBubbleStatus(`分析完成！共${summaryData.article_count}条新闻`, true);

        // 显示查看按钮
        document.getElementById('summaryViewBtn').style.display = 'block';
        document.getElementById('summaryBubble').classList.add('complete');

        // 弹出提示
        showToast('舆情分析完成，点击查看结果', 'success');

    } catch (error) {
        stopFakeProgress();
        updateSummaryBubbleStatus(`失败: ${error.message}`, false, true);
        showToast(error.message || '生成失败', 'error');
    } finally {
        BubbleManager.setRunning('summary', false);
    }
}

function showSummaryBubble() {
    BubbleManager.show('summary');
    document.getElementById('summaryBubble').classList.remove('complete');
    document.getElementById('summaryViewBtn').style.display = 'none';
    // 重置进度
    updateSummaryProgress(0);
}

function hideSummaryBubble() {
    BubbleManager.hide('summary');
}

function closeSummaryBubble() {
    BubbleManager.close('summary');
}

function updateSummaryProgress(percent) {
    document.getElementById('summaryProgressFill').style.width = `${percent}%`;
    document.getElementById('summaryProgressText').textContent = `${Math.round(percent)}%`;
}

function updateSummaryBubbleStatus(text, isComplete = false, isError = false) {
    const statusEl = document.getElementById('summaryBubbleStatus');
    statusEl.textContent = text;
    statusEl.className = 'bubble-status' + (isComplete ? ' success' : '') + (isError ? ' error' : '');
}

function viewSummaryResult() {
    if (!summaryData) {
        showToast('暂无分析结果', 'warning');
        return;
    }

    // 隐藏气泡
    hideSummaryBubble();

    // 打开弹窗并填充数据
    openSummaryModal();
}

function openSummaryModal() {
    document.getElementById('summaryModal').classList.add('active');

    // 显示当前日期
    const dateStr = summaryData?.date_str || summaryData?.date || `${new Date().getFullYear()}年${new Date().getMonth() + 1}月${new Date().getDate()}日`;
    document.getElementById('summaryDate').textContent = dateStr;

    // 如果有数据则显示
    if (summaryData) {
        displaySummaryData(summaryData);
    } else {
        // 清空内容
        document.getElementById('summarySummary').innerHTML = '<span class="empty-hint">暂无数据，请点击"重新生成"按钮</span>';
        document.getElementById('summaryHotNews').innerHTML = '';
        document.getElementById('summaryRisk').innerHTML = '';
        document.getElementById('summaryMeta').textContent = '';
    }
}

// 简易 Markdown 渲染（支持新闻超链接）
function renderMarkdown(text, titleUrlMap = null) {
    if (!text) return '';

    let html = escapeHtml(text);

    // 处理标题 ### / ## / #
    html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>');
    html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>');

    // 处理粗体 **text**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // 处理斜体 *text*
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // 处理有序列表 1. 2. 等
    html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<div class="md-list-item"><span class="md-list-num">$1.</span><span class="md-list-content">$2</span></div>');

    // 处理无序列表 -
    html = html.replace(/^[-•]\s+(.+)$/gm, '<div class="md-list-item"><span class="md-list-bullet">•</span><span class="md-list-content">$1</span></div>');

    // 处理换行
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');

    // 包装段落
    if (!html.startsWith('<')) {
        html = '<p>' + html + '</p>';
    }

    // 如果有标题URL映射，将新闻标题转换为超链接
    if (titleUrlMap && Object.keys(titleUrlMap).length > 0) {
        html = addNewsLinks(html, titleUrlMap);
    }

    return html;
}

// 将文本中的新闻标题转换为可点击的超链接
function addNewsLinks(html, titleUrlMap) {
    // 对每个标题进行匹配和替换
    for (const [title, info] of Object.entries(titleUrlMap)) {
        if (!info.url) continue;

        // 转义特殊正则字符
        const escapedTitle = title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

        // 尝试匹配标题（可能被HTML编码）
        const encodedTitle = escapeHtml(title);
        const escapedEncodedTitle = encodedTitle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

        // 创建超链接
        const link = `<a href="${escapeHtml(info.url)}" target="_blank" class="news-link" title="点击查看原文">${encodedTitle}</a>`;

        // 替换匹配的标题（避免重复替换已经是链接的部分）
        const regex = new RegExp(`(?<!<a[^>]*>)${escapedEncodedTitle}(?![^<]*</a>)`, 'g');
        html = html.replace(regex, link);
    }

    return html;
}

function displaySummaryData(data) {
    const urlMap = data.title_url_map || summaryTitleUrlMap || {};

    // 保存结构化引用数据
    summaryStructuredRefs = data.structured_refs || {};

    document.getElementById('summarySummary').innerHTML = renderMarkdown(data.summary, urlMap) || '<span class="empty-hint">暂无总结</span>';
    document.getElementById('summaryHotNews').innerHTML = renderMarkdown(data.hot_news, urlMap) || '<span class="empty-hint">暂无热点新闻</span>';
    document.getElementById('summaryRisk').innerHTML = renderMarkdown(data.risk_analysis, urlMap) || '<span class="empty-hint">暂无风险分析</span>';

    let metaText = `基于 ${data.article_count} 条新闻 | 模型: ${data.model || 'AI'}`;
    if (data.date_str || data.date) {
        metaText += ` | ${data.date_str || data.date}`;
    }
    if (data.created_at) {
        metaText += ` | 生成于 ${data.created_at}`;
    } else if (summaryGeneratedTime) {
        metaText += ` | 生成于 ${summaryGeneratedTime.toLocaleTimeString('zh-CN')}`;
    }
    document.getElementById('summaryMeta').textContent = metaText;
}

function closeSummaryModal() {
    document.getElementById('summaryModal').classList.remove('active');
}

// ==================== AI原始内容功能 ====================

function showRawContent() {
    if (!summaryData || !summaryData.full_content) {
        showToast('暂无原始内容', 'warning');
        return;
    }

    document.getElementById('rawContentText').textContent = summaryData.full_content;
    document.getElementById('rawContentModal').classList.add('active');
}

function closeRawContentModal() {
    document.getElementById('rawContentModal').classList.remove('active');
}

function copyRawContent() {
    const content = summaryData?.full_content || '';
    if (!content) {
        showToast('无内容可复制', 'warning');
        return;
    }

    navigator.clipboard.writeText(content).then(() => {
        showToast('已复制到剪贴板', 'success');
    }).catch(() => {
        // 降级方案
        const textarea = document.createElement('textarea');
        textarea.value = content;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showToast('已复制到剪贴板', 'success');
    });
}

// ==================== 引用来源功能 ====================

let summaryStructuredRefs = {};  // 结构化引用数据
let currentRefsCategory = 'all';

// 分类名称映射
const CATEGORY_NAMES = {
    'international_conflict': '国际冲突与人道主义危机',
    'international_relations': '重大国际关系动态',
    'economy_tech': '经济与科技热点',
    'immigration_border': '移民与边境管理',
    'society_culture': '社会与文化议题'
};

function showCategoryRefs(section) {
    const refs = summaryStructuredRefs || {};

    if (section === 'summary') {
        // 显示舆情总结的所有分类引用
        showRefsModal('今日舆情总结 - 引用来源', refs.category_news || {}, 'categories');
    } else if (section === 'top5') {
        // 显示热点TOP5的引用
        showRefsModal('热点新闻TOP5 - 引用来源', refs.top_5_news || [], 'top5');
    }
}

function showRefsModal(title, data, type) {
    document.getElementById('refsModalTitle').textContent = title;
    document.getElementById('refsModal').classList.add('active');

    const tabsEl = document.getElementById('refsCategoriesTabs');
    const listEl = document.getElementById('refsList');

    if (type === 'categories') {
        // 显示分类标签
        let hasAnyData = false;
        let tabsHtml = '';

        for (const [key, name] of Object.entries(CATEGORY_NAMES)) {
            const items = data[key] || [];
            const count = items.length;
            if (count > 0) hasAnyData = true;

            tabsHtml += `
                <button class="refs-tab ${currentRefsCategory === key ? 'active' : ''}"
                        onclick="switchRefsCategory('${key}')"
                        data-count="${count}">
                    ${name}
                    <span class="refs-count">${count}</span>
                </button>
            `;
        }

        tabsEl.innerHTML = tabsHtml;
        tabsEl.style.display = 'flex';

        if (!hasAnyData) {
            listEl.innerHTML = '<div class="empty-hint">AI未返回结构化引用数据，请查看报告中的新闻链接</div>';
            return;
        }

        // 默认显示第一个有数据的分类
        let firstCategory = null;
        for (const key of Object.keys(CATEGORY_NAMES)) {
            if (data[key] && data[key].length > 0) {
                firstCategory = key;
                break;
            }
        }

        if (firstCategory) {
            currentRefsCategory = firstCategory;
            renderRefsList(data[firstCategory]);
            // 更新tab高亮
            document.querySelectorAll('.refs-tab').forEach(tab => {
                tab.classList.toggle('active', tab.textContent.includes(CATEGORY_NAMES[firstCategory]));
            });
        }

        // 保存数据供切换使用
        window._refsData = data;

    } else if (type === 'top5') {
        // TOP5不需要分类标签
        tabsEl.style.display = 'none';

        if (!data || data.length === 0) {
            listEl.innerHTML = '<div class="empty-hint">AI未返回TOP5结构化数据，请查看报告中的新闻链接</div>';
            return;
        }

        // 按rank排序
        const sorted = [...data].sort((a, b) => (a.rank || 0) - (b.rank || 0));
        renderRefsList(sorted, true);
    }
}

function switchRefsCategory(category) {
    currentRefsCategory = category;
    const data = window._refsData || {};

    // 更新tab高亮
    document.querySelectorAll('.refs-tab').forEach(tab => {
        const isActive = tab.textContent.includes(CATEGORY_NAMES[category]);
        tab.classList.toggle('active', isActive);
    });

    renderRefsList(data[category] || []);
}

function renderRefsList(items, showRank = false) {
    const listEl = document.getElementById('refsList');

    if (!items || items.length === 0) {
        listEl.innerHTML = '<div class="empty-hint">该分类暂无引用的新闻</div>';
        return;
    }

    let html = '';
    items.forEach((item, index) => {
        const rank = showRank && item.rank ? `<span class="refs-rank">${item.rank}</span>` : '';
        const title = escapeHtml(item.title || '未知标题');
        const url = item.url || '#';

        html += `
            <a href="${escapeHtml(url)}" target="_blank" class="refs-item">
                ${rank}
                <span class="refs-title">${title}</span>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                    <polyline points="15 3 21 3 21 9"></polyline>
                    <line x1="10" y1="14" x2="21" y2="3"></line>
                </svg>
            </a>
        `;
    });

    listEl.innerHTML = html;
}

function closeRefsModal() {
    document.getElementById('refsModal').classList.remove('active');
}

// ==================== AI总结历史记录 ====================

let summaryHistoryPage = 1;
let summaryHistoryLoading = false;

function openSummaryHistory() {
    document.getElementById('summaryHistoryModal').classList.add('active');
    summaryHistoryPage = 1;
    loadSummaryHistory();
}

function closeSummaryHistory() {
    document.getElementById('summaryHistoryModal').classList.remove('active');
}

// 从历史记录返回到AI总结页面
function backToSummary() {
    closeSummaryHistory();
    openSummaryModal();
}

async function loadSummaryHistory() {
    if (summaryHistoryLoading) return;

    summaryHistoryLoading = true;
    const listEl = document.getElementById('summaryHistoryList');

    if (summaryHistoryPage === 1) {
        listEl.innerHTML = '<div class="loading-hint">加载中...</div>';
    }

    try {
        const response = await fetch(`/api/summary/history?page=${summaryHistoryPage}&page_size=20`);
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || '加载失败');
        }

        const data = result.data;

        if (summaryHistoryPage === 1) {
            listEl.innerHTML = '';
        }

        if (data.items.length === 0 && summaryHistoryPage === 1) {
            listEl.innerHTML = '<div class="empty-hint">暂无历史记录</div>';
            return;
        }

        data.items.forEach(item => {
            const itemEl = document.createElement('div');
            itemEl.className = 'history-item';
            itemEl.innerHTML = `
                <div class="history-item-header">
                    <span class="history-date">${item.date_str}</span>
                    <span class="history-count">${item.article_count} 条新闻</span>
                </div>
                <div class="history-preview">${escapeHtml(item.summary_preview)}</div>
                <div class="history-meta">
                    <span>模型: ${item.model || 'AI'}</span>
                    <span>生成时间: ${item.created_at}</span>
                </div>
            `;
            itemEl.onclick = () => viewHistorySummary(item.id);
            listEl.appendChild(itemEl);
        });

        // 显示/隐藏加载更多按钮
        const loadMoreBtn = document.getElementById('summaryHistoryLoadMore');
        if (summaryHistoryPage < data.total_pages) {
            loadMoreBtn.style.display = 'block';
        } else {
            loadMoreBtn.style.display = 'none';
        }

    } catch (error) {
        if (summaryHistoryPage === 1) {
            listEl.innerHTML = `<div class="error-hint">加载失败: ${error.message}</div>`;
        }
        showToast('加载历史记录失败', 'error');
    } finally {
        summaryHistoryLoading = false;
    }
}

function loadMoreSummaryHistory() {
    summaryHistoryPage++;
    loadSummaryHistory();
}

async function viewHistorySummary(summaryId) {
    try {
        const response = await fetch(`/api/summary/detail/${summaryId}`);
        const result = await response.json();

        if (!result.success || !result.data) {
            showToast('获取总结详情失败', 'error');
            return;
        }

        // 关闭历史弹窗
        closeSummaryHistory();

        // 设置数据并打开总结弹窗
        summaryData = result.data;
        summaryTitleUrlMap = result.data.title_url_map || {};
        summaryStructuredRefs = result.data.structured_refs || {};
        summaryGeneratedTime = new Date(result.data.created_at);

        openSummaryModal();

    } catch (error) {
        showToast('加载失败: ' + error.message, 'error');
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

// ==================== 全局搜索功能 ====================

let globalSearchDebounceTimer = null;
let globalSearchKeyword = '';
let globalSearchPage = 1;
let globalSearchTotal = 0;
let globalSearchLoading = false;
const GLOBAL_SEARCH_PAGE_SIZE = 20;

// 打开全局搜索
function openGlobalSearch() {
    const modal = document.getElementById('globalSearchModal');
    modal.classList.add('active');

    // 聚焦输入框
    setTimeout(() => {
        const input = document.getElementById('globalSearchInput');
        input.focus();
        input.select();
    }, 100);
}

// 关闭全局搜索
function closeGlobalSearch() {
    const modal = document.getElementById('globalSearchModal');
    modal.classList.remove('active');

    // 清理状态
    document.getElementById('globalSearchInput').value = '';
    document.getElementById('searchClearBtn').style.display = 'none';
    globalSearchKeyword = '';
    globalSearchPage = 1;
    globalSearchTotal = 0;

    // 重置显示
    document.getElementById('searchResultsInfo').innerHTML = '<span class="search-hint">输入关键词开始搜索</span>';
    document.getElementById('globalSearchResults').innerHTML = '';
    document.getElementById('searchLoadMore').style.display = 'none';
}

// 清除搜索内容
function clearGlobalSearch() {
    document.getElementById('globalSearchInput').value = '';
    document.getElementById('searchClearBtn').style.display = 'none';
    globalSearchKeyword = '';
    globalSearchPage = 1;

    document.getElementById('searchResultsInfo').innerHTML = '<span class="search-hint">输入关键词开始搜索</span>';
    document.getElementById('globalSearchResults').innerHTML = '';
    document.getElementById('searchLoadMore').style.display = 'none';

    document.getElementById('globalSearchInput').focus();
}

// 搜索输入处理（防抖）
function handleGlobalSearchInput(e) {
    const keyword = e.target.value.trim();

    // 显示/隐藏清除按钮
    document.getElementById('searchClearBtn').style.display = keyword ? 'block' : 'none';

    // 防抖处理
    if (globalSearchDebounceTimer) {
        clearTimeout(globalSearchDebounceTimer);
    }

    if (!keyword) {
        document.getElementById('searchResultsInfo').innerHTML = '<span class="search-hint">输入关键词开始搜索</span>';
        document.getElementById('globalSearchResults').innerHTML = '';
        document.getElementById('searchLoadMore').style.display = 'none';
        globalSearchKeyword = '';
        return;
    }

    // 显示加载状态
    if (keyword !== globalSearchKeyword) {
        document.getElementById('globalSearchResults').innerHTML = `
            <div class="search-loading">
                <div class="spinner"></div>
                <span>搜索中...</span>
            </div>
        `;
    }

    globalSearchDebounceTimer = setTimeout(() => {
        globalSearchKeyword = keyword;
        globalSearchPage = 1;
        performGlobalSearch(false);
    }, 200);  // 200ms 防抖，快速响应
}

// 执行搜索
async function performGlobalSearch(append = false) {
    if (globalSearchLoading || !globalSearchKeyword) return;

    globalSearchLoading = true;

    try {
        const url = `/api/articles?keyword=${encodeURIComponent(globalSearchKeyword)}&page=${globalSearchPage}&page_size=${GLOBAL_SEARCH_PAGE_SIZE}`;
        const response = await fetch(url);
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || '搜索失败');
        }

        const data = result.data;
        globalSearchTotal = data.total;

        // 更新结果信息
        if (data.total > 0) {
            document.getElementById('searchResultsInfo').innerHTML =
                `找到 <span class="search-results-count">${data.total}</span> 条相关结果`;
        } else {
            document.getElementById('searchResultsInfo').innerHTML =
                `<span class="search-hint">未找到相关结果</span>`;
        }

        // 渲染结果
        const resultsContainer = document.getElementById('globalSearchResults');

        if (!append) {
            resultsContainer.innerHTML = '';
        }

        if (data.items.length === 0 && !append) {
            resultsContainer.innerHTML = `
                <div class="search-empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="11" cy="11" r="8"></circle>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                    </svg>
                    <span>没有找到 "${escapeHtml(globalSearchKeyword)}" 相关的新闻</span>
                </div>
            `;
        } else {
            data.items.forEach(item => {
                resultsContainer.innerHTML += renderSearchResultItem(item);
            });
        }

        // 显示/隐藏"加载更多"按钮
        const hasMore = globalSearchPage * GLOBAL_SEARCH_PAGE_SIZE < data.total;
        document.getElementById('searchLoadMore').style.display = hasMore ? 'block' : 'none';

    } catch (error) {
        console.error('搜索出错:', error);
        document.getElementById('globalSearchResults').innerHTML = `
            <div class="search-empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="15" y1="9" x2="9" y2="15"></line>
                    <line x1="9" y1="9" x2="15" y2="15"></line>
                </svg>
                <span>搜索出错，请重试</span>
            </div>
        `;
    } finally {
        globalSearchLoading = false;
    }
}

// 渲染单个搜索结果
function renderSearchResultItem(item) {
    const title = item.title || '无标题';
    const url = item.url || '#';
    const source = item.source || '未知来源';
    const pubDate = item.pub_date || '';

    // 高亮关键词
    const highlightedTitle = highlightKeyword(title, globalSearchKeyword);

    return `
        <a href="${escapeHtml(url)}" target="_blank" class="search-result-item">
            <div class="search-result-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                </svg>
            </div>
            <div class="search-result-content">
                <div class="search-result-title">${highlightedTitle}</div>
                <div class="search-result-meta">
                    <span class="search-result-source">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="2" y1="12" x2="22" y2="12"></line>
                            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                        </svg>
                        ${escapeHtml(source)}
                    </span>
                    ${pubDate ? `<span class="search-result-date">${escapeHtml(pubDate)}</span>` : ''}
                </div>
            </div>
            <svg class="search-result-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
        </a>
    `;
}

// 高亮关键词
function highlightKeyword(text, keyword) {
    if (!keyword) return escapeHtml(text);

    // 转义特殊字符用于正则
    const escapedKeyword = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escapedKeyword})`, 'gi');

    // 先转义HTML，再添加高亮标记
    const escaped = escapeHtml(text);
    return escaped.replace(regex, '<mark>$1</mark>');
}

// 加载更多搜索结果
function loadMoreSearchResults() {
    if (globalSearchLoading) return;

    globalSearchPage++;
    performGlobalSearch(true);
}

// 全局键盘事件监听
document.addEventListener('keydown', function(e) {
    // Ctrl+F 或 Cmd+F 打开全局搜索
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        e.preventDefault();  // 阻止浏览器默认搜索
        openGlobalSearch();
    }

    // ESC 关闭全局搜索
    if (e.key === 'Escape') {
        const modal = document.getElementById('globalSearchModal');
        if (modal && modal.classList.contains('active')) {
            closeGlobalSearch();
        }
    }
});

// 搜索输入框事件绑定
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('globalSearchInput');
    if (searchInput) {
        searchInput.addEventListener('input', handleGlobalSearchInput);

        // 回车键打开第一个结果
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                const firstResult = document.querySelector('.search-result-item');
                if (firstResult) {
                    firstResult.click();
                }
            }
        });
    }

    // 初始化 Telegram 模块
    initTelegramModule();
});


// ==================== Telegram 群组监控模块 ====================

// 状态变量
let tgAlertsCurrentPage = 1;
let tgCurrentKwLevel = 'high';
let tgKeywordsData = { high: [], medium: [], low: [] };

// 初始化
function initTelegramModule() {
    loadTgOverviewStats();
    loadTgRecentAlerts();
    loadTgMonitorStatus();
    // 定时刷新
    tgRefreshTimer = setInterval(() => {
        loadTgOverviewStats();
        loadTgRecentAlerts();
        loadTgMonitorStatus();
    }, 30000);
}

// ---------- 概览统计 ----------

function loadTgOverviewStats() {
    fetch('/api/telegram/stats/overview')
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                const d = res.data;
                document.getElementById('tgTodayAlerts').textContent = d.today_alerts || 0;
                document.getElementById('tgUnreadAlerts').textContent = d.unread_alerts || 0;
                document.getElementById('tgGroupCount').textContent = d.total_groups || 0;
            }
        })
        .catch(() => {});
}

// ---------- 最新报警列表 ----------

function loadTgRecentAlerts() {
    fetch('/api/telegram/alerts?page=1&page_size=10')
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                renderTgAlertList(res.data.items);
            }
        })
        .catch(() => {});
}

function renderTgAlertList(items) {
    const container = document.getElementById('tgAlertList');
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="tg-empty-hint">暂无报警记录</div>';
        return;
    }

    container.innerHTML = items.map(item => {
        const levelClass = `level-${item.highest_level}`;
        const unreadClass = item.is_read ? '' : 'unread';
        const time = item.timestamp ? item.timestamp.substring(11, 16) : '';
        const kwTags = (item.matched_keywords || []).map(kw =>
            `<span class="tg-alert-kw-tag ${levelClass}">${escapeHtml(kw)}</span>`
        ).join('');

        return `
            <div class="tg-alert-item ${unreadClass} ${levelClass}" onclick="markTgAlertRead('${item.id}', this)">
                <div class="tg-alert-top">
                    <span class="tg-alert-group">${escapeHtml(item.group_title)}</span>
                    <span class="tg-alert-time">${time}</span>
                </div>
                <div class="tg-alert-content">${escapeHtml(item.content)}</div>
                <div class="tg-alert-keywords">${kwTags}</div>
            </div>
        `;
    }).join('');
}

function markTgAlertRead(alertId, el) {
    fetch(`/api/telegram/alerts/${alertId}/read`, { method: 'POST' })
        .then(r => r.json())
        .then(res => {
            if (res.success && el) {
                el.classList.remove('unread');
                loadTgOverviewStats();
            }
        })
        .catch(() => {});
}

// ---------- 监控状态 ----------

function loadTgMonitorStatus() {
    fetch('/api/telegram/monitor/status')
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                const badge = document.getElementById('tgStatusBadge');
                const btn = document.getElementById('btnToggleMonitor');
                if (res.data.running) {
                    badge.textContent = '运行中';
                    badge.className = 'tg-status-badge running';
                    if (btn) btn.querySelector('.btn-text').textContent = '停止监控';
                } else {
                    badge.textContent = '未启动';
                    badge.className = 'tg-status-badge';
                    if (btn) btn.querySelector('.btn-text').textContent = '启动监控';
                }
            }
        })
        .catch(() => {});
}

function toggleTgMonitor() {
    const badge = document.getElementById('tgStatusBadge');
    const isRunning = badge.classList.contains('running');
    const action = isRunning ? 'stop' : 'start';

    fetch(`/api/telegram/monitor/${action}`, { method: 'POST' })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                showToast(res.data.message, 'success');
                loadTgMonitorStatus();
            } else {
                showToast(res.error || '操作失败', 'error');
            }
        })
        .catch(() => showToast('请求失败', 'error'));
}

// ---------- 设置弹窗 ----------

function openTelegramSettingsModal() {
    document.getElementById('telegramSettingsModal').classList.add('active');
    switchTgTab('tg-accounts');
    loadTgAccounts();
    loadTgSubscribedGroups();
    loadTgKeywords();
    loadTgWebhookSettings();
}

function closeTelegramSettingsModal() {
    document.getElementById('telegramSettingsModal').classList.remove('active');
}

function switchTgTab(tabId) {
    document.querySelectorAll('.tg-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tg-tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`.tg-tab[data-tab="${tabId}"]`).classList.add('active');
    document.getElementById(tabId).classList.add('active');
}

// ---------- 账号管理 ----------

function showAddAccountForm() {
    document.getElementById('tgAddAccountForm').style.display = 'block';
}

function hideAddAccountForm() {
    document.getElementById('tgAddAccountForm').style.display = 'none';
    document.getElementById('tgAccountName').value = '';
    document.getElementById('tgAccountPhone').value = '';
    document.getElementById('tgAccountApiId').value = '';
    document.getElementById('tgAccountApiHash').value = '';
}

function loadTgAccounts() {
    fetch('/api/telegram/accounts')
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                renderTgAccountList(res.data);
                // 填充群组搜索账号下拉
                const select = document.getElementById('tgSearchAccount');
                if (select) {
                    select.innerHTML = '<option value="">选择账号</option>' +
                        res.data.map(a => `<option value="${a.id}">${escapeHtml(a.name)} (${escapeHtml(a.phone)})</option>`).join('');
                }
            }
        })
        .catch(() => {});
}

function renderTgAccountList(accounts) {
    const container = document.getElementById('tgAccountList');
    if (!accounts || accounts.length === 0) {
        container.innerHTML = '<div class="tg-empty-hint">暂无账号，请点击"添加账号"</div>';
        return;
    }

    const statusText = { active: '已连接', pending_auth: '待验证', disconnected: '已断开' };

    container.innerHTML = accounts.map(acc => `
        <div class="tg-account-item">
            <div class="tg-account-info">
                <div class="tg-account-name">
                    ${escapeHtml(acc.name)}
                    <span class="tg-account-status ${acc.status}">${statusText[acc.status] || acc.status}</span>
                </div>
                <div class="tg-account-phone">${escapeHtml(acc.phone)}</div>
            </div>
            <div class="tg-account-actions">
                ${acc.status !== 'active' ? `<button class="btn btn-outline btn-sm" onclick="connectTgAccount('${acc.id}')">连接</button>` : ''}
                <button class="btn btn-outline btn-sm btn-danger" onclick="deleteTgAccount('${acc.id}')">删除</button>
            </div>
        </div>
    `).join('');
}

function saveTgAccount() {
    const data = {
        name: document.getElementById('tgAccountName').value.trim(),
        api_id: document.getElementById('tgAccountApiId').value.trim(),
        api_hash: document.getElementById('tgAccountApiHash').value.trim(),
        phone: document.getElementById('tgAccountPhone').value.trim(),
    };

    if (!data.name || !data.api_id || !data.api_hash || !data.phone) {
        showToast('请填写完整信息', 'error');
        return;
    }

    fetch('/api/telegram/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            showToast('账号已添加', 'success');
            hideAddAccountForm();
            loadTgAccounts();
        } else {
            showToast(res.error || '添加失败', 'error');
        }
    })
    .catch(() => showToast('请求失败', 'error'));
}

function connectTgAccount(accountId) {
    fetch(`/api/telegram/accounts/${accountId}/connect`, { method: 'POST' })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                const data = res.data;
                if (data.status === 'active') {
                    showToast('已连接', 'success');
                    loadTgAccounts();
                } else if (data.status === 'pending_auth') {
                    showToast('验证码已发送', 'success');
                    openTgVerifyModal(accountId);
                }
            } else {
                showToast(res.error || '连接失败', 'error');
            }
        })
        .catch(() => showToast('请求失败', 'error'));
}

function deleteTgAccount(accountId) {
    if (!confirm('确定删除此账号？相关群组订阅也将被删除。')) return;

    fetch(`/api/telegram/accounts/${accountId}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                showToast('账号已删除', 'success');
                loadTgAccounts();
            } else {
                showToast(res.error || '删除失败', 'error');
            }
        })
        .catch(() => showToast('请求失败', 'error'));
}

// ---------- 验证码弹窗 ----------

function openTgVerifyModal(accountId) {
    document.getElementById('tgVerifyAccountId').value = accountId;
    document.getElementById('tgVerifyCode').value = '';
    document.getElementById('tgVerifyPassword').value = '';
    document.getElementById('tgPasswordGroup').style.display = 'none';
    document.getElementById('tgVerifyModal').classList.add('active');
}

function closeTgVerifyModal() {
    document.getElementById('tgVerifyModal').classList.remove('active');
}

function submitTgVerify() {
    const accountId = document.getElementById('tgVerifyAccountId').value;
    const code = document.getElementById('tgVerifyCode').value.trim();
    const password = document.getElementById('tgVerifyPassword').value.trim();

    if (!code) {
        showToast('请输入验证码', 'error');
        return;
    }

    fetch(`/api/telegram/accounts/${accountId}/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, password: password || undefined })
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            if (res.data.status === 'need_password') {
                document.getElementById('tgPasswordGroup').style.display = 'block';
                showToast('需要两步验证密码', 'warning');
            } else {
                showToast('登录成功', 'success');
                closeTgVerifyModal();
                loadTgAccounts();
            }
        } else {
            showToast(res.error || '验证失败', 'error');
        }
    })
    .catch(() => showToast('请求失败', 'error'));
}

// ---------- 群组管理 ----------

function loadTgSubscribedGroups() {
    fetch('/api/telegram/groups')
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                renderTgSubscribedList(res.data);
            }
        })
        .catch(() => {});
}

function renderTgSubscribedList(groups) {
    const container = document.getElementById('tgSubscribedList');
    if (!groups || groups.length === 0) {
        container.innerHTML = '<div class="tg-empty-hint">暂无订阅群组</div>';
        return;
    }

    container.innerHTML = groups.map(g => {
        const stats = g.stats || {};
        return `
            <div class="tg-group-item">
                <div class="tg-group-info">
                    <div class="tg-group-title">${escapeHtml(g.group_title)}</div>
                    ${g.group_link ? `<div class="tg-group-link">${escapeHtml(g.group_link)}</div>` : ''}
                </div>
                <div class="tg-group-stats">
                    消息: ${stats.total_messages || 0} | 报警: ${stats.alert_messages || 0}
                </div>
                <div class="tg-group-actions">
                    <div class="tg-toggle ${g.enabled ? 'active' : ''}" onclick="toggleTgGroup('${g.id}', this)"></div>
                    <button class="btn btn-outline btn-sm btn-danger" onclick="unsubscribeTgGroup('${g.id}')">删除</button>
                </div>
            </div>
        `;
    }).join('');
}

function searchTgGroups() {
    const accountId = document.getElementById('tgSearchAccount').value;
    const query = document.getElementById('tgSearchQuery').value.trim();

    if (!accountId) {
        showToast('请选择账号', 'error');
        return;
    }
    if (!query) {
        showToast('请输入搜索关键词', 'error');
        return;
    }

    fetch('/api/telegram/groups/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accountId, query })
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            const results = res.data;
            const container = document.getElementById('tgGroupSearchList');
            const section = document.getElementById('tgSearchResults');
            section.style.display = 'block';

            if (results.length === 0) {
                container.innerHTML = '<div class="tg-empty-hint">未找到群组</div>';
                return;
            }

            container.innerHTML = results.map(g => `
                <div class="tg-group-item">
                    <div class="tg-group-info">
                        <div class="tg-group-title">${escapeHtml(g.group_title)}</div>
                        ${g.group_link ? `<div class="tg-group-link">${escapeHtml(g.group_link)}</div>` : ''}
                    </div>
                    <button class="btn btn-primary btn-sm" onclick="subscribeTgGroup('${document.getElementById('tgSearchAccount').value}', ${g.group_id}, '${escapeHtml(g.group_title)}', '${escapeHtml(g.group_link || '')}')">订阅</button>
                </div>
            `).join('');
        } else {
            showToast(res.error || '搜索失败', 'error');
        }
    })
    .catch(() => showToast('请求失败', 'error'));
}

function subscribeTgGroup(accountId, groupId, title, link) {
    fetch('/api/telegram/groups/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            account_id: accountId,
            group_id: groupId,
            group_title: title,
            group_link: link,
        })
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            showToast('订阅成功', 'success');
            loadTgSubscribedGroups();
        } else {
            showToast(res.error || '订阅失败', 'error');
        }
    })
    .catch(() => showToast('请求失败', 'error'));
}

function unsubscribeTgGroup(groupDbId) {
    if (!confirm('确定取消订阅？')) return;

    fetch(`/api/telegram/groups/${groupDbId}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                showToast('已取消订阅', 'success');
                loadTgSubscribedGroups();
            }
        })
        .catch(() => showToast('请求失败', 'error'));
}

function toggleTgGroup(groupDbId, el) {
    fetch(`/api/telegram/groups/${groupDbId}/toggle`, { method: 'POST' })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                if (res.data.enabled) {
                    el.classList.add('active');
                } else {
                    el.classList.remove('active');
                }
            }
        })
        .catch(() => {});
}

// ---------- 关键词管理 ----------

function loadTgKeywords() {
    fetch('/api/telegram/keywords')
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                tgKeywordsData = res.data;
                document.getElementById('tgKwCountHigh').textContent = (res.data.high || []).length;
                document.getElementById('tgKwCountMedium').textContent = (res.data.medium || []).length;
                document.getElementById('tgKwCountLow').textContent = (res.data.low || []).length;
                renderTgKeywordList();
            }
        })
        .catch(() => {});
}

function switchTgKwTab(level) {
    tgCurrentKwLevel = level;
    document.querySelectorAll('.tg-kw-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tg-kw-tab[data-level="${level}"]`).classList.add('active');
    renderTgKeywordList();
}

function renderTgKeywordList() {
    const container = document.getElementById('tgKeywordList');
    const items = tgKeywordsData[tgCurrentKwLevel] || [];

    if (items.length === 0) {
        container.innerHTML = '<div class="tg-empty-hint">暂无关键词</div>';
        return;
    }

    container.innerHTML = items.map(kw => `
        <div class="tg-keyword-item">
            <div>
                <span class="tg-keyword-text">${escapeHtml(kw.keyword)}</span>
                <span class="tg-keyword-count">匹配 ${kw.match_count || 0} 次</span>
            </div>
            <div class="tg-keyword-actions">
                <button class="btn btn-outline btn-sm btn-danger" onclick="deleteTgKeyword('${kw.id}')">删除</button>
            </div>
        </div>
    `).join('');
}

function addTgKeyword() {
    const keyword = document.getElementById('tgNewKeyword').value.trim();
    const level = document.getElementById('tgNewKeywordLevel').value;

    if (!keyword) {
        showToast('请输入关键词', 'error');
        return;
    }

    fetch('/api/telegram/keywords', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword, level })
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            showToast('关键词已添加', 'success');
            document.getElementById('tgNewKeyword').value = '';
            loadTgKeywords();
        } else {
            showToast(res.error || '添加失败', 'error');
        }
    })
    .catch(() => showToast('请求失败', 'error'));
}

function deleteTgKeyword(keywordId) {
    fetch(`/api/telegram/keywords/${keywordId}`, { method: 'DELETE' })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                showToast('关键词已删除', 'success');
                loadTgKeywords();
            }
        })
        .catch(() => showToast('请求失败', 'error'));
}

// ---------- Webhook 设置 ----------

function loadTgWebhookSettings() {
    fetch('/api/telegram/webhook/settings')
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                document.getElementById('tgWebhookUrl').value = res.data.webhook_url || '';
                document.getElementById('tgWebhookEnabled').checked = res.data.webhook_enabled || false;
            }
        })
        .catch(() => {});
}

function saveTgWebhookSettings() {
    const data = {
        webhook_url: document.getElementById('tgWebhookUrl').value.trim(),
        webhook_enabled: document.getElementById('tgWebhookEnabled').checked,
    };

    fetch('/api/telegram/webhook/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            showToast('配置已保存', 'success');
        } else {
            showToast(res.error || '保存失败', 'error');
        }
    })
    .catch(() => showToast('请求失败', 'error'));
}

function testTgWebhook() {
    const url = document.getElementById('tgWebhookUrl').value.trim();
    if (!url) {
        showToast('请先填写 Webhook URL', 'error');
        return;
    }

    fetch('/api/telegram/webhook/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ webhook_url: url })
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            showToast('推送成功', 'success');
        } else {
            showToast(res.error || '推送失败', 'error');
        }
    })
    .catch(() => showToast('请求失败', 'error'));
}

// ---------- 全部报警弹窗 ----------

function openTelegramAllAlertsModal() {
    document.getElementById('tgAllAlertsModal').classList.add('active');
    tgAlertsCurrentPage = 1;
    refreshTgAlerts();
}

function closeTelegramAllAlertsModal() {
    document.getElementById('tgAllAlertsModal').classList.remove('active');
}

function refreshTgAlerts() {
    tgAlertsCurrentPage = 1;
    loadTgAlertsPage(1);
}

function loadTgAlertsPage(page) {
    if (page < 1) return;
    tgAlertsCurrentPage = page;

    const level = document.getElementById('tgAlertLevelFilter').value;
    const unreadOnly = document.getElementById('tgUnreadOnlyFilter').checked;

    let url = `/api/telegram/alerts?page=${page}&page_size=20`;
    if (level) url += `&level=${level}`;
    if (unreadOnly) url += '&unread_only=true';

    fetch(url)
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                const data = res.data;
                document.getElementById('tgFullAlertCount').textContent = data.total;
                document.getElementById('tgAlertsPageNum').textContent = data.page;
                document.getElementById('tgAlertsTotalPages').textContent = data.total_pages;
                document.getElementById('tgAlertsPrevBtn').disabled = data.page <= 1;
                document.getElementById('tgAlertsNextBtn').disabled = data.page >= data.total_pages;

                renderTgFullAlertList(data.items);
            }
        })
        .catch(() => {});
}

function renderTgFullAlertList(items) {
    const container = document.getElementById('tgFullAlertList');
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="tg-empty-hint">暂无报警记录</div>';
        return;
    }

    container.innerHTML = items.map(item => {
        const unreadClass = item.is_read ? '' : 'unread';
        const kwTags = (item.matched_keywords || []).map(kw =>
            `<span class="tg-alert-kw-tag level-${item.highest_level}">${escapeHtml(kw)}</span>`
        ).join('');

        return `
            <div class="tg-full-alert-item ${unreadClass}">
                <div class="tg-full-alert-header">
                    <div class="tg-full-alert-meta">
                        <span class="tg-full-alert-level ${item.highest_level}">
                            ${{high:'高风险', medium:'中风险', low:'关注'}[item.highest_level] || ''}
                        </span>
                        <span class="tg-full-alert-group">${escapeHtml(item.group_title)}</span>
                        <span class="tg-full-alert-sender">${escapeHtml(item.sender_name)}</span>
                    </div>
                    <span class="tg-full-alert-time">${item.timestamp || ''}</span>
                </div>
                <div class="tg-full-alert-content">${escapeHtml(item.content)}</div>
                <div class="tg-full-alert-footer">
                    <div class="tg-alert-keywords">${kwTags}</div>
                    <div class="tg-full-alert-actions">
                        ${!item.is_read ? `<button class="btn btn-outline btn-sm" onclick="markTgAlertReadFull('${item.id}', this)">标记已读</button>` : '<span style="font-size:11px;color:var(--text-muted)">已读</span>'}
                        ${item.webhook_sent ? '<span style="font-size:11px;color:var(--secondary)">已推送</span>' : ''}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function markTgAlertReadFull(alertId, btn) {
    fetch(`/api/telegram/alerts/${alertId}/read`, { method: 'POST' })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                btn.closest('.tg-full-alert-item').classList.remove('unread');
                btn.outerHTML = '<span style="font-size:11px;color:var(--text-muted)">已读</span>';
                loadTgOverviewStats();
                loadTgRecentAlerts();
            }
        })
        .catch(() => {});
}

// ---------- 统计分析弹窗 ----------

function openTelegramStatsModal() {
    document.getElementById('tgStatsModal').classList.add('active');
    loadTgStatsCharts();
}

function closeTelegramStatsModal() {
    document.getElementById('tgStatsModal').classList.remove('active');
}

function loadTgStatsCharts() {
    // 报警趋势
    fetch('/api/telegram/stats/alert-trend?days=7')
        .then(r => r.json())
        .then(res => {
            if (res.success) renderTgAlertTrendChart(res.data);
        })
        .catch(() => {});

    // 关键词热度
    fetch('/api/telegram/stats/keyword-hotness?limit=10')
        .then(r => r.json())
        .then(res => {
            if (res.success) renderTgKeywordHotnessChart(res.data);
        })
        .catch(() => {});

    // 群组活跃度
    fetch('/api/telegram/stats/group-activity?days=7')
        .then(r => r.json())
        .then(res => {
            if (res.success) renderTgGroupActivityChart(res.data);
        })
        .catch(() => {});
}

function renderTgAlertTrendChart(data) {
    const dom = document.getElementById('tgAlertTrendChart');
    if (!dom) return;
    const chart = echarts.init(dom);

    const dates = data.map(d => d.date);
    const highData = data.map(d => d.high || 0);
    const mediumData = data.map(d => d.medium || 0);
    const lowData = data.map(d => d.low || 0);

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: {
            data: ['高风险', '中风险', '关注'],
            textStyle: { color: '#8a94a6', fontSize: 11 },
            top: 0,
        },
        grid: { top: 30, right: 15, bottom: 25, left: 40 },
        xAxis: {
            type: 'category',
            data: dates,
            axisLabel: { color: '#8a94a6', fontSize: 10 },
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: '#8a94a6', fontSize: 10 },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        },
        series: [
            { name: '高风险', type: 'bar', stack: 'total', data: highData, itemStyle: { color: '#ff4757' } },
            { name: '中风险', type: 'bar', stack: 'total', data: mediumData, itemStyle: { color: '#ffa502' } },
            { name: '关注', type: 'bar', stack: 'total', data: lowData, itemStyle: { color: '#3498db' } },
        ]
    });
}

function renderTgKeywordHotnessChart(data) {
    const dom = document.getElementById('tgKeywordHotnessChart');
    if (!dom) return;
    const chart = echarts.init(dom);

    const keywords = data.map(d => d.keyword).reverse();
    const counts = data.map(d => d.match_count).reverse();
    const colors = data.map(d => {
        return { high: '#ff4757', medium: '#ffa502', low: '#3498db' }[d.level] || '#3498db';
    }).reverse();

    chart.setOption({
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { top: 10, right: 30, bottom: 25, left: 80 },
        xAxis: {
            type: 'value',
            axisLabel: { color: '#8a94a6', fontSize: 10 },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        },
        yAxis: {
            type: 'category',
            data: keywords,
            axisLabel: { color: '#8a94a6', fontSize: 11 },
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        },
        series: [{
            type: 'bar',
            data: counts.map((v, i) => ({ value: v, itemStyle: { color: colors[i] } })),
            barWidth: '60%',
        }]
    });
}

function renderTgGroupActivityChart(data) {
    const dom = document.getElementById('tgGroupActivityChart');
    if (!dom) return;
    const chart = echarts.init(dom);

    const groups = data.map(d => d.group_title);
    const msgCounts = data.map(d => d.message_count);
    const alertCounts = data.map(d => d.alert_count);

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: {
            data: ['消息数', '报警数'],
            textStyle: { color: '#8a94a6', fontSize: 11 },
            top: 0,
        },
        grid: { top: 30, right: 15, bottom: 40, left: 40 },
        xAxis: {
            type: 'category',
            data: groups,
            axisLabel: { color: '#8a94a6', fontSize: 10, rotate: 20 },
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: '#8a94a6', fontSize: 10 },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        },
        series: [
            { name: '消息数', type: 'bar', data: msgCounts, itemStyle: { color: '#0088ff' } },
            { name: '报警数', type: 'bar', data: alertCounts, itemStyle: { color: '#ff4757' } },
        ]
    });
}


// ==================== 布局编辑模式 ====================

// 编辑模式状态变量
let isEditMode = false;
let layoutModified = false;
let resizeHandles = [];

// 默认布局配置
const LAYOUT_DEFAULTS = {
    panels: {
        'panel-left': { width: '22%' },
        'panel-right': { width: '25%' }
    },
    cards: {
        'stats-overview': { flex: null, height: null },
        'source-chart': { flex: '1', height: null },
        'latest-articles': { flex: '1', height: null },
        'world-map': { flex: null, height: 'calc(62% + 7.5px)' },
        'achievements': { flex: '0 0 100px', height: null },
        'telegram': { flex: '1', height: null },
        'duty': { flex: null, height: null },
        'risk-monitor': { flex: null, height: null },
        'keyword-chart': { flex: null, height: null },
        'risk-alerts': { flex: '2', height: null }
    }
};

// ---------- 页面加载时读取并应用保存的布局 ----------

async function loadSavedLayout() {
    try {
        const res = await fetch('/api/layout');
        const data = await res.json();
        if (data.success && data.data && Object.keys(data.data).length > 0) {
            applyLayout(data.data);
        }
    } catch (e) {
        // 加载失败使用默认布局，不影响页面
    }
}

/**
 * 将布局配置应用到 DOM
 */
function applyLayout(layout) {
    // 应用面板宽度
    if (layout.panels) {
        const mainContent = document.querySelector('.main-content');
        if (layout.panels['panel-left']) {
            const pl = mainContent.querySelector('.panel-left');
            if (pl) pl.style.width = layout.panels['panel-left'].width;
        }
        if (layout.panels['panel-right']) {
            const pr = mainContent.querySelector('.panel-right');
            if (pr) pr.style.width = layout.panels['panel-right'].width;
        }
    }

    // 应用卡片 flex/height
    if (layout.cards) {
        Object.entries(layout.cards).forEach(([id, cfg]) => {
            const card = document.querySelector(`[data-layout-id="${id}"]`);
            if (!card) return;
            if (cfg.flex) {
                card.style.flex = cfg.flex;
            }
            if (cfg.height) {
                card.style.height = cfg.height;
            }
        });
    }

    // 触发图表重绘
    setTimeout(() => handleResize(), 100);
}

// ---------- 进入/退出编辑模式 ----------

function toggleEditMode() {
    if (isEditMode) {
        exitEditMode();
    } else {
        enterEditMode();
    }
}

function enterEditMode() {
    isEditMode = true;
    layoutModified = false;
    document.body.classList.add('edit-mode');

    // 暂停自动刷新
    if (refreshTimer) clearInterval(refreshTimer);
    if (articleRefreshTimer) clearInterval(articleRefreshTimer);
    refreshTimer = null;
    articleRefreshTimer = null;

    // 更新底部刷新状态提示
    const statusEl = document.getElementById('autoRefreshStatus');
    if (statusEl) {
        statusEl.innerHTML = '<span class="refresh-dot" style="background:#ffa502;box-shadow:0 0 6px #ffa502;"></span>编辑模式（刷新已暂停）';
    }

    // 创建浮动工具栏
    createEditToolbar();

    // 创建所有 resize handle
    createResizeHandles();

    // 更新底部按钮状态
    const btn = document.getElementById('btnEditLayout');
    if (btn) btn.classList.add('edit-active');

    showToast('已进入布局编辑模式，拖拽分隔条调整大小', 'success');
}

function exitEditMode() {
    if (layoutModified) {
        if (confirm('布局已修改但未保存，是否保存？')) {
            saveLayout();
        }
    }
    isEditMode = false;
    document.body.classList.remove('edit-mode');

    // 移除所有 handle 和工具栏
    removeResizeHandles();
    removeEditToolbar();

    // 恢复自动刷新
    startAutoRefresh();
    startArticleAutoRefresh();

    // 恢复底部刷新状态
    const statusEl = document.getElementById('autoRefreshStatus');
    if (statusEl) {
        statusEl.innerHTML = '<span class="refresh-dot"></span>自动刷新中';
    }

    // 更新按钮状态
    const btn = document.getElementById('btnEditLayout');
    if (btn) btn.classList.remove('edit-active');
}

// ---------- 浮动编辑工具栏 ----------

function createEditToolbar() {
    const toolbar = document.createElement('div');
    toolbar.className = 'edit-toolbar';
    toolbar.id = 'editToolbar';
    toolbar.innerHTML = `
        <span class="toolbar-label">编辑模式</span>
        <span class="toolbar-divider"></span>
        <button class="toolbar-btn btn-save-layout" onclick="saveLayout()">保存布局</button>
        <button class="toolbar-btn" onclick="resetLayout()">重置默认</button>
        <button class="toolbar-btn btn-exit-edit" onclick="exitEditMode()">退出编辑</button>
    `;
    document.body.appendChild(toolbar);
}

function removeEditToolbar() {
    const el = document.getElementById('editToolbar');
    if (el) el.remove();
}

// ---------- 创建/移除 resize handle ----------

function createResizeHandles() {
    const mainContent = document.querySelector('.main-content');
    const panels = mainContent.querySelectorAll('.panel');

    // 在面板之间插入垂直 handle
    // 面板排列：panel-left, panel-center, panel-right
    const panelLeft = mainContent.querySelector('.panel-left');
    const panelCenter = mainContent.querySelector('.panel-center');
    const panelRight = mainContent.querySelector('.panel-right');

    if (panelLeft && panelCenter) {
        const handle = document.createElement('div');
        handle.className = 'resize-handle resize-handle-v';
        handle.dataset.leftPanel = 'panel-left';
        handle.dataset.rightPanel = 'panel-center';
        panelLeft.after(handle);
        resizeHandles.push(handle);
        handle.addEventListener('mousedown', (e) => onPanelResizeStart(e, handle, panelLeft, panelCenter, 'left'));
    }

    if (panelCenter && panelRight) {
        const handle = document.createElement('div');
        handle.className = 'resize-handle resize-handle-v';
        handle.dataset.leftPanel = 'panel-center';
        handle.dataset.rightPanel = 'panel-right';
        panelRight.before(handle);
        resizeHandles.push(handle);
        handle.addEventListener('mousedown', (e) => onPanelResizeStart(e, handle, panelCenter, panelRight, 'right'));
    }

    // 在每个面板内的卡片之间插入水平 handle
    panels.forEach(panel => {
        const cards = Array.from(panel.children).filter(el => el.classList.contains('card'));
        for (let i = 0; i < cards.length - 1; i++) {
            const handle = document.createElement('div');
            handle.className = 'resize-handle resize-handle-h';
            handle.dataset.aboveCard = cards[i].dataset.layoutId;
            handle.dataset.belowCard = cards[i + 1].dataset.layoutId;
            cards[i].after(handle);
            resizeHandles.push(handle);
            handle.addEventListener('mousedown', (e) => onCardResizeStart(e, handle, cards[i], cards[i + 1], panel));
        }
    });
}

function removeResizeHandles() {
    resizeHandles.forEach(h => h.remove());
    resizeHandles = [];
}

// ---------- 面板宽度拖拽 ----------

function onPanelResizeStart(e, handle, leftPanel, rightPanel, side) {
    e.preventDefault();
    handle.classList.add('active');
    document.body.classList.add('resizing');
    document.body.style.cursor = 'col-resize';

    const mainContent = document.querySelector('.main-content');
    const mainWidth = mainContent.clientWidth;
    const startX = e.clientX;
    const startLeftW = leftPanel.getBoundingClientRect().width;
    const startRightW = rightPanel.getBoundingClientRect().width;

    function onMouseMove(e) {
        const deltaX = e.clientX - startX;

        if (side === 'left') {
            // 拖拽 panel-left 和 panel-center 之间的分隔条
            let newLeftW = startLeftW + deltaX;
            // 最小宽度约束
            const minW = mainWidth * 0.12;
            const maxW = mainWidth * 0.40;
            newLeftW = Math.max(minW, Math.min(maxW, newLeftW));
            leftPanel.style.width = (newLeftW / mainWidth * 100) + '%';
        } else {
            // 拖拽 panel-center 和 panel-right 之间的分隔条
            let newRightW = startRightW - deltaX;
            const minW = mainWidth * 0.12;
            const maxW = mainWidth * 0.40;
            newRightW = Math.max(minW, Math.min(maxW, newRightW));
            rightPanel.style.width = (newRightW / mainWidth * 100) + '%';
        }

        layoutModified = true;
        // 实时触发图表重绘
        requestAnimationFrame(() => handleResize());
    }

    function onMouseUp() {
        handle.classList.remove('active');
        document.body.classList.remove('resizing');
        document.body.style.cursor = '';
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        handleResize();
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
}

// ---------- 卡片高度拖拽 ----------

function onCardResizeStart(e, handle, aboveCard, belowCard, panel) {
    e.preventDefault();
    handle.classList.add('active');
    document.body.classList.add('resizing');
    document.body.style.cursor = 'row-resize';

    const startY = e.clientY;
    const aboveRect = aboveCard.getBoundingClientRect();
    const belowRect = belowCard.getBoundingClientRect();
    const startAboveH = aboveRect.height;
    const startBelowH = belowRect.height;
    const totalH = startAboveH + startBelowH;
    const minH = 60; // 最小卡片高度

    function onMouseMove(e) {
        const deltaY = e.clientY - startY;
        let newAboveH = startAboveH + deltaY;
        let newBelowH = startBelowH - deltaY;

        // 施加最小高度约束
        if (newAboveH < minH) {
            newAboveH = minH;
            newBelowH = totalH - minH;
        }
        if (newBelowH < minH) {
            newBelowH = minH;
            newAboveH = totalH - minH;
        }

        // 转换为 flex 比例
        const aboveRatio = newAboveH / totalH;
        const belowRatio = newBelowH / totalH;

        aboveCard.style.flex = aboveRatio.toFixed(4);
        belowCard.style.flex = belowRatio.toFixed(4);

        // 清除可能的固定高度
        aboveCard.style.height = '';
        belowCard.style.height = '';

        layoutModified = true;
        requestAnimationFrame(() => handleResize());
    }

    function onMouseUp() {
        handle.classList.remove('active');
        document.body.classList.remove('resizing');
        document.body.style.cursor = '';
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        handleResize();
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
}

// ---------- 保存/加载/重置布局 ----------

/**
 * 收集当前布局数据并保存到后端
 */
async function saveLayout() {
    const mainContent = document.querySelector('.main-content');
    const mainWidth = mainContent.clientWidth;
    const layout = { panels: {}, cards: {} };

    // 收集面板宽度
    const panelLeft = mainContent.querySelector('.panel-left');
    const panelRight = mainContent.querySelector('.panel-right');
    if (panelLeft) {
        const w = panelLeft.getBoundingClientRect().width;
        layout.panels['panel-left'] = { width: (w / mainWidth * 100).toFixed(2) + '%' };
    }
    if (panelRight) {
        const w = panelRight.getBoundingClientRect().width;
        layout.panels['panel-right'] = { width: (w / mainWidth * 100).toFixed(2) + '%' };
    }

    // 收集卡片 flex 值
    document.querySelectorAll('[data-layout-id]').forEach(card => {
        const id = card.dataset.layoutId;
        const computedStyle = window.getComputedStyle(card);
        const flexGrow = computedStyle.flexGrow;
        const flexShrink = computedStyle.flexShrink;
        const flexBasis = computedStyle.flexBasis;

        // 检查是否有内联 flex 样式
        const inlineFlex = card.style.flex;
        const inlineHeight = card.style.height;

        if (inlineFlex) {
            layout.cards[id] = { flex: inlineFlex, height: null };
        } else if (inlineHeight) {
            layout.cards[id] = { flex: null, height: inlineHeight };
        }
        // 无内联样式的卡片不保存（使用CSS默认值）
    });

    try {
        const res = await fetch('/api/layout', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(layout)
        });
        const data = await res.json();
        if (data.success) {
            layoutModified = false;
            showToast('布局已保存', 'success');
        } else {
            showToast(data.error || '保存失败', 'error');
        }
    } catch (e) {
        showToast('保存布局请求失败', 'error');
    }
}

/**
 * 重置布局为默认值
 */
async function resetLayout() {
    if (!confirm('确定恢复默认布局？')) return;

    // 清除所有内联样式
    const panelLeft = document.querySelector('.panel-left');
    const panelRight = document.querySelector('.panel-right');
    if (panelLeft) panelLeft.style.width = '';
    if (panelRight) panelRight.style.width = '';

    document.querySelectorAll('[data-layout-id]').forEach(card => {
        card.style.flex = '';
        card.style.height = '';
    });

    // 删除后端保存的布局
    try {
        await fetch('/api/layout', { method: 'DELETE' });
    } catch (e) {
        // 忽略
    }

    layoutModified = false;
    handleResize();
    showToast('已恢复默认布局', 'success');
}

// ========== 移动端交互逻辑 ==========

/**
 * 判断当前是否为移动端视口
 */
function isMobileView() {
    return window.innerWidth <= 768;
}

/**
 * 移动端菜单切换 - 弹出更多操作面板
 */
function toggleMobileMenu() {
    const overlay = document.getElementById('mobilePanelOverlay');
    if (!overlay) return;

    if (overlay.classList.contains('active')) {
        closeMobileMenu();
    } else {
        overlay.classList.add('active');
        // 显示一个快捷操作弹窗
        openMobileMoreMenu();
    }
}

/**
 * 关闭移动端菜单
 */
function closeMobileMenu() {
    const overlay = document.getElementById('mobilePanelOverlay');
    if (overlay) overlay.classList.remove('active');
    // 关闭更多菜单弹窗
    const moreModal = document.getElementById('mobileMoreModal');
    if (moreModal) moreModal.classList.remove('active');
}

/**
 * 打开移动端"更多"菜单
 */
function openMobileMoreMenu() {
    let modal = document.getElementById('mobileMoreModal');
    if (!modal) {
        // 动态创建更多菜单弹窗
        modal = document.createElement('div');
        modal.id = 'mobileMoreModal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal modal-sm" style="width:90vw;max-width:360px;height:auto;border-radius:12px;">
                <div class="modal-header">
                    <h3 class="modal-title">更多操作</h3>
                    <button class="modal-close" onclick="closeMobileMenu()">&times;</button>
                </div>
                <div class="modal-body" style="padding:12px;">
                    <div style="display:flex;flex-direction:column;gap:8px;">
                        <button class="btn btn-outline" style="width:100%;justify-content:flex-start;min-height:44px;" onclick="closeMobileMenu();openLogsModal();">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                <polyline points="14 2 14 8 20 8"></polyline>
                            </svg>
                            后台日志
                        </button>
                        <button class="btn btn-outline" style="width:100%;justify-content:flex-start;min-height:44px;" onclick="closeMobileMenu();openKeywordModal();">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="12" cy="12" r="3"></circle>
                                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                            </svg>
                            风控关键词
                        </button>
                        <button class="btn btn-outline" style="width:100%;justify-content:flex-start;min-height:44px;" onclick="closeMobileMenu();openAllAlertsModal();">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                                <line x1="12" y1="9" x2="12" y2="13"></line>
                                <line x1="12" y1="17" x2="12.01" y2="17"></line>
                            </svg>
                            全部告警
                        </button>
                        <button class="btn btn-outline" style="width:100%;justify-content:flex-start;min-height:44px;" onclick="closeMobileMenu();openDutyModal();">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                                <circle cx="12" cy="7" r="4"></circle>
                            </svg>
                            值班设置
                        </button>
                        <button class="btn btn-outline" style="width:100%;justify-content:flex-start;min-height:44px;" onclick="closeMobileMenu();openTelegramSettingsModal();">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="22" y1="2" x2="11" y2="13"></line>
                                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                            </svg>
                            Telegram设置
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }
    modal.classList.add('active');
}

/**
 * 增强handleResize - 移动端图表重绘
 */
const _originalHandleResize = handleResize;
// 覆盖原有的handleResize，增加移动端延迟resize
window.handleResize = function() {
    _originalHandleResize();
    // 移动端延迟再次resize，确保布局稳定后图表正确渲染
    if (isMobileView()) {
        setTimeout(() => {
            if (typeof sourceChart !== 'undefined' && sourceChart) sourceChart.resize();
            if (typeof keywordChart !== 'undefined' && keywordChart) keywordChart.resize();
            if (typeof worldMap !== 'undefined' && worldMap) worldMap.invalidateSize();
        }, 300);
    }
};

/**
 * 移动端弹窗关闭 - 支持返回键
 */
window.addEventListener('popstate', function() {
    if (!isMobileView()) return;
    // 查找当前打开的弹窗并关闭
    const activeModal = document.querySelector('.modal-overlay.active');
    if (activeModal) {
        activeModal.classList.remove('active');
    }
});

/**
 * 移动端弹窗打开时禁止背景滚动
 */
const _mobileModalObserver = new MutationObserver(function(mutations) {
    if (!isMobileView()) return;
    const anyModalActive = document.querySelector('.modal-overlay.active');
    if (anyModalActive) {
        document.body.style.overflow = 'hidden';
    } else {
        document.body.style.overflow = '';
    }
});

// 监听所有modal-overlay的class变化
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.modal-overlay').forEach(function(modal) {
        _mobileModalObserver.observe(modal, { attributes: true, attributeFilter: ['class'] });
    });
});
