"""
Management Command: پاک کردن فایل‌های orphan از BoxAPI.

فایل‌هایی که بیش از TTL در وضعیت pending موندن، orphan حساب میشن
و از BoxAPI حذف میشن.

Usage:
    python manage.py cleanup_orphan_uploads
    python manage.py cleanup_orphan_uploads --hours 48
    python manage.py cleanup_orphan_uploads --dry-run
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from windirect.comments.models import MediaUpload
from windirect.connections.boxapi import delete_file


# ==================== TTL پیش‌فرض ====================
DEFAULT_TTL_HOURS = 24


class Command(BaseCommand):
    help = "پاک کردن فایل‌های orphan (pending قدیمی) از BoxAPI"

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=DEFAULT_TTL_HOURS,
            help=f"حداکثر زمان (ساعت) برای pending بودن (پیش‌فرض: {DEFAULT_TTL_HOURS})",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="فقط نشون بده، پاک نکن",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        dry_run = options["dry_run"]

        self.stdout.write(self.style.WARNING(
            f"🧹 cleanup_orphan_uploads START | TTL={hours}h | dry_run={dry_run}"
        ))

        # ==================== پیدا کردن فایل‌های orphan ====================
        cutoff = timezone.now() - timedelta(hours=hours)

        orphans = MediaUpload.objects.filter(
            status=MediaUpload.Status.PENDING,
            created_at__lt=cutoff,
        ).order_by("created_at")

        total = orphans.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                "✅ هیچ فایل orphan‌ای پیدا نشد."
            ))
            return

        self.stdout.write(
            f"🔍 {total} فایل orphan پیدا شد (قدیمی‌تر از {hours} ساعت):"
        )

        # ==================== نمایش لیست ====================
        for upload in orphans[:20]:  # فقط ۲۰ تا اول رو نشون بده
            self.stdout.write(
                f"  - ID={upload.pk} | {upload.file_name} | "
                f"{upload.get_size_display()} | "
                f"created_at={upload.created_at}"
            )

        if total > 20:
            self.stdout.write(f"  ... و {total - 20} فایل دیگر")

        # ==================== dry-run ====================
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"🔸 DRY RUN: هیچ فایلی پاک نشد. برای پاک کردن، --dry-run رو حذف کن."
            ))
            return

        # ==================== حذف از BoxAPI ====================
        deleted_count = 0
        failed_count = 0

        for upload in orphans:
            self.stdout.write(
                f"🗑️ حذف فایل ID={upload.pk} | {upload.file_name} | "
                f"boxapi_id={upload.boxapi_file_id}"
            )

            # حذف از BoxAPI
            success = delete_file(upload.boxapi_file_id)

            if success:
                upload.mark_orphan()
                deleted_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ حذف شد | status → orphan"
                ))
            else:
                failed_count += 1
                self.stdout.write(self.style.ERROR(
                    f"  ❌ حذف ناموفق | BoxAPI error"
                ))

        # ==================== خلاصه ====================
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"🏁 cleanup_orphan_uploads DONE | "
            f"deleted={deleted_count} | failed={failed_count} | total={total}"
        ))
