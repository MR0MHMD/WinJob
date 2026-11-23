"""گروه‌بندی درختی منوی ادمین (وین دایرکت + وین فوروارد) با حفظ مجوزهای کاربر."""

from django import template

register = template.Library()

WINDIRECT_APPS = {
    "connections": "اتصالات",
    "comments": "کامنت هوشمند",
    "direct": "دایرکت هوشمند",
    "showcases": "ویترین‌ساز",
    "forms": "فرم‌ساز",
    "subscriptions": "اشتراک‌ها",
}

WINFORWARD_APPS = {
    "broadcast": "انتشار و کانال‌ها",
    "messengers": "پیام‌رسان‌ها و ربات‌ها",
    "forward_subscriptions": "کیف توکن و بسته‌ها",
}

_ADMIN_GROUPS = (
    ("وین دایرکت", "bi bi-chat-dots-fill", WINDIRECT_APPS),
    ("وین فوروارد", "bi bi-rocket-takeoff-fill", WINFORWARD_APPS),
)


@register.filter
def admin_sidebar_tree(app_list, path):
    """اپ‌های مجاز وین دایرکت و وین فوروارد را هرکدام زیر پوشه مادر اختصاصی خود قرار می‌دهد."""
    path = str(path or "")
    items = []
    group_buckets = {}

    for app in app_list or []:
        models = []
        for model in app.get("models", []):
            url = model.get("admin_url") or model.get("add_url")
            if url:
                models.append(
                    {
                        **model,
                        "sidebar_url": url,
                        "sidebar_active": path.startswith(url),
                    }
                )
        if not models:
            continue

        app_url = app.get("app_url")
        active = any(model["sidebar_active"] for model in models)
        active = active or bool(app_url and path.startswith(app_url))
        node = {**app, "models": models, "sidebar_active": active}
        label = app["app_label"]

        matched = False
        for group_name, group_icon, app_map in _ADMIN_GROUPS:
            if label in app_map:
                if group_name not in group_buckets:
                    children = []
                    group_node = {
                        "name": group_name,
                        "icon": group_icon,
                        "children": children,
                        "sidebar_active": False,
                    }
                    group_buckets[group_name] = (group_node, children, list(app_map))
                    items.append(group_node)
                group_node, children, _ = group_buckets[group_name]
                node.update(name=app_map[label], force_folder=True)
                children.append(node)
                group_node["sidebar_active"] = group_node["sidebar_active"] or active
                matched = True
                break

        if not matched:
            items.append(node)

    for _, children, order in group_buckets.values():
        children.sort(key=lambda n: order.index(n["app_label"]))

    return items
