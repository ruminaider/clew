# A2 — Checkout Source: Code Locations for Adding a New Partner Integration

## Summary

The `checkout_source` field on the `Order` model tracks where an order originated. It is populated from Shopify order custom attributes (passed at checkout creation time) and from app_id/cart_id heuristics (applied at order processing time). Adding a new partner integration checkout source requires changes in multiple layers.

---

## 1. Core Model: `CHECKOUT_SOURCE_*` Constants and Choices

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`
**Lines:** 139–175

This is the canonical definition. All checkout source string values and their human-readable labels live here as class-level constants and a `CHECKOUT_SOURCE_CHOICES` tuple.

```python
# Lines 139–154 (existing constants, pattern to follow)
CHECKOUT_SOURCE_VAGINITIS_INTAKE = "vaginitis-intake"
CHECKOUT_SOURCE_UNGATED_RX_INTAKE = "ungated-rx-intake"
CHECKOUT_SOURCE_HEALTH_HISTORY = "health-history"
CHECKOUT_SOURCE_MALE_PARTNER = "male-partner"
CHECKOUT_SOURCE_PROVIDER = "provider-portal"
CHECKOUT_SOURCE_PROVIDER_MAGIC_LINK = "provider-magic-link"
CHECKOUT_SOURCE_MARKETING_SITE = "marketing-site"
CHECKOUT_SOURCE_INTERNAL_SITE = "logged-in-cart"
CHECKOUT_SOURCE_VIOME = "viome-webhook"
CHECKOUT_SOURCE_SUBSCRIPTION = "subscription"
CHECKOUT_SOURCE_RETEST_UPSELL = "retest-upsell"
CHECKOUT_SOURCE_SOCIAL = "social"
CHECKOUT_SOURCE_POS = "pos"
CHECKOUT_SOURCE_OPS_CREATED = "ops_created"
CHECKOUT_SOURCE_DISTRIBUTION_PARTNER = "distribution_partner"
CHECKOUT_SOURCE_OTHER = "other"

CHECKOUT_SOURCE_CHOICES = (
    (CHECKOUT_SOURCE_VAGINITIS_INTAKE, "Vaginitis Intake"),
    ...
    (CHECKOUT_SOURCE_DISTRIBUTION_PARTNER, "Distribution Partner"),
    (CHECKOUT_SOURCE_OTHER, "Other"),
)

checkout_source = models.CharField(
    max_length=50, choices=CHECKOUT_SOURCE_CHOICES, null=True, blank=True
)
```

**What to change:** Add a new `CHECKOUT_SOURCE_<PARTNER> = "<partner-slug>"` constant and add it to `CHECKOUT_SOURCE_CHOICES`.

---

## 2. Database Migration

**Directory:** `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/`

Every time `CHECKOUT_SOURCE_CHOICES` changes, a new migration must be generated with `AlterField` on `order.checkout_source`. Prior migrations to reference:

- `0025_order_checkout_source.py` — initial field creation
- `0035_alter_order_checkout_source.py`
- `0039_alter_order_checkout_source.py`
- `0041_alter_order_checkout_source.py`
- `0042_alter_order_checkout_source.py`
- `0050_alter_order_checkout_source.py` — most recent, shows current full choices list

**What to do:** Run `python manage.py makemigrations ecomm` after updating the model.

---

## 3. Order Processing Logic: `_determine_checkout_source`

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
**Lines:** 810–865

This function determines checkout source from Shopify `app_id`, `cart_id`, and `source_name` fields. It mirrors the dbt-models `stg_ecomm_orders.sql` logic. If the partner has a dedicated Shopify app, a new branch must be added here.

```python
def _determine_checkout_source(
    source_name: str | None,
    app_id: int | None,
    cart_id: str | None,
) -> str | None:
    ...
    if app_id == SHOPIFY_DISTRIBUTION_PARTNER_APP_ID:
        return Order.CHECKOUT_SOURCE_DISTRIBUTION_PARTNER
    ...
