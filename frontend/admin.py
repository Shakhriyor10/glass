from django.contrib import admin

from .models import (
    GlassCategory,
    GlassType,
    Partner,
    WarehouseBalance,
    WarehouseReceipt,
)


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "partner_type", "phone", "created_at")
    list_filter = ("partner_type",)
    search_fields = ("name", "phone", "address")


@admin.register(GlassCategory)
class GlassCategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(GlassType)
class GlassTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    list_filter = ("category",)
    search_fields = ("name", "category__name")


@admin.register(WarehouseReceipt)
class WarehouseReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "glass_type",
        "supplier",
        "quantity",
        "width_mm",
        "height_mm",
        "thickness_mm",
        "total_volume_m2",
        "total_amount",
        "created_at",
    )
    list_filter = ("glass_type__category", "glass_type", "supplier", "created_at")
    search_fields = ("glass_type__name", "supplier__name")
    readonly_fields = ("total_volume_m2", "created_at")


@admin.register(WarehouseBalance)
class WarehouseBalanceAdmin(admin.ModelAdmin):
    list_display = ("glass_type", "total_sheets", "total_volume_m2")
    readonly_fields = ("glass_type", "total_sheets", "total_volume_m2")