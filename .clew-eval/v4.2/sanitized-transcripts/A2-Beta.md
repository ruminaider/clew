# Checkout Source: Comprehensive Code Location Reference

## Summary

The `checkout_source` field on the `Order` model tracks where an order originated. There are currently **16 named source values** defined as class constants on `Order`. Adding a new partner integration checkout source requires changes across the following layers.

---

## 1. Core Model Definition

### `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (lines 139–175)

This is the authoritative definition. All source constants and the `CHECKOUT_SOURCE_CHOICES` tuple are defined here.

```python
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

**Required change:** Add a new `CHECKOUT_SOURCE_<PARTNER_NAME> = "<partner-slug>"` constant and add it to `CHECKOUT_SOURCE_CHOICES`.

---

## 2. Django Migration

A new migration is required whenever `CHECKOUT_SOURCE_CHOICES` changes.

### Relevant migration history:
- `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/0025_order_checkout_source.py` — initial field (3 choices)
- `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/0035_alter_order_checkout_source.py`
- `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/0036_orderlineitem_gift_card_code_and_more.py`
- `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/0039_alter_order_checkout_source.py`
- `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/0040_orderlineitem_care_product_and_more.py`
- `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/0041_alter_order_checkout_source.py`
- `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/0042_alter_order_checkout_source.py`
- `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/0043_alter_partnerrelationship_checkout_url.py`
- `/Users/albertgwo/Work/evvy/backend/ecomm/migrations/0050_alter_order_checkout_source.py` — most recent; shows all 16 choices

**Required change:** Generate a new migration (`python manage.py makemigrations ecomm`) after updating the model choices.

---

## 3. Order Source Determination Logic

### `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`

**`_determine_checkout_source()` function (lines 810–865):** Determines checkout source from Shopify `app_id`, `cart_id`, and `source_name`. Maps known Shopify App IDs to source constants. If the new partner sends orders via a dedicated Shopify App ID, add a branch here.

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

**`process_shopify_order` / order processing (lines 283–613):** Reads `checkout_source` from Shopify `note_attributes` (custom attributes). If set and not a subscription refill, it overrides the `_determine_checkout_source()` result:

```python
elif attribute_name == "checkout_source":
    if attribute_value:
        checkout_source = attribute_value
...
if checkout_source and not is_recurring_subscription_order:
    determined_checkout_source = checkout_source
```

**`cart_requires_consult()` function (lines 2629–2653+):** Contains conditional logic on `checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY`. If the new partner needs special consult-requirement logic, add a branch here.

---

## 4. Shopify App ID Constants

### `/Users/albertgwo/Work/evvy/backend/ecomm/constants.py` (lines 323–332)

All Shopify App IDs used in source determination:

```python
SHOPIFY_RECHARGE_APP_ID = 294517
SHOPIFY_EVVY_API_APP_ID = 6687809
SHOPIFY_MARKETING_SITE_APP_IDS = [12875497473, 88312, 580111]
SHOPIFY_SHOP_PAY_APP_ID = 3890849
SHOPIFY_SOCIAL_APP_IDS = [2775569, 4383523, 2329312]
SHOPIFY_POS_APP_ID = 129785
SHOPIFY_OPS_CREATED_APP_IDS = [1354745, 1251622]
SHOPIFY_DISTRIBUTION_PARTNER_APP_ID = 2417604
SHOPIFY_TESTING_ORDERS_APP_ID = 262131515393
```

**Required change (if partner uses a dedicated App ID):** Add a new `SHOPIFY_<PARTNER>_APP_ID` constant here.

---

## 5. Partner-Specific Service / Webhook Integration

### `/Users/albertgwo/Work/evvy/backend/ecomm/services/viome.py` (line 189)

Example of how a partner integration sets `checkout_source` as a Shopify custom attribute when creating orders:

```python
custom_attributes = [
    ShopifyCustomAttribute(key="checkout_source", value=Order.CHECKOUT_SOURCE_VIOME),
    ...
]
```

**Required change:** Create a similar service file (e.g., `ecomm/services/<partner>.py`) that passes `checkout_source=Order.CHECKOUT_SOURCE_<PARTNER>` when creating Shopify orders.

---

## 6. Shopify API Client (Checkout Fallback)

### `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/shopify.py` (lines 96–103)

Falls back to `CHECKOUT_SOURCE_INTERNAL_SITE` if no `checkout_source` key is present in custom attributes:

```python
if "checkout_source" not in custom_attributes:
    custom_attributes_list.append(
        {"key": "checkout_source", "value": Order.CHECKOUT_SOURCE_INTERNAL_SITE}
    )
