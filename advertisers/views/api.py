from content_team.models import ContentOrder, ContentDeliveryFile
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages


@login_required
def delete_content_order(request, order_id):
    """حذف سفارش پیش‌نویس (فقط برای مستقل)"""
    if request.method != 'POST':
        return redirect('advertisers:content_orders_list')

    order = get_object_or_404(
        ContentOrder,
        id=order_id,
        standalone_user=request.user,
        is_standalone=True,
        status=ContentOrder.Status.DRAFT
    )

    order.delete()
    messages.success(request, '✅ سفارش پیش‌نویس با موفقیت حذف شد.')
    return redirect('advertisers:content_orders_list')


@login_required
def select_multi_choice_option(request):
    """
    انتخاب گزینه نهایی توسط تبلیغ‌دهنده در سفارش‌های multi_choice کمپینی

    این endpoint فقط برای سفارش‌های کمپینی با delivery_type='multi_choice' کار می‌کنه.
    برای سفارش‌های مستقل، کاربر از final_accept_order استفاده می‌کنه.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    # ============================================================
    # ۱. دریافت و اعتبارسنجی ورودی
    # ============================================================
    delivery_file_id = request.POST.get('delivery_file_id')
    if not delivery_file_id:
        return JsonResponse({'error': 'شناسه فایل یافت نشد'}, status=400)

    try:
        # فایل باید:
        # - از نوع option باشه
        # - متعلق به سفارش کمپینی همین کاربر باشه
        delivery_file = ContentDeliveryFile.objects.select_related(
            'delivery__order__campaign__advertiser',
            'delivery__order__plan',
        ).get(
            id=delivery_file_id,
            delivery__order__campaign__advertiser=request.user.advertiser_profile,
            is_option=True,
        )
    except ContentDeliveryFile.DoesNotExist:
        return JsonResponse({'error': 'فایل مورد نظر یافت نشد یا دسترسی ندارید'}, status=404)

    order = delivery_file.delivery.order

    # ============================================================
    # ۲. اعتبارسنجی: سفارش باید multi_choice و done باشه
    # ============================================================
    if not order.plan or order.plan.delivery_type != 'multi_choice':
        return JsonResponse({
            'error': 'این سفارش از نوع انتخاب چندگزینه‌ای نیست.'
        }, status=400)

    if order.status != ContentOrder.Status.DONE:
        return JsonResponse({
            'error': f'این سفارش در وضعیت «{order.get_status_display()}» است و قابل تأیید نیست.'
        }, status=400)

    if not delivery_file.file:
        return JsonResponse({'error': 'فایل مورد نظر وجود ندارد'}, status=400)

    # ============================================================
    # ۳. ریست کردن انتخاب‌های قبلی (اگه کاربر قبلاً یکی رو انتخاب کرده بود)
    # ============================================================
    # فقط اگه هنوز فایل انتخاب شده‌ای وجود داره، ریست می‌کنیم
    # (چون ممکنه کاربر نظرش عوض شده باشه، قبل از تأیید نهایی)
    if order.has_selected_file():
        ContentDeliveryFile.objects.filter(
            delivery__order=order,
            is_selected=True
        ).update(is_selected=False)

    # ============================================================
    # ۴. صدا زدن سرویس واحد نهایی‌سازی
    # ============================================================
    from campaigns.services.campaigns_notifications import finalize_content_order

    result = finalize_content_order(order, selected_file=delivery_file)

    # ============================================================
    # ۵. بازگشت پاسخ
    # ============================================================
    if not result['success']:
        return JsonResponse({'error': result['message']}, status=400)

    return JsonResponse({
        'success': True,
        'message': f'گزینه {delivery_file.option_number} با موفقیت انتخاب و سفارش تأیید شد.',
        'option_number': delivery_file.option_number,
        'paid_amount': result['paid_amount'],
        'members_count': result['members_count'],
        'is_final_accepted': True,
    })


@login_required
def request_revision(request, order_id):
    """
    درخواست ویرایش سفارش توسط تبلیغ دهنده
    پشتیبانی از کمپین و سفارش مستقل
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    order = None

    # تلاش ۱: سفارش مستقل
    order = ContentOrder.objects.filter(
        id=order_id,
        standalone_user=request.user,
        is_standalone=True
    ).first()

    # تلاش ۲: سفارش کمپینی
    if not order and hasattr(request.user, 'advertiser_profile'):
        order = ContentOrder.objects.filter(
            id=order_id,
            campaign__advertiser=request.user.advertiser_profile
        ).first()

    if not order:
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)

    # ========== منطق اصلی ==========
    # فقط سفارشات done قابل ویرایش هستند
    if order.status != 'done':
        return JsonResponse({'error': 'این سفارش قابل ویرایش نیست'}, status=400)

    # چک کردن اینکه آیا فایلی انتخاب شده
    if order.has_selected_file():
        return JsonResponse({
            'error': 'شما قبلاً یک فایل را انتخاب کرده‌اید و سفارش نهایی شده است. امکان درخواست ویرایش وجود ندارد.'
        }, status=400)

    # چک کردن اینکه قبلاً درخواست pending وجود نداشته باشه
    if order.revisions.filter(status='pending').exists():
        return JsonResponse({'error': 'شما قبلاً یک درخواست ویرایش ثبت کرده‌اید'}, status=400)

    feedback = request.POST.get('feedback', '')
    if not feedback or not feedback.strip():
        return JsonResponse({'error': 'لطفاً توضیحات ویرایش را وارد کنید'}, status=400)

    file = request.FILES.get('revision_file')

    from campaigns.services.campaigns_notifications import create_revision_request_service
    create_revision_request_service(
        order=order,
        requested_by=request.user,
        feedback=feedback,
        file=file
    )

    return JsonResponse({
        'success': True,
        'message': 'درخواست ویرایش با موفقیت ثبت شد. در انتظار بررسی تیم تولید محتوا.',
        'new_status': 'review_pending'
    })


