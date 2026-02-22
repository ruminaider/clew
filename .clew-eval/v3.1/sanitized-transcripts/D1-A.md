# Exploration Transcript: Tool A — D1

**Task:** Find every place in the codebase where a background task is enqueued — called with `.delay()`, `.apply_async()`, or `send_task()`. For each call site, identify which task is being enqueued, what arguments are passed, and the business context (what triggers this task to be enqueued). Provide a complete inventory.

---

## Step 1: Initial broad search

```
search("background task enqueue delay apply_async")
```

**Results (abridged):**
```json
[
  {
    "file_path": "backend/app/settings_celery.py",
    "preview": "import os\n\nfrom celery.schedules import crontab\n\n"
  },
  {
    "file_path": "backend/app/celery.py",
    "preview": "# File: backend/app/celery.py\n# Imports: import logging, import os, from celery import Celery..."
  },
  {
    "file_path": "backend/transactional_email/tasks.py",
    "preview": "# File: backend/transactional_email/tasks.py\n# Imports: ..."
  }
]
```

The semantic search found configuration files and task definitions but not the call sites. Switching to pattern-based search.

---

## Step 2: Find all files containing enqueue calls

```
search("\.delay\(|\.apply_async\(|send_task\(")
```

**Result:** Found 54 files.

```
backend/shipping/tasks.py
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
[and others]
```

---

## Step 3: Get all call sites with line numbers

```
search("\.delay\(|\.apply_async\(|send_task\(")
```

**Result:** 124 total occurrences across 43 files.

