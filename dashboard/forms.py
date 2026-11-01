from django import forms
from django.utils.text import slugify

from accounts.forms import BootstrapFormMixin
from store.models import Category, Order, Product


class ProductForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = ("name", "slug", "category", "brand", "description", "price", "discount_price", "stock", "image",
                  "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}
        help_texts = {"slug": "Used in the product's web address. Leave empty to build it from the name."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["is_active"].label = "Show in the store"

    def clean_slug(self):
        slug = self.cleaned_data.get("slug") or slugify(self.cleaned_data.get("name", ""))[:200]
        clash = Product.objects.filter(slug=slug).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("Another product already uses this web address. Change the name or slug.")
        return slug


class CategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "slug", "icon", "description", "sort_order")
        help_texts = {"icon": "A Bootstrap Icons name, e.g. laptop, book, basket."}


class OrderStatusForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Order
        fields = ("status",)


class RestockForm(forms.Form):
    product_id = forms.IntegerField(widget=forms.HiddenInput)
    add = forms.IntegerField(min_value=1, max_value=10000, label="Add units")
