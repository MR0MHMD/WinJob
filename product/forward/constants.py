"""ثابت‌های مرکزی و نرخ‌های توکن وین‌فوروارد (بدون نیاز به جدول اضافی در دیتابیس)."""

from __future__ import annotations

from dataclasses import dataclass

# ==================== نرخ‌های مصرف توکن (به ازای هر تحویل موفق در یک کانال) ====================
TOKEN_COST_TEXT: int = 2
TOKEN_COST_PHOTO: int = 2
TOKEN_COST_CAPTION_EXTRA: int = 2
TOKEN_COST_STICKER_GIF: int = 3
TOKEN_COST_MEDIA_UNDER_5MB: int = 5
TOKEN_COST_MEDIA_5_TO_10MB: int = 7
TOKEN_COST_MEDIA_10_TO_20MB: int = 10
TOKEN_COST_HUB_EXTRA: int = 2
TOKEN_COST_AI_WATERMARK: int = 2  # حذف یا بازسازی هوشمند واترمارک متنی به ازای هر کانال

# ==================== محدودیت‌ها، هدیه و نرخ نمایش تومانی ====================
MAX_FILE_SIZE_MB: int = 20
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024
FREE_GIFT_TOKENS: int = 350
TOKEN_TOMAN_RATE: int = 50  # معادل نمایشی هر توکن در گزارش‌ها و نمودارها (تومان)

# ==================== پیش‌فرض‌های هوش مصنوعی وین‌فوروارد (گیت‌وی چابکان) ====================
DEFAULT_WINFORWARD_AI_ENDPOINT: str = "https://ai.chabokan.net/v1/chat/completions"
DEFAULT_WINFORWARD_AI_MODEL: str = "deepseek/deepseek-v3.2"
DEFAULT_WINFORWARD_AI_TIMEOUT: int = 60


@dataclass(frozen=True)
class TokenPricingConfig:
    """نمای خواندنی و سازگار با قالب‌ها برای تمام نرخ‌های ثابت توکن (صفر کوئری دیتابیس)."""

    text_cost: int = TOKEN_COST_TEXT
    photo_cost: int = TOKEN_COST_PHOTO
    caption_extra_cost: int = TOKEN_COST_CAPTION_EXTRA
    sticker_gif_cost: int = TOKEN_COST_STICKER_GIF
    media_under_5mb_cost: int = TOKEN_COST_MEDIA_UNDER_5MB
    media_5_to_10mb_cost: int = TOKEN_COST_MEDIA_5_TO_10MB
    media_10_to_20mb_cost: int = TOKEN_COST_MEDIA_10_TO_20MB
    max_file_size_mb: int = MAX_FILE_SIZE_MB
    hub_extra_cost: int = TOKEN_COST_HUB_EXTRA
    ai_watermark_extra_cost: int = TOKEN_COST_AI_WATERMARK
    free_gift_tokens: int = FREE_GIFT_TOKENS
    token_toman_rate: int = TOKEN_TOMAN_RATE


PRICING_CONFIG = TokenPricingConfig()
