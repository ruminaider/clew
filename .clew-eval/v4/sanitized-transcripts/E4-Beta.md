# E4 Exploration Log

## Search 1: Top-level directory structure
Listed `/Users/albertgwo/Work/evvy` and `/Users/albertgwo/Work/evvy/backend`. Found that the backend contains:
- `subscriptions/` — subscription domain logic
- `transactional_email/` — email sending infrastructure
- `analytics/` — Braze event tracking (which triggers emails via Braze campaigns)
- `ecomm/` — order processing
- `api/` — webhook entry points

Key modules for this investigation: `subscriptions/service.py`, `transactional_email/utils.py`, `transactional_email/mandrill.py`, `transactional_email/constants.py`, `analytics/service.py`, `analytics/braze/braze.py`, `analytics/braze/utils.py`, `ecomm/utils.py`, `api/v1/views/webhooks.py`.

## Search 2: Subscription-related email sending
Searched `subscriptions/` for patterns like `send.*email`, `confirmation.*email`. Found only `send_account_email` in `recharge.py` which is a Recharge-platform-native email (not a confirmation email). No direct Mandrill email send for subscription order confirmation found in this module.

## Search 3: Order completion and subscription confirmation patterns
search("pattern")*complete`, `charge.*success`, `order_paid`, `payment.*success`. Found:
- `ecomm/utils.py:628` — `payment_status="success"` logged when Shopify webhook fires
- `ecomm/utils.py:744` — `send_any_paid_event.delay(order.order_number)` dispatched for all non-cancelled orders with a user
- `analytics/tasks.py:806` — `send_any_paid_event` task implementation (sends FullStory analytics event only, not an email)
- Subscription-specific: Recharge fires `subscription/created` webhook → `handle_subscription_webhook` → `track_event(..., BrazeEventName.SUBSCRIPTION_CREATED, ...)` — this Braze event is what triggers the confirmation email campaign in Braze

## Search 4: Subscription webhook handler (full read)
Read `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` in full. The complete flow for `subscription/created`:
1. `handle_subscription_webhook(payload, send_braze_event=True, topic="subscription/created")`
2. Extracts `subscription_data` from payload
3. Looks up user by email — if not found, logs error and returns `False` (silent to user)
4. Updates user's `active_subscriptions` profile attribute in Braze via `update_user_profile`
5. Since `send_braze_event=True`, calls `_get_braze_event_for_subscription_topic` → returns `BrazeEventName.SUBSCRIPTION_CREATED`
6. Calls `track_event(user, BrazeEventName.SUBSCRIPTION_CREATED, email, properties)` → if Braze event fires successfully, Braze campaign engine sends the confirmation email
7. Entire function is wrapped in `except Exception as e: logger.exception(...)` returning `False` — exceptions are caught and swallowed

## Search 5: Braze event tracking chain
Read `analytics/service.py` — `track_event()` is the central function. It wraps everything in a `try/except Exception` and on failure logs the error and **returns None** without re-raising. This means any failure in the chain (network error, Braze API error, misconfiguration) will be silently swallowed — the calling code gets `None` back with no exception propagated.

## Search 6: Braze API client and HTTP layer
Read `analytics/braze/braze.py` — `BrazeAPIClient.track_user()` builds the payload and calls `_make_request()`. The `_make_request()` method:
- Has `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` decorator
- Calls `make_request()` from `utils/requests.py`

Read `utils/requests.py` — `make_request()` does raise `HTTPRequestError` on non-2xx responses, which means the retry decorator will retry 3 times. After 3 failures, the exception propagates up to `track_event()` in `analytics/service.py` where it is caught and swallowed (returns `None`).

Key: `BrazeAPIClient.__init__()` raises `Exception("Missing Braze API key")` if `settings.BRAZE_API_KEY` is falsy. This exception would propagate up through `braze_track_user_event` → `track_event` where it is caught and suppressed.

## Search 7: Mandrill / transactional_email layer (for direct emails)
Read `transactional_email/utils.py` — `send_templated_email()`. Key observations:
- Line 57-59: **`DISABLED_EMAIL_FLOWS` check** — if a template is listed in this dict with value `True`, the function immediately returns `(True, "Email flow disabled")` — appearing successful to the caller but never sending anything.
- Line 72-78: Calls `send_mandrill_email()` from `transactional_email/mandrill.py`

Read `transactional_email/mandrill.py` — `send_mandrill_email()`:
- Line 36-38: On `ApiClientError`, prints the error and **returns `(False, error.text)`** — does NOT raise an exception
- The caller `send_templated_email` checks `if success:` and if False, only prints a message — no exception raised

Read `transactional_email/constants.py` — `DISABLED_EMAIL_FLOWS` dict. Many email templates are currently disabled. There is no subscription order confirmation template visible in this file's template list (no `TEMPLATE_SUBSCRIPTION_CONFIRMATION` constant), which suggests the subscription confirmation email is entirely Braze-triggered rather than Mandrill/transactional_email.

## Search 8: Recharge webhook view (entry point)
Read `api/v1/views/webhooks.py` lines 367-445. The `recharge_webhook_view` function:
- Verifies HMAC signature — returns 403 if invalid
- Parses JSON — returns 400 if invalid
- For `subscription/created`, sets `send_braze_event = True` then calls `handle_subscription_webhook(payload, send_braze_event, topic)`
- Always returns HTTP 200 regardless of whether email was sent
- If `success` is False (returned by `handle_subscription_webhook`), only logs an error — no retry, no alert

## Search 9: Shopify order webhook (for subscription orders via Shopify)
Read `api/v1/views/webhooks.py` lines 82-145. For `orders/create`, calls `process_shopify_order()`. Subscription orders placed through Shopify (using Recharge's Shopify integration) fire both a Shopify `orders/create` webhook AND a Recharge `subscription/created` webhook. The Shopify path handles fulfillment; the Recharge webhook handles the subscription-specific Braze event.

## Final Answer

### The Subscription Order Confirmation Email Pipeline

The subscription order confirmation email in this codebase is **not sent via the `transactional_email` module** (Mandrill). Instead, it relies entirely on Braze's event-triggered campaign system. The flow is:

**Entry point:** Recharge fires a `subscription/created` webhook to `/webhooks/recharge/`

**Code path:**
```
api/v1/views/webhooks.py: recharge_webhook_view()
  → subscriptions/service.py: handle_subscription_webhook(payload, send_braze_event=True, topic="subscription/created")
    → analytics/service.py: track_event(user, BrazeEventName.SUBSCRIPTION_CREATED, email, properties)
      → analytics/braze/utils.py: braze_track_user_event(...)
        → analytics/braze/braze.py: BrazeAPIClient.track_user(...)
          → POST https://rest.iad-01.braze.com/users/track (Braze API)
