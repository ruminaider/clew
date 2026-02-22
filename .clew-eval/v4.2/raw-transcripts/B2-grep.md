# B2: Order, PrescriptionFill, and Prescription Model Relationships

## Summary

The three models form a care fulfillment chain: `Order` (e-commerce purchase) → `PrescriptionFill` (pharmacy fulfillment event) → `Prescription` (individual drug authorization). The models are defined primarily in `/Users/albertgwo/Work/evvy/backend/care/models.py` and `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`.

---

## 1. Order Model

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`

```python
class Order(TimestampMixin, models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    cart = models.ForeignKey("Cart", null=True, blank=True, on_delete=models.SET_NULL)
    order_type = models.CharField(max_length=2, choices=ORDER_TYPE_CHOICES, ...)
    status = models.CharField(max_length=2, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    ...
```

**Key order types relevant to prescriptions:**
- `ORDER_TYPE_VAGINITIS_CARE = "CA"` — Vaginitis care (triggers consult/prescription flow)
- `ORDER_TYPE_PRESCRIPTION_TREATMENT = "PR"` — Prescription refill
- `ORDER_TYPE_UNGATED_RX = "UX"` — Ungated Rx (may route to refill or new consult)
- `ORDER_TYPE_A_LA_CARTE = "AL"`, `ORDER_TYPE_DYNAMIC_BUNDLE = "BU"`, `ORDER_TYPE_MIXED_CARE = "MC"`

---

## 2. Prescription Model

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 481–682)

```python
class Prescription(TimestampMixin, models.Model):
    uid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # Primary FK to consult that issued this prescription
    consult = models.ForeignKey("consults.Consult", null=False, blank=False, on_delete=models.CASCADE)

    # Audit M2M — tracks all consults that modified this prescription over time
    consults = models.ManyToManyField(
        "consults.Consult",
        through="PrescriptionConsults",
        related_name="consult_prescription_set"
    )

    # M2M to test results
    tests = models.ManyToManyField("test_results.Test", blank=True, through="PrescriptionTest")

    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE)

    # Nullable: if None, the drug is non-Evvy (off-formulary)
    product = models.ForeignKey("care.Product", null=True, blank=True, on_delete=models.CASCADE)

    num_allowed_refills = models.IntegerField(default=0)
    prescription_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    deleted = models.BooleanField(default=False, verbose_name="soft deleted")
    sent_to_pharmacy_at = models.DateTimeField(null=True, blank=True)
```

### Prescription Computed Properties

```python
@property
def fill_count(self) -> int:
    """Total fills used (rounded up), computed via PrescriptionFillPrescriptions through-table."""
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

@property
def refills_remaining(self):
    """Considers expiration_date, product.max_allowed_refills, and fill_count."""
    ...

@property
def can_refill(self):
    """True if refills_remaining > 0, product is refillable, not expired, not deprecated."""
    ...

@property
def is_refillable_product(self):
    """True if product is not antibiotic or antifungal."""
    ...
```

---

## 3. PrescriptionFill Model

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 721–829)

```python
class PrescriptionFill(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    status = models.CharField(max_length=255, choices=PRESCRIPTION_FILL_STATUS_CHOICES, ...)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)

    # FK to the consult that initiated this fill
    consult = models.ForeignKey("consults.Consult", null=True, blank=True, on_delete=models.CASCADE)

    # DIRECT FK to Order (the purchase that paid for this fill)
    order = models.ForeignKey("ecomm.Order", null=True, blank=True, on_delete=models.SET_NULL)

    # M2M to Prescription via through-table
    prescriptions = models.ManyToManyField(Prescription, blank=True, through="PrescriptionFillPrescriptions")

    # M2M to OTCTreatment via through-table
    otctreatments = models.ManyToManyField("OTCTreatment", blank=True, through="PrescriptionFillOTCTreatments")

    fill_count = models.IntegerField(default=1)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    sent_to_pharmacy_at = models.DateTimeField(null=True, blank=True)
    shipping_tracking_number = models.CharField(max_length=255, blank=True)
```

**Status choices:** `draft`, `created`, `shipped`, `delivered`, `warning`, `cancelled`, `failed`

### PrescriptionFill Computed Properties

```python
@property
def is_refill(self):
    return self.fill_count > 1

@property
def shipping_tracking_url(self):
    from shipping.utils import get_provider_tracking_url
    return get_provider_tracking_url(self.shipping_tracking_number)

@property
def can_cancel(self):
    return (
        self.status == self.PRESCRIPTION_FILL_STATUS_CREATED
        and self.sent_to_pharmacy_at is not None
    )

@property
def full_address_string(self):
    # concatenates address_first_line, address_second_line, city, state_code, zip_code
    ...
```

---

## 4. Direct FK Relationships

### PrescriptionFill → Order (direct FK)

```python
# In PrescriptionFill (care/models.py line 770):
order = models.ForeignKey("ecomm.Order", null=True, blank=True, on_delete=models.SET_NULL)
```

This is the **primary runtime link**: when an Order is paid (Shopify webhook), the system sets `prescription_fill.order = order` directly.

**Set in:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` inside `process_shopify_order_for_treatment_refill()`:

```python
# 4. set the order on the prescription fill and through table
prescription_fill.order = order
prescription_fill.save()
PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)
```

---

## 5. Through Tables

### PrescriptionFillPrescriptions (PrescriptionFill ↔ Prescription M2M)

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 864–892)

