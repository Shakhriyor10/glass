from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce


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
        indexes = [models.Index(fields=["partner_type", "name"])]
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
    total_volume_m2 = models.DecimalField("Общий объем (м²)", max_digits=12, decimal_places=3, editable=False)
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
        return f"{self.glass_type} - {self.quantity} шт. от {self.supplier.name} ({self.total_volume_m2} м²)"

    @property
    def sheet_volume_m2(self):
        return ((Decimal(self.width_mm) / Decimal("1000")) * (Decimal(self.height_mm) / Decimal("1000"))).quantize(
            Decimal("0.001")
        )

    def save(self, *args, **kwargs):
        width_m = Decimal(self.width_mm) / Decimal("1000")
        height_m = Decimal(self.height_mm) / Decimal("1000")
        self.total_volume_m2 = (width_m * height_m * Decimal(self.quantity)).quantize(Decimal("0.001"))
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            WarehouseSheet.objects.bulk_create(
                [
                    WarehouseSheet(
                        receipt=self,
                        glass_type=self.glass_type,
                        product_code=self.product_code,
                        width_mm=self.width_mm,
                        height_mm=self.height_mm,
                        thickness_mm=self.thickness_mm,
                        remaining_volume_m2=self.sheet_volume_m2,
                    )
                    for _ in range(self.quantity)
                ]
            )
        update_warehouse_balance(self.glass_type)


class WarehouseSheet(models.Model):
    receipt = models.ForeignKey(WarehouseReceipt, on_delete=models.CASCADE, related_name="sheets")
    glass_type = models.ForeignKey(GlassType, on_delete=models.PROTECT, related_name="warehouse_sheets")
    product_code = models.CharField("Код продукта", max_length=100)
    width_mm = models.PositiveIntegerField("Ширина (мм)")
    height_mm = models.PositiveIntegerField("Высота (мм)")
    thickness_mm = models.DecimalField("Толщина (мм)", max_digits=6, decimal_places=2)
    remaining_volume_m2 = models.DecimalField("Остаток объема (м²)", max_digits=12, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Лист на складе"
        verbose_name_plural = "Листы на складе"

    @property
    def full_volume_m2(self):
        return ((Decimal(self.width_mm) / Decimal("1000")) * (Decimal(self.height_mm) / Decimal("1000"))).quantize(
            Decimal("0.001")
        )

    @property
    def size_display(self):
        return f"{self.width_mm}×{self.height_mm} мм"

    def __str__(self):
        return f"{self.glass_type} / {self.product_code} / {self.size_display}"


class Order(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_STARTED = "started"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Черновик"),
        (STATUS_STARTED, "Начато"),
        (STATUS_IN_PROGRESS, "В работе"),
        (STATUS_COMPLETED, "Готово"),
        (STATUS_CANCELLED, "Отменено"),
    ]

    client = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="orders", verbose_name="Клиент")
    warehouse_sheet = models.ForeignKey(
        WarehouseSheet,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Лист стекла",
    )
    width_mm = models.PositiveIntegerField("Ширина заказа (мм)")
    height_mm = models.PositiveIntegerField("Высота заказа (мм)")
    thickness_mm = models.DecimalField("Толщина заказа (мм)", max_digits=6, decimal_places=2)
    price_per_m2 = models.DecimalField("Цена за м²", max_digits=12, decimal_places=2)
    waste_percent = models.DecimalField(
        "Процент отхода",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
    )
    order_volume_m2 = models.DecimalField("Объем заказа (м²)", max_digits=12, decimal_places=3, editable=False)
    waste_volume_m2 = models.DecimalField("Платный отход (м²)", max_digits=12, decimal_places=3, editable=False)
    total_amount = models.DecimalField("Итоговая сумма", max_digits=12, decimal_places=2, editable=False)
    consumed_volume_m2 = models.DecimalField("Списанный объем (м²)", max_digits=12, decimal_places=3, default=Decimal("0.000"))
    is_consumed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    note = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def clean(self):
        if self.client and self.client.partner_type != Partner.CLIENT:
            raise ValidationError({"client": "Выберите клиента."})

        if self.warehouse_sheet_id:
            if self.width_mm > self.warehouse_sheet.width_mm or self.height_mm > self.warehouse_sheet.height_mm:
                raise ValidationError("Размер заказа превышает размер выбранного листа.")
            if self.thickness_mm > self.warehouse_sheet.thickness_mm:
                raise ValidationError("Толщина заказа не должна превышать толщину листа.")

            order_volume = ((Decimal(self.width_mm) / Decimal("1000")) * (Decimal(self.height_mm) / Decimal("1000"))).quantize(
                Decimal("0.001")
            )
            leftover = max(self.warehouse_sheet.full_volume_m2 - order_volume, Decimal("0.000"))
            waste_volume = (leftover * self.waste_percent / Decimal("100")).quantize(Decimal("0.001"))
            consumed = order_volume + waste_volume
            if consumed > self.warehouse_sheet.remaining_volume_m2 and not self.is_consumed:
                raise ValidationError("Недостаточно остатка на выбранном листе для запуска заказа.")

    def save(self, *args, **kwargs):
        order_volume = ((Decimal(self.width_mm) / Decimal("1000")) * (Decimal(self.height_mm) / Decimal("1000"))).quantize(
            Decimal("0.001")
        )
        leftover = max(self.warehouse_sheet.full_volume_m2 - order_volume, Decimal("0.000"))
        self.order_volume_m2 = order_volume
        self.waste_volume_m2 = (leftover * self.waste_percent / Decimal("100")).quantize(Decimal("0.001"))
        self.total_amount = ((self.order_volume_m2 + self.waste_volume_m2) * self.price_per_m2).quantize(Decimal("0.01"))
        self.consumed_volume_m2 = self.order_volume_m2 + self.waste_volume_m2

        self.full_clean()
        super().save(*args, **kwargs)

        if self.status in {self.STATUS_STARTED, self.STATUS_IN_PROGRESS, self.STATUS_COMPLETED} and not self.is_consumed:
            self.warehouse_sheet.remaining_volume_m2 = (
                self.warehouse_sheet.remaining_volume_m2 - self.consumed_volume_m2
            ).quantize(Decimal("0.001"))
            self.warehouse_sheet.save(update_fields=["remaining_volume_m2"])
            WasteRecord.objects.get_or_create(
                order=self,
                defaults={
                    "warehouse_sheet": self.warehouse_sheet,
                    "waste_volume_m2": self.waste_volume_m2,
                    "waste_amount": (self.waste_volume_m2 * self.price_per_m2).quantize(Decimal("0.01")),
                },
            )
            self.is_consumed = True
            super().save(update_fields=["is_consumed"])
            update_warehouse_balance(self.warehouse_sheet.glass_type)


