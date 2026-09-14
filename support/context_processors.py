# support/context_processors.py

"""
Context Processor برای منوی داینامیک پنل Support

⚠️ فقط برای صفحات پنل Support اجرا می‌شه (بهینه برای پرفورمنس)
"""

from accounts.models import CustomUser

# ==================== مسیر پایه پنل Support ====================
# اگه URL پنل Support تو تغییر کرد، فقط این مقدار رو عوض کن
SUPPORT_URL_PREFIX = '/support/'

# ==================== برچسب بخش‌ها ====================
# عنوان نمایشی هر بخش توی سایدبار
SECTION_LABELS = {
    'main': 'داشبورد',
    'publish': 'بخش نشر',
    'content': 'تولید محتوا',
    'system': 'سیستم',
}

# ==================== ترتیب نمایش بخش‌ها ====================
# ترتیب دقیق نمایش بخش‌ها توی سایدبار
SECTION_ORDER = ['main', 'publish', 'content', 'system']


# support/context_processors.py

"""
Context Processor برای منوی داینامیک پنل Support

⚠️ فقط برای صفحات پنل Support اجرا می‌شه (بهینه برای پرفورمنس)
"""

from accounts.models import CustomUser

# ==================== مسیر پایه پنل Support ====================
SUPPORT_URL_PREFIX = '/support/'

# ==================== برچسب بخش‌ها ====================
SECTION_LABELS = {
    'main': 'داشبورد',
    'publish': 'بخش نشر',
    'content': 'تولید محتوا',
    'system': 'سیستم',
}

# ==================== ترتیب نمایش بخش‌ها ====================
SECTION_ORDER = ['main', 'publish', 'content', 'system']


def support_menu(request):
    """
    منوی داینامیک پنل Support بر اساس نقش کاربر
    """
    # ===== ۱. فقط برای صفحات Support =====
    if not request.path.startswith(SUPPORT_URL_PREFIX):
        return {}

    # ===== ۲. کاربر لاگین کرده؟ =====
    if not request.user.is_authenticated:
        return {}

    user = request.user

    # ===== ۳. دسترسی Support داره؟ =====
    if not user.has_support_access:
        return {}

    # ============ ساخت منو ============
    menu = []

    # ===== ۱. داشبورد (همه نقش‌ها) =====
    menu.append({
        'title': 'داشبورد',
        'url_name': 'support:dashboard',
        'url_prefix': 'support:dashboard',
        'bi_icon': 'bi-speedometer2',
        'section': 'main',
    })

    # ===== ۲. مدیریت مالی (فقط CEO و Dev) =====
    if user.is_top_manager:
        menu.append({
            'title': 'مدیریت مالی',
            'url_name': 'support:finance_dashboard',
            'url_prefix': 'support:finance',
            'bi_icon': 'bi-wallet2',
            'section': 'main',
        })

    # ===== ۳. بخش نشر =====
    if user.role in [
        CustomUser.Role.CEO,
        CustomUser.Role.DEVELOPER,
        CustomUser.Role.PUBLISH_MANAGER,
    ]:
        menu.append({
            'title': 'کمپین‌ها',
            'url_name': 'support:campaign_list',
            'url_prefix': 'support:campaign',
            'bi_icon': 'bi-flag',
            'section': 'publish',
        })
        menu.append({
            'title': 'کانال‌ها',
            'url_name': 'support:channel_list',
            'url_prefix': 'support:channel',
            'bi_icon': 'bi-grid-3x3-gap',
            'section': 'publish',
        })
        menu.append({
            'title': 'رزروها',
            'url_name': 'support:booking_list',
            'url_prefix': 'support:booking',
            'bi_icon': 'bi-cart',
            'section': 'publish',
        })
        menu.append({
            'title': 'گزارش‌ها',
            'url_name': 'support:report_list',
            'url_prefix': 'support:report',
            'bi_icon': 'bi-file-earmark-text',
            'section': 'publish',
        })

    # ===== ۴. بخش تولید محتوا =====
    if user.role in [
        CustomUser.Role.CEO,
        CustomUser.Role.DEVELOPER,
        CustomUser.Role.CONTENT_MANAGER,
    ]:
        menu.append({
            'title': 'تیم‌های محتوا',
            'url_name': 'support:team_list',
            'url_prefix': 'support:team',
            'bi_icon': 'bi-people',
            'section': 'content',
        })
        menu.append({
            'title': 'سفارش‌های محتوا',
            'url_name': 'support:content_order_list',
            'url_prefix': 'support:content_order',
            'bi_icon': 'bi-file-earmark',
            'section': 'content',
        })

    # ===== ۵. کاربران =====
    menu.append({
        'title': 'کاربران',
        'url_name': 'support:user_list',
        'url_prefix': 'support:user',
        'bi_icon': 'bi-person',
        'section': 'system',
    })

    # ===== ۶. تیکت‌ها =====
    menu.append({
        'title': 'تیکت‌ها',
        'url_name': 'support:ticket_list',
        'url_prefix': 'support:ticket',
        'bi_icon': 'bi-headset',
        'section': 'system',
    })

    # ===== ۷. نوتیفیکیشن‌ها =====
    menu.append({
        'title': 'نوتیفیکیشن‌ها',
        'url_name': 'support:notification_list',
        'url_prefix': 'support:notification',
        'bi_icon': 'bi-bell',
        'section': 'system',
    })

    # ============ گروه‌بندی بر اساس section ============
    grouped = {}
    for item in menu:
        section_key = item['section']
        if section_key not in grouped:
            grouped[section_key] = {
                'label': SECTION_LABELS.get(section_key, section_key),
                'items': [],
            }
        grouped[section_key]['items'].append(item)

    # مرتب‌سازی بر اساس SECTION_ORDER
    grouped = {k: grouped[k] for k in SECTION_ORDER if k in grouped}

    # ============ برچسب نقش کاربر ============
    role_label = user.get_role_display()
    if user.is_regional_manager and user.province:
        role_label = f'مدیر استانی {user.province.name}'

    return {
        'support_menu_grouped': grouped,
        'support_user_role_label': role_label,
    }
