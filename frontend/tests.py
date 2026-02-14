from decimal import Decimal

from django.test import TestCase

from .forms import OrderForm
from .models import GlassCategory, GlassType, Order, Partner, WarehouseReceipt


class OrderFormAutoThicknessTests(TestCase):
    def setUp(self):
        self.client_partner = Partner.objects.create(partner_type=Partner.CLIENT, name="Клиент")
        self.supplier = Partner.objects.create(partner_type=Partner.SUPPLIER, name="Поставщик")
        self.category = GlassCategory.objects.create(name="Прозрачное")
        self.glass_type = GlassType.objects.create(category=self.category, name="Прозрачное")
        self.receipt = WarehouseReceipt.objects.create(
            glass_type=self.glass_type,
            product_code="GL-001",
            supplier=self.supplier,
            width_mm=3210,
            height_mm=2250,
            thickness_mm=Decimal("6.00"),
            quantity=1,
            total_amount=Decimal("100.00"),
        )
        self.sheet = self.receipt.sheets.first()

    def test_order_form_uses_sheet_thickness_automatically(self):
        form = OrderForm(
            data={
                "client": self.client_partner.pk,
                "warehouse_sheet": self.sheet.pk,
                "width_mm": 1500,
                "height_mm": 1000,
                "price_per_m2": "120",
                "waste_percent": "5",
                "status": Order.STATUS_DRAFT,
                "note": "",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        order = form.save()

        self.assertEqual(order.thickness_mm, self.sheet.thickness_mm)

    def test_suitable_sheets_are_filtered_by_dimensions_only(self):
        WarehouseReceipt.objects.create(
            glass_type=self.glass_type,
            product_code="GL-002",
            supplier=self.supplier,
            width_mm=1200,
            height_mm=900,
            thickness_mm=Decimal("10.00"),
            quantity=1,
            total_amount=Decimal("100.00"),
        )

        form = OrderForm(data={"width_mm": "1400", "height_mm": "1000"})

        self.assertIn(self.sheet, form.suitable_sheets)
        self.assertEqual(len(form.suitable_sheets), 1)
