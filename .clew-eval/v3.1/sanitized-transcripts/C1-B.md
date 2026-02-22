# Exploration Transcript: Tool B — C1

**Task:** Find all Django URL patterns that involve ecomm-related views. List each URL pattern with its view and URL path.

---

## Step 1: Initial broad searches

The agent began with two parallel searches for ecomm-related URL patterns and Django cart/orders/shopify patterns.

`search("ecommerce URL patterns views")`

Results (top hits):
```json
[
  {
    "file_path": "backend/ecomm/admin.py",
    "start_line": 114,
    "name": "get_urls",
    "preview": "def get_urls(self)"
  },
  {
    "file_path": "backend/partner_api/distro/urls.py",
    "preview": "URL configuration for Partner API distro endpoints.\n\nfrom django.urls import path, register_converter"
  },
  {
    "file_path": "backend/api/v1/urls.py",
    "preview": "from django.urls import path, re_path\nfrom rest_framework import routers\n..."
  },
  {
    "file_path": "backend/api/v1/views/consult.py",
    "name": "checkout_url",
    "preview": "def checkout_url(self, request, uid=None)"
  },
  {
    "file_path": "backend/api/v1/views/pdp_configuration.py",
    "name": "by_ecomm_product",
    "preview": "def by_ecomm_product(self, request, ecomm_product_sku=None)\nGet PDP configuration by ecomm product SKU"
  }
]
```

`search("Django URL patterns cart orders shopify")`

Results (top hits):
```json
[
  {
    "file_path": "backend/ecomm/admin.py",
    "name": "get_urls",
    "preview": "def get_urls(self)"
  },
  {
    "file_path": "backend/ecomm/services/cart.py",
    "name": "CartService",
    "preview": "title = item.ecomm_product.name..."
  },
  {
    "file_path": "backend/ecomm/services/cart.py",
    "name": "create_checkout",
    "preview": "def create_checkout(self, custom_attributes=None, local_pharmacy_pickup=False) -> str"
  },
  {
    "file_path": "backend/ecomm/shopify/shopify.py",
    "name": "get_checkout_url",
    "preview": "def get_checkout_url(\nGeneric checkout url generator for product variant ID's"
  }
]
```

---

## Step 2: Discover all URL configuration files

`find_files("**/ecomm/**/urls.py")` — No files found.

`find_files("**/urls.py")` in `backend/`

Results:
```
backend/api/internal/urls.py
backend/api/urls.py
backend/api/v1/urls.py
backend/partner_api/cx_automation/urls.py
backend/partner_api/distro/urls.py
backend/partner_api/urls.py
backend/app/urls.py
```
(plus venv packages, excluded from analysis)

---

## Step 3: Read root URL config

`read("backend/app/urls.py")`

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path(r"health/", views.health, name="health"),
    path(r"unhealthy/", views.unhealthy, name="unhealthy"),
    path(r"api/", include("api.urls"), name="api"),
]
```

---

## Step 4: Read the main API v1 URL configuration

`read("backend/api/v1/urls.py")`

```python
# Router-registered viewsets:
router.register(r"user-tests", views.UserTestViewSet, basename="user-tests")
router.register(r"health-context", views.HealthContextViewSet, basename="health-context")
router.register(r"tasks", views.TasksViewSet, basename="tasks")
router.register(r"cart", views.CartViewSet, basename="cart")
router.register(r"consults", views.ConsultViewSet, basename="consults")
router.register(r"consult-intake", views.ConsultIntakeViewSet, basename="consult-intake")
router.register(r"lab-order-intake", views.LabOrderIntakeViewSet, basename="lab-order-intake")
router.register(r"treatment-interruption", views.TreatmentPlanInterruptionViewSet, ...)
router.register(r"products", views.ProductViewSet, basename="products")
router.register(r"provider-test-orders", views.ProviderTestOrderViewSet, ...)
router.register(r"calendar-treatments", views.CalendarTreatmentViewSet, ...)
router.register(r"pdp-configurations", views.PDPConfigurationViewSet, ...)

