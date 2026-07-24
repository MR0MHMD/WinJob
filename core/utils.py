import random
import string
from jdatetime import datetime as jdatetime
import jdatetime
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
import os
from PIL import Image, ImageDraw
import logging

logger = logging.getLogger(__name__)


def generate_random_slug():
    """تولید اسلاگ تصادفی ۱۴ کاراکتری"""
    from content_team.models import ContentTeam
    characters = string.ascii_letters + string.digits
    while True:
        slug_candidate = ''.join(random.choices(characters, k=14))
        if not ContentTeam.objects.filter(slug=slug_candidate).exists():
            return slug_candidate


def convert_to_jalali(date_obj):
    """تبدیل تاریخ میلادی به شمسی"""
    if not date_obj:
        return None
    try:
        if hasattr(date_obj, 'date'):
            date_obj = date_obj.date()
        return jdatetime.date.fromgregorian(date=date_obj)
    except Exception as e:
        return None


def format_jalali_date(date, format_str='%Y/%m/%d'):
    """فرمت کردن تاریخ شمسی"""
    jalali_date = convert_to_jalali(date)
    if jalali_date:
        return jalali_date.strftime(format_str)
    return '-'


def create_gradient_on_black_pixels(qr_image, color1, color2, direction='diagonal'):
    """
    فقط روی پیکسل‌های مشکی QR Code گرادیانت اعمال کن

    Args:
        qr_image (Image): تصویر QR Code (RGBA)
        color1 (tuple): رنگ شروع (R, G, B)
        color2 (tuple): رنگ پایان (R, G, B)
        direction (str): جهت گرادیانت ('horizontal', 'vertical', 'diagonal')

    Returns:
        Image: QR Code با گرادیانت روی خطوط
    """
    # تبدیل به RGBA
    if qr_image.mode != 'RGBA':
        qr_image = qr_image.convert('RGBA')

    width, height = qr_image.size

    # گرفتن دیتای پیکسل‌ها
    pixels = qr_image.load()

    # پیدا کردن محدوده پیکسل‌های مشکی (برای محاسبه گرادیانت)
    # پیدا کردن min/max ایکس و ایگرگ پیکسل‌های مشکی
    min_x, min_y = width, height
    max_x, max_y = 0, 0
    black_pixels = []

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            # اگر پیکسل مشکی است (یا خیلی تیره) و شفاف نیست
            if a > 128 and (r < 50 and g < 50 and b < 50):
                black_pixels.append((x, y))
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y

    # اگر هیچ پیکسل مشکی‌ای نبود، برگردون تصویر اصلی
    if not black_pixels:
        return qr_image

    # محاسبه محدوده
    range_x = max_x - min_x
    range_y = max_y - min_y

    # اعمال گرادیانت روی پیکسل‌های مشکی
    for x, y in black_pixels:
        # محاسبه نسبت بر اساس موقعیت
        if direction == 'horizontal':
            ratio = (x - min_x) / range_x if range_x > 0 else 0
        elif direction == 'vertical':
            ratio = (y - min_y) / range_y if range_y > 0 else 0
        else:  # diagonal
            ratio = ((x - min_x) + (y - min_y)) / (range_x + range_y) if (range_x + range_y) > 0 else 0

        # محاسبه رنگ جدید
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)

        # اعمال رنگ جدید (شفافیت رو حفظ کن)
        _, _, _, a = pixels[x, y]
        pixels[x, y] = (r, g, b, a)

    return qr_image


