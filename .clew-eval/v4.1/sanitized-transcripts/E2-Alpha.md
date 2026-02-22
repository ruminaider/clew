# E2 — Agent Alpha

Now I have a comprehensive picture of all Celery tasks. Let me compile the complete inventory.

Here is the complete inventory of all Celery tasks in the codebase, organized by module.

---

## Complete Celery Task Inventory

### `/Users/albertgwo/Work/evvy/backend/app/tasks.py`

**`clean_log_entries(delete_all=False)`**
- Arguments: `delete_all` (bool, default False) — if True, deletes all audit log entries regardless of age
- Enqueued: not found called via `.delay()` in the codebase; this is a scheduled beat task
- Retry config: none
- Purpose: Housekeeping — deletes AuditLog entries older than 30 days to control database growth

---

### `/Users/albertgwo/Work/evvy/backend/accounts/tasks.py`

**`send_intake_completed_notifications(provider_email)`**
- Arguments: `provider_email` (str) — email of the provider who completed intake
- Enqueued: `.delay()` expected from provider intake completion flow
- Retry config: none
- Purpose: Notifies internal team via admin email when a B2B provider registers and completes their intake form; includes state-specific logic (NY / "Other" state flags)

---

### `/Users/albertgwo/Work/evvy/backend/analytics/tasks.py`

This file contains the largest concentration of tasks, all analytics/event-tracking tasks.

**`send_custom_analytics_event_to_fullstory_async(user_id, event_name, event_properties, use_recent_session)`**
- Arguments: `user_id` (int), `event_name` (str), `event_properties` (dict), `use_recent_session` (bool)
- Enqueued: `.delay()` from `send_custom_analytics_event_to_destinations()`
- Retry config: none
- Purpose: Generic async wrapper for sending an event to FullStory

**`send_custom_analytics_event_to_klaviyo_async(payload)`**
- Arguments: `payload` (dict, Klaviyo-formatted event payload)
- Enqueued: `.delay()` from `send_custom_analytics_event_to_destinations()`
- Retry config: none
- Purpose: Generic async wrapper for sending an event to Klaviyo

**`send_sample_sequencing_provider_klaviyo_event(test_hash, provider_test_order_id)`**
- Arguments: `test_hash` (str), `provider_test_order_id` (int)
- Enqueued: `.delay()` from microgen tasks when a test enters sequencing status and has a provider order
- Retry config: none
- Purpose: Sends "[Provider] Sample Sequencing" Klaviyo event to notify the ordering provider that their patient's sample is being sequenced

**`send_pcr_test_results_ready_provider_klaviyo_event(test_hash, provider_test_order_id)`**
- Arguments: `test_hash` (str), `provider_test_order_id` (int)
- Enqueued: `.delay()` from microgen tasks after PCR results are processed
- Retry config: none
- Purpose: Sends "[Provider] Preliminary Results Ready" Klaviyo event to the ordering provider

**`send_results_ready_analytics_events(test_hash, eligible_for_care, ineligible_reason)`**
- Arguments: `test_hash` (str), `eligible_for_care` (bool), `ineligible_reason` (str or None)
- Enqueued: from test result release pipeline
- Retry config: none
- Purpose: Comprehensive results-ready analytics — creates/updates `CareEligible` records, computes bundle and a-la-carte treatment eligibility, and fires "Results Ready" events to FullStory, Klaviyo, and Braze

**`send_urine_test_results_ready_analytics_events(urine_test_hash)`**
- Arguments: `urine_test_hash` (str)
- Enqueued: from UTI test result pipeline
- Retry config: none
- Purpose: Saves UTI care eligibility data (`CareEligible` record) when urine test results are processed

**`send_care_checkout_created_event(consult_uid)`**
- Arguments: `consult_uid` (str)
- Enqueued: `.delay()` expected from care checkout creation
- Retry config: none
- Purpose: Sends "Care Checkout Created" FullStory event with test/care pricing/treatment details

**`send_ungated_rx_order_paid_event(order_number)`**
- Arguments: `order_number` (str)
- Enqueued: `.delay()` from order payment processing
- Retry config: none
- Purpose: Sends "Ungated Paid" FullStory event and `URX_PURCHASE` Braze event when a symptom-relief RX order is paid

**`send_mpt_voucher_paid_event(user_id)`**
- Arguments: `user_id` (int)
- Enqueued: `.delay()` from order payment processing
- Retry config: none
- Purpose: Sends "MPT Voucher Paid" event to FullStory, Klaviyo, and Braze

**`send_consult_paid_event(consult_uid, order_number)`**
- Arguments: `consult_uid` (str), `order_number` (str)
- Enqueued: `.delay()` from care payment processing
- Retry config: none
- Purpose: Sends "Care Paid" analytics events to FullStory/Klaviyo/Braze; includes UTI-specific Braze event routing

**`send_any_paid_event(order_number)`**
- Arguments: `order_number` (str)
- Enqueued: `.delay()` from order payment flow
- Retry config: none
- Purpose: Sends "Any Paid" FullStory event for any order type with order type classification logic

**`send_prescription_refills_paid_event(prescription_refill_id, order_number)`**
- Arguments: `prescription_refill_id` (int), `order_number` (str)
- Enqueued: `.delay()` from `send_prescription_refill_request()` in ecomm tasks
- Retry config: none
- Purpose: Sends "Prescription Refills Paid" FullStory event when a refill order is fulfilled

**`send_additional_tests_checkout_created_event(test_hash)`**
- Arguments: `test_hash` (str)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends "Additional Tests Checkout Created" FullStory event

