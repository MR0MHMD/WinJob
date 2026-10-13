"""ویوهای پنل کامنت هوشمند وین دایرکت."""

from .models import Automation, AutomationExecution, AutomationKeyword, CommentEvent, CommentReplyTemplate, MediaUpload
from windirect.subscriptions.access import require_feature, require_connection
from django.views.decorators.http import require_http_methods, require_POST
from django.shortcuts import get_object_or_404, redirect, render
from windirect.connections.models import InstagramConnection
from django.contrib.auth.decorators import login_required
from windirect.connections.boxapi import upload_file
from django.core.exceptions import ValidationError
from windirect.common.context import owner_context
from .forms import AutomationForm, SimulationForm
from django.db.models import Count, Prefetch, Q
from django.core.paginator import Paginator
from .services import simulate_comment
from django.http import JsonResponse
from django.contrib import messages
from django.db import transaction
from uuid import uuid4
import logging
import json
import os

logger = logging.getLogger(__name__)

# ==================== ثابت‌ها ====================
MAX_KEYWORDS = 3
MAX_COMMENT_REPLIES = 3


# ==================== helpers ====================
def _extract_keywords(request):
    """لیست کلیدواژه‌ها را از POST استخراج و پاک‌سازی می‌کند."""
    raw = request.POST.getlist("keywords[]")
    keywords = []
    seen = set()
    for value in raw:
        value = (value or "").strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        keywords.append(value)
        if len(keywords) >= MAX_KEYWORDS:
            break
    return keywords


def _extract_comment_replies(request):
    """لیست متن‌های پاسخ کامنت را از POST استخراج می‌کند."""
    raw = request.POST.getlist("comment_replies[]")
    replies = []
    for value in raw:
        value = (value or "").strip()
        if not value:
            continue
        replies.append(value)
        if len(replies) >= MAX_COMMENT_REPLIES:
            break
    return replies


def _validate_keywords(keywords):
    """اعتبارسنجی لیست کلیدواژه‌ها."""
    if not keywords:
        raise ValidationError("حداقل یک فعال‌ساز وارد کنید.")
    if len(keywords) > MAX_KEYWORDS:
        raise ValidationError(f"حداکثر {MAX_KEYWORDS} فعال‌ساز مجاز است.")


def _validate_comment_replies(replies, reply_channel):
    """اعتبارسنجی لیست پاسخ‌های کامنت."""
    if reply_channel != Automation.ReplyChannel.COMMENT:
        return
    if not replies:
        raise ValidationError("حداقل یک متن پاسخ کامنت وارد کنید.")


def _save_keywords(automation, keywords):
    """کلیدواژه‌ها را به‌صورت کامل (حذف و بازسازی) ذخیره می‌کند."""
    automation.keywords.all().delete()
    AutomationKeyword.objects.bulk_create(
        [AutomationKeyword(automation=automation, value=v) for v in keywords]
    )


def _save_comment_replies(automation, replies, reply_channel):
    """متن‌های پاسخ کامنت را به‌صورت کامل ذخیره می‌کند."""
    automation.comment_replies.all().delete()
    if reply_channel != Automation.ReplyChannel.COMMENT:
        return
    CommentReplyTemplate.objects.bulk_create(
        [CommentReplyTemplate(automation=automation, text=t) for t in replies]
    )


