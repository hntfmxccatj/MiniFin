import { state } from '../state.js';
import { uploadFiles, saveBills, fetchCategories } from '../api.js';
import { showToast } from '../utils.js';
import { DataTable } from './DataTable.js';

const uploadIcon = `
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
  <polyline points="17 8 12 3 7 8"></polyline>
  <line x1="12" y1="3" x2="12" y2="15"></line>
</svg>`;

export function UploadZone() {
    return `
        <div class="upload-zone" id="uploadZone">
            ${uploadIcon}
            <h3>拖拽微信 / 支付宝 CSV / XLSX 账单到此处</h3>
            <p>或点击选择文件，支持多选。数据解析后可在下方预览并检查</p>
            <input type="file" id="fileInput" multiple accept=".csv,.xlsx">
        </div>

        <div class="upload-meta" id="uploadMeta" style="display:none;">
            <div class="status" id="uploadStatus">已解析 0 条记录</div>
            <div style="display:flex;gap:8px;">
                <button class="btn btn-outline" id="clearUploadBtn">清空</button>
                <button class="btn btn-success" id="saveBtn" disabled>保存到数据库</button>
            </div>
        </div>

        <div id="uploadTableContainer" style="display:none;"></div>
    `;
}

function renderUploadTable() {
    const container = document.getElementById('uploadTableContainer');
    container.innerHTML = DataTable(state.uploadedRecords, { title: '本次上传数据（可编辑 Major / Sub）', editable: true });
    container.style.display = 'block';
    bindCategorySelects();
}

function bindCategorySelects() {
    const options = state.categoryOptions || {};

    document.querySelectorAll('.major-select').forEach(sel => {
        sel.addEventListener('change', e => {
            const idx = Number(e.target.dataset.row);
            const major = e.target.value;
            state.uploadedRecords[idx].major_category = major;
            state.uploadedRecords[idx].sub_category = '';

            const subSelect = document.querySelector(`.sub-select[data-row="${idx}"]`);
            const subs = options[major] || [];
            subSelect.innerHTML = `
                <option value="" selected>- Sub -</option>
                ${subs.map(s => `<option value="${s}">${s}</option>`).join('')}
            `;
        });
    });

    document.querySelectorAll('.sub-select').forEach(sel => {
        sel.addEventListener('change', e => {
            const idx = Number(e.target.dataset.row);
            state.uploadedRecords[idx].sub_category = e.target.value;
        });
    });
}

function clearUpload() {
    state.uploadedRecords = [];
    const container = document.getElementById('uploadTableContainer');
    container.innerHTML = '';
    container.style.display = 'none';
    document.getElementById('uploadMeta').style.display = 'none';
    document.getElementById('saveBtn').disabled = true;
    document.getElementById('fileInput').value = '';
}

async function loadCategories() {
    if (!state.categoryOptions) {
        try {
            state.categoryOptions = await fetchCategories();
        } catch (e) {
            console.error(e);
            state.categoryOptions = {};
        }
    }
}

async function handleFiles(files) {
    const validFiles = Array.from(files).filter(f => /\.(csv|xlsx)$/.test(f.name.toLowerCase()));
    if (!validFiles.length) { showToast('请选择 CSV 或 XLSX 文件', 'error'); return; }

    const status = document.getElementById('uploadStatus');
    status.textContent = '正在解析...';
    document.getElementById('uploadMeta').style.display = 'flex';

    try {
        await loadCategories();
        const json = await uploadFiles(validFiles);
        if (!json.records || !json.records.length) {
            showToast(json.message || '未解析到记录', 'error');
            status.textContent = '未解析到有效记录';
            return;
        }
        state.uploadedRecords = json.records;
        renderUploadTable();
        status.textContent = `已解析 ${json.total} 条记录`;
        document.getElementById('saveBtn').disabled = false;
    } catch (e) {
        console.error(e);
        showToast('解析失败', 'error');
        status.textContent = '解析失败';
    }
}

async function handleSave() {
    const btn = document.getElementById('saveBtn');
    btn.disabled = true;
    btn.textContent = '保存中...';
    try {
        const json = await saveBills(state.uploadedRecords);
        showToast(`保存成功：新写入 ${json.inserted} 条，跳过重复 ${json.skipped_duplicate} 条`, 'success');
        clearUpload();
    } catch (e) {
        console.error(e);
        showToast('保存失败', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '保存到数据库';
    }
}

export function initUploadZone() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');

    uploadZone.addEventListener('click', () => fileInput.click());
    uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
    uploadZone.addEventListener('drop', e => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });
    fileInput.addEventListener('change', e => handleFiles(e.target.files));
    document.getElementById('clearUploadBtn').addEventListener('click', clearUpload);
    document.getElementById('saveBtn').addEventListener('click', handleSave);

    // 提前加载分类选项，避免上传时等待
    loadCategories();
}

