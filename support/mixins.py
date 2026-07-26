from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages

class SupportRequiredMixin(UserPassesTestMixin):
    """
    فقط کاربرانی که در گروه Support هستند (یا is_staff=True) دسترسی دارند.
    """

    def __init__(self):
        self.request = None

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_staff or
            user.groups.filter(name='support').exists()
        )

    def handle_no_permission(self):
        messages.error(self.request, 'شما به این صفحه دسترسی ندارید.')
        return redirect('accounts:login')



class SuperUserRequiredMixin(UserPassesTestMixin):
    """فقط سوپر یوزرها دسترسی دارند"""

    def __init__(self):
        self.request = None

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser

    def handle_no_permission(self):
        messages.error(self.request, 'شما به این صفحه دسترسی ندارید.')
        return redirect('support:dashboard')
