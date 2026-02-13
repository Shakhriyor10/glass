from django import forms

from .models import GlassCategory, GlassType, Partner, WarehouseReceipt


class StyledModelForm(forms.ModelForm):
    """Base form that adds Bootstrap-friendly classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            base_class = "form-select" if isinstance(widget, forms.Select) else "form-control"
            css = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{css} {base_class}".strip()


class PartnerForm(StyledModelForm):
    class Meta:
        model = Partner
        fields = ["partner_type", "name", "phone", "address", "note"]


class GlassCategoryForm(StyledModelForm):
    class Meta:
        model = GlassCategory
        fields = ["name"]


class GlassTypeForm(StyledModelForm):
    class Meta:
        model = GlassType
        fields = ["category", "name"]


class WarehouseReceiptForm(StyledModelForm):
    category = forms.ModelChoiceField(
        queryset=GlassCategory.objects.all(),
        label="Категория",
    )

    class Meta:
        model = WarehouseReceipt
        fields = [
            "category",
            "supplier",
            "width_mm",
            "height_mm",
            "thickness_mm",
            "quantity",
            "total_amount",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Partner.objects.filter(
            partner_type=Partner.SUPPLIER
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        category = self.cleaned_data["category"]
        instance.glass_type, _ = GlassType.objects.get_or_create(
            category=category,
            name=category.name,
        )
        if commit:
            instance.save()
        return instance
