# Exploration Transcript: Tool B — D1

**Task:** Find every place in the codebase where a Celery task is enqueued — called with `.delay()`, `.apply_async()`, or `send_task()`. For each call site, identify which task is being enqueued, what arguments are passed, and the business context (what triggers this task to be enqueued). Provide a complete inventory.

---

## Exploration Process

### Step 1: Discover Python files

The agent first verified the working directory contained Python files and identified the project structure.

**Result:** Confirmed the codebase under `backend/` with Python files across multiple Django apps.

---

### Step 2: Search for `.delay()` call sites

```
search("\.delay\(", path="backend/", type=py, files_with_matches)
```

**Result:** Found 43 files containing `.delay()` calls:

```
backend/shipping/tasks.py
backend/test_results/infection_state_service.py
backend/ecomm/utils.py
backend/ecomm/services/cart.py
backend/api/v1/views/webhooks.py
backend/api/v1/views/user_tests.py
backend/api/v1/views/register.py
backend/analytics/tasks.py
backend/test_results/admin.py
backend/shipping/utils.py
backend/shipping/precision/utils.py
backend/consults/wheel/tasks.py
backend/api/v1/views/provider_test_orders.py
backend/test_results/utils.py
backend/test_results/signals.py
backend/test_results/post_processing_utils.py
backend/test_results/lab_services/providers/junction/results_processor.py
backend/test_results/lab_services/orchestrator.py
backend/test_results/lab_services/lab_order_service.py
backend/scripts/backfill_unapproved_junction_submissions.py
backend/consults/wheel/utils_webhook.py
backend/consults/wheel/utils.py
backend/consults/utils.py
backend/consults/admin.py
backend/api/v1/views/consult.py
backend/test_results/utils_processing.py
backend/test_results/tests/microgen/test_tasks.py
backend/test_results/tasks.py
backend/test_results/microgen/tasks.py
backend/shipping/precision/tasks.py
backend/scripts/test_result_tag_scripts.py
backend/scripts/resend_lab_results_to_wheel.py
backend/scripts/reprocess_subscription_refill_orders.py
backend/ecomm/tasks.py
backend/consults/signals.py
backend/care/tasks.py
backend/care/signals.py
backend/app/management/commands/create_study_cohort_tests.py
backend/api/v1/views/my_plan.py
backend/api/v1/views/account.py
backend/accounts/admin_actions.py
backend/studies/admin.py
backend/api/v1/views/account_order_transfer_verification.py
```

---

### Step 3: Search for `.apply_async()` call sites

```
search("\.apply_async\(", path="backend/", type=py, files_with_matches)
```

**Result:** Found 4 files:

```
backend/consults/utils.py
backend/test_results/tests/microgen/test_tasks.py
backend/test_results/microgen/tasks.py
backend/care/signals.py
```

---

### Step 4: Search for `send_task()` call sites

```
search("send_task\(", path="backend/", type=py, files_with_matches)
```

**Result:** No files found.

---

### Step 5: Retrieve all `.delay()` calls with context

```
search("\.delay\(", path="backend/", type=py, output_mode=content, context=3 lines)
```

The full output (80KB) was persisted to a temporary file. The agent read it in two chunks (lines 1–500 and 500–863) to obtain all call sites with surrounding code context.

**Key call sites extracted from this output (representative sample):**

```python
# analytics/tasks.py:131
send_custom_analytics_event_to_fullstory_async.delay(
    user.id, event_name, event_properties, use_recent_session_fullstory
)

# analytics/tasks.py:158
send_custom_analytics_event_to_klaviyo_async.delay(payload)

# analytics/tasks.py:1154
send_estimated_treatment_started_event.delay(treatment_plan.id)

# analytics/tasks.py:1320
send_treatment_ended_event.delay(treatment_plan.id)

# analytics/tasks.py:1335
send_treatment_delivered_event.delay(treatment_plan.consult.uid)

# ecomm/services/cart.py:701
add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay(
    user.id, order.order_number
)

# ecomm/services/cart.py:705
send_account_transfer_verification_email.delay(user.id, order.email, order_number)

# ecomm/utils.py:416
void_share_a_sale_transaction.delay(order_number, order_date, note)

# ecomm/utils.py:691
send_ungated_rx_order_paid_event.delay(order.order_number)

# ecomm/utils.py:740
process_gift_cards.delay(order.id, payload)

# ecomm/utils.py:744
send_any_paid_event.delay(order.order_number)

# ecomm/utils.py:763
send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)

# ecomm/utils.py:1138
send_mpt_voucher_paid_event.delay(user.id)

# ecomm/utils.py:1236
create_unregistered_testkit_order_for_urine_test.delay(
    urine_test_ids=urine_test_ids,
    ecomm_order_id=order.id,
)

# ecomm/utils.py:1778
send_patient_ordered_provider_test_notification.delay(
    patient_email=email,
    order_sku=order.sku,
    order_provider_id=order.provider_id,
)

# ecomm/utils.py:1874
send_consult_paid_event.delay(consult.uid, order.provider_id)

# ecomm/utils.py:1990
send_additional_tests_paid_event.delay(None, order.provider_id)

# ecomm/utils.py:2009
send_additional_tests_paid_event.delay(test_kit.hash, order.provider_id)

# ecomm/utils.py:2198
send_prescription_refill_request.delay(order.id, prescription_fill.id)

# ecomm/utils.py:2705
send_provider_bulk_order_paid_notification.delay(
    ecomm_order_id=order.id,
    provider_email=provider_test_orders.first().provider.email,
    quantity=expected_count,
)
```

---

### Step 6: Retrieve all `.apply_async()` calls with context

```
search("\.apply_async\(", path="backend/", type=py, output_mode=content, context=5 lines)
```

**Result:**

```python
# test_results/microgen/tasks.py:317
summary_task.apply_async(countdown=cache_timeout)

# test_results/microgen/tasks.py:450
process_microgen_test_results.apply_async(args=[test_hash], countdown=delay_seconds)

# care/signals.py:121
create_or_reset_calendar_treatments.apply_async(
    args=(treatment_plan.id,), countdown=300
)

# care/signals.py:129
create_or_reset_calendar_treatments.apply_async(
    args=(treatment_plan.id,), countdown=300
)

# consults/utils.py:404
submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)

# consults/utils.py:406
submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)
```

---

### Step 7: Compile complete list with line numbers

```
search("\.delay\(|\.apply_async\(", path="backend/", type=py, output_mode=content)
```

This confirmed the complete deduplicated list of all call sites with file and line number. Notable entries confirmed:

