from django.shortcuts import get_object_or_404, redirect
from campaigns.models import CampaignReport, Campaign
from django.contrib.auth import get_user_model
from django.views.generic import CreateView
from ..mixins import SupportRequiredMixin
from tickets.models import TicketMessage
from influencers.models import Channel
from django.urls import reverse_lazy
from django.contrib import messages
from ..forms import TicketReplyForm
from tickets.models import Ticket
from django.views import View
from campaigns.services.campaigns_notifications import (
    approve_campaign_by_admin,
    approve_influencer_report_service,
    reject_influencer_report_service,
    reject_campaign_by_admin
)

User = get_user_model()


class TicketReplyView(SupportRequiredMixin, CreateView):
    model = TicketMessage
    form_class = TicketReplyForm
    http_method_names = ['post']

    def form_valid(self, form):
        ticket = get_object_or_404(Ticket, pk=self.kwargs['pk'])

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


class ChannelApproveView(SupportRequiredMixin, View):
    def post(self, request, pk):
        channel = get_object_or_404(Channel, pk=pk)
        if channel.status == 'pending':
            channel.status = 'approved'
            channel.is_active = True
            channel.save()
            messages.success(request, f'✅ کانال "{channel.channel_name}" با موفقیت تأیید شد.')
        else:
            messages.error(request, 'این کانال قابل تأیید نیست.')
        return redirect('support:channel_detail', pk=pk)


class ChannelRejectView(SupportRequiredMixin, View):
    def post(self, request, pk):
        channel = get_object_or_404(Channel, pk=pk)
        if channel.status == 'pending':
            channel.status = 'rejected'
            channel.is_active = False
            channel.save()
            messages.warning(request, f'❌ کانال "{channel.channel_name}" رد شد.')
        else:
            messages.error(request, 'این کانال قابل رد نیست.')
        return redirect('support:channel_list')


class CampaignApproveView(SupportRequiredMixin, View):
    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk)
        approve_campaign_by_admin(campaign)
        return redirect('support:campaign_detail', pk=pk)


class CampaignRejectView(SupportRequiredMixin, View):
    def post(self, request, pk):
        campaign = get_object_or_404(Campaign, pk=pk)
        reason = request.POST["reason"]
        reject_campaign_by_admin(campaign, reason)
        return redirect('support:campaign_detail', pk=pk)


class ReportApproveView(SupportRequiredMixin, View):
    """تأیید گزارش توسط پشتیبان"""

    def post(self, request, pk):
        report = get_object_or_404(CampaignReport, pk=pk)

        if report.status == 'pending':
            try:
                approve_influencer_report_service(report)
                messages.success(request, '✅ گزارش با موفقیت تأیید شد و پرداخت انجام شد.')
            except Exception as e:
                messages.error(request, f'خطا در تأیید گزارش: {str(e)}')
        else:
            messages.error(request, 'این گزارش قابل تأیید نیست.')

        return redirect('support:report_detail', pk=pk)


class ReportRejectView(SupportRequiredMixin, View):
    """رد گزارش توسط پشتیبان"""

    def post(self, request, pk):
        report = get_object_or_404(CampaignReport, pk=pk)

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
