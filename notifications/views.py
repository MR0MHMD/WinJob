from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Notification, NotificationPreference
import json
from django.views.decorators.http import require_POST


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()

    # گرفتن یا ساختن تنظیمات کاربر برای مودال
    prefs, created = NotificationPreference.objects.get_or_create(user=request.user)

    context = {
        'notifications': notifications,
        'unread_count': unread_count,
        'prefs': prefs,
    }
    return render(request, 'notifications/pages/notification_list.html', context)


@login_required
def mark_all_read(request):
    """تابع AJAX برای مارک کردن تمام اعلان‌ها به عنوان خوانده شده"""
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return JsonResponse({'success': True, 'message': 'تمام پیام‌ها خوانده شدند.'})
    return JsonResponse({'error': 'متد نامعتبر'}, status=400)


@login_required
def update_preferences(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        prefs = request.user.notification_prefs

        fields = [
            'receive_in_bale', 'ticket_replies', 'marketing_messages', 'financial_alerts',
            'adv_campaign_status', 'adv_influencer_actions', 'adv_content_orders',
            'inf_new_orders', 'inf_report_status',
            'team_new_orders', 'team_revisions', 'team_financial'
        ]

        for field in fields:
            if field in data:
                setattr(prefs, field, data[field])

        prefs.save()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'متد نامعتبر'}, status=400)


@login_required
@require_POST
def mark_notification_read(request, notif_id):
    """
    علامت زدن یک اعلان به عنوان خوانده شده (AJAX)
    """
    notif = get_object_or_404(Notification, id=notif_id, user=request.user)
    if not notif.is_read:
        notif.mark_as_read()  # متد mark_as_read در مدل وجود دارد
        return JsonResponse({'success': True, 'message': 'اعلان خوانده شد.'})
    return JsonResponse({'success': False, 'message': 'قبلاً خوانده شده بود.'})
