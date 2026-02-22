# B2 Exploration Log

## Search 1: Order, PrescriptionFill, Prescription model relationships (broad)

Searched: "Order PrescriptionFill Prescription model relationships foreign keys"

Key findings:
- Top result: `PrescriptionFillOrder` class at `backend/care/models.py` lines 831-845 — a through/junction model connecting PrescriptionFill and Order.
- `PrescriptionFill` at lines 721-828 — the central model with FKs to Order, Consult, User, and M2M to Prescription via `PrescriptionFillPrescriptions`.
- `PrescriptionFillPrescriptions` at lines 864-892 — explicit through table for the PrescriptionFill↔Prescription many-to-many.
- `PrescriptionFillOTCTreatments` at lines 927-952 — parallel through table for OTC treatments.

## Search 2: Read PrescriptionFill and surrounding models (lines 700–1000 of care/models.py)

Read `backend/care/models.py` lines 700-1000 directly.

Key findings from the code:

**PrescriptionConsults** (lines 696-718): Through table tracking the many-to-many between `Prescription` and `Consult`. Stores `updated_refill_count`, `updated_expiration_date`, `updated_date` as an audit trail.

**PrescriptionFill** (lines 721-828):
- `user` — FK to User (nullable)
- `prescriptions` — ManyToManyField to Prescription via through="PrescriptionFillPrescriptions"
- `otctreatments` — ManyToManyField to OTCTreatment via through="PrescriptionFillOTCTreatments"
- `consult` — FK to consults.Consult (nullable as of 5/2/2025)
- `order` — FK to ecomm.Order (nullable, SET_NULL on delete) — the **direct/legacy** link between PrescriptionFill and Order
- `status`, `shipped_at`, `delivered_at`, `cancelled_at`, `sent_to_pharmacy_at`, `fill_count`, address fields, `pharmacy_patient_id`, `payload`
- Computed properties: `shipping_tracking_url`, `is_refill`, `full_address_string`, `can_cancel`

**PrescriptionFillOrder** (lines 831-845): The explicit **through/junction table** between PrescriptionFill and Order:
- `prescription_fill` — FK to PrescriptionFill (CASCADE, non-null)
- `order` — FK to ecomm.Order (CASCADE, non-null)
- `unique_together = ("prescription_fill", "order")`

**PrescriptionFillPrescriptions** (lines 864-892): Through table for PrescriptionFill↔Prescription M2M:
- `prescriptionfill` — FK to PrescriptionFill (CASCADE, non-null)
- `prescription` — FK to Prescription (CASCADE, non-null)
- `fill_quantity` — IntegerField (nullable)
- `precision_reference_id` — CharField
- `db_table = "care_prescriptionfill_prescriptions"`
- Method: `get_effective_fill_quantity()` — falls back to `prescription.product.quantity_value` if fill_quantity unset
- `save()` auto-sets fill_quantity from prescription.quantity_value on creation

## Search 3: Find Prescription model definition

Searched: "Prescription model definition fields foreign keys"

Found `Prescription` at `backend/care/models.py` lines 481-682.

## Search 4: Read Prescription model (lines 481-682)

**Prescription** (lines 481-682):
- `uid` — UUIDField (unique)
- `tests` — ManyToManyField to test_results.Test via through="PrescriptionTest"
- `consult` — FK to consults.Consult (non-null, CASCADE) — primary/original consult association
- `consults` — ManyToManyField to consults.Consult via through="PrescriptionConsults" (related_name="consult_prescription_set") — audit M2M for tracking prescription updates across multiple consults
- `user` — FK to User (non-null, CASCADE)
- `product` — FK to care.Product (nullable, CASCADE)
- `prescription_date`, `expiration_date`, `display_name`, `patient_instructions`
- `quantity_value`, `quantity_unit`, `supply_duration_value`, `supply_duration_unit`
- `num_allowed_refills` — IntegerField (default=0)
- `rx_price` — DecimalField
- `deleted`, `delete_reason`, `delete_reason_other`, `deleted_at` — soft-delete fields
- `created_by` — CharField (PROVIDER / EVVY)
- `sent_to_pharmacy_at`
- `needs_subscription_cancellation` — BooleanField

Computed properties on Prescription:
- `fill_count` — queries PrescriptionFillPrescriptions for this prescription, excludes DRAFT/CANCELLED fills, sums effective quantities, divides by product.quantity_value, rounds up. **This is the primary bridge from Prescription back to PrescriptionFill.**
- `is_refillable_product` — checks product type not antibiotic/antifungal
- `is_otc_product` — checks product regulatory_category
- `refills_remaining` — `num_allowed_refills - fill_count + 1`, capped by product.max_allowed_refills if set, returns 0 if expired
- `can_refill` — compound check: refills_remaining > 0, is_refillable, not expired, product not disabled/deprecated

