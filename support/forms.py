# support/forms.py
from django import forms
from tickets.models import TicketMessage

class TicketReplyForm(forms.ModelForm):
    class Meta:
        model = TicketMessage
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5, 'class': 'form-control', 'placeholder': 'متن پاسخ را وارد کنید...'}),
        }
        labels = {
            'message': 'پاسخ',
        }