```
backend/ecomm/services/cart.py:701
backend/ecomm/services/cart.py:705
backend/ecomm/services/cart.py:708
backend/ecomm/utils.py:416
backend/ecomm/utils.py:691
backend/ecomm/utils.py:740
backend/ecomm/utils.py:744
backend/ecomm/utils.py:763
backend/ecomm/utils.py:1138
backend/ecomm/utils.py:1236
backend/ecomm/utils.py:1778
backend/ecomm/utils.py:1874
backend/ecomm/utils.py:1990
backend/ecomm/utils.py:2009
backend/ecomm/utils.py:2198
backend/ecomm/utils.py:2705
backend/analytics/tasks.py:131
backend/analytics/tasks.py:158
backend/analytics/tasks.py:1154
backend/analytics/tasks.py:1320
backend/analytics/tasks.py:1335
backend/accounts/admin_actions.py:270
backend/care/tasks.py:125
backend/ecomm/tasks.py:229
backend/ecomm/tasks.py:460
backend/shipping/precision/utils.py:599
backend/shipping/precision/tasks.py:299
backend/studies/admin.py:66
backend/shipping/tasks.py:155
backend/shipping/tasks.py:768
backend/shipping/utils.py:231
backend/care/signals.py:86
backend/care/signals.py:121  (apply_async)
backend/care/signals.py:129  (apply_async)
backend/test_results/utils_processing.py:210
backend/test_results/signals.py:246
backend/test_results/signals.py:443
backend/test_results/signals.py:490
backend/test_results/infection_state_service.py:500
backend/test_results/microgen/tasks.py:92
backend/test_results/microgen/tasks.py:114
backend/test_results/microgen/tasks.py:140
backend/test_results/microgen/tasks.py:170
backend/test_results/microgen/tasks.py:187
backend/test_results/microgen/tasks.py:317  (apply_async)
backend/test_results/microgen/tasks.py:386
backend/test_results/microgen/tasks.py:387
backend/test_results/microgen/tasks.py:399
backend/test_results/microgen/tasks.py:403
backend/test_results/microgen/tasks.py:409
backend/test_results/microgen/tasks.py:450  (apply_async)
backend/test_results/microgen/tasks.py:453
backend/test_results/utils.py:3245
backend/test_results/utils.py:3252
backend/test_results/tasks.py:206
backend/test_results/tasks.py:211
backend/test_results/admin.py:1017
backend/test_results/post_processing_utils.py:429
backend/test_results/lab_services/orchestrator.py:462
backend/test_results/lab_services/orchestrator.py:556
backend/test_results/lab_services/lab_order_service.py:83
backend/scripts/backfill_unapproved_junction_submissions.py:113
backend/scripts/reprocess_subscription_refill_orders.py:229
backend/scripts/resend_lab_results_to_wheel.py:88
backend/test_results/lab_services/providers/junction/results_processor.py:119
backend/test_results/lab_services/providers/junction/results_processor.py:139
backend/app/management/commands/create_study_cohort_tests.py:147
backend/consults/utils.py:218
backend/consults/utils.py:404  (apply_async)
backend/consults/utils.py:406  (apply_async)
backend/consults/utils.py:413
backend/consults/utils.py:495
backend/consults/admin.py:1103
backend/consults/wheel/utils_webhook.py:94
backend/consults/wheel/utils_webhook.py:101
backend/consults/wheel/utils_webhook.py:153
backend/consults/wheel/utils_webhook.py:157
backend/consults/wheel/utils_webhook.py:262
backend/consults/wheel/utils_webhook.py:301
backend/consults/wheel/utils.py:2588
backend/scripts/test_result_tag_scripts.py:63
backend/api/v1/views/register.py:144
backend/api/v1/views/register.py:238
backend/consults/wheel/tasks.py:162
backend/consults/wheel/tasks.py:163
backend/consults/wheel/tasks.py:267
backend/consults/wheel/tasks.py:320
backend/consults/wheel/tasks.py:366
backend/consults/wheel/tasks.py:369
backend/consults/wheel/tasks.py:394
backend/consults/wheel/tasks.py:407
backend/consults/wheel/tasks.py:583
backend/consults/wheel/tasks.py:637
backend/consults/wheel/tasks.py:678
backend/consults/wheel/tasks.py:931
backend/api/v1/views/my_plan.py:46
backend/api/v1/views/account.py:253
backend/api/v1/views/provider_test_orders.py:104
backend/api/v1/views/provider_test_orders.py:112
backend/api/v1/views/provider_test_orders.py:245
backend/api/v1/views/provider_test_orders.py:262
backend/api/v1/views/provider_test_orders.py:310
backend/api/v1/views/user_tests.py:357
backend/api/v1/views/user_tests.py:873
backend/api/v1/views/user_tests.py:945
backend/api/v1/views/consult.py:363
backend/api/v1/views/consult.py:366
backend/api/v1/views/consult.py:463
backend/api/v1/views/consult.py:563
backend/api/v1/views/consult.py:799
backend/api/v1/views/consult.py:859
backend/api/v1/views/consult.py:912
backend/api/v1/views/consult.py:926
backend/api/v1/views/account_order_transfer_verification.py:128
backend/consults/signals.py:140
backend/consults/signals.py:158
backend/consults/signals.py:160
backend/consults/signals.py:162
backend/consults/signals.py:168
backend/api/v1/views/webhooks.py:253
backend/api/v1/views/webhooks.py:296
backend/api/v1/views/webhooks.py:311
```

---

### Step 8: Read business context for key files

The agent read specific file sections to understand the surrounding business logic for the most complex call sites.

**`ecomm/services/cart.py` lines 680–709** — Order transfer / claim flow:

```python
if evvy_account_email_matches or order_email_matches:
    order.user = user
    order.save()
    # Try to combine the current order into existing in progress/intake incomplete consult if it exists
    add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay(
        user.id, order.order_number
    )
else:
    send_account_transfer_verification_email.delay(user.id, order.email, order_number)
elif order and order.user != user:
    send_account_transfer_verification_email.delay(user.id, order.email, order_number)
```

**`ecomm/utils.py` lines 675–763** — Shopify order paid webhook processing:

```python
# Ungated Rx order routing
send_ungated_rx_order_paid_event.delay(order.order_number)

# Gift card processing
if should_process_gift_cards:
    process_gift_cards.delay(order.id, payload)

# Universal "any paid" event
if not is_order_cancellation and order.user and order.status != Order.STATUS_CANCELLED:
    send_any_paid_event.delay(order.order_number)

# Berlin fulfillment (always fires, both paid and cancellation)
send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)
```