def _rule_form(request, *, instance=None):
    """منطق مشترک ساخت و ویرایش کامنت هوشمند."""
    # ==================== دسترسی ====================
    try:
        require_feature(request.user, "smart_comments")
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect("windirect:plans")

    # ==================== حساب‌های موجود (آزمایشی + متصل) ====================
    owner_connections = InstagramConnection.objects.filter(
        owner=request.user,
        status__in=[
            InstagramConnection.Status.SIMULATED,
            InstagramConnection.Status.CONNECTED,
        ],
    )

    if not owner_connections.exists():
        messages.warning(
            request, "برای ساخت کامنت هوشمند، ابتدا یک حساب اینستاگرام ثبت یا متصل کنید."
        )
        return redirect("windirect:connections")

    # ==================== initial data ====================
    initial_data = {}
    if not instance:
        initial_data["reply_channel"] = Automation.ReplyChannel.DIRECT
        initial_data["target_type"] = Automation.TargetType.POST
        initial_data["match_type"] = Automation.MatchType.CONTAINS
        initial_data["direct_message_kind"] = Automation.DirectKind.TEXT

    form = AutomationForm(
        request.POST or None,
        request.FILES or None,
        instance=instance,
        owner=request.user,
        initial=initial_data,
    )

    # ==================== پردازش POST ====================
    if request.method == "POST":
        keywords = _extract_keywords(request)
        replies = _extract_comment_replies(request)
        media_upload_id = request.POST.get("media_upload_id", "").strip()

        if form.is_valid():
            try:
                _validate_keywords(keywords)
                _validate_comment_replies(replies, form.cleaned_data["reply_channel"])
                require_connection(form.cleaned_data["connection"], "smart_comments")
            except ValidationError as error:
                form.add_error(None, error)
            else:
                with transaction.atomic():
                    automation = form.save(commit=False)
                    # is_active
                    if not automation.pk:
                        automation.is_active = True
                    else:
                        automation.is_active = instance.is_active if instance else True

                    # ==================== اتصال MediaUpload ====================
                    media_upload = None
                    if media_upload_id and media_upload_id.isdigit():
                        media_upload = MediaUpload.objects.filter(
                            pk=int(media_upload_id),
                            status=MediaUpload.Status.PENDING,
                        ).first()

                        if media_upload:
                            logger.warning(
                                "📎 Attaching MediaUpload to Automation | "
                                "media_upload_id=%s | automation_id=%s",
                                media_upload.pk, automation.pk or "new",
                            )
                        else:
                            logger.warning(
                                "⚠️ MediaUpload not found or not pending | "
                                "media_upload_id=%s",
                                media_upload_id,
                            )

                    # چک: اگه kind غیر متن و media_upload نداریم → خطا
                    if automation.direct_message_kind in (
                        Automation.DirectKind.AUDIO,
                        Automation.DirectKind.IMAGE,
                        Automation.DirectKind.VIDEO,
                    ):
                        # اگه نه media_upload جدید داریم، نه فایل قبلی روی instance
                        existing_upload = instance.media_upload if instance else None
                        if not media_upload and not existing_upload:
                            form.add_error(
                                "media_upload",
                                "فایل مدیای دایرکت را انتخاب کنید.",
                            )
                            raise ValidationError("media_upload required")

                    # اتصال
                    if media_upload:
                        automation.media_upload = media_upload

                    automation.save()

                    # ==================== آپدیت MediaUpload ====================
                    if media_upload:
                        media_upload.mark_attached()

                    # ==================== ذخیره‌ی keywords و replies ====================
                    _save_keywords(automation, keywords)
                    _save_comment_replies(
                        automation, replies, automation.reply_channel
                    )

                messages.success(request, "کامنت هوشمند با موفقیت ذخیره شد.")
                return redirect("windirect:rules")

    # ==================== آماده‌سازی داده برای تمپلیت ====================
    editing = instance is not None
    existing_keywords = (
        list(instance.keywords.values_list("value", flat=True)) if editing else []
    )
    existing_replies = (
        list(instance.comment_replies.values_list("text", flat=True))
        if editing
        else []
    )

    # اگه POST خطا داشت، اولویت با مقادیر POST
    if request.method == "POST":
        existing_keywords = _extract_keywords(request)
        existing_replies = _extract_comment_replies(request)

    # ==================== داده‌ی media_upload فعلی ====================
    existing_media = None
    if editing and instance.media_upload:
        existing_media = {
            "id": instance.media_upload.pk,
            "url": instance.media_upload.boxapi_url,
            "file_id": instance.media_upload.boxapi_file_id,
            "name": instance.media_upload.file_name,
            "size": instance.media_upload.file_size,
            "size_display": instance.media_upload.get_size_display(),
            "kind": instance.media_upload.file_kind,
        }

    context = owner_context(request)
    context.update(
        {
            "form": form,
            "editing": editing,
            "instance": instance,
            "existing_keywords": json.dumps(existing_keywords, ensure_ascii=False),
            "existing_replies": json.dumps(existing_replies, ensure_ascii=False),
            "max_keywords": MAX_KEYWORDS,
            "max_replies": MAX_COMMENT_REPLIES,
            "has_connections": True,
            "existing_media": json.dumps(existing_media, ensure_ascii=False) if existing_media else "null",
        }
    )
    return render(request, "windirect/comments/rule_form.html", context)


