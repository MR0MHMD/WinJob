function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function getFileIcon(fileName) {
    const ext = fileName.split('.').pop().toLowerCase();
    const icons = {
        'jpg': 'fi-image', 'jpeg': 'fi-image', 'png': 'fi-image',
        'gif': 'fi-image', 'webp': 'fi-image', 'svg': 'fi-image',
        'mp4': 'fi-video', 'avi': 'fi-video', 'mov': 'fi-video',
        'webm': 'fi-video', 'mkv': 'fi-video',
        'mp3': 'fi-music', 'wav': 'fi-music', 'flac': 'fi-music',
        'pdf': 'fi-file', 'doc': 'fi-file', 'docx': 'fi-file',
        'xls': 'fi-file', 'xlsx': 'fi-file', 'ppt': 'fi-file',
        'pptx': 'fi-file', 'txt': 'fi-file',
        'zip': 'fi-archive', 'rar': 'fi-archive', '7z': 'fi-archive',
        'tar': 'fi-archive', 'gz': 'fi-archive'
    };
    return icons[ext] || 'fi-file';
}

function showMessage(message, type = 'info', onClose = null) {
    if (typeof toastManager !== 'undefined') {
        toastManager.show(message, type);
        if (onClose) setTimeout(onClose, 3000);
    } else {
        alert(message);
        if (onClose) onClose();
    }
}