**`ecomm/utils.py` lines 1120–1138** — Male partner test voucher:

```python
if user:
    send_mpt_voucher_paid_event.delay(user.id)
```

**`ecomm/utils.py` lines 1760–1782** — Provider test order via Shopify:

```python
if order.sku in PROVIDER_TEST_SKUS:
    if not bulk_order_id:
        send_patient_ordered_provider_test_notification.delay(
            patient_email=email,
            order_sku=order.sku,
            order_provider_id=order.provider_id,
        )
```

**`consults/wheel/utils.py` lines 2575–2603** — Lab order rejection:

```python
if lab_order.status == LabOrder.STATUS_REJECTED:
    send_lab_order_rejected_email.delay(lab_order.uid)
```

**`test_results/lab_services/providers/junction/results_processor.py` lines 100–148** — Junction auto-release:

```python
if can_auto_release_urine_test_results(urine_test):
    is_valid, lab_test, error_message = validate_urine_test_ready_for_wheel(urine_test)
    if is_valid and lab_test:
        urine_pcr_result.auto_released = True
        urine_pcr_result.save(update_fields=["auto_released"])
        # Send to Wheel using the same method as manual review
        issue_lab_results_to_wheel_for_lab_test.delay(str(lab_test.id))

# Trigger urine test care eligibility analytics event
send_urine_test_results_ready_analytics_events.delay(urine_test.hash)
```

---

## Final Answer

All call sites use `.delay()` unless noted. No `send_task()` calls exist in the codebase. Entries in `test_results/tests/microgen/test_tasks.py` are test assertions (checking the right method was called), not actual enqueue calls, and are excluded.

---

### ANALYTICS

**1. `send_custom_analytics_event_to_fullstory_async.delay()`**
- File: `analytics/tasks.py` line 131
- Args: `user.id, event_name, event_properties, use_recent_session_fullstory`
- Triggered by: `send_custom_analytics_event_to_destinations()` when `FULLSTORY` is in the destination set — general-purpose event fan-out called throughout the codebase.

**2. `send_custom_analytics_event_to_klaviyo_async.delay()`**
- File: `analytics/tasks.py` line 158
- Args: `payload` (full Klaviyo event payload dict)
- Triggered by: Same `send_custom_analytics_event_to_destinations()` function when `KLAVIYO` is in the destination set.

**3. `send_estimated_treatment_started_event.delay()`**
- File: `analytics/tasks.py` line 1154
- Args: `treatment_plan.id`
- Triggered by: Scheduled cron task `send_estimated_treatment_started_events_for_treatment_plans` — queries treatment plans whose estimated start date is today or yesterday, fans out per-plan.

**4. `send_treatment_ended_event.delay()`**
- File: `analytics/tasks.py` line 1320
- Args: `treatment_plan.id`
- Triggered by: Cron task `send_treatment_ended_events_for_treatment_plans()` — queries treatment plans with `treatment_end_date` equal to today or yesterday.

**5. `send_treatment_delivered_event.delay()` (analytics cron)**
- File: `analytics/tasks.py` line 1335
- Args: `treatment_plan.consult.uid`
- Triggered by: Cron task `send_treatment_probably_delivered_events_for_treatment_plans()` — for plans where `treatment_delivered_at` is null but `create_date` is past the average fulfillment window.

---

### ECOMM / ORDERS

**6. `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay()` [cart claim]**
- File: `ecomm/services/cart.py` line 701
- Args: `user.id, order.order_number`
- Triggered by: A user successfully claims an unclaimed order (email matches) during cart/order transfer — attaches the order to their account and creates or merges a consult.

**7. `send_account_transfer_verification_email.delay()` [no email match]**
- File: `ecomm/services/cart.py` line 705
- Args: `user.id, order.email, order_number`
- Triggered by: An unclaimed order's email does NOT match the current user — sends a verification email to confirm the transfer.

**8. `send_account_transfer_verification_email.delay()` [order has different user]**
- File: `ecomm/services/cart.py` line 708
- Args: `user.id, order.email, order_number`
- Triggered by: Order already has a different user attached — initiates transfer verification.

**9. `void_share_a_sale_transaction.delay()`**
- File: `ecomm/utils.py` line 416
- Args: `order_number, order_date, note`
- Triggered by: Processing a Shopify order cancellation — voids the affiliate commission on Share-a-Sale for the cancelled order.

**10. `send_ungated_rx_order_paid_event.delay()`**
- File: `ecomm/utils.py` line 691
- Args: `order.order_number`
- Triggered by: Shopify webhook processing a paid ungated Rx (UX) order with a valid user — fires analytics event.

**11. `process_gift_cards.delay()`**
- File: `ecomm/utils.py` line 740
- Args: `order.id, payload`
- Triggered by: Shopify order paid webhook, when the order involves gift card purchases or redemptions.

**12. `send_any_paid_event.delay()`**
- File: `ecomm/utils.py` line 744
- Args: `order.order_number`
- Triggered by: Any non-cancelled order with a user is paid via Shopify — universal "any paid" analytics event.

**13. `send_order_to_berlin_for_fulfillment.delay()` [Shopify webhook]**
- File: `ecomm/utils.py` line 763
- Args: `payload, is_order_cancellation, order.id`
- Triggered by: End of Shopify order processing (both paid and cancellation webhooks) — sends order to the Berlin fulfillment service.

**14. `send_mpt_voucher_paid_event.delay()`**
- File: `ecomm/utils.py` line 1138
- Args: `user.id`
- Triggered by: A Male Partner Test (MPT) voucher/gift card is processed and the user is known — fires analytics event.

**15. `create_unregistered_testkit_order_for_urine_test.delay()`**
- File: `ecomm/utils.py` line 1236
- Args: `urine_test_ids=urine_test_ids, ecomm_order_id=order.id`
- Triggered by: A urine test order is paid and urine tests are created — creates corresponding unregistered testkit orders.

**16. `send_patient_ordered_provider_test_notification.delay()`**
- File: `ecomm/utils.py` line 1778
- Args: `patient_email=email, order_sku=order.sku, order_provider_id=order.provider_id`
- Triggered by: A patient orders a provider test SKU (non-bulk) via Shopify — notifies admin Slack channel.

**17. `send_consult_paid_event.delay()`**
- File: `ecomm/utils.py` line 1874
- Args: `consult.uid, order.provider_id`
- Triggered by: A care (consult) order is paid via Shopify and the order is not cancelled.

