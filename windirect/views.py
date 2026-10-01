from django.core.exceptions import ValidationError
from .subscriptions.access import require_feature, require_connection, register_connection
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .forms import AutomationForm, InstagramConnectionForm, SimulationForm
from .models import Automation, AutomationExecution, CommentEvent, InstagramConnection
from .services import simulate_comment


def _owner_context(request):
    """داده‌های مشترک صفحات خصوصی وین دایرکت را آماده می‌کند."""
    return {"noindex": True, "connections_count": InstagramConnection.objects.filter(owner=request.user).count()}


@login_required(login_url="accounts:login")
def dashboard(request):
    """نمای کلی حساب‌ها، قوانین و آخرین اجرای آزمایشی مالک را نشان می‌دهد."""
    connections = InstagramConnection.objects.filter(owner=request.user).annotate(rule_count=Count("automations"))
    executions = AutomationExecution.objects.filter(
        automation__connection__owner=request.user,
    ).select_related("automation", "automation__connection", "event")[:5]
    context = _owner_context(request)
    context.update({
        "connections": connections,
        "rules_count": Automation.objects.filter(connection__owner=request.user).count(),
        "events_count": CommentEvent.objects.filter(connection__owner=request.user).count(),
        "executions": executions,
    })
    return render(request, "windirect/dashboard.html", context)


@login_required(login_url="accounts:login")
@require_http_methods(["GET", "POST"])
def connections(request):
    """حساب آزمایشی می‌سازد و وضعیت اتصال رسمی را شفاف نمایش می‌دهد."""
    form = InstagramConnectionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        if InstagramConnection.objects.filter(owner=request.user, username__iexact=username).exists():
            form.add_error("username", "این حساب را قبلاً ثبت کرده‌اید.")
        else:
            connection = form.save(commit=False)
            connection.owner = request.user
            connection.status = InstagramConnection.Status.SIMULATED
            connection.instagram_user_id = None
            try:
                register_connection(request.user, connection)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, "حساب آزمایشی ثبت شد؛ هنوز اتصال رسمی به اینستاگرام برقرار نشده است.")
                return redirect("windirect:connections")
    context = _owner_context(request)
    context.update({"form": form, "connections": InstagramConnection.objects.filter(owner=request.user).annotate(rule_count=Count("automations"))})
    return render(request, "windirect/connections.html", context)


@login_required(login_url="accounts:login")
def rules(request):
    """قوانین متعلق به کاربر را همراه با تعداد اجرا فهرست می‌کند."""
    queryset = Automation.objects.filter(connection__owner=request.user).select_related("connection").annotate(execution_count=Count("executions")).order_by("-created_at", "-pk")
    context = _owner_context(request)
    context.update({"rules": Paginator(queryset, 12).get_page(request.GET.get("page"))})
    return render(request, "windirect/rules.html", context)


def _rule_form(request, *, instance=None):
    """ساخت و ویرایش قانون را با اعتبارسنجی مالکیت یکسان اجرا می‌کند."""
    try:
        require_feature(request.user, 'smart_comments')
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect('windirect:plans')
    form = AutomationForm(request.POST or None, instance=instance, owner=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            require_connection(form.cleaned_data['connection'], 'smart_comments')
        except ValidationError as error:
            form.add_error(None, error)
        else:
            form.save()
            messages.success(request, "قانون با موفقیت ذخیره شد؛ ارسال واقعی هنوز فعال نیست.")
            return redirect("windirect:rules")
    context = _owner_context(request)
    context.update({"form": form, "editing": instance is not None})
    return render(request, "windirect/rule_form.html", context)


@login_required(login_url="accounts:login")
@require_http_methods(["GET", "POST"])
def rule_create(request):
    """قانون جدید برای حساب آزمایشی مالک ایجاد می‌کند."""
    return _rule_form(request)


@login_required(login_url="accounts:login")
@require_http_methods(["GET", "POST"])
def rule_edit(request, pk):
    """فقط قانون متعلق به کاربر را ویرایش می‌کند."""
    rule = get_object_or_404(Automation, pk=pk, connection__owner=request.user)
    return _rule_form(request, instance=rule)


@login_required(login_url="accounts:login")
@require_POST
def rule_toggle(request, pk):
    """فعال بودن قانون مالک را از طریق درخواست محافظت‌شده تغییر می‌دهد."""
    rule = get_object_or_404(Automation, pk=pk, connection__owner=request.user)
    if not rule.is_active:
        try:
            require_connection(rule.connection, 'smart_comments')
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect('windirect:plans')
    rule.is_active = not rule.is_active
    rule.save(update_fields=["is_active", "updated_at"])
    messages.success(request, "وضعیت قانون تغییر کرد.")
    return redirect("windirect:rules")


@login_required(login_url="accounts:login")
@require_POST
def rule_delete(request, pk):
    """قانون بدون سابقه را حذف می‌کند و لاگ‌های موجود را حفظ می‌کند."""
    rule = get_object_or_404(Automation, pk=pk, connection__owner=request.user)
    if rule.executions.exists():
        messages.error(request, "این قانون سابقهٔ اجرا دارد. برای حفظ لاگ‌ها آن را غیرفعال کنید.")
    else:
        rule.delete()
        messages.success(request, "قانون حذف شد.")
    return redirect("windirect:rules")


@login_required(login_url="accounts:login")
@require_http_methods(["GET", "POST"])
def simulation(request):
    """یک کامنت نمونه را اجرا کرده و نتیجه را بدون ارسال پیام ثبت می‌کند."""
    form = SimulationForm(request.POST or None, owner=request.user)
    result = None
    if request.method == "POST" and form.is_valid():
        try:
            event, executions = simulate_comment(
                connection=form.cleaned_data["connection"],
                comment_id=f"web-{uuid4().hex}",
                media_id=form.cleaned_data["media_id"],
                text=form.cleaned_data["text"],
            )
        except (ValueError, ValidationError) as exc:
            form.add_error(None, exc if isinstance(exc, ValidationError) else str(exc))
        else:
            result = {"event": event, "executions": executions}
    context = _owner_context(request)
    context.update({"form": form, "result": result})
    return render(request, "windirect/simulation.html", context)


@login_required(login_url="accounts:login")
def logs(request):
    """کامنت‌های نمونه و اجرای قوانین همان کاربر را به‌شکل فقط خواندنی نشان می‌دهد."""
    connections = InstagramConnection.objects.filter(owner=request.user)
    events = CommentEvent.objects.filter(connection__owner=request.user).select_related("connection").prefetch_related(
        Prefetch("executions", queryset=AutomationExecution.objects.select_related("automation")),
    )
    connection_id = request.GET.get("connection", "")
    if connection_id.isdecimal():
        events = events.filter(connection_id=connection_id)
    elif connection_id:
        connection_id = ""
    context = _owner_context(request)
    context.update({
        "connections": connections,
        "selected_connection": connection_id,
        "events": Paginator(events, 10).get_page(request.GET.get("page")),
    })
    return render(request, "windirect/logs.html", context)
