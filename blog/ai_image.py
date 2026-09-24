import base64
from io import BytesIO

import requests
from PIL import Image

MODEL = '@cf/black-forest-labs/flux-1-schnell'


class ImageGenerationError(Exception):
    """Safe image-generation error."""


def build_featured_image_prompt(visual_concept):
    visual_concept = (visual_concept or '').strip()
    if not visual_concept:
        raise ImageGenerationError('ایده تصویری خالی است.')

    return (
        'Stylized 3D animated hero artwork for a digital marketing blog cover. '
        'Dark navy-black background with blue, purple and magenta neon lighting. '
        'Premium glossy 3D illustration, cinematic depth, modern SaaS aesthetic, '
        'clean centered composition, strong focal point and tasteful floating elements. '
        f'Core visual concept: {visual_concept}. '
        'Avoid realistic office photography and generic circuit-board backgrounds. '
        'No text, no readable letters, no logos, no watermark, no brand marks.'
    )


def _convert_to_16_9(image_bytes, target_width=1280, target_height=720):
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise ImageGenerationError('فایل تصویر قابل پردازش نیست.') from None

    original_width, original_height = image.size
    target_ratio = target_width / target_height
    original_ratio = original_width / original_height

    # center crop to 16:9
    if original_ratio > target_ratio:
        # image is too wide
        new_width = int(original_height * target_ratio)
        left = (original_width - new_width) // 2
        top = 0
        right = left + new_width
        bottom = original_height
    else:
        # image is too tall or square
        new_height = int(original_width / target_ratio)
        left = 0
        top = (original_height - new_height) // 2
        right = original_width
        bottom = top + new_height

    image = image.crop((left, top, right, bottom))
    image = image.resize((target_width, target_height), Image.LANCZOS)

    output = BytesIO()
    image.save(output, format='JPEG', quality=92, optimize=True)
    return output.getvalue()


def generate_featured_image(visual_concept, account_id, api_token, steps=6):
    account_id = (account_id or '').strip()
    api_token = (api_token or '').strip()
    if not account_id:
        raise ImageGenerationError('CLOUDFLARE_ACCOUNT_ID تنظیم نشده است.')
    if not api_token:
        raise ImageGenerationError('CLOUDFLARE_API_TOKEN تنظیم نشده است.')

    try:
        steps = int(steps)
    except (TypeError, ValueError):
        raise ImageGenerationError('BLOG_IMAGE_STEPS باید عدد صحیح باشد.') from None
    if not 1 <= steps <= 8:
        raise ImageGenerationError('BLOG_IMAGE_STEPS باید بین ۱ تا ۸ باشد.')

    url = (
        'https://api.cloudflare.com/client/v4/accounts/'
        f'{account_id}/ai/run/{MODEL}'
    )

    try:
        response = requests.post(
            url,
            headers={
                'Authorization': f'Bearer {api_token}',
                'Content-Type': 'application/json',
            },
            json={'prompt': build_featured_image_prompt(visual_concept), 'steps': steps},
            timeout=(10, 120),
            allow_redirects=False,
        )
    except requests.Timeout:
        raise ImageGenerationError('مهلت ساخت تصویر در Cloudflare تمام شد.') from None
    except requests.RequestException:
        raise ImageGenerationError('ارتباط با Cloudflare برقرار نشد.') from None

    if response.status_code != 200:
        raise ImageGenerationError(f'Cloudflare HTTP {response.status_code}.')

    try:
        payload = response.json()
        if payload.get('success') is not True:
            raise ImageGenerationError('Cloudflare ساخت تصویر را ناموفق اعلام کرد.')
        encoded = (payload.get('result') or {}).get('image')
        if not isinstance(encoded, str) or not encoded:
            raise ImageGenerationError('تصویر در پاسخ Cloudflare وجود ندارد.')
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise ImageGenerationError('پاسخ تصویری Cloudflare معتبر نیست.') from None

    if len(image_bytes) < 10_000:
        raise ImageGenerationError('تصویر خروجی غیرعادی کوچک است و ذخیره نشد.')

    return _convert_to_16_9(image_bytes)