**18. `send_additional_tests_paid_event.delay()` [no test_kit_hash]**
- File: `ecomm/utils.py` line 1990
- Args: `None, order.provider_id`
- Triggered by: A Shopify PCR add-on order is paid but the test kit hash is missing from the order note attributes — fires degraded analytics event.

**19. `send_additional_tests_paid_event.delay()` [with test_kit_hash]**
- File: `ecomm/utils.py` line 2009
- Args: `test_kit.hash, order.provider_id`
- Triggered by: A Shopify expanded PCR add-on order is paid and the test kit is successfully linked.

**20. `send_prescription_refill_request.delay()` [ecomm/utils.py]**
- File: `ecomm/utils.py` line 2198
- Args: `order.id, prescription_fill.id`
- Triggered by: A subscription refill order is paid — after prescription fill records are created, sends the refill request to Precision pharmacy.

**21. `send_provider_bulk_order_paid_notification.delay()` [ecomm/utils.py]**
- File: `ecomm/utils.py` line 2705
- Args: `ecomm_order_id=order.id, provider_email=provider_test_orders.first().provider.email, quantity=expected_count`
- Triggered by: A provider bulk order is paid via Shopify — notifies the provider with confirmation.

**22. `send_prescription_refills_paid_event.delay()`**
- File: `ecomm/tasks.py` line 229
- Args: `prescription_fill_id, order.provider_id`
- Triggered by: Inside `send_prescription_refill_request` task, after the prescription fill status is set to CREATED — fires the "refills paid" analytics event.

**23. `send_rx_order_attached_to_account_klaviyo_event.delay()`**
- File: `ecomm/tasks.py` line 460
- Args: `consult.uid, order.order_number`
- Triggered by: Inside `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult` task when an existing in-progress consult is found and the ungated Rx order is attached to it.

---

### CARE / PRESCRIPTIONS / TREATMENT PLANS

**24. `create_or_reset_calendar_treatments.apply_async()` [new prescription]**
- File: `care/signals.py` line 121
- Args: `args=(treatment_plan.id,), countdown=300` (5-minute delay)
- Triggered by: `Prescription.pre_save` signal when a new non-deleted prescription is created for a completed consult — rebuilds the treatment calendar. Delay is intentional to allow all prescriptions to be saved first.

**25. `create_or_reset_calendar_treatments.apply_async()` [deleted status change]**
- File: `care/signals.py` line 129
- Args: `args=(treatment_plan.id,), countdown=300` (5-minute delay)
- Triggered by: `Prescription.pre_save` signal when an existing prescription's `deleted` status changes — adjusts or removes the calendar treatment.

**26. `update_treatment_end_date.delay()` [care/signals.py]**
- File: `care/signals.py` line 86
- Args: `instance.treatment_plan_id`
- Triggered by: `TreatmentPlanInterruption.post_save` or `post_delete` signal — recalculates treatment end date whenever an interruption (e.g., pause) is added or removed.

**27. `send_otc_treatment_fill_request.delay()`**
- File: `care/tasks.py` line 125
- Args: `order.id, prescription_fill.id`
- Triggered by: Inside `heal_otc_treatment_orders` task when an OTC-only order is found without a sent prescription fill — creates and sends the OTC fill request to Precision.

**28. `update_treatment_end_date.delay()` [consult/signals.py]**
- File: `consults/signals.py` line 140
- Args: `treatment_plan.id` (via `transaction.on_commit` lambda)
- Triggered by: `Consult.post_save` signal when a consult transitions to `STATUS_COMPLETE` and a treatment plan is created — sets the initial treatment end date after transaction commits.

**29. `send_email_organon_prescriptions_ready.delay()`**
- File: `consults/signals.py` line 158
- Args: `consult.uid`
- Triggered by: `Consult.post_save` signal when consult reaches `STATUS_COMPLETE`, pharmacy type is local pickup, and it is NOT a urine test — sends Organon pharmacy-ready email.

**30. `send_treatment_plan_ready_email.delay()`**
- File: `consults/signals.py` line 160
- Args: `consult.uid`
- Triggered by: `Consult.post_save` signal when consult reaches `STATUS_COMPLETE` and purchase type is full treatment plan — notifies patient their treatment plan is ready.

**31. `send_a_la_care_treatments_ready.delay()`**
- File: `consults/signals.py` line 162
- Args: `consult.uid`
- Triggered by: `Consult.post_save` signal when consult reaches `STATUS_COMPLETE` and purchase type is a-la-carte — notifies patient their selected treatments are ready.

**32. `send_sti_prescription_sent_to_pharmacy_email.delay()`**
- File: `consults/signals.py` line 168
- Args: `consult.uid`
- Triggered by: `Consult.post_save` signal when an STI consult reaches `STATUS_COMPLETE` — tells patient their prescription was sent to the pharmacy.

**33. `update_treatment_end_date.delay()` [API — patient sets start date]**
- File: `api/v1/views/consult.py` line 363
- Args: `treatment_plan.id`
- Triggered by: Patient updates their `treatment_start_date` via the API — recalculates treatment end date.

**34. `send_updated_treatment_start_date_event.delay()`**
- File: `api/v1/views/consult.py` line 366
- Args: `consult.uid`
- Triggered by: Same API endpoint — patient updates their treatment start date.

**35. `send_care_checkout_created_event.delay()` [cart checkout]**
- File: `api/v1/views/consult.py` line 463
- Args: `consult.uid`
- Triggered by: Patient creates a Shopify checkout URL for a care/consult purchase.

**36. `send_care_checkout_created_event.delay()` [STI checkout]**
- File: `api/v1/views/consult.py` line 563
- Args: `consult.uid`
- Triggered by: A separate checkout URL creation path (STI intake flow) — same analytics event.

**37. `send_consult_intake_started_klaviyo_event.delay()` [agree to terms]**
- File: `api/v1/views/consult.py` line 799
- Args: `intake.consult.uid`
- Triggered by: Patient agrees to terms in the consult intake (`agree_to_terms` action) — marks the start of the intake process.

**38. `send_consult_intake_started_klaviyo_event.delay()` [ungated Rx consent]**
- File: `api/v1/views/consult.py` line 859
- Args: `intake.consult.uid`
- Triggered by: Patient consents to ungated Rx terms (`consent_to_ungated_rx_terms` action) — also fires the intake started event.

**39. `resubmit_consult_photo_id_info_to_wheel.delay()`**
- File: `api/v1/views/consult.py` line 912
- Args: `consult.uid`
- Triggered by: Patient resubmits their intake when consult is in `STATUS_ID_FAILURE` — retries the ID verification with Wheel.

