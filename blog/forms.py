from django import forms
from .models import PostComments


class PostCommentForm(forms.ModelForm):
    """فرم ثبت کامنت برای پست های بلاگ."""

    class Meta:
        model = PostComments
        fields = (
            "name",
            "email",
            "content"
        )

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-light form-control-lg",
                    "type": "text",
                    "id": "comment-name",
                    "name": "name",
                    "placeholder": "نام و نام خانوادگی شما",
                }
            ),
            "email": forms.TextInput(
                attrs={
                    "class": "form-control form-control-light form-control-lg",
                    "placeholder": "ایمیل شما",
                    "type": "email",
                    "name": "email",
                    "id": "comment-email",
                }
            ),

            "content": forms.Textarea(
                attrs={
                    "class": "form-control form-control-light form-control-lg",
                    "rows": 3,
                    "placeholder": "نظر شما",
                    "name": "content",
                    "id": "comment-text",
                }
            ),
        }
