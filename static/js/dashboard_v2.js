// Dashboard V2 - Multi-Page Market Maker Dashboard
// State Management
const state = {
    currentPage: 'overview',
    charts: {},
    updateInterval: null,
    pnlPeriod: 'daily'
};

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initCharts();
    
    // Delay initial fetch to ensure charts are ready
    setTimeout(() => {
        fetchAllData();
    }, 100);
    
    // Update every 5 seconds
    state.updateInterval = setInterval(fetchAllData, 5000);
    
    // Refresh button
    document.getElementById('refreshBtn').addEventListener('click', () => {
        fetchAllData();
        animateRefresh();
    });
    
    // P&L breakdown tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            state.pnlPeriod = e.target.dataset.period;
            updatePnlBreakdown();
        });
    });
});

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;
            switchPage(page);
        });
    });
}

function switchPage(page) {
    // Update nav
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });
    
    // Update pages
    document.querySelectorAll('.page').forEach(p => {
        p.classList.toggle('active', p.id === `page-${page}`);
    });
    
    // Update title
    const titles = {
        overview: 'Overview',
        trading: 'Trading',
        performance: 'Performance',
        risk: 'Risk Management'
    };
    document.getElementById('pageTitle').textContent = titles[page];
    
    state.currentPage = page;
    
    // Refresh data for new page
    fetchAllData();
}

function animateRefresh() {
    const btn = document.getElementById('refreshBtn');
    btn.style.animation = 'spin 0.5s ease-in-out';
    setTimeout(() => {
        btn.style.animation = '';
    }, 500);
}

// Data Fetching
async function fetchAllData() {
    try {
        await Promise.all([
            fetchStats(),
            fetchMarketData(),
            fetchVolatility(),
            fetchUnrealizedPnl(),
            fetchPerformanceMetrics(),
            fetchPnlBreakdown(),
            fetchSystemHealth(),
            fetchRecentTrades(),
            fetchCurrentPosition(),
            fetchTradeHistory(),
            fetchPositionHistory(),
            fetchSpreadHistory()
        ]);
        updateConnectionStatus(true);
    } catch (error) {
        console.error('Error fetching data:', error);
        updateConnectionStatus(false);
    }
}

function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('sidebarStatus');
    const dot = statusEl.querySelector('.status-dot');
    const text = statusEl.querySelector('span');
    
    if (connected) {
        dot.style.background = 'var(--success)';
        text.textContent = 'Connected';
    } else {
        dot.style.background = 'var(--danger)';
        text.textContent = 'Disconnected';
    }
}

// API Calls
async function fetchStats() {
    const response = await fetch('/api/stats');
    const data = await response.json();
    
    // Update Overview page
    document.getElementById('realizedPnl').textContent = `$${data.realized_profit.toFixed(4)}`;
    document.getElementById('totalVolume').textContent = `$${data.total_volume.toLocaleString()}`;
    document.getElementById('totalTrades').textContent = `${data.total_trades} trades`;
    document.getElementById('currentPosition').textContent = `${data.current_position.toFixed(2)} USDHL`;
    document.getElementById('avgPrice').textContent = `Avg: $${data.average_buy_price.toFixed(5)}`;
    document.getElementById('usdcBalance').textContent = `$${data.usdc_balance.toFixed(2)}`;
}

async function fetchMarketData() {
    const response = await fetch('/api/market/current');
    const data = await response.json();
    
    // Update live price
    document.querySelector('#livePrice .value').textContent = `$${data.mid_price.toFixed(5)}`;
    
    // Update Trading page
    document.getElementById('bestBid').textContent = `$${data.best_bid.toFixed(5)}`;
    document.getElementById('bestAsk').textContent = `$${data.best_ask.toFixed(5)}`;
    document.getElementById('currentSpread').textContent = `${data.spread_bps.toFixed(1)} bps`;
    document.getElementById('spreadPct').textContent = `${(data.spread_bps / 100).toFixed(2)}%`;
    document.getElementById('bidDepth').textContent = `Depth: ${data.bid_depth.toFixed(0)}`;
    document.getElementById('askDepth').textContent = `Depth: ${data.ask_depth.toFixed(0)}`;
}

