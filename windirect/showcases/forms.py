from django.forms import inlineformset_factory
from .models import Showcase, ShowcaseCard
from windirect.common.forms import AssetForm, StyledChildForm, OrderedChildren


class ShowcaseForm(AssetForm):
    """تنظیمات عمومی ویترین."""

    class Meta:
        model = Showcase
        fields = ["connection", "name", "is_active"]


CardFormSet = inlineformset_factory(
    Showcase,
    ShowcaseCard,
    form=StyledChildForm,
    formset=OrderedChildren,
    fields=["title", "subtitle", "image_url", "button_title", "button_url", "position"],
    extra=0,
    min_num=1,
    max_num=10,
    validate_min=True,
    validate_max=True,
    absolute_max=20,
    can_delete=True,
)
