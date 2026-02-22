# E4 — Agent Alpha

## Investigation Results: Subscription Order Confirmation Email Failure Paths

### System Architecture Overview

Confirmation emails for subscription orders are NOT sent via Django's transactional email system. They flow through **Braze** (the marketing/transactional email platform), triggered by analytics events sent from the backend. There are two relevant entry points depending on whether this is a new subscription purchase or a recurring charge:

1. **New subscription order**: Shopify fires `orders/paid` webhook → `_process_shopify_order_impl` → `track_event(VAGINAL_TEST_PURCHASE)` → Braze campaign triggers email.
2. **Recurring subscription charge**: Recharge fires `subscription/created` webhook → `handle_subscription_webhook` → `track_event(SUBSCRIPTION_CREATED)` → Braze campaign triggers email.

---

### Failure Path 1: Missing `charge/paid` Webhook Topic

**File:** `/Users/albertgwo/Work/evvy/backend/subscriptions/constants.py`

```python
# ReCharge webhook topics
TOPIC_CHARGE_UPCOMING = "charge/upcoming"
TOPIC_SUBSCRIPTION_CREATED = "subscription/created"
TOPIC_SUBSCRIPTION_CANCELLED = "subscription/cancelled"
# ... NO "charge/paid" topic defined
```

**File:** `/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py` (lines 413–438)

```python
if topic == TOPIC_CHARGE_UPCOMING:
    success = handle_charge_upcoming_webhook(payload)
elif topic in [
    TOPIC_SUBSCRIPTION_ACTIVATED,
    TOPIC_SUBSCRIPTION_CANCELLED,
    TOPIC_SUBSCRIPTION_CREATED,
    TOPIC_SUBSCRIPTION_DELETED,
    TOPIC_SUBSCRIPTION_SKIPPED,
    TOPIC_SUBSCRIPTION_UPDATED,
    TOPIC_SUBSCRIPTION_UNSKIPPED,
    TOPIC_SUBSCRIPTION_SWAPPED,
    TOPIC_SUBSCRIPTION_PAUSED,
]:
    ...
else:
    logger.warning(f"Unsupported ReCharge webhook topic: {topic}")
    return HttpResponse("Unsupported webhook topic", status=200)  # SILENT 200
```

The Recharge `charge/paid` webhook topic (which fires when a recurring subscription charge succeeds) is **not handled**. The webhook is received, verified, and then silently acknowledged with `status=200` with only a warning log. No email is dispatched for recurring subscription charges processed through Recharge.

---

### Failure Path 2: Silent Exception Swallowing in `track_event`

**File:** `/Users/albertgwo/Work/evvy/backend/analytics/service.py` (lines 65–86)

```python
def track_event(user=None, event_name=None, properties=None, alias_name=None, alias_label="evvy_email"):
    try:
        ...
        if ANALYTICS_PROVIDER == "braze":
            return braze_track_user_event(...)
    except Exception as e:
        user_identifier = user.uuid if user else alias_name
        logger.error(f"Error tracking event {event_name} for {user_identifier}: {e}")
        return None  # SILENTLY RETURNS None — no re-raise, no task retry
```

Any Braze API failure (network error, invalid API key, rate limit, malformed payload) causes `track_event` to return `None`. The order processing pipeline continues uninterrupted — the Shopify webhook returns `200 OK`, the order is marked processed, but no email is ever dispatched. The retry logic in `BrazeAPIClient._make_request` (`@retry(stop_max_attempt_number=3)`) exhausts before the outer exception is caught here.

---

### Failure Path 3: `order.user` is `None` AND `order.email` is `None`

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (lines 717–727)

```python
if has_vaginal_test_line_item:
    track_event(
        user=order.user,
        alias_name=order.user.email if order.user else order.email,
        event_name=BrazeEventName.VAGINAL_TEST_PURCHASE,
        properties={
            "orderNumber": order.order_number,
            "orderSku": order.sku,
            "isSubscription": order.is_subscription_order,
        },
    )
```

