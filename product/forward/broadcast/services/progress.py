"""مدیریت پیام وضعیت زنده مرحله‌به‌مرحله (ProgressTracker) در ربات‌های بله و تلگرام."""

from __future__ import annotations

import logging

from product.forward.broadcast.models import BroadcastJob

logger = logging.getLogger(__name__)

PLATFORM_FA_NAMES = {
    "bale": "بله",
    "eitaa": "ایتا",
    "telegram": "تلگرام",
    "soroush": "سروش‌پلاس",
    "rubika": "روبیکا",
}


def platform_fa(slug: str) -> str:
    return PLATFORM_FA_NAMES.get(slug, slug)


class ProgressTracker:
    """مدیریت پیام وضعیت زنده از بالا به پایین در ربات‌ها (با حذف پیام موقت و ارسال گزارش نهایی جدید)."""

    def __init__(
        self,
        adapter,
        chat_id,
        *,
        fallback_chat_id: str = None,
        hub_title: str = "",
        hub_sender_name: str = "",
        is_file_msg: bool = False,
        source_platform: str = "bale",
        needs_download: bool = False,
        needs_ai: bool = False,
        platform_totals: dict | None = None,
    ):
        self.adapter = adapter
        self.chat_id = chat_id
        self.fallback_chat_id = fallback_chat_id
        self.hub_title = (hub_title or "").strip()
        self.hub_sender_name = (hub_sender_name or "").strip()
        self.is_fallback_to_owner = False
        self.message_id = None
        self._current_text = None
        self.is_file_msg = bool(is_file_msg)
        self.source_platform = source_platform
        self.needs_download = bool(is_file_msg and needs_download)
        self.needs_ai = bool(needs_ai)

        self.download_state = "pending"  # pending | running | done | failed
        self.ai_state = "pending"        # pending | running | done | failed
        self.platforms: dict[str, dict] = {}
        for slug, total in (platform_totals or {}).items():
            if total > 0:
                self.platforms[slug] = {
                    "total": int(total),
                    "started": 0,
                    "success": 0,
                    "failed": 0,
                    "skipped": 0,
                }

    def _update(self, text: str, parse_mode: str = None):
        if not text or text == self._current_text:
            return
        self._current_text = text
        is_tg = getattr(self.adapter, "platform_slug", "") == "telegram"
        if self.message_id:
            try:
                if is_tg and parse_mode:
                    self.adapter.edit_message_text(self.chat_id, self.message_id, text, parse_mode=parse_mode)
                else:
                    self.adapter.edit_message_text(self.chat_id, self.message_id, text)
                return
            except Exception as exc:
                logger.warning("edit_message_text failed, falling back to send: %s", exc)
                self.message_id = None
        try:
            if is_tg and parse_mode:
                result = self.adapter.send_text(self.chat_id, text, parse_mode=parse_mode)
            else:
                result = self.adapter.send_text(self.chat_id, text)
            self.message_id = result.get("message_id")
        except Exception as exc:
            # اگر فرستنده در گروه هاب هنوز ربات را استارت نکرده باشد، گزارش با ذکر نام فرستنده به پی‌وی مالک هاب می‌رود
            if (
                not self.is_fallback_to_owner
                and self.fallback_chat_id
                and str(self.fallback_chat_id) != str(self.chat_id)
            ):
                logger.info(
                    "Sender %s has not started bot; falling back progress report to hub owner %s",
                    self.chat_id,
                    self.fallback_chat_id,
                )
                self.chat_id = self.fallback_chat_id
                self.is_fallback_to_owner = True
                owner_text = self._with_owner_header(text)
                self._current_text = owner_text
                try:
                    if is_tg and parse_mode:
                        result = self.adapter.send_text(self.chat_id, owner_text, parse_mode=parse_mode)
                    else:
                        result = self.adapter.send_text(self.chat_id, owner_text)
                    self.message_id = result.get("message_id")
                    return
                except Exception as exc2:
                    logger.warning("Failed to send fallback progress message to hub owner: %s", exc2)
                    return
            logger.warning("Failed to send progress message: %s", exc)

    def _with_owner_header(self, text: str) -> str:
        if not self.is_fallback_to_owner:
            return text
        hub_part = f"👥 گزارش هاب «{self.hub_title}»" if self.hub_title else "👥 گزارش ارسال از هاب تیمی"
        sender_part = f"👤 فرستنده در گروه: {self.hub_sender_name}" if self.hub_sender_name else "👤 فرستنده: عضو گروه (ربات را استارت نکرده)"
        header = f"{hub_part}\n{sender_part}\n"
        if text.startswith(hub_part):
            return text
        return f"{header}\n{text}"

    def _render_live_text(self) -> str:
        # حالت پیام صرفاً متنی
        if not self.is_file_msg:
            if self.needs_ai and self.ai_state in ("pending", "running"):
                return self._with_owner_header("✨ در حال افزودن امضای اختصاصی ⏳")
            return self._with_owner_header("در حال ارسال به کانال‌ها ⏳")

        # حالت پیام فایلی (برد زنده دقیقاً به ترتیب اجرا از بالا به پایین)
        lines = ["درخواست شما در حال اجراست ⚙️", ""]

        if self.needs_download:
            dl_map = {
                "pending": "در صف انتظار 🕒",
                "running": "در حال انجام ⏳",
                "done": "انجام شد ✅",
                "failed": "ناموفق ❌",
            }
            lines.append(
                f"📥 دانلود از {platform_fa(self.source_platform)}: "
                f"{dl_map.get(self.download_state, 'در حال انجام ⏳')}"
            )

        if self.needs_ai:
            ai_map = {
                "pending": "در صف انتظار 🕒",
                "running": "در حال انجام ⏳",
                "done": "انجام شد ✅",
                "failed": "خطا (ارسال متن اصلی) ⚠️",
            }
            lines.append(f"✨ افزودن امضای اختصاصی: {ai_map.get(self.ai_state, 'در صف انتظار 🕒')}")

        for slug, st in self.platforms.items():
            total = st["total"]
            done_cnt = st["success"] + st["failed"] + st["skipped"]
            if done_cnt >= total:
                if st["success"] == total:
                    status_str = "ارسال شد ✅"
                elif st["skipped"] == total:
                    status_str = "رد شد ⏭️"
                elif st["success"] > 0:
                    status_str = f"نیمه‌موفق ({st['success']} از {total}) ⚠️"
                else:
                    status_str = "ناموفق ❌"
            elif st["started"] > 0:
                if total > 1:
                    status_str = f"در حال ارسال ({min(st['started'], total)} از {total}) 🚀"
                else:
                    status_str = "در حال ارسال 🚀"
            else:
                status_str = "در صف انتشار 🕒"
            lines.append(f"📤 ارسال به {platform_fa(slug)}: {status_str}")

        return self._with_owner_header("\n".join(lines))

    def start(self):
        self._update(self._render_live_text())

    def start_download(self, source_platform: str = None):
        if source_platform:
            self.source_platform = source_platform
        self.needs_download = True
        self.download_state = "running"
        self._update(self._render_live_text())

    def finish_download(self, ok: bool = True):
        if not self.needs_download:
            return
        self.download_state = "done" if ok else "failed"
        self._update(self._render_live_text())

    def start_ai(self):
        self.needs_ai = True
        self.ai_state = "running"
        self._update(self._render_live_text())

    def finish_ai(self, ok: bool = True):
        if not self.needs_ai:
            return
        self.ai_state = "done" if ok else "failed"
        self._update(self._render_live_text())

    def start_platform_target(self, platform_slug: str):
        st = self.platforms.get(platform_slug)
        if st is None:
            st = {"total": 1, "started": 0, "success": 0, "failed": 0, "skipped": 0}
            self.platforms[platform_slug] = st
        st["started"] += 1
        self._update(self._render_live_text())

    def complete_platform_target(self, platform_slug: str, outcome: str):
        st = self.platforms.get(platform_slug)
        if st is None:
            return
        if outcome == "success":
            st["success"] += 1
        elif outcome == "skipped":
            st["skipped"] += 1
        else:
            st["failed"] += 1
        self._update(self._render_live_text())

    def finish(self, job):
        final_text = self._with_owner_header(self._build_final_text(job))
        is_tg = getattr(self.adapter, "platform_slug", "") == "telegram"

        deleted = False
        if self.message_id and hasattr(self.adapter, "delete_message"):
            try:
                self.adapter.delete_message(self.chat_id, self.message_id)
                deleted = True
                self.message_id = None
                self._current_text = None
            except Exception as exc:
                logger.warning("Failed to delete live progress message %s: %s", self.message_id, exc)

        if deleted or not self.message_id:
            try:
                if is_tg:
                    self.adapter.send_text(self.chat_id, final_text, parse_mode="Markdown")
                else:
                    self.adapter.send_text(self.chat_id, final_text)
                return
            except Exception as exc:
                logger.warning("Failed to send final report message: %s", exc)

        self._update(final_text, parse_mode="Markdown")

    @staticmethod
    def _build_final_text(job) -> str:
        total_targets = int(job.total_targets or job.targets.count())
        success_count = int(job.success_count or 0)
        if total_targets == 0:
            return "⚠️ هیچ کانالی برای ارسال وجود نداشت."

        if job.status == BroadcastJob.Status.DONE or (success_count == total_targets and total_targets > 0):
            status_label = "🟢 موفق"
        elif job.status == BroadcastJob.Status.PARTIAL or (0 < success_count < total_targets):
            status_label = "🟡 نیمه‌موفق"
        else:
            status_label = "🔴 ناموفق"

        spent = 0
        try:
            from product.forward.subscriptions.models import ForwardTokenTransaction

            spent = sum(
                abs(int(x))
                for x in ForwardTokenTransaction.objects.filter(
                    user=job.message.user,
                    tx_type=ForwardTokenTransaction.TxType.SPEND,
                    broadcast_job_id=job.pk,
                ).values_list("amount", flat=True)
            )
        except Exception:
            spent = 0

        report_url = job.get_public_report_url()
        return (
            "عملیات انجام شد ✅\n"
            f"وضعیت ارسال: {status_label}\n"
            f"ارسال موفق به *{success_count}* از {total_targets} کانال\n"
            f"تعداد توکن مصرفی: {spent:,}\n"
            f"[مشاهده تکمیلی]({report_url})"
        )