```

**What to change:** If the partner integration has a dedicated Shopify app ID, add:
1. A new constant (e.g., `SHOPIFY_<PARTNER>_APP_ID`) in `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py` (line ~324 where existing app ID constants are defined).
2. A new `if app_id == SHOPIFY_<PARTNER>_APP_ID:` branch returning the new `CHECKOUT_SOURCE_<PARTNER>` constant.

The custom attribute override (lines 593–609) also applies: if the partner sends `checkout_source` as a Shopify order note attribute, it will override the heuristic value automatically.

---

## 4. Checkout URL Creation: Custom Attribute Injection

Checkout source is passed to Shopify as a custom attribute (`note_attribute`) at checkout creation time. The following call sites construct the `custom_attributes` dict that is eventually forwarded to Shopify:

### a. Cart checkout endpoint
**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py`
**Lines:** 132–170

```python
checkout_source = request.data.get("checkout_source")
...
if checkout_source:
    custom_attributes["checkout_source"] = checkout_source
```

The frontend can pass the new partner's checkout source value here.

### b. Consult checkout endpoint (vaginitis/consult flow)
**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py`
**Lines:** 406–409, 502–534

- Line 409: hardcodes `CHECKOUT_SOURCE_INTERNAL_SITE` for in-app consult checkout.
- Lines 502–534: `cross_sell_checkout_url` action passes `checkout_source` from request body. Contains source-specific branching for `"vaginitis-intake"` and `"ungated-rx-intake"` (lines 532–535). If the new partner source requires different variant_id selection, a new branch is needed here.

### c. Health history / ungated RX checkout
**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/user_tests.py`
**Lines:** 816–820

```python
custom_attributes = {
    "checkout_source": Order.CHECKOUT_SOURCE_HEALTH_HISTORY,
    ...
}
```

### d. Retest upsell checkout
**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/user_tests.py`
**Lines:** 884–887

```python
custom_attributes = {
    "checkout_source": Order.CHECKOUT_SOURCE_RETEST_UPSELL,
    ...
}
```

### e. Viome webhook integration
**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/services/viome.py`
**Line:** 189

```python
ShopifyCustomAttribute(key="checkout_source", value=Order.CHECKOUT_SOURCE_VIOME),
```

This is the direct template for a new webhook-based partner: add a similar service in `ecomm/services/` with a hardcoded `CHECKOUT_SOURCE_<PARTNER>` value.

---

## 5. Cart Service: Default Checkout Source

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/services/cart.py`
**Lines:** 422–424, 597–599

```python
# Line 422–424: reads checkout_source from custom_attributes for consult routing decision
checkout_source = custom_attributes.get("checkout_source")
consult_required = cart_requires_consult(self.cart, cart_purchase_type, checkout_source)

# Lines 597–599: default if not already provided
if "checkout_source" not in custom_attributes:
    custom_attributes["checkout_source"] = Order.CHECKOUT_SOURCE_INTERNAL_SITE
```

**What to check:** If the partner's checkout requires a consult or not, review `cart_requires_consult` below.

---

## 6. Consult Routing: `cart_requires_consult`

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`
**Lines:** 2629–2661

```python
def cart_requires_consult(
    cart: Cart, purchase_type: str, checkout_source: str | None = None
) -> bool:
    ...
    if checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY:
        # special bypass logic for ungated RX eligible treatments
        ...
```

**What to check:** If the new partner source bypasses the standard consult requirement, a new branch needs to be added here (similar to `CHECKOUT_SOURCE_HEALTH_HISTORY`).

---

## 7. Post-Order Processing: Business Logic Branches

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`

Downstream logic in `_process_shopify_order_impl` branches on `checkout_source`:

- **Line 1652–1654:** Sets provider magic link / provider source for orders with a `_provider_magic_value` attribute.
- **Line 1853:** Checks `checkout_source == Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE` to decide if an upsell order should update consult status.

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`
**Line:** 409

