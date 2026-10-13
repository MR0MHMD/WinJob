from windirect.common.assets import asset_list, asset_edit, asset_toggle, asset_delete

from .queries import _submissions
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from .models import ConversationForm, FormSubmission
from .exports import export_submissions


@login_required(login_url="accounts:login")
def submissions(request, pk):
    """نمایش پاسخ‌نامه‌های کامل، ناقص و لغوشدهٔ فرم."""
    form, items, status = _submissions(request, pk)
    return render(
        request,
        "windirect/forms/submissions.html",
        {
            "obj": form,
            "page_obj": Paginator(items, 20).get_page(request.GET.get("page")),
            "status": status,
            "statuses": FormSubmission.Status.choices,
            "section": "forms",
            "noindex": True,
        },
    )


@login_required(login_url="accounts:login")
def submission_detail(request, pk):
    """سؤال‌های زمان شروع فرم را کنار پاسخ‌های ثبت‌شده نمایش می‌دهد."""
    obj = get_object_or_404(
        FormSubmission.objects.select_related("form"),
        pk=pk,
        connection__owner=request.user,
    )
    rows = [
        {
            "prompt": q["prompt"],
            "answer": obj.answers[i] if i < len(obj.answers) else "بدون پاسخ",
        }
        for i, q in enumerate(obj.schema["questions"])
    ]
    return render(
        request,
        "windirect/forms/submission_detail.html",
        {"obj": obj, "rows": rows, "section": "forms", "noindex": True},
    )
