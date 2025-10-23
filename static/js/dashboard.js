// Dashboard state
let profitChart, volumeChart, positionChart;
let previousProfit = 0;
let updateInterval;
let allTradeHistory = [];
let allPositionHistory = [];
let currentTimeRange = { profit: 'all', volume: 'all', position: 'all' };

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    fetchData();
    updateInterval = setInterval(fetchData, 5000); // Update every 5 seconds
    
    // Setup refresh button
    document.getElementById('refreshBtn').addEventListener('click', () => {
        fetchData();
        animateRefreshButton();
    });
    
    // Hide loading overlay after initial load
    setTimeout(() => {
        document.getElementById('loadingOverlay').classList.add('hidden');
    }, 1000);
});

function animateRefreshButton() {
    const btn = document.getElementById('refreshBtn');
    btn.style.animation = 'spin 0.5s ease-in-out';
    setTimeout(() => {
        btn.style.animation = '';
    }, 500);
}

// Fetch all data
async function fetchData() {
    try {
        await Promise.all([
            fetchStats(),
            fetchRecentTrades(),
            fetchTradeHistory(),
            fetchPositionHistory(),
            fetchOpenPositions()
        ]);
        updateStatus(true);
    } catch (error) {
        console.error('Error fetching data:', error);
        updateStatus(false);
    }
}

// Update connection status
function updateStatus(connected) {
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    
    if (connected) {
        statusDot.style.background = '#10b981';
        statusText.textContent = 'Live';
    } else {
        statusDot.style.background = '#ef4444';
        statusText.textContent = 'Disconnected';
    }
}

// Fetch statistics
async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        // Update metrics
        const profitChange = data.realized_profit - previousProfit;
        const profitChangePercent = previousProfit !== 0 ? (profitChange / Math.abs(previousProfit)) * 100 : 0;
        
        document.getElementById('realizedProfit').textContent = `$${data.realized_profit.toFixed(4)}`;
        
        const profitChangeEl = document.getElementById('profitChange');
        const changeSpan = profitChangeEl.querySelector('span');
        if (changeSpan) {
            changeSpan.textContent = `${profitChange >= 0 ? '+' : ''}${profitChangePercent.toFixed(2)}%`;
        }
        profitChangeEl.className = `metric-change ${profitChange >= 0 ? 'positive' : 'negative'}`;
        
        // Update arrow direction
        const arrow = profitChangeEl.querySelector('svg path');
        if (arrow && profitChange < 0) {
            arrow.setAttribute('d', 'M7 10l5 5 5-5z'); // Down arrow
        }
        
        document.getElementById('totalVolume').textContent = `$${data.total_volume.toLocaleString()}`;
        document.getElementById('totalTrades').textContent = `${data.total_trades} trades`;
        
        document.getElementById('currentPosition').textContent = `${data.current_position.toFixed(2)} USDHL`;
        document.getElementById('avgPrice').textContent = `Avg: $${data.average_buy_price.toFixed(5)}`;
        
        document.getElementById('usdcBalance').textContent = `$${data.usdc_balance.toFixed(2)}`;
        
        if (data.last_update) {
            const lastUpdate = new Date(data.last_update * 1000);
            const now = new Date();
            const diffSeconds = Math.floor((now - lastUpdate) / 1000);
            let timeAgo;
            
            if (diffSeconds < 60) {
                timeAgo = `${diffSeconds}s ago`;
            } else if (diffSeconds < 3600) {
                timeAgo = `${Math.floor(diffSeconds / 60)}m ago`;
            } else {
                timeAgo = `${Math.floor(diffSeconds / 3600)}h ago`;
            }
            
            document.getElementById('lastUpdate').textContent = `Last update: ${timeAgo}`;
        }
        
        document.getElementById('totalBuys').textContent = data.total_buys;
        document.getElementById('totalSells').textContent = data.total_sells;
        
        // Calculate insights
        const winRate = data.total_sells > 0 ? (data.total_sells / (data.total_buys + data.total_sells)) * 100 : 0;
        document.getElementById('winRate').textContent = `${winRate.toFixed(1)}%`;
        
        const avgTradeSize = data.total_trades > 0 ? data.total_volume / data.total_trades : 0;
        document.getElementById('avgTradeSize').textContent = `$${avgTradeSize.toFixed(2)}`;
        
        previousProfit = data.realized_profit;
        
        // Update footer time
        updateFooterTime();
    } catch (error) {
        console.error('Error fetching stats:', error);
        throw error;
    }
}

function updateFooterTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString();
    const footerTime = document.getElementById('footerTime');
    if (footerTime) {
        footerTime.textContent = timeStr;
    }
}

// Fetch recent trades
async function fetchRecentTrades() {
    try {
        const response = await fetch('/api/trades/recent');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const trades = await response.json();
    
    const tbody = document.getElementById('tradesTableBody');
    
    if (trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="no-data"><span>No trades yet</span></td></tr>';
        return;
    }
    
    const MAKER_FEE = 0.0004;
    
    tbody.innerHTML = trades.map(trade => {
        const date = new Date(trade.timestamp); // Timestamp is already in milliseconds
        const timeStr = date.toLocaleTimeString();
        const fee = trade.cost * MAKER_FEE;
        
        return `
            <tr>
                <td>${timeStr}</td>
                <td><span class="trade-side ${trade.side}">${trade.side}</span></td>
                <td>$${trade.price.toFixed(5)}</td>
                <td>${trade.amount.toFixed(2)}</td>
                <td>$${trade.cost.toFixed(2)}</td>
                <td style="color: var(--danger)">$${fee.toFixed(4)}</td>
            </tr>
        `;
    }).join('');
    } catch (error) {
        console.error('Error fetching recent trades:', error);
        throw error;
    }
}

// Fetch open positions
async function fetchOpenPositions() {
    try {
        const response = await fetch('/api/positions/open');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        // Update summary stats
        document.getElementById('totalOpenPositions').textContent = data.summary.total_positions;
        document.getElementById('totalOpenAmount').textContent = `${data.summary.total_amount.toFixed(2)} USDHL`;
        document.getElementById('openPositionsAvg').textContent = `$${data.summary.average_price.toFixed(5)}`;
        
        const tbody = document.getElementById('openPositionsTableBody');
        
        if (data.positions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="no-data"><span>No open positions</span></td></tr>';
            return;
        }
        
        tbody.innerHTML = data.positions.map((pos, index) => {
            const date = new Date(pos.timestamp);
            const timeStr = date.toLocaleTimeString();
            const dateStr = date.toLocaleDateString();
            
            // Determine if position is partially filled
            const isPartial = pos.remaining_amount < pos.original_amount;
            const statusBadge = isPartial 
                ? `<span class="status-badge partial">Partial (${((pos.remaining_amount / pos.original_amount) * 100).toFixed(0)}%)</span>`
                : `<span class="status-badge open">Open</span>`;
            
            return `
                <tr class="position-row ${index === 0 ? 'oldest-position' : ''}">
                    <td>
                        <span class="position-order">#${index + 1}</span>
                        ${index === 0 ? '<span class="badge-fifo">NEXT</span>' : ''}
                    </td>
                    <td>
                        <div class="time-cell">
                            <div>${timeStr}</div>
                            <div class="time-date">${dateStr}</div>
                        </div>
                    </td>
                    <td>${pos.remaining_amount.toFixed(2)} USDHL</td>
                    <td>
                        <div class="price-cell">
                            <div class="price-main">$${pos.price_with_fee.toFixed(5)}</div>
                            <div class="price-sub">Total: $${pos.cost_basis.toFixed(2)}</div>
                        </div>
                    </td>
                    <td>
                        <span class="min-profitable">$${pos.min_profitable_price.toFixed(5)}</span>
                    </td>
                    <td>${statusBadge}</td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        console.error('Error fetching open positions:', error);
        throw error;
    }
}

// Fetch trade history for charts
async function fetchTradeHistory() {
    try {
        const response = await fetch('/api/trades/history');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const history = await response.json();
    
    if (history.length === 0) return;
    
    // Store all history for filtering
    allTradeHistory = history;
    
    // Update charts with current time range
    updateProfitChart(filterDataByTimeRange(history, currentTimeRange.profit));
    
    // Volume chart always shows 24h only
    const last24h = filterDataByTimeRange(history, '24h');
    updateVolumeChart(last24h);
    
    // Calculate total 24h volume and average per hour
    const total24hVol = last24h.reduce((sum, h) => sum + h.volume, 0);
    document.getElementById('total24hVolume').textContent = `$${total24hVol.toFixed(2)}`;
    
    const avgHourlyVol = last24h.length > 0 ? total24hVol / last24h.length : 0;
    document.getElementById('avgHourlyVolume').textContent = `$${avgHourlyVol.toFixed(2)}`;
    
    // Calculate and update stats
    updateChartStats(history);
    
    // Calculate trades per hour
    if (history.length > 1) {
        const firstTrade = new Date(history[0].timestamp);
        const lastTrade = new Date(history[history.length - 1].timestamp);
        const hoursDiff = (lastTrade - firstTrade) / (1000 * 60 * 60);
        const tradesPerHour = hoursDiff > 0 ? (history.reduce((sum, h) => sum + h.trades, 0) / hoursDiff) : 0;
        document.getElementById('tradesPerHour').textContent = tradesPerHour.toFixed(1);
    }
    } catch (error) {
        console.error('Error fetching trade history:', error);
        throw error;
    }
}

function updateChartStats(history) {
    if (history.length === 0) return;
    
    // Peak profit
    const maxProfit = Math.max(...history.map(h => h.cumulative_profit));
    document.getElementById('peakProfit').textContent = `$${maxProfit.toFixed(4)}`;
    
    // Average hourly profit
    if (history.length > 1) {
        const firstTime = new Date(history[0].timestamp);
        const lastTime = new Date(history[history.length - 1].timestamp);
        const hours = (lastTime - firstTime) / (1000 * 60 * 60);
        const totalProfit = history[history.length - 1].cumulative_profit;
        const avgHourly = hours > 0 ? totalProfit / hours : 0;
        document.getElementById('avgHourlyProfit').textContent = `$${avgHourly.toFixed(4)}`;
    }
}

// Fetch position history
async function fetchPositionHistory() {
    try {
        const response = await fetch('/api/position/history');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const history = await response.json();
    
    if (history.length === 0) return;
    
    // Store all history for filtering
    allPositionHistory = history;
    
    updatePositionChart(filterDataByTimeRange(history, currentTimeRange.position));
    
    // Calculate inventory turnover
    const totalPosition = history.reduce((sum, h) => sum + Math.abs(h.position), 0);
    const avgPosition = totalPosition / history.length;
    const inventoryTurnover = avgPosition > 0 ? totalPosition / avgPosition : 0;
    document.getElementById('inventoryTurnover').textContent = `${inventoryTurnover.toFixed(1)}x`;
    
    // Max position
    const maxPos = Math.max(...history.map(h => Math.abs(h.position)));
    document.getElementById('maxPosition').textContent = `${maxPos.toFixed(2)} USDHL`;
    } catch (error) {
        console.error('Error fetching position history:', error);
        throw error;
    }
}

function filterDataByTimeRange(data, range) {
    if (!data || data.length === 0 || range === 'all') return data;
    
    const now = Date.now();
    let cutoffTime;
    
    switch(range) {
        case '1h':
            cutoffTime = now - (60 * 60 * 1000);
            break;
        case '24h':
            cutoffTime = now - (24 * 60 * 60 * 1000);
            break;
        case '7d':
            cutoffTime = now - (7 * 24 * 60 * 60 * 1000);
            break;
        default:
            return data;
    }
    
    return data.filter(d => d.timestamp >= cutoffTime);
}

// Initialize charts
function initCharts() {
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                enabled: true,
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                titleColor: '#f8fafc',
                bodyColor: '#94a3b8',
                borderColor: 'rgba(99, 102, 241, 0.3)',
                borderWidth: 1,
                padding: 12,
                displayColors: false,
                titleFont: {
                    size: 13,
                    weight: '600'
                },
                bodyFont: {
                    size: 12
                }
            }
        },
        scales: {
            x: {
                type: 'time',
                time: {
                    tooltipFormat: 'MMM dd, HH:mm'
                },
                grid: {
                    color: 'rgba(148, 163, 184, 0.08)',
                    drawBorder: false
                },
                ticks: {
                    color: '#64748b',
                    font: {
                        size: 11,
                        weight: '500'
                    }
                }
            },
            y: {
                grid: {
                    color: 'rgba(148, 163, 184, 0.08)',
                    drawBorder: false
                },
                ticks: {
                    color: '#64748b',
                    font: {
                        size: 11,
                        weight: '500'
                    }
                }
            }
        }
    };
    
    // Profit chart
    const profitCtx = document.getElementById('profitChart').getContext('2d');
    const profitGradient = profitCtx.createLinearGradient(0, 0, 0, 400);
    profitGradient.addColorStop(0, 'rgba(16, 185, 129, 0.3)');
    profitGradient.addColorStop(1, 'rgba(16, 185, 129, 0.01)');
    
    profitChart = new Chart(profitCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Net Profit (After Fees)',
                data: [],
                borderColor: '#10b981',
                backgroundColor: profitGradient,
                fill: true,
                tension: 0.4,
                borderWidth: 3,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#10b981',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            ...chartOptions,
            plugins: {
                ...chartOptions.plugins,
                tooltip: {
                    ...chartOptions.plugins.tooltip,
                    callbacks: {
                        label: (context) => `Net Profit: $${context.parsed.y.toFixed(4)}`
                    }
                }
            }
        }
    });
    
    // Volume chart (Cumulative)
    const volumeCtx = document.getElementById('volumeChart').getContext('2d');
    const volumeGradient = volumeCtx.createLinearGradient(0, 0, 0, 280);
    volumeGradient.addColorStop(0, 'rgba(6, 182, 212, 0.3)');  // Bright cyan
    volumeGradient.addColorStop(1, 'rgba(6, 182, 212, 0.01)');
    
    volumeChart = new Chart(volumeCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Cumulative Volume',
                data: [],
                backgroundColor: volumeGradient,
                borderColor: '#06b6d4',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#06b6d4',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            ...chartOptions,
            plugins: {
                ...chartOptions.plugins,
                tooltip: {
                    ...chartOptions.plugins.tooltip,
                    callbacks: {
                        label: (context) => `Cumulative Volume: $${context.parsed.y.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
                    }
                }
            }
        }
    });
    
    // Position chart
    const positionCtx = document.getElementById('positionChart').getContext('2d');
    const positionGradient = positionCtx.createLinearGradient(0, 0, 0, 300);
    positionGradient.addColorStop(0, 'rgba(245, 158, 11, 0.3)');
    positionGradient.addColorStop(1, 'rgba(245, 158, 11, 0.01)');
    
    positionChart = new Chart(positionCtx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Position',
                data: [],
                borderColor: '#f59e0b',
                backgroundColor: positionGradient,
                fill: true,
                tension: 0.4,
                borderWidth: 3,
                pointRadius: 0,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#f59e0b',
                pointHoverBorderColor: '#fff',
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            ...chartOptions,
            plugins: {
                ...chartOptions.plugins,
                tooltip: {
                    ...chartOptions.plugins.tooltip,
                    callbacks: {
                        label: (context) => `Position: ${context.parsed.y.toFixed(2)} USDHL`
                    }
                }
            }
        }
    });
}

