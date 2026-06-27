def is_support_user(user):
    """بررسی می‌کند که کاربر پشتیبان است (is_staff یا عضو گروه Support)"""
    if not user.is_authenticated:
        return False
    return user.is_staff or user.groups.filter(name='Support').exists()