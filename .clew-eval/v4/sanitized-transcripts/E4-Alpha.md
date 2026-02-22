# E4 Exploration Log

## Search 1: subscription order confirmation email

Searched for "subscription order confirmation email". Top results:

- `/Users/albertgwo/Work/evvy/backend/subscriptions/recharge.py` lines 93-101: `send_account_email` — a RechargeAPIClient method that POSTs to the Recharge API `/customers/{id}/notifications` with `template_type: "get_account_access"`. This is a Recharge-side account access email, not an order confirmation email per se.
- `/Users/albertgwo/Work/evvy/backend/subscriptions/subscription_service.py` — `SubscriptionService` class
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 238-790: `_process_shopify_order_impl` — large function handling all Shopify order processing

## Search 2: recharge webhook charge paid order processed

Searched for "recharge webhook charge paid order processed". Top results:

- `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` lines 26-63: `handle_charge_upcoming_webhook` — handles `charge/upcoming` topic
- `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` lines 369-445: `recharge_webhook_view` — routes ReCharge webhooks to handlers

Key finding: `recharge_webhook_view` handles these topics:
- `charge/upcoming` → `handle_charge_upcoming_webhook()`
- `subscription/created`, `subscription/cancelled`, `subscription/activated`, `subscription/swapped` → `handle_subscription_webhook()`

**Critical gap**: No `charge/paid` or `orders/paid` webhook topic is handled in the ReCharge webhook view. The subscription order email flow relies on `subscription/created`.

## Search 3: shopify order paid webhook email notification

Searched for "shopify order paid webhook email notification". Confirmed:

- `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` lines 82-145: `shopify_webhook_view` only handles `orders/create` and `orders/cancelled` topics
- `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 204-790: `process_shopify_order` / `_process_shopify_order_impl` — the main order processing function
- `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py` line 806: `send_any_paid_event` — analytics/FullStory event only, NOT an email

## Search 4: Reading _process_shopify_order_impl in detail

Read `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` lines 635-790.

Key findings:
- Order is classified as subscription if `line_item_has_subscription` or `is_subscription_sku` (lines 491-582)
- `send_any_paid_event.delay(order.order_number)` (line 744) — analytics event to FullStory, not email
- `send_order_to_berlin_for_fulfillment.delay(...)` (line 763) — shipping/fulfillment only
- No direct confirmation email is sent from `_process_shopify_order_impl` for subscription orders
- No `send_membership_email`, `send_subscription_welcome`, or any other email-sending call is present

## Search 5: Reading subscriptions/service.py (handle_subscription_webhook)

Read the full `handle_subscription_webhook` function in `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py`.

This is the PRIMARY email trigger path for subscription orders:

```python
def handle_subscription_webhook(payload, send_braze_event=True, topic=None):
    try:
        subscription_data, success = _extract_data_from_payload(payload, "subscription")
        if not success:
            return False  # SILENT FAILURE: logs error but webhook returns 200

        recharge_subscription_id = subscription_data.get("id")
        if not recharge_subscription_id:
            logger.error("Missing id in subscription webhook")
            return False  # SILENT FAILURE

        formatted_subscription_data = _format_subscription_payload(subscription_data)
        email = formatted_subscription_data.get("email")
        user = User.objects.filter(email=email).first()
        if not user:
            logger.error(f"User not found for subscription webhook: {email}")
            return False  # SILENT FAILURE: email/user mismatch kills the chain

        subscription_service = SubscriptionService(user, force_refresh=True)
        subscriptions_response = subscription_service.get_all_subscriptions_with_cache()

        update_user_profile(...)  # Updates Braze profile

        if send_braze_event:
            braze_event_name = _get_braze_event_for_subscription_topic(topic, subscription_data)
            if braze_event_name:
                track_event(user=user, event_name=braze_event_name, ...)
                # ^ This triggers the Braze campaign/canvas that sends the email
        return True

    except Exception as e:
        logger.exception(f"Error processing subscription webhook: {str(e)}")
        return False  # SILENT FAILURE: exceptions swallowed
```

The `subscription/created` webhook → `handle_subscription_webhook()` → `track_event()` with `BrazeEventName.SUBSCRIPTION_CREATED` — this is what triggers the confirmation email in Braze.

## Search 6: Reading analytics/service.py track_event

Read `/Users/albertgwo/Work/evvy/backend/analytics/service.py`.

Key finding: `track_event()` wraps everything in `try/except Exception` and **returns None on any failure** without re-raising:

```python
def track_event(...) -> Dict[str, Any] | None:
    try:
        ...
        return braze_track_user_event(...)
    except Exception as e:
        user_identifier = user.uuid if user else alias_name
        logger.error(f"Error tracking event {event_name} for {user_identifier}: {e}")
        return None  # SILENT FAILURE: swallows all errors
