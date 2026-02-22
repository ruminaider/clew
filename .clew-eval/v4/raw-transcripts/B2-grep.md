# B2 Exploration Log

## Search 1: Locate Order and Prescription model files
Used Grep for `class Order` across all Python files and a parallel Glob for all `.py` files.

Found:
- `Order` model defined in `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (15 files matched `class Order`)
- `Prescription` model search returned 17 files; the canonical Django ORM model is in `/Users/albertgwo/Work/evvy/backend/care/models.py`

## Search 2: Read Order model
Read `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` in full.

Key findings:
- `Order` has no direct FK or M2M to `Prescription` or `PrescriptionFill`
- `Order` is referenced BY other models via FK (reverse relationships)
- `OrderLineItem` has a FK to `Order` (`related_name="line_items"`)
- `OrderShippingAddress` has a OneToOne to `Order`
- `RelatedOrder` references `Order` twice (parent/cross-sell)

## Search 3: Read care/models.py (Prescription, PrescriptionFill, through-tables)
Read the full `/Users/albertgwo/Work/evvy/backend/care/models.py` — 1384 lines.

Key findings (Prescription model, lines 481–683):
- `Prescription.tests` — M2M to `test_results.Test` through `PrescriptionTest`
- `Prescription.consult` — FK to `consults.Consult` (primary, non-null)
- `Prescription.consults` — M2M to `consults.Consult` through `PrescriptionConsults` (audit log)
- `Prescription.user` — FK to `User`
- `Prescription.product` — FK to `care.Product` (nullable — for non-Evvy products)
- No direct FK to `Order` on `Prescription`
- Computed properties: `fill_count`, `is_refillable_product`, `is_otc_product`, `refills_remaining`, `can_refill`

Key findings (PrescriptionFill model, lines 721–829):
- `PrescriptionFill.prescriptions` — M2M to `Prescription` through `PrescriptionFillPrescriptions`
- `PrescriptionFill.otctreatments` — M2M to `OTCTreatment` through `PrescriptionFillOTCTreatments`
- `PrescriptionFill.consult` — FK to `consults.Consult` (nullable since 5/2/2025)
- `PrescriptionFill.order` — FK to `ecomm.Order` (nullable, `on_delete=SET_NULL`)
- `PrescriptionFill.user` — FK to `User`
- Computed properties: `shipping_tracking_url`, `is_refill`, `full_address_string`, `can_cancel`

Key findings (PrescriptionFillOrder, lines 831–845):
- Through/bridge table connecting `PrescriptionFill` (FK) to `ecomm.Order` (FK)
- Unique constraint on `(prescription_fill, order)`
- This is a second Order linkage (in addition to the direct FK on PrescriptionFill)

Key findings (PrescriptionFillPrescriptions, lines 864–892):
- Through table for M2M between `PrescriptionFill` and `Prescription`
- Fields: `prescriptionfill` (FK), `prescription` (FK), `fill_quantity` (int, nullable), `precision_reference_id` (str)
- `get_effective_fill_quantity()` method falls back to `prescription.quantity_value`
- `save()` sets `fill_quantity` from `prescription.quantity_value` if not provided

Key findings (PrescriptionTest, lines 685–693):
- Through table for `Prescription.tests` M2M
- Fields: `prescription` (FK), `test` (FK to `test_results.Test`)

Key findings (PrescriptionConsults, lines 696–718):
- Through table for `Prescription.consults` M2M (audit table)
- Fields: `prescription` (FK), `consult` (FK), `updated_refill_count`, `updated_expiration_date`, `updated_date`

## Search 4: Check for direct FK/M2M on Order pointing to Prescription/PrescriptionFill
Searched `order.py` for prescription-related references — no matches. Confirmed: `Order` does not directly reference `Prescription` or `PrescriptionFill`. The linkage goes through reverse relations.

## Search 5: Search for usage patterns — prescriptionfill_set, prescription_set reverse accessors
Found:
- `consult.prescriptionfill_set.create(...)` — PrescriptionFill can be accessed from Consult via reverse FK
- `consult.prescription_set.create(...)` — Prescription can be accessed from Consult via reverse FK
- `consult.prescriptionconsults_set.select_related("prescription").all()` — audit through-table accessible from Consult
- `prescription_fill.prescriptionfillorder_set.all()` — PrescriptionFillOrder accessible from PrescriptionFill

## Search 6: Check ecomm/utils.py for Order↔PrescriptionFill linking logic
Found the `process_shopify_order_for_treatment_refill` function (line 2089) which shows:
- When a Shopify order arrives for a refill, the code does:
  1. Looks up or creates `PrescriptionFill` (using `prescription_fill_id` from order attributes or consult)
  2. Sets `prescription_fill.order = order` (the direct FK)
  3. Also calls `PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)` (the through table)
  4. Calls `create_prescription_fill_prescriptions(prescription_fill, list(prescriptions), [order])` to wire prescriptions

## Search 7: Check ConsultOrder model
Found `ConsultOrder` (consults/models.py line 742):
- FK to `Consult` + FK to `ecomm.Order`, unique_together — bridges consult to order
- This provides Consult→Order linkage (not directly Prescription→Order)

## Search 8: Check Prescription.fill_count computed property
Already captured from `care/models.py` lines 604–629:
- `fill_count` queries `PrescriptionFillPrescriptions.objects.filter(prescription=self)` excluding draft/cancelled fills
- Sums `get_effective_fill_quantity()` across through-table rows
- Divides by `product.quantity_value` and rounds up

## Search 9: Check serializer for Prescription
Read `/Users/albertgwo/Work/evvy/backend/api/v1/serializers/prescription.py`.
Exposes: `uid`, `deleted`, `fill_count`, `product`, `is_refillable_product`, `is_otc_product`, `refills_remaining`, `expiration_date`, `can_refill`, `is_disabled_for_refill` — all computed from model properties.

---

## Final Answer

### Models Overview

The three models live in two apps:
- `Order` — `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (line 11)
- `Prescription` — `/Users/albertgwo/Work/evvy/backend/care/models.py` (line 481)
- `PrescriptionFill` — `/Users/albertgwo/Work/evvy/backend/care/models.py` (line 721)

