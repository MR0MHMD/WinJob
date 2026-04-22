def get_team_province(team):
    """دریافت استان تیم از طریق مدیر تیم"""
    try:
        manager = team.members.filter(role='manager', is_active=True).first()
        if manager and manager.user and manager.user.province:
            return manager.user.province
    except:
        pass
    return None


def content_order_file_path(instance, filename):
    """
    مسیر ذخیره فایل‌های سفارش
    پشتیبانی از ContentOrderFile و ContentDeliveryFile
    """
    if hasattr(instance, 'order') and instance.order:
        return f'content_orders/{instance.order.campaign.id}/{instance.order.id}/{filename}'

    elif hasattr(instance, 'delivery') and instance.delivery:
        return f'content_orders/{instance.delivery.order.campaign.id}/{instance.delivery.order.id}/delivery/{filename}'

    # fallback
    return f'content_orders/unknown/{filename}'