## Search 5: Find Order model definition

Searched: "Order model ecomm fields shopify"

Found `Order` at `backend/ecomm/models/order.py` lines 11-181.

## Search 6: Read Order model

**Order** (backend/ecomm/models/order.py lines 11-181):
- `user` — FK to User (nullable)
- `cart` — FK to Cart (nullable, SET_NULL)
- `email`, `evvy_account_email`
- `provider`, `provider_id`, `order_number`
- `checkout_id`, `checkout_token`, `shopify_order_id`, `shopify_customer_id`
- `order_type` — CharField with choices (PRESCRIPTION_TREATMENT "PR", VAGINITIS_CARE "CA", UNGATED_RX "UX", etc.)
- `business_verticals` — MultiSelectField
- `sku`, `status`, `shipping_method`
- `payload` — JSONField (full Shopify webhook payload)
- `is_manual_invoice`, `is_subscription_order`, `is_testing_order`
- `total_line_items_price`, `sent_to_berlin_at`, `checkout_source`

The Order model itself has **no direct foreign keys to PrescriptionFill or Prescription**. Relationships go in the opposite direction (PrescriptionFill holds the FK to Order, PrescriptionFillOrder is the junction).

Reverse managers available on Order from Django ORM:
- `prescriptionfill_set` — from PrescriptionFill.order FK (default reverse name)
- `prescriptionfillorder_set` — from PrescriptionFillOrder.order FK

## Search 7: Computed properties bridging PrescriptionFill and Order

Searched: "PrescriptionFill order property computed relationship"

Found the backfill script at `backend/scripts/backfill_ecomm_order_on_prescription_fill.py` which confirms the pattern: `consult.prescriptionfill_set` gives access to fills from a consult, and the `order` field on PrescriptionFill was backfilled from `consult.order`.

## Search 8: process_shopify_order_for_treatment_refill (how Order→PrescriptionFill linkage is built at runtime)

Read `backend/ecomm/utils.py` lines 2089-2201.

This is the key wiring function showing how Order, PrescriptionFill, and Prescription are linked:

1. Parse order attributes to get prescription_fill_id
2. Get or create a `PrescriptionFill` using `order` as lookup param if no fill ID present
3. Set `prescription_fill.order = order` (direct FK)
4. Call `PrescriptionFillOrder.objects.get_or_create(prescription_fill=prescription_fill, order=order)` (junction table)
5. Resolve Prescription objects from order attributes (prescription_ids) or by matching user+product
6. Call `create_prescription_fill_prescriptions(prescription_fill, prescriptions, [order])` to populate the through table

## Search 9: create_prescription_fill_prescriptions utility

Read `backend/shipping/precision/utils.py` lines 821-843.

This function:
- Takes a `PrescriptionFill`, list of `Prescription` objects, and list of `Order` objects
- Computes fill_quantity from order line item quantities
- Calls `PrescriptionFillPrescriptions.objects.get_or_create(prescriptionfill=..., prescription=...)` to link them

## Search 10: Trace PrescriptionFill to map all relationships

Used `clew trace PrescriptionFill` to get the structural graph. Confirmed:
- PrescriptionFillOrder has_fk → PrescriptionFill
- FillPackagingItem has_fk → PrescriptionFill
- PrescriptionFillPrescriptions has_fk → PrescriptionFill
- PrescriptionFillOTCTreatments has_fk → PrescriptionFill
- PrescriptionFillOrder has_fk → ecomm.Order (depth 2)

## Search 11: Trace Prescription relationships

Used `clew trace Prescription` to verify:
- PrescriptionTest has_fk → Prescription
- PrescriptionConsults has_fk → Prescription
- PrescriptionFill has_m2m → Prescription (through PrescriptionFillPrescriptions)
- PrescriptionFillPrescriptions has_fk → Prescription

---

## Final Answer

### Overview

The three models — `Order` (ecomm), `PrescriptionFill` (care), and `Prescription` (care) — form the backbone of Evvy's prescription fulfillment pipeline. They are connected through a combination of direct foreign keys, an explicit junction table, a many-to-many with a through table, and computed properties. All definitions live in:

- **`/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`** — `Order` (lines 11-181)
- **`/Users/albertgwo/Work/evvy/backend/care/models.py`** — `Prescription` (lines 481-682), `PrescriptionConsults` (696-718), `PrescriptionFill` (721-828), `PrescriptionFillOrder` (831-845), `PrescriptionFillPrescriptions` (864-892)

