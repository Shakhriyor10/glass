from collections import defaultdict

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .forms import GlassCategoryForm, OrderForm, PartnerForm, WarehouseReceiptForm
from .models import GlassCategory, Order, Partner, WarehouseBalance, WarehouseReceipt, WasteRecord


class DashboardSectionView(View):
    template_name = "frontend/dashboard.html"
    active_tab = "warehouse"
    warehouse_view = "overview"

    def get(self, request):
        context = self._build_context(active_tab=self.active_tab, warehouse_view=self.warehouse_view)
        return render(request, self.template_name, context)

    def post(self, request):
        action = request.POST.get("action")

        form_map = {
            "create_partner": (PartnerForm, "Контрагент добавлен.", "counterparty"),
            "create_category": (GlassCategoryForm, "Категория стекла добавлена.", "warehouse_categories"),
            "create_receipt": (WarehouseReceiptForm, "Поступление на склад добавлено.", "warehouse"),
            "create_order": (OrderForm, "Заказ создан.", "orders"),
        }

        if action == "update_category":
            return self._update_category(request)

        if action not in form_map:
            messages.error(request, "Неизвестное действие формы.")
            return redirect(self.active_tab_url_name)

        form_class, success_message, target_url_name = form_map[action]
        form = form_class(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, success_message)
            return redirect(target_url_name)

        context = self._build_context(active_tab=self.active_tab, warehouse_view=self.warehouse_view)
        context[f"{action}_form"] = form
        return render(request, self.template_name, context)

    def _update_category(self, request):
        category_id = request.POST.get("category_id")
        category = get_object_or_404(GlassCategory, pk=category_id)
        form = GlassCategoryForm(request.POST, instance=category)

        if form.is_valid():
            form.save()
            messages.success(request, "Категория стекла обновлена.")
            return redirect("warehouse_categories")

        context = self._build_context(active_tab="warehouse", warehouse_view="categories")
        context["category_edit_form"] = form
        context["editing_category_id"] = category.id
        return render(request, "frontend/warehouse_categories.html", context)

    @property
    def active_tab_url_name(self):
        tab_to_url_name = {
            "counterparty": "counterparty",
            "orders": "orders",
            "warehouse": "warehouse_categories" if self.warehouse_view == "categories" else "warehouse",
        }
        return tab_to_url_name[self.active_tab]

    def _build_context(self, active_tab, warehouse_view="overview"):
        warehouse_balances = list(
            WarehouseBalance.objects.select_related("glass_type", "glass_type__category").order_by(
                "glass_type__category__name", "glass_type__name"
            )
        )

        size_pairs = WarehouseReceipt.objects.values_list("glass_type_id", "width_mm", "height_mm").distinct()
        product_code_pairs = WarehouseReceipt.objects.values_list("glass_type_id", "product_code").distinct()
        size_map = defaultdict(set)
        product_code_map = defaultdict(set)
        for glass_type_id, width_mm, height_mm in size_pairs:
            size_map[glass_type_id].add(f"{width_mm} × {height_mm}")

        for glass_type_id, product_code in product_code_pairs:
            product_code_map[glass_type_id].add(product_code)

        warehouse_balance_rows = []
        for balance in warehouse_balances:
            sizes = sorted(size_map.get(balance.glass_type_id, []))
            warehouse_balance_rows.append(
                {
                    "category_name": balance.glass_type.category.name,
                    "product_codes": ", ".join(sorted(product_code_map.get(balance.glass_type_id, []))) or "—",
                    "size_display": ", ".join(sizes) if sizes else "—",
                    "total_sheets": balance.total_sheets,
                    "total_volume_m2": balance.total_volume_m2,
                }
            )

        total_sheets = sum(balance.total_sheets for balance in warehouse_balances)
        total_volume = sum(balance.total_volume_m2 for balance in warehouse_balances)

        create_order_form = OrderForm()
        return {
            "active_tab": active_tab,
            "warehouse_view": warehouse_view,
            "create_partner_form": PartnerForm(),
            "create_category_form": GlassCategoryForm(),
            "create_receipt_form": WarehouseReceiptForm(),
            "create_order_form": create_order_form,
            "partners": Partner.objects.order_by("-created_at"),
            "warehouse_receipts": WarehouseReceipt.objects.select_related(
                "glass_type", "glass_type__category", "supplier"
            ).order_by("-created_at"),
            "warehouse_balance_rows": warehouse_balance_rows,
            "categories": GlassCategory.objects.order_by("name"),
            "orders": Order.objects.select_related(
                "client", "warehouse_sheet", "warehouse_sheet__glass_type", "warehouse_sheet__glass_type__category"
            ),
            "waste_records": WasteRecord.objects.select_related("order", "warehouse_sheet")[:10],
            "category_edit_form": None,
            "editing_category_id": None,
            "total_sheets": total_sheets,
            "total_volume": total_volume,
            "total_waste_volume": WasteRecord.objects.aggregate(total=Sum("waste_volume_m2"))["total"] or 0,
            "total_waste_amount": WasteRecord.objects.aggregate(total=Sum("waste_amount"))["total"] or 0,
        }


class CounterpartyView(DashboardSectionView):
    template_name = "frontend/counterparty.html"
    active_tab = "counterparty"


class OrdersView(DashboardSectionView):
    template_name = "frontend/orders.html"
    active_tab = "orders"


class WarehouseView(DashboardSectionView):
    template_name = "frontend/warehouse.html"
    active_tab = "warehouse"


class WarehouseCategoriesView(DashboardSectionView):
    template_name = "frontend/warehouse_categories.html"
    active_tab = "warehouse"
    warehouse_view = "categories"