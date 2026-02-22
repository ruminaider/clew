# C1-beta: Find all Django URL patterns involving ecomm-related views

## Task
Find all Django URL patterns that involve ecomm-related views. List each URL pattern with its view and URL path.

## Search Process

### Step 1: Initial Discovery
Located Django URL configuration files and ecomm directory structure:
- Main URLs: `/Users/albertgwo/Work/evvy/backend/app/urls.py`
- API URLs: `/Users/albertgwo/Work/evvy/backend/api/urls.py`
- API v1 URLs: `/Users/albertgwo/Work/evvy/backend/api/v1/urls.py`
- Ecomm app exists at: `/Users/albertgwo/Work/evvy/backend/ecomm/`

### Step 2: URL Configuration Analysis
Examined the main URL routing structure:
- `app/urls.py` routes to `api.urls`
- `api/urls.py` routes to `api.v1.urls` (v1 namespace)
- `api.v1/urls.py` contains the actual URL patterns

### Step 3: Ecomm View Discovery
Found ecomm-related views in `/Users/albertgwo/Work/evvy/backend/api/v1/views/`:
- `ecomm_products.py` - EcommProductView
- `cart.py` - CartViewSet
- `orders.py` - OrdersView
- `products.py` - ProductViewSet
- `pdp_configuration.py` - PDPConfigurationViewSet
- `subscription.py` - Various subscription function-based views
- `webhooks.py` - Shopify and Recharge webhook views
- `userconfig.py` - MalePartnerCheckoutView
- `views.py` - PublicProviderMagicLinkCheckout

## Complete List of Ecomm-Related URL Patterns

### 1. Cart Management
**URL:** `/api/v1/cart/`
**View:** `CartViewSet` (from `api.v1.views.cart`)
**Type:** ViewSet (REST framework router)
**Description:** Ecommerce cart operations - get latest active cart, add to cart, checkout

### 2. Orders
**URL:** `/api/v1/orders/`
**View:** `OrdersView.get()` (from `api.v1.views.orders`)
**Description:** Returns all orders for requesting user

**URL:** `/api/v1/orders/attach`
**View:** `OrdersView` (from `api.v1.views.orders`)
**Description:** Order attachment operations

**URL:** `/api/v1/orders/process`
**View:** `OrdersView` (from `api.v1.views.orders`)
**Description:** Order processing operations

### 3. Products
**URL:** `/api/v1/products/`
**View:** `ProductViewSet` (from `api.v1.views.products`)
**Type:** ViewSet (REST framework router)
**Description:** Model viewset for getting all care products (treatments available)

**URL:** `/api/v1/products/all-products`
**View:** `ProductViewSet.all_products()` (from `api.v1.views.products`)
**Type:** ViewSet action
**Description:** Get ecomm_products for all test types (VMT, expanded PCR, memberships) and all care products

**URL:** `/api/v1/ecomm-products/<str:sku>/`
**View:** `EcommProductView.get()` (from `api.v1.views.ecomm_products`)
**Description:** Get an EcommProduct by SKU (public endpoint, no authentication required)

### 4. PDP (Product Detail Page) Configuration
**URL:** `/api/v1/pdp-configurations/`
**View:** `PDPConfigurationViewSet` (from `api.v1.views.pdp_configuration`)
**Type:** ViewSet (REST framework router)
**Description:** ViewSet for PDP configurations

**URL:** `/api/v1/pdp-configurations/by-care-product/<care_product_slug>/`
**View:** `PDPConfigurationViewSet.by_care_product()` (from `api.v1.views.pdp_configuration`)
**Type:** ViewSet action
**Description:** Get PDP configuration by care product slug

### 5. Checkout
**URL:** `/api/v1/male-partner-checkout/`
**View:** `MalePartnerCheckoutView` (from `api.v1.views.userconfig`)
**Description:** Male partner checkout view

**URL:** `/api/v1/provider-test/<slug>/`
**View:** `PublicProviderMagicLinkCheckout` (from `api.v1.views.views`)
**Description:** Public magic link to exchange slug for checkout URL

### 6. Subscriptions
**URL:** `/api/v1/subscription/`
**View:** `get_subscription()` (from `api.v1.views.subscription`)
**Description:** Get user's subscription information

