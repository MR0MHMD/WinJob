"""کنترل مشترک دسترسی زمانی و سقف پیج در پنل و موتور اجرا."""

from django.core.exceptions import ValidationError
from django.db import transaction
from ..models import InstagramConnection, SubscriptionAccount
from .services import current_period, account_for

FEATURE_LABELS = {
    "smart_comments": "کامنت هوشمند",
    "smart_direct": "دایرکت هوشمند",
    "showcases": "ویترین‌ساز",
    "forms": "فرم‌ساز",
}


def require_feature(user, feature):
    """امکان را از نسخهٔ خریداری‌شده و زمان واقعی بررسی می‌کند."""
    period = current_period(user)
    if period is None:
        raise ValidationError(
            "برای استفاده از وین دایرکت، دورهٔ رایگان یا یک اشتراک را فعال کنید."
        )
    if not period.capabilities.get(feature, False):
        raise ValidationError(
            f"اشتراک شما به {FEATURE_LABELS[feature]} دسترسی ندارد؛ پلن را ارتقا دهید."
        )
    return period


def allowed_connection_ids(user, period=None):
    """پیج‌های قدیمی‌تر تا سقف اشتراک فعال مجاز به اجرا هستند."""
    period = period or current_period(user)
    if not period:
        return []
    return list(
        InstagramConnection.objects.filter(
            owner=user, status__in=["simulated", "connected"]
        )
        .order_by("pk")
        .values_list("pk", flat=True)[: int(period.capabilities["max_pages"])]
    )


def require_connection(connection, feature):
    """موتور اجرا علاوه بر قابلیت، حساب و سقف پیج را بررسی می‌کند."""
    period = require_feature(connection.owner, feature)
    if connection.pk not in allowed_connection_ids(connection.owner, period):
        raise ValidationError(
            "این پیج غیرفعال یا خارج از سقف پیج‌های اشتراک است. پیج‌های اضافی را قطع کنید."
        )
    return period


@transaction.atomic
def register_connection(user, connection):
    """ثبت هم‌زمان چند پیج را با قفل حساب و رعایت سقف کنترل می‌کند."""
    account_for(user)
    SubscriptionAccount.objects.select_for_update().get(user=user)
    if (
        InstagramConnection.objects.filter(
            owner=user, username__iexact=connection.username
        )
        .exclude(pk=connection.pk)
        .exists()
    ):
        raise ValidationError("این حساب را قبلاً ثبت کرده‌اید.")
    period = current_period(user)
    if period is None:
        raise ValidationError("ابتدا دورهٔ رایگان یا اشتراک وین دایرکت را فعال کنید.")
    count = (
        InstagramConnection.objects.filter(
            owner=user, status__in=["simulated", "connected"]
        )
        .exclude(pk=connection.pk)
        .count()
    )
    if count >= int(period.capabilities["max_pages"]):
        raise ValidationError(
            "به سقف پیج‌های اشتراک رسیده‌اید؛ یک پیج را قطع کنید یا پلن را ارتقا دهید."
        )
    connection.owner = user
    connection.status = "simulated"
    connection.save()
    return connection
