import { state, updateFilters } from '../state.js';

const RANGE_OPTIONS = {
    this_month: '本月',
    last_month: '上月',
    last_3_months: '近3个月',
    last_6_months: '近6个月',
    this_year: '本年',
    last_year: '去年',
    all: '全部',
};

function formatDate(d) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function getMonthRange(year, month) {
    const start = new Date(year, month, 1);
    const end = new Date(year, month + 1, 0);
    return [formatDate(start), formatDate(end)];
}

function computeDateRange(range) {
    const today = new Date();
    const year = today.getFullYear();
    const month = today.getMonth();

    switch (range) {
        case 'this_month':
            return getMonthRange(year, month);
        case 'last_month':
            return getMonthRange(year, month - 1);
        case 'last_3_months':
            return [getMonthRange(year, month - 2)[0], getMonthRange(year, month)[1]];
        case 'last_6_months':
            return [getMonthRange(year, month - 5)[0], getMonthRange(year, month)[1]];
        case 'this_year':
            return [`${year}-01-01`, `${year}-12-31`];
        case 'last_year':
            return [`${year - 1}-01-01`, `${year - 1}-12-31`];
        case 'all':
        default:
            return ['', ''];
    }
}

export function FilterBar() {
    const { range, source, keyword } = state.filters;
    return `
        <div class="filter-bar card" id="filterBar">
            <div class="filter-group">
                <label>时间范围</label>
                <select id="filterRange">
                    ${Object.entries(RANGE_OPTIONS).map(([key, label]) =>
                        `<option value="${key}" ${range === key ? 'selected' : ''}>${label}</option>`
                    ).join('')}
                </select>
            </div>
            <div class="filter-group">
                <label>来源</label>
                <select id="filterSource">
                    <option value="" ${source === '' ? 'selected' : ''}>全部</option>
                    <option value="WECHAT" ${source === 'WECHAT' ? 'selected' : ''}>微信</option>
                    <option value="ALIPAY" ${source === 'ALIPAY' ? 'selected' : ''}>支付宝</option>
                </select>
            </div>
            <div class="filter-group filter-keyword">
                <label>关键词</label>
                <input type="text" id="filterKeyword" placeholder="交易对方 / 商品" value="${keyword}">
            </div>
            <div class="filter-actions">
                <button class="btn" id="filterApply">应用</button>
                <button class="btn btn-outline" id="filterReset">重置</button>
            </div>
        </div>
    `;
}

export function initFilterBar(onChange) {
    const applyBtn = document.getElementById('filterApply');
    const resetBtn = document.getElementById('filterReset');

    applyBtn.addEventListener('click', () => {
        const range = document.getElementById('filterRange').value;
        const source = document.getElementById('filterSource').value;
        const keyword = document.getElementById('filterKeyword').value.trim();
        const [start_date, end_date] = computeDateRange(range);

        updateFilters({ range, source, keyword, start_date, end_date });
        if (onChange) onChange();
    });

    resetBtn.addEventListener('click', () => {
        document.getElementById('filterRange').value = 'all';
        document.getElementById('filterSource').value = '';
        document.getElementById('filterKeyword').value = '';

        updateFilters({ range: 'all', source: '', keyword: '', start_date: '', end_date: '' });
        if (onChange) onChange();
    });
}
