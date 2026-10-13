from django.shortcuts import get_object_or_404
from .models import ConversationForm, FormSubmission


def _submissions(request, pk):
    """فیلتر مشترک صفحهٔ پاسخ‌ها و خروجی اکسل را اعمال می‌کند."""
    form = get_object_or_404(ConversationForm, pk=pk, connection__owner=request.user)
    status = request.GET.get("status", "")
    items = form.submissions.filter(connection__owner=request.user)
    if status in FormSubmission.Status.values:
        items = items.filter(status=status)
    else:
        status = ""
    return form, items, status