The `alias_name` falls back to `order.email` (the raw email from the Shopify payload). If the Shopify payload's `email` field is missing or empty AND `order.user` is `None` (user lookup failed), both `user` and `alias_name` will be `None`. This hits the guard in `track_event`:

```python
if not user and not alias_name:
    raise ValueError("Either user or alias_name must be provided")
```

This raises immediately, is caught by the outer `except Exception`, logged as an error, and returns `None` — silently dropping the email trigger.

**User lookup code** at `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (line 2012–2023):

```python
def _update_order_user(order: Order, email: str):
    if not order.user_id:
        email_to_search = order.evvy_account_email or email
        if email_to_search:
            user = User.objects.filter(email__iexact=email_to_search.strip().lower()).first()
            if user:
                order.user = user
                order.save()
    return order
```

If the user registered with a different email address than the one on the subscription (e.g., changed email in Recharge but not in the Evvy account), `filter().first()` returns `None`, and `order.user` stays `None`.

---

### Failure Path 4: `send_any_paid_event` Gated on `order.user`

**File:** `/Users/albertgwo/Work/evvy/backend/ecomm/utils.py` (line 742–744)

```python
if not is_order_cancellation and order.user and order.status != Order.STATUS_CANCELLED:
    send_any_paid_event.delay(order.order_number)
```

The `any_paid` Braze event (which may trigger transactional email flows) is only dispatched when `order.user` is non-null. If user resolution failed (email mismatch), this event is silently skipped. Furthermore, looking at the `send_any_paid_event` implementation at line 827–833:

```python
send_custom_analytics_event_to_destinations(
    order.user,
    "Any Paid",
    event_properties,
    use_recent_session_fullstory=False,
    destinations=[FULLSTORY],  # Only Fullstory! Not Braze.
)
```

This event goes only to Fullstory, not Braze — so even when it fires, it does not trigger a Braze email campaign.

---

### Failure Path 5: Braze Profile Not Ready When Event Fires

**File:** `/Users/albertgwo/Work/evvy/backend/analytics/braze/utils.py` (lines 25–61)

There is a `ensure_braze_profile_ready()` function that documents the race condition:

```python
def ensure_braze_profile_ready(user: User) -> bool:
    """
    Ensures user's Braze profile exists and any orphan profiles are merged.
    Call this BEFORE firing critical campaign-triggering events.

    This prevents race conditions where:
    1. Event fires before profile exists in Braze
    2. Event fires while profile is mid-merge
    """
```

This function exists but is **not called** before `track_event` in the subscription order processing path (`_process_shopify_order_impl`). If the Braze profile hasn't been created or merged yet when `track_event(VAGINAL_TEST_PURCHASE)` fires, Braze receives the event against an unknown or orphaned profile and cannot associate it with the correct user to trigger an email campaign. No error is raised.

---

### Summary of Silent Failure Points

| Path | File | Lines | Description |
|------|------|-------|-------------|
| Missing `charge/paid` Recharge webhook | `backend/api/v1/views/webhooks.py` | 413–438 | Recurring subscription charges silently acknowledged with no email dispatch |
| `track_event` swallows all exceptions | `backend/analytics/service.py` | 83–86 | Braze API errors return `None`, order marked complete, no retry |
| `order.user=None` + `order.email=None` | `backend/ecomm/utils.py` | 717–727 | Email+user mismatch causes `alias_name=None`, ValueError swallowed |
| `send_any_paid_event` user gate | `backend/ecomm/utils.py` | 742–744 | Event skipped entirely when user lookup fails |
| Braze profile race condition | `backend/analytics/braze/utils.py` | 25–61 | Event fires before Braze profile is ready; `ensure_braze_profile_ready` not called in this path |

The most likely failure for a subscription order that "processed successfully" (order exists in the DB, payment succeeded) but user received no email is either **Path 1** (recurring charge, `charge/paid` not handled) or **Path 3** (email mismatch between Recharge and Evvy account causing `order.user=None`).