async function fetchVolatility() {
    const response = await fetch('/api/market/volatility');
    const data = await response.json();
    
    document.getElementById('volatilityValue').textContent = `${data.volatility_1h.toFixed(2)}%`;
    document.getElementById('priceChange1h').textContent = `$${data.price_change_1h.toFixed(5)}`;
    document.getElementById('high1h').textContent = `$${data.high_1h.toFixed(5)}`;
    document.getElementById('low1h').textContent = `$${data.low_1h.toFixed(5)}`;
    
    // Update live price change
    const changeEl = document.querySelector('#livePrice .change');
    changeEl.textContent = `${data.price_change_pct >= 0 ? '+' : ''}${data.price_change_pct.toFixed(2)}%`;
    changeEl.style.color = data.price_change_pct >= 0 ? 'var(--success)' : 'var(--danger)';
}

async function fetchUnrealizedPnl() {
    const response = await fetch('/api/performance/unrealized_pnl');
    const data = await response.json();
    
    // Overview page
    document.getElementById('unrealizedPnl').textContent = `$${data.unrealized_pnl.toFixed(4)}`;
    const unrealizedChange = document.getElementById('unrealizedChange');
    unrealizedChange.textContent = `${data.unrealized_pnl_pct >= 0 ? '+' : ''}${data.unrealized_pnl_pct.toFixed(2)}%`;
    unrealizedChange.className = `metric-change ${data.unrealized_pnl_pct >= 0 ? 'positive' : 'negative'}`;
    
    // Risk page
    document.getElementById('riskUnrealizedPnl').textContent = `$${data.unrealized_pnl.toFixed(4)}`;
    const riskChange = document.getElementById('riskUnrealizedChange');
    riskChange.textContent = `${data.unrealized_pnl_pct >= 0 ? '+' : ''}${data.unrealized_pnl_pct.toFixed(2)}%`;
    riskChange.className = `metric-change ${data.unrealized_pnl_pct >= 0 ? 'positive' : 'negative'}`;
    
    document.getElementById('totalExposure').textContent = `$${data.cost_basis.toFixed(2)}`;
}

async function fetchPerformanceMetrics() {
    const response = await fetch('/api/performance/stats');
    const data = await response.json();
    
    // Performance page
    document.getElementById('profitFactor').textContent = data.profit_factor.toFixed(2);
    document.getElementById('winRate').textContent = `${data.win_rate.toFixed(1)}%`;
    document.getElementById('winLossRatio').textContent = `${data.total_winning_trades} wins / ${data.total_losing_trades} losses`;
    document.getElementById('totalFees').textContent = `$${data.total_fees.toFixed(4)}`;
    document.getElementById('avgProfitPerTrade').textContent = `$${data.avg_profit_per_trade.toFixed(4)}`;
    
    // Overview page ROI
    document.getElementById('roiValue').textContent = `${data.roi_pct.toFixed(2)}%`;
}

async function fetchPnlBreakdown() {
    const response = await fetch('/api/performance/pnl_breakdown');
    window.pnlBreakdownData = await response.json();
    updatePnlBreakdown();
}

function updatePnlBreakdown() {
    if (!window.pnlBreakdownData) return;
    
    const data = window.pnlBreakdownData[state.pnlPeriod];
    const labels = {
        daily: 'Daily Performance',
        weekly: 'Weekly Performance',
        monthly: 'Monthly Performance'
    };
    
    document.getElementById('pnlPeriodLabel').textContent = labels[state.pnlPeriod];
    
    if (state.charts.pnlBreakdown) {
        state.charts.pnlBreakdown.data.labels = data.map(d => d.period);
        state.charts.pnlBreakdown.data.datasets[0].data = data.map(d => d.pnl);
        state.charts.pnlBreakdown.update('none');
    }
}

