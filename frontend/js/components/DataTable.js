import { formatAmount, typeBadge, sourceBadge } from '../utils.js';

export function DataTable(records, { title = '本次上传数据', emptyText = '暂无数据' } = {}) {
    const rows = records.map(r => `
        <tr>
            <td>${r.trade_time || '-'}</td>
            <td>${sourceBadge(r.source)}</td>
            <td>${typeBadge(r.type)}</td>
            <td>${formatAmount(r.amount)}</td>
            <td>${r.counterparty || '-'}</td>
            <td>${r.product || '-'}</td>
            <td>${r.payment_method || '-'}</td>
            <td>${r.major_category || '-'}</td>
            <td>${r.sub_category || '-'}</td>
        </tr>
    `).join('');

    return `
        <div class="table-wrapper">
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
