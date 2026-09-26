from django.conf import settings
from django.db import models
from django_jalali.db import models as jmodels


class Brand(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='social_brands',
        verbose_name='مالک',
    )
    name = models.CharField('نام برند', max_length=200)
    website = models.URLField('وب‌سایت', blank=True)
    created_at = jmodels.jDateTimeField('زمان ایجاد', auto_now_add=True)

    class Meta:
        verbose_name = 'برند'
        verbose_name_plural = 'برندها'

    def __str__(self):
        return self.name


class SocialAccount(models.Model):
    class Status(models.TextChoices):
        DISCONNECTED = 'disconnected', 'متصل نیست'
        CONNECTED = 'connected', 'متصل'
        REAUTH_REQUIRED = 'reauth_required', 'نیازمند اتصال دوباره'

    brand = models.ForeignKey(
        Brand,
        on_delete=models.CASCADE,
        related_name='social_accounts',
        verbose_name='برند',
    )
    platform = models.CharField('پلتفرم', max_length=30, default='instagram')
    username = models.CharField('نام کاربری', max_length=100)
    external_id = models.CharField(
        'شناسه حساب در پلتفرم', max_length=100, blank=True, null=True, unique=True,
    )
    status = models.CharField(
        'وضعیت اتصال', max_length=20, choices=Status.choices,
        default=Status.DISCONNECTED,
    )
    created_at = jmodels.jDateTimeField('زمان ایجاد', auto_now_add=True)
    updated_at = jmodels.jDateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'حساب شبکه اجتماعی'
        verbose_name_plural = 'حساب‌های شبکه اجتماعی'
        constraints = [
            models.UniqueConstraint(
                fields=['brand', 'platform', 'username'],
                name='social_account_brand_platform_username_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.username} ({self.platform})'


class ContentDraft(models.Model):
    class Format(models.TextChoices):
        POST = 'post', 'پست'
        CAROUSEL = 'carousel', 'اسلایدی'
        REEL = 'reel', 'ریلز'
        STORY = 'story', 'استوری'

    class Status(models.TextChoices):
        IDEA = 'idea', 'ایده'
        DRAFT = 'draft', 'پیش‌نویس'
        REVIEW = 'review', 'در انتظار بررسی'
        APPROVED = 'approved', 'تأیید شده'

    brand = models.ForeignKey(
        Brand, on_delete=models.CASCADE, related_name='content_drafts',
        verbose_name='برند',
    )
    title = models.CharField('عنوان داخلی', max_length=200)
    content_format = models.CharField(
        'قالب محتوا', max_length=12, choices=Format.choices,
    )
    objective = models.CharField('هدف محتوا', max_length=200, blank=True)
    idea = models.TextField('شرح ایده', blank=True)
    hook = models.TextField('جمله شروع', blank=True)
    caption = models.TextField('کپشن', blank=True)
    call_to_action = models.TextField('دعوت به اقدام', blank=True)
    hashtags = models.TextField('هشتگ‌ها', blank=True)
    planned_for = jmodels.jDateTimeField('زمان پیشنهادی انتشار', null=True, blank=True)
    status = models.CharField(
        'وضعیت', max_length=12, choices=Status.choices,
        default=Status.IDEA,
    )
    created_at = jmodels.jDateTimeField('زمان ایجاد', auto_now_add=True)
    updated_at = jmodels.jDateTimeField('آخرین ویرایش', auto_now=True)

    class Meta:
        verbose_name = 'پیش‌نویس شبکه اجتماعی'
        verbose_name_plural = 'پیش‌نویس‌های شبکه اجتماعی'
        ordering = ('planned_for', '-created_at')
        indexes = [
            models.Index(
                fields=['brand', 'status', 'planned_for'],
                name='social_mana_brand_i_878a34_idx',
            ),
        ]

    def __str__(self):
        return self.title
