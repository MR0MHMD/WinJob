"""مدیریت اتصال حساب‌های اینستاگرام به وین دایرکت."""
import base64
import json
import logging
import time
import urllib.parse
import requests
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
# from eventlet.green import urllib

from windirect.common.context import owner_context
from windirect.subscriptions.services import current_period
from .boxapi import request_list_posts
from .models import InstagramConnection
from .forms import InstagramConnectionForm
from .services import register_connection
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .webhook_handlers import route_webhook

logger = logging.getLogger(__name__)

# ==================== ثابت‌های Instagram ====================
INSTAGRAM_OAUTH_URL = "https://www.instagram.com/oauth/authorize"
INSTAGRAM_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
INSTAGRAM_LONG_TOKEN_URL = "https://graph.instagram.com/access_token"
INSTAGRAM_ME_URL = "https://graph.instagram.com/me"

INSTAGRAM_SCOPES = [
    "instagram_business_basic",
    "instagram_business_manage_messages",
    "instagram_business_manage_comments",
    "instagram_business_content_publish",
    "instagram_business_manage_insights",
]


def _fetch_and_save_profile_picture(connection, username):
    """
    عکس پروفایل رو از BoxAPI می‌گیره و توی سرور ذخیره می‌کنه.
    """

    boxapi_username = getattr(settings, "BOXAPI_USERNAME", "")
    boxapi_password = getattr(settings, "BOXAPI_PASSWORD", "")

    if not boxapi_username or not boxapi_password:
        logger.warning("BoxAPI credentials for web profile not configured")
        return

    # ۱. گرفتن URL عکس از BoxAPI
    try:
        auth = base64.b64encode(f"{boxapi_username}:{boxapi_password}".encode()).decode()
        response = requests.post(
            "https://boxapi.ir/api/instagram/user/get_web_profile_info",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
            },
            json={"username": username},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        pic_url = data.get("profile_pic_url_hd") or data.get("profile_pic_url")
    except Exception:
        logger.exception("خطا در دریافت URL عکس پروفایل از BoxAPI")
        return

    if not pic_url:
        return

    # ۲. دانلود عکس
    try:
        img_response = requests.get(pic_url, timeout=15)
        img_response.raise_for_status()
    except Exception:
        logger.exception("خطا در دانلود عکس پروفایل")
        return

    # ۳. ذخیره توی ImageField
    try:
        connection.profile_picture.save(
            f"{username}.jpg",
            ContentFile(img_response.content),
            save=True,
        )
    except Exception:
        logger.exception("خطا در ذخیره عکس پروفایل")


def _request_profile_via_boxapi(account_id):
    """درخواست آسنکرون پروفایل از BoxAPI؛ نتیجه از طریق Webhook میاد."""
    api_key = getattr(settings, "BOXAPI_API_KEY", "")
    base_url = getattr(settings, "BOXAPI_BASE_URL", "https://api.sendbox.chat/api/v1")

    try:
        response = requests.post(
            f"{base_url}/service/actions/get_profile",
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
            json={"account_id": account_id},
            timeout=15,
        )
        logger.warning(
            "BoxAPI get_profile request | status=%s | body=%s",
            response.status_code,
            response.text[:300],
        )
    except Exception:
        logger.exception("خطا در درخواست get_profile از BoxAPI")


def _download_and_save_profile_picture(connection, pic_url):
    """عکس رو دانلود و توی ImageField ذخیره می‌کنه."""
    try:
        response = requests.get(pic_url, timeout=15)
        response.raise_for_status()
        connection.profile_picture.save(
            f"{connection.username}.jpg",
            ContentFile(response.content),
            save=True,
        )
        logger.warning("✅ Profile pic saved for @%s", connection.username)
    except Exception:
        logger.exception("خطا در دانلود عکس پروفایل")


