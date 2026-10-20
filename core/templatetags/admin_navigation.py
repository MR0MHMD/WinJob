"""گروه‌بندی منوی ادمین با حفظ مجوزهای کاربر."""

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


@register.filter
def admin_sidebar_tree(app_list, path):
    """اپ‌های مجاز وین دایرکت را زیر یک بخش مادر قرار می‌دهد."""
    path = str(path or "")
    items = []
    children = []
    group = None

    for app in app_list or []:
        models = []
        for model in app.get("models", []):
            url = model.get("admin_url") or model.get("add_url")
            if url:
                models.append({
                    **model,
                    "sidebar_url": url,
                    "sidebar_active": path.startswith(url),
                })
        if not models:
            continue

        app_url = app.get("app_url")
        active = any(model["sidebar_active"] for model in models)
        active = active or bool(app_url and path.startswith(app_url))
        node = {**app, "models": models, "sidebar_active": active}
        label = app["app_label"]

        if label in WINDIRECT_APPS:
            if group is None:
                group = {
                    "name": "وین دایرکت",
                    "icon": "bi bi-chat-dots-fill",
                    "children": children,
                    "sidebar_active": False,
                }
                items.append(group)
            node.update(name=WINDIRECT_APPS[label], force_folder=True)
            children.append(node)
            group["sidebar_active"] = group["sidebar_active"] or active
        else:
            items.append(node)

    if group is not None:
        order = list(WINDIRECT_APPS)
        children.sort(key=lambda node: order.index(node["app_label"]))
    return items