async function fetchSystemHealth() {
    const response = await fetch('/api/system/health');
    const data = await response.json();
    
    // Update health banner
    const banner = document.getElementById('healthBanner');
    banner.className = `health-banner ${data.status}`;
    
    document.getElementById('healthStatus').textContent = data.status_message;
    document.getElementById('healthMessage').textContent = 
        data.status === 'healthy' ? 'Bot is running smoothly' : 
        data.status === 'warning' ? 'Some issues detected' : 
        'Critical issues detected';
    
    document.getElementById('lastUpdateTime').textContent = formatSeconds(data.last_update_seconds);
    document.getElementById('lastTradeTime').textContent = formatSeconds(data.last_trade_seconds);
    document.getElementById('errorCount').textContent = data.error_count_1h;
}

async function fetchRecentTrades() {
    const response = await fetch('/api/trades/recent');
    const trades = await response.json();
    
    const container = document.getElementById('recentTradesList');
    document.getElementById('recentTradeCount').textContent = `${trades.length} trades`;
    
    if (trades.length === 0) {
        container.innerHTML = '<div class="loading">No trades yet</div>';
        return;
    }
    
    container.innerHTML = trades.slice(0, 10).map(trade => {
        const date = new Date(trade.timestamp);
        return `
            <div class="trade-item">
                <div>
                    <span class="trade-side ${trade.side}">${trade.side}</span>
                    <span style="margin-left: 12px; color: var(--text-secondary); font-size: 13px;">
                        ${date.toLocaleTimeString()}
                    </span>
                </div>
                <div style="text-align: right;">
                    <div style="font-weight: 600;">${trade.amount.toFixed(2)} @ $${trade.price.toFixed(5)}</div>
                    <div style="font-size: 13px; color: var(--text-muted);">$${trade.cost.toFixed(2)}</div>
                </div>
            </div>
        `;
    }).join('');
}

async function fetchCurrentPosition() {
    // Fetch current stats and market data
    const [statsResponse, marketResponse, unrealizedResponse] = await Promise.all([
        fetch('/api/stats'),
        fetch('/api/market/current'),
        fetch('/api/performance/unrealized_pnl')
    ]);
    
    const stats = await statsResponse.json();
    const market = await marketResponse.json();
    const unrealized = await unrealizedResponse.json();
    
    const MAKER_FEE = 0.0004;
    const position = stats.current_position;
    const avgPrice = stats.average_buy_price;
    const midPrice = market.mid_price;
    
    // Update position display
    document.getElementById('currentPositionAmount').textContent = `${position.toFixed(2)} USDHL`;
    document.getElementById('currentAvgPrice').textContent = `$${avgPrice.toFixed(5)}`;
    
    // Calculate and display metrics
    const costBasis = position * avgPrice;
    const breakevenPrice = avgPrice / (1 - MAKER_FEE);
    
    document.getElementById('totalCostBasis').textContent = `$${costBasis.toFixed(2)}`;
    document.getElementById('breakevenPrice').textContent = `$${breakevenPrice.toFixed(5)}`;
    document.getElementById('currentMarketPrice').textContent = `$${midPrice.toFixed(5)}`;
    document.getElementById('positionUnrealizedPnl').textContent = `$${unrealized.unrealized_pnl.toFixed(2)}`;
    
    const pctElement = document.getElementById('positionUnrealizedPct');
    pctElement.textContent = `${unrealized.unrealized_pnl_pct >= 0 ? '+' : ''}${unrealized.unrealized_pnl_pct.toFixed(2)}%`;
    pctElement.className = 'detail-change ' + (unrealized.unrealized_pnl >= 0 ? 'positive' : 'negative');
}

async function fetchTradeHistory() {
    const response = await fetch('/api/trades/history');
    const history = await response.json();
    
    if (history.length === 0) return;
    
    // Update Overview profit chart
    if (state.charts.overviewProfit) {
        const last24h = history.filter(h => h.timestamp > Date.now() - 24 * 60 * 60 * 1000);
        state.charts.overviewProfit.data.datasets[0].data = last24h.map(h => ({
            x: h.timestamp,
            y: h.cumulative_profit
        }));
        state.charts.overviewProfit.update('none');
    }
    
    // Update Performance profit chart
    if (state.charts.perfProfit) {
        state.charts.perfProfit.data.datasets[0].data = history.map(h => ({
            x: h.timestamp,
            y: h.cumulative_profit
        }));
        state.charts.perfProfit.update('none');
    }
}

