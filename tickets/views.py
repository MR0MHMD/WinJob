# views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.generic import ListView
from django.db.models import Q, Count, Prefetch
from .models import Ticket, TicketMessage, TicketCategory


class TicketListView(LoginRequiredMixin, ListView):
    """
    نمایش لیست تیکت‌های کاربر
    - کاربران عادی: فقط تیکت‌های خودشان
    - ادمین/پشتیبانی: همه تیکت‌ها با قابلیت فیلتر
    """
    model = Ticket
    template_name = 'tickets/pages/ticket_list.html'
    context_object_name = 'tickets'
    paginate_by = 15

    def get_queryset(self):
        queryset = Ticket.objects.select_related(
            'user', 'category', 'title', 'assigned_to'
        ).prefetch_related(
            Prefetch('messages', queryset=TicketMessage.objects.order_by('-created_at')[:1], to_attr='last_msg_list')
        )

        # کاربر عادی فقط تیکت‌های خودش
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)

        # اعمال فیلترها
        queryset = self.apply_filters(queryset)

        # جستجو
        queryset = self.apply_search(queryset)

        return queryset.select_related('campaign').order_by('-updated_at')

    def apply_filters(self, queryset):
        # فیلتر وضعیت
        status = self.request.GET.get('status')
        if status and status in dict(Ticket.Status.choices):
            queryset = queryset.filter(status=status)

        # فیلتر اولویت
        priority = self.request.GET.get('priority')
        if priority and priority in dict(Ticket.Priority.choices):
            queryset = queryset.filter(priority=priority)

        # فیلتر دسته‌بندی
        category = self.request.GET.get('category')
        if category and category.isdigit():
            queryset = queryset.filter(category_id=int(category))

        # فیلتر تاریخ
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        # فیلتر اختصاص (فقط ادمین)
        if self.request.user.is_staff:
            assigned = self.request.GET.get('assigned')
            if assigned == 'me':
                queryset = queryset.filter(assigned_to=self.request.user)
            elif assigned == 'unassigned':
                queryset = queryset.filter(assigned_to__isnull=True)

        return queryset

    def apply_search(self, queryset):
        search = self.request.GET.get('q')
        if search:
            queryset = queryset.filter(
                Q(custom_title__icontains=search) |
                Q(title__name__icontains=search) |
                Q(category__name__icontains=search) |
                Q(messages__message__icontains=search) |
                Q(user__phone_number__icontains=search)
            ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # آمار و شمارش‌ها
        base_qs = Ticket.objects if self.request.user.is_staff else Ticket.objects.filter(user=self.request.user)

        context.update({
            # آمار کلی
            'total_count': base_qs.count(),
            'open_count': base_qs.filter(status=Ticket.Status.OPEN).count(),
            'in_progress_count': base_qs.filter(status=Ticket.Status.IN_PROGRESS).count(),
            'closed_count': base_qs.filter(status=Ticket.Status.CLOSED).count(),

            # پارامترهای فعلی فیلتر
            'current_status': self.request.GET.get('status', ''),
            'current_priority': self.request.GET.get('priority', ''),
            'current_category': self.request.GET.get('category', ''),
            'current_search': self.request.GET.get('q', ''),
            'current_assigned': self.request.GET.get('assigned', ''),

            # انتخاب‌های وضعیت و اولویت برای فیلتر
            'status_choices': Ticket.Status.choices,
            'priority_choices': Ticket.Priority.choices,

            # دسته‌بندی‌های فعال برای فیلتر
            'categories': TicketCategory.objects.filter(is_active=True).annotate(
                ticket_count=Count('tickets', filter=Q(
                    tickets__user=self.request.user)) if not self.request.user.is_staff else Count('tickets')
            ).order_by('order', 'name'),
        })

        return context


# views.py - اضافه کن به فایل views موجود

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from .models import Ticket, TicketMessage, TicketAttachment, TicketCategory, TicketTitle


class TicketCreateView(LoginRequiredMixin, CreateView):
    """
    ایجاد تیکت جدید
    - گرفتن موضوع و عنوان از کاربر
    - آپلود فایل اختیاری
    """
    model = Ticket
    template_name = 'tickets/forms/ticket_create.html'
    fields = []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = TicketCategory.objects.filter(
            is_active=True
        ).prefetch_related('titles').order_by('order', 'name')
        context['priority_choices'] = Ticket.Priority.choices
        return context

    def post(self, request, *args, **kwargs):
        # گرفتن داده‌ها از فرم
        category_id = request.POST.get('category')
        title_id = request.POST.get('title')
        custom_title = request.POST.get('custom_title', '').strip()
        message_text = request.POST.get('message', '').strip()
        files = request.FILES.getlist('attachments')

        # اعتبارسنجی
        errors = []

        if not category_id:
            errors.append('لطفاً موضوع تیکت را انتخاب کنید.')

        if not title_id and not custom_title:
            errors.append('لطفاً عنوان تیکت را انتخاب کنید یا عنوان سفارشی وارد کنید.')

        if not message_text:
            errors.append('لطفاً متن پیام را وارد کنید.')

        if len(message_text) < 10:
            errors.append('متن پیام باید حداقل ۱۰ کاراکتر باشد.')

        # بررسی حجم فایل‌ها
        max_total_size = 10 * 1024 * 1024  # 10 مگابایت
        total_size = sum(f.size for f in files)
        if total_size > max_total_size:
            errors.append('حجم کل فایل‌ها نمی‌تواند بیشتر از ۱۰ مگابایت باشد.')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if errors:
                return JsonResponse({'success': False, 'errors': errors}, status=400)
        else:
            if errors:
                for error in errors:
                    messages.error(request, error)
                return self.form_invalid(None)

        try:
            # ایجاد تیکت
            ticket = Ticket.objects.create(
                user=request.user,
                category_id=category_id,
                title_id=title_id if title_id else None,
                custom_title=custom_title if not title_id else None,
                status=Ticket.Status.OPEN
            )

            # ایجاد اولین پیام
            ticket_message = TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=message_text,
                is_admin_reply=False
            )

            # آپلود فایل‌ها
            uploaded_files = []
            for file in files:
                attachment = TicketAttachment.objects.create(
                    message=ticket_message,
                    file=file,
                    file_name=file.name,
                    file_size=file.size
                )
                uploaded_files.append({
                    'name': attachment.file_name,
                    'size': attachment.file_size_display,
                    'url': attachment.file.url
                })

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'ticket_id': ticket.pk,
                    'message': 'تیکت با موفقیت ایجاد شد.',
                    'redirect_url': reverse_lazy('tickets:ticket_list'),
                    'files': uploaded_files
                })

            messages.success(request, '✅ تیکت شما با موفقیت ثبت شد. همکاران ما در اسرع وقت پاسخگو خواهند بود.')
            return JsonResponse({'success': True, 'redirect_url': reverse_lazy('tickets:ticket_detail', kwargs={'pk': ticket.pk})})

        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': [f'خطا در ایجاد تیکت: {str(e)}']}, status=500)
            messages.error(request, f'خطا در ایجاد تیکت: {str(e)}')
            return self.form_invalid(None)

    def form_invalid(self, form):
        # برگشت به صفحه قبل با حفظ داده‌ها
        return self.render_to_response(self.get_context_data())


