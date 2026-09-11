from django.views.generic import TemplateView
from django.http import JsonResponse
from django.db.models import Count, Q
from tickets.models import TicketCategory, TicketTitle
from core.models import FAQ


class FAQPageView(TemplateView):
    """صفحه سوالات متداول — سلسله‌مراتبی با کارت و AJAX"""
    template_name = "core/pages/faq.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = (
            TicketCategory.objects
            .filter(is_active=True)
            .annotate(
                titles_count=Count('titles', filter=Q(titles__is_active=True)),
                faq_count=Count(
                    'titles__faqs',
                    filter=Q(titles__is_active=True, titles__faqs__is_active=True),
                ),
            )
            .order_by('order', 'name')
        )
        context['categories'] = categories
        context['total_faqs'] = FAQ.objects.filter(is_active=True).count()
        context['total_categories'] = categories.count()
        return context


def faq_titles_api(request, category_id):
    """AJAX: عناوین یک دسته‌بندی"""
    try:
        category = TicketCategory.objects.get(pk=category_id, is_active=True)
    except TicketCategory.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'دسته یافت نشد'}, status=404)

    titles = (
        TicketTitle.objects
        .filter(category=category, is_active=True)
        .annotate(faq_count=Count('faqs', filter=Q(faqs__is_active=True)))
        .order_by('order', 'name')
    )
    data = [
        {
            'id': t.pk,
            'name': t.name,
            'slug': t.slug,
            'description': t.description or '',
            'faqs_count': t.faqs_count,
        }
        for t in titles
    ]
    return JsonResponse({
        'ok': True,
        'category': {
            'id': category.pk,
            'name': category.name,
            'slug': category.slug,
            'icon': category.icon or 'bi-folder',
            'description': category.description or '',
        },
        'titles': data,
    })


def faq_questions_api(request, title_id):
    """AJAX: سوالات یک عنوان"""
    try:
        title = (
            TicketTitle.objects
            .select_related('category')
            .get(pk=title_id, is_active=True)
        )
    except TicketTitle.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'موضوع یافت نشد'}, status=404)

    faqs = (
        FAQ.objects
        .filter(title=title, is_active=True)
        .order_by('order', 'created_at')
    )
    data = [
        {
            'id': f.pk,
            'question': f.question,
            'answer': f.answer,
            'order': f.order,
        }
        for f in faqs
    ]
    return JsonResponse({
        'ok': True,
        'title': {
            'id': title.pk,
            'name': title.name,
            'slug': title.slug,
            'description': title.description or '',
        },
        'category': {
            'id': title.category_id,
            'name': title.category.name,
            'slug': title.category.slug,
            'icon': title.category.icon or 'bi-folder',
        },
        'faqs': data,
    })


# core/views.py

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from ..models import ContentServiceType


@require_http_methods(["GET"])
def api_content_service_types(request):
    """
    API برای دریافت لیست سرویس‌های تولید محتوا (استفاده در AJAX)
    """
    services = ContentServiceType.objects.filter(is_active=True).values(
        'id', 'name', 'slug', 'description', 'icon', 'allowed_units'
    )

    # اضافه کردن نمایش واحدهای مجاز
    services_list = list(services)
    for service in services_list:
        unit_labels = {
            'second': 'ثانیه',
            'minute': 'دقیقه',
            'quantity': 'تعدادی'
        }
        allowed = service.get('allowed_units', [])
        service['allowed_units_display'] = ', '.join([
            unit_labels.get(u, u) for u in allowed
        ])

    return JsonResponse(services_list, safe=False)