**40. `submit_async_consult.delay()` [intake submit]**
- File: `api/v1/views/consult.py` line 926
- Args: `consult.uid`
- Triggered by: Patient submits their consult intake and consult is not already in a terminal state — submits the consult to Wheel for clinician review.

---

### CONSULTS / WHEEL INTEGRATION

**41. `send_consult_intake_ineligible_event.delay()`**
- File: `consults/utils.py` line 218
- Args: `consult.uid, refer_out_reason`
- Triggered by: Intake eligibility check determines patient is ineligible (e.g., wrong state, pregnancy, severe symptoms) — fires analytics event.

**42. `submit_lab_order_to_wheel.apply_async()` [LDT vaginal test]**
- File: `consults/utils.py` line 404
- Args: `(lab_order.uid,), countdown=300` (5-minute delay)
- Triggered by: `submit_lab_order_for_test()` when test is LDT — delays submission to Wheel to allow PCR add-on orders to be processed first.

**43. `submit_lab_order_to_wheel.apply_async()` [urine test]**
- File: `consults/utils.py` line 406
- Args: `(lab_order.uid,), countdown=300` (5-minute delay)
- Triggered by: Same function when test is a urine test — also delayed to allow add-on order processing.

**44. `submit_lab_order_approval_to_microgen.delay()` [non-LDT vaginal]**
- File: `consults/utils.py` line 413
- Args: `lab_order.uid`
- Triggered by: `submit_lab_order_for_test()` for non-LDT vaginal tests — lab order is auto-approved and immediately submitted to Microgen.

**45. `mark_wheel_consult_message_as_read.delay()`**
- File: `consults/utils.py` line 495
- Args: `consult.uid, message_id`
- Triggered by: Patient marks a consult message as read — asynchronously marks the message as read in Wheel.

**46. `fetch_and_process_follow_up_consult_details.delay()` [Wheel webhook]**
- File: `consults/wheel/utils_webhook.py` line 94
- Args: `lab_order_uid, wheel_consult_id`
- Triggered by: Wheel webhook fires `consult.statusChange` with disposition `lab-follow-up-needs-attention` for a lab order.

**47. `fetch_and_process_completed_lab_order_details.delay()` [Wheel webhook]**
- File: `consults/wheel/utils_webhook.py` line 101
- Args: `lab_order_uid`
- Triggered by: Wheel webhook fires `consult.statusChange` with disposition `lab-order-approved`, `lab-order-rejected`, or `auto-referred-out` for a lab order.

**48. `fetch_and_process_referred_consult_details.delay()` [Wheel webhook]**
- File: `consults/wheel/utils_webhook.py` line 153
- Args: `consult_uid`
- Triggered by: Wheel webhook fires `consult.statusChange` with status `finished` and disposition `referred-out` or `auto-referred-out` for a full consult.

**49. `fetch_and_process_completed_consult_details.delay()` [Wheel webhook]**
- File: `consults/wheel/utils_webhook.py` line 157
- Args: `consult.uid`
- Triggered by: Wheel webhook fires `consult.statusChange` with status `finished` and disposition `diagnosed` for a full consult.

**50. `send_id_verification_failed_email.delay()`**
- File: `consults/wheel/utils_webhook.py` line 262
- Args: `consult.uid`
- Triggered by: Wheel webhook fires `consult.verification.failed` event — notifies patient their ID verification failed.

**51. `send_new_consult_message_email.delay()`**
- File: `consults/wheel/utils_webhook.py` line 301
- Args: `consult.uid`
- Triggered by: Wheel webhook fires a new message event — notifies patient they have a new message from their clinician.

**52. `send_consult_intake_submitted_event.delay()`**
- File: `consults/wheel/tasks.py` line 162
- Args: `consult_uid`
- Triggered by: Inside `submit_async_consult` task, after successfully creating an async consult in Wheel — fires analytics event.

**53. `send_consult_intake_reviewed_email.delay()`**
- File: `consults/wheel/tasks.py` line 163
- Args: `consult_uid`
- Triggered by: Same — sends the patient a confirmation email that their intake is under review.

**54. `check_recommended_prescriptions_against_prescribed_and_send_prescriptions.delay()`**
- File: `consults/wheel/tasks.py` line 267
- Args: `consult_uid`
- Triggered by: Inside `fetch_and_process_completed_consult_details` task when the consult has Evvy treatment type — verifies prescribed treatments match recommendations and submits to Precision if they do.

**55. `submit_lab_order_approval_to_junction.delay()` [route from Wheel]**
- File: `consults/wheel/tasks.py` line 320
- Args: `lab_order.uid`
- Triggered by: Inside `fetch_and_process_completed_lab_order_details` task when the lab order is a urine test and is approved — routes to Junction lab for processing.

**56. `fetch_and_process_completed_consult_details.delay()` [retry cron]**
- File: `consults/wheel/tasks.py` line 366
- Args: `consult.uid`
- Triggered by: Inside `retry_consult_detail_processing` cron task, for consults stuck in review >24 hours where Wheel shows them as `finished/diagnosed`.

**57. `fetch_and_process_referred_consult_details.delay()` [retry cron]**
- File: `consults/wheel/tasks.py` line 369
- Args: `consult.uid`
- Triggered by: Same retry cron task, for consults stuck in review where Wheel shows them as `finished/referred-out`.

**58. `submit_async_consult.delay()` [retry stuck submitted consults]**
- File: `consults/wheel/tasks.py` line 394
- Args: `consult.uid`
- Triggered by: `retry_creating_async_consults` cron task — re-attempts consult submission for consults stuck in `STATUS_SUBMITTED` for 1–5 days.

**59. `submit_async_consult.delay()` [retry errored consults]**
- File: `consults/wheel/tasks.py` line 407
- Args: `consult.uid`
- Triggered by: `retry_errored_consult_creation` cron task — re-attempts consult submission for consults stuck in `STATUS_ERROR`.

**60. `send_care_referred_out_email.delay()`**
- File: `consults/wheel/tasks.py` line 583
- Args: `consult.uid`
- Triggered by: Inside `fetch_and_process_referred_consult_details` task after the consult is set to `STATUS_REFERRED` — notifies patient they have been referred out.

**61. `submit_lab_order_to_wheel.delay()` [resubmit stuck]**
- File: `consults/wheel/tasks.py` line 637
- Args: `lab_order.uid`
- Triggered by: `resubmit_stuck_lab_orders_to_wheel` cron task — resubmits lab orders stuck in `STATUS_CREATED` or `STATUS_SUBMITTED` for >1 hour after intake submission.

