from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from django_jalali.db import models as jmodels
from django_resized import ResizedImageField
from django.utils import timezone
from django.db import models


class SupplierProfile(models.Model):
    """پروفایل تامین‌کننده - فقط برای کاربرانی که market_role=SUPPLIER دارن"""
    user = models.OneToOneField("accounts.CustomUser", on_delete=models.CASCADE, related_name="supplier_profile",
                                verbose_name=_("کاربر"))
    brand_name = models.CharField(_("نام برند/شرکت"), max_length=100)
    contact_phone = models.CharField(_("شماره تماس"), max_length=11)
    address = models.TextField(_("آدرس مبدا ارسال"), blank=True)
    description = models.TextField(_("توضیحات"), blank=True)
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        verbose_name = _("تامین‌کننده")
        verbose_name_plural = _("تامین‌کنندگان")

    def __str__(self):
        return f"{self.brand_name} ({self.user.phone_number})"


class ShippingMethod(models.Model):
    """
    روش ارسال — توسط ادمین مدیریت می‌شه
    seed شده با: پست پیشتاز، تیپاکس
    """
    name = models.CharField(_("نام روش ارسال"), max_length=50, unique=True)
    slug = models.SlugField(_("اسلاگ"), max_length=50, unique=True, allow_unicode=True)
    icon = models.CharField(_("آیکون Bootstrap"), max_length=50, blank=True, help_text=_("کلاس آیکون مثل bi-truck"), )
    description = models.CharField(_("توضیح کوتاه"), max_length=200, blank=True,
                                   help_text=_("مثلاً: ارسال عادی ۳ تا ۵ روز کاری"), )
    order = models.PositiveSmallIntegerField(_("ترتیب نمایش"), default=0)
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        verbose_name = _("روش ارسال")
        verbose_name_plural = _("روش‌های ارسال")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    """محصول - هر محصول مال یه تامین‌کننده‌ست"""

    class Status(models.TextChoices):
        DRAFT = 'draft', _('پیش‌نویس')
        ACTIVE = 'active', _('فعال')  # یعنی الان توی چرخه ۳ روزه‌ست
        SCHEDULED = 'scheduled', _('زمان‌بندی شده')
        INACTIVE = 'inactive', _('غیرفعال')
        SOLD_OUT = 'sold_out', _('ناموجود')

    supplier = models.ForeignKey('SupplierProfile', on_delete=models.PROTECT, related_name="products",
                                 verbose_name=_("تامین‌کننده"), null=True, blank=True)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True, related_name="products",
                                 verbose_name=_("دسته‌بندی"), )
    title = models.CharField(_("نام محصول"), max_length=200)
    slug = models.SlugField(_("اسلاگ"), max_length=200, unique=True, allow_unicode=True)
    description = models.TextField(_("توضیحات"), blank=True)
    short_description = models.CharField(_("توضیح کوتاه"), max_length=300, blank=True)
    base_price = models.PositiveIntegerField(_("قیمت پایه (تومان)"))
    discount_price = models.PositiveIntegerField(_("قیمت با تخفیف"), null=True, blank=True)
    stock = models.PositiveIntegerField(_("موجودی انبار"), default=0)
    main_image = ResizedImageField(_("تصویر اصلی"), upload_to="market/products/", size=[800, 800], quality=85,
                                   null=True, blank=True)
    status = models.CharField(_("وضعیت"), max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    campaign_start = jmodels.jDateTimeField(_("شروع فروش"), null=True, blank=True)
    campaign_end = jmodels.jDateTimeField(_("پایان فروش"), null=True, blank=True)
    shipping_methods = models.ManyToManyField("ShippingMethod", blank=True, related_name="products", verbose_name=_("روش‌های ارسال"), help_text=_("روش‌هایی که این محصول پشتیبانی می‌کند"))
    view_count = models.PositiveIntegerField(_("تعداد بازدید"), default=0)
    sold_count = models.PositiveIntegerField(_("تعداد فروش"), default=0)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        verbose_name = _("محصول")
        verbose_name_plural = _("محصولات")
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.status == self.Status.ACTIVE:
            # بقیه محصولات فعال رو غیرفعال کن
            Product.objects.filter(
                status=self.Status.ACTIVE
            ).exclude(pk=self.pk).update(status=self.Status.INACTIVE)
        super().save(*args, **kwargs)

    @property
    def final_price(self):
        return self.discount_price or self.base_price

    @property
    def discount_percent(self):
        if self.discount_price and self.base_price:
            return int((1 - self.discount_price / self.base_price) * 100)
        return 0

    @property
    def is_on_campaign(self):
        """آیا الان توی چرخه فروشه؟"""
        now = timezone.now()
        return (
                self.status == self.Status.ACTIVE
                and self.campaign_start and self.campaign_end
                and self.campaign_start <= now <= self.campaign_end
        )

    @property
    def remaining_time(self):
        """ثانیه‌های باقی‌مونده تا پایان کمپین"""
        if self.is_on_campaign:
            return int((self.campaign_end - timezone.now()).total_seconds())
        return 0


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images", verbose_name=_("محصول"))
    image = ResizedImageField(_("تصویر"), upload_to="market/products/gallery/", size=[800, 800], quality=85)
    alt_text = models.CharField(_("متن جایگزین"), max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(_("ترتیب"), default=0)

    class Meta:
        verbose_name = _("تصویر محصول")
        verbose_name_plural = _("تصاویر محصول")
        ordering = ['order']


class Feature(models.Model):
    """ویژگی‌های قابل استفاده برای محصولات (مثل رنگ، جنس، وزن و...)"""
    name = models.CharField(_("نام ویژگی"), max_length=50, unique=True)
    slug = models.SlugField(_("اسلاگ"), max_length=50, unique=True)
    unit = models.CharField(_("واحد"), max_length=20, blank=True)

    class Meta:
        verbose_name = _("ویژگی")
        verbose_name_plural = _("ویژگی‌ها")

    def __str__(self):
        return self.name


class ProductFeature(models.Model):
    """مقدار یه ویژگی خاص برای یه محصول خاص"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="features")
    feature = models.ForeignKey(Feature, on_delete=models.PROTECT)
    value = models.CharField(_("مقدار"), max_length=100)

    class Meta:
        verbose_name = _("ویژگی محصول")
        verbose_name_plural = _("ویژگی‌های محصول")
        unique_together = ('product', 'feature')


class Variant(models.Model):
    """تنوع محصول - مثلاً قرمز سایز M با ۵ تا موجودی"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    attributes = models.JSONField(_("ویژگی‌ها"), default=dict)
    sku = models.CharField(_("کد کالا"), max_length=50, unique=True, blank=True)
    price = models.PositiveIntegerField(_("قیمت"), null=True, blank=True)  # اگه متفاوت از محصول
    stock = models.PositiveIntegerField(_("موجودی"), default=0)
    image = ResizedImageField(_("تصویر"), upload_to="market/variants/", size=[600, 600], null=True, blank=True)
    is_active = models.BooleanField(_("فعال"), default=True)

    class Meta:
        verbose_name = _("تنوع محصول")
        verbose_name_plural = _("تنوع‌های محصول")

    def __str__(self):
        attrs = ", ".join(f"{k}: {v}" for k, v in self.attributes.items())
        return f"{self.product.title} - {attrs}"

    def save(self, *args, **kwargs):
        if not self.sku:
            import uuid
            self.sku = f"WM-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def final_price(self):
        return self.price or self.product.final_price

    @property
    def in_stock(self):
        return self.stock > 0


class Cart(models.Model):
    user = models.OneToOneField("accounts.CustomUser", on_delete=models.CASCADE, related_name="cart", null=True,
                                blank=True)
    session_key = models.CharField(_("کلید سشن"), max_length=40, blank=True)
    created_at = jmodels.jDateTimeField(auto_now_add=True)
    updated_at = jmodels.jDateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("سبد خرید")
        verbose_name_plural = _("سبدهای خرید")

    @property
    def total_price(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def items_count(self):
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveSmallIntegerField(_("تعداد"), default=1)
    added_at = jmodels.jDateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("آیتم سبد")
        verbose_name_plural = _("آیتم‌های سبد")

    @property
    def unit_price(self):
        return self.variant.final_price if self.variant else self.product.final_price

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


class OrderAddress(models.Model):
    """
    Snapshot آدرس در لحظه ثبت سفارش

    - این مدل هیچ‌وقت بعد از ثبت ویرایش نمی‌شه
    - حتی اگه کاربر Address اصلی رو ویرایش/حذف کنه، این دست‌نخورده می‌مونه
    """

    order = models.OneToOneField(
        "Order",
        on_delete=models.CASCADE,
        related_name="order_address",
        verbose_name=_("سفارش"),
        null=True, blank=True,
    )
    source_address = models.ForeignKey(
        "accounts.Address",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="order_snapshots",
        verbose_name=_("آدرس مبدا در دفترچه"),
    )

    # ========== اطلاعات گیرنده ==========
    receiver_name = models.CharField(_("نام گیرنده"), max_length=100)
    receiver_phone = models.CharField(_("شماره تماس گیرنده"), max_length=11)

    # ========== آدرس ==========
    province = models.ForeignKey(
        "core.Province",
        on_delete=models.PROTECT,
        related_name="order_addresses",
        verbose_name=_("استان"),
    )
    city = models.ForeignKey(
        "core.City",
        on_delete=models.PROTECT,
        related_name="order_addresses",
        verbose_name=_("شهر"),
    )
    address = models.TextField(_("آدرس دقیق"))
    plaque = models.CharField(_("پلاک"), max_length=10, blank=True)
    unit = models.CharField(_("واحد"), max_length=10, blank=True)
    postal_code = models.CharField(_("کد پستی"), max_length=10, blank=True)

    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        verbose_name = _("آدرس سفارش")
        verbose_name_plural = _("آدرس‌های سفارشات")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.receiver_name} — {self.province.name} / {self.city.name}"

    @property
    def full_address(self):
        """آدرس یک خطی برای نمایش/چاپ"""
        parts = [self.province.name, self.city.name, self.address]
        if self.plaque:
            parts.append(f"پلاک {self.plaque}")
        if self.unit:
            parts.append(f"واحد {self.unit}")
        if self.postal_code:
            parts.append(f"کدپستی {self.postal_code}")
        return ' — '.join(parts)

    @classmethod
    def from_user_address(cls, user_address, receiver_name=None, receiver_phone=None):
        """
        ساخت snapshot از یه Address کاربر
        اگه receiver_name/phone ندی، از خود کاربر می‌گیره
        """
        return cls(
            source_address=user_address,
            receiver_name=receiver_name or user_address.user.nickname or user_address.user.phone_number,
            receiver_phone=receiver_phone or user_address.user.phone_number,
            province=user_address.province,
            city=user_address.city,
            address=user_address.address,
            plaque=user_address.plaque,
            unit=user_address.unit,
            postal_code=user_address.postal_code,
        )


class OrderShipping(models.Model):
    """
    روش ارسال انتخاب‌شده برای هر فروشنده در یک سفارش (snapshot)
    """
    order = models.ForeignKey(
        "Order",
        on_delete=models.CASCADE,
        related_name="shippings",
        verbose_name=_("سفارش"),
    )
    supplier = models.ForeignKey(
        "SupplierProfile",
        on_delete=models.PROTECT,
        related_name="order_shippings",
        verbose_name=_("فروشنده"),
    )
    shipping_method = models.ForeignKey(
        "ShippingMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_shippings",
        verbose_name=_("روش ارسال"),
    )
    # ---- Snapshot ----
    method_name = models.CharField(_("نام روش ارسال"), max_length=50)
    method_slug = models.CharField(_("اسلاگ روش ارسال"), max_length=50, blank=True)

    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        verbose_name = _("ارسال سفارش")
        verbose_name_plural = _("ارسال‌های سفارش")
        unique_together = [["order", "supplier"]]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.order} — {self.supplier} — {self.method_name}"


class Order(models.Model):
    """
    سفارش وین مارکت

    معماری:
    - آدرس → در OrderAddress (snapshot، غیرقابل ویرایش)
    - مبالغ، درگاه، ref_id، تاریخ پرداخت → در Invoice / Payment / Transaction
    - شماره نمایشی سفارش از Invoice.invoice_number میاد
    """

    class Status(models.TextChoices):
        PENDING = 'pending', _('در انتظار پرداخت')
        PAID = 'paid', _('پرداخت شده')
        PROCESSING = 'processing', _('در حال آماده‌سازی')
        SHIPPED = 'shipped', _('ارسال شده')
        DELIVERED = 'delivered', _('تحویل داده شده')
        CANCELED = 'canceled', _('لغو شده')
        RETURNED = 'returned', _('مرجوع شده')

    # ========== کاربر و وضعیت ==========
    user = models.ForeignKey("accounts.CustomUser", on_delete=models.PROTECT, related_name="orders",
                             verbose_name=_("کاربر"))
    status = models.CharField(_("وضعیت"), max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

    # ========== ارسال ==========
    tracking_code = models.CharField(_("کد رهگیری مرسوله"), max_length=100, blank=True)
    shipped_at = jmodels.jDateTimeField(_("زمان ارسال"), null=True, blank=True)
    delivered_at = jmodels.jDateTimeField(_("زمان تحویل"), null=True, blank=True)
    delivered_confirmed_at = jmodels.jDateTimeField(_("زمان تایید دریافت توسط مشتری"), null=True, blank=True,)
    supplier_payment_released_at = jmodels.jDateTimeField(_("زمان واریز به فروشنده"), null=True, blank=True, help_text=_("بعد از تایید دریافت، پول به کیف پول فروشنده واریز می‌شود"),)

    # ========== یادداشت ==========
    customer_note = models.TextField(_("یادداشت مشتری"), blank=True)
    admin_note = models.TextField(_("یادداشت ادمین"), blank=True)

    # ========== تاریخ ==========
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        verbose_name = _("سفارش")
        verbose_name_plural = _("سفارشات")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        return self.number or f"WM-{self.pk}"

    # ============================================================
    # Shortcut properties به OrderAddress
    # ============================================================

    @property
    def receiver_name(self):
        return self.order_address.receiver_name if self.order_address else ''

    @property
    def receiver_phone(self):
        return self.order_address.receiver_phone if self.order_address else ''

    @property
    def province(self):
        return self.order_address.province if self.order_address else None

    @property
    def city(self):
        return self.order_address.city if self.order_address else None

    @property
    def address(self):
        return self.order_address.address if self.order_address else ''

    @property
    def postal_code(self):
        return self.order_address.postal_code if self.order_address else ''

    @property
    def full_address(self):
        return self.order_address.full_address if self.order_address else ''

    # ============================================================
    # Properties — همه از Invoice / Payment خونده می‌شن
    # ============================================================

    @property
    def number(self):
        """شماره نمایشی سفارش — از فاکتور میاد"""
        inv = getattr(self, 'invoice', None)
        return inv.invoice_number if inv else None

    @property
    def items_total(self):
        """جمع کالاها (قبل از ارسال و تخفیف) — از فاکتور میاد"""
        inv = getattr(self, 'invoice', None)
        return inv.items_total if inv else 0

    @property
    def shipping_cost(self):
        """هزینه ارسال — از فاکتور میاد"""
        inv = getattr(self, 'invoice', None)
        return inv.shipping_cost if inv else 0

    @property
    def discount_amount(self):
        """تخفیف — از فاکتور میاد"""
        inv = getattr(self, 'invoice', None)
        return inv.discount_amount if inv else 0

    @property
    def total_amount(self):
        """مبلغ نهایی قابل پرداخت — از فاکتور میاد"""
        inv = getattr(self, 'invoice', None)
        return inv.payable_amount if inv else 0

    @property
    def is_paid(self):
        """آیا سفارش پرداخت شده؟"""
        return self.status in [
            self.Status.PAID,
            self.Status.PROCESSING,
            self.Status.SHIPPED,
            self.Status.DELIVERED,
        ]

    def _get_successful_payment(self):
        """پرداخت موفق این سفارش (اگه وجود داشته باشه)"""
        inv = getattr(self, 'invoice', None)
        if not inv:
            return None
        return (
            inv.payments
            .filter(status='success')
            .order_by('-created_at')
            .first()
        )

    @property
    def paid_at(self):
        """زمان پرداخت — از Payment موفق میاد"""
        payment = self._get_successful_payment()
        return payment.created_at if payment else None

    @property
    def payment_gateway(self):
        """درگاه پرداخت — از Payment موفق میاد"""
        payment = self._get_successful_payment()
        return payment.payment_method if payment else ''

    @property
    def payment_ref_id(self):
        """شماره پیگیری پرداخت — از Payment موفق میاد"""
        payment = self._get_successful_payment()
        return payment.ref_id if payment else ''


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(Variant, on_delete=models.PROTECT, null=True, blank=True)
    product_title = models.CharField(_("نام محصول"), max_length=200)
    variant_info = models.CharField(_("اطلاعات تنوع"), max_length=200, blank=True)
    unit_price = models.PositiveIntegerField(_("قیمت واحد"))
    quantity = models.PositiveSmallIntegerField(_("تعداد"))
    subtotal = models.PositiveIntegerField(_("جمع"))
    supplier = models.ForeignKey(SupplierProfile, on_delete=models.PROTECT, null=True, blank=True,
                                 verbose_name=_("تامین‌کننده"))

    class Meta:
        verbose_name = _("آیتم سفارش")
        verbose_name_plural = _("آیتم‌های سفارش")


class Review(models.Model):
    """نظرات و امتیازهای کاربران"""
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews", verbose_name=_("محصول"), )
    user = models.ForeignKey("accounts.CustomUser", on_delete=models.CASCADE, related_name="reviews",
                             verbose_name=_("کاربر"), )
    rating = models.PositiveSmallIntegerField(_("امتیاز"), choices=RATING_CHOICES, )
    comment = models.TextField(_("نظر"), max_length=1500)
    is_verified_buyer = models.BooleanField(_("خریدار تایید شده"), default=False, )
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)

    class Meta:
        verbose_name = _("نظر")
        verbose_name_plural = _("نظرات")
        ordering = ["-created_at"]
        unique_together = ("product", "user")

    def __str__(self):
        return f"{self.user} → {self.product} ({self.rating}⭐)"


class Category(models.Model):
    """دسته‌بندی محصولات"""
    name = models.CharField(_("نام دسته"), max_length=50, unique=True)
    slug = models.SlugField(_("اسلاگ"), max_length=50, unique=True, allow_unicode=True)
    icon = models.CharField(_("آیکون Bootstrap"), max_length=50, blank=True,
                            help_text=_("کلاس آیکون Bootstrap مثل bi-phone"), )
    order = models.PositiveSmallIntegerField(_("ترتیب"), default=0)
    is_active = models.BooleanField(_("فعال"), default=True)
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)

    class Meta:
        verbose_name = _("دسته‌بندی")
        verbose_name_plural = _("دسته‌بندی‌ها")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


