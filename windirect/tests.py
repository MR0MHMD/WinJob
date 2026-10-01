from .test_utils import enable_test_trial
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Automation, AutomationExecution, CommentEvent, InstagramConnection
from .services import simulate_comment


class SimulationTests(TestCase):
    """تطبیق قوانین و جلوگیری از اجرای تکراری را بررسی می‌کند."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(phone_number="09120000000", password="test")
        enable_test_trial(self.user)
        self.connection = InstagramConnection.objects.create(owner=self.user, username="winjob_test")
        self.rule = Automation.objects.create(
            connection=self.connection, name="قیمت", keyword="قیمت", media_id="post-1",
            reply_text="جزئیات قیمت", is_active=True,
        )

    def test_matches_only_account_media_and_keyword(self):
        _, executions = simulate_comment(connection=self.connection, comment_id="c1",
                                         media_id="post-1", text="لطفا قيمت را بگویید")
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0].status, AutomationExecution.Status.SIMULATED)
        self.assertEqual(executions[0].response_text, "جزئیات قیمت")
        _, other_media = simulate_comment(connection=self.connection, comment_id="c2",
                                          media_id="post-2", text="قیمت")
        self.assertEqual(other_media, [])
        self.assertEqual(CommentEvent.objects.count(), 2)

    def test_duplicate_comment_does_not_execute_twice(self):
        simulate_comment(connection=self.connection, comment_id="c1", media_id="post-1", text="قیمت")
        _, executions = simulate_comment(connection=self.connection, comment_id="c1",
                                         media_id="post-1", text="قیمت")
        self.assertEqual(executions, [])
        self.assertEqual(AutomationExecution.objects.count(), 1)

    def test_exact_match_and_inactive_rule(self):
        self.rule.match_type = Automation.MatchType.EXACT
        self.rule.save(update_fields=["match_type"])
        _, executions = simulate_comment(connection=self.connection, comment_id="c1",
                                         media_id="post-1", text="قیمت محصول")
        self.assertEqual(executions, [])
        self.rule.is_active = False
        self.rule.save(update_fields=["is_active"])
        _, executions = simulate_comment(connection=self.connection, comment_id="c2",
                                         media_id="post-1", text="قیمت")
        self.assertEqual(executions, [])


class AdminTests(TestCase):
    """بارگذاری فهرست و جزئیات ادمین وین دایرکت را بررسی می‌کند."""

    def test_admin_pages_include_rules_and_persian_fields(self):
        admin_user = get_user_model().objects.create_superuser(
            phone_number="09120000001", password="test-admin",
        )
        connection = InstagramConnection.objects.create(owner=admin_user, username="winjob_test")
        self.client.force_login(admin_user)

        for url in (
            reverse("admin:windirect_instagramconnection_changelist"),
            reverse("admin:windirect_instagramconnection_change", args=[connection.pk]),
            reverse("admin:windirect_automation_changelist"),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
        self.assertContains(response, "نام قانون")
