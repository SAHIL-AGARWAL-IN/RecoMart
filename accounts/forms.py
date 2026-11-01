from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class BootstrapFormMixin:
    """Give every widget Bootstrap's classes so templates can loop over fields."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            field.widget.attrs.setdefault("class", css)

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:  # red border on fields that failed validation
                self.fields[name].widget.attrs["class"] += " is-invalid"


NO_SPELLCHECK = {"spellcheck": "false", "autocapitalize": "none"}


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(autocomplete="username", **NO_SPELLCHECK)


class RegisterForm(BootstrapFormMixin, UserCreationForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(help_text="For order updates. We won't send marketing emails.")

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].widget.attrs.update(autocomplete="given-name")
        self.fields["last_name"].widget.attrs.update(autocomplete="family-name")
        self.fields["username"].widget.attrs.update(autocomplete="username", **NO_SPELLCHECK)
        self.fields["email"].widget.attrs.update(autocomplete="email", **NO_SPELLCHECK)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists. Try logging in.")
        return email


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone")
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", **NO_SPELLCHECK}),
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel", "placeholder": "98765 43210…"}),
        }