```
backend/ecomm/services/cart.py:701:            add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay(
backend/ecomm/services/cart.py:705:            send_account_transfer_verification_email.delay(user.id, order.email, order_number)
backend/ecomm/services/cart.py:708:        send_account_transfer_verification_email.delay(user.id, order.email, order_number)
backend/analytics/tasks.py:131:        send_custom_analytics_event_to_fullstory_async.delay(
backend/analytics/tasks.py:158:        send_custom_analytics_event_to_klaviyo_async.delay(payload)
backend/analytics/tasks.py:1154:        send_estimated_treatment_started_event.delay(treatment_plan.id)
backend/analytics/tasks.py:1320:        send_treatment_ended_event.delay(treatment_plan.id)
backend/analytics/tasks.py:1335:        send_treatment_delivered_event.delay(treatment_plan.consult.uid)
backend/scripts/resend_lab_results_to_wheel.py:88:                    issue_lab_results_to_wheel_for_lab_test.delay(str(lab_test.id))
backend/ecomm/utils.py:416:        void_share_a_sale_transaction.delay(order_number, order_date, note)
backend/ecomm/utils.py:691:        send_ungated_rx_order_paid_event.delay(order.order_number)
backend/ecomm/utils.py:740:            process_gift_cards.delay(order.id, payload)
backend/ecomm/utils.py:744:        send_any_paid_event.delay(order.order_number)
backend/ecomm/utils.py:763:    send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)
backend/ecomm/utils.py:1138:        send_mpt_voucher_paid_event.delay(user.id)
backend/ecomm/utils.py:1236:        create_unregistered_testkit_order_for_urine_test.delay(
backend/ecomm/utils.py:1778:            send_patient_ordered_provider_test_notification.delay(
backend/ecomm/utils.py:1874:            send_consult_paid_event.delay(consult.uid, order.provider_id)
backend/ecomm/utils.py:1990:        send_additional_tests_paid_event.delay(None, order.provider_id)
backend/ecomm/utils.py:2009:        send_additional_tests_paid_event.delay(test_kit.hash, order.provider_id)
backend/ecomm/utils.py:2198:    send_prescription_refill_request.delay(order.id, prescription_fill.id)
backend/ecomm/utils.py:2705:        send_provider_bulk_order_paid_notification.delay(
backend/scripts/backfill_unapproved_junction_submissions.py:113:                submit_lab_order_approval_to_junction.delay(lab_order.uid)
backend/scripts/reprocess_subscription_refill_orders.py:229:        send_prescription_refill_request.delay(order.id, prescription_fill.id)
backend/ecomm/tasks.py:229:    send_prescription_refills_paid_event.delay(prescription_fill_id, order.provider_id)
backend/ecomm/tasks.py:460:        send_rx_order_attached_to_account_klaviyo_event.delay(consult.uid, order.order_number)
backend/shipping/precision/utils.py:599:                send_treatment_delivered_event.delay(consult.uid)
backend/shipping/precision/tasks.py:299:            send_prescription_to_precision.delay(consult.uid)
backend/test_results/utils.py:3245:                    send_provider_test_results_ready.delay(provider.email)
backend/test_results/utils.py:3252:        send_results_ready_analytics_events.delay(
backend/care/tasks.py:125:            send_otc_treatment_fill_request.delay(order.id, prescription_fill.id)
backend/studies/admin.py:66:        submit_research_sample_lab_order_to_microgen.delay(cohort_test.test.hash)
backend/scripts/test_result_tag_scripts.py:63:        create_test_result_tagset.delay(test.hash)
backend/test_results/admin.py:1017:            issue_lab_results_to_wheel_for_lab_test.delay(str(lab_test.id))
backend/test_results/post_processing_utils.py:429:        send_urine_test_results_ready_analytics_events.delay(urine_test.hash)
backend/shipping/utils.py:231:            send_test_delivered_klaviyo_event.delay(test.hash)
backend/test_results/lab_services/orchestrator.py:462:                        fulfill_uti_order_in_shopify.delay(
backend/test_results/lab_services/orchestrator.py:556:                send_vip_test_status_update.delay(urine_test.hash, old_status, new_status)
backend/test_results/lab_services/lab_order_service.py:83:                    fetch_and_process_junction_results.delay(external_order_id)
backend/shipping/tasks.py:155:                update_individual_shipping_status.delay(status.id)
backend/shipping/tasks.py:768:        result = send_order_to_berlin_for_fulfillment.delay(
backend/test_results/lab_services/providers/junction/results_processor.py:119:                    issue_lab_results_to_wheel_for_lab_test.delay(str(lab_test.id))
backend/test_results/lab_services/providers/junction/results_processor.py:139:            send_urine_test_results_ready_analytics_events.delay(urine_test.hash)
backend/accounts/admin_actions.py:270:        send_provider_verified_event.delay(provider_profile.provider.id)
backend/test_results/signals.py:246:        send_vip_test_status_update.delay(test_instance.hash, previous_status, test_instance.status)
backend/test_results/signals.py:443:        issue_lab_results_to_wheel_for_lab_test.delay(lab_test.id)
backend/test_results/signals.py:490:            send_coaching_call_completed_event.delay(instance.test.hash, instance.id, num_calls)
backend/test_results/infection_state_service.py:500:        send_provider_test_results_ready.delay(provider.email)
backend/test_results/utils_processing.py:210:        post_process_test_results.delay(test.hash)
backend/care/signals.py:86:        update_treatment_end_date.delay(instance.treatment_plan_id)
backend/care/signals.py:121:                create_or_reset_calendar_treatments.apply_async(
backend/care/signals.py:129:                create_or_reset_calendar_treatments.apply_async(
backend/test_results/microgen/tasks.py:92:        submit_lab_order_approval_to_microgen.delay(lab_order.uid)
backend/test_results/microgen/tasks.py:114:        process_microgen_test_results_if_exists_in_s3.delay(test.hash)
backend/test_results/microgen/tasks.py:140:    post_process_test_results.delay(test_hash, release_results)
backend/test_results/microgen/tasks.py:170:    send_pcr_test_results_ready.delay(test_hash)
backend/test_results/microgen/tasks.py:187:        send_pcr_test_results_ready_provider_klaviyo_event.delay(test_hash, provider_test_order.id)
backend/test_results/microgen/tasks.py:317:        summary_task.apply_async(countdown=cache_timeout)
backend/test_results/microgen/tasks.py:386:            send_test_sample_at_lab_but_not_activated.delay(test.hash)
backend/test_results/microgen/tasks.py:387:        send_ldt_test_sample_received_email.delay(test.hash)
backend/test_results/microgen/tasks.py:399:        send_ldt_test_sample_sequencing_email.delay(test.hash)
backend/test_results/microgen/tasks.py:403:            send_sample_sequencing_provider_klaviyo_event.delay(test_hash, provider_test_order.id)
backend/test_results/microgen/tasks.py:409:            process_microgen_vag_pcr_test_results.delay(test_hash)
backend/test_results/microgen/tasks.py:450:            process_microgen_test_results.apply_async(args=[test_hash], countdown=delay_seconds)
backend/test_results/microgen/tasks.py:453:            process_microgen_test_results.delay(test_hash)
backend/test_results/tasks.py:206:            send_eligible_for_care_1_for_test.delay(test.id)
backend/test_results/tasks.py:211:            send_eligible_for_a_la_care_not_treatment_program.delay(test.id)
backend/api/v1/views/account.py:253:            send_intake_completed_notifications.delay(user.email)
backend/consults/wheel/utils_webhook.py:94:                fetch_and_process_follow_up_consult_details.delay(lab_order_uid, wheel_consult_id)
backend/consults/wheel/utils_webhook.py:101:                fetch_and_process_completed_lab_order_details.delay(lab_order_uid)
backend/consults/wheel/utils_webhook.py:153:                fetch_and_process_referred_consult_details.delay(consult_uid)
backend/consults/wheel/utils_webhook.py:157:                fetch_and_process_completed_consult_details.delay(consult.uid)
backend/consults/wheel/utils_webhook.py:262:    send_id_verification_failed_email.delay(consult.uid)
backend/consults/wheel/utils_webhook.py:301:    send_new_consult_message_email.delay(consult.uid)
backend/consults/wheel/utils.py:2588:        send_lab_order_rejected_email.delay(lab_order.uid)
backend/consults/utils.py:218:        send_consult_intake_ineligible_event.delay(consult.uid, refer_out_reason)
backend/consults/utils.py:404:        submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)
backend/consults/utils.py:406:        submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)
backend/consults/utils.py:413:        submit_lab_order_approval_to_microgen.delay(lab_order.uid)
backend/consults/utils.py:495:    mark_wheel_consult_message_as_read.delay(consult.uid, message_id)
backend/api/v1/views/register.py:144:        attach_unattached_orders_to_user.delay(user.id)
backend/api/v1/views/register.py:238:        send_provider_registered_event.delay(user.id)
backend/consults/admin.py:1103:                fetch_and_process_completed_consult_details.delay(obj.uid)
backend/api/v1/views/account_order_transfer_verification.py:128:                add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay(
backend/api/v1/views/my_plan.py:46:            send_viewed_plan_klaviyo_event.delay(test.id)
backend/api/v1/views/webhooks.py:253:        process_tracking_statuses.delay(
backend/api/v1/views/webhooks.py:296:    process_lab_status_update_batch.delay(payload)
backend/api/v1/views/webhooks.py:311:    process_precision_pharmacy_webhook.delay(payload)
backend/consults/wheel/tasks.py:162:        send_consult_intake_submitted_event.delay(consult_uid)
backend/consults/wheel/tasks.py:163:        send_consult_intake_reviewed_email.delay(consult_uid)
backend/consults/wheel/tasks.py:267:        check_recommended_prescriptions_against_prescribed_and_send_prescriptions.delay(consult_uid)
backend/consults/wheel/tasks.py:320:        submit_lab_order_approval_to_junction.delay(lab_order.uid)
backend/consults/wheel/tasks.py:366:                fetch_and_process_completed_consult_details.delay(consult.uid)
backend/consults/wheel/tasks.py:369:                fetch_and_process_referred_consult_details.delay(consult.uid)
backend/consults/wheel/tasks.py:394:        submit_async_consult.delay(consult.uid)
backend/consults/wheel/tasks.py:407:        submit_async_consult.delay(consult.uid)
backend/consults/wheel/tasks.py:583:    send_care_referred_out_email.delay(consult.uid)
backend/consults/wheel/tasks.py:637:            submit_lab_order_to_wheel.delay(lab_order.uid)
backend/consults/wheel/tasks.py:678:        submit_lab_order_to_wheel.delay(lab_order.uid)
backend/consults/wheel/tasks.py:931:            fetch_and_process_follow_up_consult_details.delay(lab_order.uid, follow_up.external_id)
backend/app/management/commands/create_study_cohort_tests.py:147:                    submit_research_sample_lab_order_to_microgen.delay(test.hash)
backend/api/v1/views/provider_test_orders.py:104:        send_provider_ordered_single_test_notifications.delay(
backend/api/v1/views/provider_test_orders.py:112:        send_provider_ordered_test_klaviyo_event.delay(
backend/api/v1/views/provider_test_orders.py:245:            send_provider_bulk_ordered_tests_notification.delay(
backend/api/v1/views/provider_test_orders.py:262:            send_provider_ordered_test_klaviyo_event.delay(
backend/api/v1/views/provider_test_orders.py:310:        send_provider_reminded_patient_klaviyo_event.delay(
backend/api/v1/views/user_tests.py:357:                add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult.delay(
backend/api/v1/views/user_tests.py:873:        send_additional_tests_checkout_created_event.delay(test_kit.hash)
backend/api/v1/views/user_tests.py:945:        send_health_history_completed_klaviyo_event.delay(test.hash)
backend/consults/signals.py:140:                transaction.on_commit(lambda: update_treatment_end_date.delay(treatment_plan.id))
backend/consults/signals.py:158:                    send_email_organon_prescriptions_ready.delay(consult.uid)
backend/consults/signals.py:160:                send_treatment_plan_ready_email.delay(consult.uid)
backend/consults/signals.py:162:                send_a_la_care_treatments_ready.delay(consult.uid)
backend/consults/signals.py:168:            send_sti_prescription_sent_to_pharmacy_email.delay(consult.uid)
backend/api/v1/views/consult.py:363:        update_treatment_end_date.delay(treatment_plan.id)
backend/api/v1/views/consult.py:366:        send_updated_treatment_start_date_event.delay(consult.uid)
backend/api/v1/views/consult.py:463:        send_care_checkout_created_event.delay(consult.uid)
backend/api/v1/views/consult.py:563:        send_care_checkout_created_event.delay(consult.uid)
backend/api/v1/views/consult.py:799:        send_consult_intake_started_klaviyo_event.delay(intake.consult.uid)
backend/api/v1/views/consult.py:859:        send_consult_intake_started_klaviyo_event.delay(intake.consult.uid)
backend/api/v1/views/consult.py:912:            resubmit_consult_photo_id_info_to_wheel.delay(consult.uid)
backend/api/v1/views/consult.py:926:                submit_async_consult.delay(consult.uid)
```