```

The caller (`handle_subscription_webhook`) does NOT check the return value of `track_event()`. If `track_event` returns None, the caller logs "Successfully processed subscription webhook" at line 117 and returns True. The webhook response is HTTP 200.

## Search 7: Reading analytics/braze/braze.py

Read `BrazeAPIClient.track_user()` and `_make_request()`.

- `_make_request()` has `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` decorator — retries 3 times on failure
- After 3 failures, raises `HTTPRequestError` which propagates up through `braze_track_user_event()` → `track_event()` where it's caught and swallowed
- If `BRAZE_API_KEY` is not set, `BrazeAPIClient.__init__` raises `Exception("Missing Braze API key")` — caught and swallowed by `track_event`

## Search 8: Reading transactional_email/utils.py and mandrill.py

Confirmed email infrastructure:
- Mandrill (`mailchimp_transactional`) for direct templated emails (test kit lifecycle, care, treatments)
- Braze events via REST API for subscription-triggered emails (campaigns/canvases)
- `send_transactional_email()` uses `send_mail()` (Django SMTP), catches exceptions with `print()` only (no logging, no re-raise)

Key finding in `send_transactional_email()`:
```python
try:
    send_mail(subject, body, from_address, to_addresses, fail_silently=False)
except Exception as e:
    print(f"failed to send email with subject {subject}: {str(e)}")
    # No raise, no logging to logging framework
```

## Search 9: Reading transactional_email/constants.py

Confirmed there is NO Mandrill template for subscription order confirmation. The `DISABLED_EMAIL_FLOWS` dict disables 15+ templates. Subscription confirmation is NOT handled via Mandrill at all.

## Search 10: Verifying send_account_email call sites

`RechargeAPIClient.send_account_email()` is defined in `recharge.py:93` but is **never called from any other backend file** (confirmed via grep). It is effectively dead code in the subscription order confirmation flow.

## Search 11: Email flow for subscription orders in recharge_webhook_view

Read `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` lines 369-445.

The `recharge_webhook_view` returns HTTP 200 regardless of whether `handle_subscription_webhook` returns True or False (line 445). ReCharge will NOT retry if it gets a 200.

---

## Final Answer

### The Subscription Order Email Pipeline

The confirmation email for a subscription order is triggered through two separate webhook flows — Shopify (for order processing) and ReCharge (for the email trigger) — and depends on a Braze campaign/canvas firing on the `subscription_created` event. There is no direct transactional email sent for subscription orders.

### Full Flow

```
1. User places subscription order on Shopify
       |
       v
2. Shopify sends orders/create webhook
   -> POST /webhooks/shopify/
   -> shopify_webhook_view() [backend/api/v1/views/webhooks.py:82]
   -> process_shopify_order() [backend/ecomm/utils.py:204]
   -> _process_shopify_order_impl() [backend/ecomm/utils.py:238]
      - Sets order.is_subscription_order = True [line 492]
      - Dispatches send_any_paid_event (analytics only, NOT email) [line 744]
      - Dispatches send_order_to_berlin_for_fulfillment (fulfillment only) [line 763]
      - NO confirmation email sent here
       |
       v
3. ReCharge sends subscription/created webhook (separately)
   -> POST /webhooks/recharge/
   -> recharge_webhook_view() [backend/api/v1/views/webhooks.py:369]
   -> handle_subscription_webhook(payload, send_braze_event=True, topic="subscription/created")
      [backend/subscriptions/service.py:66]
      - Extracts subscription data
      - Looks up user by email (User.objects.filter(email=email).first())
      - Calls track_event(user, BrazeEventName.SUBSCRIPTION_CREATED, ...)
        [backend/analytics/service.py:51]
        -> braze_track_user_event() [backend/analytics/braze/utils.py:74]
        -> BrazeAPIClient.track_user() [backend/analytics/braze/braze.py:150]
        -> POST to Braze /users/track endpoint
       |
       v
4. Braze receives subscription_created event
   -> Braze campaign/canvas fires -> sends confirmation email to user
```

### Where Emails Can Fail Silently

There are **four distinct silent failure paths** in this pipeline:

#### Failure Path 1: User not found by email in handle_subscription_webhook

**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py`, lines 90-93

```python
email = formatted_subscription_data.get("email")
user = User.objects.filter(email=email).first()
if not user:
    logger.error(f"User not found for subscription webhook: {email}")
    return False  # <-- silent failure
```

**Scenario:** If the ReCharge subscription email does not exactly match the evvy account email (case sensitivity issue, typo, or user registered with a different email), the user lookup returns None. The webhook handler logs an error and returns False. The `recharge_webhook_view` returns HTTP 200 anyway (line 445), so ReCharge does not retry. The Braze event is never fired. The confirmation email is never sent. No exception is raised upstream.

**Why it's silent:** The webhook view at line 440-444 returns `HttpResponse(status=200)` unconditionally, regardless of the `success` flag. ReCharge treats 200 as successful delivery.

#### Failure Path 2: SubscriptionService.get_all_subscriptions_with_cache() fails

**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/subscription_service.py`, lines 137-142

```python
try:
    subscriptions = self.get_all_subscriptions()
    ...
    return subscriptions
