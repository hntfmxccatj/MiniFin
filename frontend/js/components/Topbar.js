export function Topbar(title) {
    return `
        <header class="topbar">
            <div class="topbar-title" id="pageTitle">${title}</div>
            <div style="font-size:13px;color:var(--text-muted)">个人账单数据看板</div>
        </header>
    `;
}
