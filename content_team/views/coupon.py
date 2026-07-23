from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from datetime import datetime as dt
from django.contrib import messages
from payment.models import Coupon
from django.db.models import Sum
import jdatetime


@login_required
def team_coupons(request):
    if not hasattr(request.user, 'team_member'):
        messages.error(request, "شما عضو هیچ تیم تولید محتوایی نیستید.")
        return redirect('core:home')

    member = request.user.team_member
    team = member.team

    if not member.is_active:
        messages.error(request, "حساب شما در این تیم غیرفعال است.")
        return redirect('core:home')

    is_manager = (member.role == 'manager')

    coupons = Coupon.objects.filter(
        team=team
    ).select_related('team').order_by('-id')

    total_coupons = coupons.count()
    active_coupons = coupons.filter(is_active=True).count()
    total_used = coupons.aggregate(total=Sum('used_count'))['total'] or 0

    # فیلتر پیشرفته
    status = request.GET.get('status')
    used_min = request.GET.get('used_min')
    used_max = request.GET.get('used_max')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if status == 'active':
        coupons = coupons.filter(is_active=True)
    elif status == 'inactive':
        coupons = coupons.filter(is_active=False)

    if used_min:
        coupons = coupons.filter(used_count__gte=int(used_min))
    if used_max:
        coupons = coupons.filter(used_count__lte=int(used_max))

    if date_from:
        try:
            parts = date_from.split('/')
            jd = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            coupons = coupons.filter(expires_at__gte=jd.togregorian())
        except:
            pass

    if date_to:
        try:
            parts = date_to.split('/')
            jd = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            coupons = coupons.filter(expires_at__lte=jd.togregorian())
        except:
            pass

    context = {
        'coupons': coupons,
        'team': team,
        'total_coupons': total_coupons,
        'active_coupons': active_coupons,
        'total_used': total_used,
        'is_manager': is_manager,
        'member': member,
    }

    return render(request, 'content_team/forms/coupons.html', context)


@login_required
def team_coupon_create(request):
    if request.method != 'POST':
        return redirect('content_team:team_coupons')

    member = request.user.team_member
    if member.role != 'manager':
        messages.error(request, "فقط مدیر تیم می‌تواند کد تخفیف بسازد.")
        return redirect('content_team:team_coupons')

    team = member.team

    code = request.POST.get('code', '').strip().upper()
    scope = 'content_team'
    discount_type = request.POST.get('discount_type')
    value = request.POST.get('value', '0').replace(',', '')
    max_uses = request.POST.get('max_uses')
    expires_date = request.POST.get('expires_date', '').strip()
    expires_time = request.POST.get('expires_time', '00:00').strip()

    if not all([code, discount_type, value]):
        messages.error(request, "لطفاً تمام فیلدهای ضروری را پر کنید.")
        return redirect('content_team:team_coupons')

    if Coupon.objects.filter(code=code).exists():
        messages.error(request, "این کد تخفیف قبلاً استفاده شده است.")
        return redirect('content_team:team_coupons')

    coupon = Coupon(
        code=code,
        scope=scope,
        team=team,
        discount_type=discount_type,
        value=value,
        max_uses=int(max_uses) if max_uses else None,
        is_active=True
    )

    if expires_date:
        try:
            date_parts = expires_date.split('/')
            time_parts = expires_time.split(':') if expires_time else ['00', '00']

            jyear, jmonth, jday = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
            hour = int(time_parts[0]) if time_parts else 0
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            jalali_date = jdatetime.date(jyear, jmonth, jday)
            gregorian_date = jalali_date.togregorian()

            expires_at = dt.combine(gregorian_date, dt.min.time())
            expires_at = expires_at.replace(hour=hour, minute=minute)

            coupon.expires_at = expires_at
        except (ValueError, IndexError):
            messages.error(request, "فرمت تاریخ نامعتبر است. لطفاً به صورت ۱۴۰۵/۰۲/۰۶ وارد کنید.")
            return redirect('content_team:team_coupons')

    coupon.save()
    messages.success(request, f"کد تخفیف {code} با موفقیت ساخته شد! 🎉")
    return redirect('content_team:team_coupons')


@login_required
def team_coupon_edit(request, coupon_id):
    if request.method != 'POST':
        return redirect('content_team:team_coupons')

    member = request.user.team_member
    if member.role != 'manager':
        messages.error(request, "فقط مدیر تیم می‌تواند کد تخفیف را ویرایش کند.")
        return redirect('content_team:team_coupons')

    coupon = get_object_or_404(Coupon, id=coupon_id, team=member.team)

    code = request.POST.get('code', '').strip().upper()
    discount_type = request.POST.get('discount_type')
    value = request.POST.get('value', '0').replace(',', '')
    max_uses = request.POST.get('max_uses')
    is_active = request.POST.get('is_active') == 'on'
    expires_date = request.POST.get('expires_date', '').strip()
    expires_time = request.POST.get('expires_time', '00:00').strip()

    if not all([code, discount_type, value]):
        messages.error(request, "لطفاً تمام فیلدهای ضروری را پر کنید.")
        return redirect('content_team:team_coupons')

    if Coupon.objects.filter(code=code).exclude(id=coupon_id).exists():
        messages.error(request, "این کد تخفیف قبلاً استفاده شده است.")
        return redirect('content_team:team_coupons')

    coupon.code = code
    coupon.discount_type = discount_type
    coupon.value = value
    coupon.max_uses = int(max_uses) if max_uses else None
    coupon.is_active = is_active

    if expires_date:
        try:
            date_parts = expires_date.split('/')
            time_parts = expires_time.split(':') if expires_time else ['00', '00']

            jyear, jmonth, jday = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
            hour = int(time_parts[0]) if time_parts else 0
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            jalali_date = jdatetime.date(jyear, jmonth, jday)
            gregorian_date = jalali_date.togregorian()

            expires_at = dt.combine(gregorian_date, dt.min.time())
            expires_at = expires_at.replace(hour=hour, minute=minute)

            coupon.expires_at = expires_at
        except:
            messages.error(request, "فرمت تاریخ نامعتبر است.")
            return redirect('content_team:team_coupons')
    else:
        coupon.expires_at = None

    coupon.save()
    messages.success(request, f"کد تخفیف {code} با موفقیت ویرایش شد! ✏️")
    return redirect('content_team:team_coupons')


@login_required
def team_coupon_delete(request, coupon_id):
    if request.method != 'POST':
        return redirect('content_team:team_coupons')

    member = request.user.team_member
    if member.role != 'manager':
        messages.error(request, "فقط مدیر تیم می‌تواند کد تخفیف را حذف کند.")
        return redirect('content_team:team_coupons')

    coupon = get_object_or_404(Coupon, id=coupon_id, team=member.team)
    code = coupon.code
    coupon.delete()

    messages.success(request, f"کد تخفیف {code} با موفقیت حذف شد! 🗑️")
    return redirect('content_team:team_coupons')