```python
if order.checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY:
```
Used during ungated RX consult creation to trace back to a parent test's health context.

**What to check:** Determine if the new partner source requires any special post-processing (e.g., consult creation, linking to an external entity, intake pre-population).

---

## 8. Serializers: API Exposure

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/serializers/order.py`
**Line:** 65

`checkout_source` is included in the `OrderSerializer` `fields` tuple — the field is already exposed in the order API response. No change needed unless the partner's source requires additional serializer logic.

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/serializers/consult.py`
**Lines:** 491–503, 417

```python
is_checkout_source_health_context = serializers.SerializerMethodField(...)

def get_is_checkout_source_health_context(self, obj):
    if consult_order.order.checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY:
        ...
```

If the partner source also represents a "health context" origin, this logic may need extending.

---

## 9. Monitoring and Analytics

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/metrics.py`
**Lines:** 61–62, 76–90

```python
if hasattr(order, "checkout_source") and order.checkout_source:
    record_order_metric(f"OrderValue/Source/{order.checkout_source}", order_value)

# and:
if checkout_source:
    record_order_metric(f"Conversions/Source/{checkout_source}", 1)
```

New source values appear automatically in New Relic metrics under `OrderValue/Source/<value>` — no code change needed, but the new source slug should be documented for dashboard setup.

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py`
**Lines:** 69, 121–128

`checkout_source` is included in New Relic custom events. No change needed.

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/utils.py`
**Lines:** 46, 100

`checkout_source` is passed to monitoring utils. No change needed.

---

## 10. Admin Display

**File:** `/Users/albertgwo/Work/evvy/backend/providers/admin.py`
**Lines:** 34–40

`provider_checkout_source` is a display method on `ProviderTestOrderAdmin` that reads `ecomm_order.checkout_source`. No code change needed — new values surface automatically.

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/admin.py`
**Line:** 227

```python
list_filter = ("cross_sell_order__checkout_source",)
```

The Django admin `RelatedOrderAdmin` filters by `checkout_source`. No code change needed — new values appear in the filter automatically.

---

## 11. Backfill Scripts (for historical orders)

If the partner was integrated historically (orders already exist without correct `checkout_source`), backfill scripts exist as templates:

- `/Users/albertgwo/Work/evvy/backend/scripts/backfill_order_checkout_sources.py` — general backfill using `_determine_checkout_source` logic; uses app_id from payload
- `/Users/albertgwo/Work/evvy/backend/scripts/backfill_subscription_refill_order_attributes.py` — template for attribute-based backfill

---

## 12. dbt Models (Data Warehouse)

Per the comment in `_determine_checkout_source` (line 818 of `ecomm/utils.py`):

> "This logic matches the dbt-models stg_ecomm_orders.sql logic for consistency across the data warehouse and application code."

The `stg_ecomm_orders.sql` model in the `dbt-models` repository must also be updated with a matching `CASE` branch if the new partner has a Shopify app ID that should be mapped.

---

## Summary: Minimal Change Set for a New Partner Checkout Source

| Priority | File | Change |
|----------|------|--------|
| Required | `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` | Add `CHECKOUT_SOURCE_<PARTNER>` constant and entry in `CHECKOUT_SOURCE_CHOICES` |
| Required | `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/` | Generate new migration via `makemigrations` |
| If partner has Shopify app | `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py` | Add `SHOPIFY_<PARTNER>_APP_ID` constant |
| If partner has Shopify app | `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (line ~860) | Add new branch in `_determine_checkout_source` |
| If webhook integration | `/Users/albertgwo/Work/evvy/backend/ecomm/services/` | Create new service (like `viome.py`) that injects `checkout_source` custom attribute |
| If consult bypass needed | `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (line ~2653) | Add branch in `cart_requires_consult` |
| If special post-processing | `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`, `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` | Add branch for partner-specific consult/entity logic |
| Required (data warehouse) | `dbt-models/stg_ecomm_orders.sql` | Add matching `CASE` branch |
