# C1 Exploration Log

## Search 1: clew search "ecomm URL patterns views"
Searched for ecomm URL patterns using clew. Key findings:
- `/Users/albertgwo/Work/evvy/backend/ecomm/admin.py` has a `get_urls()` method in `OrderAdmin`
- `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` is the main API url config
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/ecomm_products.py` has `EcommProductView`
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/pdp_configuration.py` has `by_ecomm_product` action

## Search 2: clew search "ecomm views URL path routing"
Confirmed the same files. Also surfaced `ShopAllRoutes.tsx` (frontend, not Django). Confirmed the main Django URL routing goes through `api/v1/urls.py`.

## Search 3: find /Users/albertgwo/Work/evvy/backend -name "urls.py"
Found all urls.py files in the backend (excluding venv):
- `/Users/albertgwo/Work/evvy/backend/app/urls.py` (root URL conf)
- `/Users/albertgwo/Work/evvy/backend/api/urls.py` (API router)
- `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py` (v1 API patterns)
- `/Users/albertgwo/Work/evvy/backend/api/internal/urls.py` (internal admin API)
- `/Users/albertgwo/Work/evvy/backend/partner_api/urls.py` (partner API)
- `/Users/albertgwo/Work/evvy/backend/partner_api/distro/urls.py`
- `/Users/albertgwo/Work/evvy/backend/partner_api/cx_automation/urls.py`

## Search 4: Read /Users/albertgwo/Work/evvy/backend/api/v1/urls.py and /Users/albertgwo/Work/evvy/backend/app/urls.py
Full read of both files. Found:

**app/urls.py**: Root URL conf mounts `api/` → `api.urls`
**api/v1/urls.py**: Contains the router registrations and one-off paths.

Ecomm-related patterns found:
- Router: `cart` → `CartViewSet`
- Router: `products` → `ProductViewSet`
- Router: `pdp-configurations` → `PDPConfigurationViewSet`
- Router: `provider-test-orders` → `ProviderTestOrderViewSet`
- Path: `ecomm-products/<str:sku>/` → `EcommProductView`
- Path: `orders/`, `orders/attach`, `orders/process` → `OrdersView`
- Path: `male-partner-checkout/` → `MalePartnerCheckoutView`
- Path: `order-transfer-verification/` → `AccountOrderTransferVerification`
- Path: `order-transfer-verification-confirm/` → `AccountOrderTransferConfirmVerification`
- Path: `provider-test/(?P<slug>[^/]+)/` → `PublicProviderMagicLinkCheckout`
- Paths: Multiple `webhooks/shopify*` → shopify webhook views
- Paths: Multiple `subscription/` and `subscriptions/` → subscription views

## Search 5: clew search "ecomm checkout order payment views"
Confirmed `CartViewSet.checkout` action, `OrdersView.post` for processing, and `ProviderTestOrderViewSet.checkout_link` action.

## Search 6: clew search "ecomm admin views get_urls"
Read the full `ecomm/admin.py`. Found:
- `OrderAdmin.get_urls()` registers a custom admin URL: `transfer-order-to-user/` → `attach_order_to_user` view

## Search 7: Read /Users/albertgwo/Work/evvy/backend/api/v1/views/ecomm_products.py
Confirmed `EcommProductView` - GET by SKU, public endpoint, no auth required.

## Search 8: grep for ecomm in api/v1/views/ directory
Listed all view files referencing ecomm: ecomm_products.py, cart.py, subscription.py, my_plan.py, register.py, consult.py, orders.py, provider_test_orders.py, webhooks.py, account_order_transfer_verification.py, pdp_configuration.py, userconfig.py

## Search 9: Read /Users/albertgwo/Work/evvy/backend/api/v1/views/__init__.py
Confirmed the view exports; `ecomm_products` is directly imported and re-exported.

