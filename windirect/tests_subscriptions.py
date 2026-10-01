"""آزمون خرید، قیمت‌گذاری، هدیه، تسهیم و مرزبندی دسترسی اشتراک."""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from django.utils import timezone
from payment.models import (
    Wallet,
    Invoice,
    Payment,
    Transaction,
    CommissionSplit,
    SubscriptionPaymentAttempt,
)
from payment.services.payout import payout_commission
from payment.services.subscription_payment import (
    pay_subscription_wallet,
    start_subscription_gateway,
    settle_subscription_gateway,
)
from .models import (
    SubscriptionPlan,
    SubscriptionOffer,
    SubscriptionAccount,
    SubscriptionOrder,
    UserSubscription,
    ReferralCode,
    ReferralRedemption,
    SubscriptionGift,
    InstagramConnection,
    Automation,
    DirectRule,
    ConversationForm,
    FormQuestion,
    FormSubmission,
)
from .subscriptions.services import (
    account_for,
    activate_trial,
    create_order,
    current_period,
    remaining_periods,
    as_datetime,
)
from .subscriptions.access import (
    require_feature,
    require_connection,
    register_connection,
)
from .services import simulate_comment
from .direct_services import simulate_direct


class SubscriptionTests(TestCase):
    """سناریوهای مالی و دسترسی را با زمان و پاسخ کنترل‌شدهٔ درگاه آزمایش می‌کند."""

    def setUp(self):
        users = get_user_model()
        self.user = users.objects.create_user(phone_number="09120003001")
        self.owner = users.objects.create_user(phone_number="09120003002")
        self.ceo = users.objects.create_user(phone_number="09120003003", role="ceo")
        self.dev = users.objects.create_user(
            phone_number="09120003004", role="developer"
        )
        self.basic = SubscriptionPlan.objects.create(
            name="پایه", code="basic", level=1, max_pages=1
        )
        self.pro = SubscriptionPlan.objects.create(
            name="حرفه‌ای", code="pro", level=2, max_pages=5, showcases=True, forms=True
        )
        self.trial = SubscriptionPlan.objects.create(
            name="رایگان",
            code="trial",
            level=0,
            max_pages=5,
            is_trial=True,
            showcases=True,
            forms=True,
        )
        self.free = SubscriptionOffer.objects.create(
            plan=self.trial, duration_days=30, price=0
        )
        self.basic_offer = SubscriptionOffer.objects.create(
            plan=self.basic, duration_days=30, price=30000
        )
        self.basic90 = SubscriptionOffer.objects.create(
            plan=self.basic, duration_days=90, price=90000
        )
        self.pro_offer = SubscriptionOffer.objects.create(
            plan=self.pro, duration_days=30, price=45000
        )
        self.pro90 = SubscriptionOffer.objects.create(
            plan=self.pro, duration_days=90, price=135000
        )
        self.referral = ReferralCode.objects.create(owner=self.owner, code="FRIEND")
        Wallet.objects.filter(user=self.user).update(balance=10000000)
        Wallet.objects.filter(user=self.owner).update(balance=10000000)
        self.client.force_login(self.user)

    def buy(self, user=None, offer=None, code=""):
        """یک سفارش واقعی سرویس را با کیف پول می‌پردازد."""
        user = user or self.user
        order = create_order(user, offer or self.basic_offer, referral_code=code)
        pay_subscription_wallet(order, user)
        order.refresh_from_db()
        return order

    def attempt(self, order, authority="A-1"):
        """تلاش محلی و نتیجهٔ تأییدشدهٔ هم‌مبلغ درگاه را آماده می‌کند."""
        payment = Payment.objects.create(
            user=order.user,
            invoice=order.invoice,
            amount=order.invoice.payable_amount,
            payment_method="gateway",
            authority=authority,
        )
        attempt = SubscriptionPaymentAttempt.objects.create(
            order=order, payment=payment, authority=authority
        )
        result = SimpleNamespace(
            status="complete",
            authority=authority,
            order_id=f"windirect-{attempt.pk}",
            amount=order.invoice.payable_amount * 10,
            gateway_slug="zarinpal",
            reference_id="REF-" + authority,
        )
        return attempt, result

    def test_signup_and_plan_view_do_not_activate_trial(self):
        self.assertIsNone(current_period(self.user))
        self.assertFalse(UserSubscription.objects.exists())
        self.client.get(reverse("windirect:plans"))
        self.assertFalse(UserSubscription.objects.exists())
        self.assertIsNone(account_for(self.user).trial_used_at)

    def test_trial_is_explicit_one_time_and_all_features(self):
        url = reverse("windirect:trial_activate", args=[self.free.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertTrue(current_period(self.user).capabilities["forms"])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(UserSubscription.objects.count(), 1)
        with self.assertRaises(ValidationError):
            activate_trial(self.user, self.basic_offer)

    def test_paid_user_can_skip_trial_and_cannot_claim_it_later(self):
        self.buy()
        self.assertEqual(current_period(self.user).kind, "paid")
        with self.assertRaises(ValidationError):
            activate_trial(self.user, self.free)

    def test_purchase_during_trial_starts_after_trial_and_keeps_paid_capabilities(self):
        trial = activate_trial(self.user, self.free)
        order = self.buy()
        paid = order.periods.get(kind="paid")
        self.assertEqual(as_datetime(paid.starts_at), as_datetime(trial.ends_at))
        self.assertTrue(require_feature(self.user, "forms"))
        with patch(
            "windirect.subscriptions.services.timezone.now",
            return_value=as_datetime(paid.starts_at) + timedelta(seconds=1),
        ):
            with self.assertRaises(ValidationError):
                require_feature(self.user, "forms")

    def test_wallet_invoice_tax_snapshot_and_net_split(self):
        order = self.buy(code="friend")
        invoice = order.invoice
        self.assertEqual(
            (
                invoice.base_plan_cost,
                invoice.plan_discount_amount,
                invoice.plan_cost,
                invoice.plan_vat,
                invoice.payable_amount,
            ),
            (30000, 9000, 21000, 2100, 23100),
        )
        self.assertEqual(Wallet.objects.get(user=self.user).balance, 10000000 - 23100)
        split = CommissionSplit.objects.get(invoice=invoice)
        self.assertEqual(
            (split.site_maintenance_amount, split.ceo_amount, split.developer_amount),
            (2100, 11340, 7560),
        )
        self.assertTrue(split.is_balanced)
        self.assertEqual(Wallet.objects.get(user=self.ceo).balance, 11340)
        self.assertEqual(Wallet.objects.get(user=self.dev).balance, 7560)
        self.assertIsNotNone(invoice.commission_paid_at)
        self.assertFalse(payout_commission(invoice).success)
        self.assertEqual(CommissionSplit.objects.count(), 1)
        pay_subscription_wallet(order, self.user)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(ReferralRedemption.objects.count(), 1)

    def test_vat_uses_payment_constant(self):
        with patch("payment.constants.VAT_PERCENT", Decimal("0.20")):
            order = create_order(self.user, self.basic_offer)
        self.assertEqual(order.invoice.plan_vat, 6000)
        self.assertEqual(order.quote["vat_rate"], "0.20")

    def test_renewal_preserves_remaining_time(self):
        self.buy()
        account = account_for(self.user)
        previous = remaining_periods(account)[-1]
        order = self.buy()
        period = order.periods.get(kind="paid")
        self.assertEqual(as_datetime(period.starts_at), as_datetime(previous.ends_at))
        self.assertEqual(
            as_datetime(period.ends_at) - as_datetime(previous.ends_at),
            timedelta(days=30),
        )

    def test_insufficient_wallet_rolls_back_everything(self):
        order = create_order(self.user, self.basic_offer, referral_code="FRIEND")
        Wallet.objects.filter(user=self.user).update(balance=1)
        with self.assertRaises(ValidationError):
            pay_subscription_wallet(order, self.user)
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(UserSubscription.objects.exists())
        self.assertFalse(CommissionSplit.objects.exists())
        self.assertFalse(ReferralRedemption.objects.exists())
        self.assertEqual(Wallet.objects.get(user=self.user).balance, 1)

    def test_referral_first_purchase_only_and_self_use_denied(self):
        own = ReferralCode.objects.create(owner=self.user, code="SELF")
        with self.assertRaises(ValidationError):
            create_order(self.user, self.basic_offer, referral_code=own.code)
        self.buy(code="FRIEND")
        with self.assertRaises(ValidationError):
            create_order(self.user, self.basic_offer, referral_code="FRIEND")
        order = self.buy()
        self.assertEqual(order.quote["discount"], 0)
        self.assertEqual(ReferralRedemption.objects.count(), 1)

    def test_referral_buyer_days_and_owner_bank_consumed_on_next_purchase(self):
        activate_trial(self.owner, self.free)
        order = self.buy(code="FRIEND")
        self.assertEqual(
            as_datetime(order.periods.last().ends_at)
            - as_datetime(order.periods.first().starts_at),
            timedelta(days=35),
        )
        self.assertEqual(account_for(self.owner).banked_gift_days, 1)
        owner_order = self.buy(user=self.owner)
        self.assertEqual(account_for(self.owner).banked_gift_days, 0)
        gift = SubscriptionGift.objects.get(account__user=self.owner)
        self.assertIsNotNone(gift.period_id)
        self.assertEqual(owner_order.periods.filter(kind="gift").count(), 1)

    def test_referrer_active_paid_receives_one_day_and_expired_banks(self):
        owner_order = self.buy(user=self.owner)
        last = owner_order.periods.last()
        self.buy(code="FRIEND")
        tail = remaining_periods(account_for(self.owner))[-1]
        self.assertEqual(
            as_datetime(tail.ends_at) - as_datetime(last.ends_at), timedelta(days=1)
        )
        self.assertEqual(account_for(self.owner).banked_gift_days, 0)

    def test_expired_referrer_gift_is_saved(self):
        self.buy(user=self.owner)
        UserSubscription.objects.filter(account__user=self.owner).update(
            starts_at=timezone.now() - timedelta(days=60),
            ends_at=timezone.now() - timedelta(days=30),
        )
        self.buy(code="FRIEND")
        self.assertEqual(account_for(self.owner).banked_gift_days, 1)

    def test_upgrade_example_and_same_duration_and_no_downgrade(self):
        self.buy(offer=self.basic90)
        period = UserSubscription.objects.get(account__user=self.user)
        now = timezone.now()
        period.starts_at = now - timedelta(days=30)
        period.ends_at = now + timedelta(days=60)
        period.save()
        with patch("windirect.subscriptions.services.timezone.now", return_value=now):
            with self.assertRaises(ValidationError):
                create_order(self.user, self.pro_offer, kind="upgrade")
            order = create_order(self.user, self.pro90, kind="upgrade")
        self.assertEqual(order.invoice.plan_cost, 30000)
        self.assertEqual(order.invoice.payable_amount, 33000)
        pay_subscription_wallet(order, self.user)
        self.assertEqual(
            as_datetime(remaining_periods(account_for(self.user))[-1].ends_at),
            now + timedelta(days=60),
        )
        self.assertEqual(current_period(self.user).plan_name, "حرفه‌ای")
        with self.assertRaises(ValidationError):
            create_order(self.user, self.basic90)

    def test_upgrade_uses_discounted_credit_and_gifts_have_zero_credit(self):
        self.buy(code="FRIEND")
        now = timezone.now()
        with patch("windirect.subscriptions.services.timezone.now", return_value=now):
            order = create_order(self.user, self.pro_offer, kind="upgrade")
        self.assertEqual(order.quote["upgrades"][0]["credit_daily"], "700.00000000")
        self.assertEqual(Decimal(order.quote["upgrades"][1]["credit_daily"]), 0)
        self.assertAlmostEqual(order.quote["base"], 800 * 30 + 1500 * 5, delta=1)
        pay_subscription_wallet(order, self.user)
        self.assertFalse(
            UserSubscription.objects.filter(
                account__user=self.user,
                is_superseded=False,
                ends_at__gt=timezone.now(),
                capabilities__level=1,
            ).exists()
        )
        self.assertTrue(SubscriptionGift.objects.get(account__user=self.user).period_id)

    def test_multiple_renewal_durations_upgrade_with_matching_offers(self):
        self.buy()
        self.buy(offer=self.basic90)
        order = create_order(self.user, self.pro_offer, kind="upgrade")
        self.assertEqual(len(order.quote["upgrades"]), 2)
        self.assertEqual(
            {row["offer_id"] for row in order.quote["upgrades"]},
            {self.pro_offer.pk, self.pro90.pk},
        )
        pay_subscription_wallet(order, self.user)

    def test_offer_edits_do_not_change_order_or_existing_entitlement(self):
        order = create_order(self.user, self.basic_offer)
        self.basic_offer.price = 999999
        self.basic_offer.duration_days = 365
        self.basic_offer.save()
        self.basic.max_pages = 99
        self.basic.save()
        pay_subscription_wallet(order, self.user)
        self.assertEqual(order.invoice.plan_cost, 30000)
        self.assertEqual(current_period(self.user).capabilities["max_pages"], 1)
        self.assertEqual(current_period(self.user).duration_days, 30)

    def test_stale_wallet_quote_rejected_without_charge(self):
        first = create_order(self.user, self.basic_offer)
        second = create_order(self.user, self.basic_offer)
        pay_subscription_wallet(second, self.user)
        before = Wallet.objects.get(user=self.user).balance
        with self.assertRaises(ValidationError):
            pay_subscription_wallet(first, self.user)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, before)

    def test_gateway_success_repeated_callback_once_and_binding_checks(self):
        order = create_order(self.user, self.basic_offer, referral_code="FRIEND")
        attempt, result = self.attempt(order)
        result.amount += 10
        with self.assertRaises(ValidationError):
            settle_subscription_gateway(attempt, result)
        result.amount -= 10
        settle_subscription_gateway(attempt, result)
        settle_subscription_gateway(attempt, result)
        self.assertEqual(
            UserSubscription.objects.filter(
                account__user=self.user, kind="paid"
            ).count(),
            1,
        )
        self.assertEqual(ReferralRedemption.objects.count(), 1)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, 10000000)
        self.assertEqual(CommissionSplit.objects.count(), 1)

    def test_gateway_expired_or_cancelled_order_credits_wallet_once(self):
        order = create_order(self.user, self.basic_offer)
        attempt, result = self.attempt(order)
        order.expires_at = timezone.now() - timedelta(seconds=1)
        order.save()
        settle_subscription_gateway(attempt, result)
        settle_subscription_gateway(attempt, result)
        order.refresh_from_db()
        self.assertEqual(order.status, "credited")
        self.assertEqual(Wallet.objects.get(user=self.user).balance, 10000000 + 33000)
        self.assertFalse(UserSubscription.objects.exists())
        self.assertFalse(CommissionSplit.objects.exists())

    def test_gateway_second_paid_attempt_is_wallet_credit(self):
        order = create_order(self.user, self.basic_offer)
        first, result1 = self.attempt(order, "FIRST")
        second, result2 = self.attempt(order, "SECOND")
        settle_subscription_gateway(first, result1)
        settle_subscription_gateway(second, result2)
        self.assertEqual(Wallet.objects.get(user=self.user).balance, 10000000 + 33000)
        self.assertEqual(UserSubscription.objects.count(), 1)
        self.assertEqual(CommissionSplit.objects.count(), 1)

    def test_missing_manager_defers_payout_but_keeps_payment_and_split(self):
        self.dev.is_active = False
        self.dev.save()
        with self.assertLogs("payment.services.subscription_payment", level="ERROR"):
            order = self.buy()
        self.assertTrue(order.invoice.is_paid)
        self.assertTrue(CommissionSplit.objects.filter(invoice=order.invoice).exists())
        self.assertIsNone(order.invoice.commission_paid_at)
        self.assertEqual(Wallet.objects.get(user=self.ceo).balance, 0)
        self.dev.is_active = True
        self.dev.save()
        self.assertTrue(payout_commission(order.invoice).success)
        self.assertEqual(Wallet.objects.get(user=self.ceo).balance, 16200)
        self.assertEqual(Wallet.objects.get(user=self.dev).balance, 10800)

    def test_access_expiry_page_cap_and_basic_feature_bypass(self):
        self.buy()
        first = register_connection(self.user, InstagramConnection(username="first"))
        with self.assertRaises(ValidationError):
            register_connection(self.user, InstagramConnection(username="second"))
        with self.assertRaises(ValidationError):
            require_feature(self.user, "forms")
        # ورود مستقیم داده توسط ادمین نیز نباید مسیر اجرای پلن پایه را دور بزند.
        form = ConversationForm.objects.create(connection=first, name="فرم")
        FormQuestion.objects.create(form=form, prompt="نام؟")
        DirectRule.objects.create(
            connection=first, name="فرم", keyword="فرم", response_type="form", form=form
        )
        event, _ = simulate_direct(
            connection=first, sender_id="x", message_id="m1", text="فرم"
        )
        self.assertEqual(event.response["kind"], "unmatched")
        UserSubscription.objects.filter(account__user=self.user).update(
            starts_at=timezone.now() - timedelta(days=60),
            ends_at=timezone.now() - timedelta(days=30),
        )
        with self.assertRaises(ValidationError):
            simulate_comment(
                connection=first, comment_id="x", media_id="p", text="سلام"
            )
        self.assertEqual(self.client.get(reverse("windirect:logs")).status_code, 200)

    def test_basic_cannot_create_rule_linked_to_form(self):
        self.buy()
        connection = register_connection(
            self.user, InstagramConnection(username="mine")
        )
        form = ConversationForm.objects.create(connection=connection, name="فرم")
        response = self.client.post(
            reverse("windirect:asset_create", args=["direct"]),
            {
                "connection": connection.pk,
                "name": "فرم",
                "keyword": "فرم",
                "match_type": "exact",
                "priority": 10,
                "response_type": "form",
                "form": form.pk,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DirectRule.objects.exists())
        self.assertEqual(
            self.client.get(
                reverse("windirect:asset_create", args=["forms"])
            ).status_code,
            302,
        )

    def test_foreign_orders_attempts_and_invoice_hidden_and_csrf(self):
        order = create_order(self.owner, self.basic_offer)
        attempt, _ = self.attempt(order)
        for name in ["subscription_order", "subscription_checkout"]:
            self.assertEqual(
                self.client.get(
                    reverse("windirect:" + name, args=[order.pk])
                ).status_code,
                404,
            )
        self.assertEqual(
            self.client.post(
                reverse("payment:subscription_reverify", args=[attempt.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("payment:invoice_detail", args=[order.invoice.pk])
            ).status_code,
            404,
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(
            client.post(
                reverse("windirect:trial_activate", args=[self.free.pk])
            ).status_code,
            403,
        )

    def test_pages_and_subscription_invoice_use_site_base(self):
        order = create_order(self.user, self.basic_offer)
        for name, args in [
            ("plans", []),
            ("subscription", []),
            ("subscribe", [self.basic_offer.pk]),
            ("subscription_checkout", [order.pk]),
            ("subscription_order", [order.pk]),
        ]:
            response = self.client.get(reverse("windirect:" + name, args=args))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "parent/base.html")
        for name in ["invoice_detail", "invoice_print"]:
            response = self.client.get(
                reverse("payment:" + name, args=[order.invoice.pk])
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "فاکتور اشتراک وین دایرکت")
            self.assertContains(response, "33,000")
        response = self.client.get(reverse("payment:invoice_list") + "?type=windirect")
        self.assertContains(response, "پایه")

    def test_seed_command_is_repeatable_without_overwriting_prices(self):
        call_command("load_windirect_plans", verbosity=0)
        self.basic_offer.price = 123456
        self.basic_offer.save()
        call_command("load_windirect_plans", verbosity=0)
        self.basic_offer.refresh_from_db()
        self.assertEqual(self.basic_offer.price, 123456)

    def test_callback_settles_without_browser_login_and_network_retry(self):
        order = create_order(self.user, self.basic_offer)
        attempt, result = self.attempt(order)
        self.client.logout()
        with patch(
            "payment.services.subscription_payment.gateway.verify_payment",
            return_value=result,
        ):
            response = self.client.get(
                reverse("payment:subscription_callback") + "?Authority=A-1&Status=OK"
            )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 302)

    def test_gateway_start_uses_database_amount_and_reuses_attempt(self):
        order = create_order(self.user, self.basic_offer)
        with patch(
            "payment.services.subscription_payment.gateway.start_payment",
            return_value=(
                SimpleNamespace(authority="START"),
                "https://sandbox.zarinpal.com/pg/StartPay/START",
            ),
        ) as start:
            first = start_subscription_gateway(order, self.user)
            second = start_subscription_gateway(order, self.user)
        self.assertEqual(first, second)
        self.assertEqual(start.call_count, 1)
        self.assertEqual(start.call_args.kwargs["amount"], 33000)
        self.assertEqual(start.call_args.kwargs["currency"], "toman")
        self.assertEqual(SubscriptionPaymentAttempt.objects.count(), 1)
        with self.assertRaises(ValidationError):
            pay_subscription_wallet(order, self.user)

    def test_existing_campaign_commission_formula_is_unchanged(self):
        from payment.services.commission import _calculate_shares

        split = _calculate_shares(100000, "content_only", None)
        self.assertEqual(
            (split.ceo_amount, split.developer_amount, split.content_manager_amount),
            (36000, 24000, 30000),
        )

    def test_trial_referrer_with_reserved_purchase_gift_follows_paid_period(self):
        activate_trial(self.owner, self.free)
        self.buy(user=self.owner)
        self.buy(code="FRIEND")
        self.assertEqual(account_for(self.owner).banked_gift_days, 0)
        gift = SubscriptionGift.objects.get(account__user=self.owner)
        self.assertIsNotNone(gift.period_id)
        self.assertEqual(gift.period.kind, "gift")
        self.assertEqual(current_period(self.owner).kind, "trial")

    def test_all_subscription_admin_pages_and_retry_action(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        order = self.buy()
        models = [
            "subscriptionplan",
            "subscriptionoffer",
            "subscriptionaccount",
            "subscriptionorder",
            "usersubscription",
            "referralcode",
            "referralredemption",
            "subscriptiongift",
        ]
        for model in models:
            response = self.client.get(
                reverse("admin:windirect_" + model + "_changelist")
            )
            self.assertEqual(response.status_code, 200)
        for name in [
            "payment_commissionsplit_changelist",
            "payment_subscriptionpaymentattempt_changelist",
        ]:
            self.assertEqual(self.client.get(reverse("admin:" + name)).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("admin:payment_invoice_change", args=[order.invoice.pk])
            ).status_code,
            200,
        )
        response = self.client.get(reverse("admin:payment_commissionsplit_changelist"))
        self.assertContains(response, "retry_payout")

    def test_expired_subscription_retains_form_excel_and_logs(self):
        self.buy(offer=self.pro_offer)
        connection = register_connection(
            self.user, InstagramConnection(username="mine")
        )
        form = ConversationForm.objects.create(connection=connection, name="اطلاعات")
        FormQuestion.objects.create(form=form, prompt="نام شما؟")
        DirectRule.objects.create(
            connection=connection,
            name="فرم",
            keyword="فرم",
            response_type="form",
            form=form,
        )
        simulate_direct(
            connection=connection, sender_id="visitor", message_id="1", text="فرم"
        )
        simulate_direct(
            connection=connection, sender_id="visitor", message_id="2", text="محمد"
        )
        UserSubscription.objects.filter(account__user=self.user).update(
            starts_at=timezone.now() - timedelta(days=60),
            ends_at=timezone.now() - timedelta(days=30),
        )
        response = self.client.get(
            reverse("windirect:export_submissions", args=[form.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(
            self.client.get(
                reverse("windirect:submissions", args=[form.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("windirect:direct_logs")).status_code, 200
        )
        with self.assertRaises(ValidationError):
            simulate_direct(
                connection=connection, sender_id="visitor", message_id="3", text="فرم"
            )

    def test_second_page_from_admin_is_blocked_until_slot_is_freed(self):
        self.buy()
        first = InstagramConnection.objects.create(owner=self.user, username="first")
        second = InstagramConnection.objects.create(owner=self.user, username="second")
        with self.assertRaises(ValidationError):
            require_connection(second, "smart_direct")
        first.status = "disconnected"
        first.save()
        self.assertTrue(require_connection(second, "smart_direct"))

    def test_gateway_network_error_keeps_order_pending_for_reverify(self):
        order = create_order(self.user, self.basic_offer)
        attempt, _ = self.attempt(order)
        with self.assertLogs("payment.views.subscription", level="ERROR"), patch(
            "payment.services.subscription_payment.gateway.verify_payment",
            side_effect=TimeoutError,
        ):
            self.client.get(
                reverse("payment:subscription_callback") + "?Authority=A-1&Status=OK"
            )
        order.refresh_from_db()
        attempt.refresh_from_db()
        self.assertEqual(order.status, "pending")
        self.assertIsNone(attempt.verified_at)
        self.assertFalse(UserSubscription.objects.exists())

    def test_reconciliation_consumes_completed_package_record(self):
        from django_iranian_payment.contrib.django.models import (
            Payment as GatewayPayment,
        )

        order = create_order(self.user, self.basic_offer)
        attempt, result = self.attempt(order)
        GatewayPayment.objects.create(
            gateway_slug="zarinpal",
            order_id=result.order_id,
            amount=result.amount,
            amount_sent=result.amount,
            authority=result.authority,
            callback_url="http://127.0.0.1/payment/windirect/callback/",
            status="complete",
            reference_id=result.reference_id,
        )
        call_command("reconcile_windirect_payments", verbosity=0)
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        call_command("reconcile_windirect_payments", verbosity=0)
        self.assertEqual(UserSubscription.objects.count(), 1)