```

If Braze receives the `subscription_created` event, its campaign engine sends the confirmation email to the user. If the event is never delivered to Braze, no email is sent.

---

### Failure Paths Where the Email Fails Silently

**Failure Path 1: User not found in the database (silent return False)**

File: `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py`, lines 89-93

```python
email = formatted_subscription_data.get("email")
user = User.objects.filter(email=email).first()
if not user:
    logger.error(f"User not found for subscription webhook: {email}")
    return False
```

If the email in the Recharge webhook payload does not match any user in the Django database (e.g., the user registered with a different email, or the Recharge account was created before the user registered), the function returns `False` immediately. No email is sent. The Recharge webhook endpoint at `api/v1/views/webhooks.py` line 440-443 receives this `False` result, logs an error, and still returns HTTP 200 to Recharge. **Recharge will not retry because it received a 200.** The failure is permanent and silent to the user.

**Failure Path 2: `track_event` swallows all exceptions**

File: `/Users/albertgwo/Work/evvy/backend/analytics/service.py`, lines 65-86

```python
try:
    ...
    return braze_track_user_event(...)
except Exception as e:
    user_identifier = user.uuid if user else alias_name
    logger.error(f"Error tracking event {event_name} for {user_identifier}: {e}")
    return None
```

Any exception in the Braze call chain — network timeout, Braze API error, missing API key, rate limiting — is caught here and the function returns `None`. The caller (`handle_subscription_webhook`) checks nothing about the return value of `track_event`. The event is lost with only a log entry.

**Failure Path 3: Braze API key missing — exception caught and swallowed**

File: `/Users/albertgwo/Work/evvy/backend/analytics/braze/braze.py`, lines 34-35

```python
if not settings.BRAZE_API_KEY:
    raise Exception("Missing Braze API key")