---

### Relationship Map

#### PrescriptionFill → Order (direct FK, nullable)
```python
# care/models.py line 770
order = models.ForeignKey("ecomm.Order", null=True, blank=True, on_delete=models.SET_NULL)
```
`PrescriptionFill` holds a direct nullable FK to `ecomm.Order`. Set `null=True` / `on_delete=SET_NULL` so deleting an order does not cascade to fill records. Reverse accessor on `Order`: `order.prescriptionfill_set`.

#### PrescriptionFill → Order (through PrescriptionFillOrder)
```python
# care/models.py lines 831–845
class PrescriptionFillOrder(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    prescription_fill = models.ForeignKey(PrescriptionFill, null=False, blank=False, on_delete=models.CASCADE)
    order = models.ForeignKey("ecomm.Order", null=False, blank=False, on_delete=models.CASCADE)
    class Meta:
        unique_together = ("prescription_fill", "order")
```
A dedicated bridge table (`care_prescriptionfillorder`) tracks the same PrescriptionFill→Order relationship more durably. A single PrescriptionFill can be associated with multiple Orders (e.g., when a replacement order is issued). Accessible via `prescription_fill.prescriptionfillorder_set.all()`.

#### PrescriptionFill ↔ Prescription (M2M through PrescriptionFillPrescriptions)
```python
# care/models.py lines 755–757
prescriptions = models.ManyToManyField(
    Prescription, blank=True, through="PrescriptionFillPrescriptions"
)
```
Through table definition:
```python
# care/models.py lines 864–892
class PrescriptionFillPrescriptions(models.Model):
    class Meta:
        db_table = "care_prescriptionfill_prescriptions"
    prescriptionfill = models.ForeignKey(PrescriptionFill, null=False, blank=False, on_delete=models.CASCADE)
    prescription    = models.ForeignKey(Prescription,     null=False, blank=False, on_delete=models.CASCADE)
    fill_quantity          = models.IntegerField(null=True, blank=True)
    precision_reference_id = models.CharField(max_length=100, blank=True)
```
Extra fields on the through table:
- `fill_quantity` — quantity dispensed for this prescription in this fill
- `precision_reference_id` — external pharmacy reference ID

`get_effective_fill_quantity()` (line 881) falls back to `prescription.quantity_value` if `fill_quantity` is null.

#### Prescription → Order (no direct FK — indirect through PrescriptionFill)
`Prescription` has **no direct FK or M2M to `Order`**. The path is:
```
Prescription ← PrescriptionFillPrescriptions → PrescriptionFill → Order
```
Or equivalently via `PrescriptionFillOrder`.

---

### Computed Properties That Bridge the Models

#### On `Prescription` (care/models.py lines 604–666)

**`fill_count` (int)**
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
Traverses the M2M through table (`PrescriptionFillPrescriptions`) to count non-draft, non-cancelled fills for this prescription.

**`refills_remaining` (int)**
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
Depends on `fill_count` which traverses PrescriptionFillPrescriptions → PrescriptionFill.