class TicketTitleAPIView(LoginRequiredMixin, View):
    """API برای گرفتن عنوان‌های هر دسته‌بندی (برای AJAX)"""

    def get(self, request, category_id):
        titles = TicketTitle.objects.filter(
            category_id=category_id,
            is_active=True
        ).prefetch_related('faqs').order_by('order', 'name')

        titles_data = []
        for title in titles:
            faqs = title.faqs.filter(is_active=True).order_by('order', 'created_at')
            titles_data.append({
                'id': title.id,
                'name': title.name,
                'description': title.description,
                'slug': title.slug,
                'faqs_count': faqs.count(),
                'faqs': [
                    {
                        'id': faq.id,
                        'question': faq.question,
                        'answer': faq.answer,
                    } for faq in faqs
                ]
            })

        return JsonResponse({'titles': titles_data})


# views.py - اضافه کن

from django.views.generic import DetailView
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Prefetch


class TicketDetailView(LoginRequiredMixin, DetailView):
    """
    نمایش جزئیات تیکت + لیست پیام‌ها + فرم ارسال پیام جدید
    """
    model = Ticket
    template_name = 'tickets/pages/ticket_detail.html'
    context_object_name = 'ticket'
    pk_url_kwarg = 'pk'

    def get_queryset(self):
        qs = Ticket.objects.select_related(
            'user', 'category', 'title', 'assigned_to', 'campaign'
        ).prefetch_related(
            Prefetch(
                'messages',
                queryset=TicketMessage.objects.select_related('sender')
                .prefetch_related('attachments')
                .order_by('created_at')
            )
        )

        # کاربر عادی فقط تیکت خودش رو ببینه
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['max_file_size'] = 10  # مگابایت
        context['allowed_file_types'] = '.jpg,.jpeg,.png,.gif,.pdf,.zip,.rar,.doc,.docx'
        return context

    def post(self, request, *args, **kwargs):
        """ارسال پیام جدید در تیکت"""
        self.object = self.get_object()
        ticket = self.object

        # چک کردن بسته نبودن تیکت
        if ticket.status == Ticket.Status.CLOSED:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': ['این تیکت بسته شده است و امکان ارسال پیام وجود ندارد.']
                }, status=400)
            messages.error(request, 'این تیکت بسته شده است.')
            return redirect('tickets:ticket_detail', pk=ticket.pk)

        message_text = request.POST.get('message', '').strip()
        files = request.FILES.getlist('attachments')

        errors = []

        if not message_text:
            errors.append('لطفاً متن پیام را وارد کنید.')

        if len(message_text) < 2:
            errors.append('متن پیام حداقل ۲ کاراکتر باشد.')

        # بررسی حجم فایل‌ها
        max_total_size = 10 * 1024 * 1024  # 10MB
        total_size = sum(f.size for f in files)
        if total_size > max_total_size:
            errors.append('حجم کل فایل‌ها نمی‌تواند بیشتر از ۱۰ مگابایت باشد.')

        if errors:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': errors}, status=400)
            for error in errors:
                messages.error(request, error)
            return self.render_to_response(self.get_context_data())

        try:
            # ایجاد پیام
            ticket_message = TicketMessage.objects.create(
                ticket=ticket,
                sender=request.user,
                message=message_text,
                is_admin_reply=request.user.is_staff
            )

            # آپلود فایل‌ها
            uploaded_files = []
            for file in files:
                attachment = TicketAttachment.objects.create(
                    message=ticket_message,
                    file=file,
                    file_name=file.name,
                    file_size=file.size
                )
                uploaded_files.append({
                    'id': attachment.id,
                    'name': attachment.file_name,
                    'size': attachment.file_size_display,
                    'url': attachment.file.url,
                    'extension': attachment.file_extension
                })

            # آپدیت وضعیت تیکت
            if request.user.is_staff:
                # اگه ادمین پاسخ میده
                ticket.status = Ticket.Status.WAITING_USER
            else:
                # اگه کاربر عادی پاسخ میده
                ticket.status = Ticket.Status.WAITING_ADMIN

            ticket.save()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': '✅ پیام با موفقیت ارسال شد.',
                    'ticket_id': ticket.pk,
                    'sender_name': '👤 پشتیبانی' if request.user.is_staff else '👤 شما',
                    'message_text': message_text,
                    'created_at': ticket_message.created_at.strftime('%Y/%m/%d - %H:%M'),
                    'files': uploaded_files,
                    'new_status': ticket.get_status_display(),
                    'new_status_class': ticket.status,
                })

            messages.success(request, '✅ پیام با موفقیت ارسال شد.')
            return redirect('tickets:ticket_detail', pk=ticket.pk)

        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': [f'خطا در ارسال پیام: {str(e)}']
                }, status=500)
            messages.error(request, f'خطا در ارسال پیام: {str(e)}')
            return self.render_to_response(self.get_context_data())
