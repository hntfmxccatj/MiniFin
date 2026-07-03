import { UploadZone, initUploadZone } from '../components/UploadZone.js';

export function UploadPage() {
    return UploadZone();
}

export function mountUpload() {
    initUploadZone();
}
