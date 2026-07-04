export const state = {
    sidebarCollapsed: false,
    uploadedRecords: [],
    summary: null,
    categoryOptions: null,
    filters: {
        range: 'all',
        source: '',
        keyword: '',
        start_date: '',
        end_date: '',
    },
};

export function updateFilters(newFilters) {
    Object.assign(state.filters, newFilters);
}
