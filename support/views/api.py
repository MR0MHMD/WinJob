# support/views/api.py

"""
API Views پنل Support

اکشن‌های مختلف (تأیید، رد، پاسخ) با کنترل دسترسی.
اگه کاربر به آبجکت دسترسی نداشت، 404 می‌گیره.
"""

from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import get_user_model
from django.views.generic import CreateView
from django.views import View
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q

from ..mixins import (
    BaseSupportMixin,
    PublishManagerRequiredMixin,
)
from ..forms import TicketReplyForm
from campaigns.models import CampaignReport, Campaign
from tickets.models import TicketMessage, Ticket
from influencers.models import Channel
from campaigns.services.campaigns_notifications import (
    approve_campaign_by_admin,
    approve_influencer_report_service,
    reject_influencer_report_service,
    reject_campaign_by_admin,
)

User = get_user_model()


# ============================================================
#  تابع کمکی برای چک دسترسی Regional به آبجکت
# ============================================================
def check_regional_access(request, province):
    """
    چک می‌کنه کاربر به این استان دسترسی داره یا نه.
    اگه Regional Manager باشه و استان فرق کنه → 404 می‌ده.
    """
    user = request.user
    if user.is_regional_manager and user.province_id:
        if province is None or province.id != user.province_id:
            from django.http import Http404
            raise Http404("این آبجکت برای شما وجود ندارد.")


# ============================================================
#                    Ticket Reply
# ============================================================
class TicketReplyView(BaseSupportMixin, CreateView):
    """
    پاسخ به تیکت

    دسترسی: همه نقش‌ها
    فیلتر Regional: فقط تیکت استان خودش
    """
    model = TicketMessage
    form_class = TicketReplyForm
    http_method_names = ['post']

    def form_valid(self, form):
        ticket = get_object_or_404(Ticket, pk=self.kwargs['pk'])

        # ========== چک دسترسی Regional ==========
        check_regional_access(self.request, ticket.user.province)

        if ticket.status == Ticket.Status.CLOSED:
            messages.error(self.request, 'این تیکت بسته شده است و امکان پاسخ وجود ندارد.')
            return redirect('support:ticket_detail', pk=ticket.pk)

        form.instance.ticket = ticket
        form.instance.sender = self.request.user
        form.instance.is_admin_reply = True

        if ticket.status in [Ticket.Status.WAITING_ADMIN, Ticket.Status.IN_PROGRESS]:
            ticket.status = Ticket.Status.WAITING_USER
            ticket.save()

        messages.success(self.request, 'پاسخ شما با موفقیت ثبت شد.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('support:ticket_detail', args=[self.kwargs['pk']])


# ============================================================
#                  Channel Approve
# ============================================================
class ChannelApproveView(PublishManagerRequiredMixin, View):
    """
    تأیید کانال

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: فقط کانال استان خودش
    """

    def post(self, request, pk):
        channel = get_object_or_404(Channel, pk=pk)

        # ========== چک دسترسی Regional ==========
        check_regional_access(request, channel.province)

        if channel.status == 'pending':
            channel.status = 'approved'
            channel.is_active = True
            channel.save()
            messages.success(
                request,
                f'✅ کانال "{channel.channel_name}" با موفقیت تأیید شد.'
            )
        else:
            messages.error(request, 'این کانال قابل تأیید نیست.')

        return redirect('support:channel_detail', pk=pk)


# ============================================================
#                   Channel Reject
# ============================================================
class ChannelRejectView(PublishManagerRequiredMixin, View):
    """
    رد کانال

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: فقط کانال استان خودش
    """

    def post(self, request, pk):
        channel = get_object_or_404(Channel, pk=pk)

        # ========== چک دسترسی Regional ==========
        check_regional_access(request, channel.province)

        if channel.status == 'pending':
            channel.status = 'rejected'
            channel.is_active = False
            channel.save()
            messages.warning(
                request,
                f'❌ کانال "{channel.channel_name}" رد شد.'
            )
        else:
            messages.error(request, 'این کانال قابل رد نیست.')

        return redirect('support:channel_list')


# ============================================================
#                  Campaign Approve
# ============================================================
class CampaignApproveView(PublishManagerRequiredMixin, View):
    """
    تأیید کمپین

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: فقط کمپین استان خودش
    """

    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk)

        # ========== چک دسترسی Regional ==========
        check_regional_access(request, campaign.advertiser.user.province)

        approve_campaign_by_admin(campaign)
        messages.success(request, f'✅ کمپین "{campaign.name}" تأیید شد.')

        return redirect('support:campaign_detail', pk=pk)


# ============================================================
#                  Campaign Reject
# ============================================================
class CampaignRejectView(PublishManagerRequiredMixin, View):
    """
    رد کمپین

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: فقط کمپین استان خودش
    """

    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk)

        # ========== چک دسترسی Regional ==========
        check_regional_access(request, campaign.advertiser.user.province)

        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'دلیل رد کمپین الزامی است.')
            return redirect('support:campaign_detail', pk=pk)

        reject_campaign_by_admin(campaign, reason)
        messages.warning(request, f'❌ کمپین "{campaign.name}" رد شد.')

        return redirect('support:campaign_detail', pk=pk)


# ============================================================
#                  Report Approve
# ============================================================
class ReportApproveView(PublishManagerRequiredMixin, View):
    """
    تأیید گزارش ناشر

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: فقط گزارش استان خودش
    """

    def post(self, request, pk):
        report = get_object_or_404(CampaignReport, pk=pk)

        # ========== چک دسترسی Regional ==========
        channel_province = report.campaign_influencer.channel.province
        check_regional_access(request, channel_province)

        if report.status == 'pending':
            try:
                approve_influencer_report_service(report)
                messages.success(
                    request,
                    '✅ گزارش با موفقیت تأیید شد و پرداخت انجام شد.'
                )
            except Exception as e:
                messages.error(request, f'خطا در تأیید گزارش: {str(e)}')
        else:
            messages.error(request, 'این گزارش قابل تأیید نیست.')

        return redirect('support:report_detail', pk=pk)


# ============================================================
#                  Report Reject
# ============================================================
class ReportRejectView(PublishManagerRequiredMixin, View):
    """
    رد گزارش ناشر

    دسترسی: CEO + Dev + Publish Manager
    فیلتر Regional: فقط گزارش استان خودش
    """

    def post(self, request, pk):
        report = get_object_or_404(CampaignReport, pk=pk)

        # ========== چک دسترسی Regional ==========
        channel_province = report.campaign_influencer.channel.province
        check_regional_access(request, channel_province)

        if report.status == 'pending':
            reason = request.POST.get('reason', '').strip()
            if not reason:
                reason = 'رد شده توسط پشتیبانی'

            try:
                reject_influencer_report_service(report, reason=reason)
                messages.success(request, '✅ گزارش با موفقیت رد شد.')
            except Exception as e:
                messages.error(request, f'خطا در رد گزارش: {str(e)}')
        else:
            messages.error(request, 'این گزارش قابل رد نیست.')

        return redirect('support:report_detail', pk=pk)