except Exception as e:
    logger.error(f"Failed to refresh subscriptions for user {self.user.id}: {e}")
    cached_subscriptions = cache.get(cache_key)
    if cached_subscriptions:
        return cached_subscriptions
    return SubscriptionsResponse(subscriptions=[])  # <-- empty, but continues
```

The Recharge API call to `get_active_subscriptions` (which wraps `_make_request`) has `@retry(stop_max_attempt_number=3)` but after 3 failures raises. The outer `except` in `get_all_subscriptions_with_cache` swallows it and returns an empty `SubscriptionsResponse`. Execution continues to `update_user_profile` and then `track_event`. **This path does NOT block email sending**, but it silently sets `active_subscriptions` to an empty string in Braze.

**More critically:** If `get_all_subscriptions()` raises an exception that is NOT caught by the inner `try/except` inside `get_all_subscriptions_with_cache`, it will propagate to the outer `try/except Exception` in `handle_subscription_webhook` at line 122, which returns False and the email is never sent.

#### Failure Path 3: track_event() fails silently — Braze API error

**File:** `/Users/albertgwo/Work/evvy/backend/analytics/service.py`, lines 83-86

```python
except Exception as e:
    user_identifier = user.uuid if user else alias_name
    logger.error(f"Error tracking event {event_name} for {user_identifier}: {e}")
    return None  # <-- swallows all failures
```

After `BrazeAPIClient._make_request()` retries 3 times (with 500ms exponential backoff) and still fails, the `HTTPRequestError` propagates up through `braze_track_user_event` → `track_event`, where it is caught and swallowed, returning `None`. The return value of `track_event` is **not checked** by `handle_subscription_webhook` (line 111-116):

```python
track_event(
    user=user,
    event_name=braze_event_name,
    alias_name=email,
    properties=formatted_subscription_data,
)
# Return value ignored!
logger.info(f"Successfully processed {braze_event_name} ...")  # logged as success
```

The caller logs "Successfully processed" and returns True even if `track_event` returned None (Braze call failed). No email is sent, but the system believes everything worked.

**Specific triggers for this failure:**
- `BRAZE_API_KEY` not set → `BrazeAPIClient.__init__` raises `Exception("Missing Braze API key")` — caught by `track_event`
- `BRAZE_API_URL` not set or wrong → HTTP connection failure after 3 retries
- Braze API rate limit (HTTP 429) — retried 3x but may still fail
- Braze API returns a non-2xx status — `make_request` raises `HTTPRequestError` from `response.raise_for_status()`

#### Failure Path 4: send_transactional_email() swallows SMTP exceptions

**File:** `/Users/albertgwo/Work/evvy/backend/transactional_email/utils.py`, lines 33-42

```python
try:
    send_mail(subject, body, from_address, to_addresses, fail_silently=False)
except Exception as e:
    print(f"failed to send email with subject {subject}: {str(e)}")
    # No raise! Uses print(), not logger.error(). No re-raise.
```

Although this path is not directly in the subscription order flow (subscription emails use Braze, not Mandrill/SMTP directly), if any code calls `send_transactional_email`, failures are only printed to stdout (not structured logging), never re-raised, and never tracked.

### Summary of Most Likely Failure Cause

The most probable cause for "order processed successfully, no confirmation email received" is **Failure Path 1** or **Failure Path 3**:

**Failure Path 1 (most likely):** The user's ReCharge account email doesn't match the evvy account email. The `User.objects.filter(email=email).first()` at `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py:90` returns None. The webhook handler returns False but the 200 response to ReCharge prevents any retry. Check: compare `recharge_webhook` logs for `"User not found for subscription webhook"` errors against the affected user's email.

**Failure Path 3 (also likely):** The Braze API call fails after 3 retries (network issue, rate limit, misconfiguration). The failure is logged at the `logger.error` level in `analytics/service.py:85` but the system logs "Successfully processed" immediately after. Check: look for `"Error tracking event subscription_created"` in logs around the time of the order.

### Key Files

| File | Purpose | Silent Failure |
|------|---------|----------------|
| `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py:369-445` | ReCharge webhook router — always returns 200 | Yes: ReCharge never retries |
| `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py:66-124` | `handle_subscription_webhook` — email trigger | Yes: user not found, all exceptions |
| `/Users/albertgwo/Work/evvy/backend/analytics/service.py:51-86` | `track_event` — Braze event dispatch | Yes: all exceptions swallowed |
| `/Users/albertgwo/Work/evvy/backend/analytics/braze/braze.py:269-275` | `_make_request` — Braze HTTP call (3 retries) | No: raises after retries |
| `/Users/albertgwo/Work/evvy/backend/transactional_email/utils.py:20-42` | `send_transactional_email` — SMTP email | Yes: prints, doesn't raise |
| `/Users/albertgwo/Work/evvy/backend/subscriptions/recharge.py:93-101` | `send_account_email` — dead code, never called | N/A |
