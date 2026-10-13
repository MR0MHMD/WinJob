from windirect.tests.utils import enable_test_trial
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from windirect.comments.models import Automation, AutomationExecution, CommentEvent
from windirect.connections.models import InstagramConnection


class WindirectPanelTests(TestCase):
    """ساخت قانون، شبیه‌سازی و مرزبندی داده‌های کاربران را بررسی می‌کند."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            phone_number="09120001001", password="test"
        )
        self.other = user_model.objects.create_user(
            phone_number="09120001002", password="test"
        )
        enable_test_trial(self.user)
        self.connection = InstagramConnection.objects.create(
            owner=self.user, username="my_page"
        )
        self.other_connection = InstagramConnection.objects.create(
            owner=self.other, username="other_page"
        )
        self.other_rule = Automation.objects.create(
            connection=self.other_connection,
            name="خصوصی",
            keyword="قیمت",
            reply_text="محرمانه",
        )
        self.client.force_login(self.user)

    def test_private_pages_require_login(self):
        """بازدیدکنندهٔ ناشناس به پنل خصوصی دسترسی ندارد."""
        self.client.logout()
        for name in (
            "dashboard",
            "connections",
            "rules",
            "rule_create",
            "simulation",
            "logs",
        ):
            response = self.client.get(reverse(f"windirect:{name}"))
            self.assertEqual(response.status_code, 302)

    def test_account_registration_is_simulated(self):
        """فرم ثبت حساب هیچ ادعای اتصال رسمی یا شناسهٔ رسمی ایجاد نمی‌کند."""
        response = self.client.post(
            reverse("windirect:connections"), {"username": "@New.Page"}
        )
        self.assertRedirects(response, reverse("windirect:connections"))
        connection = InstagramConnection.objects.get(
            owner=self.user, username="new.page"
        )
        self.assertEqual(connection.status, InstagramConnection.Status.SIMULATED)
        self.assertIsNone(connection.instagram_user_id)

    def test_rule_cannot_target_another_users_account(self):
        """شناسهٔ حساب دست‌کاری‌شده در POST رد می‌شود."""
        data = {
            "connection": self.other_connection.pk,
            "name": "نادرست",
            "media_id": "",
            "keyword": "قیمت",
            "match_type": Automation.MatchType.CONTAINS,
            "reply_text": "پاسخ",
            "is_active": "on",
        }
        response = self.client.post(reverse("windirect:rule_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Automation.objects.filter(name="نادرست").exists())
        data["connection"] = self.connection.pk
        response = self.client.post(reverse("windirect:rule_create"), data)
        self.assertRedirects(response, reverse("windirect:rules"))
        self.assertTrue(
            Automation.objects.filter(
                name="نادرست", connection=self.connection
            ).exists()
        )

    def test_foreign_rule_is_hidden_and_cannot_be_changed(self):
        """لیست، ویرایش، فعال‌سازی و حذف قانون کاربر دیگر بسته است."""
        response = self.client.get(reverse("windirect:rules"))
        self.assertNotContains(response, "خصوصی")
        self.assertEqual(
            self.client.get(
                reverse("windirect:rule_edit", args=[self.other_rule.pk])
            ).status_code,
            404,
        )
        for name in ("rule_toggle", "rule_delete"):
            self.assertEqual(
                self.client.post(
                    reverse(f"windirect:{name}", args=[self.other_rule.pk])
                ).status_code,
                404,
            )
        self.assertTrue(
            Automation.objects.filter(pk=self.other_rule.pk, is_active=True).exists()
        )

    def test_simulation_creates_only_owned_logs_and_keeps_history(self):
        """فرم نمونه لاگ را می‌سازد و حذف قانون دارای سابقه را مسدود می‌کند."""
        rule = Automation.objects.create(
            connection=self.connection,
            name="قیمت محصول",
            keyword="قیمت",
            reply_text="جزئیات قیمت",
        )
        data = {"connection": self.connection.pk, "media_id": "post-1", "text": "قیمت؟"}
        response = self.client.post(reverse("windirect:simulation"), data)
        self.assertContains(response, "جزئیات قیمت")
        self.assertEqual(
            CommentEvent.objects.filter(connection=self.connection).count(), 1
        )
        self.assertEqual(AutomationExecution.objects.filter(automation=rule).count(), 1)
        response = self.client.get(reverse("windirect:logs"))
        self.assertContains(response, "قیمت محصول")
        self.client.post(reverse("windirect:rule_delete", args=[rule.pk]))
        self.assertTrue(Automation.objects.filter(pk=rule.pk).exists())
        self.assertEqual(
            self.client.post(
                reverse("windirect:simulation"),
                {
                    "connection": self.other_connection.pk,
                    "media_id": "post-1",
                    "text": "قیمت؟",
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            CommentEvent.objects.filter(connection=self.other_connection).count(), 0
        )