## Search 10: Read /Users/albertgwo/Work/evvy/backend/api/v1/views/pdp_configuration.py
Found `PDPConfigurationViewSet` with these router actions:
- `list` (GET `pdp-configurations/`)
- `retrieve` (GET `pdp-configurations/<id>/`)
- `by-care-product/<care_product_slug>` (GET)
- `by-ecomm-product/<ecomm_product_sku>` (GET) - explicitly ecomm-related
- `by-slug/<slug>` (GET)
- `featured` (GET)

## Search 11: Read /Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py (first 80 lines)
Confirmed `CartViewSet` with:
- `create` (POST `cart/`)
- `items` (POST/DELETE `cart/<id>/items/`)
- `items/delete` (POST `cart/<id>/items/delete`)
- `checkout` (POST `cart/<id>/checkout/`)

## Search 12: grep for @action in cart.py
Confirmed 3 action decorators:
- `items` at detail=True
- `items/delete` at detail=True
- `checkout` at detail=True

## Search 13: grep ecomm/cart/order/product in api/v1/urls.py
Confirmed exact line numbers and URL patterns referencing ecomm-related views.

## Search 14: grep for @action in provider_test_orders.py
Found provider-test-orders router actions:
- `magic-link` (GET, detail=False)
- anonymous action (POST, detail=False, line 149)
- anonymous action (POST, detail=False, line 302)
- `plan-items` (GET, detail=True)
- `checkout-link` (POST, detail=True) - ecomm-related
- `mark-downloaded` (POST, detail=True)

## Search 15: grep for class views in products.py and @action
`ProductViewSet` has one custom action: `all-products` (GET, detail=False)

## Search 16: grep for webhook function definitions in webhooks.py
Found all webhook function views including ecomm-critical ones:
- `shopify_webhook_view` (line 82)
- `shopify_webhook_graphql_view` (line 150)
- `shopify_fulfillment_webhook_view` (line 175)
- `recharge_webhook_view` (line 369) - Recharge is the subscription/ecomm platform

## Search 17: grep ecomm/checkout/order/subscription in api/v1/urls.py
Confirmed all subscription-related URL patterns and their views.

## Search 18: grep for class definitions in account_order_transfer_verification.py
Found `AccountOrderTransferVerification` and `AccountOrderTransferConfirmVerification`.

## Search 19: grep for MalePartnerCheckoutView
Found in `userconfig.py` at line 209.

## Search 20: grep for get_active_subscription_by_product_sku in subscription.py
Confirmed function exists at line 29.

---

## Final Answer

All Django URL patterns involving ecomm-related views are spread across two main files: the API v1 URL configuration and the ecomm Django admin. The full URL paths assume the hierarchy: root mounts `api/` → `api/urls.py` mounts `v1/` → `api/v1/urls.py`.

---

### File: `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`

The base prefix for all patterns below is `api/v1/` (from root → api → v1 includes).

#### Router-registered ViewSets (REST framework SimpleRouter generates CRUD URLs)

**1. Cart ViewSet**
- URL prefix: `cart/`
- View: `CartViewSet` (`/Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py`)
- Generated patterns:
  - `GET/POST api/v1/cart/` — list/create carts
  - `GET/PUT/PATCH/DELETE api/v1/cart/<pk>/` — retrieve/update/destroy a cart
  - `POST/DELETE api/v1/cart/<pk>/items/` — add/remove cart line items
  - `POST api/v1/cart/<pk>/items/delete` — remove specific cart item (explicit delete URL)
  - `POST api/v1/cart/<pk>/checkout/` — create a Shopify checkout URL for the cart

**2. Products ViewSet**
- URL prefix: `products/`
- View: `ProductViewSet` (`/Users/albertgwo/Work/evvy/backend/api/v1/views/products.py`)
- Generated patterns:
  - `GET api/v1/products/` — list products
  - `GET api/v1/products/<pk>/` — retrieve a product
  - `GET api/v1/products/all-products/` — custom action returning all products