// Update profit chart
function updateProfitChart(history) {
    const data = history.map(h => ({
        x: h.timestamp,
        y: h.cumulative_profit
    }));
    
    profitChart.data.datasets[0].data = data;
    profitChart.update('none');
}

// Update volume chart (cumulative)
function updateVolumeChart(history) {
    let cumulativeVolume = 0;
    const data = history.map(h => {
        cumulativeVolume += h.volume;
        return {
            x: h.timestamp,
            y: cumulativeVolume
        };
    });
    
    volumeChart.data.datasets[0].data = data;
    volumeChart.update('none');
}

// Update position chart
function updatePositionChart(history) {
    const data = history.map(h => ({
        x: h.timestamp,
        y: h.position
    }));
    
    positionChart.data.datasets[0].data = data;
    positionChart.update('none');
}

// Chart range controls
document.querySelectorAll('.btn-small').forEach(btn => {
    btn.addEventListener('click', (e) => {
        const range = e.target.dataset.range;
        const chartType = e.target.dataset.chart;
        
        // Update active state for this chart's buttons
        const chartButtons = document.querySelectorAll(`.btn-small[data-chart="${chartType}"]`);
        chartButtons.forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        
        // Update time range and refresh chart
        currentTimeRange[chartType] = range;
        
        switch(chartType) {
            case 'profit':
                if (allTradeHistory.length > 0) {
                    updateProfitChart(filterDataByTimeRange(allTradeHistory, range));
                }
                break;
            case 'position':
                if (allPositionHistory.length > 0) {
                    updatePositionChart(filterDataByTimeRange(allPositionHistory, range));
                }
                break;
        }
    });
});
