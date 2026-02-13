from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import GlassCategory, GlassType, Partner, WarehouseReceipt


class WarehouseBalanceViewTests(TestCase):
    def test_balance_table_shows_product_codes(self):
        supplier = Partner.objects.create(
            partner_type=Partner.SUPPLIER,
            name="ООО Поставщик",
        )
        category = GlassCategory.objects.create(name="Прозрачное")
        glass_type = GlassType.objects.create(category=category, name="M1")

        WarehouseReceipt.objects.create(
            glass_type=glass_type,
            product_code="GL-001",
            supplier=supplier,
            width_mm=1000,
            height_mm=2000,
            thickness_mm=Decimal("4.00"),
            quantity=2,
            total_amount=Decimal("1000.00"),
        )

        response = self.client.get(reverse("dashboard"), {"tab": "warehouse", "warehouse_view": "overview"})

        self.assertContains(response, "Код продукта")
        self.assertContains(response, "GL-001")