**`send_additional_tests_paid_event(test_hash, order_number)`**
- Arguments: `test_hash` (str, optional), `order_number` (str)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends "Additional Tests Paid" FullStory event

**`send_consult_intake_ineligible_event(consult_uid, refer_out_reason)`**
- Arguments: `consult_uid` (str), `refer_out_reason` (str)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends "Consult Intake Ineligible" FullStory event when a patient is referred out

**`send_rx_order_attached_to_account_klaviyo_event(consult_uid, order_number)`**
- Arguments: `consult_uid` (str), `order_number` (str)
- Enqueued: `.delay()` from `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult()`
- Retry config: none
- Purpose: Sends "RX Attached to Account" Klaviyo event when an ungated RX order is linked to a user's consult

**`send_consult_intake_submitted_event(consult_uid)`**
- Arguments: `consult_uid` (str)
- Enqueued: `.delay()` from Wheel consult submission task
- Retry config: none
- Purpose: Sends "Consult Intake Submitted" event to FullStory/Klaviyo/Braze, with UTI-specific event routing

**`send_coaching_call_completed_event(test_hash, coaching_call_notes_id=None, num_calls=None)`**
- Arguments: `test_hash` (str), `coaching_call_notes_id` (int, optional), `num_calls` (int, optional)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends "Coaching Call Completed" FullStory event

**`send_treatment_delivered_event(consult_uid)`**
- Arguments: `consult_uid` (str)
- Enqueued: `.delay()` from `send_treatment_probably_delivered_events_for_treatment_plans()`
- Retry config: none
- Purpose: Sends "Treatment Delivered" Klaviyo event with treatment dates and SKUs

**`send_estimated_treatment_started_events()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Daily scheduled task — queries treatment plans where start date is today or yesterday and fans out to `send_estimated_treatment_started_event` per plan

**`send_estimated_treatment_started_event(treatment_plan_id)`**
- Arguments: `treatment_plan_id` (int)
- Enqueued: `.delay()` from `send_estimated_treatment_started_events()`
- Retry config: none
- Purpose: Sends "Treatment Started" Klaviyo event for a specific treatment plan if the estimated start date is today or yesterday

**`send_test_delivered_klaviyo_event(test_hash)`**
- Arguments: `test_hash` (str)
- Enqueued: `.delay()` from shipping tasks
- Retry config: none
- Purpose: Sends "Test Kit Delivered" Klaviyo event when the test kit is delivered to the customer

**`send_health_history_completed_klaviyo_event(test_hash)`**
- Arguments: `test_hash` (str)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends "Health History Completed" Klaviyo event

**`send_updated_treatment_start_date_event(consult_uid)`**
- Arguments: `consult_uid` (str)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends "Updated Treatment Start Date" Klaviyo event when user changes their treatment start date

**`send_treatment_ended_event(treatment_plan_id)`**
- Arguments: `treatment_plan_id` (int)
- Enqueued: `.delay()` from `send_treatment_ended_events_for_treatment_plans()`
- Retry config: none
- Purpose: Sends "Treatment Ended" Klaviyo event and `TREATMENT_ENDED` Braze event for a specific treatment plan

**`send_treatment_ended_events_for_treatment_plans()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Daily scheduled task — fans out to `send_treatment_ended_event` for all treatment plans whose end date is today or yesterday

**`send_treatment_probably_delivered_events_for_treatment_plans()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Fans out "Treatment Delivered" events for treatment plans without a confirmed delivery timestamp but whose creation date suggests delivery has occurred (based on average fulfillment days)

**`send_provider_registered_event(provider_id)`**
- Arguments: `provider_id` (int)
- Enqueued: `.delay()` from provider registration flow
- Retry config: none
- Purpose: Sends "Provider Registered" Klaviyo event

**`send_provider_verified_event(provider_id)`**
- Arguments: `provider_id` (int)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends "[Provider] Provider Verified" Klaviyo event; includes guard check that provider is actually verified

**`send_provider_ordered_test_klaviyo_event(provider_id, provider_test_order_ids, payer, add_expanded_pcr=False, patient_email=None)`**
- Arguments: `provider_id` (int), `provider_test_order_ids` (list), `payer` (str), `add_expanded_pcr` (bool), `patient_email` (str, optional)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends "Provider Ordered A Test for User" to the patient's Klaviyo profile and "[Provider] Provider Ordered a Test" to the provider's profile; generates checkout link

**`send_provider_reminded_patient_klaviyo_event(provider_id, patient_email)`**
- Arguments: `provider_id` (int), `patient_email` (str)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends "Provider Reminded User to Purchase Test" Klaviyo event with checkout link

**`send_viewed_plan_klaviyo_event(test_id)`**
- Arguments: `test_id` (int)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends "Viewed Plan" Klaviyo event when a patient views their results plan

**`send_consult_intake_started_klaviyo_event(consult_uid)`**
- Arguments: `consult_uid` (str)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends "Consult Intake Started" Klaviyo event

**`send_three_weeks_after_treatment_delivered_klaviyo()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Sends "Consult Eligible for Refill" Klaviyo event to all consults eligible for prescription refills (~3 weeks post-treatment)

---

### `/Users/albertgwo/Work/evvy/backend/care/tasks.py`

**`update_treatment_end_date(treatment_plan_id)`**
- Arguments: `treatment_plan_id` (int)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Recomputes and saves the `treatment_end_date` on a TreatmentPlan

