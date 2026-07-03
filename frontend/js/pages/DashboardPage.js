import { fetchSummary } from '../api.js';
import { SummaryCards, updateSummaryCards } from '../components/SummaryCards.js';
import { Charts, renderCharts } from '../components/Charts.js';
import { showToast } from '../utils.js';

export function DashboardPage() {
    return `
        ${SummaryCards()}
        ${Charts()}
    `;
}

export async function mountDashboard() {
    try {
        const s = await fetchSummary();
        updateSummaryCards(s);
        await renderCharts(s);
    } catch (e) {
        console.error(e);
        showToast('加载摘要失败', 'error');
    }
}