**`can_refill` (bool)**
```python
@property
def can_refill(self):
    return (
        self.refills_remaining > 0
        and self.is_refillable_product
        and self.expiration_date > get_current_time().date()
        and not self.product.is_disabled_for_refill
        and not self.product.is_deprecated
    )
```
Transitively depends on `fill_count` via `refills_remaining`.

**`is_refillable_product` (bool)**
```python
@property
def is_refillable_product(self):
    return self.product_id and self.product.type not in [
        Product.TYPE_ANTIBIOTIC,
        Product.TYPE_ANTIFUNGAL,
    ]
```

**`is_otc_product` (bool)**
```python
@property
def is_otc_product(self):
    return (
        self.product
        and self.product.regulatory_category == RegulatoryCategory.OVER_THE_COUNTER.code
    )
```

#### On `PrescriptionFill` (care/models.py lines 798–828)

**`is_refill` (bool)**
```python
@property
def is_refill(self):
    return self.fill_count > 1
```
Note: `PrescriptionFill.fill_count` is a stored integer field (not computed), incremented each time a refill is processed.

**`can_cancel` (bool)**
```python
@property
def can_cancel(self):
    return (
        self.status == self.PRESCRIPTION_FILL_STATUS_CREATED
        and self.sent_to_pharmacy_at is not None
    )
```

**`shipping_tracking_url` (str)**
```python
@property
def shipping_tracking_url(self):
    from shipping.utils import get_provider_tracking_url
    return get_provider_tracking_url(self.shipping_tracking_number)
```

**`full_address_string` (str)**
Concatenates address fields stored on PrescriptionFill for the shipping address sent to precision pharmacy.

---

### Complete Relationship Diagram

```
ecomm.Order
    │
    │ (reverse: prescriptionfill_set)
    ▼
care.PrescriptionFill ──────────────────────────────────────────────────────────┐
    │  FK: order (nullable, SET_NULL)                                             │
    │  FK: consult (nullable FK to consults.Consult)                              │
    │  FK: user                                                                   │
    │                                                                             │
    │  M2M: prescriptions (through PrescriptionFillPrescriptions)                 │
    │  M2M: otctreatments (through PrescriptionFillOTCTreatments)                 │
    │                                                                             │
    ▼                                                                             │
care.PrescriptionFillPrescriptions                             care.PrescriptionFillOrder
    │  FK: prescriptionfill                                        FK: prescription_fill
    │  FK: prescription                                            FK: order (ecomm.Order)
    │  fill_quantity (int)                                         unique_together (fill, order)
    │  precision_reference_id (str)
    ▼
care.Prescription
    │  FK: consult (non-null FK to consults.Consult)
    │  FK: user
    │  FK: product (nullable FK to care.Product)
    │  M2M: tests (through PrescriptionTest → test_results.Test)
    │  M2M: consults (through PrescriptionConsults, audit log)
    │
    │  [NO DIRECT FK TO Order]
    │
    Computed properties (all bridge through PrescriptionFillPrescriptions):
      fill_count        → counts non-draft/cancelled fills
      refills_remaining → num_allowed_refills - fill_count + 1 (with expiry/product caps)
      can_refill        → refills_remaining > 0 AND not expired AND product is refillable
      is_refillable_product → product type not antibiotic/antifungal
      is_otc_product    → product.regulatory_category == OTC
```

---

### Key Design Notes

1. **Dual Order linkage on PrescriptionFill**: Both a direct nullable FK (`prescriptionfill.order`) and a through table (`PrescriptionFillOrder`) exist. The through table was added later (migration `0056_prescriptionfillorder`) to support replacement orders where multiple `Order` records map to one `PrescriptionFill`. Application code at `ecomm/utils.py` line 2143 writes both simultaneously.

2. **No direct Prescription → Order path**: To find the orders associated with a given `Prescription`, you must traverse: `Prescription` → `PrescriptionFillPrescriptions` → `PrescriptionFill` → `PrescriptionFillOrder` → `Order` (or `PrescriptionFill.order`).

3. **Consult as the hub**: `Consult` is the central hub connecting everything. Both `Prescription` (non-nullable FK) and `PrescriptionFill` (nullable FK) point to `Consult`. `ConsultOrder` (`consults/models.py` line 742) separately links `Consult` to `Order`.

4. **OTCTreatment is a parallel track**: `PrescriptionFill` also has a direct FK to `ecomm.Order` on `OTCTreatment` (`care/models.py` line 906–912, `related_name="otc_treatments"`), making OTC treatments directly Order-linked without going through PrescriptionFill.
