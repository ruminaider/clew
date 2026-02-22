# B2: Order, PrescriptionFill, and Prescription Model Relationships

## Summary

The three models live across two Django apps:
- `Order` — `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`
- `Prescription`, `PrescriptionFill`, and all through-tables — `/Users/albertgwo/Work/evvy/backend/care/models.py`

---

## 1. Order Model (`ecomm/models/order.py`, line 11)

```python
class Order(TimestampMixin, models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    cart = models.ForeignKey("Cart", null=True, blank=True, on_delete=models.SET_NULL)
    email = models.EmailField()
    provider_id = models.CharField(max_length=500)
    order_number = models.CharField(max_length=500, null=True, blank=True)
    order_type = models.CharField(max_length=2, choices=ORDER_TYPE_CHOICES)
    status = models.CharField(max_length=2, choices=STATUS_CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    # ... other fields
    class Meta:
        unique_together = ("provider_id", "provider")
```

Order has no direct FK to PrescriptionFill or Prescription. The connection flows the other way.

---

## 2. Prescription Model (`care/models.py`, line 481)

```python
class Prescription(TimestampMixin, models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    consult = models.ForeignKey("consults.Consult", null=False, blank=False, on_delete=models.CASCADE)
    consults = models.ManyToManyField(
        "consults.Consult", through="PrescriptionConsults", related_name="consult_prescription_set"
    )
    tests = models.ManyToManyField("test_results.Test", blank=True, through="PrescriptionTest")
    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE)
    product = models.ForeignKey("care.Product", null=True, blank=True, on_delete=models.CASCADE)
    num_allowed_refills = models.IntegerField(default=0)
    expiration_date = models.DateField(null=True, blank=True)
    deleted = models.BooleanField(default=False)
```

Prescription has **no direct FK to Order** or PrescriptionFill. The connection is through the `PrescriptionFillPrescriptions` through-table.

### Computed Properties on Prescription

**`fill_count`** (line 604): Counts total fills used by querying `PrescriptionFillPrescriptions`, excluding DRAFT and CANCELLED fills:
```python
@property
def fill_count(self) -> int:
    valid_not_cancelled_fills = PrescriptionFillPrescriptions.objects.filter(
        prescription=self
    ).exclude(
        prescriptionfill__status__in=[
            PrescriptionFill.PRESCRIPTION_FILL_STATUS_DRAFT,
            PrescriptionFill.PRESCRIPTION_FILL_STATUS_CANCELLED,
        ]
    )
    total_quantity = sum(fill.get_effective_fill_quantity() for fill in valid_not_cancelled_fills)
    return math.ceil(total_quantity / self.product.quantity_value)
```

**`refills_remaining`** (line 646): Computes remaining refills accounting for expiration date and product-level limits:
```python
@property
def refills_remaining(self):
    if self.expiration_date is not None and self.expiration_date < get_current_time().date():
        return 0
    elif (self.product_id and self.product.max_allowed_refills is not None
          and self.product.max_allowed_refills < self.num_allowed_refills):
        return self.product.max_allowed_refills - self.fill_count + 1
    else:
        return self.num_allowed_refills - self.fill_count + 1
```

**`can_refill`** (line 658): Checks if the prescription is eligible for another fill.

**`is_refillable_product`** (line 631): Returns True if the linked product is not an antibiotic or antifungal.

---

## 3. PrescriptionFill Model (`care/models.py`, line 721)

This is the central hub connecting all three.

```python
class PrescriptionFill(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    status = models.CharField(max_length=255, choices=PRESCRIPTION_FILL_STATUS_CHOICES)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)

    # M2M to Prescription via through-table
    prescriptions = models.ManyToManyField(
        Prescription, blank=True, through="PrescriptionFillPrescriptions"
    )

    # FK to Order (nullable — legacy fills may not have an order)
    order = models.ForeignKey("ecomm.Order", null=True, blank=True, on_delete=models.SET_NULL)

    # FK to Consult (nullable as of 5/2/2025)
    consult = models.ForeignKey("consults.Consult", null=True, blank=True, on_delete=models.CASCADE)

    fill_count = models.IntegerField(default=1)
    sent_to_pharmacy_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Also has M2M to OTCTreatment via through-table
    otctreatments = models.ManyToManyField(
        "OTCTreatment", blank=True, through="PrescriptionFillOTCTreatments"
    )
```

### Computed Properties on PrescriptionFill

**`is_refill`** (line 805): `return self.fill_count > 1`