**62. `submit_lab_order_to_wheel.delay()` [resubmit errored]**
- File: `consults/wheel/tasks.py` line 678
- Args: `lab_order.uid`
- Triggered by: `resubmit_errored_lab_orders_to_wheel` cron task — resubmits lab orders in `STATUS_ERROR` that haven't had results sent yet.

**63. `fetch_and_process_follow_up_consult_details.delay()` [pending follow-ups cron]**
- File: `consults/wheel/tasks.py` line 931
- Args: `lab_order.uid, follow_up.external_id`
- Triggered by: A cron task monitoring pending lab result follow-ups where diagnosis is not yet confirmed — retries fetching follow-up consult details from Wheel.

**64. `send_lab_order_rejected_email.delay()`**
- File: `consults/wheel/utils.py` line 2588
- Args: `lab_order.uid`
- Triggered by: Inside `store_lab_order_disposition()` when Wheel rejects the lab order — emails the patient that their order was rejected.

**65. `fetch_and_process_completed_consult_details.delay()` [admin action]**
- File: `consults/admin.py` line 1103
- Args: `obj.uid`
- Triggered by: Admin manually triggers "Fetch completed consult details" action in the Django admin for a consult.

---

### TEST RESULTS / LAB PIPELINE

**66. `issue_lab_results_to_wheel_for_lab_test.delay()` [LabTest signal]**
- File: `test_results/signals.py` line 443
- Args: `lab_test.id`
- Triggered by: `LabTest.pre_save` signal when a lab test transitions to `STATUS_COMPLETE` and is not a urine test — sends results to Wheel for clinical review.

**67. `send_vip_test_status_update.delay()` [test signal]**
- File: `test_results/signals.py` line 246
- Args: `test_instance.hash, previous_status, test_instance.status`
- Triggered by: `Test` or `UrineTest` status change signal when `track_status_change=True` — sends VIP status update to Slack.

**68. `send_coaching_call_completed_event.delay()`**
- File: `test_results/signals.py` line 490
- Args: `instance.test.hash, instance.id, num_calls`
- Triggered by: `CoachingCallNotes.pre_save` signal when `had_call` changes from False to True — fires analytics event for completed coaching call.

**69. `post_process_test_results.delay()` [utils_processing]**
- File: `test_results/utils_processing.py` line 210
- Args: `test.hash`
- Triggered by: `_trigger_post_processing()` helper called after NGS results are processed — runs post-processing pipeline if a test result exists.

**70. `send_provider_test_results_ready.delay()` [utils.py non-LDT]**
- File: `test_results/utils.py` line 3245
- Args: `provider.email`
- Triggered by: Inside `release_test_results()` for non-LDT tests with a provider test order and authorized release — notifies the provider their patient's results are ready.

**71. `send_results_ready_analytics_events.delay()`**
- File: `test_results/utils.py` line 3252
- Args: `test.hash, eligible_for_care, ineligible_reason`
- Triggered by: Inside `release_test_results()` for all test types — fires analytics events tied to results release.

**72. `issue_lab_results_to_wheel_for_lab_test.delay()` [admin action]**
- File: `test_results/admin.py` line 1017
- Args: `str(lab_test.id)`
- Triggered by: Admin manually triggers "Send results to Wheel" action on a urine PCR result in the Django admin.

**73. `send_urine_test_results_ready_analytics_events.delay()` [post_processing_utils]**
- File: `test_results/post_processing_utils.py` line 429
- Args: `urine_test.hash`
- Triggered by: UTI test post-processing pipeline, after infection state is created — fires care eligibility analytics event.

**74. `fulfill_uti_order_in_shopify.delay()`**
- File: `test_results/lab_services/orchestrator.py` line 462
- Args: `urine_test_id=urine_test.id, tracking_number=shipment_data["outbound_tracking_number"], courier=shipment_data.get("outbound_courier", "")`
- Triggered by: Junction orchestrator processes a status update with `transit_customer` event — fulfills the UTI test order in Shopify with tracking info.

**75. `send_vip_test_status_update.delay()` [orchestrator]**
- File: `test_results/lab_services/orchestrator.py` line 556
- Args: `urine_test.hash, old_status, new_status`
- Triggered by: Junction orchestrator processes a urine test status update when `track_status_change=True` on the test.

**76. `fetch_and_process_junction_results.delay()`**
- File: `test_results/lab_services/lab_order_service.py` line 83
- Args: `external_order_id`
- Triggered by: Junction `results_ready` webhook received — dispatches async task to fetch and process the results from Junction.

**77. `issue_lab_results_to_wheel_for_lab_test.delay()` [Junction auto-release]**
- File: `test_results/lab_services/providers/junction/results_processor.py` line 119
- Args: `str(lab_test.id)`
- Triggered by: Junction results processor determines a urine test with no pathogens can be auto-released — sends results to Wheel without manual review.

**78. `send_urine_test_results_ready_analytics_events.delay()` [Junction processor]**
- File: `test_results/lab_services/providers/junction/results_processor.py` line 139
- Args: `urine_test.hash`
- Triggered by: Junction results processor finishes processing results — fires care eligibility analytics event.

**79. `send_provider_test_results_ready.delay()` [infection_state_service LDT]**
- File: `test_results/infection_state_service.py` line 500
- Args: `provider.email`
- Triggered by: Inside `confirm_diagnosis()` for LDT tests with a provider test order — provider notification is sent at diagnosis confirmation time (not at results release).

**80. `send_eligible_for_care_1_for_test.delay()`**
- File: `test_results/tasks.py` line 206
- Args: `test.id`
- Triggered by: Inside `send_results_ready_emails` task, if the test is LDT and eligible for care — triggers care eligibility email #1.

**81. `send_eligible_for_a_la_care_not_treatment_program.delay()`**
- File: `test_results/tasks.py` line 211
- Args: `test.id`
- Triggered by: Same task, if test is LDT, NOT eligible for full care program, but IS eligible for a-la-carte — sends alternative care pathway email.

---

### MICROGEN / NGS LAB PIPELINE

**82. `submit_lab_order_approval_to_microgen.delay()` [healing cron]**
- File: `test_results/microgen/tasks.py` line 92
- Args: `lab_order.uid`
- Triggered by: `submit_missing_lab_order_approvals_to_microgen` cron task — re-submits approved lab orders that were never sent to Microgen within the last 60 days.

**83. `process_microgen_test_results_if_exists_in_s3.delay()`**
- File: `test_results/microgen/tasks.py` line 114
- Args: `test.hash`
- Triggered by: `process_test_results_stuck_in_sequencing_status` cron task — checks S3 for results of tests stuck in sequencing for >7 days.