**`create_or_reset_calendar_treatments(treatment_plan_id)`**
- Arguments: `treatment_plan_id` (int)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Rebuilds the treatment calendar for a plan (deletes old calendar treatments, creates new ones based on current prescriptions)

**`heal_prescription_fill_orders()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Data integrity healing task — finds prescription fills modified in the last 24 hours with an order set but missing a `PrescriptionFillOrder` join table record and creates it

**`heal_otc_treatment_only_orders()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Data integrity healing task — finds OTC-only orders from the last day that were not processed through Precision pharmacy and re-triggers the fill pipeline for them

---

### `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py`

**`send_patient_ordered_provider_test_notification(patient_email, order_sku, order_provider_id)`**
- Arguments: `patient_email` (str), `order_sku` (str), `order_provider_id` (int)
- Enqueued: `.delay()` from order payment processing
- Retry config: none
- Purpose: Sends FYI admin email to B2B team when a patient pays for a provider-ordered test, noting whether the provider or patient is the payer

**`void_share_a_sale_transaction(order_number, order_date, reason)`**
- Arguments: `order_number` (str), `order_date` (str), `reason` (str)
- Enqueued: `.delay()` from order cancellation/refund flow
- Retry config: `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` — 3 attempts with exponential wait starting at 500ms (using `retrying` library, not Celery native retry)
- Purpose: Voids a ShareASale affiliate transaction via the ShareASale API when an order is cancelled

**`send_prescription_refill_request(order_id, prescription_fill_id)`**
- Arguments: `order_id` (int), `prescription_fill_id` (int)
- Enqueued: `.delay()` from subscription refill order processing
- Retry config: none (raises exception on failure, logged to ConsultTask)
- Purpose: Orchestrates the prescription refill pipeline — validates state restrictions and refill availability, updates fill status, and fans out to Precision pharmacy tasks (create patient → create prescriptions → create OTC treatments → send fill request); handles cancellations by calling cancel fill

**`send_otc_treatment_fill_request(order_id, prescription_fill_id)`**
- Arguments: `order_id` (int), `prescription_fill_id` (int)
- Enqueued: `.delay()` from OTC-only order processing and `heal_otc_treatment_only_orders()`
- Retry config: none
- Purpose: Sends OTC-only orders (no prescription required) to Precision pharmacy without state restriction checks

**`attach_unattached_orders_to_user(user_id)`**
- Arguments: `user_id` (int)
- Enqueued: `.delay()` when a user registers/signs in and matches historical orders
- Retry config: none
- Purpose: Finds all orders matching the user's email that are not yet assigned to a user, attaches them, and for ungated RX orders also creates/attaches consults

**`add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult(user_id, order_number)`**
- Arguments: `user_id` (int), `order_number` (str)
- Enqueued: `.delay()` and called directly
- Retry config: none
- Purpose: Core ungated RX logic — finds the latest in-progress consult for the user and adds the ordered treatments to it, or creates a new ungated RX consult; also pre-populates symptom fields from health history when applicable

**`create_consults_for_ungated_rx_orders_with_users_but_no_consult()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Backfill task — finds all ungated RX orders that have a user assigned but no consult and creates consults for them

**`process_gift_card_redemptions(order_id)`**
- Arguments: `order_id` (int)
- Enqueued: `.delay()`
- Retry config: none; re-raises on failure
- Purpose: Processes gift card redemptions (not purchases) for a specific order using `GiftCardRedemptionService`

**`process_gift_cards(order_id, payload=None)`**
- Arguments: `order_id` (int), `payload` (dict, optional Shopify payload)
- Enqueued: `.delay()`
- Retry config: none; re-raises on failure
- Purpose: Processes both gift card purchases and redemptions for an order; if no payload provided, only processes redemptions

**`reprocess_subscription_refill_orders_daily()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat daily scheduled task
- Retry config: none; re-raises on failure
- Purpose: Daily healing task — reprocesses subscription refill orders from the last 24 hours that were missed or incorrectly routed; delegates to `scripts.reprocess_subscription_refill_orders`

---

### `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py`

**`retry_failed_shopify_orders()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none; has `soft_time_limit=600` (10 min) and `time_limit=900` (15 min); catches `SoftTimeLimitExceeded`
- Purpose: Polls Shopify Admin API for all orders created in the last 3 days (up to 50 pages / 1,000 orders) and re-processes any that are missing from the local DB — a safety net for missed webhook deliveries

---

### `/Users/albertgwo/Work/evvy/backend/subscriptions/tasks.py`

**`cancel_expired_prescription_subscriptions()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat daily scheduled task
- Retry config: none; re-raises on failure
- Purpose: Cancels Recharge subscription plans for prescriptions that have run out of refills; delegates to `cancel_subscriptions_for_expired_prescriptions()` service

---

### `/Users/albertgwo/Work/evvy/backend/shipping/tasks.py`

**`update_individual_shipping_status(status_id)`**
- Arguments: `status_id` (int) — ID of a `ShippingStatus` record
- Enqueued: `.delay()` from `update_eligible_shipping_statuses_async()`
- Retry config: none
- Purpose: Updates the shipping status for a single kit or sample by calling USPS/FedEx tracking APIs

**`update_eligible_shipping_statuses_async()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Fans out individual shipping status update tasks for all active kit and sample shipments; uses different update frequencies depending on recency (daily for recent, every 3 days for stale, weekly for unactivated)

**`send_daily_express_orders_email()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat daily scheduled task
- Retry config: none
- Purpose: Sends a daily email + Google Sheets entry listing all express-shipping orders from the last 24 hours to the Berlin fulfillment operations team