**`shipping_tracking_url`** (line 798): Derives a tracking URL from `shipping_tracking_number`.

**`full_address_string`** (line 809): Concatenates address fields.

**`can_cancel`** (line 823): True if status is CREATED and `sent_to_pharmacy_at` is set.

---

## 4. Through-Tables

### PrescriptionFillPrescriptions (`care/models.py`, line 864)

This is the **primary M2M bridge** between PrescriptionFill and Prescription.

```python
class PrescriptionFillPrescriptions(models.Model):
    class Meta:
        db_table = "care_prescriptionfill_prescriptions"
        indexes = [
            models.Index(fields=["prescriptionfill"], name="care_pfp_prescriptionfill_idx"),
        ]

    prescriptionfill = models.ForeignKey(
        PrescriptionFill, null=False, blank=False, on_delete=models.CASCADE
    )
    prescription = models.ForeignKey(
        Prescription, null=False, blank=False, on_delete=models.CASCADE
    )
    fill_quantity = models.IntegerField(null=True, blank=True)
    precision_reference_id = models.CharField(max_length=100, blank=True)
```

Extra fields on the through-table:
- `fill_quantity`: quantity dispatched for this fill (may differ from product default)
- `precision_reference_id`: external pharmacy system reference ID

**`get_effective_fill_quantity()`** method (line 881): Falls back to the product's `quantity_value` if `fill_quantity` is not set:
```python
def get_effective_fill_quantity(self) -> int:
    from shipping.precision.utils import get_prescription_fill_quantity
    return self.fill_quantity or get_prescription_fill_quantity(self.prescription)
```

**`save()`** (line 889): Auto-populates `fill_quantity` from `prescription.quantity_value` if not provided.

### PrescriptionFillOrder (`care/models.py`, line 831)

A **secondary join table** connecting PrescriptionFill and Order (in addition to the direct FK on PrescriptionFill). This was backfilled via a script to support the case where multiple orders may relate to one fill.

```python
class PrescriptionFillOrder(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    """For a given consult, stores the order that were placed"""

    prescription_fill = models.ForeignKey(
        PrescriptionFill, null=False, blank=False, on_delete=models.CASCADE
    )
    order = models.ForeignKey("ecomm.Order", null=False, blank=False, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("prescription_fill", "order")
```

---

## 5. Relationship Diagram

```
Order (ecomm/models/order.py)
  |
  | PrescriptionFill.order (FK, nullable, SET_NULL)
  |
  +---> PrescriptionFill (care/models.py, line 721)
           |
           | via PrescriptionFillOrder (care/models.py, line 831)
           |   - additional join table (prescription_fill FK + order FK, unique_together)
           |
           | prescriptions M2M via PrescriptionFillPrescriptions (care/models.py, line 864)
           |   - prescriptionfill FK
           |   - prescription FK
           |   - fill_quantity (int, nullable)
           |   - precision_reference_id (char)
           |
           +---> Prescription (care/models.py, line 481)
                   |
                   | product FK -> care.Product
                   | consult FK -> consults.Consult
                   | user FK -> auth.User
                   |
                   | Computed: fill_count (queries PrescriptionFillPrescriptions)
                   | Computed: refills_remaining (uses fill_count + expiration_date)
                   | Computed: can_refill
```

---

## 6. Key Design Notes

1. **Dual Order linkage on PrescriptionFill**: `PrescriptionFill.order` (direct FK, nullable) AND `PrescriptionFillOrder` (through-table, non-null). The through-table was added later (`backfill_prescription_fill_orders.py`) to support tracking multiple orders per fill. Both are populated in `process_shopify_order_for_treatment_refill` (`ecomm/utils.py`, line 2141-2143):
   ```python
   prescription_fill.order = order
   prescription_fill.save()
   PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)
   ```

2. **M2M fills are what Prescription.fill_count counts**: The `Prescription.fill_count` property traverses `PrescriptionFillPrescriptions` (not `PrescriptionFill.order`) to compute how many refills have been used. This is the authoritative count for eligibility checks.

3. **Order has no reverse accessor to Prescription**: You cannot go directly from `Order` to `Prescription`. You must traverse: `Order` → `PrescriptionFill` (via `prescriptionfill_set` reverse FK or `PrescriptionFillOrder`) → `PrescriptionFillPrescriptions` → `Prescription`.

4. **Status values on PrescriptionFill** that affect `Prescription.fill_count`: DRAFT and CANCELLED fills are excluded from the count.
