from django import forms

from config.forms import BootstrapFormMixin, HoneypotMixin

from .models import CustomerReview


class CustomerReviewForm(BootstrapFormMixin, HoneypotMixin, forms.ModelForm):
    class Meta:
        model = CustomerReview
        fields = ["reviewer_name", "rating", "comment"]
        widgets = {
            "rating": forms.Select(choices=[(n, f"{n} ดาว") for n in range(5, 0, -1)]),
            "comment": forms.Textarea(attrs={"rows": 3}),
        }