@login_required(login_url="accounts:login")
@require_http_methods(["GET", "POST"])
def connections(request):
    """حساب آزمایشی می‌سازد و وضعیت اتصال رسمی را شفاف نمایش می‌دهد."""
    form = InstagramConnectionForm(request.POST or None)
    open_modal = False
    prefilled_username = ""

    if request.method == "POST":
        if form.is_valid():
            connection = form.save(commit=False)
            try:
                register_connection(request.user, connection)
            except ValidationError as error:
                msg = error.messages[0] if error.messages else str(error)
                messages.error(request, msg)
                open_modal = True
                prefilled_username = form.cleaned_data.get("username", "")
            else:
                messages.success(
                    request,
                    f"حساب @{connection.username} با موفقیت ثبت شد. "
                    "هنوز اتصال رسمی به اینستاگرام برقرار نشده است.",
                )
                return redirect("windirect:connections")
        else:
            open_modal = True
            prefilled_username = request.POST.get("username", "")
            if form.errors.get("username"):
                messages.error(request, form.errors["username"][0])
            elif form.non_field_errors():
                messages.error(request, form.non_field_errors()[0])
            else:
                messages.error(request, "لطفاً خطاهای فرم را برطرف کنید.")

    owner_connections = (
        InstagramConnection.objects
        .filter(owner=request.user)
        .annotate(rule_count=Count("automations", distinct=True))
        .order_by("-created_at")
    )

    period = current_period(request.user)
    allowed_pages = int(period.capabilities.get("max_pages", 0)) if period else 0

    active_count = owner_connections.filter(
        status__in=["simulated", "connected"]
    ).count()
    disconnected_count = owner_connections.filter(status="disconnected").count()

    total_rules_count = (
            InstagramConnection.objects
            .filter(owner=request.user)
            .aggregate(total=Count("automations"))["total"] or 0
    )

    has_active_subscription = period is not None
    can_add_connection = has_active_subscription and active_count < allowed_pages

    context = owner_context(request)
    context.update({
        "form": form,
        "connections": owner_connections,
        "allowed_pages": allowed_pages,
        "has_active_subscription": has_active_subscription,
        "active_connections_count": active_count,
        "disconnected_connections_count": disconnected_count,
        "total_rules_count": total_rules_count,
        "can_add_connection": can_add_connection,
        "open_modal": open_modal,
        "prefilled_username": prefilled_username,
        "instagram_oauth_configured": bool(
            getattr(settings, "INSTAGRAM_APP_ID", "")
            and getattr(settings, "INSTAGRAM_APP_SECRET", "")
        ),
    })
    return render(request, "windirect/connections/list.html", context)


@login_required(login_url="accounts:login")
@require_POST
def connection_toggle(request, pk):
    """قطع پیج داده‌ها را حذف نمی‌کند؛ فعال‌سازی نمونه سقف اشتراک را رعایت می‌کند."""
    with transaction.atomic():
        connection = get_object_or_404(
            InstagramConnection.objects.select_for_update(), pk=pk, owner=request.user
        )
        if connection.status == "disconnected":
            if connection.instagram_user_id and not connection.instagram_user_id.startswith("sim_"):
                messages.error(
                    request, "اتصال مجدد رسمی با ورود متا در مرحلهٔ اتصال انجام می‌شود."
                )
            else:
                try:
                    register_connection(request.user, connection)
                except ValidationError as error:
                    messages.error(request, error.messages[0])
                else:
                    messages.success(request, f"حساب @{connection.username} دوباره فعال شد.")
        else:
            connection.status = "disconnected"
            connection.save(update_fields=["status", "updated_at"])
            messages.warning(
                request,
                f"حساب @{connection.username} قطع شد. قوانین آن حفظ شده‌اند.",
            )
    return redirect("windirect:connections")


# ==================== Instagram OAuth ====================