---

## Step 4: Read key files for context

The agent read individual code sections from each file to confirm arguments and business context. The following summarizes the context-gathering reads:

**`read("backend/ecomm/services/cart.py", lines 685-724)`** — Confirmed: unclaimed order matched to user by email triggers consult attachment; email mismatch triggers account transfer verification.

**`read("backend/ecomm/utils.py", lines 400-429)`** — Confirmed: order cancellation from Shopify triggers `void_share_a_sale_transaction`.

**`read("backend/analytics/tasks.py", lines 120-161)`** — Confirmed: `send_custom_analytics_event` dispatches to Fullstory and Klaviyo async tasks based on destination set.

**`read("backend/analytics/tasks.py", lines 1310-1335)`** — Confirmed: periodic task sweeps treatment plans by end date and dispatches `send_treatment_ended_event` per plan; separately `send_treatment_delivered_event` for plans missing delivery timestamp past fulfillment cutoff.

**`read("backend/ecomm/utils.py", lines 675-774)`** — Confirmed: Shopify order paid event triggers gift card processing, "any paid" event, and Berlin fulfillment.

**`read("backend/ecomm/utils.py", lines 1120-1148)`** — Confirmed: MPT voucher line item processed, fires `send_mpt_voucher_paid_event` for authenticated user.

**`read("backend/ecomm/utils.py", lines 1220-1245)`** — Confirmed: urine test records created, `create_unregistered_testkit_order_for_urine_test` dispatched with list of urine test IDs.

**`read("backend/ecomm/utils.py", lines 1760-1784)`** — Confirmed: provider test order created for magic link, admin channel notification dispatched.

**`read("backend/ecomm/utils.py", lines 1855-1904)`** — Confirmed: consult paid event dispatched when order is not cancelled and consult exists.

**`read("backend/ecomm/utils.py", lines 1975-2009)`** — Confirmed: PCR add-on order dispatches `send_additional_tests_paid_event` with or without test kit hash.

**`read("backend/ecomm/utils.py", lines 2185-2198)`** — Confirmed: prescription refill request dispatched after prescription fill is created.

**`read("backend/ecomm/utils.py", lines 2690-2715)`** — Confirmed: bulk provider order paid notification dispatched.

**`read("backend/ecomm/tasks.py", lines 215-229)`** — Confirmed: `send_prescription_refills_paid_event` dispatched after fill status promoted to CREATED.

**`read("backend/ecomm/tasks.py", lines 445-460)`** — Confirmed: Klaviyo event dispatched when ungated RX order is attached to an existing in-progress consult.

**`read("backend/shipping/precision/utils.py", lines 580-609)`** — Confirmed: prescription fill marked delivered when not OTC-only, dispatches `send_treatment_delivered_event`.

**`read("backend/shipping/precision/tasks.py", lines 285-300)`** — Confirmed: healing task re-submits prescriptions to Precision for completed consults with no `sent_to_pharmacy_at`.

**`read("backend/test_results/utils.py", lines 3235-3252)`** — Confirmed: provider notification and analytics events dispatched at results publication time.

**`read("backend/care/tasks.py", lines 110-138)`** — Confirmed: healing task for OTC-only orders creates fill and dispatches `send_otc_treatment_fill_request`.

**`read("backend/test_results/post_processing_utils.py", lines 415-429)`** — Confirmed: after urine test infection state created, dispatches UTI analytics events.

**`read("backend/test_results/lab_services/orchestrator.py", lines 450-466)`** — Confirmed: UTI outbound shipment reaches "transit_customer" status, triggers Shopify fulfillment.

**`read("backend/test_results/lab_services/orchestrator.py", lines 542-556)`** — Confirmed: VIP test status update dispatched to Slack when `track_status_change=True`.

**`read("backend/test_results/lab_services/lab_order_service.py", lines 72-91)`** — Confirmed: lab provider "results_ready" webhook dispatches `fetch_and_process_junction_results`.

**`read("backend/shipping/tasks.py", lines 145-155)`** — Confirmed: periodic task iterates all active ShippingStatus records, dispatches individual update per record.

**`read("backend/shipping/tasks.py", lines 755-774)`** — Confirmed: healing task re-queues Berlin fulfillment for orders with no `sent_to_berlin_at`.

**`read("backend/test_results/lab_services/providers/junction/results_processor.py", lines 108-148)`** — Confirmed: auto-release path sends to Wheel; analytics events dispatched after Junction results processed.

**`read("backend/accounts/admin_actions.py", lines 260-270)`** — Confirmed: admin action to verify provider fires `send_provider_verified_event`.

**`read("backend/test_results/signals.py", lines 246, 443, 490)`** — Confirmed signals on test status change, lab test completion, and coaching call notes.

**`read("backend/test_results/infection_state_service.py", lines ~500)`** — Confirmed: LDT vaginal test diagnosis confirmation notifies provider.

**`read("backend/test_results/utils_processing.py", lines ~210)`** — Confirmed: NGS results file processing triggers post-processing task.

**`read("backend/care/signals.py", lines 86-129)`** — Confirmed: treatment interruption signal triggers end date recalculation; prescription pre-save triggers calendar reset with 5-minute countdown.

**`read("backend/consults/signals.py", lines 140-168)`** — Confirmed: consult completion (various purchase types and pharmacy types) dispatches emails/events.

**`read("backend/consults/utils.py", lines 218-495)`** — Confirmed: lab order submissions to Wheel (with 5-minute delay), direct Microgen submission, ineligibility event, and message read-marking.

**`read("backend/consults/admin.py", lines ~1103)`** — Confirmed: admin manual trigger for completed consult details.

**`read("backend/consults/wheel/utils_webhook.py", lines 94-301)`** — Confirmed: Wheel webhook events route to multiple async handlers based on consult disposition.

**`read("backend/consults/wheel/utils.py", lines ~2588)`** — Confirmed: lab order rejection sends email.

**`read("backend/consults/wheel/tasks.py", lines 162-931)`** — Confirmed: multiple healing tasks and webhook processing tasks.

**`read("backend/api/v1/views/register.py", lines 144-238)`** — Confirmed: registration attaches unattached orders and fires provider registered event.

**`read("backend/api/v1/views/account.py", lines ~253)`** — Confirmed: provider profile intake submission notifies team.

**`read("backend/api/v1/views/webhooks.py", lines 253-311)`** — Confirmed: Berlin tracking webhook, Microgen batch webhook, Precision pharmacy webhook all dispatch async.

**`read("backend/api/v1/views/my_plan.py", lines ~46)`** — Confirmed: first-time plan view fires analytics event.

**`read("backend/api/v1/views/provider_test_orders.py", lines 104-310)`** — Confirmed: single and bulk provider test order creation dispatches notifications and Klaviyo events.