**`process_tracking_statuses(test_hash, order_number, kit_tracking_number, sample_tracking_number, mode=MODE_ALL, from_csv=False)`**
- Arguments: `test_hash` (str), `order_number` (str), `kit_tracking_number` (str), `sample_tracking_number` (str), `mode` (str, default `"all"`), `from_csv` (bool)
- Enqueued: `.delay()` from Berlin fulfillment webhook handler
- Retry config: none
- Purpose: Core order fulfillment task — associates a test with its Shopify order, creates `ShippingStatus` records for kit and sample tracking numbers, handles duplicate tracking numbers and bulk orders, and marks the order fulfilled in Shopify via the Admin API

**`send_order_to_berlin_for_fulfillment(shopify_payload, is_order_cancellation, order_id)`**
- Arguments: `shopify_payload` (dict), `is_order_cancellation` (bool), `order_id` (int)
- Enqueued: `.delay()` from `retry_failed_berlin_order_fulfillments()`
- Retry config: none; re-raises on failure; NewRelic monitoring
- Purpose: Sends a test kit order to Berlin (fulfillment partner) via their API for kit creation and shipping; handles both new orders and cancellations

**`retry_failed_berlin_order_fulfillments()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Healing task — finds orders created after the Berlin integration launch (March 2024) that were not sent to Berlin and retries them via `send_order_to_berlin_for_fulfillment`

**`alert_if_no_orders_sent_to_berlin()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none; raises exception (which triggers Celery failure notification)
- Purpose: Monitoring/alerting task — sends admin email and raises an exception if no orders have been successfully sent to Berlin in the last 6 hours

**`alert_if_no_orders_created()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none; raises exception
- Purpose: Monitoring/alerting task — sends admin email and raises an exception if no orders have been created in Shopify in the last 6 hours (checks for Shopify/webhook pipeline failures)

---

### `/Users/albertgwo/Work/evvy/backend/shipping/precision/tasks.py`

**`process_precision_pharmacy_webhook(payload)`**
- Arguments: `payload` (dict) — Precision webhook body with `type`, `reference_id`, etc.
- Enqueued: `.delay()` from the Precision webhook view
- Retry config: none
- Purpose: Routes Precision pharmacy webhooks — handles `received`, `shipped` (triggers shipping notifications), `delivered` (triggers delivery notifications), and `warning` event types

**`send_prescription_to_precision(consult_uid, skip_set_sent_to_pharmacy=False)`**
- Arguments: `consult_uid` (str), `skip_set_sent_to_pharmacy` (bool)
- Enqueued: `.delay()` from Wheel consult completion pipeline and `send_missing_prescriptions_to_precision()`
- Retry config: none
- Purpose: Sends a new consult's prescription to Precision pharmacy (create patient + create/fill prescription); also tracks `CONSULT_ELIGIBLE_FOR_REFILLS` Braze event if applicable

**`send_create_patient_request_to_precision(prescription_fill_id, consult_uid=None, user_id=None, order_id=None)`**
- Arguments: `prescription_fill_id` (int); one of `consult_uid` (str), `user_id` (int), or `order_id` (int)
- Enqueued: called directly (not via `.delay()`) from `send_prescription_refill_request()` and `send_otc_treatment_fill_request()`
- Retry config: none (exception caught and logged)
- Purpose: Registers/upserts a patient in Precision pharmacy; stores returned `pharmacy_patient_id` on the prescription fill

**`send_create_prescription_request_to_precision(prescription_uid, fill_quantity=None, prescription_fill_prescription=None)`**
- Arguments: `prescription_uid` (str), `fill_quantity` (optional), `prescription_fill_prescription` (PrescriptionFillPrescriptions instance)
- Enqueued: called directly from `send_prescription_refill_request()`
- Retry config: none; on failure sets fill status to `WARNING` and re-raises
- Purpose: Creates a prescription record in Precision pharmacy for a specific medication

**`send_create_otc_treatment_request_to_precision(otc_treatment_uid, prescription_fill_otc_treatment_id)`**
- Arguments: `otc_treatment_uid` (str), `prescription_fill_otc_treatment_id` (int)
- Enqueued: called directly from `send_prescription_refill_request()` and `send_otc_treatment_fill_request()`
- Retry config: none; on failure sets fill status to `WARNING` and re-raises
- Purpose: Creates an OTC treatment record in Precision pharmacy

**`send_fill_request_to_precision(fill_uid, order_shipping_address=None)`**
- Arguments: `fill_uid` (int), `order_shipping_address` (optional)
- Enqueued: called directly from `send_prescription_refill_request()` and `send_otc_treatment_fill_request()`
- Retry config: none; on failure sets fill status to `WARNING` and re-raises; NewRelic monitoring
- Purpose: Sends the actual fill/dispense request to Precision pharmacy; updates consult `sent_to_pharmacy_at` timestamp on success

**`send_cancel_fill_request_to_precision(fill_uid)`**
- Arguments: `fill_uid` (int)
- Enqueued: called directly from `send_prescription_refill_request()` when order is cancelled
- Retry config: none; raises if fill already shipped/delivered
- Purpose: Cancels a prescription fill in Precision pharmacy

**`send_missing_prescriptions_to_precision()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Healing task — finds complete Precision-pharmacy consults from the last 2 days that have no `sent_to_pharmacy_at` timestamp and re-submits them after verifying prescriptions match recommendations

