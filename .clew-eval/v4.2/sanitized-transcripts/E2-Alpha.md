# Complete Inventory of Celery Tasks in the Evvy Codebase

## Summary

The codebase contains **95 Celery tasks** across **12 task files**, all using `@shared_task`. The one exception is `submit_lab_order_approval_to_junction` and `fetch_and_process_junction_results` which use `@shared_task(bind=True, max_retries=3, ...)` for retry support. One task (`void_share_a_sale_transaction`) uses the `@retry` decorator from the `retrying` library rather than Celery's built-in retry mechanism.

Tasks are enqueued primarily via `.delay()`. The `apply_async(countdown=N)` form is used in a few places for delayed execution.

---

## 1. `/Users/albertgwo/Work/evvy/backend/accounts/tasks.py`

### `send_intake_completed_notifications`
- **Arguments:** `provider_email` (str)
- **Enqueue pattern:** `.delay()` (called from signal handlers / views)
- **Retry config:** None
- **Business purpose:** Sends admin notification email when a B2B provider registers and completes their intake form. Includes provider profile details. Different subject lines for NY providers, "Other" state providers, and standard providers.

---

## 2. `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`

This is the largest task file with ~30 tasks, all analytics/event-tracking oriented.

### `send_custom_analytics_event_to_fullstory_async`
- **Arguments:** `user_id` (int), `event_name` (str), `event_properties` (dict), `use_recent_session` (bool)
- **Enqueue:** `.delay()` via `send_custom_analytics_event_to_destinations()`
- **Retry:** None
- **Purpose:** Generic async wrapper to send events to Fullstory.

### `send_custom_analytics_event_to_klaviyo_async`
- **Arguments:** `payload` (dict)
- **Enqueue:** `.delay()` via `send_custom_analytics_event_to_destinations()`
- **Retry:** None
- **Purpose:** Generic async wrapper to send events to Klaviyo.

### `send_sample_sequencing_provider_klaviyo_event`
- **Arguments:** `test_hash` (str), `provider_test_order_id` (int)
- **Enqueue:** `.delay()` from `test_results/microgen/tasks.py`
- **Retry:** None
- **Purpose:** Notifies a provider via Klaviyo that their patient's sample is being sequenced.

### `send_pcr_test_results_ready_provider_klaviyo_event`
- **Arguments:** `test_hash` (str), `provider_test_order_id` (int)
- **Enqueue:** `.delay()` from `test_results/microgen/tasks.py`
- **Retry:** None
- **Purpose:** Notifies a provider via Klaviyo that PCR (preliminary) results are ready for their patient.

### `send_results_ready_analytics_events`
- **Arguments:** `test_hash` (str), `eligible_for_care` (bool), `ineligible_reason` (str | None)
- **Enqueue:** `.delay()` (from test results release flow)
- **Retry:** None
- **Purpose:** Core post-processing task when test results are released. Creates/updates CareEligible records (bundle care + a la carte care eligibility), computes pricing, and fires "Results Ready" events to Fullstory, Klaviyo, and Braze.

### `send_urine_test_results_ready_analytics_events`
- **Arguments:** `urine_test_hash` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Saves UTI care eligibility analytics for urine test results. Creates/updates CareEligible record with UTI eligibility and expiration date. Similar to `send_results_ready_analytics_events` but for UTI/urine tests.

### `send_care_checkout_created_event`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Care Checkout Created" event to Fullstory when a user enters the care checkout flow. Includes test hash, care price, consult type, and a la carte treatment info.

### `send_ungated_rx_order_paid_event`
- **Arguments:** `order_number` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Ungated Paid" event to Fullstory and URX_PURCHASE event to Braze when an over-the-counter (symptom relief) order is paid.

### `send_mpt_voucher_paid_event`
- **Arguments:** `user_id` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "MPT Voucher Paid" event to Fullstory, Klaviyo, and Braze when a membership/MPT voucher is purchased.

### `send_consult_paid_event`
- **Arguments:** `consult_uid` (str), `order_number` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Care Paid" event (and UTI_CONSULT_PAID for UTI consults) to Fullstory, Klaviyo, and Braze when a care consult order is paid. Includes SKUs, purchase type, pharmacy type, care eligibility.

### `send_any_paid_event`
- **Arguments:** `order_number` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends generic "Any Paid" event to Fullstory for any completed order. Categorizes order as test, care, refill, ungated rx, or combinations.

### `send_prescription_refills_paid_event`
- **Arguments:** `prescription_refill_id` (int), `order_number` (str)
- **Enqueue:** `.delay()` from `ecomm/tasks.py`
- **Retry:** None
- **Purpose:** Sends "Prescription Refills Paid" event to Fullstory when a prescription refill order is paid.

### `send_additional_tests_checkout_created_event`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Additional Tests Checkout Created" event to Fullstory when a user starts checkout for add-on tests.

### `send_additional_tests_paid_event`
- **Arguments:** `test_hash` (str), `order_number` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Additional Tests Paid" event to Fullstory when add-on test order is paid.

### `send_consult_intake_ineligible_event`
- **Arguments:** `consult_uid` (str), `refer_out_reason` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Consult Intake Ineligible" event to Fullstory when a user is referred out during the care intake process.

