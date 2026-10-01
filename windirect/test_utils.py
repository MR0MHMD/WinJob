"""دادهٔ آزمایشی اشتراک برای آزمون‌های پنل و موتور اجرا."""

from .models import SubscriptionPlan, SubscriptionOffer
from .subscriptions.services import activate_trial


def enable_test_trial(user):
    """در تست‌ها به صورت صریح یک پلن آزمایشی فعال می‌کند."""
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code="test-trial",
        defaults={
            "name": "رایگان آزمایش",
            "is_trial": True,
            "level": 0,
            "forms": True,
            "showcases": True,
            "max_pages": 10,
        },
    )
    offer, _ = SubscriptionOffer.objects.get_or_create(
        plan=plan, duration_days=30, defaults={"price": 0}
    )
    return activate_trial(user, offer)
