# B2 — Agent Beta

Here is the complete relationship map between `Order`, `PrescriptionFill`, and `Prescription`.

---

## Model Definitions

All three core models live in `/Users/albertgwo/Work/evvy/backend/care/models.py`. `Order` lives in `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`.

---

## 1. Order (ecomm app)

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`, line 11

`Order` is the Shopify-backed purchase record. It has no direct foreign key to `Prescription` or `PrescriptionFill`. The relationship goes the other way — both `PrescriptionFill` and `OTCTreatment` point at `Order`.

---

## 2. PrescriptionFill (care app)

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py`, line 721

This model represents a single fulfillment event — a physical shipment sent to the pharmacy (Precision).

### Foreign keys on PrescriptionFill

```python
order = models.ForeignKey("ecomm.Order", null=True, blank=True, on_delete=models.SET_NULL)
consult = models.ForeignKey("consults.Consult", null=True, blank=True, on_delete=models.CASCADE)
user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
```

### Many-to-many on PrescriptionFill

```python
prescriptions = models.ManyToManyField(
    Prescription, blank=True, through="PrescriptionFillPrescriptions"
)
otctreatments = models.ManyToManyField(
    "OTCTreatment", blank=True, through="PrescriptionFillOTCTreatments"
)
```

### Computed properties on PrescriptionFill

```python
@property
def shipping_tracking_url(self): ...
@property
def is_refill(self):
    return self.fill_count > 1
@property
def full_address_string(self): ...
@property
def can_cancel(self):
    return (
        self.status == self.PRESCRIPTION_FILL_STATUS_CREATED
        and self.sent_to_pharmacy_at is not None
    )
```

---

## 3. Prescription (care app)

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py`, line 481

### Foreign keys on Prescription

```python
consult = models.ForeignKey("consults.Consult", null=False, blank=False, on_delete=models.CASCADE)
user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE)
product = models.ForeignKey("care.Product", null=True, blank=True, on_delete=models.CASCADE)
```

### Many-to-many on Prescription

```python
tests = models.ManyToManyField("test_results.Test", blank=True, through="PrescriptionTest")
consults = models.ManyToManyField(
    "consults.Consult", through="PrescriptionConsults", related_name="consult_prescription_set"
)
```

### Computed properties on Prescription that bridge to PrescriptionFill

```python
@property
def fill_count(self) -> int:
    # Queries PrescriptionFillPrescriptions excluding DRAFT and CANCELLED fills
    # sums fill_quantity from each row, divides by product.quantity_value, rounds up

@property
def refills_remaining(self):
    # Uses fill_count and num_allowed_refills; also caps at product.max_allowed_refills

@property
def can_refill(self):
    # True if refills_remaining > 0, product is refillable, not expired, not deprecated

@property
def is_refillable_product(self):
    # True if product exists and is NOT antibiotic or antifungal

@property
def is_otc_product(self):
    # True if product.regulatory_category == OVER_THE_COUNTER
```

---

## 4. Through-Tables

### PrescriptionFillPrescriptions

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py`, line 864

```python
class PrescriptionFillPrescriptions(models.Model):
    class Meta:
        db_table = "care_prescriptionfill_prescriptions"

    prescriptionfill = models.ForeignKey(PrescriptionFill, ...)
    prescription = models.ForeignKey(Prescription, ...)
    fill_quantity = models.IntegerField(null=True, blank=True)
    precision_reference_id = models.CharField(...)

    def get_effective_fill_quantity(self) -> int:
        # Falls back to prescription.product.quantity_value if fill_quantity is null
```

### PrescriptionFillOrder

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py`, line 831

```python
class PrescriptionFillOrder(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    prescription_fill = models.ForeignKey(PrescriptionFill, ...)
    order = models.ForeignKey("ecomm.Order", ...)

    class Meta:
        unique_together = ("prescription_fill", "order")
```

### PrescriptionConsults

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py`, line 696

```python
class PrescriptionConsults(TimestampMixin, models.Model):
    prescription = models.ForeignKey(Prescription, ...)
    consult = models.ForeignKey("consults.Consult", ...)
    updated_refill_count = models.IntegerField(null=True, blank=True)
    updated_expiration_date = models.DateField(null=True, blank=True)
    updated_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("prescription", "consult")
```

### PrescriptionTest

**File:** `/Users/albertgwo/Work/evvy/backend/care/models.py`, line 685

```python
class PrescriptionTest(TimestampMixin, models.Model):
    prescription = models.ForeignKey(Prescription, ...)
    test = models.ForeignKey("test_results.Test", ...)
```

---

## 5. Complete Relationship Diagram

```
ecomm.Order
    |
    |-- FK <- PrescriptionFill.order  (nullable, SET_NULL)
    |-- FK <- PrescriptionFillOrder.order  (NOT NULL, CASCADE)  [audit/extra link]
    |-- FK <- OTCTreatment.order  (NOT NULL, CASCADE)
    |
    care.PrescriptionFill
        |-- FK  -> consults.Consult     (nullable)
        |-- FK  -> auth.User            (nullable)
        |-- FK  -> ecomm.Order          (nullable, direct primary order)
        |-- M2M -> care.Prescription    via PrescriptionFillPrescriptions
        |         fill_quantity, precision_reference_id per row
        |-- M2M -> care.OTCTreatment   via PrescriptionFillOTCTreatments
        |
        Properties:
            is_refill         (fill_count > 1)
            can_cancel
            shipping_tracking_url
            full_address_string

    care.Prescription
        |-- FK  -> consults.Consult     (NOT NULL, CASCADE) -- primary consult
        |-- FK  -> auth.User            (NOT NULL, CASCADE)
        |-- FK  -> care.Product         (nullable -- null if non-Evvy drug)
        |-- M2M -> test_results.Test    via PrescriptionTest
        |-- M2M -> consults.Consult     via PrescriptionConsults (audit trail)
        |
        Properties:
            fill_count         (counts active PrescriptionFillPrescriptions rows)
            refills_remaining  (num_allowed_refills - fill_count + 1, capped)
            can_refill         (refills_remaining > 0 and product refillable and not expired)
            is_refillable_product
            is_otc_product
```

---

## 6. Key Design Notes

1. **Dual Order link on PrescriptionFill**: `PrescriptionFill.order` is a direct FK (primary order). `PrescriptionFillOrder` is a separate through-table that records all orders ever associated with a fill.

2. **fill_count lives on Prescription, not PrescriptionFill**: `Prescription.fill_count` queries `PrescriptionFillPrescriptions` to sum quantities across fills, excluding draft/cancelled fills. `PrescriptionFill.fill_count` is a simple integer field (fill number: 1 = initial, 2+ = refill).

3. **`consult_prescription.py` is a separate Pydantic model**: used for Wheel API payloads. It is not a Django ORM model.

4. **Order -> Prescription path is indirect**: There is no direct FK from `Order` to `Prescription`. To get prescriptions from an order you traverse: `Order -> PrescriptionFill (via .order FK or PrescriptionFillOrder) -> PrescriptionFillPrescriptions -> Prescription`.
