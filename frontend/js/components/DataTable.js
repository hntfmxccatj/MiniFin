import { formatAmount, typeBadge, sourceBadge } from '../utils.js';
import { state } from '../state.js';

export function DataTable(records, { title = '本次上传数据', emptyText = '暂无数据', editable = false } = {}) {
    const options = state.categoryOptions || {};
    const majors = Object.keys(options);

    const rows = records.map((r, idx) => {
        const currentMajor = r.major_category || '';
        const currentSubs = options[currentMajor] || [];

        const majorCell = editable
            ? `<select class="cat-select major-select" data-row="${idx}">
                <option value="" ${currentMajor ? '' : 'selected'}>- Major -</option>
                ${majors.map(m => `<option value="${m}" ${m === currentMajor ? 'selected' : ''}>${m}</option>`).join('')}
                ${currentMajor && !majors.includes(currentMajor) ? `<option value="${currentMajor}" selected>${currentMajor}</option>` : ''}
               </select>`
            : (r.major_category || '-');

        const subCell = editable
            ? `<select class="cat-select sub-select" data-row="${idx}">
                <option value="" ${r.sub_category ? '' : 'selected'}>- Sub -</option>
                ${currentSubs.map(s => `<option value="${s}" ${s === r.sub_category ? 'selected' : ''}>${s}</option>`).join('')}
                ${r.sub_category && !currentSubs.includes(r.sub_category) ? `<option value="${r.sub_category}" selected>${r.sub_category}</option>` : ''}
               </select>`
            : (r.sub_category || '-');

        return `
        <tr>
            <td>${r.trade_time || '-'}</td>
            <td>${sourceBadge(r.source)}</td>
            <td>${typeBadge(r.type)}</td>
            <td>${formatAmount(r.amount)}</td>
            <td>${r.counterparty || '-'}</td>
            <td>${r.product || '-'}</td>
            <td>${r.payment_method || '-'}</td>
            <td class="cell-major">${majorCell}</td>
            <td class="cell-sub">${subCell}</td>
        </tr>
    `}).join('');

    return `
        <div class="table-wrapper" id="${editable ? 'editableTable' : ''}">
            <div class="table-header"><span>${title}</span></div>
            <div class="table-scroll">
                <table>
                    <thead>
                        <tr>
                            <th>交易时间</th>
                            <th>来源</th>
                            <th>类型</th>
                            <th>金额</th>
                            <th>交易对方</th>
                            <th>商品</th>
                            <th>支付方式</th>
                            <th>Major</th>
                            <th>Sub</th>
                        </tr>
                    </thead>
                    <tbody>${rows || `<tr><td colspan="9" class="empty">${emptyText}</td></tr>`}</tbody>
                </table>
            </div>
        </div>
    `;
}