# ==================== لیست قوانین ====================
@login_required()
def rules(request):
    """کامنت‌های هوشمند متعلق به کاربر را با فیلترها فهرست می‌کند."""
    base_queryset = Automation.objects.filter(connection__owner=request.user)

    # ==================== آمار کلی (بدون فیلتر) ====================
    stats = base_queryset.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        comment=Count("id", filter=Q(reply_channel=Automation.ReplyChannel.COMMENT)),
        direct=Count("id", filter=Q(reply_channel=Automation.ReplyChannel.DIRECT)),
    )

    # ==================== queryset اصلی ====================
    queryset = (
        base_queryset
        .select_related("connection")
        .prefetch_related("keywords", "comment_replies")
        .annotate(execution_count=Count("executions", distinct=True))
        .order_by("-created_at", "-pk")
    )

    # ==================== فیلترها ====================
    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(connection__username__icontains=q)
            | Q(keywords__value__icontains=q)
        ).distinct()

    target = request.GET.get("target", "")
    if target in (Automation.TargetType.POST, Automation.TargetType.LIVE):
        queryset = queryset.filter(target_type=target)
    else:
        target = ""

    channel = request.GET.get("channel", "")
    if channel in (Automation.ReplyChannel.COMMENT, Automation.ReplyChannel.DIRECT):
        queryset = queryset.filter(reply_channel=channel)
    else:
        channel = ""

    connection_id = request.GET.get("connection", "")
    if connection_id.isdecimal():
        queryset = queryset.filter(connection_id=connection_id)
    else:
        connection_id = ""

    status = request.GET.get("status", "")
    if status == "active":
        queryset = queryset.filter(is_active=True)
    elif status == "inactive":
        queryset = queryset.filter(is_active=False)
    else:
        status = ""

    connections = InstagramConnection.objects.filter(owner=request.user)

    # ==================== querystring برای حفظ فیلترها ====================
    query_params = request.GET.copy()
    query_params.pop("page", None)
    querystring = query_params.urlencode()

    # ==================== ساخت لیست فیلترهای فعال ====================
    active_filters = []
    if q:
        active_filters.append({"key": "q", "label": f'جستجو: "{q}"', "icon": "search", "value": q})
    if target:
        label = "پست" if target == "post" else "لایو"
        icon = "image" if target == "post" else "broadcast"
        active_filters.append({"key": "target", "label": label, "icon": icon, "value": target})
    if channel:
        label = "کامنت" if channel == "comment" else "دایرکت"
        icon = "chat-left-text" if channel == "comment" else "chat-dots"
        active_filters.append({"key": "channel", "label": label, "icon": icon, "value": channel})
    if connection_id:
        conn_obj = connections.filter(pk=connection_id).first()
        if conn_obj:
            active_filters.append({
                "key": "connection",
                "label": f"@{conn_obj.username}",
                "icon": "instagram",
                "value": connection_id,
            })
    if status:
        label = "فعال" if status == "active" else "غیرفعال"
        icon = "check-circle" if status == "active" else "pause-circle"
        active_filters.append({"key": "status", "label": label, "icon": icon, "value": status})

    context = owner_context(request)
    context.update(
        {
            "rules": Paginator(queryset, 12).get_page(request.GET.get("page")),
            "connections": connections,
            "q": q,
            "selected_target": target,
            "selected_channel": channel,
            "selected_connection": connection_id,
            "selected_status": status,
            "total_count": stats["total"] or 0,
            "active_count": stats["active"] or 0,
            "comment_count": stats["comment"] or 0,
            "direct_count": stats["direct"] or 0,
            "has_filters": bool(active_filters),
            "active_filters": active_filters,
            "querystring": querystring,
        }
    )
    return render(request, "windirect/comments/rules.html", context)