```

This exception propagates up to `track_event` where Failure Path 2 catches it. If `BRAZE_API_KEY` is misconfigured or missing in the environment, every subscription confirmation email silently fails. The service returns 200 to Recharge so no retry occurs.

**Failure Path 4: Braze API call fails after 3 retries**

File: `/Users/albertgwo/Work/evvy/backend/analytics/braze/braze.py`, lines 269-275

```python
@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)
def _make_request(self, method: str, url: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    return make_request(method, url, json=data, headers=self.headers)
```

`make_request` in `utils/requests.py` raises `HTTPRequestError` on non-2xx responses. The retry decorator tries 3 times. After the third failure, the exception propagates up to `track_event`'s `except Exception` handler (Failure Path 2) and returns `None`. The Braze API docs indicate common failure modes: invalid API key (401), rate limiting (429), invalid event data (400). All of these are caught and swallowed.

**Failure Path 5: `send_braze_event` flag never set to True**

File: `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`, lines 412-433

```python
success = False
if topic == TOPIC_CHARGE_UPCOMING:
    success = handle_charge_upcoming_webhook(payload)
elif topic in [...]:
    if topic in [
        TOPIC_SUBSCRIPTION_CREATED,
        TOPIC_SUBSCRIPTION_CANCELLED,
        TOPIC_SUBSCRIPTION_ACTIVATED,
        TOPIC_SUBSCRIPTION_SWAPPED,
    ]:
        send_braze_event = True
    success = handle_subscription_webhook(payload, send_braze_event, topic)
```

Note that `send_braze_event` is never initialized before the `if topic in [...]` block — it is only set to `True` inside the inner conditional. If the topic is `TOPIC_SUBSCRIPTION_CREATED` (which it is for a new subscription), this works correctly. However, `handle_subscription_webhook` has a default parameter `send_braze_event: bool = True`, so even if the flag had defaulted to False due to a logic change, there is ambiguity in precedence. (Currently not a bug for the created case, but a code smell.)

**Failure Path 6: `_get_braze_event_for_subscription_topic` returns None**

File: `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py`, lines 107-119

```python
if send_braze_event:
    braze_event_name = _get_braze_event_for_subscription_topic(topic, subscription_data)
    if braze_event_name:
        track_event(...)
```

If `_get_braze_event_for_subscription_topic` returns `None`, `track_event` is never called and no email is sent. Looking at the function (lines 127-153), for `TOPIC_SUBSCRIPTION_CREATED` it returns `BrazeEventName.SUBSCRIPTION_CREATED` — this path works. But the fallback at line 150-153 uses `status` field: if the status is not `"CANCELLED"`, it returns `SUBSCRIPTION_CREATED`. If the webhook payload has an unexpected status value and the topic doesn't match any known constant, this fallback fires and may still produce the right result. This is not a current active failure, but a future risk if topic constants drift.

---

### Most Likely Cause for the Reported Issue

Given that the order was **processed successfully**, the Shopify/Recharge payment side is fine. The most likely failure points (in order of probability) are:

1. **The Braze API call failed silently** (Failure Path 4) — network issue, Braze rate limit, or invalid API key. The exception is swallowed in `analytics/service.py:track_event()` with only a `logger.error()`. Since the Recharge webhook already got a 200 response, there is no retry.

2. **User email mismatch** (Failure Path 1) — The email in the Recharge subscription webhook doesn't match the `User` record in the database. The function logs `"User not found for subscription webhook: {email}"` and returns `False`. Check the logs for this specific error message around the time of the order.

3. **Braze received the event but the campaign was not triggered** — This would be a Braze configuration issue (campaign inactive, segment misconfigured, user filtered out) rather than a code issue. The code's responsibility ends when it successfully calls `POST /users/track` to Braze.

### Where to Look in Logs

- Look for `logger.error(f"User not found for subscription webhook: {email}")` in the `evvy.subscriptions.webhooks` logger
- Look for `logger.error(f"Error tracking event subscription_created for {user_identifier}: {e}")` in the `evvy.analytics.service` logger
- Look for `logger.error(f"HTTP {status_code} error from POST {braze_url}")` in the `evvy.requests` logger
- Look for `"Failed to process ReCharge webhook"` in the webhook logs