@login_required(login_url="accounts:login")
def instagram_connect(request):
    """
    کاربر را به لینک اختصاصی BoxAPI می‌فرستد.
    """

    api_key = getattr(settings, "BOXAPI_API_KEY", "")
    base_url = getattr(settings, "BOXAPI_BASE_URL", "https://api.sendbox.chat/api/v1")

    if not api_key:
        messages.error(request, "تنظیمات BoxAPI کامل نیست.")
        return redirect("windirect:connections")

    # بررسی سقف اشتراک
    period = current_period(request.user)
    if period is None:
        messages.error(request, "ابتدا دورهٔ رایگان یا اشتراک وین دایرکت را فعال کنید.")
        return redirect("windirect:plans")

    active_count = InstagramConnection.objects.filter(
        owner=request.user, status__in=["simulated", "connected"]
    ).count()
    if active_count >= int(period.capabilities["max_pages"]):
        messages.error(request, "به سقف پیج‌های اشتراک رسیده‌اید.")
        return redirect("windirect:connections")

    # ==================== دریافت لینک ورود از BoxAPI ====================
    endpoint = f"{base_url}/service/info"
    headers = {"X-Api-Key": api_key}

    logger.warning(
        "🔵 BOXAPI REQUEST | URL=%s | API-Key=%s...",
        endpoint,
        api_key[:10] if api_key else "MISSING",
    )

    try:
        response = requests.get(endpoint, headers=headers, timeout=15)

        logger.warning(
            "🟡 BOXAPI RESPONSE | status=%s | content-type=%s | body=%s",
            response.status_code,
            response.headers.get("Content-Type", "unknown"),
            response.text[:500],
        )

        response.raise_for_status()
        data = response.json()

    except requests.exceptions.HTTPError as exc:
        logger.error("BoxAPI HTTP error: %s | body=%s", exc, response.text[:500] if response else "no response")
        messages.error(request, f"خطای BoxAPI: {response.status_code}")
        return redirect("windirect:connections")
    except requests.exceptions.RequestException as exc:
        logger.exception("BoxAPI request failed: %s", exc)
        messages.error(request, "اتصال به BoxAPI برقرار نشد.")
        return redirect("windirect:connections")
    except ValueError:
        logger.exception("BoxAPI response not JSON")
        messages.error(request, "پاسخ BoxAPI نامعتبر است.")
        return redirect("windirect:connections")

    oauth_url = (
            data.get("data", {}).get("instagram_oauth_url")
            or data.get("instagram_oauth_url")
    )

    if not oauth_url:
        logger.error("BoxAPI response missing instagram_oauth_url: %s", data)
        messages.error(request, "پاسخ BoxAPI شامل لینک ورود نیست.")
        return redirect("windirect:connections")

    # اضافه کردن id برای شناسایی کاربر در بازگشت
    params = {"id": str(request.user.pk)}
    oauth_url = f"{oauth_url}&{urllib.parse.urlencode(params)}"

    logger.warning("🟢 BoxAPI redirecting to: %s", oauth_url[:200])
    return redirect(oauth_url)


