# C1 Exploration Log

## Search 1: Find all urls.py files and ecomm directory structure

Used Glob to find all `urls.py` files and all files under `ecomm*/**` pattern.

Key findings:
- Main application URL files (non-venv): `/Users/albertgwo/Work/evvy/backend/api/urls.py`, `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`, `/Users/albertgwo/Work/evvy/backend/api/internal/urls.py`, `/Users/albertgwo/Work/evvy/backend/app/urls.py`, `/Users/albertgwo/Work/evvy/backend/partner_api/urls.py`, `/Users/albertgwo/Work/evvy/backend/partner_api/cx_automation/urls.py`, `/Users/albertgwo/Work/evvy/backend/partner_api/distro/urls.py`
- The `ecomm` Django app lives at `/Users/albertgwo/Work/evvy/backend/ecomm/`
- No `urls.py` file exists inside the ecomm app itself — it does not define its own URL routes

## Search 2: Read the main API urls.py hierarchy

Read `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` — this is the primary router file.

Key findings:
- Line 87-90: `path(r"ecomm-products/<str:sku>/", views.EcommProductView.as_view(), name="ecomm-products")` — the only URL pattern with "ecomm" in its path
- Router registrations that involve ecomm models:
  - `router.register(r"cart", views.CartViewSet, basename="cart")` — CartViewSet uses ecomm models
  - `router.register(r"products", views.ProductViewSet, basename="products")` — ProductViewSet uses EcommProduct
  - `router.register(r"pdp-configurations", views.PDPConfigurationViewSet, basename="pdp-configurations")` — PDPConfigurationViewSet uses ecomm PDPConfiguration model
- One-off ecomm-related URL patterns:
  - `path(r"orders/", views.OrdersView.as_view(), name="orders")` — uses ecomm Order model
  - `path(r"orders/attach", views.OrdersView.as_view(), name="orders-detail")`
  - `path(r"orders/process", views.OrdersView.as_view(), name="orders-process")`
  - `path(r"order-transfer-verification/", views.AccountOrderTransferVerification.as_view(), name="order-transfer-verification")` — uses ecomm Order model
  - `path(r"order-transfer-verification-confirm/", views.AccountOrderTransferConfirmVerification.as_view(), name="order-transfer-verification-confirm")`
  - `path(r"webhooks/shopify", views.shopify_webhook_view, name="shopify-webhook")` — processes Shopify orders (ecomm)
  - `path(r"webhooks/shopify-graphql", views.shopify_webhook_graphql_view, name="shopify-webhook-graphql")`
  - `path(r"webhooks/shopify-fulfillment", views.shopify_fulfillment_webhook_view, name="shopify-fulfillment-webhook")`
  - `path(r"webhooks/recharge", views.recharge_webhook_view, name="recharge-webhook")` — subscription ecomm
  - `path(r"webhooks/viome", views.viome_webhook_view, name="viome-webhook")` — ViomeOrderService from ecomm
  - Subscription endpoints (ecomm-related): `subscription/`, `subscriptions/`, etc.

Read `/Users/albertgwo/Work/evvy/backend/api/internal/urls.py` — no ecomm references.

Read `/Users/albertgwo/Work/evvy/backend/app/urls.py` — top-level router, no ecomm references directly.

## Search 3: Grep for "ecomm" in urls.py files

Ran grep for the literal string "ecomm" in all `**/urls.py` files.

Result: Only 2 hits, both in `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`:
- Line 87: `r"ecomm-products/<str:sku>/"`
- Line 89: `name="ecomm-products"`

This confirms that only one URL *path string* contains "ecomm". The broader task requires identifying all URL patterns backed by views that use ecomm module code.

## Search 4: Grep for views files that import from ecomm

Ran grep for `from ecomm|import ecomm` in `backend/api/v1/views/*.py` with content and line numbers.

Key findings (files with ecomm imports):
- `cart.py` — imports `ecomm.constants`, `ecomm.models.cart.Cart`, `ecomm.monitoring`, `ecomm.services.cart`, `ecomm.utils`
- `orders.py` — imports `ecomm.models.order.Order`, `ecomm.services.cart`, `ecomm.shopify.tasks`
- `products.py` — imports `ecomm.constants`, `ecomm.models.product.Product`
- `ecomm_products.py` — imports `ecomm.models.product.Product`
- `pdp_configuration.py` — imports `ecomm.models.PDPConfiguration`
- `account_order_transfer_verification.py` — imports `ecomm.models.order.Order`, `ecomm.services.cart`, `ecomm.tasks`
- `webhooks.py` — imports `ecomm.monitoring`, `ecomm.services.viome.ViomeOrderService`, `ecomm.utils`
- `provider_test_orders.py` — imports `ecomm.constants`, `ecomm.models.order.Order`, `ecomm.shopify.shopify`
- `consult.py` — imports `ecomm.constants`, `ecomm.models.order.Order`, `ecomm.shopify.shopify`
- `register.py` — imports `ecomm.models.order.Order`, `ecomm.services.cart`, `ecomm.tasks`
- `subscription.py` — imports `ecomm.constants.RETEST_DISCOUNT_CODE`
- `userconfig.py` — imports `ecomm.models.order.PartnerRelationship`
- `user_tests.py` — imports `ecomm.constants`, `ecomm.models.order.Order`, `ecomm.models.product.Product`, `ecomm.shopify.shopify`, `ecomm.tasks`