@login_required()
def rule_create(request):
    """ساخت کامنت هوشمند جدید."""
    return _rule_form(request)


@login_required()
def rule_edit(request, pk):
    """ویرایش کامنت هوشمند متعلق به کاربر."""
    rule = get_object_or_404(
        Automation.objects.prefetch_related("keywords", "comment_replies"),
        pk=pk,
        connection__owner=request.user,
    )
    return _rule_form(request, instance=rule)


# ==================== toggle و delete ====================
@login_required()
@require_POST
def rule_toggle(request, pk):
    """وضعیت فعال/غیرفعال کامنت هوشمند را تغییر می‌دهد."""
    rule = get_object_or_404(Automation, pk=pk, connection__owner=request.user)
    if not rule.is_active:
        try:
            require_connection(rule.connection, "smart_comments")
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect("windirect:plans")
    rule.is_active = not rule.is_active
    rule.save(update_fields=["is_active", "updated_at"])
    messages.success(request, "وضعیت کامنت هوشمند تغییر کرد.")
    return redirect("windirect:rules")


@login_required()
@require_POST
def rule_delete(request, pk):
    """کامنت هوشمند بدون سابقه را حذف می‌کند."""
    rule = get_object_or_404(Automation, pk=pk, connection__owner=request.user)
    if rule.executions.exists():
        messages.error(
            request,
            "این کامنت هوشمند سابقهٔ اجرا دارد. برای حفظ لاگ‌ها آن را غیرفعال کنید.",
        )
    else:
        rule.delete()
        messages.success(request, "کامنت هوشمند حذف شد.")
    return redirect("windirect:rules")


# ==================== شبیه‌سازی ====================
@login_required()
def simulation(request):
    """یک کامنت نمونه را اجرا کرده و نتیجه را ثبت می‌کند."""
    form = SimulationForm(request.POST or None, owner=request.user)
    result = None

    if request.method == "POST" and form.is_valid():
        try:
            event, executions = simulate_comment(
                connection=form.cleaned_data["connection"],
                comment_id=f"web-{uuid4().hex}",
                media_id=form.cleaned_data["media_id"],
                text=form.cleaned_data["text"],
                assume_followed=form.cleaned_data.get("assume_followed", False),
            )
        except (ValueError, ValidationError) as exc:
            form.add_error(
                None, exc if isinstance(exc, ValidationError) else str(exc)
            )
        else:
            result = {"event": event, "executions": executions}

    context = owner_context(request)
    context.update({"form": form, "result": result})
    return render(request, "windirect/comments/simulation.html", context)


