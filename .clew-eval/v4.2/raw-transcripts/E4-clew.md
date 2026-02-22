# E4: Subscription Order Confirmation Email — Failure Path Investigation

## Summary

The subscription order confirmation email is delivered via Braze. When a subscription order is processed, the code fires a `SUBSCRIPTION_CREATED` Braze event (from the Recharge `subscription/created` webhook) and/or a `VAGINAL_TEST_PURCHASE` event (from the Shopify `orders/create` webhook). Braze then triggers the confirmation email campaign in response to these events.

There are **four distinct silent failure paths** where the email can fail to send without surfacing as an error to the customer.

---

## Pipeline Overview

```
Shopify order paid
       |
       v
POST /webhooks/shopify/  (shopify_webhook_view)
       |
       v (topic == "orders/create")
process_shopify_order()  [backend/ecomm/utils.py:204]
       |
       v
_process_shopify_order_impl()  [backend/ecomm/utils.py:238]
       |
       +-- track_event(VAGINAL_TEST_PURCHASE)  [line 718]  <-- direct, synchronous
       |
       +-- send_any_paid_event.delay()  [line 744]  <-- Celery async (FullStory only, not email)
       |
       +-- [if subscription order] ReCharge fires subscription/created webhook separately:

POST /webhooks/recharge/  (recharge_webhook_view)
       |
       v (topic == "subscription/created")
handle_subscription_webhook(payload, send_braze_event=True, topic)
       |
       +-- SubscriptionService.get_all_subscriptions_with_cache()  [Recharge API call]
       |
       +-- update_user_profile(ACTIVE_SUBSCRIPTIONS)  [Braze profile update]
       |
       +-- track_event(SUBSCRIPTION_CREATED)  [backend/analytics/service.py:51]
              |
              v
       braze_track_user_event()  [backend/analytics/braze/utils.py:74]
              |
              v
       BrazeAPIClient.track_user()  [backend/analytics/braze/braze.py:150]
              |
              v
       BrazeAPIClient._make_request()  [POST /users/track]
```

---

## Failure Path 1: `track_event` Swallows All Exceptions Silently

**File:** `/Users/albertgwo/Work/evvy/backend/analytics/service.py`, lines 65–86

```python
def track_event(
    user: User | None = None,
    event_name: str = None,
    ...
) -> Dict[str, Any] | None:
    try:
        ...
        if ANALYTICS_PROVIDER == "braze":
            return braze_track_user_event(...)
        else:
            logger.warning(f"Unsupported analytics provider: {ANALYTICS_PROVIDER}")
            return None

    except Exception as e:
        user_identifier = user.uuid if user else alias_name
        logger.error(f"Error tracking event {event_name} for {user_identifier}: {e}")
        return None  # <-- silently returns None; caller never knows event failed
```

**Problem:** Any failure (Braze API down, network timeout, invalid payload, wrong API key) is caught, logged at `logger.error`, and returns `None`. The caller — `handle_subscription_webhook` — does not check the return value of `track_event`. The webhook handler returns `True` (success) even though the Braze event was never delivered.

**Result:** The `subscription/created` Braze event is silently dropped. No retry. No alert to the user. Braze never receives the event that would trigger the confirmation email.

---

## Failure Path 2: Uninitialized `send_braze_event` Variable in Webhook View

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py`, lines 412–433

```python
success = False
if topic == TOPIC_CHARGE_UPCOMING:
    success = handle_charge_upcoming_webhook(payload)
elif topic in [
    TOPIC_SUBSCRIPTION_ACTIVATED,
    TOPIC_SUBSCRIPTION_CANCELLED,
    TOPIC_SUBSCRIPTION_CREATED,
    TOPIC_SUBSCRIPTION_DELETED,    # <-- outer group includes these topics
    TOPIC_SUBSCRIPTION_SKIPPED,
    TOPIC_SUBSCRIPTION_UPDATED,
    TOPIC_SUBSCRIPTION_UNSKIPPED,
    TOPIC_SUBSCRIPTION_SWAPPED,
    TOPIC_SUBSCRIPTION_PAUSED,
]:
    if topic in [
        TOPIC_SUBSCRIPTION_CREATED,
        TOPIC_SUBSCRIPTION_CANCELLED,
        TOPIC_SUBSCRIPTION_ACTIVATED,
        TOPIC_SUBSCRIPTION_SWAPPED,
    ]:
        send_braze_event = True   # <-- only assigned in this inner branch
    success = handle_subscription_webhook(payload, send_braze_event, topic)  # <-- NameError risk
```

**Problem:** `send_braze_event` is only assigned inside the inner `if` block. If the topic matches the outer `elif` but NOT the inner `if` (e.g., `TOPIC_SUBSCRIPTION_DELETED`, `TOPIC_SUBSCRIPTION_SKIPPED`, `TOPIC_SUBSCRIPTION_UPDATED`, `TOPIC_SUBSCRIPTION_UNSKIPPED`, `TOPIC_SUBSCRIPTION_PAUSED`), the code raises a `NameError: name 'send_braze_event' is not defined`. This exception is not caught in the view, so the webhook fails with a 500 and Recharge may retry — but for `subscription/created` this code path is correct. The bug is that if there's any prior invocation in the same request context that set `send_braze_event` in a prior branch (unlikely in production, but possible under certain test or code-path scenarios), the value is stale.

**More practically:** The function signature `handle_subscription_webhook(payload, send_braze_event=True, topic=None)` has a default of `True`, but the call in the view passes `send_braze_event` as a positional argument. For the `subscription/created` topic this is `True` and correct. The risk here is that any webhook topic not in the inner `if` (deleted, skipped, etc.) will cause a `NameError` that goes unhandled, potentially causing the ReCharge webhook system to retry and reach a bad state.

---

## Failure Path 3: Recharge API Failure in `get_all_subscriptions_with_cache` Blocks Email Dispatch

**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/subscription_service.py`, lines 120–142

