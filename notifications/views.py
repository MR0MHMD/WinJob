from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Notification


@login_required
def notification_list(request):
    """صفحه لیست تمام نوتیفیکیشن‌ها"""
    notifications = Notification.objects.filter(user=request.user)
    unread_count = notifications.filter(is_read=False).count()

    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    return render(request, 'notifications/list.html', context)


@login_required
def mark_as_read(request, notification_id):
    """علامت‌گذاری یک نوتیفیکیشن به عنوان خوانده شده"""
    notif = get_object_or_404(Notification, id=notification_id, user=request.user)
    notif.mark_as_read()

    # اگر لینک داشت به اون لینک برو
    if notif.link:
        return redirect(notif.link)

    return redirect(request.META.get('HTTP_REFERER', 'core:home'))


@login_required
def mark_all_as_read(request):
    """علامت‌گذاری همه نوتیفیکیشن‌ها به عنوان خوانده شده"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, 'همه پیام‌ها به عنوان خوانده شده علامت‌گذاری شدند.')
    return redirect('notifications:list')