# ==================== لاگ‌ها ====================
@login_required()
def logs(request):
    """کامنت‌های نمونه و اجرای قوانین کاربر را نمایش می‌دهد."""
    base_queryset = CommentEvent.objects.filter(connection__owner=request.user)

    # ==================== آمار کلی ====================
    executions_base = AutomationExecution.objects.filter(
        automation__connection__owner=request.user
    )
    stats = executions_base.aggregate(
        total=Count("id"),
        simulated=Count("id", filter=Q(status=AutomationExecution.Status.SIMULATED)),
        sent=Count("id", filter=Q(status=AutomationExecution.Status.SENT)),
        failed=Count("id", filter=Q(status=AutomationExecution.Status.FAILED)),
    )

    # ==================== queryset اصلی ====================
    events = (
        base_queryset
        .select_related("connection")
        .prefetch_related(
            Prefetch(
                "executions",
                queryset=AutomationExecution.objects
                .select_related("automation", "automation__connection")
                .order_by("-created_at"),
            ),
        )
        .order_by("-created_at")
    )

    # ==================== فیلترها ====================
    q = request.GET.get("q", "").strip()
    if q:
        events = events.filter(
            Q(text__icontains=q)
            | Q(connection__username__icontains=q)
            | Q(media_id__icontains=q)
        )

    connection_id = request.GET.get("connection", "")
    if connection_id.isdecimal():
        events = events.filter(connection_id=connection_id)
    else:
        connection_id = ""

    status = request.GET.get("status", "")
    if status in (
            AutomationExecution.Status.SIMULATED,
            AutomationExecution.Status.SENT,
            AutomationExecution.Status.FAILED,
            AutomationExecution.Status.FOLLOW_REQUIRED,
    ):
        events = events.filter(executions__status=status).distinct()
    else:
        status = ""

    connections = InstagramConnection.objects.filter(owner=request.user)

    # ==================== querystring ====================
    query_params = request.GET.copy()
    query_params.pop("page", None)
    querystring = query_params.urlencode()

    # ==================== فیلترهای فعال ====================
    active_filters = []
    if q:
        active_filters.append({"key": "q", "label": f'جستجو: "{q}"', "icon": "search", "value": q})
    if connection_id:
        conn_obj = connections.filter(pk=connection_id).first()
        if conn_obj:
            active_filters.append({
                "key": "connection",
                "label": f"@{conn_obj.username}",
                "icon": "instagram",
                "value": connection_id,
            })
    if status:
        status_labels = {
            AutomationExecution.Status.SIMULATED: "شبیه‌سازی شد",
            AutomationExecution.Status.SENT: "ارسال شد",
            AutomationExecution.Status.FAILED: "ناموفق",
            AutomationExecution.Status.FOLLOW_REQUIRED: "فالو اجباری",
        }
        active_filters.append({
            "key": "status",
            "label": status_labels.get(status, status),
            "icon": "check-circle",
            "value": status,
        })

    context = owner_context(request)
    context.update(
        {
            "connections": connections,
            "events": Paginator(events, 10).get_page(request.GET.get("page")),
            "q": q,
            "selected_connection": connection_id,
            "selected_status": status,
            "total_count": stats["total"] or 0,
            "simulated_count": stats["simulated"] or 0,
            "sent_count": stats["sent"] or 0,
            "failed_count": stats["failed"] or 0,
            "has_filters": bool(active_filters),
            "active_filters": active_filters,
            "querystring": querystring,
        }
    )
    return render(request, "windirect/comments/logs.html", context)