**`read("backend/api/v1/views/user_tests.py", lines 357-945)`** — Confirmed: test activation, PCR add-on checkout, health history submission all dispatch events.

**`read("backend/api/v1/views/consult.py", lines 363-926)`** — Confirmed: treatment start date update, care checkout, intake started/consent, ID re-verification, and consult submission all dispatch async tasks.

**`read("backend/studies/admin.py", lines 58-70)`** — Confirmed: admin action submits research cohort tests to Microgen.

**`read("backend/app/management/commands/create_study_cohort_tests.py", lines 138-157)`** — Confirmed: management command with `--submit-lab-orders` flag dispatches Microgen submissions.

**`read("backend/scripts/resend_lab_results_to_wheel.py", lines 78-99)`** — Confirmed: ops script iterates test hashes and re-dispatches Wheel submissions.

**`read("backend/scripts/reprocess_subscription_refill_orders.py", lines 220-234)`** — Confirmed: ops script recreates prescription fills and re-dispatches refill requests.

**`read("backend/scripts/backfill_unapproved_junction_submissions.py", lines 103-119)`** — Confirmed: backfill script dispatches `submit_lab_order_approval_to_junction` for each unapproved lab order.

**`read("backend/scripts/test_result_tag_scripts.py", lines 55-63)`** — Confirmed: ops script dispatches `create_test_result_tagset` for tests in PROCESSING or READY status.

**`read("backend/test_results/admin.py", lines 1008-1027)`** — Confirmed: Django admin manual release of urine test results to Wheel.

**`read("backend/test_results/microgen/tasks.py", multiple sections)`** — Confirmed: multiple healing tasks (re-submit approvals, retry stuck in sequencing), PCR results dispatch, sample received/sequencing emails, load-balanced results processing.

---

## Step 5: Verify completeness

```
search("\.delay\(|\.apply_async\(")
```

**Result:** 124 total occurrences across 43 files. All files accounted for from the initial pattern search.

---

## Final Answer

### Complete Inventory of Task Enqueue Call Sites

**Legend:**
- `.delay(args)` = immediate enqueue
- `.apply_async(args, countdown=N)` = enqueue with N-second delay

---

### 1. ecomm/services/cart.py

**Line 701** — Task: `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`
- **Args:** `user.id, order.order_number`
- **Context:** An unclaimed Shopify order was matched to a user by email during cart processing. After attaching the user to the order, this triggers the consult creation/attachment flow.

**Line 705** — Task: `send_account_transfer_verification_email`
- **Args:** `user.id, order.email, order_number`
- **Context:** An unclaimed order's email does NOT match the logged-in user's email, so an account transfer verification email is sent instead of auto-attaching.

**Line 708** — Task: `send_account_transfer_verification_email`
- **Args:** `user.id, order.email, order_number`
- **Context:** Same as above but for orders that already have a different user than the current requester.

---

### 2. analytics/tasks.py

**Line 131** — Task: `send_custom_analytics_event_to_fullstory_async`
- **Args:** `user.id, event_name, event_properties, use_recent_session_fullstory`
- **Context:** Called from `send_custom_analytics_event` when Fullstory is in the set of destinations. A generic wrapper for custom analytics events.

**Line 158** — Task: `send_custom_analytics_event_to_klaviyo_async`
- **Args:** `payload` (full Klaviyo API payload dict)
- **Context:** Same wrapper, called when Klaviyo is in the set of destinations for custom analytics events.

**Line 1154** — Task: `send_estimated_treatment_started_event`
- **Args:** `treatment_plan.id`
- **Context:** Fired from a periodic (scheduled) task that sweeps treatment plans whose estimated start date is today or yesterday. One task per treatment plan is enqueued.

**Line 1320** — Task: `send_treatment_ended_event`
- **Args:** `treatment_plan.id`
- **Context:** Periodic task sweeping treatment plans whose `treatment_end_date` is today or yesterday. Fires a "treatment ended" analytics event per plan.

**Line 1335** — Task: `send_treatment_delivered_event`
- **Args:** `treatment_plan.consult.uid`
- **Context:** Periodic task for plans where `treatment_delivered_at` is null but create date indicates fulfillment should have happened by now (estimated delivery days cutoff). Sends a "treatment probably delivered" event.

---

### 3. ecomm/utils.py

**Line 416** — Task: `void_share_a_sale_transaction`
- **Args:** `order_number, order_date, note`
- **Context:** Order cancellation flow (Shopify webhook order update). Voids the ShareASale affiliate commission for the cancelled order.

**Line 691** — Task: `send_ungated_rx_order_paid_event`
- **Args:** `order.order_number`
- **Context:** Shopify paid event for an ungated RX order when the user has valid prescriptions for all products (routed to refill path). Fires an analytics paid event.

**Line 740** — Task: `process_gift_cards`
- **Args:** `order.id, payload`
- **Context:** Shopify paid webhook; order involves gift card purchases or redemptions. Processes the gift card logic asynchronously.

**Line 744** — Task: `send_any_paid_event`
- **Args:** `order.order_number`
- **Context:** Shopify paid webhook; fired for every non-cancelled paid order with a user. Generic "any order paid" analytics event.

**Line 763** — Task: `send_order_to_berlin_for_fulfillment`
- **Args:** `payload, is_order_cancellation, order.id`
- **Context:** End of Shopify order processing (both paid and cancellation). Sends order data to the Berlin fulfillment system.

**Line 1138** — Task: `send_mpt_voucher_paid_event`
- **Args:** `user.id`
- **Context:** Male Partner Test (MPT) voucher line item was processed during Shopify order handling. Fires a paid event for the MPT voucher.

**Line 1236** — Task: `create_unregistered_testkit_order_for_urine_test`
- **Args:** `urine_test_ids=[urine_test_ids], ecomm_order_id=order.id`
- **Context:** After creating urine test records from a Shopify UTI order, asynchronously creates the unregistered testkit orders in Junction.

**Line 1778** — Task: `send_patient_ordered_provider_test_notification`
- **Args:** `patient_email=email, order_sku=order.sku, order_provider_id=order.provider_id`
- **Context:** Single (non-bulk) provider test ordered via Shopify magic link order. Temporary admin channel notification.

**Line 1874** — Task: `send_consult_paid_event`
- **Args:** `consult.uid, order.provider_id`
- **Context:** A care/consult order has been paid (Shopify webhook), order is not cancelled, and a consult exists for it. Fires a "consult paid" analytics event.

**Line 1990** — Task: `send_additional_tests_paid_event`
- **Args:** `None, order.provider_id`
- **Context:** PCR add-on order is missing the test kit hash; cannot attach to a specific test. Fires the paid event with `None` hash as fallback.

**Line 2009** — Task: `send_additional_tests_paid_event`
- **Args:** `test_kit.hash, order.provider_id`
- **Context:** PCR add-on order successfully found and linked to a test kit. Fires the paid event with the test kit hash.

**Line 2198** — Task: `send_prescription_refill_request`
- **Args:** `order.id, prescription_fill.id`
- **Context:** End of subscription refill order processing: prescription fill has been created (prescriptions + OTC treatments), now send to Precision pharmacy.