```python
def get_all_subscriptions_with_cache(self) -> SubscriptionsResponse:
    cache_key = self._get_cache_key("all_subscriptions")

    if self.force_refresh:  # <-- always True in webhook handler
        logger.info(f"Force refreshing subscriptions for user {self.user.id}")
        try:
            subscriptions = self.get_all_subscriptions()
            ...
            return subscriptions
        except Exception as e:
            logger.error(f"Failed to refresh subscriptions for user {self.user.id}: {e}")
            cached_subscriptions = cache.get(cache_key)
            if cached_subscriptions:
                return cached_subscriptions
            return SubscriptionsResponse(subscriptions=[])  # <-- returns empty list on API failure
```

**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py`, lines 95–116

```python
subscription_service = SubscriptionService(user, force_refresh=True)
subscriptions_response = subscription_service.get_all_subscriptions_with_cache()

# Update active_subscriptions attribute with comma-separated SKUs
active_skus = [sub.sku for sub in subscriptions_response.subscriptions if sub.sku]
update_user_profile(
    user=user,
    alias_name=email,
    attributes={ACTIVE_SUBSCRIPTIONS: ",".join(active_skus) if active_skus else ""},
)
# ^ update_user_profile is called BEFORE track_event
```

**Problem:** If the Recharge API is unavailable when the `subscription/created` webhook is received, `get_all_subscriptions_with_cache` returns an empty `SubscriptionsResponse`. Then `update_user_profile` is called with an empty `ACTIVE_SUBSCRIPTIONS` string — this may itself fail (Braze API error), and `update_user_profile` similarly swallows exceptions (same pattern as `track_event` in `analytics/service.py:89-127`). Crucially, the code continues to call `track_event` regardless, so this is not a direct block — but it does mean the user's `active_subscriptions` attribute in Braze will be cleared to `""`, which could prevent the Braze email campaign from targeting the user correctly if the campaign uses that attribute as a filter.

---

## Failure Path 4: `BrazeAPIClient` Raises on Missing API Key

**File:** `/Users/albertgwo/Work/evvy/backend/analytics/braze/braze.py`, lines 30–35

```python
def __init__(self):
    if not settings.BRAZE_API_KEY:
        raise Exception("Missing Braze API key")
```

**File:** `/Users/albertgwo/Work/evvy/backend/analytics/braze/utils.py`, lines 74–100

```python
def braze_track_user_event(...) -> Dict[str, Any]:
    ...
    client = BrazeAPIClient()   # <-- raises Exception if BRAZE_API_KEY missing
    return client.track_user(...)
```

**Problem:** If `BRAZE_API_KEY` is not set (misconfigured environment, key rotated/expired), `BrazeAPIClient()` raises a plain `Exception`. This propagates up through `braze_track_user_event` (no try/except there) and is caught by `track_event`'s bare `except Exception` at `analytics/service.py:83`, which logs the error and returns `None`. The email is silently dropped.

---

## Most Likely Failure Path for the Reported Bug

The most likely scenario for "order processed successfully but no confirmation email received" is **Failure Path 1** combined with a transient Braze API failure:

1. Shopify fires `orders/create` webhook → `_process_shopify_order_impl` runs, order is created in DB, `track_event(VAGINAL_TEST_PURCHASE)` is called synchronously at line 718.
2. If `track_event` fails (e.g., Braze API timeout, 4xx/5xx response from `_make_request`), the exception is caught at `analytics/service.py:83`, logged as `logger.error`, and `None` is returned. The order processing continues normally.
3. Separately, Recharge fires `subscription/created` webhook → `handle_subscription_webhook` is called → `track_event(SUBSCRIPTION_CREATED)` is called. Same silent failure applies.
4. The customer's DB record is correct (order created, subscription linked), but Braze never received the event, so the confirmation email campaign never fired.

There is **no retry mechanism** for failed `track_event` calls. Once the event is dropped, it is gone unless manually replayed.

---

## Key Files

| File | Relevant Lines | Issue |
|------|---------------|-------|
| `/Users/albertgwo/Work/evvy/backend/analytics/service.py` | 65–86 | `track_event` swallows all exceptions, returns `None` silently |
| `/Users/albertgwo/Work/evvy/backend/analytics/service.py` | 107–127 | `update_user_profile` same pattern — clears `active_subscriptions` on failure |
| `/Users/albertgwo/Work/evvy/backend/subscriptions/service.py` | 107–124 | `handle_subscription_webhook` does not check return value of `track_event` |
| `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` | 412–433 | `send_braze_event` uninitialized before use (potential `NameError` for non-email topics) |
| `/Users/albertgwo/Work/evvy/backend/subscriptions/subscription_service.py` | 129–142 | Recharge API failure clears `active_subscriptions` in Braze |
| `/Users/albertgwo/Work/evvy/backend/analytics/braze/braze.py` | 30–35, 270–275 | `BrazeAPIClient` raises on missing key; `_make_request` raises `HTTPRequestError` on 4xx/5xx |
| `/Users/albertgwo/Work/evvy/backend/analytics/braze/utils.py` | 74–100 | No error handling in `braze_track_user_event` |
| `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` | 717–727 | `track_event(VAGINAL_TEST_PURCHASE)` called synchronously, no return value check |
