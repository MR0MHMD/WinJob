from django.core.management.base import BaseCommand, CommandError

from windirect.models import InstagramConnection
from windirect.services import simulate_comment


class Command(BaseCommand):
    help = "آزمایش قوانین وین دایرکت بدون ارسال پیام به اینستاگرام"

    def add_arguments(self, parser):
        parser.add_argument("connection_id", type=int)
        parser.add_argument("comment_id")
        parser.add_argument("media_id")
        parser.add_argument("text")

    def handle(self, *args, **options):
        try:
            connection = InstagramConnection.objects.get(pk=options["connection_id"])
            _, executions = simulate_comment(
                connection=connection, comment_id=options["comment_id"],
                media_id=options["media_id"], text=options["text"],
            )
        except InstagramConnection.DoesNotExist as exc:
            raise CommandError("حساب آزمایشی پیدا نشد.") from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"{len(executions)} قانون اجرا شد (فقط شبیه‌سازی؛ هیچ دایرکتی ارسال نشد).")