### `send_rx_order_attached_to_account_klaviyo_event`
- **Arguments:** `consult_uid` (str), `order_number` (str)
- **Enqueue:** `.delay()` from `ecomm/tasks.py`
- **Retry:** None
- **Purpose:** Sends "RX Attached to Account" Klaviyo event when an ungated RX order is linked to a user's account (handles anonymous-to-registered user reconciliation).

### `send_consult_intake_submitted_event`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()` from `consults/wheel/tasks.py`
- **Retry:** None
- **Purpose:** Sends "Consult Intake Submitted" event (and UTI variant) to Fullstory, Klaviyo, and Braze when a user submits their care intake form.

### `send_coaching_call_completed_event`
- **Arguments:** `test_hash` (str), `coaching_call_notes_id` (optional int), `num_calls` (optional int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Coaching Call Completed" event to Fullstory after a care coaching call is logged.

### `send_treatment_delivered_event`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()` from `analytics/tasks.py` (via `send_treatment_probably_delivered_events_for_treatment_plans`)
- **Retry:** None
- **Purpose:** Sends "Treatment Delivered" Klaviyo event with treatment SKUs and dates when prescription treatment is delivered.

### `send_estimated_treatment_started_events`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Daily batch job that identifies treatment plans where treatment should be starting today. Fans out to `send_estimated_treatment_started_event` for each plan.

### `send_estimated_treatment_started_event`
- **Arguments:** `treatment_plan_id` (int)
- **Enqueue:** `.delay()` from `send_estimated_treatment_started_events`
- **Retry:** None
- **Purpose:** Sends "Treatment Started" Klaviyo event for a specific treatment plan if the estimated start date is today or yesterday.

### `send_test_delivered_klaviyo_event`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Test Kit Delivered" Klaviyo event using the order email (for pre-registered users) when the test kit is delivered.

### `send_health_history_completed_klaviyo_event`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Health History Completed" Klaviyo event when a user completes their health history questionnaire.

### `send_updated_treatment_start_date_event`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Updated Treatment Start Date" Klaviyo event when a user updates their treatment plan start date.

### `send_treatment_ended_event`
- **Arguments:** `treatment_plan_id` (int)
- **Enqueue:** `.delay()` from `send_treatment_ended_events_for_treatment_plans`
- **Retry:** None
- **Purpose:** Sends "Treatment Ended" event to Klaviyo and Braze when a treatment plan's end date is reached.

### `send_treatment_ended_events_for_treatment_plans`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Daily batch job that finds all treatment plans ending today or yesterday and fans out to `send_treatment_ended_event`.

### `send_treatment_probably_delivered_events_for_treatment_plans`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Periodic job to find treatment plans that were probably delivered (based on average fulfillment days from creation, with no explicit delivery timestamp) and send the "Treatment Delivered" Klaviyo event.

### `send_provider_registered_event`
- **Arguments:** `provider_id` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Provider Registered" Klaviyo event when a new B2B provider registers.

### `send_provider_verified_event`
- **Arguments:** `provider_id` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "[Provider] Provider Verified" Klaviyo event when a provider's account is verified.

### `send_provider_ordered_test_klaviyo_event`
- **Arguments:** `provider_id` (int), `provider_test_order_ids` (list), `payer` (str), `add_expanded_pcr` (bool, default False), `patient_email` (str, optional)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends both patient-facing ("Provider Ordered A Test for User") and provider-facing ("[Provider] Provider Ordered a Test") Klaviyo events when a provider orders a test for a patient. Generates checkout link.

### `send_provider_reminded_patient_klaviyo_event`
- **Arguments:** `provider_id` (int), `patient_email` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Provider Reminded User to Purchase Test" Klaviyo event when a provider sends a payment reminder to a patient. Generates checkout link.

### `send_viewed_plan_klaviyo_event`
- **Arguments:** `test_id` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Viewed Plan" Klaviyo event when a user views their test results plan.

### `send_consult_intake_started_klaviyo_event`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "Consult Intake Started" Klaviyo event when a user begins the care intake form.

### `send_three_weeks_after_treatment_delivered_klaviyo`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Finds consults eligible for prescription refills (~3 weeks post-delivery) and sends "Consult Eligible for Refill" Klaviyo event.

---

## 3. `/Users/albertgwo/Work/evvy/backend/app/tasks.py`

### `clean_log_entries`
- **Arguments:** `delete_all` (bool, default False)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Cleans up Django auditlog entries older than 30 days. Can delete all entries if `delete_all=True`.

---

## 4. `/Users/albertgwo/Work/evvy/backend/care/tasks.py`

### `update_treatment_end_date`
- **Arguments:** `treatment_plan_id` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Recalculates and saves the treatment end date on a TreatmentPlan based on current prescription data.

### `create_or_reset_calendar_treatments`
- **Arguments:** `treatment_plan_id` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Rebuilds the treatment calendar (CalendarTreatment objects) for a treatment plan, deleting existing entries and recreating based on current prescriptions.

### `heal_prescription_fill_orders`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Data integrity job: finds prescription fills modified in the last 24 hours that have an order but no PrescriptionFillOrder junction record, and creates the missing records.

### `heal_otc_treatment_only_orders`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Data integrity job: finds OTC-only orders (no prescriptions) in the last 24 hours that haven't been sent to Precision pharmacy, creates prescription fills, and dispatches them through the fulfillment pipeline.

---

## 5. `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`

### `send_patient_ordered_provider_test_notification`
- **Arguments:** `patient_email` (str), `order_sku` (str), `order_provider_id` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends internal admin email notification when a patient completes a checkout for a provider-ordered test.

### `void_share_a_sale_transaction`
- **Arguments:** `order_number` (str), `order_date` (str), `reason` (str)
- **Enqueue:** `.delay()`
- **Retry:** `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` — uses the `retrying` library, up to 3 attempts with exponential backoff starting at 500ms
- **Purpose:** Voids a Share-A-Sale affiliate commission transaction when an order is cancelled/refunded.

### `send_prescription_refill_request`
- **Arguments:** `order_id` (int), `prescription_fill_id` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Orchestrates sending a prescription refill to Precision pharmacy. Validates state eligibility, checks remaining refills, updates fill status, creates patient/prescription records in Precision, and sends the fill request. Handles cancellation by cancelling the fill in Precision.

### `send_otc_treatment_fill_request`
- **Arguments:** `order_id` (int), `prescription_fill_id` (int)
- **Enqueue:** `.delay()` from `care/tasks.py`
- **Retry:** None
- **Purpose:** Sends an OTC-only fill request to Precision for orders without prescriptions (no state restrictions, no consult required).

### `attach_unattached_orders_to_user`
- **Arguments:** `user_id` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** After user account creation, attaches any pre-existing orders with matching email to the user's account. Also triggers consult creation for ungated RX orders.

### `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`
- **Arguments:** `user_id` (int), `order_number` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** For ungated RX orders, consolidates newly purchased treatments into the user's latest in-progress vaginitis or ungated RX consult. If no in-progress consult exists, creates a new ungated RX consult automatically.

### `create_consults_for_ungated_rx_orders_with_users_but_no_consult`
- **Arguments:** None (periodic task / admin trigger)
- **Enqueue:** Direct call or periodic task
- **Retry:** None
- **Purpose:** Backfill/healing job: creates consults for ungated RX orders that have a user attached but no ConsultOrder record.

### `process_gift_card_redemptions`
- **Arguments:** `order_id` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Processes gift card redemptions for a specific order using GiftCardRedemptionService.

### `process_gift_cards`
- **Arguments:** `order_id` (int), `payload` (dict, optional)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Processes both gift card purchases and redemptions for an order. Handles full gift card lifecycle.

### `reprocess_subscription_refill_orders_daily`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Daily job to reprocess subscription refill orders that were incorrectly routed or missed in the last 24 hours. Calls external reprocessing script.

---

## 6. `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py`

### `retry_failed_shopify_orders`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None (but has `soft_time_limit=600, time_limit=900` — soft 10 min, hard 15 min limit)
- **Task decorator:** `@shared_task(soft_time_limit=600, time_limit=900)`
- **Purpose:** Polls Shopify for orders created in the last 3 days (excluding the last hour) and processes any that are missing from the local database. Handles up to 1,000 orders (50 pages × 20/page).

---

## 7. `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`

### `update_individual_shipping_status`
- **Arguments:** `status_id` (int)
- **Enqueue:** `.delay()` from `update_eligible_shipping_statuses_async`
- **Retry:** None
- **Purpose:** Updates the shipping status for a single ShippingStatus record by polling the carrier (USPS/FedEx).

### `update_eligible_shipping_statuses_async`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Batch job that identifies all active shipments needing status updates (kit and sample tracking) with different polling frequencies (kits: daily, recent samples: daily, old samples: 3 days, unactivated: weekly) and fans out to `update_individual_shipping_status`.

### `send_daily_express_orders_email`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends daily summary email of express shipping orders to the fulfillment operations team. Also adds these orders to a Google Sheet.

### `process_tracking_statuses`
- **Arguments:** `test_hash` (str), `order_number` (str), `kit_tracking_number` (str), `sample_tracking_number` (str), `mode` (str, default "all"), `from_csv` (bool, default False)
- **Enqueue:** `.delay()` (from Berlin fulfillment webhook / CSV import)
- **Retry:** None
- **Purpose:** Core fulfillment processing task. Associates a test with an order, creates ShippingStatus records for kit and return sample tracking numbers, and marks the order as fulfilled in Shopify. Handles bulk orders, duplicate detection, and different processing modes (all, fulfill-only, with/without customer notifications). Also handles non-test products and expanded PCR tests.

### `send_order_to_berlin_for_fulfillment`
- **Arguments:** `shopify_payload` (dict), `is_order_cancellation` (bool), `order_id` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends a test kit order to Berlin (3PL fulfillment partner) via their API. Records `sent_to_berlin_at` timestamp on success. Logs to NewRelic.

### `retry_failed_berlin_order_fulfillments`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Finds active/cancelled orders since the Berlin integration launch date (3/27/2024) that were never sent to Berlin and retries sending them.

### `alert_if_no_orders_sent_to_berlin`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Monitoring/alerting task. Sends admin email if no orders have been successfully sent to Berlin in the last 6 hours.

### `alert_if_no_orders_created`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Monitoring/alerting task. Sends admin email if no new orders have been created in the last 6 hours.

---

## 8. `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`

### `process_precision_pharmacy_webhook`
- **Arguments:** `payload` (dict)
- **Enqueue:** `.delay()` from webhook handler
- **Retry:** None
- **Purpose:** Routes incoming Precision pharmacy webhooks by type: "received" (logged only), "shipped" (triggers shipment processing), "delivered" (triggers delivery processing), "warning" (logged only).

### `send_prescription_to_precision`
- **Arguments:** `consult_uid` (str), `skip_set_sent_to_pharmacy` (bool, default False)
- **Enqueue:** Direct call and `.delay()` from `consults/wheel/tasks.py`
- **Retry:** None
- **Purpose:** Sends an initial prescription to Precision pharmacy for a completed consult. Creates patient record, creates and fills prescription. Also tracks Braze "consult eligible for refills" event if applicable.

### `send_create_patient_request_to_precision`
- **Arguments:** `prescription_fill_id` (int), `consult_uid` (str, optional), `user_id` (int, optional), `order_id` (int, optional)
- **Enqueue:** Direct call and `.delay()`
- **Retry:** None
- **Purpose:** Creates a patient record in Precision pharmacy. Stores `pharmacy_patient_id` on the PrescriptionFill record. One of `user_id`, `order_id`, or `consult_uid` must be provided.

### `send_create_prescription_request_to_precision`
- **Arguments:** `prescription_uid` (str), `fill_quantity` (optional), `prescription_fill_prescription` (PrescriptionFillPrescriptions, optional)
- **Enqueue:** Direct call
- **Retry:** None (but sets fill status to WARNING on failure)
- **Purpose:** Creates a prescription record in Precision pharmacy for a specific medication.

### `send_create_otc_treatment_request_to_precision`
- **Arguments:** `otc_treatment_uid` (str), `prescription_fill_otc_treatment_id` (int)
- **Enqueue:** Direct call and `.delay()`
- **Retry:** None (but sets fill status to WARNING on failure)
- **Purpose:** Creates an OTC treatment record in Precision pharmacy.

### `send_fill_request_to_precision`
- **Arguments:** `fill_uid` (int), `order_shipping_address` (optional)
- **Enqueue:** Direct call
- **Retry:** None (but sets fill status to WARNING and clears `sent_to_pharmacy_at` on failure)
- **Purpose:** Sends the actual fill request to Precision to fulfill a prescription. Sets `sent_to_pharmacy_at` on the consult on success. Logs to NewRelic.

### `send_cancel_fill_request_to_precision`
- **Arguments:** `fill_uid` (int)
- **Enqueue:** Direct call from `ecomm/tasks.py`
- **Retry:** None
- **Purpose:** Cancels a prescription fill in Precision pharmacy. Raises exception if fill is already shipped or delivered.

### `send_missing_prescriptions_to_precision`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Healing job: finds consults that are STATUS_COMPLETE but were never sent to pharmacy in the last 2 days, and resubmits them.

### `retry_failed_prescription_fills`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None (but implements internal retry logic with 10-per-run limit, 1-hour minimum gap, 7-day maximum age, and 3-day permanent failure cutoff)
- **Purpose:** Retries prescription fills stuck in WARNING status (failed to send to Precision). Marks fills as FAILED after 3 days of retries.

### `send_notification_for_stuck_prescriptions`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Monitoring task: sends admin email listing prescription refills (not initial fills) that have been in CREATED status for more than 3 business days.

---

## 9. `/Users/albertgwo/Work/evvy/backend/subscriptions/tasks.py`

### `cancel_expired_prescription_subscriptions`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Daily job to cancel Recharge subscriptions for prescriptions that have exhausted their refills. Calls `cancel_subscriptions_for_expired_prescriptions()` service.

---

## 10. `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`

### `send_provider_ordered_single_test_notifications`
- **Arguments:** `provider_email` (str), `patient_email` (str), `provider_test_order_id` (int), `payer` (str), `add_expanded_pcr` (bool, default False)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends internal admin notification email when a provider orders a single test for a patient.

### `send_provider_bulk_ordered_tests_notification`
- **Arguments:** `provider_email` (str), `num_ordered` (int), `provider_test_order_ids` (list)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends internal admin notification when a provider creates a bulk test order (pending payment).

### `send_provider_bulk_order_paid_notification`
- **Arguments:** `ecomm_order_id` (int), `provider_email` (str), `quantity` (int)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends internal admin notification when a provider's bulk order is paid.

### `send_provider_test_results_ready`
- **Arguments:** `provider_email` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends templated email to a provider when their patient's test results are ready.

---

## 11. `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`

This file has ~30 tasks, all focused on sending transactional emails to customers.

### `send_test_activated_reminder`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends reminder emails to users who activated a test 4+ days ago but haven't progressed to "sample taken" status.

### `send_tests_in_transit_through_usps_and_fedex_emails`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends "sample in transit" emails to users whose samples moved to in-transit status in the last 3 days. Includes tracking link.

### `send_tests_in_transit_hh_incomplete`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends reminder to complete health history to users whose samples are in transit but health history is incomplete.

### `send_tests_received_at_lab_hh_incomplete`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends reminder to complete health history to users whose samples have been received at the lab but health history is still incomplete.

### `send_ldt_test_sample_received_email`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()` from `test_results/microgen/tasks.py`
- **Retry:** None
- **Purpose:** Sends "sample received at lab" email to users of LDT tests (standard or comprehensive variant).

### `send_ldt_test_sample_sequencing_email`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()` from `test_results/microgen/tasks.py`
- **Retry:** None
- **Purpose:** Sends "sample is being sequenced" email for LDT tests. Also sends internal lab notification.

### `send_ldt_tests_results_almost_ready`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends "results almost ready" email to users whose LDT tests have been in sequencing for 10+ days.

### `send_pcr_test_results_ready`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()` from `test_results/microgen/tasks.py`
- **Retry:** None
- **Purpose:** Sends "PCR/preliminary results ready" email for the expanded panel tests.

### `send_expert_call_emails`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends "schedule an expert call" email 1-6 days after results are ready to users with v2 plans who haven't started a care consult.

### `send_view_unread_plan_emails`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends reminder email to view test plan 3-6 days after results were viewed but plan has not been viewed.

### `send_eligible_for_care_1_for_test`
- **Arguments:** `test_id` (int)
- **Enqueue:** `.delay()` from `test_results/tasks.py`
- **Retry:** None
- **Purpose:** Sends first care eligibility email immediately when results are ready and user is eligible for care.

### `send_eligible_for_a_la_care_not_treatment_program`
- **Arguments:** `test_id` (int)
- **Enqueue:** `.delay()` from `test_results/tasks.py`
- **Retry:** None
- **Purpose:** Sends a la carte care eligibility email for users eligible for individual treatments but not the full treatment program.

### `send_a_la_care_treatments_ready`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "individual treatments ready" email when an a la carte care consult is complete.

### `send_eligible_for_care_2`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Second care eligibility reminder email sent 6-8 days after results are ready. LDT only.

### `send_eligible_for_care_3`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Third care eligibility reminder email sent 12-14 days after results are ready. LDT only.

### `send_treatments_shipped`
- **Arguments:** `prescription_fill_id` (int)
- **Enqueue:** `.delay()` (from Precision webhook processing)
- **Retry:** None (raises exception on failure)
- **Purpose:** Sends "your treatments have shipped" email with tracking link when prescription fills are shipped.

### `send_treatments_delivered`
- **Arguments:** `prescription_fill_id` (int)
- **Enqueue:** `.delay()` (from Precision webhook processing)
- **Retry:** None (raises exception on failure)
- **Purpose:** Sends "your treatments have been delivered" email. Uses different template for initial vs refill or a la carte fills.

### `send_consult_intake_abandonment_reminder`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends "you started care, finish your intake" reminder email 2-6 hours after consult ordered but not submitted. Excludes STI consults.

### `send_consult_intake_abandonment_reminder_2`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Second abandonment reminder 24-48 hours after consult ordered but not submitted. Excludes STI consults.

### `send_sti_consult_intake_abandonment_reminder`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** STI-specific intake abandonment reminder 24-36 hours after STI consult ordered but not submitted.

### `send_sti_prescription_sent_to_pharmacy_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "your STI prescription has been sent to your local pharmacy" email with pharmacy pickup info.

### `send_email_organon_prescriptions_ready`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends Organon prescription pharmacy pickup email.

### `send_consult_intake_reviewed_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()` from `consults/wheel/tasks.py`
- **Retry:** None
- **Purpose:** Sends notification email when a care intake has been reviewed by the clinical team.

### `send_treatment_plan_ready_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends "your treatment plan is ready" email with link to view the plan.

### `send_lab_order_rejected_email`
- **Arguments:** `lab_order_uid` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends email notifying user their lab order was rejected, directing them to contact support.

### `send_id_verification_failed_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()` (from Wheel webhook)
- **Retry:** None (allows duplicates)
- **Purpose:** Sends "ID verification failed" email with re-upload link and reason/notes.

### `send_care_referred_out_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()` from `consults/wheel/tasks.py`
- **Retry:** None (allows duplicates)
- **Purpose:** Sends "you've been referred out" email when clinical review determines care is not appropriate.

### `send_new_consult_message_email`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()` (from Wheel webhook)
- **Retry:** None (allows duplicates)
- **Purpose:** Sends email notification that a new message from the clinician is available in the care chat.

### `send_care_first_check_in_email`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends first care check-in email 4-24 hours after a v0 bundle care consult completes. Includes coaching call link.

### `send_prescription_refills_available`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends prescription refill availability email to users eligible for refills (~3 weeks post-delivery).

### `send_sample_taken_but_not_in_transit_reminder`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Sends "please mail your sample" reminder 5-10 days after the sample was taken but not yet in transit to the lab.

### `send_test_sample_at_lab_but_not_activated`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()` from `test_results/microgen/tasks.py`
- **Retry:** None
- **Purpose:** Sends activation reminder email to the order email when a sample arrives at the lab but the test kit was never activated in the user's account.

### `send_test_sample_received_at_lab_but_not_activated`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Periodic version of above — finds unactivated samples received at lab in the last 7 days and sends activation reminders.

### `send_account_transfer_verification_email`
- **Arguments:** `user_id` (int), `order_email` (str), `order_number` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends order transfer verification email when a logged-in user's account email doesn't match the email used for an order. Allows them to claim the order.

---

## 12. `/Users/albertgwo/Work/evvy/backend/test_results/tasks.py`

### `create_test_result_tagset`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()` (direct call within `post_process_test_results`)
- **Retry:** None
- **Purpose:** Creates or updates the TestResultTagSet for a test result — computes pregnancy, menopause, symptoms, pathogen, and health context tags from health history data. These tags drive plan profile assignment and care eligibility logic.

### `post_process_test_results`
- **Arguments:** `test_hash` (str), `release_results` (bool, default True)
- **Enqueue:** `.delay()` from `test_results/microgen/tasks.py`
- **Retry:** None
- **Purpose:** Comprehensive post-processing pipeline after raw lab data is loaded. Updates Valencia type, computes test scores, creates fertility module, captures infection state snapshot, assigns plan profile, assigns suspected yeast flag, creates recommended treatment program, and auto-releases results if eligible.

### `assign_suspected_yeast_flag_to_test_result`
- **Arguments:** `test_hash` (str)
- **Enqueue:** Direct call within `post_process_test_results`
- **Retry:** None
- **Purpose:** Sets `suspected_yeast=True` on a test result if yeast is present in results or if user reported yeast diagnosis in the past year.

### `send_results_ready_emails`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()` (from results release flow)
- **Retry:** None (raises exception on email failure)
- **Purpose:** Sends the "your results are ready" email and triggers care eligibility emails (email 1 or a la carte eligibility email) if applicable.

### `send_test_status_duration_alert`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Monitoring task: checks for MDX tests stuck in "received", "sequencing", or "processing" status beyond threshold durations (7 days for received/sequencing, 4 days for processing). Categorizes by waiting on lab order vs. actual delays. Sends admin email alert.

### `send_lab_test_status_duration_alert`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Monitoring task: checks for PCR (vaginitis) lab tests stuck in "at lab" status for more than 3 days and sends admin alert.

### `send_vip_test_status_update`
- **Arguments:** `test_hash` (str), `previous_status` (str), `new_status` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Sends admin email notification for every status change of VIP (provider-ordered) tests for special monitoring.

---

## 13. `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`

### `submit_lab_order_approval_to_microgen`
- **Arguments:** `lab_order_uid` (str)
- **Enqueue:** Direct call and `.delay()` from `consults/wheel/tasks.py`
- **Retry:** None
- **Purpose:** Submits an approved lab order (after Wheel clinical approval) to Microgen (MDX) API for processing. Records `electronic_order_submitted_at` timestamp. Skips if already submitted.

### `submit_research_sample_lab_order_to_microgen`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Submits a research/non-clinical sample lab order to Microgen. Used for research track tests.

### `submit_missing_lab_order_approvals_to_microgen`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Healing job: finds lab orders approved in the last 60 days that were never submitted to Microgen and resubmits them.

### `process_test_results_stuck_in_sequencing_status`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Finds tests stuck in sequencing status for 7-60 days with no processing errors and tries to process them from S3.

### `process_microgen_test_results`
- **Arguments:** `test_hash` (str), `report_errors` (bool, default True), `read_from_staging` (bool, default False), `release_results` (bool, default True), `bypass_ready_check` (bool, default False), `force_update_result_value` (bool, default False)
- **Enqueue:** `.delay()` and `apply_async(args=[test_hash], countdown=delay_seconds)` (with random delay for load balancing)
- **Retry:** None
- **Purpose:** Processes NGS sequencing results from S3 for a test. Loads raw Microgen results file, then kicks off `post_process_test_results` async.

### `process_microgen_test_results_if_exists_in_s3`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()` from `process_test_results_stuck_in_sequencing_status`
- **Retry:** None (silently handles S3 NoSuchKey errors)
- **Purpose:** Wrapper around `process_microgen_test_results` that gracefully handles missing S3 files (for healing jobs).

### `process_microgen_vag_pcr_test_results`
- **Arguments:** `test_hash` (str)
- **Enqueue:** `.delay()` from `process_lab_status_update` in same file
- **Retry:** None
- **Purpose:** Processes vaginitis PCR panel (expanded test) results from S3. Sends PCR results ready email and Braze/Klaviyo events to user and provider.

### `send_summary_tests_entered_sequencing`
- **Arguments:** None
- **Enqueue:** `apply_async(countdown=N)` via `_queue_summary_notification("sequencing")`
- **Retry:** None
- **Purpose:** Batched notification: sends admin summary email of all tests that entered sequencing in the last 2 hours.

### `send_summary_vpcr_results_processed`
- **Arguments:** None
- **Enqueue:** `apply_async(countdown=N)` via `_queue_summary_notification("partial-results")`
- **Retry:** None
- **Purpose:** Batched notification: sends admin summary email of PCR results processed in the last 2 hours.

### `send_summary_vngs_results_processed`
- **Arguments:** None
- **Enqueue:** `apply_async(countdown=N)` via `_queue_summary_notification("ready")`
- **Retry:** None
- **Purpose:** Batched notification: sends admin summary email of NGS results processed in the last 2 hours.

### `process_lab_status_update_batch`
- **Arguments:** `payload` (dict with `status_updates` list)
- **Enqueue:** `.delay()` (from MDX webhook batch handler)
- **Retry:** None
- **Purpose:** Processes a batch of lab status updates from MDX webhook. Fans out to `process_lab_status_update()` (non-task function) for each individual update.

---

## 14. `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`

### `submit_async_consult`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Prepares and routes a consult intake for submission to Wheel. Sets recommended prescriptions, checks if manual review is required, and either creates a ConsultReview or submits directly to Wheel.

### `submit_consult_intake_to_wheel`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** Direct call from `submit_async_consult` and `.delay()` from retrying tasks
- **Retry:** None (raises on error)
- **Purpose:** Submits the actual consult intake to Wheel API. Handles pharmacy type routing (local pickup pre-population). Triggers analytics event and intake reviewed email on success.

### `issue_lab_results_to_wheel_for_lab_test`
- **Arguments:** `lab_test_id` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Issues lab results (NGS, vPCR, or urine PCR) to Wheel for clinical interpretation after results are processed from Microgen/Junction.

### `resubmit_consult_photo_id_info_to_wheel`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Re-submits updated photo ID information to Wheel after an identity verification failure, resetting the consult to in-progress status.

### `fetch_and_process_completed_consult_details`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()` (from Wheel webhook)
- **Retry:** None
- **Purpose:** After a consult is marked finished/diagnosed by Wheel, fetches clinician info, diagnosis, prescriptions, and clinical notes from Wheel API. Routes to prescription matching and Precision submission.

### `fetch_and_process_completed_lab_order_details`
- **Arguments:** `lab_order_uid` (str)
- **Enqueue:** `.delay()` (from Wheel webhook)
- **Retry:** None
- **Purpose:** After Wheel approves a lab order, fetches clinician details and routes the approved order to the appropriate lab provider (Junction for urine tests, Microgen for vaginal tests).

### `retry_consult_detail_processing`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Healing job: finds consults stuck in IN_PROGRESS/SUBMITTED/ERROR status for 24+ hours, checks if they're finished on Wheel's side, and re-fetches/processes them.

### `retry_creating_async_consults`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Healing job: retries consults in SUBMITTED status (intake submitted but not yet sent to Wheel) that are 1-5 days old with no open tasks or reviews.

### `retry_errored_consult_creation`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Healing job: retries consults in ERROR status (Wheel submission failed) with no open tasks or reviews.

### `fetch_and_process_follow_up_consult_details`
- **Arguments:** `lab_order_uid` (str), `follow_up_external_id` (str)
- **Enqueue:** `.delay()` (from Wheel webhook and `send_notification_for_diagnosis_pending_consults`)
- **Retry:** None
- **Purpose:** Fetches Wheel's interpretation of follow-up lab result consultation. Stores interpretation/patient instructions, and confirms diagnosis if interpretability is ALL or SOME. Creates amendment task if Wheel disagrees with diagnosis (NONE interpretability).

### `check_recommended_prescriptions_against_prescribed_and_send_prescriptions`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()` from `fetch_and_process_completed_consult_details`
- **Retry:** None
- **Purpose:** Validates that Wheel prescribed exactly what was recommended. If matched: marks consult complete, fires Braze event, sends to Precision. If not matched: creates a ConsultReview for manual intervention.

### `check_recommended_prescriptions_against_prescribed`
- **Arguments:** `consult_uid` (str), `notify_admins` (bool, default False)
- **Enqueue:** Direct call and `.delay()` (called from `send_missing_prescriptions_to_precision`)
- **Retry:** None
- **Purpose:** Checks if recommended prescriptions match what was actually prescribed. Creates ConsultReview if mismatched and notify_admins=True. Returns bool.

### `fetch_and_process_referred_consult_details`
- **Arguments:** `consult_uid` (str)
- **Enqueue:** `.delay()` (from Wheel webhook and `retry_consult_detail_processing`)
- **Retry:** None
- **Purpose:** Handles consults that Wheel referred out. Stores referral info, creates a ConsultTask, sets status to REFERRED, and sends the referred-out email.

### `submit_lab_order_to_wheel`
- **Arguments:** `lab_order_uid` (str)
- **Enqueue:** `.delay()` from retry tasks
- **Retry:** None (but idempotent — skips if already approved/submitted)
- **Purpose:** Submits a lab order to Wheel for physician requisition approval.

### `resubmit_stuck_lab_orders_to_wheel`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Healing job: resubmits lab orders stuck in CREATED/SUBMITTED status (submitted intake 1+ hour ago but not approved). Skips Canadian addresses. Clears provider_id before resubmission.

### `resubmit_errored_lab_orders_to_wheel`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Healing job: resubmits lab orders in ERROR status, skipping Canadian addresses and orders where results have already been sent (to prevent status regression).

### `mark_wheel_consult_message_as_read`
- **Arguments:** `consult_uid` (str), `message_id` (str)
- **Enqueue:** `.delay()`
- **Retry:** None
- **Purpose:** Marks a consult chat message as read in Wheel.

### `send_notification_for_stuck_consults`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Monitoring task: sends admin email for non-UTI consults stuck in clinical review 24+ hours, stuck lab orders, and open manual review items.

### `send_notification_for_stuck_uti_consults`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Monitoring task: UTI-specific version of above. Sends separate alerts for UTI consults stuck in review and open UTI manual reviews.

### `send_notification_for_diagnosis_pending_consults`
- **Arguments:** `hours_threshold` (int, default 24)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Monitoring task: alerts when results have been sent to Wheel for interpretation but diagnosis hasn't been confirmed after X hours. Separate tracking for VHT and UTI. Also re-triggers `fetch_and_process_follow_up_consult_details` for each pending item.

### `send_notification_for_care_orders_in_bad_states`
- **Arguments:** None (periodic task)
- **Enqueue:** Celery Beat periodic task
- **Retry:** None
- **Purpose:** Comprehensive data integrity monitoring: alerts for care orders without consults, completed consults without prescription fills, and ungated RX orders with users but no consults. Looks at orders from 5-10 days ago.

### `attach_latest_otc_treatment_to_consult`
- **Arguments:** `consult` (Consult object — note: this is an ORM object, not a serializable ID)
- **Enqueue:** Direct call from `_post_prescription_fetch_and_process_consult_details`
- **Retry:** None
- **Purpose:** If a user has an active probiotic subscription, attaches the latest OTCTreatment to their new consult (so the care treatment plan includes the subscription probiotic).

---

## 15. `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py`

### `create_unregistered_testkit_order_for_urine_test`
- **Arguments:** `urine_test_ids` (list[int]), `ecomm_order_id` (int)
- **Enqueue:** `.delay()` (from order processing)
- **Retry:** None
- **Purpose:** Creates unregistered testkit orders in Junction when urine test orders are first created (before Wheel approval). Stores the `external_order_id` on the LabOrder for later registration. Pre-populates shipping address on LabOrderIntake.

### `submit_lab_order_approval_to_junction`
- **Arguments:** `lab_order_uid` (str)
- **Enqueue:** `.delay()` from `consults/wheel/tasks.py`
- **Retry:** `@shared_task(bind=True, max_retries=3, default_retry_delay=60)` — up to 3 retries; on retryable errors (5xx, Timeout) uses exponential backoff (60s, 120s, 240s); non-retryable 4xx client errors raise `LabOrderCreationError` immediately
- **Purpose:** Registers a previously-created unregistered testkit order in Junction after Wheel approves the lab requisition. Stores `electronic_order_submitted_at` on success.

### `fetch_and_process_junction_results`
- **Arguments:** `external_order_id` (str)
- **Enqueue:** `.delay()` (from Junction results-ready webhook)
- **Retry:** `@shared_task(bind=True, max_retries=3)` — up to 3 retries with exponential backoff (60s, 120s, 240s, capped at 300s)
- **Purpose:** Fetches UTI lab results from Junction API asynchronously (so the webhook can return 200 immediately). Processes results via LabServicesOrchestrator.

### `fulfill_uti_order_in_shopify`
- **Arguments:** `urine_test_id` (int), `tracking_number` (str), `courier` (str)
- **Enqueue:** `.delay()` (from Junction shipping webhook)
- **Retry:** None
- **Purpose:** Marks a UTI test kit order as fulfilled in Shopify with tracking information when Junction ships the kit to the customer.

---

## Enqueue Pattern Summary

| Pattern | Usage |
|---------|-------|
| `.delay(arg1, arg2)` | Most common — ~90% of task calls |
| `apply_async(args=[...], countdown=N)` | Delayed execution: `process_microgen_test_results` (random load balancing delay), `send_summary_*` tasks (batch notification with cache lock) |
| `apply_async(countdown=N)` via `self.retry(exc=e, countdown=N)` | Celery built-in retry: `submit_lab_order_approval_to_junction`, `fetch_and_process_junction_results` |
| `@retry(...)` from `retrying` library | `void_share_a_sale_transaction` only |
| Direct synchronous call | `send_prescription_to_precision`, `send_create_patient_request_to_precision`, `send_create_prescription_request_to_precision`, `send_fill_request_to_precision`, `send_cancel_fill_request_to_precision` (called directly in some contexts) |

## Retry Configuration Summary

Only 3 tasks have explicit Celery retry configurations:
- `submit_lab_order_approval_to_junction`: `max_retries=3, default_retry_delay=60`, exponential backoff (60/120/240s), only retries on 5xx/Timeout
- `fetch_and_process_junction_results`: `max_retries=3`, exponential backoff (60/120/240s capped at 300s), retries on all exceptions
- `retry_failed_shopify_orders`: No Celery retry but has `soft_time_limit=600, time_limit=900` (10/15 minute limits)
- `void_share_a_sale_transaction`: Uses `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` from the `retrying` library (not Celery retry)