**`retry_failed_prescription_fills()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none at Celery level; internal logic: only retries fills modified >1 hour ago and <7 days old; fills failing >3 days are marked `FAILED` with a `ConsultTask` created; max 10 fills per run
- Purpose: Retries prescription fills stuck in `WARNING` status (failed Precision API calls)

**`send_notification_for_stuck_prescriptions()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Sends admin email listing prescription refill fills stuck in `CREATED` status for more than 3 business days

---

### `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`

**`send_provider_ordered_single_test_notifications(provider_email, patient_email, provider_test_order_id, payer, add_expanded_pcr=False)`**
- Arguments: `provider_email` (str), `patient_email` (str), `provider_test_order_id` (int), `payer` (str), `add_expanded_pcr` (bool)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends internal FYI admin email when a provider orders a single test for a patient

**`send_provider_bulk_ordered_tests_notification(provider_email, num_ordered, provider_test_order_ids)`**
- Arguments: `provider_email` (str), `num_ordered` (int), `provider_test_order_ids` (list)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends internal FYI admin email when a provider initiates a bulk test order (pending payment)

**`send_provider_bulk_order_paid_notification(ecomm_order_id, provider_email, quantity)`**
- Arguments: `ecomm_order_id` (int), `provider_email` (str), `quantity` (int)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends internal FYI admin email confirming a provider bulk test order has been paid

**`send_provider_test_results_ready(provider_email)`**
- Arguments: `provider_email` (str)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Sends a templated "results ready" email to the provider whose patient's test results are ready

---

### `/Users/albertgwo/Work/evvy/backend/test_results/tasks.py`

**`create_test_result_tagset(test_hash)`**
- Arguments: `test_hash` (str)
- Enqueued: called directly from `post_process_test_results()`; can also be called via `.delay()`
- Retry config: none
- Purpose: Creates/updates the `TestResultTagSet` for a test — computes pregnancy, menopause, symptoms, pathogen, and health context tags from the health history and test result

**`post_process_test_results(test_hash, release_results=True)`**
- Arguments: `test_hash` (str), `release_results` (bool, default True)
- Enqueued: `.delay()` from microgen task after NGS results are processed
- Retry config: none
- Purpose: Full post-processing pipeline after test results arrive — updates Valencia type, computes test scores, captures infection state, computes postmenopausal atrophy tag, builds tagset, assigns plan profile, assigns suspected yeast flag, creates recommended treatment program, and conditionally auto-releases results to the patient

**`assign_suspected_yeast_flag_to_test_result(test_hash)`**
- Arguments: `test_hash` (str)
- Enqueued: called directly from `post_process_test_results()`
- Retry config: none
- Purpose: Sets `suspected_yeast=True` on a test result if yeast is detected or if the patient has a recent yeast infection diagnosis in their health history

**`send_results_ready_emails(test_hash)`**
- Arguments: `test_hash` (str)
- Enqueued: `.delay()` from test result release pipeline
- Retry config: none; raises on send failure
- Purpose: Sends the "Results Ready" transactional email; also conditionally triggers care eligibility emails (email 1 for bundle-eligible, a-la-care eligibility email for a-la-care-only eligible)

**`send_test_status_duration_alert()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Monitoring task — checks MDX tests stuck in `RECEIVED`, `SEQUENCING`, or `PROCESSING` status beyond alert thresholds (7 days / 7 days / 4 days respectively) and sends a summary admin email

**`send_lab_test_status_duration_alert()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Monitoring task — checks PCR `LabTest` records stuck in `AT_LAB` status for more than 3 days and sends admin email

**`send_vip_test_status_update(test_hash, previous_status, new_status)`**
- Arguments: `test_hash` (str), `previous_status` (str), `new_status` (str)
- Enqueued: `.delay()` when a VIP/provider test changes status
- Retry config: none
- Purpose: Sends internal admin email with test status change details for VIP (provider-ordered) tests

---

### `/Users/albertgwo/Work/evvy/backend/test_results/microgen/tasks.py`

**`submit_lab_order_approval_to_microgen(lab_order_uid)`**
- Arguments: `lab_order_uid` (str)
- Enqueued: called directly from `fetch_and_process_completed_lab_order_details()` and `.delay()` from `submit_missing_lab_order_approvals_to_microgen()`
- Retry config: none; raises if lab order not approved
- Purpose: Submits an approved lab order's data to Microgen (MDX lab) API and records the submission timestamp

**`submit_research_sample_lab_order_to_microgen(test_hash)`**
- Arguments: `test_hash` (str)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Submits a research-type test's electronic lab order to Microgen

**`submit_missing_lab_order_approvals_to_microgen()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Healing task — finds approved lab orders from the last 60 days not yet submitted to Microgen and re-submits them

**`process_test_results_stuck_in_sequencing_status()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Healing task — for tests stuck in sequencing for 7–60 days without errors, tries to fetch and process results from S3

**`process_microgen_test_results(test_hash, report_errors=True, read_from_staging=False, release_results=True, bypass_ready_check=False, force_update_result_value=False)`**
- Arguments: `test_hash` (str), plus several optional boolean flags for processing behavior
- Enqueued: `.delay()` or `.apply_async(countdown=delay_seconds)` from `process_lab_status_update()` and from `process_test_results_stuck_in_sequencing_status()`
- Retry config: none at Celery level; load balancing via random countdown delay (`RESULTS_PROCESSING_MAX_DELAY_MINUTES` setting)
- Purpose: Processes Microgen NGS results file from S3 and then triggers `post_process_test_results`

**`process_microgen_test_results_if_exists_in_s3(test_hash)`**
- Arguments: `test_hash` (str)
- Enqueued: `.delay()` from `process_test_results_stuck_in_sequencing_status()`
- Retry config: none; catches S3 `NoSuchKey` silently, re-raises other errors
- Purpose: Safe wrapper around `process_microgen_test_results()` that ignores missing S3 files