## Search 5: Read the ecomm_products.py view

Read `/Users/albertgwo/Work/evvy/backend/api/v1/views/ecomm_products.py` in full.

Confirmed: `EcommProductView` is a `GET`-only `APIView` that retrieves an `EcommProduct` by SKU. Public endpoint (no auth required).

## Search 6: Read cart.py and orders.py views

Read first 60 lines of both. Both use ecomm models directly as their primary data source, confirming they are core ecomm views.

## Search 7: Read products.py view

Read in full. `ProductViewSet` uses `ecomm.models.product.Product` for the `all-products` action. The base list/retrieve actions use `care.models.Product` (care layer), but the `all-products` custom action explicitly fetches `EcommProduct` objects for multiple SKUs.

## Search 8: Read pdp_configuration.py view

Read in full. `PDPConfigurationViewSet` uses `ecomm.models.PDPConfiguration`. Has extra actions:
- `by-care-product/<care_product_slug>/`
- `by-ecomm-product/<ecomm_product_sku>/`
- `by-slug/<slug>/`
- `featured`

## Search 9: Read account_order_transfer_verification.py view

Read in full. Both `AccountOrderTransferVerification` and `AccountOrderTransferConfirmVerification` use ecomm `Order` model as primary entity.

## Search 10: Read api/urls.py (top-level api router)

Read `/Users/albertgwo/Work/evvy/backend/api/urls.py`. Confirmed URL prefix structure:
- `api/v1/` → `api.v1.urls`
- `api/internal/` → `api.internal.urls`
- `api/partner/` → `partner_api.urls`

## Search 11: Check partner_api for ecomm usage

Grep for `from ecomm|import ecomm` in `backend/partner_api/**/*.py`. Only test files and service files reference ecomm — none of the partner_api URL views directly use ecomm as their primary entity. The `cx_automation/services.py` imports `ecomm.models.order.Order` but for lookup purposes only.

## Search 12: Read partner_api URLs

Read `partner_api/urls.py`, `partner_api/cx_automation/urls.py`, and `partner_api/distro/urls.py`. None of these URL patterns are specifically ecomm views — they deal with test lookup, shipping status, consult info, etc.

---

## Final Answer

All Django URL patterns that involve ecomm-related views in `/Users/albertgwo/Work/evvy/backend/`.

The URL hierarchy is:
- `app/urls.py` → `api/` prefix → `api/urls.py`
- `api/urls.py` → `v1/` prefix → `api/v1/urls.py`

All ecomm-related URL patterns are registered in **`/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`**, with full base path `api/v1/`.

### 1. EcommProduct by SKU (explicit ecomm path)

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` (line 87-90)
**View file:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/ecomm_products.py`

```python
path(
    r"ecomm-products/<str:sku>/",
    views.EcommProductView.as_view(),
    name="ecomm-products",
)
```

- Full path: `api/v1/ecomm-products/<sku>/`
- View: `EcommProductView` (GET only, public — no auth required)
- Retrieves an `ecomm.models.product.Product` by SKU and returns it serialized via `EcommProductSerializer`

---

### 2. Cart ViewSet (router-generated routes)

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` (line 19)
**View file:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py`

```python
router.register(r"cart", views.CartViewSet, basename="cart")
```

Router generates:
- `api/v1/cart/` — GET (list), POST (create)
- `api/v1/cart/<pk>/` — GET (retrieve), PUT/PATCH (update), DELETE (destroy)
- `api/v1/cart/<pk>/items/` — POST/DELETE (custom `items` action)

View: `CartViewSet` — core ecomm view. Imports and uses:
- `ecomm.models.cart.Cart`
- `ecomm.constants.CONSULT_UID`, `PURCHASE_TYPE`
- `ecomm.monitoring.track_cart_creation`
- `ecomm.services.cart.CartService`
- `ecomm.utils.cart_requires_consult`

---

### 3. Orders (one-off paths)

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` (lines 76-78)
**View file:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py`

