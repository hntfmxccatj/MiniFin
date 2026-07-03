export async function fetchSummary() {
    const res = await fetch('/api/bills/summary');
    return res.json();
}

export async function fetchCounterparties(limit = 10) {
    const res = await fetch(`/api/bills/counterparties?limit=${limit}`);
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
