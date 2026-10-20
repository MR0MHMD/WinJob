# market/context_processors.py

from .models import Cart


def cart_context(request):
    """
    اطلاعات سبد خرید رو در تمام قالب‌ها در دسترس قرار می‌ده
    """
    if not request.user.is_authenticated:
        return {
            "cart_items_count": 0,
            "cart_total": 0,
            "cart_items_preview": [],
        }

    try:
        cart = request.user.cart
    except Cart.DoesNotExist:
        return {
            "cart_items_count": 0,
            "cart_total": 0,
            "cart_items_preview": [],
        }

    items = cart.items.select_related("product", "variant").all()[:5]

    preview = []
    for item in items:
        preview.append({
            "id": item.id,
            "title": item.product.title,
            "image": item.product.main_image.url if item.product.main_image else None,
            "quantity": item.quantity,
            "subtotal": item.subtotal,
            "variant_info": (
                " / ".join(f"{v}" for v in item.variant.attributes.values())
                if item.variant else ""
            ),
        })

    return {
        "cart_items_count": cart.items_count,
        "cart_total": cart.total_price,
        "cart_items_preview": preview,
    }