```python
path(r"orders/", views.OrdersView.as_view(), name="orders"),
path(r"orders/attach", views.OrdersView.as_view(), name="orders-detail"),
path(r"orders/process", views.OrdersView.as_view(), name="orders-process"),
```

- Full paths: `api/v1/orders/`, `api/v1/orders/attach`, `api/v1/orders/process`
- View: `OrdersView` — uses `ecomm.models.order.Order`, `ecomm.services.cart.attach_order_to_user`, `ecomm.shopify.tasks`

---

### 4. Order Transfer Verification

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` (lines 63-71)
**View file:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/account_order_transfer_verification.py`

```python
path(
    r"order-transfer-verification/",
    views.AccountOrderTransferVerification.as_view(),
    name="order-transfer-verification",
),
path(
    r"order-transfer-verification-confirm/",
    views.AccountOrderTransferConfirmVerification.as_view(),
    name="order-transfer-verification-confirm",
),
```

- Full paths: `api/v1/order-transfer-verification/`, `api/v1/order-transfer-verification-confirm/`
- Views: `AccountOrderTransferVerification` (GET/POST) and `AccountOrderTransferConfirmVerification` (POST)
- Both use `ecomm.models.order.Order` as the primary entity, along with `ecomm.services.cart` and `ecomm.tasks`

---

### 5. Products ViewSet (with ecomm all-products action)

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` (line 28)
**View file:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/products.py`

```python
router.register(r"products", views.ProductViewSet, basename="products")
```

Router generates:
- `api/v1/products/` — GET (list)
- `api/v1/products/<slug>/` — GET (retrieve)
- `api/v1/products/all-products/` — GET (custom action)

The `all-products` action fetches `ecomm.models.product.Product` objects for all test SKUs (VHT, expanded PCR, memberships, UTI, etc.) alongside care products.

---

### 6. PDP Configurations ViewSet (ecomm PDPConfiguration model)

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` (lines 39-43)
**View file:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/pdp_configuration.py`

```python
router.register(
    r"pdp-configurations",
    views.PDPConfigurationViewSet,
    basename="pdp-configurations",
)
```

Router + custom actions generate:
- `api/v1/pdp-configurations/` — GET (list)
- `api/v1/pdp-configurations/<pk>/` — GET (retrieve)
- `api/v1/pdp-configurations/by-care-product/<care_product_slug>/` — GET
- `api/v1/pdp-configurations/by-ecomm-product/<ecomm_product_sku>/` — GET
- `api/v1/pdp-configurations/by-slug/<slug>/` — GET
- `api/v1/pdp-configurations/featured/` — GET

View: `PDPConfigurationViewSet` — uses `ecomm.models.PDPConfiguration` as its primary queryset.

---

### 7. Shopify Webhook Routes

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` (lines 117-127)
**View file:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`

```python
path(r"webhooks/shopify", views.shopify_webhook_view, name="shopify-webhook"),
path(
    r"webhooks/shopify-graphql",
    views.shopify_webhook_graphql_view,
    name="shopify-webhook-graphql",
),
path(
    r"webhooks/shopify-fulfillment",
    views.shopify_fulfillment_webhook_view,
    name="shopify-fulfillment-webhook",
),
```

- Full paths: `api/v1/webhooks/shopify`, `api/v1/webhooks/shopify-graphql`, `api/v1/webhooks/shopify-fulfillment`
- Views: function-based webhook handlers that use `ecomm.utils.process_shopify_order`, `ecomm.monitoring`, and `ecomm.shopify.tasks`

---

### 8. Viome Webhook Route

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` (line 148)
**View file:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`

```python
path(r"webhooks/viome", views.viome_webhook_view, name="viome-webhook"),
```

- Full path: `api/v1/webhooks/viome`
- View: `viome_webhook_view` — uses `ecomm.services.viome.ViomeOrderService`

---

### 9. Recharge Webhook Route

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` (line 147)
**View file:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`

```python
path(r"webhooks/recharge", views.recharge_webhook_view, name="recharge-webhook"),
```

- Full path: `api/v1/webhooks/recharge`
- View: `recharge_webhook_view` — processes subscription/order webhooks; the webhooks.py file imports `ecomm.utils.process_shopify_subscription_webhook`

---

### 10. Subscription Routes (ecomm-adjacent)

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` (lines 151-175)
**View file:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/subscription.py`

```python
path(r"subscription/", views.get_subscription, name="subscription"),
path(r"subscriptions/", views.get_subscriptions, name="subscriptions"),
path(
    r"subscriptions/<str:subscription_id>/",
    views.get_subscription_by_id,
    name="subscription-by-id",
),
path(
    r"subscriptions/sku/<str:sku>/",
    views.get_active_subscription_by_product_sku,
    name="subscription-by-product-sku",
),
path(r"subscription/exists/", views.subscription_exists, name="subscription-exists"),
path(
    r"subscription/next-charge/",
    views.update_next_subscription_charge,
    name="subscription-next-charge",
),
path(
    r"subscription/next-charge-with-discount/",
    views.update_next_subscription_charge_with_discount,
    name="subscription-next-charge-with-discount",
),
path(r"subscription/portal-link/", views.portal_link, name="subscription-portal-link"),
path(r"subscription/swap/", views.swap_subscription, name="subscription-swap"),
```

