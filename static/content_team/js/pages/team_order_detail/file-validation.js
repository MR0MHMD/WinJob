const SERVICE_FILE_TYPES = {
    'طراحی استوری': {
        extensions: ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.mp4', '.mov'],
        mimeTypes: ['image/*', 'video/mp4', 'video/quicktime'],
        message: 'فایل‌های مجاز: تصاویر (JPG, PNG, GIF, WEBP) و ویدیوهای کوتاه (MP4, MOV)'
    },
    'تولید ویدیو کوتاه': {
        extensions: ['.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v'],
        mimeTypes: ['video/*'],
        message: 'فایل‌های مجاز: ویدیو (MP4, MOV, AVI, WEBM, MKV)'
    },
    'موشن گرافیک': {
        extensions: ['.mp4', '.mov', '.webm', '.gif', '.m4v'],
        mimeTypes: ['video/*', 'image/gif'],
        message: 'فایل‌های مجاز: ویدیو (MP4, MOV, WEBM) و GIF'
    },
    'عکاسی تبلیغاتی': {
        extensions: ['.jpg', '.jpeg', '.png', '.webp', '.tiff', '.bmp', '.raw'],
        mimeTypes: ['image/*'],
        message: 'فایل‌های مجاز: تصاویر با کیفیت بالا (JPG, PNG, TIFF, RAW)'
    },
    'طراحی پوستر و بنر': {
        extensions: ['.jpg', '.jpeg', '.png', '.webp', '.svg', '.pdf', '.psd', '.ai', '.eps'],
        mimeTypes: ['image/*', 'application/pdf', 'application/postscript', 'image/vnd.adobe.photoshop'],
        message: 'فایل‌های مجاز: تصاویر (JPG, PNG, SVG) و فایل‌های طراحی (PSD, AI, EPS, PDF)'
    },
    'پادکست و محتوای صوتی': {
        extensions: ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'],
        mimeTypes: ['audio/*'],
        message: 'فایل‌های مجاز: فایل‌های صوتی (MP3, WAV, FLAC, AAC, OGG)'
    },
    'اینفوگرافیک متحرک': {
        extensions: ['.mp4', '.mov', '.webm', '.gif', '.m4v', '.svg'],
        mimeTypes: ['video/*', 'image/gif', 'image/svg+xml'],
        message: 'فایل‌های مجاز: ویدیو (MP4, MOV, WEBM) و GIF و SVG'
    },
    'تدوین ویدیو': {
        extensions: ['.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v', '.mpg', '.mpeg'],
        mimeTypes: ['video/*'],
        message: 'فایل‌های مجاز: ویدیو (MP4, MOV, AVI, WEBM, MKV, MPEG)'
    }
};

const DEFAULT_ALLOWED = {
    extensions: ['*'],
    mimeTypes: ['*/*'],
    message: 'همه انواع فایل‌ها مجاز هستند'
};

function getServiceFileTypes(serviceName) {
    for (const [key, value] of Object.entries(SERVICE_FILE_TYPES)) {
        if (serviceName.includes(key) || key.includes(serviceName)) {
            return value;
        }
    }
    return DEFAULT_ALLOWED;
}

function isValidFileType(file, serviceName) {
    const allowed = getServiceFileTypes(serviceName);

    if (allowed.extensions[0] === '*') {
        return { valid: true, message: allowed.message };
    }

    const fileName = file.name.toLowerCase();
    const fileType = file.type;

    const extValid = allowed.extensions.some(ext => fileName.endsWith(ext));
    const mimeValid = allowed.mimeTypes.some(mime => {
        if (mime.endsWith('/*')) {
            const prefix = mime.replace('/*', '');
            return fileType.startsWith(prefix);
        }
        return fileType === mime;
    });

    const valid = extValid || mimeValid;
    return {
        valid: valid,
        message: valid ? allowed.message : `نوع فایل "${fileName.split('.').pop()}" برای این سرویس مجاز نیست. ${allowed.message}`
    };
}