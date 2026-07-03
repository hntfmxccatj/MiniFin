import { Sidebar, initSidebar } from './Sidebar.js';
import { Topbar } from './Topbar.js';

export function Layout(pageHtml, title) {
    return `
        <div class="app">
            ${Sidebar()}
            <div class="main">
                ${Topbar(title)}
                <main class="container" id="page-content">
                    ${pageHtml}
                </main>
            </div>
        </div>
    `;
}

export function initLayout() {
    initSidebar();
}
