export function formatAmount(val) {
    const n = Number(val);
    if (n < 0) return `<span class="amount-expense">-¥${Math.abs(n).toFixed(2)}</span>`;
    return `<span class="amount-income">+¥${n.toFixed(2)}</span>`;
}

export function typeBadge(t) {
    const map = { EXPENSE: '支出', INCOME: '收入', REFUND: '退款' };
    return `<span class="badge ${t.toLowerCase()}">${map[t] || t}</span>`;
}

export function sourceBadge(s) {
    const map = { WECHAT: '微信', ALIPAY: '支付宝' };
    return `<span class="badge ${s.toLowerCase()}">${map[s] || s}</span>`;
}

export function showToast(msg, type = 'success') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast ' + type + ' show';
    setTimeout(() => el.className = 'toast', 3000);
}
