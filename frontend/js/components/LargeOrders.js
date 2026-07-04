import { fetchLargeOrders } from '../api.js';
import { state } from '../state.js';

const LIMIT_OPTIONS = [5, 10, 15, 20];

export function LargeOrders() {
    return `
        <div class="card large-orders-card" id="largeOrdersCard">
            <div class="section-header">
                <h3 class="section-title">大额订单</h3>
                <div class="limit-selector">
                    <label>显示</label>
                    <select id="largeOrderLimit">
                        ${LIMIT_OPTIONS.map(n => `<option value="${n}" ${n === 5 ? 'selected' : ''}>${n}</option>`).join('')}
                    </select>
                    <span>笔</span>
                </div>
            </div>
            <div class="large-orders-list" id="largeOrdersList">
                <div class="loading"></div>
            </div>
        </div>
    `;
}

export async function renderLargeOrders(limit = 5) {
    const container = document.getElementById('largeOrdersList');
    if (!container) return;

    container.innerHTML = '<div class="loading"></div>';

    try {
        const filters = { ...state.filters };
        const orders = await fetchLargeOrders(limit, filters);

        if (!orders.length) {
            container.innerHTML = '<div class="empty">暂无大额订单</div>';
            return;
        }

        container.innerHTML = `
            <table class="simple-table">
                <thead>
                    <tr>
                        <th>日期</th>
                        <th>交易对方</th>
                        <th>分类</th>
                        <th class="amount-cell">金额</th>
                    </tr>
                </thead>
                <tbody>
                    ${orders.map(o => `
                        <tr>
                            <td>${formatDate(o.trade_time)}</td>
                            <td>${escapeHtml(o.counterparty || '未命名')}</td>
                            <td>
                                <span class="category-tag">
                                    ${escapeHtml(o.major_category || '未分类')}
                                </span>
                            </td>
                            <td class="amount-cell amount-expense">-¥${Math.abs(o.amount).toFixed(2)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (e) {
        console.error(e);
        container.innerHTML = '<div class="empty">加载失败</div>';
    }
}

export function initLargeOrders(onChange) {
    const select = document.getElementById('largeOrderLimit');
    if (select) {
        select.addEventListener('change', () => {
            renderLargeOrders(Number(select.value));
        });
    }
}

function formatDate(tradeTime) {
    if (!tradeTime) return '--';
    const d = new Date(tradeTime);
    if (isNaN(d)) return tradeTime.slice(0, 10);
    return `${d.getMonth() + 1}/${d.getDate()}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