**84. `post_process_test_results.delay()` [from process_microgen_test_results]**
- File: `test_results/microgen/tasks.py` line 140
- Args: `test_hash, release_results`
- Triggered by: Inside `process_microgen_test_results` task, after NGS results are downloaded from S3 — runs the post-processing pipeline.

**85. `send_pcr_test_results_ready.delay()`**
- File: `test_results/microgen/tasks.py` line 170
- Args: `test_hash`
- Triggered by: Inside `process_microgen_vag_pcr_test_results` task after PCR results are fully processed — notifies user their PCR results are ready.

**86. `send_pcr_test_results_ready_provider_klaviyo_event.delay()`**
- File: `test_results/microgen/tasks.py` line 187
- Args: `test_hash, provider_test_order.id`
- Triggered by: Same task, when the test has a provider test order — notifies the provider via Klaviyo that their patient's PCR results are ready.

**87. `summary_task.apply_async()` (dynamic task reference)**
- File: `test_results/microgen/tasks.py` line 317
- Args: `countdown=cache_timeout` (60 min for sequencing, 20 min for partial-results/ready)
- Triggered by: `_queue_summary_notification()` helper — batches lab summary emails using Redis as a lock; actual task is one of `send_summary_tests_entered_sequencing`, `send_summary_vpcr_results_processed`, or `send_summary_vngs_results_processed` depending on lab event type.

**88. `send_test_sample_at_lab_but_not_activated.delay()`**
- File: `test_results/microgen/tasks.py` line 386
- Args: `test.hash`
- Triggered by: Microgen webhook fires status `received` for a test that has no user (`user_id` is null) — alerts that sample arrived but test hasn't been activated by the patient yet.

**89. `send_ldt_test_sample_received_email.delay()`**
- File: `test_results/microgen/tasks.py` line 387
- Args: `test.hash`
- Triggered by: Microgen webhook fires status `received` — always sent, regardless of activation status.

**90. `send_ldt_test_sample_sequencing_email.delay()`**
- File: `test_results/microgen/tasks.py` line 399
- Args: `test.hash`
- Triggered by: Microgen webhook fires status `sequencing` — notifies patient their sample is being sequenced.

**91. `send_sample_sequencing_provider_klaviyo_event.delay()`**
- File: `test_results/microgen/tasks.py` line 403
- Args: `test_hash, provider_test_order.id`
- Triggered by: Microgen webhook fires status `sequencing` for a test with a provider test order — notifies provider via Klaviyo that sequencing is underway.

**92. `process_microgen_vag_pcr_test_results.delay()`**
- File: `test_results/microgen/tasks.py` line 409
- Args: `test_hash`
- Triggered by: Microgen webhook fires status `partial-results` with panel `vag-sti` — processes vaginal PCR results.

**93. `process_microgen_test_results.apply_async()` (with countdown)**
- File: `test_results/microgen/tasks.py` line 450
- Args: `args=[test_hash], countdown=delay_seconds` (random 0 to `RESULTS_PROCESSING_MAX_DELAY_MINUTES * 60` seconds)
- Triggered by: Microgen webhook fires status `ready` when `RESULTS_PROCESSING_MAX_DELAY_MINUTES > 0` — schedules processing with a random delay to spread load.

**94. `process_microgen_test_results.delay()` [immediate — ready status]**
- File: `test_results/microgen/tasks.py` line 453
- Args: `test_hash`
- Triggered by: Microgen webhook fires status `ready` when `RESULTS_PROCESSING_MAX_DELAY_MINUTES == 0` (immediate mode).

---

### SHIPPING / FULFILLMENT

**95. `update_individual_shipping_status.delay()`**
- File: `shipping/tasks.py` line 155
- Args: `status.id`
- Triggered by: `update_shipping_statuses` cron task — fans out individual shipping status poll updates for all active tracked shipments across FedEx/USPS.

**96. `send_order_to_berlin_for_fulfillment.delay()` [retry cron]**
- File: `shipping/tasks.py` line 768
- Args: `order.payload, is_order_cancellation, order.id`
- Triggered by: `retry_failed_berlin_order_fulfillments` cron task — retries orders that never had `sent_to_berlin_at` set since 3/27/2024.

**97. `send_test_delivered_klaviyo_event.delay()`**
- File: `shipping/utils.py` line 231
- Args: `test.hash`
- Triggered by: Inside `update_shipping_status_for_test()` when a test kit shipping status transitions to delivered — fires Klaviyo "test delivered" event.

**98. `send_prescription_to_precision.delay()` [healing cron]**
- File: `shipping/precision/tasks.py` line 299
- Args: `consult.uid`
- Triggered by: `send_missing_prescriptions_to_precision` cron task — re-submits prescriptions for completed consults that were never sent to Precision within the last 2 days.

**99. `send_treatment_delivered_event.delay()` [precision webhook]**
- File: `shipping/precision/utils.py` line 599
- Args: `consult.uid`
- Triggered by: Precision pharmacy webhook callback processes successful prescription fulfillment — fires Klaviyo treatment delivered event for non-OTC-only prescription fills.

---

### USER REGISTRATION / ACCOUNT

**100. `attach_unattached_orders_to_user.delay()`**
- File: `api/v1/views/register.py` line 144
- Args: `user.id`
- Triggered by: New patient account registration — scans for any prior guest orders with a matching email and attaches them to the new account.

**101. `send_provider_registered_event.delay()`**
- File: `api/v1/views/register.py` line 238
- Args: `user.id`
- Triggered by: New provider account registration — fires Klaviyo "Provider Registered" analytics event.

**102. `send_intake_completed_notifications.delay()`**
- File: `api/v1/views/account.py` line 253
- Args: `user.email`
- Triggered by: Provider completes their profile intake for the first time (`profile.submitted_at` is newly set) — notifies Slack channel and sends confirmation email.

**103. `send_provider_verified_event.delay()`**
- File: `accounts/admin_actions.py` line 270
- Args: `provider_profile.provider.id`
- Triggered by: Admin manually verifies a provider profile in the Django admin — fires Klaviyo "Provider Verified" analytics event.

---

### PROVIDER TEST ORDERS

**104. `send_provider_ordered_single_test_notifications.delay()`**
- File: `api/v1/views/provider_test_orders.py` line 104
- Args: `provider_email, patient_email, provider_test_order_id, payer, add_expanded_pcr`
- Triggered by: Provider orders a single test for a patient via the API — sends confirmation notifications.