**`process_microgen_vag_pcr_test_results(test_hash)`**
- Arguments: `test_hash` (str)
- Enqueued: `.delay()` from `process_lab_status_update()` on "partial-results" webhook with panel "vag-sti"
- Retry config: none
- Purpose: Processes vaginal PCR (vaginitis STI panel) results from S3; re-computes test scores if full results are ready; triggers PCR results ready email and Braze/Klaviyo events

**`send_summary_tests_entered_sequencing()`** (no arguments)
- Arguments: none
- Enqueued: `.apply_async(countdown=...)` via `_queue_summary_notification("sequencing")` with Redis cache lock
- Retry config: none
- Purpose: Sends lab team notification email with count and list of tests that entered sequencing in the last 2 hours

**`send_summary_vpcr_results_processed()`** (no arguments)
- Arguments: none
- Enqueued: `.apply_async(countdown=...)` via `_queue_summary_notification("partial-results")`
- Retry config: none
- Purpose: Sends lab team notification email with count of PCR results processed in last 2 hours

**`send_summary_vngs_results_processed()`** (no arguments)
- Arguments: none
- Enqueued: `.apply_async(countdown=...)` via `_queue_summary_notification("ready")`
- Retry config: none
- Purpose: Sends lab team notification email with count of NGS (full sequencing) results processed in last 2 hours

**`process_lab_status_update_batch(payload)`**
- Arguments: `payload` (dict with `status_updates` list)
- Enqueued: `.delay()` from Microgen webhook batch endpoint
- Retry config: none
- Purpose: Fan-in for batch lab status updates from Microgen — routes each individual update to `process_lab_status_update()` which handles status transitions (received → sequencing → partial-results → negative → low-reads → ready)

---

### `/Users/albertgwo/Work/evvy/backend/transactional_email/tasks.py`

This file has many transactional email tasks, all following similar patterns (query-based or ID-based).

**`send_test_activated_reminder()`** — Scheduled; sends reminder to users who activated their test 4+ days ago but haven't progressed to "taken"

**`send_tests_in_transit_through_usps_and_fedex_emails()`** — Scheduled; sends "in transit" email with tracking links for tests that entered transit in last 3 days

**`send_tests_in_transit_hh_incomplete()`** — Scheduled; sends email to users whose test is in transit but health history is incomplete

**`send_tests_received_at_lab_hh_incomplete()`** — Scheduled; sends email when test received at lab but health history not yet submitted

**`send_ldt_test_sample_received_email(test_hash)`** — Args: `test_hash` (str); triggered by Microgen webhook; sends "sample received at lab" email (template differs for comprehensive vs standard tests)

**`send_ldt_test_sample_sequencing_email(test_hash)`** — Args: `test_hash` (str); triggered by Microgen webhook; sends "sample sequencing" email

**`send_ldt_tests_results_almost_ready()`** — Scheduled; sends "almost ready" email to users whose LDT tests have been in sequencing for ~10 days

**`send_pcr_test_results_ready(test_hash)`** — Args: `test_hash` (str); triggered after PCR results processed; sends PCR results ready email

**`send_expert_call_emails()`** — Scheduled; sends expert coaching call offer email ~1 day after results ready, excluding users already in care

**`send_view_unread_plan_emails()`** — Scheduled; sends email 3 days after results viewed if treatment plan not yet viewed

**`send_eligible_for_care_1_for_test(test_id)`** — Args: `test_id` (int); triggered from `send_results_ready_emails()`; sends first care eligibility email

**`send_eligible_for_a_la_care_not_treatment_program(test_id)`** — Args: `test_id` (int); triggered from `send_results_ready_emails()`; sends a-la-care eligibility email for patients not eligible for bundle care

**`send_a_la_care_treatments_ready(consult_uid)`** — Args: `consult_uid` (str); triggered when individual a-la-care treatments are ready

**`send_eligible_for_care_2()`** — Scheduled; sends second care eligibility email 6 days after results ready

**`send_eligible_for_care_3()`** — Scheduled; sends third care eligibility email 12 days after results ready

**`send_treatments_shipped(prescription_fill_id)`** — Args: `prescription_fill_id` (int); triggered by Precision shipped webhook; sends treatments shipped email with tracking

**`send_treatments_delivered(prescription_fill_id)`** — Args: `prescription_fill_id` (int); triggered by Precision delivered webhook; sends treatments delivered email

**`send_consult_intake_abandonment_reminder()`** — Scheduled; sends reminder 2–6 hours after care checkout if intake not started

**`send_consult_intake_abandonment_reminder_2()`** — Scheduled; sends second reminder 24–48 hours after checkout

**`send_sti_consult_intake_abandonment_reminder()`** — Scheduled; sends STI-specific abandonment reminder 24–36 hours after checkout

**`send_sti_prescription_sent_to_pharmacy_email(consult_uid)`** — Args: `consult_uid` (str); sends STI prescription pickup info email

**`send_email_organon_prescriptions_ready(consult_uid)`** — Args: `consult_uid` (str); sends Organon (local pickup) pharmacy prescription ready email

**`send_consult_intake_reviewed_email(consult_uid)`** — Args: `consult_uid` (str); triggered after Wheel completes consult review

**`send_treatment_plan_ready_email(consult_uid)`** — Args: `consult_uid` (str); sends treatment plan ready email with link