@login_required
def final_accept_order(request, order_id):
    """
    تأیید نهایی سفارش توسط تبلیغ‌دهنده یا سفارش‌دهنده مستقل

    پشتیبانی از:
    - سفارش کمپینی (campaign__advertiser)
    - سفارش مستقل (standalone_user)

    این تابع فقط لایه HTTP هست — منطق اصلی توی
    campaigns.services.campaigns_notifications.finalize_content_order انجام میشه.
    """

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    # ============================================================
    # ۱. پیدا کردن سفارش (اول کمپینی، بعد مستقل)
    # ============================================================
    order = None

    # اول: چک کن کاربر صاحب این سفارشه (چه مستقل چه کمپینی)
    order = ContentOrder.objects.filter(id=order_id).select_related(
        'campaign', 'campaign__advertiser', 'plan', 'team', 'standalone_user'
    ).first()

    if not order:
        return JsonResponse({'error': 'سفارش یافت نشد'}, status=404)

    # بعد: بررسی مالکیت
    is_owner = False

    if order.is_standalone and order.standalone_user_id == request.user.id:
        is_owner = True
    elif order.campaign and hasattr(request.user, 'advertiser_profile'):
        if order.campaign.advertiser_id == request.user.advertiser_profile.id:
            is_owner = True

    if not is_owner:
        return JsonResponse({'error': 'دسترسی ندارید'}, status=403)

    # ============================================================
    # ۲. اعتبارسنجی سریع (قبل از صدا زدن سرویس)
    # ============================================================
    if order.status != ContentOrder.Status.DONE:
        return JsonResponse({
            'error': f'این سفارش در وضعیت «{order.get_status_display()}» است و قابل تأیید نیست.'
        }, status=400)

    if order.has_selected_file():
        return JsonResponse({
            'error': 'این سفارش قبلاً تأیید نهایی شده است.'
        }, status=400)

    # ============================================================
    # ۳. تشخیص نوع سفارش
    # ============================================================
    is_multi_choice = (
            order.plan and
            order.plan.delivery_type == 'multi_choice'
    )

    # ============================================================
    # ۴. برای سفارش multi_choice کمپینی: باید فایل انتخاب بشه
    # ============================================================
    # (این حالت از طریق select_multi_choice_option هندل میشه،
    #  ولی اگه کسی این endpoint رو مستقیم صدا زد، خطا بدیم)
    if order.campaign and is_multi_choice:
        return JsonResponse({
            'error': 'برای این سفارش باید یکی از گزینه‌ها را از طریق دکمه «انتخاب گزینه» انتخاب کنید.'
        }, status=400)

    # ============================================================
    # ۵. صدا زدن سرویس نهایی‌سازی
    # ============================================================
    # نکته: selected_file=None می‌فرستیم چون:
    # - برای کمپینی single: تابع خودش اولین فایل آخرین تحویل رو برمی‌داره
    # - برای مستقل: تابع خودش اولین فایل آخرین تحویل رو برمی‌داره
    # - برای کمپینی multi_choice: بالاتر خطا دادیم و به اینجا نمی‌رسه

    from campaigns.services.campaigns_notifications import finalize_content_order

    result = finalize_content_order(order, selected_file=None)

    # ============================================================
    # ۶. بازگشت پاسخ
    # ============================================================
    if not result['success']:
        return JsonResponse({'error': result['message']}, status=400)

    return JsonResponse({
        'success': True,
        'message': result['message'],
        'paid_amount': result['paid_amount'],
        'members_count': result['members_count'],
    })