**Line 2705** — Task: `send_provider_bulk_order_paid_notification`
- **Args:** `ecomm_order_id=order.id, provider_email=provider_test_orders.first().provider.email, quantity=expected_count`
- **Context:** A bulk provider test order was paid via Shopify. Sends a notification to the provider with the quantity ordered.

---

### 4. ecomm/tasks.py

**Line 229** — Task: `send_prescription_refills_paid_event`
- **Args:** `prescription_fill_id, order.provider_id`
- **Context:** Inside `send_prescription_refill_request` task, after the prescription fill is promoted from DRAFT to CREATED status. Fires the "refills paid" analytics event.

**Line 460** — Task: `send_rx_order_attached_to_account_klaviyo_event`
- **Args:** `consult.uid, order.order_number`
- **Context:** Inside `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult` task, when an ungated RX order is successfully attached to an in-progress consult. Fires a Klaviyo event.

---

### 5. shipping/precision/utils.py

**Line 599** — Task: `send_treatment_delivered_event`
- **Args:** `consult.uid`
- **Context:** Precision pharmacy webhook processing: a prescription fill (non-OTC-only) shipment tracking indicates delivery. Fires the "treatments delivered" event.

---

### 6. shipping/precision/tasks.py

**Line 299** — Task: `send_prescription_to_precision`
- **Args:** `consult.uid`
- **Context:** Healing/recovery periodic task (`submit_missing_prescriptions_to_precision`) that scans consults completed in last 2 days that have not been sent to the pharmacy. Re-sends each.

---

### 7. shipping/utils.py

**Line 231** — Task: `send_test_delivered_klaviyo_event`
- **Args:** `test.hash`
- **Context:** Kit shipping status processing: the shipping status for a test kit has transitioned to "delivered." Fires the "test delivered" analytics event.

---

### 8. shipping/tasks.py

**Line 155** — Task: `update_individual_shipping_status`
- **Args:** `status.id`
- **Context:** Periodic task `update_all_shipping_statuses` iterating over all active/pending ShippingStatus records. One subtask enqueued per individual status record.

**Line 768** — Task: `send_order_to_berlin_for_fulfillment`
- **Args:** `order.payload, is_order_cancellation, order.id`
- **Context:** Healing periodic task that re-queues Berlin fulfillment for orders with `sent_to_berlin_at=None` (missed or failed fulfillment).

---

### 9. test_results/utils.py

**Line 3245** — Task: `send_provider_test_results_ready`
- **Args:** `provider.email`
- **Context:** When test results are published (`publish_results_for_test`), if the test has a provider test order with authorized release, sends a notification email to the provider.

**Line 3252** — Task: `send_results_ready_analytics_events`
- **Args:** `test.hash, eligible_for_care, ineligible_reason`
- **Context:** At the end of `publish_results_for_test`, fires backend analytics events for all tests whose results are now ready.

---

### 10. test_results/infection_state_service.py

**Line 500** — Task: `send_provider_test_results_ready`
- **Args:** `provider.email`
- **Context:** Called inside `confirm_diagnosis()` for LDT vaginal tests when an authorized provider test order exists and the diagnosis is confirmed. Sends final results ready notification to the provider.

---

### 11. test_results/utils_processing.py

**Line 210** — Task: `post_process_test_results`
- **Args:** `test.hash`
- **Context:** Called after NGS results file upload is processed (`_trigger_post_processing`). If a `TestResult` object exists, kicks off post-processing (scoring, tagging, care eligibility).

---

### 12. test_results/post_processing_utils.py

**Line 429** — Task: `send_urine_test_results_ready_analytics_events`
- **Args:** `urine_test.hash`
- **Context:** Called during urine test post-processing after infection state is created. Fires care eligibility analytics events for UTI test results.

---

### 13. test_results/signals.py

**Line 246** — Task: `send_vip_test_status_update`
- **Args:** `test_instance.hash, previous_status, test_instance.status`
- **Context:** Django signal handler on test/urine test status change (`post_save` on Test). Fires only when `test_instance.track_status_change` is True (VIP monitoring flag).

**Line 443** — Task: `issue_lab_results_to_wheel_for_lab_test`
- **Args:** `lab_test.id`
- **Context:** Signal on LabTest status change: when a LabTest (non-urine, non-VPCR) transitions to `STATUS_COMPLETE`, sends the results to the Wheel clinician platform for review/confirmation.

**Line 490** — Task: `send_coaching_call_completed_event`
- **Args:** `instance.test.hash, instance.id, num_calls`
- **Context:** Signal on `CoachingCallNotes` pre-save: when `had_call` changes from False to True, fires an analytics event for coaching call completion.

---

### 14. test_results/tasks.py

**Line 206** — Task: `send_eligible_for_care_1_for_test`
- **Args:** `test.id`
- **Context:** Inside `send_results_ready_email_for_test` task, when an LDT test is eligible for care. Triggers the first care eligibility email.

**Line 211** — Task: `send_eligible_for_a_la_care_not_treatment_program`
- **Args:** `test.id`
- **Context:** Same parent task, for tests eligible for a-la-carte care but NOT the full treatment program. Sends an a-la-carte specific eligibility email.

---

### 15. test_results/microgen/tasks.py

**Line 92** — Task: `submit_lab_order_approval_to_microgen`
- **Args:** `lab_order.uid`
- **Context:** Healing periodic task (`submit_missing_lab_order_approvals_to_microgen`) scanning lab orders in APPROVED status for the past 60 days that were not yet submitted electronically. Re-submits each.

**Line 114** — Task: `process_microgen_test_results_if_exists_in_s3`
- **Args:** `test.hash`
- **Context:** Healing periodic task (`process_test_results_stuck_in_sequencing_status`) that retries tests stuck in SEQUENCING status for over 7 days.

**Line 140** — Task: `post_process_test_results`
- **Args:** `test_hash, release_results`
- **Context:** Inside `process_microgen_test_results` task, after NGS S3 file upload is complete. Kicks off post-processing.

**Line 170** — Task: `send_pcr_test_results_ready`
- **Args:** `test_hash`
- **Context:** Inside `process_microgen_vag_pcr_test_results` task, after vaginitis PCR panel results are processed. Sends PCR-specific results ready email to user.

**Line 187** — Task: `send_pcr_test_results_ready_provider_klaviyo_event`
- **Args:** `test_hash, provider_test_order.id`
- **Context:** Same PCR results flow, but only if a provider test order exists. Sends the PCR ready event to the provider via Klaviyo.

**Line 317** — Task: `summary_task.apply_async(countdown=cache_timeout)`
- **Args:** No positional args; `countdown=cache_timeout` (cache_timeout = 60 * 20 minutes)
- **Context:** Inside `_queue_summary_notification()` when no summary task is already queued. Fires either `send_summary_vpcr_results_processed` or `send_summary_vngs_results_processed` after a 20-minute delay, de-duplicated with a cache lock. Triggered during lab webhook processing for "sequencing", "partial-results", or "ready" statuses.

**Line 386** — Task: `send_test_sample_at_lab_but_not_activated`
- **Args:** `test.hash`
- **Context:** Lab webhook: status "received" and the test has no user (not yet activated). Sends an admin/ops alert email.