**`send_lab_order_rejected_email(lab_order_uid)`** — Args: `lab_order_uid` (str); sends email when a lab order is rejected

**`send_id_verification_failed_email(consult_uid)`** — Args: `consult_uid` (str); sends ID verification failure email (allows duplicate sends)

**`send_care_referred_out_email(consult_uid)`** — Args: `consult_uid` (str); sends referred-out email when consult is auto-referred

**`send_new_consult_message_email(consult_uid)`** — Args: `consult_uid` (str); sends new message notification email (allows duplicates)

**`send_care_first_check_in_email()`** — Scheduled; sends first care check-in email 4 hours after treatment plan ready for bundle purchase patients

**`send_prescription_refills_available()`** — Scheduled; sends prescription refill availability email to all eligible consults

**`send_sample_taken_but_not_in_transit_reminder()`** — Scheduled; sends reminder to patients whose sample is taken but not yet in transit after 5 days

**`send_test_sample_at_lab_but_not_activated(test_hash)`** — Args: `test_hash` (str); sends email to activate a test that arrived at the lab unactivated

**`send_test_sample_received_at_lab_but_not_activated()`** — Scheduled; query version of the above for all test types

**`send_account_transfer_verification_email(user_id, order_email, order_number)`** — Args: `user_id` (int), `order_email` (str), `order_number` (str); sends order transfer verification email when a user's Evvy account email differs from their order email; creates `OrderTransferVerification` record

All transactional email tasks have no Celery-level retry configuration.

---

### `/Users/albertgwo/Work/evvy/backend/consults/wheel/tasks.py`

**`submit_async_consult(consult_uid)`**
- Arguments: `consult_uid` (str)
- Enqueued: `.delay()` from consult intake submission; also called from `retry_creating_async_consults()` and `retry_errored_consult_creation()`
- Retry config: none
- Purpose: Entry point for consult submission — sets recommended prescriptions, determines if manual review is needed (if so creates a `ConsultReview`), otherwise submits directly to Wheel

**`submit_consult_intake_to_wheel(consult_uid)`**
- Arguments: `consult_uid` (str)
- Enqueued: called directly from `submit_async_consult()` or `.delay()` after manual review passes
- Retry config: none; re-raises on failure; NewRelic monitoring
- Purpose: Sends consult intake data to Wheel API and triggers intake-submitted analytics event and intake-reviewed email

**`issue_lab_results_to_wheel_for_lab_test(lab_test_id)`**
- Arguments: `lab_test_id` (str)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Issues lab results to Wheel for a specific lab test (VNGS/VPCR/Urine type); skip if already sent

**`resubmit_consult_photo_id_info_to_wheel(consult_uid)`**
- Arguments: `consult_uid` (str)
- Enqueued: `.delay()` from ID verification retry flow
- Retry config: none
- Purpose: Re-submits updated photo ID via Wheel `amend_patient` when previous ID verification failed

**`fetch_and_process_completed_consult_details(consult_uid)`**
- Arguments: `consult_uid` (str)
- Enqueued: `.delay()` from Wheel webhook on consult completion
- Retry config: none
- Purpose: Fetches clinician, diagnosis, and prescription details from Wheel for a completed consult; stores all details and triggers `check_recommended_prescriptions_against_prescribed_and_send_prescriptions`

**`fetch_and_process_completed_lab_order_details(lab_order_uid)`**
- Arguments: `lab_order_uid` (str)
- Enqueued: `.delay()` from Wheel lab order approval webhook
- Retry config: none
- Purpose: Fetches Wheel-approved lab order details and routes to appropriate lab provider (Junction for urine tests, Microgen for vaginal tests)

**`retry_consult_detail_processing()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Healing task — finds consults stuck in `IN_PROGRESS`/`SUBMITTED`/`ERROR` for 24+ hours that Wheel shows as finished and re-processes them

**`retry_creating_async_consults()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Healing task — retries submission for consults in `SUBMITTED` state (not yet sent to Wheel) from 1–5 days ago

**`retry_errored_consult_creation()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Healing task — retries consults stuck in `ERROR` state that never reached Wheel

**`fetch_and_process_follow_up_consult_details(lab_order_uid, follow_up_external_id)`**
- Arguments: `lab_order_uid` (str), `follow_up_external_id` (str)
- Enqueued: `.delay()` from `send_notification_for_diagnosis_pending_consults()`
- Retry config: none
- Purpose: Fetches Wheel follow-up consult details for lab result interpretation; handles diagnosis confirmation, disagreement (creates amendment task), and UTI-specific flows

**`check_recommended_prescriptions_against_prescribed_and_send_prescriptions(consult_uid)`**
- Arguments: `consult_uid` (str)
- Enqueued: `.delay()` from `_post_prescription_fetch_and_process_consult_details()`
- Retry config: none
- Purpose: Validates recommended vs actually prescribed medications match; if they match, marks consult complete and sends to Precision pharmacy; if mismatch, creates a `ConsultReview` for manual review

**`check_recommended_prescriptions_against_prescribed(consult_uid, notify_admins=False)`**
- Arguments: `consult_uid` (str), `notify_admins` (bool)
- Enqueued: `.delay()` and called directly
- Retry config: none
- Purpose: Compares recommended vs actual prescriptions; optionally creates `ConsultReview` on mismatch

**`fetch_and_process_referred_consult_details(consult_uid)`**
- Arguments: `consult_uid` (str)
- Enqueued: `.delay()` from Wheel webhook (referred-out disposition) and `retry_consult_detail_processing()`
- Retry config: none
- Purpose: Stores referral info from Wheel, creates a `ConsultTask` for referred-out handling, marks consult as `REFERRED`, and sends refer-out email

**`submit_lab_order_to_wheel(lab_order_uid)`**
- Arguments: `lab_order_uid` (str)
- Enqueued: `.delay()` from `resubmit_stuck_lab_orders_to_wheel()` and `resubmit_errored_lab_orders_to_wheel()`
- Retry config: none; returns early if already submitted/approved
- Purpose: Submits a lab order to Wheel for requisition approval

**`resubmit_stuck_lab_orders_to_wheel()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Finds lab orders in `CREATED`/`SUBMITTED` state with a Wheel provider ID and an intake submitted >1 hour ago and resubmits them (with provider_id cleared to force new submission); skips Canadian lab orders

