"""ویوهای پنل وب وین فوروارد."""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from product.forward.broadcast.forms import BroadcastSendForm
from product.forward.broadcast.models import BroadcastJob, BroadcastTarget
from product.forward.broadcast.services.dispatcher import dispatch_job


@login_required
def send_broadcast(request):
    """صفحه ارسال پیام جدید به کانال‌ها از طریق پنل وب."""
    if request.method == "POST":
        form = BroadcastSendForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            message = form.save(commit=False)
            message.user = request.user
            message.save()

            job = BroadcastJob.objects.create(message=message)
            selected_channels = form.cleaned_data["channels"]

            for channel in selected_channels:
                BroadcastTarget.objects.create(job=job, channel=channel)

            dispatch_job(job.pk)
            job.refresh_from_db()

            if job.status == BroadcastJob.Status.DONE:
                messages.success(request, f"✅ پیام با موفقیت به {job.success_count} کانال ارسال شد.")
            else:
                messages.warning(request, f"⚠️ ارسال انجام شد: {job.success_count} موفق، {job.failed_count} ناموفق.")

            return redirect("broadcast:job_detail", job_id=job.pk)
    else:
        form = BroadcastSendForm(user=request.user)

    return render(request, "product/forward/broadcast/send.html", {"form": form})


@login_required
def job_detail(request, job_id):
    """نمایش جزئیات یک جاب و وضعیت ارسال به هر کانال."""
    job = get_object_or_404(BroadcastJob, pk=job_id, message__user=request.user)
    targets = job.targets.select_related("channel").all()
    return render(request, "product/forward/broadcast/job_detail.html", {"job": job, "targets": targets})


from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

# ... کدهای قبلی ...

@method_decorator(login_required, name='dispatch')
class JobListView(ListView):
    """نمایش تاریخچه جاب‌های ارسال کاربر."""
    model = BroadcastJob
    template_name = "product/forward/broadcast/job_list.html"
    context_object_name = "jobs"
    paginate_by = 15

    def get_queryset(self):
        """فقط جاب‌های مربوط به کاربر لاگین شده را برمی‌گرداند."""
        return BroadcastJob.objects.filter(message__user=self.request.user).select_related("message").order_by("-created_at")