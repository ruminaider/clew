# B2 — Agent Alpha

## Relationship Map: Order, PrescriptionFill, and Prescription

All models live in `/Users/albertgwo/Work/evvy/backend/care/models.py` (care app) and `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (ecomm app).

---

### 1. `Order` (`ecomm/models/order.py`, line 11)

`Order` is the Shopify-sourced e-commerce record. It has **no direct ForeignKey or M2M to Prescription**. Its connections to the care domain run exclusively through `PrescriptionFill` and through-table `PrescriptionFillOrder`.

Reverse relations accessible on an `Order` instance (via Django's default accessor naming):
- `order.prescriptionfill_set` — all `PrescriptionFill` records where `PrescriptionFill.order = this` (the deprecated direct FK; see note below)
- `order.prescriptionfillorder_set` — all `PrescriptionFillOrder` join-table rows linking this order to fills
- `order.otc_treatments` (explicit `related_name`) — `OTCTreatment` objects belonging to this order

---

### 2. `PrescriptionFill` (`care/models.py`, line 721)

This is the central hub model representing one dispensing event (initial fill or refill).

**Foreign Keys on `PrescriptionFill`:**

| Field | Target | Null | on_delete | Notes |
|---|---|---|---|---|
| `user` | `User` | True | CASCADE | |
| `consult` | `consults.Consult` | True | CASCADE | nullable since 5/2/2025 |
| `order` | `ecomm.Order` | True | **SET_NULL** | **deprecated/legacy** — kept for backcompat; primary link now via `PrescriptionFillOrder` |

**Many-to-Many on `PrescriptionFill`:**

| Field | Target | Through table | Notes |
|---|---|---|---|
| `prescriptions` | `Prescription` | `PrescriptionFillPrescriptions` | One fill can contain multiple prescriptions |
| `otctreatments` | `OTCTreatment` | `PrescriptionFillOTCTreatments` | OTC (non-prescription) items in same fill |

**Computed properties on `PrescriptionFill`:**
- `shipping_tracking_url` — delegates to `shipping.utils.get_provider_tracking_url(self.shipping_tracking_number)`
- `is_refill` — `return self.fill_count > 1` (where `fill_count` is a plain integer field on PrescriptionFill, not computed)
- `full_address_string` — concatenates address fields stored on the fill
- `can_cancel` — `status == CREATED and sent_to_pharmacy_at is not None`

---

### 3. `Prescription` (`care/models.py`, line 481)

This represents the clinical act of prescribing a product to a user, tied to a consult.

**Foreign Keys on `Prescription`:**

| Field | Target | Null | on_delete |
|---|---|---|---|
| `consult` | `consults.Consult` | False | CASCADE |
| `user` | `User` | False | CASCADE |
| `product` | `care.Product` | True | CASCADE |

**Many-to-Many on `Prescription`:**

| Field | Target | Through table | Related name |
|---|---|---|---|
| `tests` | `test_results.Test` | `PrescriptionTest` | (default) |
| `consults` | `consults.Consult` | `PrescriptionConsults` | `consult_prescription_set` |

**Computed properties on `Prescription`:**

- `fill_count` — queries `PrescriptionFillPrescriptions` to count non-cancelled, non-draft fills for this prescription; sums `get_effective_fill_quantity()` and divides by `product.quantity_value` (ceiling). This is the bridge from `Prescription` back to `PrescriptionFill`:
  ```python
  # care/models.py, line 605-629
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
      ...
      return math.ceil(total_quantity / self.product.quantity_value)
  ```

- `refills_remaining` — `num_allowed_refills - fill_count + 1` (capped by `product.max_allowed_refills` if set; returns 0 if expired)

- `can_refill` — `refills_remaining > 0 and is_refillable_product and expiration_date > today and not product.is_disabled_for_refill and not product.is_deprecated`

- `is_refillable_product` — product type is not antibiotic or antifungal

- `is_otc_product` — product's `regulatory_category == OVER_THE_COUNTER`

---

### 4. Through Tables

#### `PrescriptionFillPrescriptions` (`care/models.py`, line 864)
The primary M2M join between `PrescriptionFill` and `Prescription`.

```python
# db_table = "care_prescriptionfill_prescriptions"
prescriptionfill = models.ForeignKey(PrescriptionFill, on_delete=CASCADE)
prescription     = models.ForeignKey(Prescription,     on_delete=CASCADE)
fill_quantity             = models.IntegerField(null=True)
precision_reference_id    = models.CharField(max_length=100, blank=True)
```

Extra computed method:
- `get_effective_fill_quantity()` — returns `fill_quantity` if set, else falls back to `shipping.precision.utils.get_prescription_fill_quantity(self.prescription)`

The `save()` method auto-populates `fill_quantity` from `prescription.quantity_value` if not provided.

#### `PrescriptionFillOrder` (`care/models.py`, line 831)
The **authoritative** link between `PrescriptionFill` and `Order` (the older direct FK on `PrescriptionFill.order` is now considered legacy).

```python
prescription_fill = models.ForeignKey(PrescriptionFill, on_delete=CASCADE)
order             = models.ForeignKey("ecomm.Order",    on_delete=CASCADE)
# unique_together = ("prescription_fill", "order")
```

This was introduced to support the case where a single prescription fill may span multiple orders (e.g., replacement fills). The `heal_prescription_fill_orders` Celery task (`care/tasks.py`, line 47) runs periodically to backfill any `PrescriptionFill` records that have `PrescriptionFill.order` set but no corresponding `PrescriptionFillOrder` row.

---

### 5. Relationship Diagram (Summary)

```
ecomm.Order
    │
    ├─── FK (legacy, SET_NULL) ───────────────────────────► PrescriptionFill
    │                                                              │
    └─── PrescriptionFillOrder (through table) ──────────────────►│
              prescription_fill FK                                  │
              order FK                                             │
              unique_together(prescription_fill, order)            │
                                                                   │
                                        PrescriptionFillPrescriptions (through table)
                                              prescriptionfill FK ─┘
                                              prescription FK
                                              fill_quantity
                                              precision_reference_id
                                                   │
                                                   ▼
                                             Prescription
                                                   │
                                                   ├── FK ──► consults.Consult
                                                   ├── FK ──► auth.User
                                                   └── FK ──► care.Product
```

---

### 6. Key Bridging Logic in `ecomm/utils.py`

The function at `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` line ~2095 is the canonical write path that ties all three together when a Shopify order is processed:

1. Finds or creates a `PrescriptionFill` (via `prescription_fill_id` from order note attributes, or `get_or_create(order=order)`)
2. Sets `prescription_fill.order = order` (legacy FK) and calls `PrescriptionFillOrder.objects.get_or_create(prescription_fill=..., order=...)` (new through table)
3. Resolves `Prescription` objects either from explicit `prescription_ids` in order attributes, or by filtering `Prescription.objects.filter(user=order.user, product__in=ordered_products, deleted=False)`
4. Calls `create_prescription_fill_prescriptions()` which populates `PrescriptionFillPrescriptions`
5. Triggers `send_prescription_refill_request.delay(order.id, prescription_fill.id)` to kick off pharmacy fulfillment