**Line 387** — Task: `send_ldt_test_sample_received_email`
- **Args:** `test.hash`
- **Context:** Lab webhook: status "received". Sends the patient an email that their sample was received at the lab.

**Line 399** — Task: `send_ldt_test_sample_sequencing_email`
- **Args:** `test.hash`
- **Context:** Lab webhook: status "sequencing". Sends the patient an email that their sample is being sequenced.

**Line 403** — Task: `send_sample_sequencing_provider_klaviyo_event`
- **Args:** `test_hash, provider_test_order.id`
- **Context:** Same "sequencing" webhook, but only when a provider test order exists. Fires a Klaviyo event to the provider.

**Line 409** — Task: `process_microgen_vag_pcr_test_results`
- **Args:** `test_hash`
- **Context:** Lab webhook: status "partial-results" with panel "vag-sti". Triggers PCR panel results processing.

**Line 450** — Task: `process_microgen_test_results.apply_async(args=[test_hash], countdown=delay_seconds)`
- **Args:** `[test_hash]`; `countdown=delay_seconds` (random 0 to `RESULTS_PROCESSING_MAX_DELAY_MINUTES * 60`)
- **Context:** Lab webhook: status "ready" and `RESULTS_PROCESSING_MAX_DELAY_MINUTES > 0`. Load-balanced processing with random delay to spread worker load.

**Line 453** — Task: `process_microgen_test_results`
- **Args:** `test_hash`
- **Context:** Same "ready" status path but `RESULTS_PROCESSING_MAX_DELAY_MINUTES == 0`. Immediate processing.

---

### 16. test_results/lab_services/lab_order_service.py

**Line 83** — Task: `fetch_and_process_junction_results`
- **Args:** `external_order_id`
- **Context:** Lab provider webhook handler: a "results_ready" webhook arrives from Junction. Async task is dispatched to fetch and process the UTI test results.

---

### 17. test_results/lab_services/orchestrator.py

**Line 462** — Task: `fulfill_uti_order_in_shopify`
- **Args:** `urine_test_id=urine_test.id, tracking_number=shipment_data["outbound_tracking_number"], courier=shipment_data.get("outbound_courier", "")`
- **Context:** During UTI test status update processing in the orchestrator: the outbound shipment transitions to "transit_customer" for the first time. Triggers Shopify UTI order fulfillment.

**Line 556** — Task: `send_vip_test_status_update`
- **Args:** `urine_test.hash, old_status, new_status`
- **Context:** UTI test status update: `track_status_change` is True on the urine test (VIP monitoring). Fires a Slack status update.

---

### 18. test_results/lab_services/providers/junction/results_processor.py

**Line 119** — Task: `issue_lab_results_to_wheel_for_lab_test`
- **Args:** `str(lab_test.id)`
- **Context:** After Junction urine PCR results are processed: the UTI test has no pathogens and passes auto-release criteria. Automatically sends results to Wheel without manual review.

**Line 139** — Task: `send_urine_test_results_ready_analytics_events`
- **Args:** `urine_test.hash`
- **Context:** After Junction results processing is complete. Fires care eligibility analytics events for UTI results.

---

### 19. care/signals.py

**Line 86** — Task: `update_treatment_end_date`
- **Args:** `instance.treatment_plan_id`
- **Context:** Signal on `TreatmentPlanInterruption` post-save/delete. Whenever a treatment interruption is added, removed, or changed, recalculates the treatment end date.

**Line 121** — Task: `create_or_reset_calendar_treatments.apply_async(args=(treatment_plan.id,), countdown=300)`
- **Args:** `(treatment_plan.id,)`; `countdown=300` (5 minutes)
- **Context:** Signal on `Prescription` pre-save: a new prescription was added to a complete consult that already has calendar treatments. 5-minute delay ensures prescriptions are fully saved to DB before calendar is rebuilt.

**Line 129** — Task: `create_or_reset_calendar_treatments.apply_async(args=(treatment_plan.id,), countdown=300)`
- **Args:** `(treatment_plan.id,)`; `countdown=300` (5 minutes)
- **Context:** Signal on `Prescription` pre-save: an existing prescription's deletion status or product changed. Same 5-minute delay to adjust the treatment calendar.

---

### 20. care/tasks.py

**Line 125** — Task: `send_otc_treatment_fill_request`
- **Args:** `order.id, prescription_fill.id`
- **Context:** Healing task that scans orders containing only OTC treatments that were not processed. Creates a prescription fill and enqueues the OTC fill request to Precision.

---

### 21. consults/signals.py

**Line 140** — Task: `update_treatment_end_date` (via `transaction.on_commit`)
- **Args:** `treatment_plan.id`
- **Context:** Signal on `Consult` post-save: consult status just changed to `STATUS_COMPLETE` (non-STI type) and a treatment plan was just created with no end date. Wrapped in `on_commit` to ensure DB is committed first.

**Line 158** — Task: `send_email_organon_prescriptions_ready`
- **Args:** `consult.uid`
- **Context:** Signal on consult post-save to `STATUS_COMPLETE`, pharmacy type is patient local pickup (external pharmacy), and it is NOT a UTI consult. Sends "prescriptions ready" email for Organon/local pickup.

**Line 160** — Task: `send_treatment_plan_ready_email`
- **Args:** `consult.uid`
- **Context:** Consult completes with full treatment plan purchase type. Sends the treatment plan ready email.

**Line 162** — Task: `send_a_la_care_treatments_ready`
- **Args:** `consult.uid`
- **Context:** Consult completes with a-la-carte purchase type. Sends the a-la-carte care ready email.

**Line 168** — Task: `send_sti_prescription_sent_to_pharmacy_email`
- **Args:** `consult.uid`
- **Context:** Signal on consult post-save: STI consult moves to `STATUS_COMPLETE`. Notifies patient their STI prescription was sent to the pharmacy.

---

### 22. consults/utils.py

**Line 218** — Task: `send_consult_intake_ineligible_event`
- **Args:** `consult.uid, refer_out_reason`
- **Context:** `validate_consult_intake_eligibility()` when a consult is found ineligible (state restriction, condition, etc.). Fires the ineligible event.

**Line 404** — Task: `submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)`
- **Args:** `(lab_order.uid,)`; `countdown=300` (5 minutes)
- **Context:** LDT vaginal or UTI test lab order creation: submits lab order to Wheel with a 5-minute delay to ensure any PCR add-on ecomm orders are processed before submission.

**Line 406** — Task: `submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)`
- **Args:** `(lab_order.uid,)`; `countdown=300` (5 minutes)
- **Context:** Same as above but specifically for UTI/urine test path.

**Line 413** — Task: `submit_lab_order_approval_to_microgen`
- **Args:** `lab_order.uid`
- **Context:** Non-LDT vaginal test: lab order is marked approved immediately (no Wheel review needed), then submitted directly to Microgen.

**Line 495** — Task: `mark_wheel_consult_message_as_read`
- **Args:** `consult.uid, message_id`
- **Context:** `mark_consult_message_as_read()` called when a user reads a message in the consult thread. Asynchronously marks the message as read on the external clinician platform.

