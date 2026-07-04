const LIGHT = {
    foreColor: '#64748b',
    gridBorder: '#e2e8f0',
    labelColor: '#64748b',
    titleColor: '#1e293b',
    tooltip: 'light',
};

const UNCATEGORIZED_COLOR = '#94a3b8';
const chartInstances = [];

function categoryColor(name) {
    return name === '未分类' ? UNCATEGORIZED_COLOR : undefined;
}

export function Charts() {
    return `
        <div class="charts-row full-width">
            <div class="card chart-card" id="trendChart"></div>
        </div>
        <div class="charts-row full-width">
            <div class="card chart-card" id="categoryChart"></div>
        </div>
    `;
}

export async function renderCharts(categoryData) {
    // 先销毁旧图表，防止内存泄漏和渲染叠加
    chartInstances.forEach(chart => {
        try { chart.destroy(); } catch (e) {}
    });
    chartInstances.length = 0;

    await renderTrendChart(categoryData);
    await renderCategoryChart(categoryData);
}

async function renderTrendChart(catData) {
    const el = document.querySelector('#trendChart');
    if (!el) return;

    const { months, series } = catData;
    if (!months || !months.length) {
        el.innerHTML = '<div class="empty">暂无支出数据</div>';
        return;
    }

    const chartSeries = series.map(s => ({
        ...s,
        color: categoryColor(s.name),
    }));

    const chart = new ApexCharts(el, {
        title: {
            text: '支出趋势（按分类堆叠）',
            style: { color: LIGHT.titleColor, fontSize: '14px', fontWeight: 600 },
        },
        chart: {
            type: 'area',
            height: 360,
            stacked: true,
            foreColor: LIGHT.foreColor,
            background: 'transparent',
            toolbar: { show: false },
            fontFamily: 'inherit',
        },
        grid: { borderColor: LIGHT.gridBorder, strokeDashArray: 4 },
        stroke: { curve: 'smooth', width: 2 },
        fill: { type: 'solid', opacity: 0.7 },
        series: chartSeries,
        xaxis: {
            categories: months,
            labels: { style: { colors: LIGHT.labelColor } },
            axisBorder: { color: LIGHT.gridBorder },
            axisTicks: { color: LIGHT.gridBorder },
        },
        yaxis: {
            labels: {
                style: { colors: LIGHT.labelColor },
                formatter: v => '¥' + Number(v).toFixed(0),
            },
        },
        tooltip: {
            theme: LIGHT.tooltip,
            y: { formatter: v => '¥' + Number(v).toFixed(2) },
        },
        legend: {
            position: 'top',
            horizontalAlign: 'left',
            labels: { colors: LIGHT.labelColor },
        },
        dataLabels: { enabled: false },
    });
    chart.render();
    chartInstances.push(chart);
}

async function renderCategoryChart(catData) {
    const el = document.querySelector('#categoryChart');
    if (!el) return;

    const totals = catData.totals_by_major || [];
    if (!totals.length) {
        el.innerHTML = '<div class="empty">暂无分类数据</div>';
        return;
    }

    const data = totals.map(t => ({
        x: t.major_category || '未分类',
        y: Math.abs(t.total_amount),
        fillColor: categoryColor(t.major_category),
    })).reverse();

    const total = data.reduce((sum, d) => sum + d.y, 0);

    const chart = new ApexCharts(el, {
        title: {
            text: `支出分类排名（总支出 ¥${total.toFixed(0)}）`,
            style: { color: LIGHT.titleColor, fontSize: '14px', fontWeight: 600 },
        },
        chart: {
            type: 'bar',
            height: Math.max(260, 60 + data.length * 32),
            foreColor: LIGHT.foreColor,
            background: 'transparent',
            toolbar: { show: false },
            fontFamily: 'inherit',
        },
        grid: { borderColor: LIGHT.gridBorder },
        plotOptions: {
            bar: { borderRadius: 4, horizontal: true, barHeight: '65%' },
        },
        series: [{ name: '支出金额', data: data }],
        colors: ['#0284c7'],
        xaxis: {
            labels: {
                style: { colors: LIGHT.labelColor },
                formatter: v => '¥' + Number(v).toFixed(0),
            },
            axisBorder: { color: LIGHT.gridBorder },
        },
        yaxis: {
            labels: { style: { colors: LIGHT.labelColor, fontSize: '12px' } },
        },
        tooltip: {
            theme: LIGHT.tooltip,
            x: { formatter: v => v },
            y: { formatter: v => '¥' + Number(v).toFixed(2) },
        },
        dataLabels: {
            enabled: true,
            style: { colors: [LIGHT.labelColor] },
            formatter: (val) => {
                const pct = total > 0 ? (val / total * 100).toFixed(1) : '0.0';
                return `¥${Number(val).toFixed(0)} (${pct}%)`;
            },
        },
    });
    chart.render();
    chartInstances.push(chart);
}
