# C2 — Agent Beta

## Stripe API Calls in the Evvy Codebase

After an exhaustive search across all Python files in `/Users/albertgwo/Work/evvy/backend`, all TypeScript/JavaScript files in `/Users/albertgwo/Work/evvy/frontend` and `/Users/albertgwo/Work/evvy/internal-frontend`, and the scripts directory, **there are no Stripe API SDK calls in this codebase.**

### What the search found

The only references to "stripe" in the codebase are string literals used as a payment gateway name identifier in Shopify webhook processing:

**File: `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_order_monitoring.py`** (lines 189, 196, 202, 208)

These are test assertions checking that when a Shopify order webhook arrives with `payment_gateway_names: ["stripe"]`, the system correctly passes the string `"stripe"` as a `payment_method` label to analytics/metrics tracking. The string `"stripe"` here is Shopify's name for the Stripe payment gateway — it is NOT a call to the Stripe API.

```python
# Line 189
payload_with_session["payment_gateway_names"] = ["stripe"]
# ...
self.assertEqual(call_kwargs["payment_method"], "stripe")  # Line 196

# Line 202
payload["payment_gateway_names"] = ["stripe", "paypal"]
# ...
self.assertEqual(call_kwargs["payment_method"], "stripe")  # Line 208
```

### What payment infrastructure IS used

The codebase uses **Recharge** as its subscription/billing API (via `/Users/albertgwo/Work/evvy/backend/subscriptions/recharge.py`), which handles payment processing. Recharge itself integrates with Stripe on the backend, which is why "stripe" appears as a `payment_gateway_name` in Shopify webhooks — but the Evvy application does not call Stripe APIs directly.

Key observations:
- The `stripe` Python package is **not listed** in `requirements.txt` or `requirements.in`
- There are no `import stripe` statements anywhere
- There are no `stripe.Customer.create()`, `stripe.PaymentIntent.create()`, or similar method calls
- The frontend `package.json` files do not include `@stripe/stripe-js` or similar Stripe SDKs

**Conclusion: This codebase does not make any direct Stripe API calls.** Payment processing is delegated to Recharge, and Stripe only appears as a payment gateway name string passed through from Shopify order webhooks.
