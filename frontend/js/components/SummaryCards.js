export function SummaryCards() {
    return `
        <div class="kpi-bar" id="kpiBar">
            <div class="kpi-item">
                <div class="kpi-label">本月总支出</div>
                <div class="kpi-value expense" id="kpiMonthExpense">--</div>
            </div>
            <div class="kpi-item">
                <div class="kpi-label">日均支出</div>
                <div class="kpi-value expense" id="kpiDailyExpense">--</div>
            </div>
            <div class="kpi-item">
                <div class="kpi-label">预计月末支出</div>
                <div class="kpi-value expense" id="kpiProjectedExpense">--</div>
            </div>
            <div class="kpi-item">
                <div class="kpi-label">近3月月均支出</div>
                <div class="kpi-value expense" id="kpiAvg3Month">--</div>
            </div>
        </div>
    `;
}

export function updateSummaryCards(s) {
    const fmt = n => `¥${Math.abs(Number(n)).toFixed(2)}`;
    const monthExpense = Math.abs(s.total_expense || 0);

    document.getElementById('kpiMonthExpense').textContent = fmt(monthExpense);
    document.getElementById('kpiDailyExpense').textContent = fmt(s.avg_daily_expense || 0);
    document.getElementById('kpiProjectedExpense').textContent = fmt(s.projected_month_expense || 0);

    // 近3月月均支出（基于 monthly 中最近3个月支出的绝对值）
    const monthlyExpenses = (s.monthly || [])
        .slice(0, 3)
        .map(m => Math.abs(m.expense || 0));
    const avg3Month = monthlyExpenses.length
        ? monthlyExpenses.reduce((a, b) => a + b, 0) / monthlyExpenses.length
        : 0;
    document.getElementById('kpiAvg3Month').textContent = fmt(avg3Month);
}
