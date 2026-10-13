from windirect.common.assets import asset_list, asset_edit, asset_toggle, asset_delete

from uuid import uuid4
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from windirect.direct.models import DirectMessageEvent
from windirect.direct.forms import DirectSimulationForm
from .services import simulate_direct


@login_required(login_url="accounts:login")
def direct_simulation(request):
    """آزمایش پیوستهٔ پیام‌ها با جلوگیری از ارسال مجدد پس از تازه‌سازی."""
    selected = None
    if request.GET.get("event", "").isdigit():
        selected = get_object_or_404(
            DirectMessageEvent, pk=request.GET["event"], connection__owner=request.user
        )
    initial = {"message_id": uuid4()}
    if selected:
        initial.update(connection=selected.connection_id, sender_id=selected.sender_id)
    form = DirectSimulationForm(
        request.POST if request.method == "POST" else None,
        owner=request.user,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            event, _ = simulate_direct(
                connection=data["connection"],
                sender_id=data["sender_id"],
                message_id=str(data["message_id"]),
                text=data["text"],
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return redirect(
                reverse("windirect:direct_simulation") + f"?event={event.pk}"
            )
    history = []
    if selected:
        history = list(
            DirectMessageEvent.objects.filter(
                connection=selected.connection, sender_id=selected.sender_id
            ).select_related("rule")[:30]
        )[::-1]
    return render(
        request,
        "windirect/direct/simulation.html",
        {"form": form, "history": history, "section": "simulation", "noindex": True},
    )


@login_required(login_url="accounts:login")
def direct_logs(request):
    """گزارش پیام‌های نمونه و نتیجهٔ مسیریابی آن‌ها."""
    items = DirectMessageEvent.objects.filter(
        connection__owner=request.user
    ).select_related("connection", "rule")
    return render(
        request,
        "windirect/direct/logs.html",
        {
            "page_obj": Paginator(items, 20).get_page(request.GET.get("page")),
            "section": "direct_logs",
            "noindex": True,
        },
    )
