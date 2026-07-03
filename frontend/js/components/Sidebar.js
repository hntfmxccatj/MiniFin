import { state } from '../state.js';

const menuIcon = `
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="3" y1="12" x2="21" y2="12"></line>
  <line x1="3" y1="6" x2="21" y2="6"></line>
  <line x1="3" y1="18" x2="21" y2="18"></line>
</svg>`;

const dashboardIcon = `
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="3" y="3" width="7" height="7"></rect>
  <rect x="14" y="3" width="7" height="7"></rect>
  <rect x="14" y="14" width="7" height="7"></rect>
  <rect x="3" y="14" width="7" height="7"></rect>
</svg>`;

const uploadIcon = `
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
  <polyline points="17 8 12 3 7 8"></polyline>
  <line x1="12" y1="3" x2="12" y2="15"></line>
</svg>`;

const logoIcon = `
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"></circle>
  <path d="M12 6v6l4 2"></path>
</svg>`;

export function Sidebar() {
    return `
        <aside class="sidebar ${state.sidebarCollapsed ? 'collapsed' : ''}" id="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-logo">
                    ${logoIcon}
                    <span>MiniFin</span>
                </div>
                <button class="sidebar-toggle" id="sidebarToggle" title="收起/展开">
                    ${menuIcon}
                </button>
            </div>
            <nav class="sidebar-nav">
                <a class="nav-item" href="#dashboard" data-route="dashboard">
                    ${dashboardIcon}
                    <span>概览看板</span>
                </a>
                <a class="nav-item" href="#upload" data-route="upload">
                    ${uploadIcon}
                    <span>上传账单</span>
                </a>
            </nav>
        </aside>
    `;
}

export function initSidebar() {
    document.getElementById('sidebarToggle').addEventListener('click', () => {
        state.sidebarCollapsed = !state.sidebarCollapsed;
        document.getElementById('sidebar').classList.toggle('collapsed');
    });
}