**URL:** `/api/v1/subscriptions/`
**View:** `get_subscriptions()` (from `api.v1.views.subscription`)
**Description:** Get all subscriptions for user

**URL:** `/api/v1/subscriptions/<str:subscription_id>/`
**View:** `get_subscription_by_id()` (from `api.v1.views.subscription`)
**Description:** Get subscription by ID

**URL:** `/api/v1/subscriptions/sku/<str:sku>/`
**View:** `get_active_subscription_by_product_sku()` (from `api.v1.views.subscription`)
**Description:** Get active subscription by product SKU

**URL:** `/api/v1/subscription/exists/`
**View:** `subscription_exists()` (from `api.v1.views.subscription`)
**Description:** Check if user has a subscription

**URL:** `/api/v1/subscription/next-charge/`
**View:** `update_next_subscription_charge()` (from `api.v1.views.subscription`)
**Description:** Update next subscription charge date

**URL:** `/api/v1/subscription/next-charge-with-discount/`
**View:** `update_next_subscription_charge_with_discount()` (from `api.v1.views.subscription`)
**Description:** Update next subscription charge with discount

**URL:** `/api/v1/subscription/portal-link/`
**View:** `portal_link()` (from `api.v1.views.subscription`)
**Description:** Get subscription portal link

**URL:** `/api/v1/subscription/swap/`
**View:** `swap_subscription()` (from `api.v1.views.subscription`)
**Description:** Swap subscription type

### 7. Webhooks (Ecomm-related)
**URL:** `/api/v1/webhooks/shopify`
**View:** `shopify_webhook_view()` (from `api.v1.views.webhooks`)
**Description:** Shopify webhook endpoint

**URL:** `/api/v1/webhooks/shopify-graphql`
**View:** `shopify_webhook_graphql_view()` (from `api.v1.views.webhooks`)
**Description:** Shopify GraphQL webhook endpoint

**URL:** `/api/v1/webhooks/shopify-fulfillment`
**View:** `shopify_fulfillment_webhook_view()` (from `api.v1.views.webhooks`)
**Description:** Shopify fulfillment webhook endpoint

**URL:** `/api/v1/webhooks/recharge`
**View:** `recharge_webhook_view()` (from `api.v1.views.webhooks`)
**Description:** Recharge (subscription platform) webhook endpoint

## Summary

Found **26 distinct ecomm-related URL patterns** across 7 functional categories:
1. Cart Management (1 viewset endpoint)
2. Orders (3 endpoints)
3. Products (3 endpoints)
4. PDP Configuration (2 endpoints)
5. Checkout (2 endpoints)
6. Subscriptions (8 endpoints)
7. Webhooks (4 endpoints)

All endpoints are mounted under `/api/v1/` prefix (except webhooks which are also under `/api/v1/webhooks/`).

## Tool Calls Used
1. find_files("urls.py")
2. find_files("ecomm/")
3. search("ecomm")
4. read("/Users/albertgwo/Work/evvy/backend/app/urls.py")
5. read("/Users/albertgwo/Work/evvy/backend/api/urls.py")
6. read("/Users/albertgwo/Work/evvy/backend/api/v1/urls.py")
7. find_files("ecomm views")
8. search("ecomm view classes")
9. read("/Users/albertgwo/Work/evvy/backend/api/v1/views/ecomm_products.py")
10. search("cart/order/product related files")
11. read("/Users/albertgwo/Work/evvy/backend/api/v1/views/__init__.py")
12. read("/Users/albertgwo/Work/evvy/backend/api/v1/views/cart.py")
13. read("/Users/albertgwo/Work/evvy/backend/api/v1/views/orders.py")
14. read("/Users/albertgwo/Work/evvy/backend/api/v1/views/products.py")
15. read("/Users/albertgwo/Work/evvy/backend/api/v1/views/pdp_configuration.py")
16. search("shopify/recharge webhook functions")
17. read("/Users/albertgwo/Work/evvy/backend/api/v1/views/subscription.py")
18. search("checkout view classes")
19. read("/Users/albertgwo/Work/evvy/backend/api/internal/urls.py")
