from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels
from core.utils.utils import generate_random_slug
from django.urls import reverse
from django.db import models


class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=Post.Status.PUBLISHED)


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = '0', 'Draft'
        PUBLISHED = '1', 'Published'
        REJECTED = '-1', 'Rejected'

    user = models.ForeignKey("accounts.CustomUser", on_delete=models.CASCADE, related_name='posts', verbose_name=_('کاربر'))
    title = models.CharField(_('عنوان'), max_length=200)
    content = models.TextField(_('متن'))
    slug = models.SlugField()
    image = models.ImageField(_('تصویر'), upload_to=f'blog/', null=True, blank=True)
    read_time = models.PositiveIntegerField(_('زمان مطالعه (دقیقه)'), help_text=_('زمان تخمینی مطالعه بلاگ به دقیقه'))
    tags = models.ManyToManyField("BlogTags", related_name='posts', blank=True, verbose_name=_('برچسب'))
    category = models.ForeignKey("BlogCategory",on_delete=models.CASCADE, related_name='posts', blank=True, verbose_name=_('دسته بندی'))
    status = models.CharField(max_length=2, choices=Status.choices, default=Status.DRAFT, verbose_name=_('وضعیت'))
    created_at = jmodels.jDateTimeField(_('تاریخ ساخت'), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_('تاریخ ویرایش'), auto_now=True)

    objects = models.Manager()
    published = PublishedManager()

    def comment_count(self):
        return self.comments.count()


    def get_absolute_url(self):
        return reverse('blog:detail', args=[self.id, self.slug])


    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_random_slug()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('پست')
        verbose_name_plural = _('پست ها')
        ordering = ['-created_at']


class PostComments(models.Model):
    user = models.ForeignKey("accounts.CustomUser", on_delete=models.CASCADE, related_name='post_comments',
                             verbose_name=_('کاربر'), null=True, blank=True)
    name = models.CharField(_('نام'), max_length=70, null=True, blank=True)
    post = models.ForeignKey('Post', on_delete=models.CASCADE, related_name="comments", verbose_name=_('پست'))
    content = models.TextField(_('متن'), max_length=1500)
    created_at = jmodels.jDateTimeField(_('تاریخ ساخت'), auto_now_add=True)
    parent_comment = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies',
                                       verbose_name=_('پاسخ به'))
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = self.user.nickname
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.post.title} - {self.name}"

    class Meta:
        verbose_name = _('نظر پست')
        verbose_name_plural = _('نظرات پست')
        ordering = ['-created_at']


class BlogTags(models.Model):
    name = models.CharField(_('برچسب'), max_length=150)
    slug = models.SlugField()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_random_slug()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('برچسب بلاگ')
        verbose_name_plural = _('برچسب های بلاگ')


class BlogCategory(models.Model):
    name = models.CharField(_('دسته بندی'), max_length=150)
    slug = models.SlugField()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_random_slug()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('دسته بندی بلاگ')
        verbose_name_plural = _('دسته بندی های بلاگ')
