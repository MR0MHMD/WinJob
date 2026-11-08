"""رجیستری آداپتورهای پیام‌رسان — نگاشت slug پلتفرم به کلاس آداپتور."""

from typing import Optional, Type
from .base import MessengerAdapter

_REGISTRY: dict[str, Type[MessengerAdapter]] = {}


def register(adapter_class: Type[MessengerAdapter], slug: Optional[str] = None) -> Type[MessengerAdapter]:
    """ثبت یک کلاس آداپتور برای پلتفرم مشخص (قابل استفاده به‌عنوان دکوراتور)."""
    key = slug or getattr(adapter_class, "platform_slug", "")
    if not key:
        raise ValueError("آداپتور باید platform_slug داشته باشد یا slug صریحاً داده شود.")
    _REGISTRY[key] = adapter_class
    return adapter_class


def unregister(platform_slug: str) -> None:
    """حذف آداپتور از رجیستری (عمدتاً برای تست)."""
    _REGISTRY.pop(platform_slug, None)


def get_adapter(platform_slug: str, **kwargs) -> Optional[MessengerAdapter]:
    """نمونه آداپتور برای پلتفرم مشخص یا None در صورت ثبت‌نشدن.

    kwargs اختیاری به سازنده آداپتور پاس داده می‌شوند (مثلاً token برای ایتا).
    """
    cls = _REGISTRY.get(platform_slug)
    return cls(**kwargs) if cls else None


def get_adapter_class(platform_slug: str):
    """کلاس آداپتور ثبت‌شده را بدون نمونه‌سازی برمی‌گرداند (برای save/restore در تست‌ها)."""
    return _REGISTRY.get(platform_slug)


def get_registered_slugs() -> list[str]:
    """لیست slug های ثبت‌شده."""
    return sorted(_REGISTRY.keys())