import uuid


class GuestOrder(models.Model):
    """
    سفارش مهمان — بدون نیاز به لاگین یا سبد خرید
    برای پرداخت اقساطی از طریق درگاه مینی‌پی
    """

    class Status(models.TextChoices):
        PENDING = 'pending', _('در انتظار شروع پرداخت')
        INQUIRY_OK = 'inquiry_ok', _('استعلام موفق')
        AWAITING_OTP = 'awaiting_otp', _('در انتظار رمز خرید')
        PAID = 'paid', _('پرداخت شده')
        PROCESSING = 'processing', _('در حال آماده‌سازی')
        SHIPPED = 'shipped', _('ارسال شده')
        DELIVERED = 'delivered', _('تحویل داده شده')
        CANCELED = 'canceled', _('لغو شده')
        FAILED = 'failed', _('ناموفق')

    class Source(models.TextChoices):
        WEBSITE = 'website', _('وب‌سایت')
        BALE_BOT = 'bale_bot', _('بات بله')

    # ========== شناسه ==========
    order_number = models.CharField(
        _("شماره سفارش"), max_length=20, unique=True, editable=False,
        db_index=True,
    )

    # ========== محصول (snapshot) ==========
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="guest_orders",
        verbose_name=_("محصول"),
    )
    product_title = models.CharField(_("نام محصول (در لحظه سفارش)"), max_length=200)
    unit_price = models.PositiveIntegerField(_("قیمت واحد (در لحظه سفارش)"))
    quantity = models.PositiveSmallIntegerField(_("تعداد"), default=1)
    total_amount = models.PositiveIntegerField(_("مبلغ کل"))

    # ========== هویت خریدار (برای احراز مینی‌پی) ==========
    phone_number = models.CharField(_("شماره تلفن همراه"), max_length=11, db_index=True)
    national_id = models.CharField(_("کد ملی"), max_length=10, db_index=True)
    receiver_name = models.CharField(_("نام گیرنده"), max_length=100)

    # ========== آدرس ==========
    province = models.ForeignKey(
        "core.Province", on_delete=models.PROTECT,
        related_name="guest_orders", verbose_name=_("استان"),
    )
    city = models.ForeignKey(
        "core.City", on_delete=models.PROTECT,
        related_name="guest_orders", verbose_name=_("شهر"),
    )
    address = models.TextField(_("آدرس دقیق"))
    postal_code = models.CharField(_("کد پستی"), max_length=10, blank=True)

    # ========== پرداخت مینی‌پی ==========
    status = models.CharField(
        _("وضعیت"), max_length=20,
        choices=Status.choices, default=Status.PENDING, db_index=True,
    )

    source = models.CharField(
        _("منبع سفارش"), max_length=20,
        choices=Source.choices, default=Source.WEBSITE, db_index=True,
    )

    inquiry_id = models.CharField(_("شناسه استعلام"), max_length=100, blank=True)
    pre_transaction_id = models.CharField(_("شناسه پیش‌تراکنش"), max_length=100, blank=True)
    transaction_id = models.CharField(_("شناسه تراکنش"), max_length=100, blank=True)
    payment_ref_id = models.CharField(_("شماره پیگیری"), max_length=100, blank=True)
    payment_error = models.TextField(_("خطای پرداخت"), blank=True)

    # ========== زمان‌ها ==========
    created_at = jmodels.jDateTimeField(_("تاریخ ایجاد"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("تاریخ ویرایش"), auto_now=True)
    paid_at = jmodels.jDateTimeField(_("زمان پرداخت"), null=True, blank=True)

    class Meta:
        verbose_name = _("سفارش مهمان")
        verbose_name_plural = _("سفارشات مهمان")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['national_id']),
        ]

    def __str__(self):
        return f"{self.order_number} — {self.product_title}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            # مثلاً GO-7A3F2B
            self.order_number = f"GO-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    @property
    def full_address(self):
        parts = [self.province.name, self.city.name, self.address]
        if self.postal_code:
            parts.append(f"کدپستی {self.postal_code}")
        return ' — '.join(parts)

    @property
    def is_paid(self):
        return self.status in [
            self.Status.PAID,
            self.Status.PROCESSING,
            self.Status.SHIPPED,
            self.Status.DELIVERED,
        ]