**3. PDP Configurations ViewSet**
- URL prefix: `pdp-configurations/`
- View: `PDPConfigurationViewSet` (`/Users/albertgwo/Work/evvy/backend/api/v1/views/pdp_configuration.py`)
- Generated patterns:
  - `GET api/v1/pdp-configurations/` — list active PDP configurations (filterable by `slug`, `care_product_slug`, `ecomm_product_sku` query params)
  - `GET api/v1/pdp-configurations/<pk>/` — retrieve a specific PDP configuration
  - `GET api/v1/pdp-configurations/by-care-product/<care_product_slug>/` — get PDP config by care product slug
  - `GET api/v1/pdp-configurations/by-ecomm-product/<ecomm_product_sku>/` — get PDP config by ecomm product SKU
  - `GET api/v1/pdp-configurations/by-slug/<slug>/` — get PDP config by slug
  - `GET api/v1/pdp-configurations/featured/` — get featured PDP configurations

**4. Provider Test Orders ViewSet**
- URL prefix: `provider-test-orders/`
- View: `ProviderTestOrderViewSet` (`/Users/albertgwo/Work/evvy/backend/api/v1/views/provider_test_orders.py`)
- Ecomm-related generated pattern:
  - `POST api/v1/provider-test-orders/<pk>/checkout-link/` — return a provider-paid checkout URL for the given ProviderTestOrder

#### One-off path() patterns

**5. EcommProduct by SKU**
```python
path(r"ecomm-products/<str:sku>/", views.EcommProductView.as_view(), name="ecomm-products")
```
- Full URL: `api/v1/ecomm-products/<sku>/`
- View: `EcommProductView` (`/Users/albertgwo/Work/evvy/backend/api/v1/views/ecomm_products.py`)
- HTTP method: GET
- Description: Public endpoint (no auth required) to fetch an ecomm Product by SKU

**6. Orders (process/attach)**
```python
path(r"orders/", views.OrdersView.as_view(), name="orders")
path(r"orders/attach", views.OrdersView.as_view(), name="orders-detail")
path(r"orders/process", views.OrdersView.as_view(), name="orders-process")
```
- Full URLs: `api/v1/orders/`, `api/v1/orders/attach`, `api/v1/orders/process`
- View: `OrdersView` (`/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py`)
- Description: Handles ecomm order retrieval, order attachment to user, and synchronous order processing

**7. Order Transfer Verification**
```python
path(r"order-transfer-verification/", views.AccountOrderTransferVerification.as_view(), name="order-transfer-verification")
path(r"order-transfer-verification-confirm/", views.AccountOrderTransferConfirmVerification.as_view(), name="order-transfer-verification-confirm")
```
- Full URLs: `api/v1/order-transfer-verification/`, `api/v1/order-transfer-verification-confirm/`
- Views: `AccountOrderTransferVerification`, `AccountOrderTransferConfirmVerification` (`/Users/albertgwo/Work/evvy/backend/api/v1/views/account_order_transfer_verification.py`)
- Description: Handles account order transfer verification workflow

**8. Male Partner Checkout**
```python
path(r"male-partner-checkout/", views.MalePartnerCheckoutView.as_view(), name="male-partner-checkout")
```
- Full URL: `api/v1/male-partner-checkout/`
- View: `MalePartnerCheckoutView` (`/Users/albertgwo/Work/evvy/backend/api/v1/views/userconfig.py`, line 209)
- Description: Handles male partner treatment checkout flow

**9. Public Provider Magic Link Checkout**
```python
re_path(r"^provider-test/(?P<slug>[^/]+)/$", PublicProviderMagicLinkCheckout.as_view(), name="provider-magic-checkout")
```
- Full URL: `api/v1/provider-test/<slug>/`
- View: `PublicProviderMagicLinkCheckout` (`/Users/albertgwo/Work/evvy/backend/api/v1/views/views.py`, line 37)
- Description: Public magic link that exchanges a slug for a Shopify checkout URL