async function fetchPositionHistory() {
    const response = await fetch('/api/position/history');
    const history = await response.json();
    
    if (history.length === 0) return;
    
    // Calculate max position
    const maxPos = Math.max(...history.map(h => Math.abs(h.position)));
    document.getElementById('maxPositionValue').textContent = maxPos.toFixed(2);
    
    // Calculate inventory risk
    const currentPos = history[history.length - 1].position;
    const maxPosition = 1000; // From config
    const riskPct = (currentPos / maxPosition * 100);
    document.getElementById('inventoryRisk').textContent = `${riskPct.toFixed(1)}%`;
    
    const riskStatus = riskPct < 40 ? 'Low Risk' : 
                       riskPct < 70 ? 'Moderate Risk' : 
                       riskPct < 90 ? 'High Risk' : 'Critical Risk';
    document.getElementById('inventoryStatus').textContent = riskStatus;
    
    // Update position gauge chart
    if (state.charts.positionGauge) {
        state.charts.positionGauge.data.datasets[0].data = [currentPos, maxPosition - currentPos];
        state.charts.positionGauge.update('none');
    }
    
    // Update risk position chart
    if (state.charts.riskPosition) {
        state.charts.riskPosition.data.datasets[0].data = history.map(h => ({
            x: h.timestamp,
            y: h.position
        }));
        state.charts.riskPosition.update('none');
    }
    
    // Update inventory heatmap
    if (state.charts.inventoryHeatmap) {
        const heatmapData = history.map(h => {
            const pct = (h.position / maxPosition * 100);
            let color;
            if (pct < 40) color = 'rgba(16, 185, 129, 0.6)';
            else if (pct < 70) color = 'rgba(6, 182, 212, 0.6)';
            else if (pct < 90) color = 'rgba(245, 158, 11, 0.6)';
            else color = 'rgba(239, 68, 68, 0.6)';
            
            return {
                x: h.timestamp,
                y: pct,
                backgroundColor: color
            };
        });
        
        state.charts.inventoryHeatmap.data.datasets[0].data = heatmapData;
        state.charts.inventoryHeatmap.update('none');
    }
}

async function fetchSpreadHistory() {
    const response = await fetch('/api/market/spread_history');
    const history = await response.json();
    
    if (history.length === 0) return;
    
    // Calculate spread stats
    const spreads = history.map(h => h.spread_bps);
    const avgSpread = spreads.reduce((a, b) => a + b, 0) / spreads.length;
    const minSpread = Math.min(...spreads);
    const maxSpread = Math.max(...spreads);
    
    document.getElementById('avgSpread').textContent = `${avgSpread.toFixed(1)} bps`;
    document.getElementById('minSpread').textContent = `${minSpread.toFixed(1)} bps`;
    document.getElementById('maxSpread').textContent = `${maxSpread.toFixed(1)} bps`;
    
    // Update spread chart
    if (state.charts.spread) {
        state.charts.spread.data.datasets[0].data = history.map(h => ({
            x: h.timestamp,
            y: h.spread_bps
        }));
        state.charts.spread.update('none');
    }
}

