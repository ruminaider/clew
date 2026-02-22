# E4 Ground Truth Checklist: Email Confirmation Debugging

Scenario: Subscription order processed successfully but no confirmation email received.

## E4 Ground Truth Checklist

- [ ] Artifact 1: `shopify_webhook_view` (`/Users/albertgwo/Work/evvy/backend/api/v1/views/webhooks.py:82`) — receives Shopify `orders/create` webhook and calls `process_shopify_order()`; the entry point for all order processing including subscription refill orders
- [ ] Artifact 2: `_process_shopify_order_impl` (`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:238`) — core order processing function; detects `is_recurring_subscription_order` flag via `line_item_is_recurring_order_item`; routes subscription refill orders to `process_shopify_order_for_treatment_refill()`
- [ ] Artifact 3: `process_shopify_order_for_treatment_refill` (`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:2089`) — handles prescription refill / subscription orders; resolves user via multiple fallback strategies; dispatches `send_prescription_refill_request.delay()` as the fulfillment step
- [ ] Artifact 4: `send_prescription_refill_request` (`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py:157`) — Celery task; validates state restrictions, prescription refill availability, then dispatches `send_fill_request_to_precision()`; also fires `send_prescription_refills_paid_event.delay()`
- [ ] Artifact 5: `send_mandrill_email` (`/Users/albertgwo/Work/evvy/backend/transactional_email/mandrill.py:7`) — the actual email delivery function via Mailchimp Transactional (Mandrill) API; returns `(True, None)` on success or `(False, error.text)` on `ApiClientError`
- [ ] Artifact 6: `send_templated_email` (`/Users/albertgwo/Work/evvy/backend/transactional_email/utils.py:45`) — wrapper that checks `DISABLED_EMAIL_FLOWS`, calls `send_mandrill_email`, and records sent emails in `EmailSent` model
- [ ] Artifact 7: `DISABLED_EMAIL_FLOWS` (`/Users/albertgwo/Work/evvy/backend/transactional_email/constants.py:132`) — dict mapping template IDs to `True` to disable flows; if a template is set to `True` here, `send_templated_email` returns `(True, "Email flow disabled")` silently without sending
- [ ] Artifact 8: `braze_track_user_event` / `track_event` (`/Users/albertgwo/Work/evvy/backend/analytics/braze/utils.py:74`, `/Users/albertgwo/Work/evvy/backend/analytics/service.py:51`) — fires `BrazeEventName.VAGINAL_TEST_PURCHASE` (for test orders, `ecomm/utils.py:721`) and `BrazeEventName.TREATMENTS_SHIPPED` (via precision webhook, `shipping/precision/utils.py:492`); Braze campaigns consume these events and send confirmation emails
- [ ] Artifact 9: `process_precision_shipped_webhook` (`/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py:411`) — handles pharmacy shipping confirmation; triggers `track_event(BrazeEventName.TREATMENTS_SHIPPED)` which is the main confirmation signal to Braze for treatment shipments; also triggers `send_treatments_shipped.delay()` (Mandrill path — but this task is NEVER CALLED in practice, no `.delay()` invocations exist)
- [ ] Artifact 10: `send_treatments_shipped` (`/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py:493`) — Mandrill-based "treatment-shipped" email task; defined but has NO callers — `send_treatments_shipped.delay()` is never invoked anywhere in the codebase; the shipped email relies entirely on Braze

## Email Pipeline

```
Shopify orders/create webhook
  → shopify_webhook_view() [api/v1/views/webhooks.py:82]
  → process_shopify_order() [ecomm/utils.py:204]          (wrapper with error logging)
  → _process_shopify_order_impl() [ecomm/utils.py:238]    (detects is_recurring_subscription_order)
  → process_shopify_order_for_treatment_refill() [ecomm/utils.py:2089]
  → send_prescription_refill_request.delay() [ecomm/tasks.py:157]  (Celery async)
  → send_fill_request_to_precision() [shipping/precision/tasks.py]   (sends to pharmacy)
  → [Precision pharmacy ships order]
  → process_precision_shipped_webhook() [shipping/precision/utils.py:411]  (Precision webhook)
  → track_event(BrazeEventName.TREATMENTS_SHIPPED)  [analytics/service.py:51]
  → BrazeAPIClient.track_user() [analytics/braze/braze.py]  → Braze API
  → [Braze campaign fires confirmation email to user]

For test purchase orders (not subscription refills):
  → _process_shopify_order_impl() line 718
  → track_event(BrazeEventName.VAGINAL_TEST_PURCHASE)
  → Braze campaign fires order confirmation
```

