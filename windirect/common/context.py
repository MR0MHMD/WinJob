from windirect.connections.models import InstagramConnection


def owner_context(request):
    """داده‌های مشترک صفحات خصوصی وین دایرکت را آماده می‌کند."""
    return {
        "noindex": True,
        "connections_count": InstagramConnection.objects.filter(
            owner=request.user
        ).count(),
    }
