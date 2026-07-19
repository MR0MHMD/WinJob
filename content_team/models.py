from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from gamification.mixins import GamificationMixin
from django_jalali.db import models as jmodels
from django_resized import ResizedImageField
from core.utils import generate_random_slug
from .utils import content_order_file_path
from django.db.models import Sum
from django.db import models
import mimetypes


class ContentTeam(GamificationMixin, models.Model):
    """
    مدل تیم تولید محتوا - توسط ادمین ایجاد می‌شود
    """
    name = models.CharField(
        _('نام تیم'),
        max_length=200
    )
    slug = models.SlugField(
        _('شناسه'),
        unique=True,
        allow_unicode=True,
        blank=True,
        default=generate_random_slug
    )

    description = models.TextField(
        _('توضیحات'),
        blank=True
    )
    logo = ResizedImageField(_('لوگو'), upload_to='content_team/logos/',
                             size=[500, 500], scale=1,
                             crop=['middle', 'center'],
                             null=True, blank=True)

    is_active = models.BooleanField(
        _('فعال'),
        default=True
    )
    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )
    updated_at = jmodels.jDateTimeField(
        _('تاریخ ویرایش'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('تیم تولید محتوا')
        verbose_name_plural = _('تیم‌های تولید محتوا')
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_total_revenue_percent(self):
        """مجموع درصد سهام اعضای فعال تیم"""
        total = self.members.filter(is_active=True).aggregate(
            total=Sum('revenue_share_percent')
        )['total'] or 0
        return total

    def is_revenue_share_valid(self):
        """آیا مجموع درصدها دقیقاً ۱۰۰ هست؟"""
        return self.get_total_revenue_percent() == 100

    def clean(self):
        """اعتبارسنجی در سطح تیم"""
        super().clean()
        total_percent = self.get_total_revenue_percent()

        if self.members.filter(is_active=True).exists() and total_percent != 100:
            raise ValidationError(
                f'مجموع درصد سهام اعضای فعال تیم باید دقیقاً ۱۰۰ باشد (در حال حاضر: {total_percent}%)'
            )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_random_slug()
        super().save(*args, **kwargs)

    @property
    def avg_rating(self):
        """میانگین امتیاز تیم"""
        result = self.reviews.aggregate(avg=models.Avg('rating'))
        return round(result['avg'], 1) if result['avg'] else None

    @property
    def completed_orders_count(self):
        """تعداد سفارشات تکمیل شده"""
        return self.orders.filter(status='completed').count()

    @property
    def members_count(self):
        return self.members.filter(is_active=True).count()


class ContentTeamMember(models.Model):
    """
    اعضای تیم تولید محتوا
    """

    class Role(models.TextChoices):
        MANAGER = 'manager', _('مدیر تیم')
        EDITOR = 'editor', _('ادیتور')
        WRITER = 'writer', _('نویسنده')
        DESIGNER = 'designer', _('طراح')
        VIDEOGRAPHER = 'videographer', _('فیلمبردار')
        OTHER = 'other', _('سایر')

    team = models.ForeignKey(
        ContentTeam,
        on_delete=models.CASCADE,
        related_name='members',
        verbose_name=_('تیم')
    )

    user = models.OneToOneField('accounts.CustomUser', on_delete=models.CASCADE, related_name='team_member',
                                verbose_name=_('کاربر'))

    role = models.CharField(
        _('نقش'),
        max_length=50,
        choices=Role.choices
    )

    revenue_share_percent = models.PositiveSmallIntegerField(
        _('درصد سهم از درآمد'),
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_('درصدی که این عضو از هر سفارش دریافت می‌کند (۰ تا ۱۰۰)')
    )

    bio = models.TextField(
        _('بیوگرافی'),
        blank=True
    )

    is_active = models.BooleanField(
        _('فعال'),
        default=True
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('عضو تیم تولید محتوا')
        verbose_name_plural = _('اعضای تیم تولید محتوا')
        ordering = ['team', 'created_at']

    def __str__(self):
        return f"{self.user} - {self.team.name}"

    def clean(self):
        """اعتبارسنجی در سطح مدل"""
        if self.revenue_share_percent > 100:
            raise ValidationError({
                'revenue_share_percent': 'درصد سهم نمی‌تواند بیشتر از ۱۰۰ باشد.'
            })

        if self.is_active and self.revenue_share_percent > 0:
            other_members_sum = ContentTeamMember.objects.filter(
                team=self.team,
                is_active=True
            ).exclude(pk=self.pk).aggregate(
                total=Sum('revenue_share_percent')
            )['total'] or 0

            if other_members_sum + self.revenue_share_percent > 100:
                raise ValidationError({
                    'revenue_share_percent': f'مجموع درصد سهام اعضای فعال تیم نمی‌تواند از ۱۰۰ بیشتر شود. (در حال حاضر {other_members_sum}% + {self.revenue_share_percent}% = {other_members_sum + self.revenue_share_percent}%)'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def is_manager(self):
        return self.role == self.Role.MANAGER and self.is_active


class ContentServiceType(models.Model):
    """
    انواع خدمات تولید محتوا - توسط ادمین تعریف می‌شود
    """
    ad_type = models.ManyToManyField(
        "campaigns.AdType",
        verbose_name=_('نوع تبلیغ'),
        related_name='content_service_type',
    )

    name = models.CharField(
        _('نام خدمت'),
        max_length=100,
        unique=True
    )
    slug = models.SlugField(
        _('شناسه'),
        unique=True,
        allow_unicode=True
    )
    description = models.TextField(
        _('توضیحات'),
        blank=True
    )
    icon = models.CharField(
        _('آیکون'),
        max_length=50,
        blank=True,
        help_text=_('نام کلاس آیکون (مثلاً: fa-video)')
    )

    allowed_units = models.JSONField(
        _('واحدهای مجاز'),
        default=list,
        blank=True,
        help_text=_('واحدهایی که این سرویس می‌تواند داشته باشد. مثال: ["second", "minute", "quantity"]')
    )

    is_active = models.BooleanField(
        _('فعال'),
        default=True
    )
    display_order = models.PositiveIntegerField(
        _('ترتیب نمایش'),
        default=0
    )
    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('نوع خدمت تولید محتوا')
        verbose_name_plural = _('انواع خدمات تولید محتوا')
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def get_allowed_units_display(self):
        """نمایش واحدهای مجاز به صورت خوانا"""
        unit_labels = {
            'second': 'ثانیه',
            'minute': 'دقیقه',
            'quantity': 'تعدادی'
        }
        return ', '.join([unit_labels.get(u, u) for u in self.allowed_units])


class ContentServicePlan(models.Model):
    """
    پلن‌های قیمت‌گذاری خدمات تیم‌های تولید محتوا
    """

    class PricingUnit(models.TextChoices):
        SECOND = 'second', 'ثانیه'
        MINUTE = 'minute', 'دقیقه'
        QUANTITY = 'quantity', 'تعدادی'

    class DeliveryType(models.TextChoices):
        SINGLE = 'single', 'تحویل یک فایل'
        MULTI_CHOICE = 'multi_choice', 'تحویل چند گزینه و انتخاب یکی'

    # ========== ارتباطات ==========
    team = models.ForeignKey(
        'ContentTeam',
        on_delete=models.CASCADE,
        related_name='service_plans',
        verbose_name=_('تیم')
    )

    service_type = models.ForeignKey(
        'ContentServiceType',
        on_delete=models.CASCADE,
        related_name='plans',
        verbose_name=_('نوع خدمت')
    )

    # ========== اطلاعات پلن ==========
    name = models.CharField(
        _('نام پلن'),
        max_length=200,
        help_text=_('مثلاً: "موشن ساده" یا "پکیج ۳ پوستر"')
    )

    description = models.TextField(
        _('توضیحات پلن'),
        blank=True,
        help_text=_('توضیح کامل این پلن شامل چه چیزایی میشه')
    )

    features = models.JSONField(
        _('ویژگی‌ها'),
        default=list,
        blank=True,
        help_text=_('لیست ویژگی‌های این پلن. مثال: ["۲ دوربین 4K", "تدوین حرفه‌ای"]')
    )

    # ========== واحد و مقدار ==========
    pricing_unit = models.CharField(
        _('واحد قیمت‌گذاری'),
        max_length=20,
        choices=PricingUnit.choices,
        help_text=_('واحد اندازه‌گیری برای این پلن (ثانیه، دقیقه، یا تعدادی)')
    )

    # ✅ فقط برای SECOND و MINUTE استفاده میشه
    base_quantity = models.PositiveIntegerField(
        _('مقدار پایه'),
        null=True,
        blank=True,
        help_text=_('مقدار پایه این پلن. مثلاً ۲۰ برای ۲۰ ثانیه، یا ۳ دقیقه. (فقط برای واحدهای ثانیه و دقیقه)')
    )

    # ✅ فقط برای SECOND و MINUTE استفاده میشه
    min_quantity = models.PositiveIntegerField(
        _('حداقل مقدار'),
        null=True,
        blank=True,
        help_text=_('حداقل مقداری که این پلن پوشش میدهد. (فقط برای واحدهای ثانیه و دقیقه)')
    )

    # ✅ فقط برای SECOND و MINUTE استفاده میشه
    max_quantity = models.PositiveIntegerField(
        _('حداکثر مقدار'),
        null=True,
        blank=True,
        help_text=_('حداکثر مقداری که این پلن پوشش میدهد. (فقط برای واحدهای ثانیه و دقیقه)')
    )

    # ========== قیمت نهایی ==========
    price = models.PositiveBigIntegerField(
        _('قیمت نهایی (تومان)'),
        help_text=_('قیمت کاملاً مشخص این پلن. مثلاً ۲۵۰,۰۰۰ تومان')
    )

    # ========== نوع تحویل ==========
    delivery_type = models.CharField(
        _('نوع تحویل'),
        max_length=20,
        choices=DeliveryType.choices,
        default=DeliveryType.SINGLE,
        help_text=_('نحوه تحویل فایل‌ها به کاربر')
    )

    delivery_options_count = models.PositiveIntegerField(
        _('تعداد گزینه‌های تحویلی'),
        null=True,
        blank=True,
        help_text=_('برای نوع تحویل MULTI_CHOICE: چند گزینه به کاربر داده میشه؟')
    )

    # ========== زمان تحویل ==========
    estimated_delivery_days = models.PositiveIntegerField(
        _('مدت آماده سازی'),
        default=5,
        validators=[MinValueValidator(1)],
        help_text=_('حداکثر چند روز کاری طول میکشه تا تحویل داده بشه')
    )

    # ========== وضعیت ==========
    is_active = models.BooleanField(
        _('فعال'),
        default=True,
        help_text=_('آیا این پلن در حال حاضر قابل سفارش هست؟')
    )

    # ========== متادیتا ==========
    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ بروزرسانی'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('پلن خدمت')
        verbose_name_plural = _('پلن‌های خدمات')
        unique_together = [
            ['team', 'service_type', 'name']
        ]
        ordering = ['team', 'service_type', 'price']
        indexes = [
            models.Index(fields=['team', 'service_type', 'is_active']),
            models.Index(fields=['price']),
        ]

    def __str__(self):
        unit_labels = {
            'second': 'ثانیه',
            'minute': 'دقیقه',
            'quantity': 'عدد'
        }
        unit = unit_labels.get(self.pricing_unit, '')

        # نمایش مقدار پایه فقط برای SECOND و MINUTE
        if self.pricing_unit in [self.PricingUnit.SECOND, self.PricingUnit.MINUTE]:
            quantity_str = f" ({self.base_quantity} {unit})"
        else:
            quantity_str = ""

        return f"{self.team.name} - {self.service_type.name} - {self.name}{quantity_str}"

    def clean(self):
        """اعتبارسنجی پلن"""
        super().clean()

        # ========== ۱. اعتبارسنجی واحد ==========
        if self.service_type.allowed_units:
            if self.pricing_unit not in self.service_type.allowed_units:
                raise ValidationError({
                    'pricing_unit': f'واحد "{self.get_pricing_unit_display()}" برای این سرویس مجاز نیست. '
                                    f'واحدهای مجاز: {self.service_type.get_allowed_units_display()}'
                })

        # ========== ۲. اعتبارسنجی مقادیر (فقط برای SECOND و MINUTE) ==========
        if self.pricing_unit in [self.PricingUnit.SECOND, self.PricingUnit.MINUTE]:
            # فیلدها باید پر شده باشند
            if not self.base_quantity:
                raise ValidationError({
                    'base_quantity': 'برای واحد ثانیه/دقیقه، مقدار پایه الزامی است.'
                })
            if not self.min_quantity:
                raise ValidationError({
                    'min_quantity': 'برای واحد ثانیه/دقیقه، حداقل مقدار الزامی است.'
                })

            # اعتبارسنجی مقادیر
            if self.min_quantity > self.base_quantity:
                raise ValidationError({
                    'min_quantity': 'حداقل مقدار نمی‌تواند از مقدار پایه بیشتر باشد.'
                })

            if self.max_quantity and self.max_quantity < self.base_quantity:
                raise ValidationError({
                    'max_quantity': 'حداکثر مقدار نمی‌تواند از مقدار پایه کمتر باشد.'
                })

            if self.max_quantity and self.min_quantity > self.max_quantity:
                raise ValidationError({
                    'min_quantity': 'حداقل مقدار نمی‌تواند از حداکثر مقدار بیشتر باشد.'
                })

        # ========== ۳. اعتبارسنجی برای واحد QUANTITY ==========
        if self.pricing_unit == self.PricingUnit.QUANTITY:
            # فیلدهای quantity نباید پر شوند
            if self.base_quantity:
                raise ValidationError({
                    'base_quantity': 'برای واحد تعدادی، نیازی به مقدار پایه نیست.'
                })
            if self.min_quantity:
                raise ValidationError({
                    'min_quantity': 'برای واحد تعدادی، نیازی به حداقل مقدار نیست.'
                })
            if self.max_quantity:
                raise ValidationError({
                    'max_quantity': 'برای واحد تعدادی، نیازی به حداکثر مقدار نیست.'
                })

            # برای QUANTITY، فقط SINGLE و MULTI_CHOICE مجاز هستن
            if self.delivery_type not in [self.DeliveryType.SINGLE, self.DeliveryType.MULTI_CHOICE]:
                raise ValidationError({
                    'delivery_type': 'برای واحد تعدادی، فقط تحویل یک فایل یا چند گزینه مجاز است.'
                })

        # ========== ۴. اعتبارسنجی تعداد گزینه‌ها ==========
        if self.delivery_type == self.DeliveryType.MULTI_CHOICE:
            if not self.delivery_options_count or self.delivery_options_count < 2:
                raise ValidationError({
                    'delivery_options_count': 'برای تحویل چند گزینه‌ای، حداقل ۲ گزینه باید مشخص شود.'
                })
        else:
            if self.delivery_options_count is not None:
                self.delivery_options_count = None

        # ========== ۵. بررسی تعداد پلن‌های فعال ==========
        active_plans_count = ContentServicePlan.objects.filter(
            team=self.team,
            service_type=self.service_type,
            is_active=True
        ).exclude(pk=self.pk).count()

        if self.is_active and not self.pk:
            if active_plans_count >= 3:
                raise ValidationError(
                    _('هر تیم برای هر خدمت حداکثر می‌تونه ۳ پلن فعال داشته باشه.')
                )
        elif self.is_active and self.pk:
            if active_plans_count > 3:
                raise ValidationError(
                    _('نمیشه بیشتر از ۳ پلن فعال برای یک خدمت داشت.')
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def price_display(self):
        return f"{self.price:,} تومان"

    @property
    def quantity_display(self):
        """نمایش مقدار به صورت خوانا (فقط برای SECOND و MINUTE)"""
        if self.pricing_unit not in [self.PricingUnit.SECOND, self.PricingUnit.MINUTE]:
            return "-"

        unit_labels = {
            'second': 'ثانیه',
            'minute': 'دقیقه',
            'quantity': 'عدد'
        }
        unit = unit_labels.get(self.pricing_unit, '')

        if self.min_quantity == self.base_quantity == (self.max_quantity or self.base_quantity):
            return f"{self.base_quantity} {unit}"
        elif self.max_quantity:
            return f"{self.min_quantity} تا {self.max_quantity} {unit} (پایه: {self.base_quantity})"
        else:
            return f"از {self.min_quantity} {unit} به بالا (پایه: {self.base_quantity})"

    @property
    def delivery_type_display(self):
        labels = {
            'single': 'تحویل یک فایل',
            'multi_choice': f'{self.delivery_options_count or "چند"} گزینه برای انتخاب',
        }
        return labels.get(self.delivery_type, self.delivery_type)

    def get_features_list(self):
        if isinstance(self.features, list):
            return self.features
        elif isinstance(self.features, str):
            try:
                import json
                return json.loads(self.features)
            except:
                return [self.features]
        return []


class ContentOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        REVIEW_PENDING = "review_pending", "در انتظار ویرایش"
        IN_PROGRESS = "in_progress", "در حال انجام"
        DONE = "done", "انجام شده"
        COMPLETED = "completed", "تمام شده"
        CANCELLED = "cancelled", "لغو شده"

    # ========== ارتباطات ==========
    campaign = models.ForeignKey(
        'campaigns.Campaign',
        on_delete=models.CASCADE,
        related_name="content_orders",
        verbose_name="کمپین"
    )

    team = models.ForeignKey(
        ContentTeam,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="تیم تولید محتوا"
    )

    plan = models.ForeignKey(
        ContentServicePlan,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="پلن انتخابی"
    )

    # ========== قیمت ==========
    price = models.PositiveBigIntegerField(
        verbose_name="قیمت",
        help_text='قیمت نهایی از روی پلن کپی می‌شود'
    )

    # ========== مقدار انتخابی کاربر (فقط برای اطلاع) ==========
    selected_quantity = models.PositiveIntegerField(
        _('مقدار انتخابی'),
        null=True,
        blank=True,
        help_text='مقداری که کاربر انتخاب کرده (در صورت قابل تنظیم بودن)'
    )

    # ========== وضعیت ==========
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name="وضعیت"
    )

    # ========== ددلاین ==========
    deadline = jmodels.jDateTimeField(
        verbose_name='ددلاین تحویل',
        null=True,
        blank=True,
        help_text='تاریخ و زمان نهایی تحویل سفارش'
    )

    deadline_timestamp = models.BigIntegerField(
        verbose_name='ددلاین تحویل (Unix Timestamp)',
        null=True,
        blank=True,
        help_text='تایم‌استمپ ددلاین به میلی‌ثانیه'
    )

    # ========== جایگزینی ==========
    replaced_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replaced_orders',
        verbose_name='جایگزین شده توسط'
    )

    replaced_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name='تاریخ جایگزینی'
    )

    # ========== متادیتا ==========
    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="زمان ایجاد"
    )

    class Meta:
        verbose_name = "سفارش تولید محتوا"
        verbose_name_plural = "سفارش‌های تولید محتوا"

    def __str__(self):
        return f'سفارش {self.campaign.name} - {self.team.name}'

    def save(self, *args, **kwargs):
        """قیمت رو مستقیم از پلن میگیره"""
        if self.plan and not self.price:
            self.price = self.plan.price
        super().save(*args, **kwargs)

    def has_selected_file(self):
        """آیا فایلی برای این سفارش انتخاب شده است؟"""
        return self.deliveries.filter(files__is_selected=True).exists()

    def get_selected_file(self):
        """دریافت فایل انتخاب شده برای این سفارش"""
        return self.deliveries.filter(files__is_selected=True).first()


class ContentOrderDescription(models.Model):
    """
    بریف ساختارمند سفارش تولید محتوا
    اطلاعات دقیق‌تر از نیاز کاربر برای تیم تولید محتوا
    """

    class ContentGoal(models.TextChoices):
        PRODUCT_INTRO = 'product_intro', _('معرفی محصول یا خدمت')
        BRAND_AWARENESS = 'brand_awareness', _('افزایش آگاهی از برند')
        SALE_CAMPAIGN = 'sale_campaign', _('کمپین فروش یا تخفیف')
        EDUCATIONAL = 'educational', _('محتوای آموزشی')
        ENGAGEMENT = 'engagement', _('افزایش تعامل مخاطب')
        OTHER = 'other', _('سایر')

    class ContentTone(models.TextChoices):
        FORMAL = 'formal', _('رسمی')
        FRIENDLY = 'friendly', _('صمیمی')
        HUMOROUS = 'humorous', _('طنز')
        EMOTIONAL = 'emotional', _('احساسی')
        MOTIVATIONAL = 'motivational', _('انگیزشی')

    order = models.OneToOneField(
        ContentOrder,
        on_delete=models.CASCADE,
        related_name='brief',
        verbose_name=_('سفارش')
    )

    goal = models.CharField(
        _('هدف محتوا'),
        max_length=50,
        choices=ContentGoal.choices,
    )
    goal_description = models.CharField(
        _('توضیح هدف'),
        max_length=200,
        blank=True, null=True,
        help_text=_('اگر "سایر" انتخاب کردید توضیح دهید')
    )

    tone = models.CharField(
        _('لحن محتوا'),
        max_length=30,
        choices=ContentTone.choices,
    )

    brand_name = models.CharField(
        _('نام برند یا محصول'),
        max_length=100,
    )

    hashtags = models.CharField(
        _('هشتگ‌ها'),
        max_length=500,
        blank=True,
        help_text=_('مثلاً: #برند_من #تخفیف')
    )

    reference_links = models.TextField(
        _('لینک‌های مرجع'),
        blank=True,
        help_text=_('لینک نمونه‌کارهای مشابه که دوست دارید')
    )

    target_audience = models.CharField(
        _('مخاطب هدف'),
        max_length=300,
        blank=True,
        help_text=_('مثلاً: زنان ۲۵-۳۵ ساله علاقه‌مند به مد')
    )

    description = models.TextField(
        _('توضیحات کامل'),
        help_text=_('هر اطلاعات دیگری که تیم باید بداند')
    )

    do_not_include = models.TextField(
        _('چه چیزهایی نباشد؟'),
        blank=True,
        help_text=_('مثلاً: رنگ قرمز، افکت‌های بصری خاص، لوگوی رقبا')
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ثبت'),
        auto_now_add=True
    )
    updated_at = jmodels.jDateTimeField(
        _('تاریخ ویرایش'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('توضیح سفارش')
        verbose_name_plural = _('توضیحات سفارش')

    def __str__(self):
        return f"بریف سفارش {self.order.id}"


class ContentOrderFile(models.Model):
    """
    فایل‌های پیوست سفارش تولید محتوا
    کاربر می‌تواند چندین فایل آپلود کند
    """

    class FileType(models.TextChoices):
        IMAGE = 'image', _('تصویر')
        VIDEO = 'video', _('ویدیو')
        AUDIO = 'audio', _('صدا')
        DOCUMENT = 'document', _('سند')
        OTHER = 'other', _('سایر')

    order = models.ForeignKey(
        ContentOrder,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name=_('سفارش')
    )

    file = models.FileField(
        _('فایل'),
        upload_to=content_order_file_path
    )

    file_type = models.CharField(
        _('نوع فایل'),
        max_length=20,
        choices=FileType.choices,
        default=FileType.OTHER
    )

    original_name = models.CharField(
        _('نام اصلی فایل'),
        max_length=255,
        blank=True
    )

    description = models.CharField(
        _('توضیح فایل'),
        max_length=200,
        blank=True,
        help_text=_('این فایل چیست؟ مثلاً: لوگوی برند')
    )

    file_size = models.PositiveIntegerField(
        _('حجم فایل (بایت)'),
        null=True,
        blank=True
    )

    uploaded_at = jmodels.jDateTimeField(
        _('تاریخ آپلود'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('فایل سفارش')
        verbose_name_plural = _('فایل‌های سفارش')
        ordering = ['uploaded_at']

    def __str__(self):
        return f"فایل {self.original_name} - سفارش {self.order.id}"

    def save(self, *args, **kwargs):
        if self.file and not self.original_name:
            self.original_name = self.file.name.split('/')[-1]
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def file_size_display(self):
        """نمایش حجم فایل به صورت خوانا"""
        if not self.file_size:
            return 'نامشخص'
        size = self.file_size
        for unit in ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} گیگابایت"

    @property
    def mime_type(self):
        mime, _ = mimetypes.guess_type(self.file.name)
        return mime or self.file_type


class TeamReview(models.Model):
    """
    نظرات و امتیازات تیم‌های تولید محتوا
    """
    team = models.ForeignKey(
        ContentTeam,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name=_('تیم')
    )
    order = models.OneToOneField(
        ContentOrder,
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='review',
        verbose_name=_('سفارش')
    )
    advertiser = models.ForeignKey(
        'advertisers.AdvertiserProfile',
        on_delete=models.CASCADE,
        related_name='team_reviews',
        verbose_name=_('تبلیغ‌دهنده')
    )
    rating = models.PositiveSmallIntegerField(
        _('امتیاز'),
        choices=[(i, str(i)) for i in range(1, 6)],
        help_text=_('از 1 تا 5')
    )
    comment = models.TextField(
        _('نظر'),
    )
    created_at = jmodels.jDateTimeField(
        _('تاریخ ثبت'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('نظر درباره تیم')
        verbose_name_plural = _('نظرات درباره تیم‌ها')
        ordering = ['-created_at']

    def __str__(self):
        return f"نظر {self.advertiser.user.nickname} برای {self.team.name} - {self.rating}/5"


class TeamJoinRequest(models.Model):
    """
    مدل درخواست عضویت در تیم تولید محتوا
    """

    class Status(models.TextChoices):
        PENDING = 'pending', _('در انتظار بررسی')
        APPROVED = 'approved', _('تایید شده')
        REJECTED = 'rejected', _('رد شده')

    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='team_join_requests',
        verbose_name=_('کاربر درخواست‌دهنده')
    )

    team = models.ForeignKey(
        ContentTeam,
        on_delete=models.CASCADE,
        related_name='join_requests',
        verbose_name=_('تیم')
    )

    status = models.CharField(
        _('وضعیت'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ درخواست'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('درخواست عضویت در تیم')
        verbose_name_plural = _('درخواست‌های عضویت در تیم')
        ordering = ['-created_at']
        unique_together = ['team', 'user']

    def __str__(self):
        return f"درخواست {self.user.nickname} برای عضویت در {self.team.name} - {self.get_status_display()}"


class ContentOrderRevision(models.Model):
    """
    درخواست ویرایش سفارش تولید محتوا
    کاربر می‌تواند بعد از تحویل، درخواست ویرایش بدهد
    """

    class Status(models.TextChoices):
        PENDING = 'pending', _('در انتظار بررسی')
        ACCEPTED = 'accepted', _('پذیرفته شده')
        REJECTED = 'rejected', _('رد شده')
        DONE = 'done', _('انجام شد')

    order = models.ForeignKey(
        'ContentOrder',
        on_delete=models.CASCADE,
        related_name='revisions',
        verbose_name=_('سفارش')
    )

    requested_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='content_revisions',
        verbose_name=_('درخواست‌کننده')
    )

    feedback = models.TextField(
        _('توضیحات ویرایش'),
        help_text=_('مشخص کنید چه تغییراتی می‌خواهید')
    )

    status = models.CharField(
        _('وضعیت'),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )

    file = models.FileField(
        _('فایل مرجع'),
        upload_to='revision_files/',
        null=True,
        blank=True,
        help_text=_('فایل مرجع برای ویرایش (اختیاری)')
    )

    file_name = models.CharField(
        _('نام فایل'),
        max_length=255,
        blank=True,
        help_text=_('نام اصلی فایل آپلود شده')
    )

    file_size = models.PositiveIntegerField(
        _('حجم فایل (بایت)'),
        null=True,
        blank=True
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ درخواست'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ بروزرسانی'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('درخواست ویرایش')
        verbose_name_plural = _('درخواست‌های ویرایش')
        ordering = ['-created_at']

    def __str__(self):
        return f"ویرایش سفارش {self.order.id} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if self.file and not self.file_name:
            self.file_name = self.file.name.split('/')[-1]
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def file_size_display(self):
        if not self.file_size:
            return 'نامشخص'
        size = self.file_size
        for unit in ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} گیگابایت"


class ContentDelivery(models.Model):
    class DeliveryStatus(models.TextChoices):
        PENDING = 'pending', _('در انتظار تحویل')
        DELIVERED = 'delivered', _('تحویل داده شد')
        REVISION_REQUESTED = 'revision_requested', _('درخواست ویرایش')
        FINAL_ACCEPTED = 'final_accepted', _('تأیید نهایی')

    # ========== ارتباط ==========
    order = models.ForeignKey(
        'ContentOrder',
        on_delete=models.CASCADE,
        related_name='deliveries',
        verbose_name=_('سفارش')
    )

    status = models.CharField(
        _('وضعیت تحویل'),
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True
    )

    # ========== تحویل‌دهنده ==========
    delivered_by = models.ForeignKey(
        ContentTeamMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deliveries',
        verbose_name=_('تحویل‌دهنده')
    )

    delivered_at = jmodels.jDateTimeField(
        _('تاریخ تحویل'),
        null=True,
        blank=True
    )

    notes = models.TextField(
        _('توضیحات تحویل'),
        blank=True,
        help_text=_('توضیحات تکمیلی برای سفارش‌دهنده')
    )

    accepted_at = jmodels.jDateTimeField(
        _('تاریخ تأیید نهایی'),
        null=True,
        blank=True
    )

    version = models.PositiveSmallIntegerField(
        _('نسخه'),
        default=1,
        help_text=_('نسخه تحویل سفارش (۱ برای تحویل اولیه، ۲ برای ویرایش اول، و...)')
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ بروزرسانی'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('تحویل سفارش')
        verbose_name_plural = _('تحویل‌های سفارش')
        ordering = ['-version', '-delivered_at']
        indexes = [
            models.Index(fields=['order', 'version']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"تحویل سفارش {self.order.id} - نسخه {self.version}"

    @property
    def primary_file(self):
        """فایل اصلی (اولین فایل یا گزینه انتخاب شده)"""
        return self.files.filter(is_option=True).first() or self.files.first()

    @property
    def has_multiple_options(self):
        """آیا این تحویل چند گزینه داره؟"""
        return self.files.filter(is_option=True).count() > 1

    @property
    def file_count(self):
        """تعداد فایل‌های این تحویل"""
        return self.files.count()


class ContentDeliveryFile(models.Model):
    """
    فایل‌های یک تحویل سفارش
    هر تحویل می‌تواند چندین فایل داشته باشد
    """
    delivery = models.ForeignKey(
        'ContentDelivery',
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name=_('تحویل')
    )

    file = models.FileField(
        _('فایل'),
        upload_to=content_order_file_path,
        help_text=_('فایل تحویل داده شده توسط تیم')
    )

    file_name = models.CharField(
        _('نام فایل'),
        max_length=255,
        blank=True,
        help_text=_('نام اصلی فایل آپلود شده')
    )

    file_size = models.PositiveIntegerField(
        _('حجم فایل (بایت)'),
        null=True,
        blank=True
    )

    # ===== ✅ فیلدهای جدید =====

    # ۱. آیا این فایل یک گزینه است؟ (برای MULTI_CHOICE)
    is_option = models.BooleanField(
        _('گزینه'),
        default=False,
        help_text='آیا این فایل یکی از گزینه‌های تحویلی است؟ (برای MULTI_CHOICE)'
    )

    # ۲. شماره گزینه (برای MULTI_CHOICE)
    option_number = models.PositiveSmallIntegerField(
        _('شماره گزینه'),
        null=True,
        blank=True,
        help_text='شماره گزینه (۱، ۲، ۳، ...)'
    )

    # ۳. ✅ آیا این فایل توسط تبلیغ‌دهنده انتخاب شده است؟
    is_selected = models.BooleanField(
        _('انتخاب شده'),
        default=False,
        help_text='آیا این فایل توسط تبلیغ‌دهنده به عنوان فایل نهایی انتخاب شده است؟'
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ بروزرسانی'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('فایل تحویل')
        verbose_name_plural = _('فایل‌های تحویل')
        ordering = ['option_number', 'created_at']
        indexes = [
            models.Index(fields=['delivery', 'is_option']),
            models.Index(fields=['option_number']),
            models.Index(fields=['is_selected']),
        ]

    def __str__(self):
        return f"فایل {self.option_number or ''} - {self.file_name}"

    def save(self, *args, **kwargs):
        if self.file and not self.file_name:
            self.file_name = self.file.name.split('/')[-1]
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)

    @property
    def file_size_display(self):
        """نمایش حجم فایل به صورت خوانا"""
        if not self.file_size:
            return 'نامشخص'
        size = self.file_size
        for unit in ['بایت', 'کیلوبایت', 'مگابایت', 'گیگابایت']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} گیگابایت"


class ContentPortfolio(models.Model):
    """
    نمونه کارهای تیم تولید محتوا
    """

    team = models.ForeignKey(
        ContentTeam,
        on_delete=models.CASCADE,
        related_name='portfolio_items',
        verbose_name=_('تیم')
    )

    title = models.CharField(
        _('عنوان'),
        max_length=200,
        help_text=_('مثلاً: ویدیوی معرفی محصول ایکس')
    )

    description = models.TextField(
        _('توضیحات'),
        blank=True,
        help_text=_('توضیح درباره این نمونه کار')
    )

    media = ResizedImageField(
        _('تصویر نمونه کار'),
        upload_to='team_portfolio/',
        size=[800, 800],
        scale=1,
        crop=['middle', 'center'],
        null=True,
        blank=True
    )

    video_url = models.URLField(
        _('لینک ویدیو'),
        blank=True,
        help_text=_('لینک آپارات، یوتیوب، ویمئو و...')
    )

    external_link = models.URLField(
        _('لینک خارجی'),
        blank=True,
        help_text=_('لینک به نمونه کار در سایت دیگر')
    )

    service_type = models.ForeignKey(
        ContentServiceType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='portfolio_items',
        verbose_name=_('نوع خدمت')
    )

    display_order = models.PositiveSmallIntegerField(
        _('ترتیب نمایش'),
        default=0
    )

    is_active = models.BooleanField(
        _('فعال'),
        default=True
    )

    created_at = jmodels.jDateTimeField(
        _('تاریخ ایجاد'),
        auto_now_add=True
    )

    updated_at = jmodels.jDateTimeField(
        _('تاریخ ویرایش'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('نمونه کار')
        verbose_name_plural = _('نمونه کارها')
        ordering = ['display_order', '-created_at']

    def __str__(self):
        return f"{self.team.name} - {self.title}"
