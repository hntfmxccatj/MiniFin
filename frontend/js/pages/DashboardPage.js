import {
    fetchExpenseByCategory,
    fetchLargeOrders,
    fetchSummary,
} from '../api.js';
import { CashFlowCalendar, initCashFlowCalendar, renderCashFlowCalendar } from '../components/CashFlowCalendar.js';
import { Charts, renderCharts } from '../components/Charts.js';
import { FilterBar, initFilterBar } from '../components/FilterBar.js';
import { LargeOrders, initLargeOrders, renderLargeOrders } from '../components/LargeOrders.js';
import { SummaryCards, updateSummaryCards } from '../components/SummaryCards.js';
import { state } from '../state.js';
import { showToast } from '../utils.js';

export function DashboardPage() {
    return `
        ${FilterBar()}
        ${SummaryCards()}
        ${Charts()}
        ${CashFlowCalendar()}
        ${LargeOrders()}
    `;
}

export async function mountDashboard() {
    initFilterBar(() => applyFilters());
    initLargeOrders();
    initCashFlowCalendar();
    await loadDashboardData();
}

async function applyFilters() {
    const applyBtn = document.getElementById('filterApply');
    const resetBtn = document.getElementById('filterReset');
    if (applyBtn) {
        applyBtn.disabled = true;
        applyBtn.textContent = '加载中...';
    }
    if (resetBtn) resetBtn.disabled = true;

    try {
        await loadDashboardData();
    } finally {
        if (applyBtn) {
            applyBtn.disabled = false;
            applyBtn.textContent = '应用';
        }
        if (resetBtn) resetBtn.disabled = false;
    }
}

async function loadDashboardData() {
    try {
        const filters = { ...state.filters };
        const limit = getLargeOrderLimit();

        const [summary, categoryData] = await Promise.all([
            fetchSummary(filters),
            fetchExpenseByCategory(filters),
        ]);

        updateSummaryCards(summary);
        await renderCharts(categoryData);

        // 日历优先展示筛选范围内最新有支出的月份
        const calYearMonth = getCalendarMonth(summary.monthly, filters.end_date);
        await renderCashFlowCalendar(calYearMonth.year, calYearMonth.month);

        // 大额订单
        await renderLargeOrders(limit);
    } catch (e) {
        console.error(e);
        showToast('加载看板数据失败', 'error');
    }
}

function getCalendarMonth(monthlyData, endDate) {
    // 1. 如果筛选结束日期明确，优先使用
    if (endDate) {
        const d = new Date(endDate);
        if (!isNaN(d)) {
            return { year: d.getFullYear(), month: d.getMonth() + 1 };
        }
    }

    // 2. 否则使用最近有支出的月份
    const months = monthlyData || [];
    for (const m of months) {
        const expense = Math.abs(m.expense || 0);
        if (expense > 0) {
            const [year, month] = m.month.split('-').map(Number);
            return { year, month };
        }
    }

    // 3. 兜底：当前月
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

function getLargeOrderLimit() {
    const select = document.getElementById('largeOrderLimit');
    return select ? Number(select.value) : 5;
}
