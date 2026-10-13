"""آزمون مالکیت مدل‌ها و حفظ داده هنگام تفکیک اپ‌ها."""

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase
from django.urls import resolve, reverse
from django.utils import timezone

GROUPS = {
    "connections": ["InstagramConnection"],
    "comments": ["Automation", "CommentEvent", "AutomationExecution"],
    "direct": ["DirectRule", "DirectMessageEvent"],
    "showcases": ["Showcase", "ShowcaseCard"],
    "forms": ["ConversationForm", "FormQuestion", "FormSubmission"],
    "subscriptions": [
        "SubscriptionPlan",
        "SubscriptionOffer",
        "SubscriptionAccount",
        "ReferralCode",
        "SubscriptionOrder",
        "UserSubscription",
        "ReferralRedemption",
        "SubscriptionGift",
    ],
}


class AppOwnershipTests(SimpleTestCase):
    """تفکیک واقعی اپ‌ها و قرارداد عمومی مسیرها را بررسی می‌کند."""

    def test_each_model_belongs_to_its_app_with_existing_table(self):
        self.assertEqual(list(apps.get_app_config("windirect").get_models()), [])
        for group, models in GROUPS.items():
            config = apps.get_app_config("windirect_" + group)
            self.assertEqual(config.name, "windirect." + group)
            self.assertEqual(
                {model.__name__ for model in config.get_models()}, set(models)
            )
            for name in models:
                self.assertEqual(
                    config.get_model(name)._meta.db_table, "windirect_" + name.lower()
                )

    def test_tools_keep_public_urls_and_route_only_to_their_app(self):
        for kind in ("direct", "showcases", "forms"):
            url = reverse("windirect:asset_create", args=[kind])
            self.assertEqual(url, "/windirect/panel/tools/" + kind + "/new/")
            self.assertEqual(resolve(url).kwargs["kind"], kind)
        self.assertEqual(
            resolve(reverse("windirect:connections")).func.__module__,
            "windirect.connections.views",
        )
        self.assertEqual(
            resolve(reverse("windirect:rules")).func.__module__,
            "windirect.comments.views",
        )


class AppMigrationTests(TransactionTestCase):
    """داده و مجوز قدیمی را از ساختار تک‌اپ به شش اپ منتقل می‌کند."""

    def test_existing_records_relations_permissions_and_content_type_ids_survive(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old_targets = [
            (label, name)
            for label, name in latest
            if label != "windirect"
            and label != "payment"
            and not label.startswith("windirect_")
        ]
        old_targets += [
            ("windirect", "0004_subscriptions"),
            ("payment", "0013_merge_0012_alter_transaction_type_0012_subscriptions"),
        ]
        old_targets += [("windirect_" + group, None) for group in GROUPS]
        try:
            executor.migrate(old_targets)
            state = executor.loader.project_state(
                [target for target in old_targets if target[1] is not None]
            )
            old = state.apps
            user = get_user_model().objects.create_user(
                phone_number="09120001111", password="test-pass"
            )
            conn = old.get_model("windirect", "InstagramConnection").objects.create(
                owner_id=user.pk, username="kept"
            )
            rule = old.get_model("windirect", "Automation").objects.create(
                connection_id=conn.pk, name="قانون", keyword="قیمت", reply_text="پاسخ"
            )
            event = old.get_model("windirect", "CommentEvent").objects.create(
                connection_id=conn.pk,
                external_comment_id="old-comment",
                media_id="post",
                text="قیمت",
            )
            execution = old.get_model(
                "windirect", "AutomationExecution"
            ).objects.create(
                automation_id=rule.pk, event_id=event.pk, response_text="پاسخ"
            )
            plan = old.get_model("windirect", "SubscriptionPlan").objects.create(
                name="پلن قبلی", code="kept", level=1
            )
            offer = old.get_model("windirect", "SubscriptionOffer").objects.create(
                plan_id=plan.pk, duration_days=30, price=1000
            )
            order = old.get_model("windirect", "SubscriptionOrder").objects.create(
                user_id=user.pk,
                offer_id=offer.pk,
                kind="purchase",
                quote={},
                account_revision=0,
                expires_at=timezone.now(),
            )
            invoice = old.get_model("payment", "Invoice").objects.create(
                user_id=user.pk,
                type="windirect",
                subscription_order_id=order.pk,
                plan_cost=1000,
            )
            content = ContentType.objects.get(app_label="windirect", model="automation")
            permission = Permission.objects.get(
                content_type=content, codename="change_automation"
            )
            group = Group.objects.create(name="مدیریت قوانین")
            group.permissions.add(permission)
            user.groups.add(group)
            ids = (
                conn.pk,
                rule.pk,
                event.pk,
                execution.pk,
                plan.pk,
                offer.pk,
                order.pk,
                invoice.pk,
                content.pk,
                permission.pk,
            )
            tables = set(connection.introspection.table_names())
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            from windirect.connections.models import InstagramConnection
            from windirect.comments.models import Automation, AutomationExecution
            from windirect.subscriptions.models import SubscriptionOrder
            from payment.models import Invoice

            self.assertEqual(
                InstagramConnection.objects.get(pk=ids[0]).username, "kept"
            )
            self.assertEqual(Automation.objects.get(pk=ids[1]).connection_id, ids[0])
            self.assertEqual(
                AutomationExecution.objects.get(pk=ids[3]).event_id, ids[2]
            )
            self.assertEqual(SubscriptionOrder.objects.get(pk=ids[6]).offer_id, ids[5])
            self.assertEqual(
                Invoice.objects.get(pk=ids[7]).subscription_order_id, ids[6]
            )
            self.assertEqual(set(connection.introspection.table_names()), tables)
            self.assertEqual(
                ContentType.objects.get(pk=ids[8]).app_label, "windirect_comments"
            )
            self.assertTrue(group.permissions.filter(pk=ids[9]).exists())
            self.assertTrue(
                get_user_model()
                .objects.get(pk=user.pk)
                .has_perm("windirect_comments.change_automation")
            )
        finally:
            MigrationExecutor(connection).migrate(latest)
            ContentType.objects.clear_cache()
