function buildQuery(filters) {
    if (!filters) return '';
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
        if (value !== '' && value !== null && value !== undefined) {
            params.append(key, value);
        }
    });
    const qs = params.toString();
    return qs ? '?' + qs : '';
}

export async function fetchSummary(filters = {}) {
    const res = await fetch('/api/bills/summary' + buildQuery(filters));
    return res.json();
}

export async function fetchCounterparties(limit = 10, filters = {}) {
    const params = { ...filters, limit };
    const res = await fetch('/api/bills/counterparties' + buildQuery(params));
    return res.json();
}

export async function fetchCategories() {
    const res = await fetch('/api/categories/tree');
    return res.json();
}

export async function fetchExpenseByCategory(filters = {}) {
    const res = await fetch('/api/bills/expense_by_category' + buildQuery(filters));
    return res.json();
}

export async function fetchLargeOrders(limit = 5, filters = {}) {
    const params = { ...filters, limit };
    const res = await fetch('/api/bills/large_orders' + buildQuery(params));
    return res.json();
}

export async function fetchDailyExpenses(year, month, filters = {}) {
    const params = { ...filters, year, month };
    const res = await fetch('/api/bills/daily_expenses' + buildQuery(params));
    return res.json();
}

export async function fetchBillsByDay(year, month, day, filters = {}) {
    const params = { ...filters, year, month, day };
    const res = await fetch('/api/bills/by_day' + buildQuery(params));
    return res.json();
}

export async function uploadFiles(files) {
    const form = new FormData();
    files.forEach(f => form.append('files', f));
    const res = await fetch('/api/upload', { method: 'POST', body: form });
    return res.json();
}

export async function saveBills(records) {
    const res = await fetch('/api/bills/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ records }),
    });
    return res.json();
}
