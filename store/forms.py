import re
from datetime import date

from django import forms

from accounts.forms import BootstrapFormMixin

from .models import Order, Review

PHONE_RE = re.compile(r"^[6-9]\d{9}$")        # Indian mobile numbers
PINCODE_RE = re.compile(r"^[1-9]\d{5}$")      # Indian PIN codes
UPI_RE = re.compile(r"^[\w.\-]{2,}@[a-zA-Z]{2,}$")
EXPIRY_RE = re.compile(r"^(0[1-9]|1[0-2])\s*/\s*(\d{2})$")


def luhn_valid(number):
    """The Luhn checksum used by every real card number (4111 1111 1111 1111 passes)."""
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    if not 12 <= len(digits) <= 19:
        return False
    total = 0
    for position, digit in enumerate(reversed(digits)):
        if position % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


class CheckoutForm(BootstrapFormMixin, forms.Form):
    SHIPPING_FIELDS = ("full_name", "phone", "address_line", "city", "state", "pincode")

    full_name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"autocomplete": "name"}))
    phone = forms.CharField(label="Mobile number", max_length=15, widget=forms.TextInput(
        attrs={"type": "tel", "autocomplete": "tel-national", "inputmode": "numeric", "placeholder": "98765 43210…"}))
    address_line = forms.CharField(label="Address", max_length=255, widget=forms.TextInput(
        attrs={"autocomplete": "street-address", "placeholder": "House no., street, area…"}))
    city = forms.CharField(max_length=80, widget=forms.TextInput(attrs={"autocomplete": "address-level2"}))
    state = forms.CharField(max_length=80, widget=forms.TextInput(attrs={"autocomplete": "address-level1"}))
    pincode = forms.CharField(label="PIN code", max_length=6, widget=forms.TextInput(
        attrs={"autocomplete": "postal-code", "inputmode": "numeric", "placeholder": "411001…"}))

    payment_method = forms.ChoiceField(choices=Order.PaymentMethod.choices, widget=forms.RadioSelect,
                                       initial=Order.PaymentMethod.UPI)
    upi_id = forms.CharField(label="UPI ID", required=False, widget=forms.TextInput(
        attrs={"placeholder": "yourname@okaxis…", "autocomplete": "off", "spellcheck": "false", "autocapitalize": "none"}))
    card_number = forms.CharField(label="Card number", required=False, widget=forms.TextInput(
        attrs={"inputmode": "numeric", "autocomplete": "off", "placeholder": "4111 1111 1111 1111…"}))
    card_expiry = forms.CharField(label="Expiry (MM/YY)", required=False, widget=forms.TextInput(
        attrs={"inputmode": "numeric", "autocomplete": "off", "placeholder": "12/30…"}))
    card_cvv = forms.CharField(label="CVV", required=False, widget=forms.PasswordInput(
        attrs={"inputmode": "numeric", "autocomplete": "off", "maxlength": "4"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_method"].widget.attrs["class"] = "form-check-input"
        # Required only for their own payment method (checked in clean()), so don't label them "optional".
        for name in ("upi_id", "card_number", "card_expiry", "card_cvv"):
            self.fields[name].conditional = True

    def clean_phone(self):
        phone = re.sub(r"[\s\-]", "", self.cleaned_data["phone"]).removeprefix("+91")
        if not PHONE_RE.match(phone):
            raise forms.ValidationError("Enter a 10-digit Indian mobile number, like 98765 43210.")
        return phone

    def clean_pincode(self):
        pincode = self.cleaned_data["pincode"].strip()
        if not PINCODE_RE.match(pincode):
            raise forms.ValidationError("Enter a 6-digit PIN code, like 411001.")
        return pincode

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get("payment_method")
        if method == Order.PaymentMethod.UPI:
            if not UPI_RE.match(cleaned.get("upi_id", "").strip()):
                self.add_error("upi_id", "Enter a UPI ID like yourname@okaxis.")
        elif method == Order.PaymentMethod.CARD:
            self._clean_card(cleaned)
        return cleaned

    def _clean_card(self, cleaned):
        number = re.sub(r"\D", "", cleaned.get("card_number", ""))
        if not luhn_valid(number):
            self.add_error("card_number", "This card number isn't valid. For the demo, use 4111 1111 1111 1111.")
        match = EXPIRY_RE.match(cleaned.get("card_expiry", "").strip())
        if not match:
            self.add_error("card_expiry", "Enter the expiry as MM/YY, like 12/30.")
        else:
            month, year = int(match.group(1)), 2000 + int(match.group(2))
            today = date.today()
            if (year, month) < (today.year, today.month):
                self.add_error("card_expiry", "This card has expired.")
        if not re.fullmatch(r"\d{3,4}", cleaned.get("card_cvv", "")):
            self.add_error("card_cvv", "Enter the 3 or 4 digit CVV.")
        cleaned["card_number"] = number

    def shipping_data(self):
        return {name: self.cleaned_data[name] for name in self.SHIPPING_FIELDS}

    def payment_detail(self):
        """What place_order needs to build the fake transaction id. The CVV is never used or stored."""
        method = self.cleaned_data["payment_method"]
        if method == Order.PaymentMethod.CARD:
            return self.cleaned_data["card_number"]
        if method == Order.PaymentMethod.UPI:
            return self.cleaned_data["upi_id"]
        return ""


class ReviewForm(BootstrapFormMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(choices=[(n, n) for n in range(5, 0, -1)], coerce=int, widget=forms.RadioSelect)

    class Meta:
        model = Review
        fields = ("rating", "comment")
        widgets = {"comment": forms.Textarea(attrs={"rows": 3, "placeholder": "What did you like or dislike?…"})}
        labels = {"comment": "Your review"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rating"].widget.attrs["class"] = "visually-hidden"  # styled as clickable stars