// Chart Initialization
function initCharts() {
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                titleColor: '#f8fafc',
                bodyColor: '#cbd5e1',
                borderColor: 'rgba(99, 102, 241, 0.3)',
                borderWidth: 1,
                padding: 12,
            }
        },
        scales: {
            x: {
                type: 'time',
                time: { tooltipFormat: 'MMM dd, HH:mm' },
                grid: { color: 'rgba(148, 163, 184, 0.08)' },
                ticks: { color: '#64748b' }
            },
            y: {
                grid: { color: 'rgba(148, 163, 184, 0.08)' },
                ticks: { color: '#64748b' }
            }
        }
    };
    
    // Overview Profit Chart
    const overviewProfitCtx = document.getElementById('overviewProfitChart').getContext('2d');
    state.charts.overviewProfit = new Chart(overviewProfitCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Profit',
                data: [],
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                fill: true,
                tension: 0.4,
                borderWidth: 2
            }]
        },
        options: chartOptions
    });
    
    // Position Gauge Chart
    const positionGaugeCtx = document.getElementById('positionGaugeChart').getContext('2d');
    state.charts.positionGauge = new Chart(positionGaugeCtx, {
        type: 'doughnut',
        data: {
            labels: ['Current Position', 'Available'],
            datasets: [{
                data: [0, 1000],
                backgroundColor: ['#6366f1', 'rgba(148, 163, 184, 0.1)'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            }
        }
    });
    
    // Spread Chart
    const spreadCtx = document.getElementById('spreadChart').getContext('2d');
    state.charts.spread = new Chart(spreadCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Spread (bps)',
                data: [],
                borderColor: '#06b6d4',
                backgroundColor: 'rgba(6, 182, 212, 0.1)',
                fill: true,
                tension: 0.4,
                borderWidth: 2
            }]
        },
        options: chartOptions
    });
    
    // P&L Breakdown Chart
    const pnlBreakdownCtx = document.getElementById('pnlBreakdownChart').getContext('2d');
    state.charts.pnlBreakdown = new Chart(pnlBreakdownCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'P&L',
                data: [],
                backgroundColor: (context) => {
                    // Handle undefined data during initialization
                    if (!context.parsed || context.parsed.y === undefined) {
                        return 'rgba(16, 185, 129, 0.6)';
                    }
                    const value = context.parsed.y;
                    return value >= 0 ? 'rgba(16, 185, 129, 0.6)' : 'rgba(239, 68, 68, 0.6)';
                },
                borderWidth: 0
            }]
        },
        options: {
            ...chartOptions,
            scales: {
                ...chartOptions.scales,
                x: { type: 'category' }
            }
        }
    });
    
    // Performance Profit Chart
    const perfProfitCtx = document.getElementById('perfProfitChart').getContext('2d');
    state.charts.perfProfit = new Chart(perfProfitCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Cumulative Profit',
                data: [],
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                fill: true,
                tension: 0.4,
                borderWidth: 2
            }]
        },
        options: chartOptions
    });
    
    // Trade Distribution Chart
    const tradeDistCtx = document.getElementById('tradeDistChart').getContext('2d');
    state.charts.tradeDist = new Chart(tradeDistCtx, {
        type: 'doughnut',
        data: {
            labels: ['Winning Trades', 'Losing Trades'],
            datasets: [{
                data: [0, 0],
                backgroundColor: ['#10b981', '#ef4444'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#cbd5e1' } }
            }
        }
    });
    
    // Inventory Heatmap Chart
    const inventoryHeatmapCtx = document.getElementById('inventoryHeatmapChart').getContext('2d');
    state.charts.inventoryHeatmap = new Chart(inventoryHeatmapCtx, {
        type: 'bar',
        data: {
            datasets: [{
                label: 'Inventory Risk %',
                data: [],
                backgroundColor: 'rgba(99, 102, 241, 0.6)',
                borderWidth: 0
            }]
        },
        options: chartOptions
    });
    
    // Risk Position Chart
    const riskPositionCtx = document.getElementById('riskPositionChart').getContext('2d');
    state.charts.riskPosition = new Chart(riskPositionCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Position',
                data: [],
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                fill: true,
                tension: 0.4,
                borderWidth: 2
            }]
        },
        options: chartOptions
    });
    
    // Unrealized P&L Chart
    const unrealizedPnlCtx = document.getElementById('unrealizedPnlChart').getContext('2d');
    state.charts.unrealizedPnl = new Chart(unrealizedPnlCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Unrealized P&L',
                data: [],
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                fill: true,
                tension: 0.4,
                borderWidth: 2
            }]
        },
        options: chartOptions
    });
}

// Utility Functions
function formatSeconds(seconds) {
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

// Add CSS animation for refresh button
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);