**10. Shopify Webhooks (ecomm order processing)**
```python
path(r"webhooks/shopify", views.shopify_webhook_view, name="shopify-webhook")
path(r"webhooks/shopify-graphql", views.shopify_webhook_graphql_view, name="shopify-webhook-graphql")
path(r"webhooks/shopify-fulfillment", views.shopify_fulfillment_webhook_view, name="shopify-fulfillment-webhook")
```
- Full URLs: `api/v1/webhooks/shopify`, `api/v1/webhooks/shopify-graphql`, `api/v1/webhooks/shopify-fulfillment`
- Views: `shopify_webhook_view` (line 82), `shopify_webhook_graphql_view` (line 150), `shopify_fulfillment_webhook_view` (line 175) — all in `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`
- Description: Receive Shopify order/fulfillment events and trigger ecomm order processing via `process_shopify_order`

**11. Recharge Webhooks (subscription ecomm)**
```python
path(r"webhooks/recharge", views.recharge_webhook_view, name="recharge-webhook")
```
- Full URL: `api/v1/webhooks/recharge`
- View: `recharge_webhook_view` (line 369, `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`)
- Description: Handles Recharge subscription platform webhook events

**12. Subscription Management**
```python
path(r"subscription/", views.get_subscription, name="subscription")
path(r"subscriptions/", views.get_subscriptions, name="subscriptions")
path(r"subscriptions/<str:subscription_id>/", views.get_subscription_by_id, name="subscription-by-id")
path(r"subscriptions/sku/<str:sku>/", views.get_active_subscription_by_product_sku, name="subscription-by-product-sku")
path(r"subscription/exists/", views.subscription_exists, name="subscription-exists")
path(r"subscription/next-charge/", views.update_next_subscription_charge, name="subscription-next-charge")
path(r"subscription/next-charge-with-discount/", views.update_next_subscription_charge_with_discount, name="subscription-next-charge-with-discount")
path(r"subscription/portal-link/", views.portal_link, name="subscription-portal-link")
path(r"subscription/swap/", views.swap_subscription, name="subscription-swap")
```
- All views in `/Users/albertgwo/Work/evvy/backend/api/v1/views/subscription.py`
- Full URLs: `api/v1/subscription/`, `api/v1/subscriptions/`, `api/v1/subscriptions/<subscription_id>/`, `api/v1/subscriptions/sku/<sku>/`, `api/v1/subscription/exists/`, `api/v1/subscription/next-charge/`, `api/v1/subscription/next-charge-with-discount/`, `api/v1/subscription/portal-link/`, `api/v1/subscription/swap/`
- Description: Subscription management for ecomm subscription products (via Recharge platform)

---

### File: `/Users/albertgwo/Work/evvy/backend/ecomm/admin.py`

**13. Admin custom URL: Transfer Order to User**
```python
# In OrderAdmin.get_urls():
path("transfer-order-to-user/", self.attach_order_to_user)
```
- Full URL: `admin/ecomm/order/transfer-order-to-user/`
- View: `OrderAdmin.attach_order_to_user` method
- Description: Django admin custom action to attach (transfer) a Shopify order number to a specified user account

---

### Summary Table

