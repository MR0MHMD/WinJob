from .models import Notification


def unread_notifications(request):
    """
    Context processor برای در دسترس قرار دادن نوتیفیکیشن‌ها در تمام تمپلیت‌ها
    """
    if request.user.is_authenticated:
        recent_notifications = Notification.objects.filter(
            user=request.user
        ).order_by('-created_at')[:10]

        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()

        return {
            'recent_notifications': recent_notifications,
            'unread_notifications_count': unread_count,
        }

    return {
        'recent_notifications': [],
        'unread_notifications_count': 0,
    }