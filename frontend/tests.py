from django.test import TestCase

from .models import GlassCategory, GlassType, Partner, WarehouseBalance


class DashboardViewTests(TestCase):
    def setUp(self):
        self.supplier = Partner.objects.create(
            partner_type=Partner.SUPPLIER,
            name="ООО Поставщик",
        )
        self.category = GlassCategory.objects.create(name="Прозрачное")
        self.glass_type = GlassType.objects.create(
            category=self.category,
            name="М1",
        )

    def test_dashboard_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Панель управления стекольным складом")

    def test_can_create_partner(self):
        response = self.client.post(
            "/",
            {
                "action": "create_partner",
                "active_tab": "counterparty",
                "partner_type": Partner.CLIENT,
                "name": "ЗАО Клиент",
                "phone": "+7 900 111 22 33",
                "address": "Москва",
                "note": "Тест",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Partner.objects.filter(name="ЗАО Клиент").exists())

    def test_can_create_receipt_and_update_balance(self):
        response = self.client.post(
            "/",
            {
                "action": "create_receipt",
                "active_tab": "warehouse",
                "glass_type": self.glass_type.pk,
                "supplier": self.supplier.pk,
                "width_mm": 1000,
                "height_mm": 2000,
                "thickness_mm": "4.00",
                "quantity": 2,
                "total_amount": "1000.00",
            },
        )
        self.assertEqual(response.status_code, 302)
        balance = WarehouseBalance.objects.get(glass_type=self.glass_type)
        self.assertEqual(balance.total_sheets, 2)
        self.assertEqual(str(balance.total_volume_m2), "4.000")
