# A2-clew Raw Transcript

**Agent ID:** aa578c0f329a74b1b
**Tool:** clew (Bash + Read)
**Test:** A2 — Adding a new checkout source type: what code needs to change
**Tool calls:** 38
**Tokens:** 63,526

## Final Answer

Here is a comprehensive list of every file and code location that references or depends on the checkout source concept. Adding a new checkout source type for a partner integration requires changes across the following layers:

---

## 1. Core Model: Enum Constants and Field Definition

**`/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (lines 139-175)**

This is the single source of truth for all checkout source values. You must add a new constant and add it to `CHECKOUT_SOURCE_CHOICES`:

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
CHECKOUT_SOURCE_CHOICES = (...)

checkout_source = models.CharField(max_length=50, choices=CHECKOUT_SOURCE_CHOICES, null=True, blank=True)
```

You will need to add e.g. `CHECKOUT_SOURCE_NEW_PARTNER = "new-partner"` and add it to `CHECKOUT_SOURCE_CHOICES`.

---

## 2. Django Database Migration (Required)

**`/Users/albertgwo/Work/evvy/backend/ecomm/migrations/`**

A new migration must be created (following the pattern of `0050_alter_order_checkout_source.py`) to update the `choices` list on the database field. The migration is a cosmetic change (choices aren't enforced at the DB level) but is required for consistency.

Previous migrations in this series: `0025`, `0035`, `0039`, `0041`, `0042`, `0050`.

---

## 3. Source Determination Logic

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 810-865)**

`_determine_checkout_source(source_name, app_id, cart_id)` maps Shopify app IDs to checkout sources. If the new partner has its own Shopify app ID, add a new branch here:

```python
def _determine_checkout_source(source_name, app_id, cart_id):
    ...
    if app_id == SHOPIFY_DISTRIBUTION_PARTNER_APP_ID:
        return Order.CHECKOUT_SOURCE_DISTRIBUTION_PARTNER
    ...
```

This function is also mirrored in the backfill script (see item 7 below).

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 593-611)**

The order processing flow at line 593 calls `_determine_checkout_source` and then applies any `checkout_source` custom attribute override from the Shopify order payload. If your partner sends a custom attribute, no additional changes are needed here, but you need to make sure the new value string is allowed.

**`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 2629-2668)** — `cart_requires_consult`

This function checks `checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY` to skip the consult requirement. Evaluate if the new partner source needs similar special-casing.

---

## 4. Shopify App ID Constants

**`/Users/albertgwo/Work/evvy/backend/ecomm/constants.py` (lines 323-332)**

If the partner has its own Shopify app ID, define it here alongside existing IDs:

```python
SHOPIFY_RECHARGE_APP_ID = 294517
SHOPIFY_EVVY_API_APP_ID = 6687809
SHOPIFY_MARKETING_SITE_APP_IDS = [12875497473, 88312, 580111]
SHOPIFY_DISTRIBUTION_PARTNER_APP_ID = 2417604
# Add new partner app ID here
SHOPIFY_NEW_PARTNER_APP_ID = <id>
```

---

## 5. API Views That Set or Route on checkout_source

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py` (lines 132-170)**

Reads `checkout_source` from the request body and passes it as a Shopify custom attribute on the cart. No enum changes needed here, but the value must be a valid `CHECKOUT_SOURCE_*` constant string.

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/consult.py` (lines 409, 502-534)**

- Line 409: Hardcodes `CHECKOUT_SOURCE_INTERNAL_SITE` for a specific flow.
- Lines 502-534: Reads `checkout_source` from request data, switches on `"vaginitis-intake"` and `"ungated-rx-intake"` to select Shopify variant IDs. If the new partner needs a different variant, add a branch here.

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py` (lines 128-130)**