```

No change required here unless the fallback behavior needs to differ for the partner.

---

## 7. Cart Service

### `/Users/albertgwo/Work/evvy/backend/ecomm/services/cart.py` (lines 417–599)

`create_checkout()` accepts `custom_attributes` dict including `checkout_source`, and falls back to `CHECKOUT_SOURCE_INTERNAL_SITE` if not supplied:

```python
checkout_source = custom_attributes.get("checkout_source")
consult_required = cart_requires_consult(self.cart, cart_purchase_type, checkout_source)
...
if "checkout_source" not in custom_attributes:
    custom_attributes["checkout_source"] = Order.CHECKOUT_SOURCE_INTERNAL_SITE
```

No direct change required unless the partner uses cart-based checkout.

---

## 8. API Views That Set checkout_source as Custom Attribute

These views hardcode a `checkout_source` value when creating checkout URLs:

| File | Line(s) | Source value set |
|------|---------|-----------------|
| `/Users/albertgwo/Work/evvy/backend/api/v1/views/user_tests.py` | 817, 885 | `CHECKOUT_SOURCE_HEALTH_HISTORY`, `CHECKOUT_SOURCE_RETEST_UPSELL` |
| `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py` | 409, 523 | `CHECKOUT_SOURCE_INTERNAL_SITE`, passes through `checkout_source` from request |
| `/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py` | 199 | `CHECKOUT_SOURCE_PROVIDER` |
| `/Users/albertgwo/Work/evvy/backend/api/v1/utils/male_partner.py` | 99 | `CHECKOUT_SOURCE_MALE_PARTNER` |
| `/Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py` | 132–170 | Passes `checkout_source` through from request body |

**Required change:** If the new partner flow originates from a new API endpoint, add a new view that sets `checkout_source=Order.CHECKOUT_SOURCE_<PARTNER>` in its custom attributes.

---

## 9. Order Processing Downstream Logic

### `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (line 409)

Routes post-order processing based on `checkout_source`:

```python
if order.checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY:
    related_order = RelatedOrder.objects.filter(cross_sell_order=order).first()
    ...
```

**Required change (if partner needs custom post-order behavior):** Add a conditional branch here for the new partner's source.

### `/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py` (lines 128–131)

Routes post-checkout redirect based on `checkout_source`:

```python
if order.checkout_source in [
    Order.CHECKOUT_SOURCE_UNGATED_RX_INTAKE,
    Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE,
]:
    ...
```

**Required change (if partner has a custom post-checkout redirect flow):** Add the new source to this check.

### `/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py` (lines 516, 532–534)

Uses `checkout_source` to determine purchase type and variant selection during cross-sell checkout:

```python
purchase_type = (
    Consult.PURCHASE_TYPE_A_LA_CARTE
    if checkout_source == Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE
    else "consult-add-on"
)
...
if checkout_source == "vaginitis-intake" and product.ecomm_product.variant_id:
    ...
elif checkout_source == "ungated-rx-intake" and product.ungated_rx_variant.variant_id:
    ...
```

---

## 10. Serializers

### `/Users/albertgwo/Work/evvy/backend/api/v1/serializers/order.py` (line 65)

`checkout_source` is included in the `OrderSerializer` fields — no change needed.

### `/Users/albertgwo/Work/evvy/backend/api/v1/serializers/consult.py` (lines 491–506)

`is_checkout_source_health_context` computed field checks if any linked order has `checkout_source == CHECKOUT_SOURCE_HEALTH_HISTORY`. No change needed unless partner has similar consult logic.

---

## 11. Monitoring and Analytics

### `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py` (lines 69, 121–130)

`checkout_source` is automatically included in all NewRelic order events via `getattr(order, "checkout_source", None)`. No change required.

### `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/metrics.py` (lines 61–62, 76–90)

Records per-source metrics automatically:
```python
if hasattr(order, "checkout_source") and order.checkout_source:
    record_order_metric(f"OrderValue/Source/{order.checkout_source}", order_value)
```
No change required — new source values flow through automatically.

### `/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/utils.py` (lines 46, 100)

Same pattern — passes `checkout_source` through to metrics. No change required.

---

## 12. Admin

### `/Users/albertgwo/Work/evvy/backend/ecomm/admin.py` (line 227)

`RelatedOrderAdmin` uses `checkout_source` as a list filter:
```python
list_filter = ("cross_sell_order__checkout_source",)
```
No change required — new choices automatically appear in the filter dropdown once the model is updated.

### `/Users/albertgwo/Work/evvy/backend/providers/admin.py` (lines 34–40)

`provider_checkout_source` readonly field on `ProviderTestOrderAdmin` reads `ecomm_order.checkout_source`. No change required.

---

## 13. Backfill Scripts

### `/Users/albertgwo/Work/evvy/backend/scripts/backfill_order_checkout_sources.py`

Contains `APPLICATION_SPECIFIC_SOURCES` list (lines 165–174) — sources set via custom attributes that should be preserved and not overridden by app_id logic:

```python
APPLICATION_SPECIFIC_SOURCES = [
    Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE,
    Order.CHECKOUT_SOURCE_UNGATED_RX_INTAKE,
    Order.CHECKOUT_SOURCE_HEALTH_HISTORY,
    Order.CHECKOUT_SOURCE_MALE_PARTNER,
    Order.CHECKOUT_SOURCE_PROVIDER,
    Order.CHECKOUT_SOURCE_PROVIDER_MAGIC_LINK,
    Order.CHECKOUT_SOURCE_VIOME,
    Order.CHECKOUT_SOURCE_RETEST_UPSELL,
]
```

Also contains `_determine_checkout_source_from_payload()` which mirrors the main utils logic.

**Required change:** Add the new partner source to `APPLICATION_SPECIFIC_SOURCES` if it is set via custom attributes (not app_id detection).

### `/Users/albertgwo/Work/evvy/backend/scripts/backfill_subscription_refill_order_attributes.py`

Tracks `checkout_source` distributions. No structural change required.

### `/Users/albertgwo/Work/evvy/backend/scripts/backfill_upsell_purchase_types.py`

Filters `RelatedOrder` by `cross_sell_order__checkout_source=Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE`. No change needed unless partner uses the same flow.

---

## 14. Frontend

### `/Users/albertgwo/Work/evvy/frontend/src/types/orders.ts` (lines 27–31)

TypeScript `Order` type includes `checkout_source` as a union type:
```typescript
checkout_source?:
  | "vaginitis-upsell"
  | "ungated-rx-upsell"
  | "health-history"
  | "male-partner";
```

**Required change:** Add the new partner's slug string to this union type if frontend code needs to branch on it.

### `/Users/albertgwo/Work/evvy/frontend/src/services/cart.ts` (lines 76–99)

`createCartCheckout()` accepts and forwards `checkoutSource` parameter to the backend. No change needed.

### `/Users/albertgwo/Work/evvy/frontend/src/pages/loadingOrder.tsx` (lines 58–64, 177)

Switches on `order.checkout_source` to determine redirect path after checkout:
```typescript
switch (checkout_source) {
  case "vaginitis-upsell":
    return `...rx/consults/${consultUid}/intake/treatment/shipping/`;
  ...
}
```

**Required change (if partner has a custom post-checkout redirect):** Add a new `case` for the partner slug.

### `/Users/albertgwo/Work/evvy/frontend/src/utils/analytics/customEventTracking.js`

Passes `checkoutSource` through to analytics events. No structural change needed — it flows through automatically.

### Other frontend files with minor usage:
- `/Users/albertgwo/Work/evvy/frontend/src/hooks/cart/usePanelCart.tsx` — passes `checkoutSource` to `createCartCheckout()`
- `/Users/albertgwo/Work/evvy/frontend/src/hooks/useOrderTracking.ts` — passes `checkoutSource` to NewRelic
- `/Users/albertgwo/Work/evvy/frontend/src/utils/newrelicHelpers.js` — logs `checkoutSource` as a page action attribute
- `/Users/albertgwo/Work/evvy/frontend/src/pages/care/intake/ungatedRx/Consent.tsx` — reads `is_checkout_source_health_context` from consult intake
- `/Users/albertgwo/Work/evvy/frontend/src/components/care/consultIntake/upsells/SymptomsUpsell.tsx` — uses `is_checkout_source_health_context`
- `/Users/albertgwo/Work/evvy/frontend/src/types/care.ts` (line 384) — `is_checkout_source_health_context?: boolean` on consult intake type

---

## Checklist: Adding a New Partner Checkout Source

1. **`/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py`** — Add `CHECKOUT_SOURCE_<PARTNER> = "<partner-slug>"` constant and entry in `CHECKOUT_SOURCE_CHOICES`
2. **New Django migration** — Run `python manage.py makemigrations ecomm` to generate an `AlterField` migration
3. **`/Users/albertgwo/Work/evvy/backend/ecomm/constants.py`** — Add `SHOPIFY_<PARTNER>_APP_ID` if the partner sends orders via a dedicated Shopify App ID
4. **`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (`_determine_checkout_source`)** — Add a branch mapping the partner's App ID to the new constant (if app_id-based)
5. **`/Users/albertgwo/Work/evvy/backend/ecomm/services/<partner>.py`** — Create a service/webhook handler that sets `checkout_source=Order.CHECKOUT_SOURCE_<PARTNER>` in Shopify custom attributes (if attribute-based, like Viome)
6. **`/Users/albertgwo/Work/evvy/backend/scripts/backfill_order_checkout_sources.py`** — Add to `APPLICATION_SPECIFIC_SOURCES` if set via custom attributes
7. **`/Users/albertgwo/Work/evvy/frontend/src/types/orders.ts`** — Add partner slug to `checkout_source` union type
8. **`/Users/albertgwo/Work/evvy/frontend/src/pages/loadingOrder.tsx`** — Add `case` for partner slug if it needs a custom post-checkout redirect
9. **New API view or endpoint** (if needed) — Add to `api/v1/views/` and set the appropriate `checkout_source` value
10. **`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`** and **`/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py`** — Add partner-specific post-order processing logic if required
