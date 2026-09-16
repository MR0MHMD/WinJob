def create_portfolio_from_order(order, final_file):
    """
    ساخت خودکار نمونه کار از فایل تحویل انتخاب شده
    - فایل فیزیکی کپی نمیشه، فقط مسیرش ذخیره میشه
    - فقط ۵ نمونه کار آخر هر پلن نگه داشته میشه
    """
    from content_team.models import ContentPortfolio
    from django.db import transaction

    # چک: پلن و فایل وجود دارن؟
    if not order.plan or not final_file or not final_file.file:
        return None

    file_name = final_file.file.name

    with transaction.atomic():
        # چک تکراری نبودن
        if ContentPortfolio.objects.filter(
            plan=order.plan,
            file=file_name
        ).exists():
            return None

        # ساخت نمونه کار
        portfolio = ContentPortfolio.objects.create(
            plan=order.plan,
            file=file_name,
        )

        # پاک کردن نمونه‌کارهای قدیمی (فقط ۵ تای آخر بمونه)
        old_ids = ContentPortfolio.objects.filter(
            plan=order.plan
        ).order_by('-created_at').values_list('id', flat=True)[5:]

        if old_ids:
            ContentPortfolio.objects.filter(id__in=list(old_ids)).delete()

        return portfolio