@login_required(login_url="accounts:login")
def instagram_callback(request):
    """
    بازگشت از BoxAPI: پارامترهای username و account_id را دریافت می‌کند.
    """
    # لاگ برای دیباگ
    logger.warning(
        "🔔 BOXAPI CALLBACK HIT | user=%s | GET=%s",
        request.user.pk,
        dict(request.GET),
    )

    status = request.GET.get("status")
    username = request.GET.get("username")
    account_id = request.GET.get("account_id")
    user_id = request.GET.get("id")

    if status != "success" or not username or not account_id:
        messages.error(request, "اتصال به اینستاگرام ناموفق بود یا لغو شد.")
        return redirect("windirect:connections")

    # امنیت: چک کن id با user فعلی یکی باشه
    if user_id and str(user_id) != str(request.user.pk):
        logger.warning("BoxAPI callback: state mismatch (got=%s, expected=%s)", user_id, request.user.pk)
        messages.error(request, "درخواست نامعتبر است.")
        return redirect("windirect:connections")

    # چک سقف اشتراک
    period = current_period(request.user)
    if period is None:
        messages.error(request, "اشتراک فعالی برای ثبت پیج وجود ندارد.")
        return redirect("windirect:connections")

    # چک تکراری نبودن (توسط کاربر دیگه)
    duplicate = InstagramConnection.objects.filter(
        instagram_user_id=account_id
    ).exclude(owner=request.user).first()
    if duplicate:
        messages.error(request, "این حساب اینستاگرام قبلاً در سیستم ثبت شده است.")
        return redirect("windirect:connections")

    # ذخیره یا آپدیت
    connection, created = InstagramConnection.objects.update_or_create(
        owner=request.user,
        instagram_user_id=account_id,
        defaults={
            "username": username,
            "status": InstagramConnection.Status.CONNECTED,
        }
    )

    # بعد از ذخیره connection
    _request_profile_via_boxapi(account_id)

    logger.warning(
        "✅ BoxAPI connection %s: @%s (account_id=%s)",
        "created" if created else "updated",
        username,
        account_id,
    )

    messages.success(
        request,
        f"حساب @{username} با موفقیت به وین دایرکت متصل شد.",
    )
    return redirect("windirect:connections")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def instagram_webhook(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        expected_token = getattr(
            settings,
            "BOXAPI_WEBHOOK_SECRET",
            "",
        )

        if mode == "subscribe" and token == expected_token:
            return HttpResponse(challenge, content_type="text/plain")

        return HttpResponse("Forbidden", status=403)

    started = time.monotonic()

    logger.warning(
        "WEBHOOK START | method=%s | content_type=%s",
        request.method,
        request.headers.get("Content-Type", "unknown"),
    )

    try:
        body = request.body

        logger.warning(
            "WEBHOOK BODY READ | bytes=%s | elapsed=%.3fs",
            len(body),
            time.monotonic() - started,
        )

        payload = json.loads(body)

        logger.warning(
            "WEBHOOK JSON PARSED | elapsed=%.3fs",
            time.monotonic() - started,
        )

        route_started = time.monotonic()
        success = route_webhook(payload)

        logger.warning(
            "WEBHOOK ROUTE FINISHED | success=%s | "
            "route_elapsed=%.3fs | total_elapsed=%.3fs",
            success,
            time.monotonic() - route_started,
            time.monotonic() - started,
        )

    except json.JSONDecodeError:
        logger.exception("WEBHOOK INVALID JSON")

    except Exception:
        logger.exception(
            "WEBHOOK PROCESSING ERROR | elapsed=%.3fs",
            time.monotonic() - started,
        )

    response = HttpResponse("EVENT_RECEIVED", status=200)

    logger.warning(
        "WEBHOOK RESPONSE READY | elapsed=%.3fs",
        time.monotonic() - started,
    )

    return response


# ==================== لیست پست‌های پیج (AJAX) ====================

@login_required(login_url="accounts:login")
@require_POST
def instagram_posts_load(request):
    """
    شروع درخواست لیست پست‌ها از BoxAPI.
    پاسخ آسنکرون از طریق Webhook میاد.
    """

    connection_id = request.POST.get("connection_id")
    if not connection_id:
        return JsonResponse({
            "success": False,
            "message": "شناسه‌ی پیج ارسال نشده.",
        }, status=400)

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

    if connection.status != InstagramConnection.Status.CONNECTED:
        return JsonResponse({
            "success": False,
            "message": "این پیج فعال نیست.",
        }, status=400)

    account_id = connection.instagram_user_id
    cache_key = f"instagram_posts:{account_id}"

    # پاک کردن cache قبلی برای شروع تازه
    cache.delete(cache_key)

    # ثبت وضعیت "loading"
    cache.set(cache_key, {"status": "loading"}, timeout=600)

    logger.warning("📸 instagram_posts_load | @%s | account_id=%s", connection.username, account_id)

    # درخواست به BoxAPI
    success = request_list_posts(account_id, limit=12)

    if not success:
        cache.set(cache_key, {
            "status": "failed",
            "message": "درخواست به BoxAPI ناموفق بود.",
        }, timeout=600)
        return JsonResponse({
            "success": False,
            "message": "درخواست لیست پست‌ها ناموفق بود.",
        }, status=500)

    return JsonResponse({
        "success": True,
        "message": "درخواست ثبت شد. در حال دریافت پست‌ها...",
        "cache_key": cache_key,
    })


@login_required(login_url="accounts:login")
@require_http_methods(["GET"])
def instagram_posts_status(request):
    """
    بررسی وضعیت لیست پست‌ها (برای polling).
    """

    connection_id = request.GET.get("connection_id")
    if not connection_id:
        return JsonResponse({
            "success": False,
            "message": "شناسه‌ی پیج ارسال نشده.",
        }, status=400)

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

    account_id = connection.instagram_user_id
    cache_key = f"instagram_posts:{account_id}"

    cached = cache.get(cache_key)

    if not cached:
        return JsonResponse({
            "status": "not_started",
            "message": "درخواستی ثبت نشده.",
        })

    status = cached.get("status")

    if status == "loading":
        return JsonResponse({
            "status": "loading",
            "message": "در حال دریافت پست‌ها...",
        })

    if status == "failed":
        return JsonResponse({
            "status": "failed",
            "message": cached.get("message", "خطا در دریافت پست‌ها."),
        })

    if status == "ready":
        posts = cached.get("posts", [])
        logger.warning(
            "✅ instagram_posts_status ready | @%s | count=%s",
            connection.username, len(posts),
        )
        return JsonResponse({
            "status": "ready",
            "posts": posts,
            "count": len(posts),
        })

    return JsonResponse({
        "status": "unknown",
        "message": "وضعیت ناشناخته.",
    })