Checks if `order.checkout_source` is in a list of care intake sources to gate certain order operations. May need to include the new partner source if it behaves like a care intake.

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/user_tests.py` (lines 817, 885)**

Hardcodes `CHECKOUT_SOURCE_HEALTH_HISTORY` and `CHECKOUT_SOURCE_RETEST_UPSELL` for specific user test flows. No change needed unless the partner flow originates from user tests.

**`/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py` (line 199)**

Hardcodes `CHECKOUT_SOURCE_PROVIDER` for provider-initiated orders.

**`/Users/albertgwo/Work/evvy/backend/api/v1/utils/male_partner.py` (line 99)**

Hardcodes `CHECKOUT_SOURCE_MALE_PARTNER` as a Shopify custom attribute for male partner flows.

---

## 6. Serializers

**`/Users/albertgwo/Work/evvy/backend/api/v1/serializers/order.py` (line 65)**

Includes `"checkout_source"` in the serializer `fields` list, so it is exposed in the order API response. No change needed.

**`/Users/albertgwo/Work/evvy/backend/api/v1/serializers/consult.py` (lines 417, 491-530)**

Exposes `is_checkout_source_health_context` computed field: checks if the associated order's `checkout_source == CHECKOUT_SOURCE_HEALTH_HISTORY`. No change needed unless the partner introduces a similar concept.

---

## 7. Shopify Integration

**`/Users/albertgwo/Work/evvy/backend/ecomm/shopify/shopify.py` (lines 100-102)**

Default-sets `checkout_source` to `CHECKOUT_SOURCE_INTERNAL_SITE` if not already present in custom attributes before cart creation:

```python
if "checkout_source" not in custom_attributes:
    custom_attributes.append({"key": "checkout_source", "value": Order.CHECKOUT_SOURCE_INTERNAL_SITE})
```

**`/Users/albertgwo/Work/evvy/backend/ecomm/services/cart.py` (lines 422-424, 597-599)**

- Line 422-424: Reads `checkout_source` from cart custom attributes to check if a consult is required.
- Lines 597-599: Sets `checkout_source = CHECKOUT_SOURCE_INTERNAL_SITE` as default if missing from custom attributes.

**`/Users/albertgwo/Work/evvy/backend/ecomm/services/viome.py` (line 189)**

Sets `checkout_source = CHECKOUT_SOURCE_VIOME` as a Shopify custom attribute for Viome webhook-initiated orders. Your new partner integration will likely need a similar pattern here or in a new service file.

---

## 8. Celery Tasks

**`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` (line 409)**

Checks `order.checkout_source == Order.CHECKOUT_SOURCE_HEALTH_HISTORY` to conditionally execute post-order logic. Evaluate if the new partner source needs to trigger similar task behavior.

---

## 9. Monitoring and Metrics

**`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/events.py` (lines 69, 121-128)**

Includes `checkout_source` in order event payloads sent to monitoring. No change needed — it forwards the value automatically.

**`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/metrics.py` (lines 61-62, 76-90)**

Records CloudWatch metrics keyed by `checkout_source` string: `OrderValue/Source/{checkout_source}` and `Conversions/Source/{checkout_source}`. The new source will automatically create new metric dimensions.

**`/Users/albertgwo/Work/evvy/backend/ecomm/monitoring/utils.py` (lines 46, 100)**

Passes `checkout_source` through to monitoring utilities. No change needed.

---

## 10. Admin

**`/Users/albertgwo/Work/evvy/backend/ecomm/admin.py` (line 227)**

Uses `checkout_source` as a list filter on cross-sell orders: `list_filter = ("cross_sell_order__checkout_source",)`. The new value will appear automatically in the filter dropdown once orders exist.

**`/Users/albertgwo/Work/evvy/backend/providers/admin.py` (lines 19, 34-39)**

`provider_checkout_source` is a read-only field displayed on provider test admin pages. No change needed.

---

## 11. Backfill Scripts

**`/Users/albertgwo/Work/evvy/backend/scripts/backfill_order_checkout_sources.py` (lines 68-117, 163-173)**

Contains a mirror of `_determine_checkout_source` for use on existing orders. If the new source can be determined from app ID (i.e., it's app ID-based rather than custom attribute-based), update `_determine_checkout_source_from_payload` here too.

The `APPLICATION_SPECIFIC_SOURCES` list (lines 165-173) contains sources that are set via custom attributes and should be preserved during backfill. If the new partner source is set via a custom attribute, add it to this list:

```python
APPLICATION_SPECIFIC_SOURCES = [
    Order.CHECKOUT_SOURCE_VAGINITIS_INTAKE,
    ...
    Order.CHECKOUT_SOURCE_RETEST_UPSELL,
    # Order.CHECKOUT_SOURCE_NEW_PARTNER,  # add here if set via custom attribute
]
```

**`/Users/albertgwo/Work/evvy/backend/scripts/backfill_subscription_refill_order_attributes.py` (line 111)**

Also backfills `checkout_source` for subscription refill orders. No structural change needed.

---

## 12. Frontend Types and Routing

**`/Users/albertgwo/Work/evvy/frontend/src/types/orders.ts` (lines 27-31)**

TypeScript union type for `checkout_source`. Add the new string value:

```typescript
checkout_source?:
  | "vaginitis-upsell"
  | "ungated-rx-upsell"
  | "health-history"
  | "male-partner"
  | "new-partner";  // add here
