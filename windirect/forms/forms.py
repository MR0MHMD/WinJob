from django.forms import inlineformset_factory
from .models import ConversationForm, FormQuestion
from windirect.common.forms import AssetForm, StyledChildForm, OrderedChildren


class ConversationFormEditor(AssetForm):
    """تنظیمات پرسش‌نامه و پیام پایان آن."""

    class Meta:
        model = ConversationForm
        fields = [
            "connection",
            "name",
            "completion_text",
            "cancel_keyword",
            "is_active",
        ]


QuestionFormSet = inlineformset_factory(
    ConversationForm,
    FormQuestion,
    form=StyledChildForm,
    formset=OrderedChildren,
    fields=["prompt", "kind", "options", "position"],
    extra=0,
    min_num=1,
    max_num=20,
    validate_min=True,
    validate_max=True,
    absolute_max=30,
    can_delete=True,
)
