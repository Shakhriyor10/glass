from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from .forms import GlassCategoryForm, GlassTypeForm, PartnerForm, WarehouseReceiptForm
from .models import Partner, WarehouseBalance, WarehouseReceipt


class DashboardView(View):
    template_name = "frontend/dashboard.html"

    def get(self, request):
        active_tab = request.GET.get("tab", "warehouse")
        context = self._build_context(active_tab=active_tab)
        return render(request, self.template_name, context)

    def post(self, request):
        action = request.POST.get("action")
        active_tab = request.POST.get("active_tab", "warehouse")

        form_map = {
            "create_partner": (PartnerForm, "Контрагент добавлен.", "counterparty"),
            "create_category": (GlassCategoryForm, "Категория стекла добавлена.", "warehouse"),
            "create_glass_type": (GlassTypeForm, "Вид стекла добавлен.", "warehouse"),
            "create_receipt": (WarehouseReceiptForm, "Поступление на склад добавлено.", "warehouse"),
        }

        if action not in form_map:
            messages.error(request, "Неизвестное действие формы.")
            return redirect("dashboard")

        form_class, success_message, target_tab = form_map[action]
        form = form_class(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, success_message)
            return redirect(f"/?tab={target_tab}")

        context = self._build_context(active_tab=active_tab)
        context[f"{action}_form"] = form
        return render(request, self.template_name, context)

    def _build_context(self, active_tab):
        return {
            "active_tab": active_tab,
            "create_partner_form": PartnerForm(),
            "create_category_form": GlassCategoryForm(),
            "create_glass_type_form": GlassTypeForm(),
            "create_receipt_form": WarehouseReceiptForm(),
            "partners": Partner.objects.order_by("-created_at"),
            "warehouse_receipts": WarehouseReceipt.objects.select_related(
                "glass_type", "glass_type__category", "supplier"
            ).order_by("-created_at"),
            "warehouse_balances": WarehouseBalance.objects.select_related(
                "glass_type", "glass_type__category"
            ).order_by("glass_type__category__name", "glass_type__name"),
        }