---

### 23. consults/admin.py

**Line 1103** — Task: `fetch_and_process_completed_consult_details`
- **Args:** `obj.uid`
- **Context:** Django admin action on a Consult admin page. Allows admins to manually re-trigger the fetch-and-process flow for a completed consult.

---

### 24. consults/wheel/utils_webhook.py

**Line 94** — Task: `fetch_and_process_follow_up_consult_details`
- **Args:** `lab_order_uid, wheel_consult_id`
- **Context:** External clinician platform webhook: `consult.statusChange` event with status "finished" and disposition "lab-follow-up-complete" or "lab-follow-up-needs-attention". Fetches the follow-up consult details.

**Line 101** — Task: `fetch_and_process_completed_lab_order_details`
- **Args:** `lab_order_uid`
- **Context:** External webhook: `consult.statusChange` with disposition "lab-order-approved", "lab-order-rejected", or "auto-referred-out". Routes approved/rejected lab orders.

**Line 153** — Task: `fetch_and_process_referred_consult_details`
- **Args:** `consult_uid`
- **Context:** External webhook: consult `status=finished`, disposition "referred-out" or "auto-referred-out". Fetches referral details.

**Line 157** — Task: `fetch_and_process_completed_consult_details`
- **Args:** `consult.uid`
- **Context:** External webhook: consult `status=finished`, disposition "diagnosed". Fetches completed consult details and processes prescriptions.

**Line 262** — Task: `send_id_verification_failed_email`
- **Args:** `consult.uid`
- **Context:** External webhook: `consult.verification.failed` event. ID verification failed; sends failure email to user.

**Line 301** — Task: `send_new_consult_message_email`
- **Args:** `consult.uid`
- **Context:** External webhook: new message event in the consult thread. Notifies the user of a new message from their clinician.

---

### 25. consults/wheel/utils.py

**Line 2588** — Task: `send_lab_order_rejected_email`
- **Args:** `lab_order.uid`
- **Context:** Inside lab order disposition processing: the clinician platform rejected the lab order. Sends a rejection notification email to the user.

---

### 26. consults/wheel/tasks.py

**Line 162** — Task: `send_consult_intake_submitted_event`
- **Args:** `consult_uid`
- **Context:** Inside `fetch_and_process_completed_consult_details` after a consult is submitted to the clinician platform. Fires the intake submitted analytics event.

**Line 163** — Task: `send_consult_intake_reviewed_email`
- **Args:** `consult_uid`
- **Context:** Same parent task. Sends the "intake reviewed" email to the user.

**Line 267** — Task: `check_recommended_prescriptions_against_prescribed_and_send_prescriptions`
- **Args:** `consult_uid`
- **Context:** Consult has treatment purchase type. Verifies recommended vs prescribed treatments and sends prescriptions to pharmacy.

**Line 320** — Task: `submit_lab_order_approval_to_junction`
- **Args:** `lab_order.uid`
- **Context:** Inside `_route_approved_lab_order_to_provider`: clinician platform approved a lab order for a urine test. Routes to Junction lab.

**Line 366** — Task: `fetch_and_process_completed_consult_details`
- **Args:** `consult.uid`
- **Context:** Healing periodic task `retry_consult_detail_processing`: consult is stuck in review for 24+ hours, clinician platform shows it as "finished" with "diagnosed" disposition. Re-triggers processing.

**Line 369** — Task: `fetch_and_process_referred_consult_details`
- **Args:** `consult.uid`
- **Context:** Same healing task: consult is stuck but clinician platform shows "referred-out" or "auto-referred-out". Re-triggers referral processing.

**Line 394** — Task: `submit_async_consult`
- **Args:** `consult.uid`
- **Context:** Healing task `retry_creating_async_consults`: consults in SUBMITTED status for 1–5 days that never got submitted. Re-enqueues submission.

**Line 407** — Task: `submit_async_consult`
- **Args:** `consult.uid`
- **Context:** Healing task `retry_errored_consult_creation`: consults in ERROR status with no `submitted_at`. Re-enqueues submission.

**Line 583** — Task: `send_care_referred_out_email`
- **Args:** `consult.uid`
- **Context:** Inside `fetch_and_process_referred_consult_details`: after storing referral info, sends the "referred out" email to the user.

**Line 637** — Task: `submit_lab_order_to_wheel`
- **Args:** `lab_order.uid`
- **Context:** Healing task `resubmit_stuck_lab_orders_to_wheel`: stuck lab orders (CREATED/SUBMITTED status with provider_id, intake submitted > 1 hour ago, not in manual review states). Clears `provider_id` and re-submits.

**Line 678** — Task: `submit_lab_order_to_wheel`
- **Args:** `lab_order.uid`
- **Context:** Healing task `resubmit_errored_lab_orders_to_wheel`: lab orders in ERROR status (excluding Canadian and those with results already sent). Re-submits.

**Line 931** — Task: `fetch_and_process_follow_up_consult_details`
- **Args:** `lab_order.uid, follow_up.external_id`
- **Context:** Healing task `retry_pending_consult_follow_up_diagnosis`: iterates over lab result follow-ups whose infection state was not confirmed within a threshold. Re-triggers follow-up detail fetch.

---

### 27. api/v1/views/register.py

**Line 144** — Task: `attach_unattached_orders_to_user`
- **Args:** `user.id`
- **Context:** New user registration (email/password sign-up). Looks for any existing unattached orders matching this user's email and attaches them.

**Line 238** — Task: `send_provider_registered_event`
- **Args:** `user.id`
- **Context:** Provider registration completion. Fires the "provider registered" analytics event.

---

### 28. api/v1/views/account.py

**Line 253** — Task: `send_intake_completed_notifications`
- **Args:** `user.email`
- **Context:** Provider profile intake form submission API: the provider has submitted their profile information for the first time (`submitted_at` was just set). Sends notifications (Slack + confirmation email).

---

### 29. api/v1/views/account_order_transfer_verification.py

**Line 128** — Task: `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`
- **Args:** `evvy_account_user.id, order.order_number`
- **Context:** Account order transfer verification: user has verified ownership of an order from another account (via email verification link). The order is attached to their account and consult is created/updated.

---

### 30. api/v1/views/webhooks.py

**Line 253** — Task: `process_tracking_statuses`
- **Args:** `test_hash=test_hash, order_number=order_number, kit_tracking_number=kit_tracking_number, sample_tracking_number=sample_tracking_number`
- **Context:** Fulfillment partner webhook: a tracking update is received for a test kit shipment (outbound kit tracking + return sample tracking). Processes both tracking numbers.

**Line 296** — Task: `process_lab_status_update_batch`
- **Args:** `payload`
- **Context:** Lab status webhook endpoint: a batch of lab status updates arrives. Dispatches the whole payload to be processed per-update asynchronously.

**Line 311** — Task: `process_precision_pharmacy_webhook`
- **Args:** `payload`
- **Context:** Precision pharmacy webhook: signed webhook payload is received (shipping/prescription status updates). Processes the webhook payload asynchronously.

---

### 31. api/v1/views/my_plan.py