---

### Order Model (`ecomm.Order`)

`Order` has **no direct foreign keys to PrescriptionFill or Prescription**. Linkage flows in the other direction. Key fields relevant to the prescription pipeline:

```python
# backend/ecomm/models/order.py lines 11-181
class Order(TimestampMixin, models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    order_type = models.CharField(...)  # includes ORDER_TYPE_PRESCRIPTION_TREATMENT = "PR", ORDER_TYPE_UNGATED_RX = "UX"
    status = models.CharField(...)  # STATUS_ACTIVE / STATUS_CANCELLED
    payload = models.JSONField(default=dict, blank=True)  # full Shopify webhook payload
    # No FK to PrescriptionFill or Prescription
```

Reverse access from Order:
- `order.prescriptionfill_set.all()` — all PrescriptionFills whose `order` FK points here (Django default reverse manager)
- `order.prescriptionfillorder_set.all()` — all PrescriptionFillOrder junction records
- `order.otc_treatments.all()` — OTCTreatments via `related_name="otc_treatments"` on `OTCTreatment.order`

---

### PrescriptionFill Model (`care.PrescriptionFill`)

PrescriptionFill is the central hub. It holds:

**Direct FK to Order:**
```python
# backend/care/models.py line 770
order = models.ForeignKey("ecomm.Order", null=True, blank=True, on_delete=models.SET_NULL)
```
This is the **legacy direct link** — nullable, SET_NULL on delete. A PrescriptionFill may reference at most one primary Order this way.

**M2M to Prescription via through table:**
```python
# backend/care/models.py lines 755-757
prescriptions = models.ManyToManyField(
    Prescription, blank=True, through="PrescriptionFillPrescriptions"
)
```

**Other FKs:**
```python
user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
consult = models.ForeignKey("consults.Consult", null=True, blank=True, on_delete=models.CASCADE)
otctreatments = models.ManyToManyField("OTCTreatment", blank=True, through="PrescriptionFillOTCTreatments")
```

**Status lifecycle:**
- `draft` → `created` → `shipped` → `delivered`
- Also: `warning`, `cancelled`, `failed`

**Computed properties:**
```python
@property
def is_refill(self):
    return self.fill_count > 1  # fill_count is a field here (IntegerField, not computed)

@property
def can_cancel(self):
    return (
        self.status == self.PRESCRIPTION_FILL_STATUS_CREATED
        and self.sent_to_pharmacy_at is not None
    )

@property
def shipping_tracking_url(self):
    from shipping.utils import get_provider_tracking_url
    return get_provider_tracking_url(self.shipping_tracking_number)

@property
def full_address_string(self):  # assembles stored address fields
    ...
```

Note: `fill_count` on `PrescriptionFill` is a stored **IntegerField** (line 779, `default=1`), tracking which fill number this is (1st fill, 2nd refill, etc.). This is distinct from `fill_count` on `Prescription` (which is a computed @property).

---

### Prescription Model (`care.Prescription`)

**Direct FK to primary Consult:**
```python
# backend/care/models.py lines 491-493
consult = models.ForeignKey(
    "consults.Consult", null=False, blank=False, on_delete=models.CASCADE
)
```

**M2M to Consult (audit trail):**
```python
# backend/care/models.py lines 494-496
consults = models.ManyToManyField(
    "consults.Consult", through="PrescriptionConsults", related_name="consult_prescription_set"
)
```

**Other FKs:**
```python
user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE)
product = models.ForeignKey("care.Product", null=True, blank=True, on_delete=models.CASCADE)
tests = models.ManyToManyField("test_results.Test", blank=True, through="PrescriptionTest")
```

