# C2: Stripe API Calls — Search Transcript

## Task

Find all Stripe API calls in the codebase. List each call site with the Stripe API method being called and the context in which it's used.

## Search Strategy

Searched the `/Users/albertgwo/Work/evvy` codebase using the following queries:

1. `stripe\.` (regex, all files) — 0 source-code matches
2. `import stripe` (Python files) — 0 matches
3. `Stripe` (case-sensitive, all source files) — 0 matches
4. `stripe` (case-insensitive, all `.py`, `.js`, `.ts`, `.tsx`, `.jsx` files)
5. `STRIPE` / `stripe_` (env vars, variable names in Python) — 0 matches
6. Checked `requirements.txt` for the `stripe` package — not present
7. Checked `frontend/package.json` and `internal-frontend/package.json` for `@stripe` / `stripe` — not present
8. Checked `backend/app/settings.py` for Stripe configuration — none found
9. Checked `frontend/src/` directory tree for any Stripe JS SDK usage — none found

## Result

**There are no Stripe API calls in this codebase.**

The word "stripe" appears in exactly one file, and only as a string literal representing a payment gateway name — not as an SDK or API call:

### `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_order_monitoring.py`

Lines 189, 196, 202, 208 — "stripe" is used as a test fixture value for the `payment_gateway_names` field in a Shopify order payload, and as an expected assertion value in metric tracking tests:

```python
# Line 189
payload_with_session["payment_gateway_names"] = ["stripe"]

# Line 196
self.assertEqual(call_kwargs["payment_method"], "stripe")

# Line 202
payload["payment_gateway_names"] = ["stripe", "paypal"]

# Line 208
self.assertEqual(call_kwargs["payment_method"], "stripe")
```

These are test fixtures verifying that the order processing pipeline correctly passes through whatever `payment_gateway_names` value Shopify sends (Shopify can route payments through Stripe as a gateway), but the evvy application itself does not call any Stripe API directly.

## Payment Infrastructure Actually Used

The codebase uses:
- **Shopify Payments** — via the Shopify webhook/order pipeline (`ecomm/` module)
- **Recharge** — for subscription billing (`subscriptions/recharge.py`, `RechargeAPIClient` class calling `https://api.rechargeapps.com/`)

Neither the Python backend nor the React frontend integrates the Stripe SDK or calls any Stripe API endpoints directly.