```

**`/Users/albertgwo/Work/evvy/frontend/src/pages/loadingOrder.tsx` (lines 56-97)**

`getCareConsultRedirect` switches on `checkout_source` to route users to the correct post-checkout flow. If the new partner requires a distinct intake flow URL, add a `case` here:

```typescript
switch (checkout_source) {
  case "vaginitis-upsell": ...
  case "ungated-rx-upsell": ...
  case "health-history": ...
  case "male-partner": ...
  // case "new-partner": return `${basePath}/treatments/new-partner/intake/`;
  default: ...
}
```

**`/Users/albertgwo/Work/evvy/frontend/src/services/cart.ts` (lines 86, 98)**

Passes `checkout_source` in cart API request body. No change needed.

**`/Users/albertgwo/Work/evvy/frontend/src/hooks/useProcessOrder.ts` (line 8)**

Typed as `checkout_source?: string` — no change needed.

**`/Users/albertgwo/Work/evvy/frontend/src/components/care/consultIntake/upsells/SymptomsUpsell.tsx` (lines 50, 102)** and **`/Users/albertgwo/Work/evvy/frontend/src/pages/care/intake/ungatedRx/Consent.tsx` (line 80)**

Read `is_checkout_source_health_context` from the consult object. No change needed.

---

## Summary: Minimum Required Changes for a New Partner Source

| File | Change |
|------|--------|
| `backend/ecomm/models/order.py` | Add `CHECKOUT_SOURCE_NEW_PARTNER = "new-partner"` constant and entry in `CHECKOUT_SOURCE_CHOICES` |
| `backend/ecomm/migrations/` | Create new migration `AlterField` for `checkout_source` choices |
| `backend/ecomm/constants.py` | Add `SHOPIFY_NEW_PARTNER_APP_ID` if app-ID-based detection |
| `backend/ecomm/utils.py` | Add branch in `_determine_checkout_source` for app ID; evaluate `cart_requires_consult` |
| `backend/ecomm/services/` (or new file) | Set `checkout_source = Order.CHECKOUT_SOURCE_NEW_PARTNER` as Shopify custom attribute when creating the partner-initiated cart/order |
| `backend/scripts/backfill_order_checkout_sources.py` | Mirror the detection logic in `_determine_checkout_source_from_payload`; add to `APPLICATION_SPECIFIC_SOURCES` if custom-attribute-based |
| `frontend/src/types/orders.ts` | Add `"new-partner"` to the union type |
| `frontend/src/pages/loadingOrder.tsx` | Add `case "new-partner":` to route to the partner's intake flow |