## Silent Failure Points

1. **`DISABLED_EMAIL_FLOWS` flag set to `True`** (`/Users/albertgwo/Work/evvy/backend/transactional_email/constants.py:132-151`): `send_templated_email()` returns `(True, "Email flow disabled")` without sending and without logging an error; currently 17 templates are disabled this way. Any developer could add a template here and all emails for that flow silently stop.

2. **`send_treatments_shipped` task is never dispatched** (`/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py:493`): The Mandrill-based shipped email task exists but no code calls `.delay()` on it. The shipped confirmation relies entirely on the Braze event path via `process_precision_shipped_webhook()`. If the Precision webhook fails (network error, task failure), the Braze event never fires and no confirmation email is sent.

3. **User not attached to order → Braze event uses `alias_name` only** (`/Users/albertgwo/Work/evvy/backend/ecomm/utils.py:718-727`): The `VAGINAL_TEST_PURCHASE` event falls through to `alias_name=order.email`. If the user's Braze profile does not exist under that email alias (anonymous user who hasn't registered), the event is tracked but no campaign fires.

4. **`send_prescription_refill_request` returns early on invalid state or missing prescriptions** (`/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py:196-223`): If the shipping address is in an unsupported state (`invalid_state_code`) or if prescriptions have no remaining refills, the task logs an error and returns without dispatching to Precision — no shipment, no shipped webhook, no confirmation email. The error is recorded in `ConsultTask` but no email alert is sent to the customer.

5. **`process_precision_shipped_webhook` deduplication lock** (`/Users/albertgwo/Work/evvy/backend/shipping/precision/utils.py:396-408`): A 1-hour cache lock (`prescription_fill_shipped_{reference_id}`) prevents duplicate processing. If a webhook was received once (even if processing failed mid-way after setting the lock), a retry within 1 hour silently returns early without re-sending the Braze event.

6. **`send_templated_email` swallows Mandrill errors without re-raising** (`/Users/albertgwo/Work/evvy/backend/transactional_email/utils.py:72-78`): `send_mandrill_email` catches `ApiClientError` and returns `(False, error.text)`. `send_templated_email` logs the failure with `print()` (not `logger.error()`) and returns `(False, error)` — the calling task must check this return value. If the caller ignores it (e.g., `send_account_transfer_verification_email` at line 1232 does not check the return value), the failure is silent.

7. **`send_mandrill_email` itself has no retry logic** (`/Users/albertgwo/Work/evvy/backend/transactional_email/mandrill.py:7-38`): Unlike `void_share_a_sale_transaction` which uses `@retry(stop_max_attempt_number=3)`, Mandrill email sends have no automatic retry. A transient API error causes a permanent send failure.

8. **`send_transactional_email` (SMTP path) silently catches all exceptions** (`/Users/albertgwo/Work/evvy/backend/transactional_email/utils.py:33-42`): The `send_mail` Django SMTP path wraps in `try/except Exception` and calls `print()` — the failure is not logged to the Django logger or re-raised; monitoring systems (NewRelic) will not see this failure.

## Email Infrastructure Summary

- **Primary templated email provider**: Mandrill (Mailchimp Transactional) via `send_mandrill_email()`
- **Confirmation email triggers**: Braze event-based campaigns (not direct Mandrill calls) for order/shipping confirmations
- **Subscription order email path**: Precision pharmacy webhook → `track_event(TREATMENTS_SHIPPED)` → Braze campaign
- **Duplicate-send protection**: `EmailSent` model + `email_has_been_sent_with_context()` check in helper tasks
- **Template management**: Template IDs defined in `transactional_email/constants.py`; disabled via `DISABLED_EMAIL_FLOWS` dict
