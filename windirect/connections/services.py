import re
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import InstagramConnection
from windirect.subscriptions.models import SubscriptionAccount
from windirect.subscriptions.services import current_period, account_for


def build_simulated_identity(owner_id, username):
    """شناسه مصنوعی یکتا برای حساب آزمایشی می‌سازد."""
    normalized = re.sub(r"[^a-z0-9._]", "", username.lower())
    return f"sim_{owner_id}_{normalized}"


@transaction.atomic
def register_connection(user, connection):
    """ثبت هم‌زمان چند پیج را با قفل حساب و رعایت سقف کنترل می‌کند."""
    account_for(user)
    SubscriptionAccount.objects.select_for_update().get(user=user)

    # بررسی یکتایی نام کاربری در کل دیتابیس (نه فقط حساب‌های خود کاربر)
    if (
        InstagramConnection.objects.filter(username__iexact=connection.username)
        .exclude(pk=connection.pk)
        .exists()
    ):
        raise ValidationError("این نام کاربری قبلاً در سیستم ثبت شده است.")

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
    # شناسه مصنوعی یکتا برای حساب آزمایشی
    connection.instagram_user_id = build_simulated_identity(
        user.pk, connection.username
    )
    connection.save()
    return connection