**`resubmit_errored_lab_orders_to_wheel()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Re-submits all lab orders in `ERROR` state to Wheel; skips Canadian orders and orders where results have already been sent (to prevent status regression)

**`mark_wheel_consult_message_as_read(consult_uid, message_id)`**
- Arguments: `consult_uid` (str), `message_id` (str)
- Enqueued: `.delay()`
- Retry config: none
- Purpose: Marks a Wheel consult message as read via the Wheel API

**`send_notification_for_stuck_consults()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Sends admin emails for: (1) non-UTI consults stuck in clinical review for 24+ hours, (2) lab orders stuck in processing, (3) open manual review items (UTI excluded from all — handled by a separate task)

**`send_notification_for_stuck_uti_consults()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: UTI-specific variant of the above — alerts for UTI consults in review for 24+ hours and open UTI manual reviews

**`send_notification_for_diagnosis_pending_consults(hours_threshold=24)`**
- Arguments: `hours_threshold` (int, default 24)
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Monitoring task — finds VHT and UTI tests where the Wheel follow-up was sent but diagnosis (infection state confirmation) is still pending after the threshold; sends admin email and re-triggers `fetch_and_process_follow_up_consult_details` for each pending one

**`send_notification_for_care_orders_in_bad_states()`** (no arguments)
- Arguments: none
- Enqueued: Celery beat scheduled task
- Retry config: none
- Purpose: Data integrity monitoring — alerts for care orders without consults, completed consults without prescription fills, and ungated RX orders without consults (all scoped to orders from 5–10 days ago)

**`attach_latest_otc_treatment_to_consult(consult)`**
- Arguments: `consult` (Consult object, not an ID)
- Enqueued: called directly from `_post_prescription_fetch_and_process_consult_details()` — note: takes a model instance, not a serializable ID, so this is unusual for a Celery task and should only be called synchronously
- Retry config: none
- Purpose: Attaches the user's latest probiotic OTC treatment to their consult if they have an active probiotic subscription

---

### `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py`

**`create_unregistered_testkit_order_for_urine_test(urine_test_ids, ecomm_order_id)`**
- Arguments: `urine_test_ids` (list of int), `ecomm_order_id` (int)
- Enqueued: `.delay()` from urine test order processing
- Retry config: none; exceptions caught per-test and reported via Slack alert
- Purpose: Creates unregistered testkit orders in Junction (UTI lab provider) when UTI orders are placed; stores `external_order_id` on the `LabOrder` and pre-populates `LabOrderIntake` address from the Shopify shipping address for later Wheel registration

**`submit_lab_order_approval_to_junction(lab_order_uid)`**
- Arguments: `lab_order_uid` (str)
- Enqueued: `.delay()` from `_route_approved_lab_order_to_provider()` in Wheel tasks
- Retry config: `bind=True, max_retries=3, default_retry_delay=60`; retries on 5xx HTTP errors and timeouts with exponential backoff (60s, 120s, 240s); 4xx errors are not retried; `task_failure` signal connected to `handle_junction_submission_failure` for final failure alerting
- Purpose: Registers (activates) a previously created unregistered testkit in Junction after Wheel approves the lab order and provides clinician NPI; marks `electronic_order_submitted_at` on success

**`fetch_and_process_junction_results(external_order_id)`**
- Arguments: `external_order_id` (str) — Junction's external order ID
- Enqueued: `.delay()` from Junction results-ready webhook handler
- Retry config: `bind=True, max_retries=3`; exponential backoff starting at 60s, capped at 300s (60s, 120s, 240s)
- Purpose: Fetches UTI lab results from Junction API and processes them through `LabServicesOrchestrator`; decouples webhook response from API call to prevent webhook timeouts

**`fulfill_uti_order_in_shopify(urine_test_id, tracking_number, courier)`**
- Arguments: `urine_test_id` (int), `tracking_number` (str), `courier` (str)
- Enqueued: `.delay()` from Junction shipping webhook handler
- Retry config: none
- Purpose: Marks UTI test kit line items as fulfilled in Shopify with Junction-provided tracking information when the test kit ships to the customer

---

## Summary of Retry Configurations

Only three tasks have meaningful Celery-native retry logic:

| Task | File | Retry Config |
|------|------|-------------|
| `void_share_a_sale_transaction` | `ecomm/tasks.py` | 3 attempts, 500ms exponential wait (via `retrying` library, not Celery) |
| `submit_lab_order_approval_to_junction` | `junction/tasks.py` | 3 retries, exponential backoff 60s/120s/240s; only on 5xx/timeout |
| `fetch_and_process_junction_results` | `junction/tasks.py` | 3 retries, exponential backoff 60s/120s/240s (capped at 300s) |

All other tasks have no Celery-level retry configuration and rely on healing/monitoring scheduled tasks to recover from failures.
