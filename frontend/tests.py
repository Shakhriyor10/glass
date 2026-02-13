from django.test import TestCase
from django.urls import reverse

from .models import GlassCategory


class DashboardViewTests(TestCase):
    def test_warehouse_categories_view_loads(self):
        response = self.client.get(reverse("dashboard"), {"tab": "warehouse", "warehouse_view": "categories"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Список категорий стекла")

    def test_category_can_be_updated(self):
        category = GlassCategory.objects.create(name="Прозрачное")

        response = self.client.post(
            reverse("dashboard"),
            {
                "action": "update_category",
                "category_id": category.id,
                "name": "Матовое",
                "active_tab": "warehouse",
                "warehouse_view": "categories",
            },
            follow=True,
        )

        category.refresh_from_db()
        self.assertEqual(category.name, "Матовое")
        self.assertContains(response, "Категория стекла обновлена")