def generate_qr_code(data, size=300, logo_path=None, color1=(0, 119, 255), color2=(120, 0, 255),
                     gradient_direction='diagonal', use_gradient=True):
    """
    تولید QR Code با گرادیانت روی خطوط و لوگو

    Args:
        data (str): لینک یا داده‌ای که باید در QR Code قرار بگیره
        size (int): سایز نهایی تصویر (پیکسل)
        logo_path (str): مسیر لوگو برای قرارگیری وسط QR Code
        color1 (tuple): رنگ شروع گرادیانت (R, G, B)
        color2 (tuple): رنگ پایان گرادیانت (R, G, B)
        gradient_direction (str): جهت گرادیانت ('horizontal', 'vertical', 'diagonal')
        use_gradient (bool): آیا از گرادیانت استفاده بشه یا نه

    Returns:
        BytesIO: بافر حاوی تصویر QR Code
    """

    # ایجاد QR Code با سطح تصحیح خطای بالا (برای لوگو)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    # تولید تصویر با استایل گرد و رنگ مشکی/سفید (پایه)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(
            back_color=(255, 255, 255),  # پس‌زمینه سفید
            front_color=(0, 0, 0)  # رنگ مربع‌ها مشکی
        )
    )

    # تبدیل به RGBA
    img = img.convert("RGBA")

    # اگر گرادیانت فعال باشه، فقط روی پیکسل‌های مشکی اعمال کن
    if use_gradient:
        img = create_gradient_on_black_pixels(img, color1, color2, gradient_direction)

    # قرار دادن لوگو (با پس‌زمینه سفید پشتش)
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path)

            # تبدیل لوگو به RGBA
            if logo.mode != 'RGBA':
                logo = logo.convert('RGBA')

            # محاسبه سایز لوگو (حداکثر ۱/۴ اندازه QR Code)
            logo_size = size // 4
            logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

            # ایجاد دایره سفید پشت لوگو (برای خوانایی بهتر)
            circle_size = logo_size + 20
            circle = Image.new('RGBA', (circle_size, circle_size), (255, 255, 255, 0))
            draw = ImageDraw.Draw(circle)
            draw.ellipse(
                [(0, 0), (circle_size, circle_size)],
                fill=(255, 255, 255, 255)  # سفید با شفافیت کم
            )

            # موقعیت قرارگیری لوگو (دقیقاً وسط)
            pos = (img.size[0] // 2 - logo_size // 2, img.size[1] // 2 - logo_size // 2)

            # ابتدا دایره سفید رو بذار، بعد لوگو روش
            circle_pos = (pos[0] - 10, pos[1] - 10)
            img.paste(circle, circle_pos, circle)
            img.paste(logo, pos, logo)

        except Exception as e:
            logger.error(f"⚠️ خطا در قرارگیری لوگو روی QR Code: {e}")

    # تغییر سایز
    if img.size[0] != size:
        img = img.resize((size, size), Image.Resampling.LANCZOS)

    # ذخیره در بافر با کیفیت بالا
    buffer = BytesIO()
    img.save(buffer, format='PNG', quality=95, optimize=True)
    buffer.seek(0)

    return buffer


def generate_and_save_qr(data, filename, logo_path=None, color1=(0, 119, 255), color2=(120, 0, 255),
                         gradient_direction='diagonal', use_gradient=True):
    """تولید QR Code و ذخیره‌اش به عنوان فایل جنگو"""
    buffer = generate_qr_code(
        data=data,
        logo_path=logo_path,
        color1=color1,
        color2=color2,
        gradient_direction=gradient_direction,
        use_gradient=use_gradient
    )
    return ContentFile(buffer.read(), name=filename)


def get_site_logo_path():
    """دریافت مسیر لوگوی سایت برای قرارگیری روی QR Code"""
    logo_paths = [
        os.path.join(settings.BASE_DIR, 'static', 'finder', 'img', 'icons', 'favicon.ico'),
        os.path.join(settings.BASE_DIR, 'static', 'finder', 'img', 'logo', 'Untitled03.png'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png'),
        os.path.join(settings.BASE_DIR, 'static', 'img', 'logo.png'),
        os.path.join(settings.BASE_DIR, 'media', 'logo', 'logo.png'),
    ]

    for path in logo_paths:
        if os.path.exists(path):
            return path
    return None


def hex_to_rgb(hex_code):
    """تبدیل کد هگزادسیمال به RGB"""
    hex_code = hex_code.lstrip('#')
    return tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))


def get_default_qr_colors():
    """
    دریافت رنگ‌های پیش‌فرض برای QR Code (گرادیانت روی خطوط)
    """
    # ====== تبدیل Hex به RGB ======
    color1 = hex_to_rgb('#5d3cf2')
    color2 = hex_to_rgb('#fd5631')

    return color1, color2, 'diagonal'
