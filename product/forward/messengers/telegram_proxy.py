"""مدیریت دائمی و خودکار پروکسی محلی Xray برای ارتباط با API تلگرام (سازگار با لینوکس و ویندوز)."""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

try:
    import fcntl
except ImportError:
    fcntl = None

from django.conf import settings

logger = logging.getLogger(__name__)

XRAY_DOWNLOAD_URL = "https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip"
RUNTIME_DIR = Path(tempfile.gettempdir()) / "xray_runtime"
XRAY_BIN_NAME = "xray.exe" if os.name == "nt" else "xray"
XRAY_BIN_PATH = RUNTIME_DIR / XRAY_BIN_NAME
XRAY_LOG_PATH = RUNTIME_DIR / "xray.log"
XRAY_LOCK_PATH = RUNTIME_DIR / "xray.lock"
_THREAD_LOCK = threading.Lock()


def get_telegram_proxy_url() -> str:
    """دریافت آدرس پروکسی تلگرام از تنظیمات جنگو یا متغیر محیطی."""
    return (getattr(settings, "TELEGRAM_PROXY_URL", "") or os.environ.get("TELEGRAM_PROXY_URL", "")).strip()


def get_telegram_proxies() -> Optional[Dict[str, str]]:
    """ساخت دیکشنری پروکسی سازگار با کتابخانه requests برای ارسال درخواست‌های تلگرام."""
    url = get_telegram_proxy_url()
    if not url:
        return None
    return {"http": url, "https": url}


def _is_port_open(host: str, port: int, timeout: float = 0.6) -> bool:
    """بررسی باز بودن پورت TCP روی هاست مشخص."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _get_default_config_path() -> Path:
    """یافتن مسیر فایل کانفیگ Xray داخل پروژه."""
    custom = os.environ.get("TELEGRAM_XRAY_CONFIG_PATH", "").strip()
    if custom:
        return Path(custom)
    return Path(settings.BASE_DIR) / "product" / "forward" / "bin" / "xray_config.json"


def _download_xray_binary() -> bool:
    """دانلود و آماده‌سازی باینری رسمی Xray (روی لینوکس) در مسیر موقت دائمی کانتینر."""
    if os.name == "nt":
        logger.info("[telegram_proxy] On Windows, please keep v2rayN open on port 10808.")
        return False
    zip_path = RUNTIME_DIR / "xray.zip"
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("[telegram_proxy] Downloading Xray binary from GitHub...")
        urllib.request.urlretrieve(XRAY_DOWNLOAD_URL, str(zip_path))
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(RUNTIME_DIR)
        if zip_path.exists():
            zip_path.unlink()
        if XRAY_BIN_PATH.exists():
            os.chmod(XRAY_BIN_PATH, 0o755)
            return True
    except Exception as exc:
        logger.error("[telegram_proxy] Failed to download Xray binary: %s", exc)
    return False


def _start_xray_locked(host: str, port: int, config_path: Path) -> bool:
    """اجرای امن Xray پس از گرفتن قفل پروسس/ترد."""
    if _is_port_open(host, port):
        return True

    if not XRAY_BIN_PATH.exists():
        if not _download_xray_binary():
            return False

    log_fp = open(XRAY_LOG_PATH, "ab")
    subprocess.Popen(
        [str(XRAY_BIN_PATH), "run", "-c", str(config_path)],
        stdout=log_fp,
        stderr=log_fp,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )

    for _ in range(25):
        if _is_port_open(host, port, timeout=0.3):
            time.sleep(1.8)
            logger.info("[telegram_proxy] Xray proxy started cleanly on %s:%s", host, port)
            return True
        time.sleep(0.2)

    logger.error("[telegram_proxy] Xray started but port %s:%s did not open in time.", host, port)
    return False


def ensure_telegram_proxy() -> bool:
    """اطمینان از فعال بودن پروکسی تلگرام؛ روی لینوکس Xray را خودکار بالا می‌آورد و روی ویندوز از پورت باز v2rayN استفاده می‌کند."""
    proxy_url = get_telegram_proxy_url()
    if not proxy_url:
        return True

    parsed = urlparse(proxy_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 10808

    if host not in ("127.0.0.1", "localhost", "::1"):
        return _is_port_open(host, port, timeout=1.5)

    if _is_port_open(host, port):
        return True

    config_path = _get_default_config_path()
    if not config_path.exists():
        logger.error("[telegram_proxy] Xray config not found at %s", config_path)
        return False

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if fcntl is not None:
        with open(XRAY_LOCK_PATH, "w", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                return _start_xray_locked(host, port, config_path)
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)

    with _THREAD_LOCK:
        return _start_xray_locked(host, port, config_path)


def restart_telegram_proxy() -> bool:
    """ری‌استارت کردن پروسه Xray محلی پس از تغییر فایل کانفیگ."""
    if os.name != "nt":
        try:
            subprocess.run(["pkill", "-f", str(XRAY_BIN_PATH)], check=False)
            time.sleep(0.5)
        except Exception:
            pass
    return ensure_telegram_proxy()
