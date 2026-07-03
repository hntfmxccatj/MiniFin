import { fetchCounterparties } from '../api.js';

const LIGHT = {
    foreColor: '#64748b',
    gridBorder: '#e2e8f0',
    labelColor: '#64748b',
    titleColor: '#1e293b',
    tooltip: 'light',
};

export function Charts() {
    return `
        <div class="charts-row">
            <div class="card" id="monthlyChart"></div>
            <div class="card" id="typeChart"></div>
        </div>
        <div class="charts-row">
            <div class="card" id="counterpartyChart"></div>
            <div class="card" id="sourceChart"></div>
        </div>
    `;
}

export async function renderCharts(s) {
    const months = s.monthly.map(m => m.month).reverse();
    const monthExpense = s.monthly.map(m => Math.abs(m.expense)).reverse();
    const monthIncome = s.monthly.map(m => m.income).reverse();

    new ApexCharts(document.querySelector('#monthlyChart'), {
        title: { text: '月度收支趋势', style: { color: LIGHT.titleColor, fontSize: '14px', fontWeight: 600 } },
        chart: { type: 'bar', height: 320, foreColor: LIGHT.foreColor, background: 'transparent', toolbar: { show: false } },
        grid: { borderColor: LIGHT.gridBorder },
        plotOptions: { bar: { borderRadius: 4, columnWidth: '55%' } },
        series: [{ name: '支出', data: monthExpense, color: '#e11d48' }, { name: '收入', data: monthIncome, color: '#16a34a' }],
        xaxis: { categories: months, labels: { style: { colors: LIGHT.labelColor } }, axisBorder: { color: LIGHT.gridBorder } },
        yaxis: { labels: { style: { colors: LIGHT.labelColor }, formatter: v => '¥' + v } },
        tooltip: { theme: LIGHT.tooltip, y: { formatter: v => '¥' + v.toFixed(2) } },
        dataLabels: { enabled: false },
    }).render();

    const typeSeries = s.by_type.map(t => Math.abs(t.total_amount));
    const typeLabels = s.by_type.map(t => ({ EXPENSE: '支出', INCOME: '收入', REFUND: '退款' }[t.type] || t.type));
    new ApexCharts(document.querySelector('#typeChart'), {
        title: { text: '收支类型分布', style: { color: LIGHT.titleColor, fontSize: '14px', fontWeight: 600 } },
        chart: { type: 'donut', height: 320, background: 'transparent' },
        labels: typeLabels, series: typeSeries, colors: ['#e11d48', '#16a34a', '#d97706'],
        legend: { labels: { colors: LIGHT.labelColor } },
        tooltip: { theme: LIGHT.tooltip, y: { formatter: v => '¥' + v.toFixed(2) } },
        dataLabels: { style: { colors: [LIGHT.labelColor] } }, stroke: { width: 2 },
        plotOptions: { pie: { donut: { labels: { show: true, total: { show: true, color: LIGHT.labelColor, label: '总计' } } } } },
    }).render();

    const cps = await fetchCounterparties(10);
    if (cps.length) {
        new ApexCharts(document.querySelector('#counterpartyChart'), {
            title: { text: '支出排名 Top 10', style: { color: LIGHT.titleColor, fontSize: '14px', fontWeight: 600 } },
            chart: { type: 'bar', height: 320, foreColor: LIGHT.foreColor, background: 'transparent', toolbar: { show: false } },
            grid: { borderColor: LIGHT.gridBorder },
            plotOptions: { bar: { borderRadius: 4, horizontal: true, barHeight: '70%' } },
            series: [{ name: '支出金额', data: cps.map(c => Math.abs(c.total_amount)).reverse(), color: '#0284c7' }],
            xaxis: { categories: cps.map(c => c.counterparty).reverse(), labels: { style: { colors: LIGHT.labelColor, fontSize: '11px' } }, axisBorder: { color: LIGHT.gridBorder } },
            yaxis: { labels: { style: { colors: LIGHT.labelColor } } },
            tooltip: { theme: LIGHT.tooltip, x: { formatter: v => v }, y: { formatter: v => '¥' + v.toFixed(2) } },
            dataLabels: { enabled: false },
        }).render();
    }

    const srcLabels = s.by_source.map(x => x.source === 'WECHAT' ? '微信' : '支付宝');
    const srcSeries = s.by_source.map(x => x.count);
    new ApexCharts(document.querySelector('#sourceChart'), {
        title: { text: '账单来源占比', style: { color: LIGHT.titleColor, fontSize: '14px', fontWeight: 600 } },
        chart: { type: 'pie', height: 320, background: 'transparent' },
        labels: srcLabels, series: srcSeries, colors: ['#059669', '#2563eb'],
        legend: { labels: { colors: LIGHT.labelColor } },
        tooltip: { theme: LIGHT.tooltip },
        dataLabels: { style: { colors: [LIGHT.labelColor] } },
    }).render();
}