class SupportOrderRequest(models.Model):
    """
    درخواست تماس برای ثبت سفارش توسط پشتیبان
    کاربر در مودال شماره + کد ملی وارد می‌کنه → اینجا ذخیره می‌شه → کارشناس تماس می‌گیره
    """

    class Status(models.TextChoices):
        PENDING = 'pending', _('در انتظار تماس')
        CONTACTED = 'contacted', _('تماس گرفته شد')
        ORDERED = 'ordered', _('سفارش ثبت شد')
        CANCELED = 'canceled', _('لغو شده')
        UNREACHABLE = 'unreachable', _('پاسخگو نبود')

    # ========== محصول مرتبط (اختیاری) ==========
    product = models.ForeignKey(
        "Product", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="support_order_requests",
        verbose_name=_("محصول مرتبط"),
    )

    # ========== اطلاعات تماس ==========
    phone_number = models.CharField(
        _("شماره تلفن همراه"), max_length=11, db_index=True,
    )
    national_id = models.CharField(
        _("کد ملی"), max_length=10, db_index=True,
    )

    # ========== وضعیت و یادداشت ==========
    status = models.CharField(
        _("وضعیت"), max_length=20,
        choices=Status.choices, default=Status.PENDING, db_index=True,
    )
    admin_note = models.TextField(
        _("یادداشت ادمین"), blank=True,
        help_text=_("نتیجه تماس، مشکلات و ..."),
    )

    # ========== اطلاعات تکمیلی (برای پیگیری/ضد اسپم) ==========
    source_ip = models.GenericIPAddressField(
        _("آی‌پی مبدا"), null=True, blank=True,
    )
    user_agent = models.CharField(
        _("مرورگر کاربر"), max_length=255, blank=True,
    )

    # ========== زمان‌ها ==========
    created_at = jmodels.jDateTimeField(_("تاریخ درخواست"), auto_now_add=True)
    updated_at = jmodels.jDateTimeField(_("آخرین ویرایش"), auto_now=True)
    contacted_at = jmodels.jDateTimeField(
        _("زمان تماس"), null=True, blank=True,
    )

    class Meta:
        verbose_name = _("درخواست تماس پشتیبان")
        verbose_name_plural = _("درخواست‌های تماس پشتیبان")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['phone_number', '-created_at']),
            models.Index(fields=['national_id']),
        ]

    def __str__(self):
        return f"{self.phone_number} — {self.get_status_display()}"
