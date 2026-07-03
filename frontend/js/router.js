import { DashboardPage, mountDashboard } from './pages/DashboardPage.js';
import { UploadPage, mountUpload } from './pages/UploadPage.js';
import { Layout, initLayout } from './components/Layout.js';

const routes = {
    dashboard: { page: DashboardPage, mount: mountDashboard, title: '概览看板' },
    upload: { page: UploadPage, mount: mountUpload, title: '上传账单' },
};

function updateSidebarActive(routeName) {
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    const active = document.querySelector(`.nav-item[data-route="${routeName}"]`);
    if (active) active.classList.add('active');
}

export function getRoute() {
    const hash = location.hash.replace('#', '');
    return routes[hash] ? hash : 'dashboard';
}

export function renderApp() {
    const routeName = getRoute();
    const route = routes[routeName];
    document.getElementById('app').innerHTML = Layout(route.page(), route.title);
    initLayout();
    updateSidebarActive(routeName);
    route.mount();
}

export function initRouter() {
    window.addEventListener('hashchange', renderApp);
    renderApp();
}