| URL Pattern | View | File | Notes |
|---|---|---|---|
| `api/v1/cart/` | `CartViewSet` | `api/v1/views/cart.py` | Router CRUD |
| `api/v1/cart/<pk>/items/` | `CartViewSet.items` | `api/v1/views/cart.py` | POST/DELETE |
| `api/v1/cart/<pk>/items/delete` | `CartViewSet.items_delete` | `api/v1/views/cart.py` | POST |
| `api/v1/cart/<pk>/checkout/` | `CartViewSet.checkout` | `api/v1/views/cart.py` | POST |
| `api/v1/products/` | `ProductViewSet` | `api/v1/views/products.py` | Router CRUD |
| `api/v1/products/all-products/` | `ProductViewSet.all_products` | `api/v1/views/products.py` | GET |
| `api/v1/pdp-configurations/` | `PDPConfigurationViewSet` | `api/v1/views/pdp_configuration.py` | Router list |
| `api/v1/pdp-configurations/<pk>/` | `PDPConfigurationViewSet` | `api/v1/views/pdp_configuration.py` | Router retrieve |
| `api/v1/pdp-configurations/by-ecomm-product/<ecomm_product_sku>/` | `PDPConfigurationViewSet.by_ecomm_product` | `api/v1/views/pdp_configuration.py` | GET |
| `api/v1/pdp-configurations/by-care-product/<care_product_slug>/` | `PDPConfigurationViewSet.by_care_product` | `api/v1/views/pdp_configuration.py` | GET |
| `api/v1/pdp-configurations/by-slug/<slug>/` | `PDPConfigurationViewSet.by_slug` | `api/v1/views/pdp_configuration.py` | GET |
| `api/v1/pdp-configurations/featured/` | `PDPConfigurationViewSet.featured` | `api/v1/views/pdp_configuration.py` | GET |
| `api/v1/provider-test-orders/<pk>/checkout-link/` | `ProviderTestOrderViewSet.checkout_link` | `api/v1/views/provider_test_orders.py` | POST |
| `api/v1/ecomm-products/<sku>/` | `EcommProductView` | `api/v1/views/ecomm_products.py` | GET, public |
| `api/v1/orders/` | `OrdersView` | `api/v1/views/orders.py` | GET |
| `api/v1/orders/attach` | `OrdersView` | `api/v1/views/orders.py` | POST |
| `api/v1/orders/process` | `OrdersView` | `api/v1/views/orders.py` | POST |
| `api/v1/order-transfer-verification/` | `AccountOrderTransferVerification` | `api/v1/views/account_order_transfer_verification.py` | POST |
| `api/v1/order-transfer-verification-confirm/` | `AccountOrderTransferConfirmVerification` | `api/v1/views/account_order_transfer_verification.py` | POST |
| `api/v1/male-partner-checkout/` | `MalePartnerCheckoutView` | `api/v1/views/userconfig.py` | POST |
| `api/v1/provider-test/<slug>/` | `PublicProviderMagicLinkCheckout` | `api/v1/views/views.py` | GET, public |
| `api/v1/webhooks/shopify` | `shopify_webhook_view` | `api/v1/views/webhooks.py` | POST |
| `api/v1/webhooks/shopify-graphql` | `shopify_webhook_graphql_view` | `api/v1/views/webhooks.py` | POST |
| `api/v1/webhooks/shopify-fulfillment` | `shopify_fulfillment_webhook_view` | `api/v1/views/webhooks.py` | POST |
| `api/v1/webhooks/recharge` | `recharge_webhook_view` | `api/v1/views/webhooks.py` | POST |
| `api/v1/subscription/` | `get_subscription` | `api/v1/views/subscription.py` | GET |
| `api/v1/subscriptions/` | `get_subscriptions` | `api/v1/views/subscription.py` | GET |
| `api/v1/subscriptions/<subscription_id>/` | `get_subscription_by_id` | `api/v1/views/subscription.py` | GET |
| `api/v1/subscriptions/sku/<sku>/` | `get_active_subscription_by_product_sku` | `api/v1/views/subscription.py` | GET |
| `api/v1/subscription/exists/` | `subscription_exists` | `api/v1/views/subscription.py` | GET |
| `api/v1/subscription/next-charge/` | `update_next_subscription_charge` | `api/v1/views/subscription.py` | POST |
| `api/v1/subscription/next-charge-with-discount/` | `update_next_subscription_charge_with_discount` | `api/v1/views/subscription.py` | POST |
| `api/v1/subscription/portal-link/` | `portal_link` | `api/v1/views/subscription.py` | GET |
| `api/v1/subscription/swap/` | `swap_subscription` | `api/v1/views/subscription.py` | POST |
| `admin/ecomm/order/transfer-order-to-user/` | `OrderAdmin.attach_order_to_user` | `ecomm/admin.py` | POST (admin) |