class WasteRecord(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="waste_record")
    warehouse_sheet = models.ForeignKey(WarehouseSheet, on_delete=models.CASCADE, related_name="waste_records")
    waste_volume_m2 = models.DecimalField("Объем отхода (м²)", max_digits=12, decimal_places=3)
    waste_amount = models.DecimalField("Сумма отхода", max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Отход"
        verbose_name_plural = "Отходы"


class WarehouseBalance(models.Model):
    glass_type = models.OneToOneField(
        GlassType,
        on_delete=models.CASCADE,
        related_name="warehouse_balance",
        verbose_name="Вид стекла",
    )
    total_sheets = models.PositiveIntegerField("Общее количество листов", default=0)
    total_volume_m2 = models.DecimalField("Общий объем (м²)", max_digits=12, decimal_places=3, default=Decimal("0.000"))

    class Meta:
        verbose_name = "Остаток на складе"
        verbose_name_plural = "Остатки на складе"

    def __str__(self):
        return f"{self.glass_type}: {self.total_sheets} шт., {self.total_volume_m2} м²"


def update_warehouse_balance(glass_type):
    aggregated = WarehouseSheet.objects.filter(glass_type=glass_type, remaining_volume_m2__gt=0).aggregate(
        total_sheets=Coalesce(models.Count("id"), 0),
        total_volume=Coalesce(Sum("remaining_volume_m2"), Decimal("0.000")),
    )
    WarehouseBalance.objects.update_or_create(
        glass_type=glass_type,
        defaults={"total_sheets": aggregated["total_sheets"], "total_volume_m2": aggregated["total_volume"]},
    )