# One-off paths:
path(r"orders/", views.OrdersView.as_view(), name="orders"),
path(r"orders/attach", views.OrdersView.as_view(), name="orders-detail"),
path(r"orders/process", views.OrdersView.as_view(), name="orders-process"),
path(r"male-partner-checkout/", views.MalePartnerCheckoutView.as_view(), name="male-partner-checkout"),
path(r"ecomm-products/<str:sku>/", views.EcommProductView.as_view(), name="ecomm-products"),
re_path(r"^provider-test/(?P<slug>[^/]+)/$", PublicProviderMagicLinkCheckout.as_view(), name="provider-magic-checkout"),
path(r"webhook/", views.webhook_view, name="webhook"),
path(r"webhooks/shopify", views.shopify_webhook_view, name="shopify-webhook"),
path(r"webhooks/shopify-graphql", views.shopify_webhook_graphql_view, name="shopify-webhook-graphql"),
path(r"webhooks/shopify-fulfillment", views.shopify_fulfillment_webhook_view, name="shopify-fulfillment-webhook"),
path(r"webhooks/recharge", views.recharge_webhook_view, name="recharge-webhook"),
path(r"webhooks/viome", views.viome_webhook_view, name="viome-webhook"),
path(r"subscription/", views.get_subscription, name="subscription"),
path(r"subscriptions/", views.get_subscriptions, name="subscriptions"),
path(r"subscriptions/<str:subscription_id>/", views.get_subscription_by_id, name="subscription-by-id"),
path(r"subscriptions/sku/<str:sku>/", views.get_active_subscription_by_product_sku, name="subscription-by-product-sku"),
path(r"subscription/exists/", views.subscription_exists, name="subscription-exists"),
path(r"subscription/next-charge/", views.update_next_subscription_charge, name="subscription-next-charge"),
path(r"subscription/next-charge-with-discount/", views.update_next_subscription_charge_with_discount, ...),
path(r"subscription/portal-link/", views.portal_link, name="subscription-portal-link"),
path(r"subscription/swap/", views.swap_subscription, name="subscription-swap"),
# (plus other non-ecomm paths: account, compare, trends, email-verification, etc.)
```

---

## Step 5: Read api/urls.py to understand structure

`read("backend/api/urls.py")`

```python
urlpatterns = [
    path(r"v1/", include(("api.v1.urls", "v1"), namespace="v1")),
    path(r"internal/", include(("api.internal.urls", "admin"), namespace="internal")),
    path(r"partner/", include(("partner_api.urls", "partner_api"), namespace="partner")),
    path("token/", EvvyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", EvvyTokenRefreshView.as_view(), name="token_refresh"),
    path("token/logout/", EvvyTokenBlacklistView.as_view(), name="token_blacklist"),
]
```

---

## Step 6: Read the views `__init__.py` to confirm modules

`read("backend/api/v1/views/__init__.py")`

Confirmed imports: cart, ecomm_products, orders, pdp_configuration, products, subscription, webhooks, consult, provider_test_orders, and others.

---

## Step 7: Read ecomm-specific view files

### CartViewSet — `backend/api/v1/views/cart.py`

`read("backend/api/v1/views/cart.py")`

`CartViewSet` registered at `r"cart"`. Actions:
- `create` — POST: create or get active cart
- `items` (POST/DELETE) on `cart/{id}/items/` — add or remove cart items
- `delete_items` (POST) on `cart/{id}/items/delete/` — alternative delete endpoint
- `checkout` (POST) on `cart/{id}/checkout/` — create checkout URL (supports OTC and prescription)

### OrdersView — `backend/api/v1/views/orders.py`

`read("backend/api/v1/views/orders.py")`

`OrdersView` at `orders/`, `orders/attach`, `orders/process`:
- GET: returns all orders for the user (open orders filter supported)
- PUT: attach an order to the current user by checkout_id or order_number
- POST: process unprocessed orders synchronously by checkout_token or checkout_id

### EcommProductView — `backend/api/v1/views/ecomm_products.py`

`read("backend/api/v1/views/ecomm_products.py")`

`EcommProductView` at `ecomm-products/<str:sku>/`:
- GET: public endpoint, returns a product by SKU

### Subscription views — `backend/api/v1/views/subscription.py`

`read("backend/api/v1/views/subscription.py")`

Function-based views (all authenticated):
- `get_subscription` — GET `subscription/`
- `get_subscriptions` — GET `subscriptions/`
- `get_subscription_by_id` — GET `subscriptions/<subscription_id>/`
- `get_active_subscription_by_product_sku` — GET `subscriptions/sku/<sku>/`
- `subscription_exists` — GET `subscription/exists/`
- `update_next_subscription_charge` — PUT `subscription/next-charge/`
- `update_next_subscription_charge_with_discount` — PUT `subscription/next-charge-with-discount/`
- `portal_link` — GET `subscription/portal-link/`
- `swap_subscription` — PUT `subscription/swap/`

### Webhook views — `backend/api/v1/views/webhooks.py`

`read("backend/api/v1/views/webhooks.py")`

Webhook handlers (all `@csrf_exempt`):
- `webhook_view` — POST `webhook/` — handles S3 upload events
- `shopify_webhook_view` — POST `webhooks/shopify` — orders/create, orders/cancelled
- `shopify_webhook_graphql_view` — POST `webhooks/shopify-graphql` — products/update, selling_plan_groups/update
- `shopify_fulfillment_webhook_view` — POST `webhooks/shopify-fulfillment` — fulfillment events
- `wheel_webhook_view` — POST `webhooks/wheel`
- `berlin_webhook_view` — POST `webhooks/berlin` — shipping/tracking
- `microgen_webhook_view` — POST `webhooks/microgen` — lab results
- `microgen_batch_webhook_view` — POST `webhooks/microgen-batch`
- `precision_pharmacy_webhook_view` — POST `webhooks/precision`
- `survicate_survey_complete_webhook_view` — POST `webhooks/survicate-survey-complete`
- `calendly_webhook_view` — POST `webhooks/calendly`
- `recharge_webhook_view` — POST `webhooks/recharge` — subscription lifecycle events
- `viome_webhook_view` — POST `webhooks/viome` — order creation/cancellation
- `junction_webhook_view` — POST `webhooks/junction` — lab test status updates
- `typeform_webhook_view` — POST `webhooks/typeform`

### ProductViewSet — `backend/api/v1/views/products.py`

`read("backend/api/v1/views/products.py")`

`ProductViewSet` registered at `r"products"`. Actions:
- Standard list/retrieve (care products)
- `all_products` (GET) on `products/all-products/` — returns test ecomm products (VMT, expanded PCR, memberships) and all care products

### PDPConfigurationViewSet — `backend/api/v1/views/pdp_configuration.py`

`read("backend/api/v1/views/pdp_configuration.py")`

`PDPConfigurationViewSet` registered at `r"pdp-configurations"`. Actions:
- Standard list/retrieve
- `by_care_product` (GET) on `pdp-configurations/by-care-product/<care_product_slug>/`
- `by_ecomm_product` (GET) on `pdp-configurations/by-ecomm-product/<ecomm_product_sku>/`
- `by_slug` (GET) on `pdp-configurations/by-slug/<slug>/`
- `featured` (GET) on `pdp-configurations/featured/`

---

## Step 8: Search for consult checkout views

`search("consult checkout URL view")`

Results:
```
backend/api/v1/views/consult.py 391  def checkout_url(self, request, uid=None)
backend/api/v1/views/consult.py 499  def cross_sell_checkout_url(self, request, uid=None)
```

`read("backend/api/v1/views/consult.py")` (lines 1–100 — class definition and imports)

`search("@action")` in consult.py revealed all action URLs:
```
254: @action(methods=["get"], detail=True)                        # treatment_plan
334: @action(methods=["post"], detail=True)                       # treatment_start_date
382: @action(methods=["patch"], detail=True, url_path="reset-calendar")
390: @action(methods=["get", "post"], detail=True)                # checkout_url (deprecated)
466: @action(methods=["get"], detail=False, url_path="order")     # get_consult_for_order
498: @action(methods=["get", "post"], detail=True, url_path="cross-sell-checkout-url")
572: @action(methods=["get"], detail=True, url_path="recommended-products")
595: @action(methods=["get", "post"], detail=True)                # messages
621: @action(methods=["put"], detail=True, url_path="messages/(?P<message_id>[^/.]+)/read")
772: @action(methods=["get"], detail=True, url_path="address-info")
791: @action(methods=["post"], detail=True)                       # agree_to_terms
817: @action(methods=["post"], detail=True)                       # consent_to_ungated_rx_terms
864: @action(methods=["post"], detail=True)                       # consent_to_not_trying_to_conceive
872: @action(methods=["post"], detail=True)                       # select_remove_antibiotics
895: @action(methods=["post"], detail=True)                       # submit
931: @action(methods=["get"], detail=False)                       # medications
952: @action(methods=["get"], detail=False)                       # pharmacies
```

`read("backend/api/v1/views/consult.py")` (lines 382–510) confirmed:
- `checkout_url` (GET/POST) on `consults/<uid>/checkout_url/` — deprecated, still used for STI intake; generates Shopify checkout URL for vaginitis/STI/UTI consults
- `get_consult_for_order` (GET) on `consults/order/?checkout_id=...` — look up consult by order
- `cross_sell_checkout_url` (GET/POST) on `consults/<uid>/cross-sell-checkout-url/` — upsell checkout URL generation

---

## Step 9: Search for additional checkout views

`search("refill prescription order view URL")`

Results:
```
backend/transactional_email/tasks.py   get_prescription_refills_context
backend/consults/admin.py              refill_page_url
backend/ecomm/tasks.py                 send_prescription_refill_request
```
(No additional URL patterns found for refills — these are background tasks, not views)

`search("male partner checkout view")`

Results:
```
backend/api/v1/views/userconfig.py 209  class MalePartnerCheckoutView(EvvyUserAPIView)
backend/api/v1/utils/male_partner.py 78 def create_male_partner_consult_and_checkout_url
```

---

## Step 10: Read `views.py` for `PublicProviderMagicLinkCheckout`

`read("backend/api/v1/views/views.py")`

`PublicProviderMagicLinkCheckout` (public, no auth) at `provider-test/<slug>/`:
- GET: exchanges a provider magic-link slug for a Shopify checkout URL

---

## Step 11: Check partner API URL files

`read("backend/partner_api/urls.py")` — routes to `cx_automation/`, `distro/`; no ecomm patterns

`read("backend/partner_api/distro/urls.py")`

```python
path("reports/<TestHash:test_hash>/", PartnerReportsView.as_view(), name="reports"),
path("tests/statuses/", PartnerTestStatusesView.as_view(), name="test-statuses"),
```
(Lab/reporting focused, not ecomm)

`read("backend/partner_api/cx_automation/urls.py")`

```python
path("test/", TestLookupView.as_view()),
path("test/<TestHash:test_hash>/status/", TestStatusView.as_view()),
path("test/<TestHash:test_hash>/shipping-status/", TestShippingView.as_view()),
path("consult/<str:consult_id>/prescription/", PrescriptionStatusView.as_view()),
path("consult/<str:consult_id>/intake/", ConsultIntakeView.as_view()),
```
(CX automation, not ecomm checkout)

---

## Step 12: Search for additional checkout and payment views

`search("payment checkout view URL payment processing")`

Results:
```
backend/api/v1/views/views.py           PublicProviderMagicLinkCheckout
backend/api/v1/views/provider_test_orders.py 336  def checkout_link(self, request, pk=None)
```

`search("provider test order checkout URL view")`

Confirmed: `provider_test_orders.py` has a `checkout_link` action.

---

## Step 13: Read ProviderTestOrderViewSet actions

`read("backend/api/v1/views/provider_test_orders.py")` (actions portion)

`ProviderTestOrderViewSet` registered at `r"provider-test-orders"`. Actions:
- `magic_link` (GET) on `provider-test-orders/magic-link/` — returns/generates provider magic link slug
- `create` — POST: create a single provider test order
- `bulk_create` (POST) on `provider-test-orders/bulk-create/`
- `remind_patient` (POST) on `provider-test-orders/remind-patient/`
- `plan_items` (GET) on `provider-test-orders/<id>/plan-items/`
- `checkout_link` (POST) on `provider-test-orders/<id>/checkout-link/` — generates provider-paid Shopify checkout URL
- `mark_downloaded` (POST) on `provider-test-orders/<id>/mark-downloaded/`

---

## Step 14: Check user_tests.py for ecomm-related checkout actions

`search("@action")` in `backend/api/v1/views/user_tests.py` revealed:
```
807: @action(methods=["post"], detail=True, url_path="ungated-checkout")
837: @action(methods=["post"], detail=True)                          # checkout
876: @action(methods=["post"], detail=False, url_path="retest-checkout")
995: @action(methods=["get"], detail=True, url_path="recommended-products")
1019: @action ... url_path="a-la-care-recommendations"
1056: @action(methods=["get"], detail=True, url_path="treatment-recommendations")
1148: @action(methods=["get"], detail=True, url_path="treatment-recommendations-lightweight")
1228: @action(methods=["get"], detail=False, url_path="all-available-treatments-lightweight")
```

`read("backend/api/v1/views/user_tests.py")` (lines 807–907):

`UserTestViewSet` registered at `r"user-tests"`. Ecomm-related actions:
- `ungated_checkout` (POST) on `user-tests/<hash>/ungated-checkout/` — creates ungated RX checkout for health-history upsell
- `checkout` (POST) on `user-tests/<hash>/checkout/` — creates checkout for vPCR add-on
- `retest_checkout` (POST) on `user-tests/retest-checkout/` — creates retest checkout with RETEST20 discount

---

## Step 15: Scan for any remaining ecomm URL patterns

`search("path.*ecomm|url.*ecomm|ecomm.*path|ecomm.*url")` across all `*.py` files

Confirmed:
- `api/v1/views/pdp_configuration.py:67` — `by-ecomm-product/(?P<ecomm_product_sku>[^/.]+)` (already found)
- Various migration files and test patches (not URL patterns)

---

## Final Answer

### Comprehensive List of Ecomm-Related URL Patterns

All patterns below are under `api/` prefix, then `v1/` prefix (i.e., full path is `/api/v1/<pattern>`).

---

#### Cart

| URL Path | View | File |
|---|---|---|
| `cart/` (GET/POST) | `CartViewSet` (list/create) | `api/v1/views/cart.py` |
| `cart/<id>/` (GET/PUT/PATCH/DELETE) | `CartViewSet` | `api/v1/views/cart.py` |
| `cart/<id>/items/` (POST/DELETE) | `CartViewSet.items` | `api/v1/views/cart.py` |
| `cart/<id>/items/delete/` (POST) | `CartViewSet.delete_items` | `api/v1/views/cart.py` |
| `cart/<id>/checkout/` (POST) | `CartViewSet.checkout` | `api/v1/views/cart.py` |

---

#### Orders

| URL Path | View | File |
|---|---|---|
| `orders/` (GET) | `OrdersView` | `api/v1/views/orders.py` |
| `orders/attach` (PUT) | `OrdersView` | `api/v1/views/orders.py` |
| `orders/process` (POST) | `OrdersView` | `api/v1/views/orders.py` |

---

#### Products & PDP

| URL Path | View | File |
|---|---|---|
| `ecomm-products/<str:sku>/` (GET) | `EcommProductView` | `api/v1/views/ecomm_products.py` |
| `products/` (GET) | `ProductViewSet` (care products) | `api/v1/views/products.py` |
| `products/all-products/` (GET) | `ProductViewSet.all_products` | `api/v1/views/products.py` |
| `pdp-configurations/` (GET) | `PDPConfigurationViewSet` | `api/v1/views/pdp_configuration.py` |
| `pdp-configurations/<id>/` (GET) | `PDPConfigurationViewSet` | `api/v1/views/pdp_configuration.py` |
| `pdp-configurations/by-care-product/<care_product_slug>/` (GET) | `PDPConfigurationViewSet.by_care_product` | `api/v1/views/pdp_configuration.py` |
| `pdp-configurations/by-ecomm-product/<ecomm_product_sku>/` (GET) | `PDPConfigurationViewSet.by_ecomm_product` | `api/v1/views/pdp_configuration.py` |
| `pdp-configurations/by-slug/<slug>/` (GET) | `PDPConfigurationViewSet.by_slug` | `api/v1/views/pdp_configuration.py` |
| `pdp-configurations/featured/` (GET) | `PDPConfigurationViewSet.featured` | `api/v1/views/pdp_configuration.py` |

---

#### Subscriptions

| URL Path | View | File |
|---|---|---|
| `subscription/` (GET) | `get_subscription` | `api/v1/views/subscription.py` |
| `subscriptions/` (GET) | `get_subscriptions` | `api/v1/views/subscription.py` |
| `subscriptions/<subscription_id>/` (GET) | `get_subscription_by_id` | `api/v1/views/subscription.py` |
| `subscriptions/sku/<sku>/` (GET) | `get_active_subscription_by_product_sku` | `api/v1/views/subscription.py` |
| `subscription/exists/` (GET) | `subscription_exists` | `api/v1/views/subscription.py` |
| `subscription/next-charge/` (PUT) | `update_next_subscription_charge` | `api/v1/views/subscription.py` |
| `subscription/next-charge-with-discount/` (PUT) | `update_next_subscription_charge_with_discount` | `api/v1/views/subscription.py` |
| `subscription/portal-link/` (GET) | `portal_link` | `api/v1/views/subscription.py` |
| `subscription/swap/` (PUT) | `swap_subscription` | `api/v1/views/subscription.py` |

---

#### Consult Checkout

| URL Path | View | File |
|---|---|---|
| `consults/<uid>/checkout_url/` (GET/POST) | `ConsultViewSet.checkout_url` [deprecated] | `api/v1/views/consult.py` |
| `consults/<uid>/cross-sell-checkout-url/` (GET/POST) | `ConsultViewSet.cross_sell_checkout_url` | `api/v1/views/consult.py` |
| `consults/order/` (GET) | `ConsultViewSet.get_consult_for_order` | `api/v1/views/consult.py` |
| `male-partner-checkout/` (POST) | `MalePartnerCheckoutView` | `api/v1/views/userconfig.py` |

---

#### Provider / Magic Link Checkout

| URL Path | View | File |
|---|---|---|
| `provider-test/<slug>/` (GET, public) | `PublicProviderMagicLinkCheckout` | `api/v1/views/views.py` |
| `provider-test-orders/` (GET/POST) | `ProviderTestOrderViewSet` | `api/v1/views/provider_test_orders.py` |
| `provider-test-orders/magic-link/` (GET) | `ProviderTestOrderViewSet.magic_link` | `api/v1/views/provider_test_orders.py` |
| `provider-test-orders/bulk-create/` (POST) | `ProviderTestOrderViewSet.bulk_create` | `api/v1/views/provider_test_orders.py` |
| `provider-test-orders/remind-patient/` (POST) | `ProviderTestOrderViewSet.remind_patient` | `api/v1/views/provider_test_orders.py` |
| `provider-test-orders/<id>/plan-items/` (GET) | `ProviderTestOrderViewSet.plan_items` | `api/v1/views/provider_test_orders.py` |
| `provider-test-orders/<id>/checkout-link/` (POST) | `ProviderTestOrderViewSet.checkout_link` | `api/v1/views/provider_test_orders.py` |
| `provider-test-orders/<id>/mark-downloaded/` (POST) | `ProviderTestOrderViewSet.mark_downloaded` | `api/v1/views/provider_test_orders.py` |

---

#### User Test Checkout

| URL Path | View | File |
|---|---|---|
| `user-tests/<hash>/ungated-checkout/` (POST) | `UserTestViewSet.ungated_checkout` | `api/v1/views/user_tests.py` |
| `user-tests/<hash>/checkout/` (POST) | `UserTestViewSet.checkout` | `api/v1/views/user_tests.py` |
| `user-tests/retest-checkout/` (POST) | `UserTestViewSet.retest_checkout` | `api/v1/views/user_tests.py` |

---

#### Shopify & Payment Webhooks

| URL Path | View | File |
|---|---|---|
| `webhook/` (POST) | `webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/shopify` (POST) | `shopify_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/shopify-graphql` (POST) | `shopify_webhook_graphql_view` | `api/v1/views/webhooks.py` |
| `webhooks/shopify-fulfillment` (POST) | `shopify_fulfillment_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/recharge` (POST) | `recharge_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/viome` (POST) | `viome_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/wheel` (POST) | `wheel_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/precision` (POST) | `precision_pharmacy_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/berlin` (POST) | `berlin_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/microgen` (POST) | `microgen_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/microgen-batch` (POST) | `microgen_batch_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/survicate-survey-complete` (POST) | `survicate_survey_complete_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/calendly` (POST) | `calendly_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/junction` (POST) | `junction_webhook_view` | `api/v1/views/webhooks.py` |
| `webhooks/typeform` (POST) | `typeform_webhook_view` | `api/v1/views/webhooks.py` |
