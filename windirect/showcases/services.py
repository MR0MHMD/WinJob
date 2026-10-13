"""تهیهٔ کارت‌های ویترین برای موتور دایرکت."""


def build_response(showcase, connection):
    """فقط کارت‌های معتبر ویترین فعال متعلق به همین اتصال را برمی‌گرداند."""
    if (
        not showcase
        or showcase.connection_id != connection.pk
        or not showcase.is_active
    ):
        return None
    cards = list(
        showcase.cards.values(
            "title", "subtitle", "image_url", "button_title", "button_url"
        )
    )
    if not 1 <= len(cards) <= 10:
        return None
    response = {
        "kind": "showcase",
        "text": showcase.name,
        "cards": cards,
    }
    return response
