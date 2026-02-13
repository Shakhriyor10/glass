from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db.models.functions import Coalesce
from django.db import models
from django.db.models import Sum


class Partner(models.Model):
    CLIENT = "client"
    SUPPLIER = "supplier"
    TYPE_CHOICES = [
        (CLIENT, "Клиент"),
        (SUPPLIER, "Поставщик"),
    ]

    partner_type = models.CharField("Тип партнера", max_length=20, choices=TYPE_CHOICES)
    name = models.CharField("Название", max_length=255)
    phone = models.CharField("Телефон", max_length=50, blank=True)
    address = models.CharField("Адрес", max_length=255, blank=True)
    note = models.TextField("Примечание", blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["partner_type", "name"]),
        ]
        verbose_name = "Партнер"
        verbose_name_plural = "Партнеры"

    def __str__(self):
        return f"{self.name} ({self.get_partner_type_display()})"


class GlassCategory(models.Model):
    name = models.CharField("Категория стекла", max_length=255, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Категория стекла"
        verbose_name_plural = "Категории стекла"

    def __str__(self):
        return self.name


class GlassType(models.Model):
    category = models.ForeignKey(
        GlassCategory,
        on_delete=models.PROTECT,
        related_name="glass_types",
        verbose_name="Категория",
    )
    name = models.CharField("Вид стекла", max_length=255)

    class Meta:
        ordering = ["category__name", "name"]
        unique_together = ("category", "name")
        verbose_name = "Вид стекла"
        verbose_name_plural = "Виды стекла"

    def __str__(self):
        return f"{self.category.name} / {self.name}"


class WarehouseReceipt(models.Model):
    glass_type = models.ForeignKey(
        GlassType,
        on_delete=models.PROTECT,
        related_name="receipts",
        verbose_name="Вид стекла",
    )
    product_code = models.CharField("Код продукта", max_length=100)
    supplier = models.ForeignKey(
        Partner,
        on_delete=models.PROTECT,
        related_name="warehouse_receipts",
        verbose_name="Поставщик",
        limit_choices_to={"partner_type": Partner.SUPPLIER},
    )
    width_mm = models.PositiveIntegerField("Ширина (мм)")
    height_mm = models.PositiveIntegerField("Высота (мм)")
    thickness_mm = models.DecimalField(
        "Толщина (мм)",
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    quantity = models.PositiveIntegerField("Количество листов", default=1)
    total_volume_m2 = models.DecimalField(
        "Общий объем (м²)",
        max_digits=12,
        decimal_places=3,
        editable=False,
    )
    total_amount = models.DecimalField(
        "Общая сумма",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField("Дата прихода", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Приход на склад"
        verbose_name_plural = "Приходы на склад"

    def __str__(self):
        return (
            f"{self.glass_type} - {self.quantity} шт. от {self.supplier.name} "
            f"({self.total_volume_m2} м²)"
        )

    def save(self, *args, **kwargs):
        previous_glass_type = None
        if self.pk:
            previous_glass_type = (
                WarehouseReceipt.objects.filter(pk=self.pk)
                .values_list("glass_type", flat=True)
                .first()
            )

        width_m = Decimal(self.width_mm) / Decimal("1000")
        height_m = Decimal(self.height_mm) / Decimal("1000")
        self.total_volume_m2 = (width_m * height_m * Decimal(self.quantity)).quantize(
            Decimal("0.001")
        )
        super().save(*args, **kwargs)
        update_warehouse_balance(self.glass_type)

        if previous_glass_type and previous_glass_type != self.glass_type_id:
            update_warehouse_balance(GlassType.objects.get(pk=previous_glass_type))

    def delete(self, *args, **kwargs):
        glass_type = self.glass_type
        super().delete(*args, **kwargs)
        update_warehouse_balance(glass_type)




def update_warehouse_balance(glass_type):
    aggregated = WarehouseReceipt.objects.filter(glass_type=glass_type).aggregate(
        total_sheets=Coalesce(Sum("quantity"), 0),
        total_volume=Coalesce(Sum("total_volume_m2"), Decimal("0.000")),
    )
    WarehouseBalance.objects.update_or_create(
        glass_type=glass_type,
        defaults={
            "total_sheets": aggregated["total_sheets"],
            "total_volume_m2": aggregated["total_volume"],
        },
    )


class WarehouseBalance(models.Model):
    glass_type = models.OneToOneField(
        GlassType,
        on_delete=models.CASCADE,
        related_name="warehouse_balance",
        verbose_name="Вид стекла",
    )
    total_sheets = models.PositiveIntegerField("Общее количество листов", default=0)
    total_volume_m2 = models.DecimalField(
        "Общий объем (м²)",
        max_digits=12,
        decimal_places=3,
        default=Decimal("0.000"),
    )

    class Meta:
        verbose_name = "Остаток на складе"
        verbose_name_plural = "Остатки на складе"

    def __str__(self):
        return (
            f"{self.glass_type}: {self.total_sheets} шт., "
            f"{self.total_volume_m2} м²"
        )