# ==================== آپلود مدیا به BoxAPI ====================
@login_required()
@require_POST
def upload_media(request):
    """
    آپلود فایل مدیا به BoxAPI.

    این ویو با AJAX صدا زده میشه و:
    1. فایل رو از request می‌گیره
    2. حجم و فرمت رو چک می‌کنه
    3. فایل رو به BoxAPI آپلود می‌کنه
    4. یه MediaUpload با status=pending می‌سازه
    5. URL و file_id رو برمی‌گردونه
    """

    # ==================== استخراج پارامترها ====================
    connection_id = request.POST.get("connection_id")
    kind = request.POST.get("kind")  # audio, image, video
    uploaded_file = request.FILES.get("file")

    logger.warning(
        "📤 upload_media START | user=%s | connection_id=%s | kind=%s | "
        "file=%s | size=%s",
        request.user.pk, connection_id, kind,
        getattr(uploaded_file, "name", "?"),
        getattr(uploaded_file, "size", "?"),
    )

    # ==================== اعتبارسنجی اولیه ====================
    if not connection_id:
        return JsonResponse({
            "success": False,
            "message": "شناسه‌ی پیج ارسال نشده.",
        }, status=400)

    if kind not in ("audio", "image", "video"):
        return JsonResponse({
            "success": False,
            "message": "نوع فایل نامعتبر است.",
        }, status=400)

    if not uploaded_file:
        return JsonResponse({
            "success": False,
            "message": "فایلی ارسال نشده.",
        }, status=400)

    # ==================== پیدا کردن connection ====================
    connection = get_object_or_404(
        InstagramConnection,
        pk=connection_id,
        owner=request.user,
    )

    if not connection.instagram_user_id:
        return JsonResponse({
            "success": False,
            "message": "این پیج به اینستاگرام متصل نیست.",
        }, status=400)

    # ==================== چک حجم و فرمت ====================
    file_size = uploaded_file.size
    file_ext = os.path.splitext(uploaded_file.name)[1].lower()

    # محدودیت حجم (بایت)
    MAX_SIZES = {
        "audio": 25 * 1024 * 1024,  # 25 MB
        "image": 8 * 1024 * 1024,  # 8 MB
        "video": 25 * 1024 * 1024,  # 25 MB
    }
    max_size = MAX_SIZES[kind]

    if file_size > max_size:
        max_mb = max_size // (1024 * 1024)
        logger.warning(
            "❌ upload_media: file too large | size=%s | max=%s",
            file_size, max_size,
        )
        return JsonResponse({
            "success": False,
            "message": f"حجم فایل بیش از حد مجاز است (حداکثر {max_mb} مگابایت).",
        }, status=400)

    # محدودیت فرمت
    ALLOWED_EXTENSIONS = {
        "audio": [".aac", ".m4a", ".wav", ".mp4"],
        "image": [".png", ".jpg", ".jpeg"],
        "video": [".mp4", ".ogg", ".avi", ".mov", ".webm"],
    }
    allowed = ALLOWED_EXTENSIONS[kind]

    if file_ext not in allowed:
        logger.warning(
            "❌ upload_media: invalid extension | ext=%s | allowed=%s",
            file_ext, allowed,
        )
        return JsonResponse({
            "success": False,
            "message": f"فرمت فایل مجاز نیست. فرمت‌های مجاز: {', '.join(allowed)}",
        }, status=400)

    # ==================== آپلود به BoxAPI ====================
    username = connection.username

    # MIME type
    if file_ext == ".png":
        mime = "image/png"
    elif file_ext in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif file_ext == ".m4a":
        mime = "audio/m4a"
    elif file_ext == ".wav":
        mime = "audio/wav"
    elif file_ext == ".aac":
        mime = "audio/aac"
    elif file_ext == ".mp4" and kind == "audio":
        mime = "audio/mp4"
    elif file_ext == ".mp4" and kind == "video":
        mime = "video/mp4"
    elif file_ext == ".mov":
        mime = "video/quicktime"
    elif file_ext == ".avi":
        mime = "video/x-msvideo"
    elif file_ext == ".webm":
        mime = "video/webm"
    elif file_ext == ".ogg":
        mime = "video/ogg"
    else:
        mime = "application/octet-stream"

    result = upload_file(
        username=username,
        file_obj=uploaded_file,
        file_type=mime,
    )

    if not result.get("success"):
        logger.error(
            "❌ upload_media: BoxAPI upload failed | result=%s",
            result.get("raw"),
        )
        return JsonResponse({
            "success": False,
            "message": "آپلود فایل به BoxAPI ناموفق بود. لطفاً دوباره تلاش کنید.",
        }, status=500)

    file_id = result.get("file_id")
    file_url = result.get("url")

    if not file_id or not file_url:
        logger.error(
            "❌ upload_media: BoxAPI returned no file_id/url | file_id=%s | url=%s",
            file_id, file_url,
        )
        return JsonResponse({
            "success": False,
            "message": "پاسخ BoxAPI نامعتبر است.",
        }, status=500)

    # ==================== ساخت MediaUpload ====================
    media_upload = MediaUpload.objects.create(
        boxapi_file_id=file_id,
        boxapi_url=file_url,
        file_name=uploaded_file.name,
        file_size=file_size,
        file_kind=kind,
        status=MediaUpload.Status.PENDING,
    )

    logger.warning(
        "✅ upload_media DONE | media_upload_id=%s | file_id=%s | url=%s",
        media_upload.pk, file_id, file_url,
    )

    return JsonResponse({
        "success": True,
        "media_upload_id": media_upload.pk,
        "url": file_url,
        "file_id": file_id,
        "file_name": uploaded_file.name,
        "file_size": file_size,
        "file_size_display": media_upload.get_size_display(),
    })
