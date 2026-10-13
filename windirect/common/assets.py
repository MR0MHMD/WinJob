from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from windirect.subscriptions.access import require_feature, require_connection
from windirect.direct.models import DirectRule
from windirect.showcases.models import Showcase
from windirect.forms.models import ConversationForm
from windirect.direct.forms import DirectRuleForm
from windirect.showcases.forms import ShowcaseForm, CardFormSet
from windirect.forms.forms import ConversationFormEditor, QuestionFormSet

TOOLS = {
    "direct": (
        DirectRule,
        DirectRuleForm,
        None,
        "دایرکت هوشمند",
        "قانون دایرکت",
        "کلمهٔ فعال‌کننده را به پاسخ متنی، ویترین یا فرم متصل کنید. قوانین به ترتیب اولویت بررسی می‌شوند.",
    ),
    "showcases": (
        Showcase,
        ShowcaseForm,
        CardFormSet,
        "ویترین‌ساز",
        "ویترین",
        "کارت‌های تصویری محصولات را بسازید؛ سپس در یک قانون دایرکت از ویترین استفاده کنید.",
    ),
    "forms": (
        ConversationForm,
        ConversationFormEditor,
        QuestionFormSet,
        "فرم‌ساز",
        "فرم",
        "سؤال‌ها را مرتب کنید؛ پاسخ‌ها مرحله‌به‌مرحله ثبت می‌شوند و خروجی اکسل دارند.",
    ),
}


def _tool(kind):
    """نوع ابزار را فقط از فهرست ثابت بخش‌های پنل می‌پذیرد."""
    if kind not in TOOLS:
        raise Http404
    model, form, formset, title, singular, intro = TOOLS[kind]
    return (
        model,
        form,
        formset,
        {
            "section": kind,
            "kind": kind,
            "heading": title,
            "singular": singular,
            "intro": intro,
            "noindex": True,
        },
    )


@login_required(login_url="accounts:login")
def asset_list(request, kind):
    """فهرست و جست‌وجوی ابزارهای حساب‌های مالک."""
    model, _, _, context = _tool(kind)
    items = model.objects.filter(connection__owner=request.user).select_related(
        "connection"
    )
    query = request.GET.get("q", "").strip()[:150]
    if query:
        items = items.filter(name__icontains=query)
    context.update(
        page_obj=Paginator(items, 12).get_page(request.GET.get("page")), query=query
    )
    return render(request, "windirect/common/assets/list.html", context)


@login_required(login_url="accounts:login")
def asset_edit(request, kind, pk=None):
    """ابزار و فرزندانش را به صورت یک تراکنش ذخیره می‌کند."""
    model, form_class, formset_class, context = _tool(kind)
    obj = (
        get_object_or_404(model, pk=pk, connection__owner=request.user)
        if pk
        else model()
    )
    feature = {"direct": "smart_direct", "showcases": "showcases", "forms": "forms"}[
        kind
    ]
    try:
        require_feature(request.user, feature)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("windirect:plans")
    form = form_class(
        request.POST if request.method == "POST" else None,
        owner=request.user,
        instance=obj,
    )
    children = (
        formset_class(
            request.POST if request.method == "POST" else None,
            instance=obj,
            prefix="items",
        )
        if formset_class
        else None
    )
    if request.method == "POST":
        valid = form.is_valid()
        children_valid = children.is_valid() if children is not None else True
        if valid:
            try:
                require_connection(form.cleaned_data["connection"], feature)
            except ValidationError as error:
                form.add_error(None, error)
                valid = False
        if valid and children_valid:
            with transaction.atomic():
                form.save()
                if children is not None:
                    children.save()
            messages.success(request, "تغییرات با موفقیت ذخیره شد.")
            return redirect("windirect:asset_list", kind=kind)
    context.update(
        form=form,
        children=children,
        obj=obj,
        child_limit=10 if kind == "showcases" else 20,
    )
    return render(request, "windirect/common/assets/editor.html", context)


@login_required(login_url="accounts:login")
@require_POST
def asset_toggle(request, kind, pk):
    """وضعیت ابزار متعلق به کاربر را تغییر می‌دهد."""
    model, _, _, _ = _tool(kind)
    with transaction.atomic():
        obj = get_object_or_404(
            model.objects.select_for_update(), pk=pk, connection__owner=request.user
        )
        if not obj.is_active:
            try:
                require_connection(
                    obj.connection,
                    {
                        "direct": "smart_direct",
                        "showcases": "showcases",
                        "forms": "forms",
                    }[kind],
                )
            except ValidationError as error:
                messages.error(request, error.messages[0])
                return redirect("windirect:plans")
        obj.is_active = not obj.is_active
        obj.save(update_fields=["is_active", "updated_at"])
    messages.success(
        request, "وضعیت تغییر کرد. فرم‌های از قبل شروع‌شده تا پایان قابل تکمیل هستند."
    )
    return redirect("windirect:asset_list", kind=kind)


@login_required(login_url="accounts:login")
def asset_delete(request, kind, pk):
    """حذف ابزار بدون سابقه را پس از نمایش صفحهٔ تأیید انجام می‌دهد."""
    model, _, _, context = _tool(kind)
    obj = get_object_or_404(model, pk=pk, connection__owner=request.user)
    if request.method == "POST":
        try:
            obj.delete()
        except ProtectedError:
            messages.error(
                request,
                "این مورد سابقه یا قانون وابسته دارد؛ برای حفظ اطلاعات، به جای حذف غیرفعالش کنید.",
            )
        else:
            messages.success(request, "مورد انتخاب‌شده حذف شد.")
        return redirect("windirect:asset_list", kind=kind)
    context["obj"] = obj
    return render(request, "windirect/common/assets/delete.html", context)
