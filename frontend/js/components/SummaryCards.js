export function SummaryCards() {
    return `
        <div class="summary-cards" id="summaryCards">
            <div class="card"><div class="label">总记录数</div><div class="value count" id="totalCount">--</div></div>
            <div class="card"><div class="label">总支出</div><div class="value expense" id="totalExpense">--</div></div>
            <div class="card"><div class="label">总收入</div><div class="value income" id="totalIncome">--</div></div>
            <div class="card"><div class="label">净收支</div><div class="value" id="netAmount" style="color: var(--accent);">--</div></div>
        </div>
    `;
}

export function updateSummaryCards(s) {
    document.getElementById('totalCount').textContent = s.total_count;
    document.getElementById('totalExpense').textContent = `-¥${Math.abs(s.total_expense).toFixed(2)}`;
    document.getElementById('totalIncome').textContent = `+¥${s.total_income.toFixed(2)}`;
    const net = s.total_income + s.total_expense;
    const netEl = document.getElementById('netAmount');
    netEl.textContent = net >= 0 ? `+¥${net.toFixed(2)}` : `-¥${Math.abs(net).toFixed(2)}`;
    netEl.style.color = net >= 0 ? 'var(--income)' : 'var(--expense)';
}
