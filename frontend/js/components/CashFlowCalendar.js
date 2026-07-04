import { fetchBillsByDay, fetchDailyExpenses } from '../api.js';
import { state } from '../state.js';

let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth() + 1;
let selectedDay = null;

export function CashFlowCalendar() {
    return `
        <div class="card calendar-card" id="cashFlowCalendar">
            <div class="section-header">
                <h3 class="section-title">现金流日历</h3>
                <div class="calendar-nav">
                    <button class="btn-icon" id="calPrev" title="上月">&lt;</button>
                    <span class="calendar-label" id="calMonthLabel">--</span>
                    <button class="btn-icon" id="calNext" title="下月">&gt;</button>
                </div>
            </div>
            <div class="calendar-legend">
                <span>低</span>
                <div class="legend-box level-1"></div>
                <div class="legend-box level-2"></div>
                <div class="legend-box level-3"></div>
                <div class="legend-box level-4"></div>
                <div class="legend-box level-5"></div>
                <span>高</span>
            </div>
            <div class="calendar-grid" id="calGrid">
                <div class="loading"></div>
            </div>
            <div class="day-detail" id="dayDetail">
                <div class="day-detail-empty">点击某一天查看详细支出</div>
            </div>
        </div>
    `;
}

export async function renderCashFlowCalendar(year = currentYear, month = currentMonth) {
    currentYear = year;
    currentMonth = month;
    selectedDay = null;

    const label = document.getElementById('calMonthLabel');
    if (label) label.textContent = `${year}年${month}月`;

    const grid = document.getElementById('calGrid');
    if (!grid) return;
    grid.innerHTML = '<div class="loading"></div>';

    clearDayDetail();

    try {
        const filters = { source: state.filters.source, keyword: state.filters.keyword };
        const data = await fetchDailyExpenses(year, month, filters);
        const days = data.days || [];
        renderGrid(grid, year, month, days);
    } catch (e) {
        console.error(e);
        grid.innerHTML = '<div class="empty">加载失败</div>';
    }
}

export function initCashFlowCalendar() {
    document.getElementById('calPrev').addEventListener('click', () => {
        const d = new Date(currentYear, currentMonth - 2, 1);
        renderCashFlowCalendar(d.getFullYear(), d.getMonth() + 1);
    });
    document.getElementById('calNext').addEventListener('click', () => {
        const d = new Date(currentYear, currentMonth, 1);
        renderCashFlowCalendar(d.getFullYear(), d.getMonth() + 1);
    });
}

function renderGrid(grid, year, month, days) {
    const dayMap = new Map(days.map(d => [d.day, d]));
    const firstDay = new Date(year, month - 1, 1);
    const daysInMonth = new Date(year, month, 0).getDate();
    const startWeekday = firstDay.getDay(); // 0 = Sunday

    const maxAmount = Math.max(...days.map(d => d.amount), 0.01);

    const weekdays = ['日', '一', '二', '三', '四', '五', '六'];

    let html = weekdays.map(w => `<div class="cal-weekday">${w}</div>`).join('');

    // Empty cells before the 1st
    for (let i = 0; i < startWeekday; i++) {
        html += '<div class="cal-day cal-day-empty"></div>';
    }

    for (let day = 1; day <= daysInMonth; day++) {
        const info = dayMap.get(day);
        const amount = info ? info.amount : 0;
        const count = info ? info.count : 0;
        const level = info ? getHeatLevel(amount, maxAmount) : 0;
        const hasData = amount > 0;

        html += `
            <div class="cal-day level-${level} ${hasData ? 'cal-day-clickable' : ''}"
                 data-day="${day}"
                 title="${month}月${day}日：${count}笔，¥${amount.toFixed(2)}">
                <div class="cal-day-number">${day}</div>
                ${hasData ? `<div class="cal-day-amount">¥${Math.round(amount)}</div>` : ''}
            </div>
        `;
    }

    grid.innerHTML = html;

    // Bind click events to days with data
    grid.querySelectorAll('.cal-day-clickable').forEach(el => {
        el.addEventListener('click', () => {
            const day = Number(el.dataset.day);
            selectDay(day);
        });
    });
}

async function selectDay(day) {
    selectedDay = day;

    // Highlight selected day
    document.querySelectorAll('.cal-day').forEach(el => el.classList.remove('cal-day-selected'));
    const selectedEl = document.querySelector(`.cal-day[data-day="${day}"]`);
    if (selectedEl) selectedEl.classList.add('cal-day-selected');

    const detail = document.getElementById('dayDetail');
    detail.innerHTML = '<div class="day-detail-loading">加载中...</div>';

    try {
        const filters = { source: state.filters.source, keyword: state.filters.keyword };
        const bills = await fetchBillsByDay(currentYear, currentMonth, day, filters);
        renderDayDetail(currentYear, currentMonth, day, bills);
    } catch (e) {
        console.error(e);
        detail.innerHTML = '<div class="day-detail-empty">加载失败</div>';
    }
}

function renderDayDetail(year, month, day, bills) {
    const detail = document.getElementById('dayDetail');
    const total = bills.reduce((sum, b) => sum + Math.abs(b.amount), 0);

    if (!bills.length) {
        detail.innerHTML = `<div class="day-detail-empty">${month}月${day}日暂无支出明细</div>`;
        return;
    }

    detail.innerHTML = `
        <div class="day-detail-header">
            <span class="day-detail-title">${month}月${day}日 支出明细</span>
            <span class="day-detail-total">共 ${bills.length} 笔，合计 ¥${total.toFixed(2)}</span>
        </div>
        <table class="simple-table day-detail-table">
            <thead>
                <tr>
                    <th>时间</th>
                    <th>交易对方</th>
                    <th>商品</th>
                    <th>分类</th>
                    <th class="amount-cell">金额</th>
                </tr>
            </thead>
            <tbody>
                ${bills.map(b => `
                    <tr>
                        <td>${formatTime(b.trade_time)}</td>
                        <td>${escapeHtml(b.counterparty || '未命名')}</td>
                        <td>${escapeHtml(b.product || '')}</td>
                        <td>
                            <span class="category-tag">
                                ${escapeHtml(b.major_category || '未分类')}
                            </span>
                        </td>
                        <td class="amount-cell amount-expense">-¥${Math.abs(b.amount).toFixed(2)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function clearDayDetail() {
    const detail = document.getElementById('dayDetail');
    if (detail) {
        detail.innerHTML = '<div class="day-detail-empty">点击某一天查看详细支出</div>';
    }
}

function getHeatLevel(amount, maxAmount) {
    if (amount <= 0 || maxAmount <= 0) return 0;
    const ratio = amount / maxAmount;
    if (ratio < 0.2) return 1;
    if (ratio < 0.4) return 2;
    if (ratio < 0.6) return 3;
    if (ratio < 0.8) return 4;
    return 5;
}

function formatTime(tradeTime) {
    if (!tradeTime) return '--';
    const d = new Date(tradeTime);
    if (isNaN(d)) return tradeTime.slice(11, 16) || '--';
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