**Key computed properties bridging back to PrescriptionFill:**
```python
# backend/care/models.py lines 604-629
@property
def fill_count(self) -> int:
    """Total number of fills used for this prescription (rounds up to nearest integer)."""
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
    # 0 if expired
    # otherwise: num_allowed_refills - fill_count + 1
    # capped by product.max_allowed_refills if set
    ...

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

`fill_count` on `Prescription` is the computed bridge back through the through table to count active PrescriptionFills.

---

### Through Tables

#### PrescriptionFillOrder (junction: PrescriptionFill ↔ Order)
```python
# backend/care/models.py lines 831-845
class PrescriptionFillOrder(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    """For a given consult, stores the orders that were placed."""
    prescription_fill = models.ForeignKey(PrescriptionFill, null=False, blank=False, on_delete=models.CASCADE)
    order = models.ForeignKey("ecomm.Order", null=False, blank=False, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("prescription_fill", "order")
```
This is the **explicit many-to-many junction** between PrescriptionFill and Order. A single PrescriptionFill can be associated with multiple Orders (e.g., refill + replacement orders), and the `unique_together` constraint prevents duplicate pairings.

#### PrescriptionFillPrescriptions (through: PrescriptionFill ↔ Prescription)
```python
# backend/care/models.py lines 864-892
class PrescriptionFillPrescriptions(models.Model):
    class Meta:
        db_table = "care_prescriptionfill_prescriptions"
        indexes = [models.Index(fields=["prescriptionfill"], name="care_pfp_prescriptionfill_idx")]

    prescriptionfill = models.ForeignKey(PrescriptionFill, null=False, blank=False, on_delete=models.CASCADE)
    prescription = models.ForeignKey(Prescription, null=False, blank=False, on_delete=models.CASCADE)
    fill_quantity = models.IntegerField(null=True, blank=True)
    precision_reference_id = models.CharField(max_length=100, blank=True)

    def get_effective_fill_quantity(self) -> int:
        """Falls back to prescription.product.quantity_value if fill_quantity is not set."""
        return self.fill_quantity or get_prescription_fill_quantity(self.prescription)

    def save(self, *args, **kwargs):
        if not self.fill_quantity:
            self.fill_quantity = self.prescription.quantity_value
        super().save(*args, **kwargs)
```
This through table adds `fill_quantity` (how much of the prescription was dispensed in this fill) and `precision_reference_id` (pharmacy fulfillment ID) on top of the M2M link.

#### PrescriptionConsults (through: Prescription ↔ Consult — audit trail)
```python
# backend/care/models.py lines 696-718
class PrescriptionConsults(TimestampMixin, models.Model):
    """Through table for audit trail of prescription changes across consults."""
    prescription = models.ForeignKey(Prescription, null=False, blank=False, on_delete=models.CASCADE)
    consult = models.ForeignKey("consults.Consult", null=False, blank=False, on_delete=models.CASCADE)
    updated_refill_count = models.IntegerField(null=True, blank=True)
    updated_expiration_date = models.DateField(null=True, blank=True)
    updated_date = models.DateTimeField(null=True, blank=True)
    class Meta:
        unique_together = ("prescription", "consult")
```

---

### Relationship Summary Diagram

```
Order (ecomm)
  │
  │ FK (nullable, SET_NULL)
  ▼
PrescriptionFill (care)
  │  ▲
  │  └─────── PrescriptionFillOrder (junction, unique_together)
  │                   │ FK (non-null, CASCADE)
  │                   └──── Order (ecomm)   [many Orders per Fill]
  │
  │ M2M via PrescriptionFillPrescriptions
  │   ├── prescriptionfill FK → PrescriptionFill
  │   ├── prescription FK → Prescription
  │   ├── fill_quantity (dispensed amount)
  │   └── precision_reference_id (pharmacy ref)
  ▼
Prescription (care)
  │  [computed property fill_count queries back through PrescriptionFillPrescriptions]
  │
  ├── consult FK → Consult (primary, non-null)
  ├── consults M2M → Consult (via PrescriptionConsults, audit trail)
  ├── user FK → User
  ├── product FK → care.Product
  └── tests M2M → test_results.Test (via PrescriptionTest)
```

---

### Key Design Notes

1. **Dual Order linkage on PrescriptionFill**: There are two ways PrescriptionFill links to Order:
   - `PrescriptionFill.order` (direct nullable FK, legacy, SET_NULL) — identifies the "primary" order
   - `PrescriptionFillOrder` junction table (non-null CASCADE FKs, many-to-many semantics) — supports multiple orders per fill (e.g., refill + replacement in same fill)
   Both are populated at order processing time in `process_shopify_order_for_treatment_refill()` (`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 2140-2143).

2. **fill_count naming collision**: There are two `fill_count` attributes with different semantics:
   - `PrescriptionFill.fill_count` — stored `IntegerField(default=1)`, tracks which sequential fill this is (1=initial, 2=first refill, etc.)
   - `Prescription.fill_count` — computed `@property`, queries `PrescriptionFillPrescriptions` to count total dispensed quantity divided by dose quantity

3. **PrescriptionFillPrescriptions is the linchpin**: `Prescription.fill_count`, `Prescription.refills_remaining`, and `Prescription.can_refill` all depend on this through table. The `create_prescription_fill_prescriptions()` utility function (`/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py` lines 821-843) is where Order line item quantities are resolved into fill quantities stored on this table.

4. **Order has no direct FK to Prescription**: To go from Order to Prescription, you traverse: `Order → PrescriptionFill (via PrescriptionFillOrder or direct FK) → Prescription (via PrescriptionFillPrescriptions)`.
