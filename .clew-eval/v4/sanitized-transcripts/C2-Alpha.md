# C2 Exploration Log

## Search 1: Broad case-insensitive grep for "stripe" across entire evvy directory

Searched for the literal string "stripe" (case-insensitive) across all files in /Users/albertgwo/Work/evvy. Found only one application file match:

- `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_order_monitoring.py`

The match was a string literal `"stripe"` used as a payment gateway name value, not a Stripe SDK import or API call.

## Search 2: Grep for `stripe.` (dot notation method calls)

search("stripe\.")

## Search 3: Grep for capitalized "Stripe" (class/module references)

Searched for `Stripe` (exact case). No matches found.

## Search 4: List top-level directory structure

Confirmed the repo structure: `backend/`, `frontend/`, `internal-frontend/`, `scripts/`, `docs/`, `tools/`.

## Search 5: Grep for Stripe-related API patterns

search("import stripe|from stripe|stripe\.api|stripe\.PaymentIntent|stripe\.Customer|stripe\.Subscription|stripe\.Charge|stripe\.Invoice|stripe\.checkout|stripe\.webhook|stripe\.Price|stripe\.Product|StripeClient|stripe_sdk")

## Search 6: Grep for payment-related keywords

search("payment_intent|PaymentIntent|payment_method|checkout.session|webhook|STRIPE")

## Search 7: Check backend requirements for stripe package

Read `/Users/albertgwo/Work/evvy/backend/requirements.txt` and searched for "stripe". No stripe package listed.

## Search 8: Check frontend directory for Stripe

Listed frontend directory structure. Searched for `stripe|Stripe|@stripe` in `frontend/src` and `frontend/` directories. No matches found. Checked `frontend/package.json` — no stripe dependency listed.

## Search 9: Check internal-frontend for Stripe

Searched for `stripe|Stripe|@stripe` in `/Users/albertgwo/Work/evvy/internal-frontend`. No matches.

## Search 10: Read the webhooks view for Stripe webhook handlers

Read `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` in full. Confirmed: webhook handlers exist for Shopify, Recharge, Wheel, Berlin, Microgen, Precision Pharmacy, Survicate, Calendly, Viome, Junction, and Typeform — but NO Stripe webhook handler.

## Search 11: Glob for stripe-named files

Used Glob pattern `/Users/albertgwo/Work/evvy/backend/**/*stripe*`. Found only FontAwesome SVG icon files and static assets in the admin UI — no application code files.

## Search 12: Check requirements files for stripe SDK

Searched both `requirements.txt` and `requirements.in` for "stripe". Neither file contains a stripe dependency.

## Search 13: Broad search across all code file types

Searched all `.py`, `.ts`, `.tsx`, `.js`, `.json` files (excluding `node_modules`, `venv`, `__pycache__`, `.svg`) for "stripe". Confirmed: only matches are in:
1. `test_order_monitoring.py` — the string `"stripe"` as a Shopify `payment_gateway_names` value
2. FontAwesome JavaScript bundles (icon library, unrelated to payments)
3. Git worktree copies of the same test file

## Search 14: Check settings.py for Stripe configuration keys

Searched `app/settings.py` for `STRIPE_`, `stripe_key`, `stripe_secret`, `STRIPE_API`, etc. No Stripe configuration found.

## Search 15: Examine how payment_gateway_names is used in ecomm/utils.py

Confirmed that `payment_gateway_names` in `ecomm/utils.py` is a field read from Shopify order payloads. The value `"stripe"` can appear in this list when a Shopify customer used Stripe as a payment gateway at checkout — but this is Shopify-side data, not a direct Stripe API call from this codebase.

---

## Final Answer

**There are no Stripe API calls in the Evvy codebase.**

The Stripe SDK is not installed (not listed in `backend/requirements.txt` or `backend/requirements.in`), there are no `import stripe` or `from stripe` statements in any Python file, no `@stripe/*` packages in the frontend (`frontend/package.json`), and no Stripe API methods are called anywhere in the application code.

### What was found (and why it is NOT a Stripe API call):

**File: `/Users/albertgwo/Work/evvy/backend/ecomm/tests/test_order_monitoring.py`**
Lines 189, 196, 202, 208 — The string `"stripe"` appears as a test fixture value for a Shopify order's `payment_gateway_names` field:

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

This is a **Shopify webhook payload field** — Shopify reports which payment gateway was used for a customer's checkout. The string `"stripe"` is a Shopify-defined identifier for orders processed through their Stripe integration. The application reads this value passively from Shopify's webhook payload for analytics tracking purposes; it does not call any Stripe API.

**Related application code in `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py`:**

```python
# Line 619-626
payment_gateway_names = payload.get("payment_gateway_names", [])
if payment_gateway_names and not is_order_cancellation:
    payment_method = payment_gateway_names[0] if payment_gateway_names else "unknown"
    ...
    track_checkout_completion(
        ...,
        payment_method=payment_method,
    )
```

This reads the Shopify-provided payment gateway name (which may be `"stripe"` or any other gateway) and forwards it to analytics tracking — still not a Stripe API call.

### Conclusion

The Evvy codebase uses **Shopify** as its e-commerce platform and **Recharge** for subscription management. Shopify itself may use Stripe as an underlying payment processor for some orders, but the Evvy application never directly integrates with Stripe's API. There are no Stripe SDK installations, no Stripe API key configurations, no Stripe webhook handlers, and no calls to Stripe's REST endpoints or SDK methods anywhere in the codebase.