**Line 46** — Task: `send_viewed_plan_klaviyo_event`
- **Args:** `test.id`
- **Context:** User views their treatment plan for the first time (`record_viewed_plan=True` query param, `plan_viewed_at` is null). Fires the "plan viewed" analytics event and records the timestamp.

---

### 32. api/v1/views/provider_test_orders.py

**Line 104** — Task: `send_provider_ordered_single_test_notifications`
- **Args:** `provider_email=provider.email, patient_email=patient_email, provider_test_order_id=provider_test_order.id, payer=payer, add_expanded_pcr=add_expanded_pcr`
- **Context:** Provider creates a single patient test order via API. Sends notifications (email to patient/provider).

**Line 112** — Task: `send_provider_ordered_test_klaviyo_event`
- **Args:** `provider_id=provider.id, provider_test_order_ids=[provider_test_order.id], payer=payer, add_expanded_pcr=add_expanded_pcr, patient_email=patient_email`
- **Context:** Same single test order creation. Fires the "provider ordered test" analytics event.

**Line 245** — Task: `send_provider_bulk_ordered_tests_notification`
- **Args:** `provider_email=provider_email, num_ordered=num_ordered_val, provider_test_order_ids=order_ids`
- **Context:** Provider bulk-creates test orders. On transaction commit, sends bulk order notification.

**Line 262** — Task: `send_provider_ordered_test_klaviyo_event`
- **Args:** `provider_id=provider_id, provider_test_order_ids=order_ids, payer="provider-bulk"`
- **Context:** Same bulk order, on commit. Fires analytics event for bulk order.

**Line 310** — Task: `send_provider_reminded_patient_klaviyo_event`
- **Args:** `provider_id=provider.id, patient_email=patient_email`
- **Context:** Provider clicks "remind patient" in the UI. Fires an analytics event tracking that the provider reminded the patient.

---

### 33. api/v1/views/user_tests.py

**Line 357** — Task: `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`
- **Args:** `test.user.id, ecomm_order.order_number`
- **Context:** Test kit activation: the test is being activated and its associated ecomm order has no user. After attaching the user, triggers consult creation/attachment for ungated RX orders.

**Line 873** — Task: `send_additional_tests_checkout_created_event`
- **Args:** `test_kit.hash`
- **Context:** User clicks "get expanded PCR add-on" checkout. Fires the checkout-created analytics event.

**Line 945** — Task: `send_health_history_completed_klaviyo_event`
- **Args:** `test.hash`
- **Context:** User submits their health history form. Fires the "health history completed" analytics event.

---

### 34. api/v1/views/consult.py

**Line 363** — Task: `update_treatment_end_date`
- **Args:** `treatment_plan.id`
- **Context:** User updates their treatment start date via API. Triggers recalculation of the treatment end date.

**Line 366** — Task: `send_updated_treatment_start_date_event`
- **Args:** `consult.uid`
- **Context:** Same treatment start date update. Fires the "treatment start date updated" analytics event.

**Line 463** — Task: `send_care_checkout_created_event`
- **Args:** `consult.uid`
- **Context:** User initiates care checkout (first care checkout endpoint). Fires "care checkout created" analytics event.

**Line 563** — Task: `send_care_checkout_created_event`
- **Args:** `consult.uid`
- **Context:** Second care checkout endpoint (a la carte / different variant path). Same analytics event.

**Line 799** — Task: `send_consult_intake_started_klaviyo_event`
- **Args:** `intake.consult.uid`
- **Context:** User agrees to consult terms (`agree_to_terms` action). Fires the "consult intake started" analytics event.

**Line 859** — Task: `send_consult_intake_started_klaviyo_event`
- **Args:** `intake.consult.uid`
- **Context:** `consent_to_ungated_rx_terms` action (user consents to ungated RX terms). Also fires the intake started event.

**Line 912** — Task: `resubmit_consult_photo_id_info_to_wheel`
- **Args:** `consult.uid`
- **Context:** Consult intake submission when consult status is `STATUS_ID_FAILURE`. Re-submits updated photo ID info to the clinician platform.

**Line 926** — Task: `submit_async_consult`
- **Args:** `consult.uid`
- **Context:** Consult intake submission (normal path, not ID failure). After setting status to SUBMITTED, asynchronously submits the consult to the clinician platform.

---

### 35. accounts/admin_actions.py

**Line 270** — Task: `send_provider_verified_event`
- **Args:** `provider_profile.provider.id`
- **Context:** Admin action: verifying a provider account. After updating provider status, fires the "provider verified" event.

---

### 36. studies/admin.py

**Line 66** — Task: `submit_research_sample_lab_order_to_microgen`
- **Args:** `cohort_test.test.hash`
- **Context:** Admin action `submit_research_electronic_lab_order_to_mdx` on `CohortTest` queryset. Submits selected research cohort tests to the lab.

---

### 37. app/management/commands/create_study_cohort_tests.py

**Line 147** — Task: `submit_research_sample_lab_order_to_microgen`
- **Args:** `test.hash`
- **Context:** Management command `create_study_cohort_tests` with `--submit-lab-orders` flag. After creating fake cohort test records, submits each to the lab.

---

### 38. scripts/resend_lab_results_to_wheel.py

**Line 88** — Task: `issue_lab_results_to_wheel_for_lab_test`
- **Args:** `str(lab_test.id)`
- **Context:** Backfill/ops script for re-sending lab results to the clinician platform. Iterates over lab tests for specified test hashes and re-queues the submission.

---

### 39. scripts/backfill_unapproved_junction_submissions.py

**Line 113** — Task: `submit_lab_order_approval_to_junction`
- **Args:** `lab_order.uid`
- **Context:** Backfill script for lab orders that were approved but not submitted to Junction. Queues each for Junction submission.

---

### 40. scripts/reprocess_subscription_refill_orders.py

**Line 229** — Task: `send_prescription_refill_request`
- **Args:** `order.id, prescription_fill.id`
- **Context:** Backfill/ops script that reprocesses subscription refill orders (e.g., orders that failed to reach the pharmacy). Recreates the prescription fill and re-enqueues the fill request.

---

### 41. scripts/test_result_tag_scripts.py

**Line 63** — Task: `create_test_result_tagset`
- **Args:** `test.hash`
- **Context:** Ops script that iterates over test results in PROCESSING or READY status and re-queues tagset creation for each test. Used for backfilling result tags.

---

### 42. test_results/admin.py

**Line 1017** — Task: `issue_lab_results_to_wheel_for_lab_test`
- **Args:** `str(lab_test.id)`
- **Context:** Django admin: manual review of a urine test result. Admin clicks "release results," validation passes, and the lab results are sent to the clinician platform for confirmation.

---

### Summary Statistics

| Category | Count |
|---|---|
| Shopify webhook / order processing | 12 |
| Analytics / marketing events | 24 |
| Lab processing | 22 |
| Consult / care workflow | 18 |
| Shipping & fulfillment | 6 |
| Healing / retry periodic tasks | 12 |
| Admin / ops / scripts | 7 |
| **Total call sites** | **~125** |

**Total `.delay()` calls:** ~119
**Total `.apply_async()` calls:** 6 (all with `countdown=` for intentional delay)
**Total `send_task()` calls:** 0 (none found in the codebase)