**105. `send_provider_ordered_test_klaviyo_event.delay()` [single order]**
- File: `api/v1/views/provider_test_orders.py` line 112
- Args: `provider_id, provider_test_order_ids=[provider_test_order.id], payer, add_expanded_pcr, patient_email`
- Triggered by: Same single test order — sends Klaviyo event to provider.

**106. `send_provider_bulk_ordered_tests_notification.delay()`**
- File: `api/v1/views/provider_test_orders.py` line 245
- Args: `provider_email, num_ordered, provider_test_order_ids`
- Triggered by: Provider generates a bulk checkout URL — after transaction commits, sends bulk order notification.

**107. `send_provider_ordered_test_klaviyo_event.delay()` [bulk order]**
- File: `api/v1/views/provider_test_orders.py` line 262
- Args: `provider_id, provider_test_order_ids, payer="provider-bulk"`
- Triggered by: Same bulk order checkout — sends Klaviyo event for the bulk provider order.

**108. `send_provider_reminded_patient_klaviyo_event.delay()`**
- File: `api/v1/views/provider_test_orders.py` line 310
- Args: `provider_id=provider.id, patient_email=patient_email`
- Triggered by: Provider sends a reminder to a patient who hasn't activated/used their test order yet.

---

### USER TESTS

**109. `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay()` [test activation]**
- File: `api/v1/views/user_tests.py` line 357
- Args: `test.user.id, ecomm_order.order_number`
- Triggered by: Patient activates a test kit and the associated ecomm order is an ungated Rx type without a user — attaches order and creates/merges consult.

**110. `send_additional_tests_checkout_created_event.delay()`**
- File: `api/v1/views/user_tests.py` line 873
- Args: `test_kit.hash`
- Triggered by: Patient creates checkout URL for adding an expanded PCR panel to an existing test kit.

**111. `send_health_history_completed_klaviyo_event.delay()`**
- File: `api/v1/views/user_tests.py` line 945
- Args: `test.hash`
- Triggered by: Patient submits their health history questionnaire — fires Klaviyo event and triggers lab order submission.

---

### MY PLAN (RESULTS VIEWING)

**112. `send_viewed_plan_klaviyo_event.delay()`**
- File: `api/v1/views/my_plan.py` line 46
- Args: `test.id`
- Triggered by: Patient views their test results plan for the first time (`record_viewed_plan=true` query param and `plan_viewed_at` not yet set) — fires Klaviyo event.

---

### INBOUND WEBHOOKS

**113. `process_tracking_statuses.delay()`**
- File: `api/v1/views/webhooks.py` line 253
- Args: `test_hash=test_hash, order_number=order_number, kit_tracking_number=kit_tracking_number, sample_tracking_number=sample_tracking_number`
- Triggered by: Berlin fulfillment webhook fires with shipping/tracking data.

**114. `process_lab_status_update_batch.delay()`**
- File: `api/v1/views/webhooks.py` line 296
- Args: `payload` (batch of lab status updates)
- Triggered by: Microgen batch webhook endpoint receives a batch of lab status updates — queues batch processing.

**115. `process_precision_pharmacy_webhook.delay()`**
- File: `api/v1/views/webhooks.py` line 311
- Args: `payload`
- Triggered by: Precision pharmacy webhook endpoint receives a callback (e.g., prescription filled, shipped) — processes the pharmacy update asynchronously.

---

### ACCOUNT ORDER TRANSFER

**116. `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay()` [order transfer verification]**
- File: `api/v1/views/account_order_transfer_verification.py` line 128
- Args: `evvy_account_user.id, order.order_number`
- Triggered by: Patient verifies an order transfer email link — attaches verified orders to their account and creates/merges consults.

---

### STUDIES / RESEARCH

**117. `submit_research_sample_lab_order_to_microgen.delay()` [admin action]**
- File: `studies/admin.py` line 66
- Args: `cohort_test.test.hash`
- Triggered by: Admin triggers "Submit to Microgen" action in the Django admin for study cohort tests.

**118. `submit_research_sample_lab_order_to_microgen.delay()` [management command]**
- File: `app/management/commands/create_study_cohort_tests.py` line 147
- Args: `test.hash`
- Triggered by: `create_study_cohort_tests` Django management command — submits newly created study cohort tests to Microgen for research.

---

### SCRIPTS (ONE-OFF / BACKFILL)

**119. `issue_lab_results_to_wheel_for_lab_test.delay()` [script]**
- File: `scripts/resend_lab_results_to_wheel.py` line 88
- Args: `str(lab_test.id)`
- Triggered by: One-off backfill script to resend lab results to Wheel — used for manual remediation.

**120. `submit_lab_order_approval_to_junction.delay()` [backfill script]**
- File: `scripts/backfill_unapproved_junction_submissions.py` line 113
- Args: `lab_order.uid`
- Triggered by: One-off backfill script to submit previously unapproved lab orders to Junction.

**121. `send_prescription_refill_request.delay()` [reprocess script]**
- File: `scripts/reprocess_subscription_refill_orders.py` line 229
- Args: `order.id, prescription_fill.id`
- Triggered by: One-off script to reprocess subscription refill orders that failed initial processing.

**122. `create_test_result_tagset.delay()`**
- File: `scripts/test_result_tag_scripts.py` line 63
- Args: `test.hash`
- Triggered by: One-off script to backfill test result tagsets for existing test results.

---

## Summary Statistics

| Method | Count |
|---|---|
| `.delay()` | 119 |
| `.apply_async()` | 4 (3 with `countdown`, 1 dynamic) |
| `send_task()` | 0 |
| **Total** | **123 call sites across 43 files** |

**Task categories:**
- **Analytics / Klaviyo / Fullstory events:** ~35 call sites (sending events when user actions occur or schedules fire)
- **Wheel/Consult pipeline:** ~22 call sites (submit, process, retry consults and lab orders)
- **Lab/Test results pipeline:** ~20 call sites (Microgen webhook routing, NGS processing, results release)
- **Ecomm/Order processing:** ~15 call sites (Shopify webhooks, fulfillment, refills)
- **Care/Treatment management:** ~8 call sites (calendar, treatment dates, prescription fills)
- **Shipping/Tracking:** ~5 call sites (Berlin fulfillment, FedEx/USPS status polling)
- **Registration/Account:** ~5 call sites (new users, provider onboarding, order transfer)
- **Scripts/Admin/Research:** ~7 call sites (backfills, admin actions, study submissions)
- **Inbound webhook dispatch:** ~3 call sites (Microgen batch, Precision, Berlin tracking)