```python
class PrescriptionFillPrescriptions(models.Model):
    class Meta:
        db_table = "care_prescriptionfill_prescriptions"
        indexes = [
            models.Index(fields=["prescriptionfill"], name="care_pfp_prescriptionfill_idx"),
        ]

    prescriptionfill = models.ForeignKey(PrescriptionFill, null=False, blank=False, on_delete=models.CASCADE)
    prescription = models.ForeignKey(Prescription, null=False, blank=False, on_delete=models.CASCADE)
    fill_quantity = models.IntegerField(null=True, blank=True)
    precision_reference_id = models.CharField(max_length=100, blank=True)

    def get_effective_fill_quantity(self) -> int:
        """Falls back to product's quantity_value if fill_quantity is not set."""
        return self.fill_quantity or get_prescription_fill_quantity(self.prescription)

    def save(self, *args, **kwargs):
        if not self.fill_quantity:
            self.fill_quantity = self.prescription.quantity_value
        super().save(*args, **kwargs)
```

This is the **critical bridge** used by `Prescription.fill_count` to determine how many units of a given prescription have been dispensed across all fills.

### PrescriptionFillOrder (PrescriptionFill ↔ Order M2M audit table)

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 831–845)

```python
class PrescriptionFillOrder(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    """
    For a given consult, stores the order that were placed
    """
    prescription_fill = models.ForeignKey(PrescriptionFill, null=False, blank=False, on_delete=models.CASCADE)
    order = models.ForeignKey("ecomm.Order", null=False, blank=False, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("prescription_fill", "order")
```

This is a **secondary audit/history table** — it records all orders ever associated with a PrescriptionFill (e.g., replacement orders). The direct FK `PrescriptionFill.order` is used for active lookups; this table is used for historical audit queries.

### PrescriptionConsults (Prescription ↔ Consult M2M audit table)

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 696–718)

```python
class PrescriptionConsults(TimestampMixin, models.Model):
    """
    Through table for audit — tracks updates to prescriptions through time.
    """
    prescription = models.ForeignKey(Prescription, null=False, blank=False, on_delete=models.CASCADE)
    consult = models.ForeignKey("consults.Consult", null=False, blank=False, on_delete=models.CASCADE)
    updated_refill_count = models.IntegerField(null=True, blank=True)
    updated_expiration_date = models.DateField(null=True, blank=True)
    updated_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("prescription", "consult")
```

### PrescriptionTest (Prescription ↔ Test M2M)

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 685–693)

```python
class PrescriptionTest(TimestampMixin, models.Model):
    """
    Through table: many-to-many between prescriptions and tests.
    """
    prescription = models.ForeignKey(Prescription, null=False, blank=False, on_delete=models.CASCADE)
    test = models.ForeignKey("test_results.Test", null=False, blank=False, on_delete=models.CASCADE)
```

---

## 6. Indirect Order → Prescription Path

There is no direct FK from `Order` to `Prescription`. The path is:

```
Order
  └──> PrescriptionFill.order (direct FK)
         └──> PrescriptionFillPrescriptions (through table)
                └──> Prescription
```

Or via the audit table:

```
Order
  └──> PrescriptionFillOrder.order (M2M audit table)
         └──> PrescriptionFillOrder.prescription_fill
                └──> PrescriptionFillPrescriptions
                       └──> Prescription
```

In `process_shopify_order_for_treatment_refill()` (`ecomm/utils.py`), prescriptions for a refill order are looked up either:
1. By explicit `prescription_ids` stored in Shopify order note attributes, or
2. By user's active prescriptions for the products in the order (evergreen prescription path):

```python
prescriptions = (
    Prescription.objects.filter(user=order.user, product__in=rx_products, deleted=False)
    .order_by("product_id", "create_date")
    .distinct("product_id")
)
```

---

## 7. Key Utility Functions

### `get_first_consult_prescription_fill(consult)`
**File:** `/Users/albertgwo/Work/evvy/backend/consults/service.py` (line 41)

```python
def get_first_consult_prescription_fill(consult: Consult) -> PrescriptionFill:
    return (
        consult.prescriptionfill_set.filter(cancelled_at__isnull=True)
        .order_by("-create_date")
        .first()
    )
```

Used in the consult serializer to surface the shipping tracking URL for the most recent fill.

### `can_refill_entire_order(user, order)`
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (line 2732)

Checks whether every Rx product in an order has a valid `Prescription.can_refill == True` for the given user. Used to route ungated Rx orders.

---

## 8. Relationship Diagram

```
Order (ecomm.Order)
  │
  ├── PrescriptionFill.order [FK, nullable, SET_NULL]
  │     │
  │     ├── PrescriptionFillPrescriptions [through table]
  │     │     ├── prescriptionfill FK → PrescriptionFill
  │     │     ├── prescription FK → Prescription
  │     │     ├── fill_quantity (int, nullable)
  │     │     └── precision_reference_id (str)
  │     │
  │     └── PrescriptionFillOrder [M2M audit table, unique_together(fill, order)]
  │           ├── prescription_fill FK → PrescriptionFill
  │           └── order FK → Order
  │
  └── OTCTreatment.order [FK, non-null, CASCADE, related_name="otc_treatments"]
        └── PrescriptionFillOTCTreatments [through table]
              └── prescriptionfill FK → PrescriptionFill


Prescription (care.Prescription)
  │
  ├── consult FK → consults.Consult [non-null, CASCADE]
  ├── consults M2M → consults.Consult [through PrescriptionConsults — audit]
  ├── tests M2M → test_results.Test [through PrescriptionTest]
  ├── user FK → User [non-null, CASCADE]
  ├── product FK → care.Product [nullable]
  │
  └── [reverse] PrescriptionFillPrescriptions → PrescriptionFill (via M2M prescriptions field)


PrescriptionFill (care.PrescriptionFill)
  │
  ├── order FK → ecomm.Order [nullable, SET_NULL]  ← direct link to Order
  ├── consult FK → consults.Consult [nullable, CASCADE]
  ├── user FK → User [nullable, CASCADE]
  ├── prescriptions M2M → Prescription [through PrescriptionFillPrescriptions]
  └── otctreatments M2M → OTCTreatment [through PrescriptionFillOTCTreatments]
```

---

## 9. Notable Design Decisions

1. **Dual Order linkage on PrescriptionFill**: Both a direct FK (`PrescriptionFill.order`) and an audit through-table (`PrescriptionFillOrder`) exist simultaneously. The direct FK is the active pointer; the through-table preserves history of all associated orders (e.g., replacement orders).

2. **`Prescription.fill_count` crosses M2M boundary**: This computed property on `Prescription` traverses back through `PrescriptionFillPrescriptions` to count units dispensed — it does not count fills directly, but sums `fill_quantity` values from the through-table records.

3. **No direct Order → Prescription FK**: Orders don't directly reference Prescriptions. The relationship is always mediated by `PrescriptionFill`. During order processing, prescriptions are looked up by user + product to match the fill.

4. **Soft-delete on Prescription**: `deleted=True` excludes a prescription from active `fill_count` and `can_refill` computations, but the record is preserved.

5. **`PrescriptionFill.fill_count` vs `Prescription.fill_count`**: These are different fields. `PrescriptionFill.fill_count` (integer, default=1) tracks which fill number this event is (1st fill, 2nd fill, etc.). `Prescription.fill_count` (computed property) counts total units consumed across all fills of that prescription.
