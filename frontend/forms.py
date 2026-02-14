from django import forms
from django.forms.models import ModelChoiceIteratorValue

from .models import GlassCategory, GlassType, Order, Partner, WarehouseReceipt, WarehouseSheet


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            base_class = "form-select" if isinstance(widget, forms.Select) else "form-control"
            css = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{css} {base_class}".strip()


class WarehouseSheetSelect(forms.Select):
    def __init__(self, *args, sheet_map=None, **kwargs):
        self.sheet_map = sheet_map or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        option_value = value
        if isinstance(value, ModelChoiceIteratorValue):
            option_value = value.value

        sheet_data = self.sheet_map.get(str(option_value))
        if sheet_data:
            option["attrs"].update(
                {
                    "data-width-mm": sheet_data["width_mm"],
                    "data-height-mm": sheet_data["height_mm"],
                    "data-thickness-mm": sheet_data["thickness_mm"],
                    "data-remaining-volume-m2": sheet_data["remaining_volume_m2"],
                }
            )
        return option


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
    category = forms.ModelChoiceField(queryset=GlassCategory.objects.all(), label="Категория")

    class Meta:
        model = WarehouseReceipt
        fields = [
            "category",
            "product_code",
            "supplier",
            "width_mm",
            "height_mm",
            "thickness_mm",
            "quantity",
            "total_amount",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Partner.objects.filter(partner_type=Partner.SUPPLIER)

    def save(self, commit=True):
        instance = super().save(commit=False)
        category = self.cleaned_data["category"]
        instance.glass_type, _ = GlassType.objects.get_or_create(category=category, name=category.name)
        if commit:
            instance.save()
        return instance


class OrderForm(StyledModelForm):
    client = forms.ModelChoiceField(
        queryset=Partner.objects.filter(partner_type=Partner.CLIENT),
        required=False,
        label="Клиент из базы",
    )
    new_client_name = forms.CharField(required=False, label="Новый клиент (имя)")
    new_client_phone = forms.CharField(required=False, label="Телефон нового клиента")
    new_client_address = forms.CharField(required=False, label="Адрес нового клиента")

    class Meta:
        model = Order
        fields = [
            "client",
            "new_client_name",
            "new_client_phone",
            "new_client_address",
            "warehouse_sheet",
            "width_mm",
            "height_mm",
            "price_per_m2",
            "waste_percent",
            "status",
            "note",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        warehouse_sheets = WarehouseSheet.objects.filter(remaining_volume_m2__gt=0).select_related(
            "glass_type", "glass_type__category"
        )
        self.fields["warehouse_sheet"].queryset = warehouse_sheets
        self.fields["client"].empty_label = "— Выберите клиента из базы —"
        self.fields["warehouse_sheet"].empty_label = "— Выберите лист со склада —"

        self.fields["warehouse_sheet"].widget = WarehouseSheetSelect(
            attrs=self.fields["warehouse_sheet"].widget.attrs,
            choices=self.fields["warehouse_sheet"].choices,
            sheet_map={
                str(sheet.pk): {
                    "width_mm": sheet.width_mm,
                    "height_mm": sheet.height_mm,
                    "thickness_mm": sheet.thickness_mm,
                    "remaining_volume_m2": sheet.remaining_volume_m2,
                }
                for sheet in warehouse_sheets
            },
        )
        self.fields["warehouse_sheet"].widget.choices = self.fields["warehouse_sheet"].choices
        self.fields["warehouse_sheet"].label_from_instance = self._sheet_label
        self.suitable_sheets = []

        data = self.data or None
        if data and data.get("width_mm") and data.get("height_mm"):
            try:
                width = int(data["width_mm"])
                height = int(data["height_mm"])
                self.suitable_sheets = list(
                    self.fields["warehouse_sheet"].queryset.filter(
                        width_mm__gte=width,
                        height_mm__gte=height,
                    )[:8]
                )
            except (ValueError, ArithmeticError):
                self.suitable_sheets = []

    def _sheet_label(self, sheet):
        return (
            f"{sheet.glass_type.category.name} / {sheet.product_code} / {sheet.width_mm}×{sheet.height_mm} мм / "
            f"{sheet.thickness_mm} мм / остаток {sheet.remaining_volume_m2} м²"
        )

    def clean(self):
        cleaned_data = super().clean()
        client = cleaned_data.get("client")
        new_client_name = cleaned_data.get("new_client_name")

        if not client and not new_client_name:
            raise forms.ValidationError("Выберите клиента из базы или заполните нового клиента.")

        if client and new_client_name:
            raise forms.ValidationError("Нужно выбрать только один вариант: существующий или новый клиент.")

        sheet = cleaned_data.get("warehouse_sheet")
        width = cleaned_data.get("width_mm")
        height = cleaned_data.get("height_mm")
        if sheet and width and width > sheet.width_mm:
            self.add_error("width_mm", "Ширина заказа больше ширины листа.")
        if sheet and height and height > sheet.height_mm:
            self.add_error("height_mm", "Высота заказа больше высоты листа.")

        if sheet:
            cleaned_data["thickness_mm"] = sheet.thickness_mm

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.thickness_mm = self.cleaned_data["warehouse_sheet"].thickness_mm
        if not self.cleaned_data.get("client"):
            instance.client = Partner.objects.create(
                partner_type=Partner.CLIENT,
                name=self.cleaned_data["new_client_name"],
                phone=self.cleaned_data.get("new_client_phone", ""),
                address=self.cleaned_data.get("new_client_address", ""),
            )
        if commit:
            instance.save()
        return instance