- View file imports `ecomm.constants.RETEST_DISCOUNT_CODE` — ecomm-adjacent (subscription management uses ecomm discount codes)

---

### Summary Table

| URL Path (under `api/v1/`) | View | Ecomm Dependency |
|---|---|---|
| `ecomm-products/<sku>/` | `EcommProductView` | `ecomm.models.product.Product` (primary) |
| `cart/` | `CartViewSet` | `ecomm.models.cart.Cart` (primary) |
| `cart/<pk>/` | `CartViewSet` | `ecomm.models.cart.Cart` (primary) |
| `cart/<pk>/items/` | `CartViewSet.items` action | `ecomm.services.cart.CartService` |
| `orders/` | `OrdersView` | `ecomm.models.order.Order` (primary) |
| `orders/attach` | `OrdersView` | `ecomm.models.order.Order` (primary) |
| `orders/process` | `OrdersView` | `ecomm.models.order.Order` (primary) |
| `order-transfer-verification/` | `AccountOrderTransferVerification` | `ecomm.models.order.Order` (primary) |
| `order-transfer-verification-confirm/` | `AccountOrderTransferConfirmVerification` | `ecomm.models.order.Order` (primary) |
| `products/all-products/` | `ProductViewSet.all_products` action | `ecomm.models.product.Product` (fetched) |
| `pdp-configurations/` | `PDPConfigurationViewSet` | `ecomm.models.PDPConfiguration` (primary) |
| `pdp-configurations/<pk>/` | `PDPConfigurationViewSet` | `ecomm.models.PDPConfiguration` (primary) |
| `pdp-configurations/by-care-product/<slug>/` | `PDPConfigurationViewSet.by_care_product` | `ecomm.models.PDPConfiguration` (primary) |
| `pdp-configurations/by-ecomm-product/<sku>/` | `PDPConfigurationViewSet.by_ecomm_product` | `ecomm.models.PDPConfiguration` (primary) |
| `pdp-configurations/by-slug/<slug>/` | `PDPConfigurationViewSet.by_slug` | `ecomm.models.PDPConfiguration` (primary) |
| `pdp-configurations/featured/` | `PDPConfigurationViewSet.featured` | `ecomm.models.PDPConfiguration` (primary) |
| `webhooks/shopify` | `shopify_webhook_view` | `ecomm.utils.process_shopify_order` |
| `webhooks/shopify-graphql` | `shopify_webhook_graphql_view` | `ecomm.utils`, `ecomm.monitoring` |
| `webhooks/shopify-fulfillment` | `shopify_fulfillment_webhook_view` | `ecomm.monitoring`, `ecomm.shopify` |
| `webhooks/viome` | `viome_webhook_view` | `ecomm.services.viome.ViomeOrderService` |
| `webhooks/recharge` | `recharge_webhook_view` | `ecomm.utils.process_shopify_subscription_webhook` |
| `subscription/` | `get_subscription` | `ecomm.constants.RETEST_DISCOUNT_CODE` |
| `subscriptions/` | `get_subscriptions` | `ecomm.constants.RETEST_DISCOUNT_CODE` |
| `subscriptions/<subscription_id>/` | `get_subscription_by_id` | `ecomm.constants.RETEST_DISCOUNT_CODE` |
| `subscriptions/sku/<sku>/` | `get_active_subscription_by_product_sku` | `ecomm.constants.RETEST_DISCOUNT_CODE` |
| `subscription/exists/` | `subscription_exists` | `ecomm.constants.RETEST_DISCOUNT_CODE` |
| `subscription/next-charge/` | `update_next_subscription_charge` | `ecomm.constants.RETEST_DISCOUNT_CODE` |
| `subscription/next-charge-with-discount/` | `update_next_subscription_charge_with_discount` | `ecomm.constants.RETEST_DISCOUNT_CODE` |
| `subscription/portal-link/` | `portal_link` | `ecomm.constants.RETEST_DISCOUNT_CODE` |
| `subscription/swap/` | `swap_subscription` | `ecomm.constants.RETEST_DISCOUNT_CODE` |

**Note:** The `ecomm` Django app has no `urls.py` of its own — all its models and services are consumed by views in `api/v1/views/`. The sole URL path string containing the literal word "ecomm" is `ecomm-products/<str:sku>/`.
