from collections import defaultdict

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from .forms import GlassCategoryForm, PartnerForm, WarehouseReceiptForm
from .models import GlassCategory, Partner, WarehouseBalance, WarehouseReceipt


class DashboardView(View):
    template_name = "frontend/dashboard.html"

    def get(self, request):
        active_tab = request.GET.get("tab", "warehouse")
        warehouse_view = request.GET.get("warehouse_view", "overview")
        context = self._build_context(active_tab=active_tab, warehouse_view=warehouse_view)
        return render(request, self.template_name, context)

    def post(self, request):
        action = request.POST.get("action")
        active_tab = request.POST.get("active_tab", "warehouse")
        warehouse_view = request.POST.get("warehouse_view", "overview")

        form_map = {
            "create_partner": (PartnerForm, "Контрагент добавлен.", "counterparty", "overview"),
            "create_category": (GlassCategoryForm, "Категория стекла добавлена.", "warehouse", "categories"),
            "create_receipt": (WarehouseReceiptForm, "Поступление на склад добавлено.", "warehouse", "overview"),
        }

        if action == "update_category":
            return self._update_category(request)

        if action not in form_map:
            messages.error(request, "Неизвестное действие формы.")
            return redirect("dashboard")

        form_class, success_message, target_tab, target_view = form_map[action]
        form = form_class(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, success_message)
            return redirect(f"/?tab={target_tab}&warehouse_view={target_view}")

        context = self._build_context(active_tab=active_tab, warehouse_view=warehouse_view)
        context[f"{action}_form"] = form
        return render(request, self.template_name, context)

    def _update_category(self, request):
        category_id = request.POST.get("category_id")
        category = get_object_or_404(GlassCategory, pk=category_id)
        form = GlassCategoryForm(request.POST, instance=category)

        if form.is_valid():
            form.save()
            messages.success(request, "Категория стекла обновлена.")
            return redirect("/?tab=warehouse&warehouse_view=categories")

        context = self._build_context(active_tab="warehouse", warehouse_view="categories")
        context["category_edit_form"] = form
        context["editing_category_id"] = category.id
        return render(request, self.template_name, context)

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

        return {
            "active_tab": active_tab,
            "warehouse_view": warehouse_view,
            "create_partner_form": PartnerForm(),
            "create_category_form": GlassCategoryForm(),
            "create_receipt_form": WarehouseReceiptForm(),
            "partners": Partner.objects.order_by("-created_at"),
            "warehouse_receipts": WarehouseReceipt.objects.select_related(
                "glass_type", "glass_type__category", "supplier"
            ).order_by("-created_at"),
            "warehouse_balance_rows": warehouse_balance_rows,
            "categories": GlassCategory.objects.order_by("name"),
            "category_edit_form": None,
            "editing_category_id": None,
            "total_sheets": total_sheets,
            "total_volume": total_volume,
        }
