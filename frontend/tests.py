from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from .forms import OrderForm
from .models import GlassCategory, GlassType, Order, Partner, WarehouseReceipt


class OrderSheetRotationTest(TestCase):
    def setUp(self):
        self.client_partner = Partner.objects.create(partner_type=Partner.CLIENT, name="Клиент")
        self.supplier = Partner.objects.create(partner_type=Partner.SUPPLIER, name="Поставщик")
        self.category = GlassCategory.objects.create(name="Прозрачное")
        self.glass_type = GlassType.objects.create(category=self.category, name=self.category.name)
        self.receipt = WarehouseReceipt.objects.create(
            glass_type=self.glass_type,
            product_code="GL-1200x1580",
            supplier=self.supplier,
            width_mm=1200,
            height_mm=1580,
            thickness_mm=Decimal("4.00"),
            quantity=1,
            total_amount=Decimal("1000.00"),
        )
        self.sheet = self.receipt.sheets.first()

    def test_order_form_accepts_rotated_dimensions(self):
        form = OrderForm(
            data={
                "client": self.client_partner.id,
                "warehouse_sheet": self.sheet.id,
                "width_mm": 1580,
                "height_mm": 1200,
                "price_per_m2": "1000.00",
                "waste_percent": "10.00",
                "status": Order.STATUS_DRAFT,
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_order_form_rejects_too_large_dimensions(self):
        form = OrderForm(
            data={
                "client": self.client_partner.id,
                "warehouse_sheet": self.sheet.id,
                "width_mm": 2000,
                "height_mm": 1200,
                "price_per_m2": "1000.00",
                "waste_percent": "10.00",
                "status": Order.STATUS_DRAFT,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("warehouse_sheet", form.errors)

    def test_model_clean_accepts_rotated_dimensions(self):
        order = Order(
            client=self.client_partner,
            warehouse_sheet=self.sheet,
            width_mm=1580,
            height_mm=1200,
            thickness_mm=Decimal("4.00"),
            price_per_m2=Decimal("1000.00"),
            waste_percent=Decimal("10.00"),
            status=Order.STATUS_DRAFT,
        )

        order.full_clean()

    def test_model_clean_rejects_too_large_dimensions(self):
        order = Order(
            client=self.client_partner,
            warehouse_sheet=self.sheet,
            width_mm=2000,
            height_mm=1200,
            thickness_mm=Decimal("4.00"),
            price_per_m2=Decimal("1000.00"),
            waste_percent=Decimal("10.00"),
            status=Order.STATUS_DRAFT,
        )

        with self.assertRaises(ValidationError):
            order.full_clean()
