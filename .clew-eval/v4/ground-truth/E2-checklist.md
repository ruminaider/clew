# E2 Ground Truth Checklist: Celery Task Inventory

Source codebase: `/Users/albertgwo/Work/evvy/backend`
Task files searched: all `**/tasks.py` under `backend/` (excluding worktrees and venv).

---

## E2 Ground Truth Checklist

### app / infrastructure tasks

- [ ] Artifact 1: `clean_log_entries` (`backend/app/tasks.py`)
  - Args: `delete_all=False`
  - Enqueue: not found enqueued via `.delay()` — likely called from celery beat schedule
  - Retry: none
  - Purpose: Deletes auditlog `LogEntry` records older than 30 days (retention cleanup)

### accounts tasks

- [ ] Artifact 2: `send_intake_completed_notifications` (`backend/accounts/tasks.py`)
  - Args: `provider_email`
  - Enqueue: `.delay(user.email)` at `api/v1/views/account.py:253`
  - Retry: none
  - Purpose: Sends admin email notifications when a B2B provider completes their intake form

### analytics tasks (backend/analytics/tasks.py — large file, 38+ tasks)

- [ ] Artifact 3: `send_custom_analytics_event_to_fullstory_async` (`backend/analytics/tasks.py`)
  - Args: `user_id, event_name, event_properties, use_recent_session`
  - Enqueue: `.delay(user.id, event_name, event_properties, use_recent_session_fullstory)` at `analytics/tasks.py:131`
  - Retry: none
  - Purpose: Generic async wrapper for sending a custom event to Fullstory

- [ ] Artifact 4: `send_custom_analytics_event_to_klaviyo_async` (`backend/analytics/tasks.py`)
  - Args: `payload` (Klaviyo event dict)
  - Enqueue: `.delay(payload)` at `analytics/tasks.py:158`
  - Retry: none
  - Purpose: Generic async wrapper for sending a custom event to Klaviyo

- [ ] Artifact 5: `send_results_ready_analytics_events` (`backend/analytics/tasks.py`)
  - Args: `test_hash: str, eligible_for_care: bool, ineligible_reason: str | None`
  - Enqueue: `.delay(test_hash, eligible_for_care, ineligible_reason)` at `test_results/utils.py:3252`
  - Retry: none
  - Purpose: Fires "Results Ready" analytics events to Fullstory, Klaviyo, and Braze; creates/updates `CareEligible` records with bundle and a-la-carte eligibility

- [ ] Artifact 6: `send_urine_test_results_ready_analytics_events` (`backend/analytics/tasks.py`)
  - Args: `urine_test_hash: str`
  - Enqueue: `.delay(urine_test.hash)` at `test_results/lab_services/providers/junction/results_processor.py:139` and `test_results/post_processing_utils.py:429`
  - Retry: none
  - Purpose: Saves UTI care eligibility records for urine tests when results are ready

- [ ] Artifact 7: `send_sample_sequencing_provider_klaviyo_event` (`backend/analytics/tasks.py`)
  - Args: `test_hash: str, provider_test_order_id: int`
  - Enqueue: `.delay(test_hash, provider_test_order.id)` at `test_results/microgen/tasks.py:403`
  - Retry: none
  - Purpose: Fires "[Provider] Sample Sequencing" Klaviyo event to provider when their patient's sample enters sequencing

- [ ] Artifact 8: `send_pcr_test_results_ready_provider_klaviyo_event` (`backend/analytics/tasks.py`)
  - Args: `test_hash: str, provider_test_order_id: int`
  - Enqueue: `.delay(test_hash, provider_test_order.id)` at `test_results/microgen/tasks.py:187`
  - Retry: none
  - Purpose: Fires "[Provider] Preliminary Results Ready" Klaviyo event when PCR results are available

- [ ] Artifact 9: `send_consult_paid_event` (`backend/analytics/tasks.py`)
  - Args: `consult_uid, order_number`
  - Enqueue: `.delay(consult.uid, order.provider_id)` at `ecomm/utils.py:1874`
  - Retry: none
  - Purpose: Fires "Care Paid" analytics event (Fullstory, Klaviyo, Braze) when a consult is paid; handles UTI-specific Braze events

- [ ] Artifact 10: `send_any_paid_event` (`backend/analytics/tasks.py`)
  - Args: `order_number: str`
  - Enqueue: `.delay(order.order_number)` at `ecomm/utils.py:744`
  - Retry: none
  - Purpose: Fires "Any Paid" Fullstory event for any paid order; categorizes order type (test, care, refill, etc.)

- [ ] Artifact 11: `send_prescription_refills_paid_event` (`backend/analytics/tasks.py`)
  - Args: `prescription_refill_id, order_number`
  - Enqueue: `.delay(prescription_fill_id, order.provider_id)` at `ecomm/tasks.py:229`
  - Retry: none
  - Purpose: Fires "Prescription Refills Paid" Fullstory event when a prescription refill order is paid

- [ ] Artifact 12: `send_treatment_delivered_event` (`backend/analytics/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(treatment_plan.consult.uid)` at `analytics/tasks.py:1335`; also at `shipping/precision/utils.py:599`
  - Retry: none
  - Purpose: Fires "Treatment Delivered" Klaviyo event with treatment dates and SKUs when treatment is delivered

- [ ] Artifact 13: `send_estimated_treatment_started_events` (`backend/analytics/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule (no `.delay()` call site — this is the beat task that fans out)
  - Retry: none
  - Purpose: Periodic task that finds treatment plans with start dates matching today, fans out to `send_estimated_treatment_started_event` per plan

- [ ] Artifact 14: `send_estimated_treatment_started_event` (`backend/analytics/tasks.py`)
  - Args: `treatment_plan_id: int`
  - Enqueue: `.delay(treatment_plan.id)` at `analytics/tasks.py:1154`
  - Retry: none
  - Purpose: Fires "Treatment Started" Klaviyo event for a specific treatment plan if start date is today or yesterday

- [ ] Artifact 15: `send_treatment_ended_event` (`backend/analytics/tasks.py`)
  - Args: `treatment_plan_id: int`
  - Enqueue: `.delay(treatment_plan.id)` at `analytics/tasks.py:1320`
  - Retry: none
  - Purpose: Fires "Treatment Ended" Klaviyo event and Braze `TREATMENT_ENDED` event for a specific treatment plan

- [ ] Artifact 16: `send_treatment_ended_events_for_treatment_plans` (`backend/analytics/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic task — finds treatment plans with end date today or yesterday, fans out to `send_treatment_ended_event` per plan

- [ ] Artifact 17: `send_treatment_probably_delivered_events_for_treatment_plans` (`backend/analytics/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic task — finds treatment plans past average fulfillment window with no delivered timestamp, fires treatment delivered events

- [ ] Artifact 18: `send_consult_intake_submitted_event` (`backend/analytics/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(consult_uid)` at `consults/wheel/tasks.py:162`
  - Retry: none
  - Purpose: Fires "Consult Intake Submitted" analytics event to Fullstory, Klaviyo, Braze; handles UTI-specific Braze event

- [ ] Artifact 19: `send_care_checkout_created_event` (`backend/analytics/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(consult.uid)` at `api/v1/views/consult.py:463` and `api/v1/views/consult.py:563`
  - Retry: none
  - Purpose: Fires "Care Checkout Created" Fullstory event with test and pricing details when care checkout is created

- [ ] Artifact 20: `send_consult_intake_ineligible_event` (`backend/analytics/tasks.py`)
  - Args: `consult_uid, refer_out_reason`
  - Enqueue: `.delay(consult.uid, refer_out_reason)` at `consults/utils.py:218`
  - Retry: none
  - Purpose: Fires "Consult Intake Ineligible" Fullstory event when a consult is referred out

- [ ] Artifact 21: `send_mpt_voucher_paid_event` (`backend/analytics/tasks.py`)
  - Args: `user_id`
  - Enqueue: `.delay(user.id)` at `ecomm/utils.py:1138`
  - Retry: none
  - Purpose: Fires "MPT Voucher Paid" event to Fullstory, Klaviyo, Braze when an MPT voucher is purchased

- [ ] Artifact 22: `send_ungated_rx_order_paid_event` (`backend/analytics/tasks.py`)
  - Args: `order_number`
  - Enqueue: `.delay(order.order_number)` at `ecomm/utils.py:691`
  - Retry: none
  - Purpose: Fires "Ungated Paid" Fullstory event and Braze `URX_PURCHASE` event for symptom-relief RX orders

- [ ] Artifact 23: `send_additional_tests_checkout_created_event` (`backend/analytics/tasks.py`)
  - Args: `test_hash`
  - Enqueue: `.delay(test_kit.hash)` at `api/v1/views/user_tests.py:873`
  - Retry: none
  - Purpose: Fires "Additional Tests Checkout Created" Fullstory event

- [ ] Artifact 24: `send_additional_tests_paid_event` (`backend/analytics/tasks.py`)
  - Args: `test_hash, order_number`
  - Enqueue: `.delay(None, order.provider_id)` at `ecomm/utils.py:1990`; `.delay(test_kit.hash, order.provider_id)` at `ecomm/utils.py:2009`
  - Retry: none
  - Purpose: Fires "Additional Tests Paid" Fullstory event

- [ ] Artifact 25: `send_rx_order_attached_to_account_klaviyo_event` (`backend/analytics/tasks.py`)
  - Args: `consult_uid, order_number`
  - Enqueue: `.delay(consult.uid, order.order_number)` at `ecomm/tasks.py:460`
  - Retry: none
  - Purpose: Fires "RX Attached to Account" Klaviyo event when an ungated RX order is attached to a user account

- [ ] Artifact 26: `send_provider_registered_event` (`backend/analytics/tasks.py`)
  - Args: `provider_id`
  - Enqueue: `.delay(user.id)` at `api/v1/views/register.py:238`
  - Retry: none
  - Purpose: Fires "Provider Registered" Klaviyo event when a provider completes registration

- [ ] Artifact 27: `send_provider_verified_event` (`backend/analytics/tasks.py`)
  - Args: `provider_id`
  - Enqueue: `.delay(provider_profile.provider.id)` at `accounts/admin_actions.py:270`
  - Retry: none
  - Purpose: Fires "[Provider] Provider Verified" Klaviyo event when a provider is verified by admin

- [ ] Artifact 28: `send_provider_ordered_test_klaviyo_event` (`backend/analytics/tasks.py`)
  - Args: `provider_id, provider_test_order_ids, payer, add_expanded_pcr=False, patient_email=None`
  - Enqueue: `.delay(...)` at `api/v1/views/provider_test_orders.py:112` and `api/v1/views/provider_test_orders.py:262`
  - Retry: none
  - Purpose: Fires "Provider Ordered A Test for User" (patient Klaviyo) and "[Provider] Provider Ordered a Test" (provider Klaviyo) events

- [ ] Artifact 29: `send_provider_reminded_patient_klaviyo_event` (`backend/analytics/tasks.py`)
  - Args: `provider_id, patient_email`
  - Enqueue: `.delay(provider.id, patient_email)` at `api/v1/views/provider_test_orders.py:310`
  - Retry: none
  - Purpose: Fires "Provider Reminded User to Purchase Test" Klaviyo event

- [ ] Artifact 30: `send_viewed_plan_klaviyo_event` (`backend/analytics/tasks.py`)
  - Args: `test_id`
  - Enqueue: `.delay(test.id)` at `api/v1/views/my_plan.py:46`
  - Retry: none
  - Purpose: Fires "Viewed Plan" Klaviyo event when a user views their results plan

- [ ] Artifact 31: `send_consult_intake_started_klaviyo_event` (`backend/analytics/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(intake.consult.uid)` at `api/v1/views/consult.py:799` and `:859`
  - Retry: none
  - Purpose: Fires "Consult Intake Started" Klaviyo event

- [ ] Artifact 32: `send_health_history_completed_klaviyo_event` (`backend/analytics/tasks.py`)
  - Args: `test_hash`
  - Enqueue: `.delay(test.hash)` at `api/v1/views/user_tests.py:945`
  - Retry: none
  - Purpose: Fires "Health History Completed" Klaviyo event

- [ ] Artifact 33: `send_three_weeks_after_treatment_delivered_klaviyo` (`backend/analytics/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic task — finds consults eligible for refill (~3 weeks after delivery), fires "Consult Eligible for Refill" Klaviyo event

- [ ] Artifact 34: `send_test_delivered_klaviyo_event` (`backend/analytics/tasks.py`)
  - Args: `test_hash`
  - Enqueue: `.delay(test.hash)` at `shipping/utils.py:231`
  - Retry: none
  - Purpose: Fires "Test Kit Delivered" Klaviyo event when a test kit is delivered to the customer

- [ ] Artifact 35: `send_updated_treatment_start_date_event` (`backend/analytics/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(consult.uid)` at `api/v1/views/consult.py:366`
  - Retry: none
  - Purpose: Fires "Updated Treatment Start Date" Klaviyo event when user updates treatment start date

- [ ] Artifact 36: `send_coaching_call_completed_event` (`backend/analytics/tasks.py`)
  - Args: `test_hash, coaching_call_notes_id=None, num_calls=None`
  - Enqueue: `.delay(instance.test.hash, instance.id, num_calls)` at `test_results/signals.py:490`
  - Retry: none
  - Purpose: Fires "Coaching Call Completed" Fullstory event

### care tasks (backend/care/tasks.py)

- [ ] Artifact 37: `update_treatment_end_date` (`backend/care/tasks.py`)
  - Args: `treatment_plan_id: int`
  - Enqueue: `.delay(treatment_plan.id)` at `consults/signals.py:140`; `.delay(treatment_plan.id)` at `api/v1/views/consult.py:363`; `.delay(instance.treatment_plan_id)` at `care/signals.py:86`
  - Retry: none
  - Purpose: Computes and saves the treatment end date for a treatment plan

- [ ] Artifact 38: `create_or_reset_calendar_treatments` (`backend/care/tasks.py`)
  - Args: `treatment_plan_id: int`
  - Enqueue: `.apply_async((treatment_plan_id,), countdown=X)` at `care/signals.py:121` and `care/signals.py:129` (with countdown delay)
  - Retry: none (uses `apply_async` with countdown for scheduling, not retry)
  - Purpose: Deletes and recreates calendar treatments for a treatment plan based on prescriptions

- [ ] Artifact 39: `heal_prescription_fill_orders` (`backend/care/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic healing task — finds prescription fills modified in last 24h with an order but no `PrescriptionFillOrder`, creates missing records

- [ ] Artifact 40: `heal_otc_treatment_only_orders` (`backend/care/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic healing task — finds OTC-only orders that were not routed to Precision, creates prescription fills and sends OTC fill requests

### ecomm tasks (backend/ecomm/tasks.py)

- [ ] Artifact 41: `send_patient_ordered_provider_test_notification` (`backend/ecomm/tasks.py`)
  - Args: `patient_email, order_sku, order_provider_id`
  - Enqueue: `.delay(patient_email, order_sku, order_provider_id)` at `ecomm/utils.py:1778`
  - Retry: none
  - Purpose: Sends admin FYI email to B2B ops team when a patient pays for a provider-ordered test

- [ ] Artifact 42: `void_share_a_sale_transaction` (`backend/ecomm/tasks.py`)
  - Args: `order_number, order_date, reason`
  - Enqueue: `.delay(order_number, order_date, note)` at `ecomm/utils.py:416`
  - Retry: `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` — retries up to 3 times with exponential backoff starting at 500ms
  - Purpose: Voids a ShareASale affiliate commission transaction via their API when an order is cancelled/refunded

- [ ] Artifact 43: `send_prescription_refill_request` (`backend/ecomm/tasks.py`)
  - Args: `order_id, prescription_fill_id`
  - Enqueue: `.delay(order.id, prescription_fill.id)` at `ecomm/utils.py:2198`; `.delay(order.id, prescription_fill.id)` at `scripts/reprocess_subscription_refill_orders.py:229`
  - Retry: none
  - Purpose: Orchestrates prescription refill fulfillment — validates state restrictions, checks remaining refills, creates patient in Precision, creates prescription, sends fill request

- [ ] Artifact 44: `send_otc_treatment_fill_request` (`backend/ecomm/tasks.py`)
  - Args: `order_id: int, prescription_fill_id: int`
  - Enqueue: `.delay(order.id, prescription_fill.id)` at `care/tasks.py:125`
  - Retry: none
  - Purpose: Sends OTC-only fill request to Precision pharmacy (no jurisdiction/refill restrictions apply)

- [ ] Artifact 45: `attach_unattached_orders_to_user` (`backend/ecomm/tasks.py`)
  - Args: `user_id: int`
  - Enqueue: `.delay(user.id)` at `api/v1/views/register.py:144`; also at `api/v1/views/account_order_transfer_verification.py:128` (indirect)
  - Retry: none
  - Purpose: Attaches orders with matching email to a user account after registration or order transfer verification

- [ ] Artifact 46: `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult` (`backend/ecomm/tasks.py`)
  - Args: `user_id: int, order_number: str`
  - Enqueue: `.delay(user_id, order_number)` at `ecomm/services/cart.py:701`; `api/v1/views/account_order_transfer_verification.py:128`; `api/v1/views/user_tests.py:357`
  - Retry: none
  - Purpose: Finds or creates an ungated RX consult and attaches treatments from an order to it

- [ ] Artifact 47: `create_consults_for_ungated_rx_orders_with_users_but_no_consult` (`backend/ecomm/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule (healing task)
  - Retry: none
  - Purpose: Periodic healing task — finds ungated RX orders with users but no consult and creates consults for them

- [ ] Artifact 48: `process_gift_card_redemptions` (`backend/ecomm/tasks.py`)
  - Args: `order_id: int`
  - Enqueue: likely via beat or triggered from order processing (not found via grep as `.delay()` call)
  - Retry: raises on exception
  - Purpose: Processes gift card redemptions for a specific order via `GiftCardRedemptionService`

- [ ] Artifact 49: `process_gift_cards` (`backend/ecomm/tasks.py`)
  - Args: `order_id: int, payload: dict = None`
  - Enqueue: `.delay(order.id, payload)` at `ecomm/utils.py:740`
  - Retry: raises on exception
  - Purpose: Processes both gift card purchases and redemptions for an order

- [ ] Artifact 50: `reprocess_subscription_refill_orders_daily` (`backend/ecomm/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule (daily)
  - Retry: raises on exception
  - Purpose: Daily healing task — reprocesses subscription refill orders from the last 24 hours that were incorrectly routed

### ecomm shopify tasks (backend/ecomm/shopify/tasks.py)

- [ ] Artifact 51: `retry_failed_shopify_orders` (`backend/ecomm/shopify/tasks.py`)
  - Args: none; `soft_time_limit=600, time_limit=900`
  - Enqueue: Celery beat schedule
  - Retry: none (soft time limit via decorator)
  - Purpose: Periodic task — fetches Shopify orders from last 3 days that are missing in Evvy DB and processes them

### shipping tasks (backend/shipping/tasks.py)

- [ ] Artifact 52: `update_individual_shipping_status` (`backend/shipping/tasks.py`)
  - Args: `status_id`
  - Enqueue: `.delay(status.id)` at `shipping/tasks.py:155`
  - Retry: none
  - Purpose: Updates a single `ShippingStatus` record by querying USPS/FedEx tracking APIs

- [ ] Artifact 53: `update_eligible_shipping_statuses_async` (`backend/shipping/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic fan-out task — queries shipping statuses for kits/samples and fans out to `update_individual_shipping_status` per record

- [ ] Artifact 54: `send_daily_express_orders_email` (`backend/shipping/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Sends daily email + Google Sheet update listing all express-shipping orders from the last 24 hours

- [ ] Artifact 55: `process_tracking_statuses` (`backend/shipping/tasks.py`)
  - Args: `test_hash: str, order_number: str, kit_tracking_number: str, sample_tracking_number: str, mode=MODE_ALL, from_csv=False`
  - Enqueue: `.delay(test_hash, order_number, kit_tracking_number, sample_tracking_number, ...)` at `api/v1/views/webhooks.py:253`
  - Retry: none
  - Purpose: Processes kit and sample tracking numbers from Berlin fulfillment partner — links order to test, creates shipping status records, marks Shopify order as fulfilled

- [ ] Artifact 56: `send_order_to_berlin_for_fulfillment` (`backend/shipping/tasks.py`)
  - Args: `shopify_payload: Dict[str, Any], is_order_cancellation: bool, order_id: int`
  - Enqueue: `.delay(payload, is_order_cancellation, order.id)` at `ecomm/utils.py:763`; `.delay(order.payload, is_order_cancellation, order.id)` at `shipping/tasks.py:768`
  - Retry: none (but `retry_failed_berlin_order_fulfillments` is a healing task)
  - Purpose: Sends or cancels a fulfillment order with Berlin (test kit fulfillment provider)

- [ ] Artifact 57: `retry_failed_berlin_order_fulfillments` (`backend/shipping/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic healing task — retries orders that were never sent to Berlin (missing `sent_to_berlin_at`)

- [ ] Artifact 58: `alert_if_no_orders_sent_to_berlin` (`backend/shipping/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Sends admin alert if no orders have been fulfilled by Berlin in the last 6 hours

- [ ] Artifact 59: `alert_if_no_orders_created` (`backend/shipping/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Sends admin alert if no new orders have been created in the last 6 hours

### shipping precision tasks (backend/shipping/precision/tasks.py)

- [ ] Artifact 60: `process_precision_pharmacy_webhook` (`backend/shipping/precision/tasks.py`)
  - Args: `payload`
  - Enqueue: `.delay(payload)` at `api/v1/views/webhooks.py:311`
  - Retry: none
  - Purpose: Processes inbound webhook from Precision pharmacy — handles received/shipped/delivered/warning status updates

- [ ] Artifact 61: `send_prescription_to_precision` (`backend/shipping/precision/tasks.py`)
  - Args: `consult_uid, skip_set_sent_to_pharmacy=False`
  - Enqueue: `.delay(consult.uid)` at `shipping/precision/tasks.py:299`; called directly (not `.delay()`) from `consults/wheel/tasks.py:526`
  - Retry: none
  - Purpose: Creates patient + prescription in Precision pharmacy and submits fill from a consult; fires Braze `CONSULT_ELIGIBLE_FOR_REFILLS` event if consult has eligible refills

- [ ] Artifact 62: `send_create_patient_request_to_precision` (`backend/shipping/precision/tasks.py`)
  - Args: `prescription_fill_id: int, consult_uid: str = None, user_id: int = None, order_id: int = None`
  - Enqueue: called synchronously (not via `.delay()`) from `ecomm/tasks.py` lines 232-237 and 288-290
  - Retry: none
  - Purpose: Creates or looks up a patient record in Precision pharmacy, saves `pharmacy_patient_id` on the prescription fill

- [ ] Artifact 63: `send_create_prescription_request_to_precision` (`backend/shipping/precision/tasks.py`)
  - Args: `prescription_uid, fill_quantity=None, prescription_fill_prescription=None`
  - Enqueue: called synchronously from `ecomm/tasks.py:247-249`
  - Retry: none (raises on exception, sets fill to WARNING status)
  - Purpose: Creates a prescription in Precision pharmacy for a specific prescription fill

- [ ] Artifact 64: `send_create_otc_treatment_request_to_precision` (`backend/shipping/precision/tasks.py`)
  - Args: `otc_treatment_uid: str, prescription_fill_otc_treatment_id: int`
  - Enqueue: called synchronously from `ecomm/tasks.py:258-263` and `ecomm/tasks.py:297-302`
  - Retry: none (raises on exception, sets fill to WARNING status)
  - Purpose: Creates an OTC treatment record in Precision pharmacy

- [ ] Artifact 65: `send_fill_request_to_precision` (`backend/shipping/precision/tasks.py`)
  - Args: `fill_uid, order_shipping_address=None`
  - Enqueue: called synchronously from `ecomm/tasks.py:266` and `ecomm/tasks.py:304`
  - Retry: none (raises on exception, sets fill to WARNING status)
  - Purpose: Submits the actual fill/dispensing request to Precision pharmacy

- [ ] Artifact 66: `send_cancel_fill_request_to_precision` (`backend/shipping/precision/tasks.py`)
  - Args: `fill_uid`
  - Enqueue: called synchronously from `ecomm/tasks.py:179`
  - Retry: none (raises on already-shipped/delivered fills)
  - Purpose: Cancels a prescription fill at Precision pharmacy

- [ ] Artifact 67: `send_missing_prescriptions_to_precision` (`backend/shipping/precision/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic healing task — finds consults completed in last 2 days but never sent to pharmacy, submits them if recommended prescriptions match

- [ ] Artifact 68: `retry_failed_prescription_fills` (`backend/shipping/precision/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none (task itself manages retry logic — up to 10 fills/run, marks failed after 3 days)
  - Purpose: Periodic healing task — retries prescription fills in WARNING status; marks as FAILED after 3 days of failures

- [ ] Artifact 69: `send_notification_for_stuck_prescriptions` (`backend/shipping/precision/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Sends admin email for prescription fills still in CREATED status after 3 business days

### subscriptions tasks (backend/subscriptions/tasks.py)

- [ ] Artifact 70: `cancel_expired_prescription_subscriptions` (`backend/subscriptions/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule (daily)
  - Retry: raises on exception
  - Purpose: Daily task — cancels Recharge subscriptions for prescriptions that have run out of refills

### providers tasks (backend/providers/tasks.py)

- [ ] Artifact 71: `send_provider_ordered_single_test_notifications` (`backend/providers/tasks.py`)
  - Args: `provider_email, patient_email, provider_test_order_id, payer, add_expanded_pcr=False`
  - Enqueue: `.delay(provider_email, patient_email, provider_test_order_id, payer, add_expanded_pcr)` at `api/v1/views/provider_test_orders.py:104`
  - Retry: none
  - Purpose: Sends FYI admin email when a provider orders a single test for a patient

- [ ] Artifact 72: `send_provider_bulk_ordered_tests_notification` (`backend/providers/tasks.py`)
  - Args: `provider_email, num_ordered, provider_test_order_ids`
  - Enqueue: `.delay(provider_email, num_ordered, provider_test_order_ids)` at `api/v1/views/provider_test_orders.py:245`
  - Retry: none
  - Purpose: Sends FYI admin email when a provider initiates a bulk order (pending payment)

- [ ] Artifact 73: `send_provider_bulk_order_paid_notification` (`backend/providers/tasks.py`)
  - Args: `ecomm_order_id, provider_email, quantity`
  - Enqueue: `.delay(ecomm_order_id, provider_email, quantity)` at `ecomm/utils.py:2705`
  - Retry: none
  - Purpose: Sends FYI admin email when a provider bulk order is paid

- [ ] Artifact 74: `send_provider_test_results_ready` (`backend/providers/tasks.py`)
  - Args: `provider_email`
  - Enqueue: `.delay(provider.email)` at `test_results/infection_state_service.py:500`; `.delay(provider.email)` at `test_results/utils.py:3245`
  - Retry: none
  - Purpose: Sends "Provider Results Ready" templated email to the provider when patient results are released

### test_results tasks (backend/test_results/tasks.py)

- [ ] Artifact 75: `create_test_result_tagset` (`backend/test_results/tasks.py`)
  - Args: `test_hash: str`
  - Enqueue: called directly (not `.delay()`) from `test_results/tasks.py:130`; `.delay(test.hash)` at `scripts/test_result_tag_scripts.py:63`
  - Retry: none
  - Purpose: Creates or updates a `TestResultTagSet` with pregnancy, menopause, symptoms, pathogen, and health context tags

- [ ] Artifact 76: `post_process_test_results` (`backend/test_results/tasks.py`)
  - Args: `test_hash, release_results=True`
  - Enqueue: `.delay(test_hash, release_results)` at `test_results/microgen/tasks.py:140`; `.delay(test.hash)` at `test_results/utils_processing.py:210`
  - Retry: none
  - Purpose: Full post-processing pipeline for test results — updates Valencia type, creates scores, fertility module, assigns plan profile, computes care eligibility, auto-releases results if eligible

- [ ] Artifact 77: `assign_suspected_yeast_flag_to_test_result` (`backend/test_results/tasks.py`)
  - Args: `test_hash: str`
  - Enqueue: called directly from `test_results/tasks.py:134` (inside `post_process_test_results`)
  - Retry: none
  - Purpose: Sets `suspected_yeast=True` on test result if yeast is present or recently diagnosed

- [ ] Artifact 78: `send_results_ready_emails` (`backend/test_results/tasks.py`)
  - Args: `test_hash: str`
  - Enqueue: called from `test_results/utils.py` (via `release_test_results`)
  - Retry: raises if email fails
  - Purpose: Sends results ready email to user; also triggers care eligibility emails if eligible

- [ ] Artifact 79: `send_test_status_duration_alert` (`backend/test_results/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Sends admin email alerting on tests stuck in RECEIVED/SEQUENCING/PROCESSING status beyond defined thresholds

- [ ] Artifact 80: `send_lab_test_status_duration_alert` (`backend/test_results/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Sends admin email alerting on PCR lab tests stuck in `AT_LAB` status beyond 3 days

- [ ] Artifact 81: `send_vip_test_status_update` (`backend/test_results/tasks.py`)
  - Args: `test_hash, previous_status, new_status`
  - Enqueue: `.delay(test_instance.hash, previous_status, test_instance.status)` at `test_results/signals.py:246`; `.delay(urine_test.hash, old_status, new_status)` at `test_results/lab_services/orchestrator.py:556`
  - Retry: none
  - Purpose: Sends VIP-test admin email notification when a provider-ordered test changes status

### test_results microgen tasks (backend/test_results/microgen/tasks.py)

- [ ] Artifact 82: `submit_lab_order_approval_to_microgen` (`backend/test_results/microgen/tasks.py`)
  - Args: `lab_order_uid`
  - Enqueue: `.delay(lab_order.uid)` at `test_results/microgen/tasks.py:92`; called directly from `consults/wheel/tasks.py:323`; `.delay(lab_order.uid)` at `consults/utils.py:413`
  - Retry: none
  - Purpose: Submits approved lab order data to the Microgen sequencing lab API

- [ ] Artifact 83: `submit_research_sample_lab_order_to_microgen` (`backend/test_results/microgen/tasks.py`)
  - Args: `test_hash`
  - Enqueue: `.delay(cohort_test.test.hash)` at `studies/admin.py:66`; `.delay(test.hash)` at `app/management/commands/create_study_cohort_tests.py:147`
  - Retry: none
  - Purpose: Submits electronic lab order for research/study samples to Microgen

- [ ] Artifact 84: `submit_missing_lab_order_approvals_to_microgen` (`backend/test_results/microgen/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic healing task — finds approved lab orders not yet submitted to Microgen in last 60 days, submits them

- [ ] Artifact 85: `process_test_results_stuck_in_sequencing_status` (`backend/test_results/microgen/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic healing task — finds tests stuck in sequencing status for over 7 days, triggers result processing from S3

- [ ] Artifact 86: `process_microgen_test_results` (`backend/test_results/microgen/tasks.py`)
  - Args: `test_hash, report_errors=True, read_from_staging=False, release_results=True, bypass_ready_check=False, force_update_result_value=False`
  - Enqueue: `.delay(test_hash)` at `test_results/microgen/tasks.py:453`; `.apply_async(args=[test_hash], countdown=delay_seconds)` at `test_results/microgen/tasks.py:450` (load-balanced with random delay)
  - Retry: none
  - Purpose: Main NGS result processing task — reads NGS results from S3, parses bacteria counts, then chains `post_process_test_results`

- [ ] Artifact 87: `process_microgen_test_results_if_exists_in_s3` (`backend/test_results/microgen/tasks.py`)
  - Args: `test_hash`
  - Enqueue: `.delay(test.hash)` at `test_results/microgen/tasks.py:114`
  - Retry: none (silently catches S3 NoSuchKey errors)
  - Purpose: Wrapper around `process_microgen_test_results` that silently skips if results file not yet in S3

- [ ] Artifact 88: `process_microgen_vag_pcr_test_results` (`backend/test_results/microgen/tasks.py`)
  - Args: `test_hash`
  - Enqueue: `.delay(test_hash)` at `test_results/microgen/tasks.py:409`
  - Retry: none
  - Purpose: Processes vaginitis PCR panel results from S3; re-scores tests if already ready; fires PCR results ready email and analytics

- [ ] Artifact 89: `send_summary_tests_entered_sequencing` (`backend/test_results/microgen/tasks.py`)
  - Args: none
  - Enqueue: `.apply_async(countdown=cache_timeout)` via `_queue_summary_notification("sequencing")` — delayed 60 minutes with Redis deduplication lock
  - Retry: none
  - Purpose: Summary admin email of tests that entered sequencing in the last 2 hours (batched/deduplicated via Redis)

- [ ] Artifact 90: `send_summary_vpcr_results_processed` (`backend/test_results/microgen/tasks.py`)
  - Args: none
  - Enqueue: `.apply_async(countdown=cache_timeout)` via `_queue_summary_notification("partial-results")` — delayed 20 minutes
  - Retry: none
  - Purpose: Summary admin email of PCR results processed in last 2 hours

- [ ] Artifact 91: `send_summary_vngs_results_processed` (`backend/test_results/microgen/tasks.py`)
  - Args: none
  - Enqueue: `.apply_async(countdown=cache_timeout)` via `_queue_summary_notification("ready")` — delayed 20 minutes
  - Retry: none
  - Purpose: Summary admin email of NGS results processed in last 2 hours

- [ ] Artifact 92: `process_lab_status_update_batch` (`backend/test_results/microgen/tasks.py`)
  - Args: `payload` (dict with `status_updates` list)
  - Enqueue: `.delay(payload)` at `api/v1/views/webhooks.py:296`
  - Retry: none
  - Purpose: Processes a batch of lab status updates from Microgen webhook; delegates to `process_lab_status_update` per item

### test_results junction tasks (backend/test_results/lab_services/providers/junction/tasks.py)

- [ ] Artifact 93: `create_unregistered_testkit_order_for_urine_test` (`backend/test_results/lab_services/providers/junction/tasks.py`)
  - Args: `urine_test_ids: list[int], ecomm_order_id: int`
  - Enqueue: `.delay(urine_test_ids, ecomm_order_id)` at `ecomm/utils.py:1236`
  - Retry: none
  - Purpose: Creates unregistered testkit orders with Junction lab for UTI tests at time of order, stores `external_order_id` on `LabOrder`

- [ ] Artifact 94: `submit_lab_order_approval_to_junction` (`backend/test_results/lab_services/providers/junction/tasks.py`)
  - Args: `lab_order_uid: str`
  - Enqueue: `.delay(lab_order.uid)` at `consults/wheel/tasks.py:320`; `.delay(lab_order.uid)` at `scripts/backfill_unapproved_junction_submissions.py:113`
  - Retry: `bind=True, max_retries=3, default_retry_delay=60`; exponential backoff on HTTP 5xx/Timeout (60s → 120s → 240s); non-retryable 4xx raises `LabOrderCreationError`; final failure fires `handle_junction_submission_failure` signal handler for Slack alert
  - Purpose: Registers an existing unregistered testkit with Junction after Wheel approves the lab order (clinician NPI assigned)

- [ ] Artifact 95: `fetch_and_process_junction_results` (`backend/test_results/lab_services/providers/junction/tasks.py`)
  - Args: `external_order_id: str`
  - Enqueue: `.delay(external_order_id)` at `test_results/lab_services/lab_order_service.py:83`
  - Retry: `bind=True, max_retries=3`; exponential backoff (60s → 120s → 240s, capped at 300s); all exceptions are retried
  - Purpose: Fetches UTI test results from Junction API and processes them asynchronously when a results_ready webhook is received

- [ ] Artifact 96: `fulfill_uti_order_in_shopify` (`backend/test_results/lab_services/providers/junction/tasks.py`)
  - Args: `urine_test_id: int, tracking_number: str, courier: str`
  - Enqueue: `.delay(urine_test_id, tracking_number, courier)` at `test_results/lab_services/orchestrator.py:462`
  - Retry: none
  - Purpose: Marks UTI kit order as fulfilled in Shopify with tracking info when Junction notifies of shipment to customer

### transactional_email tasks (backend/transactional_email/tasks.py — large file, 20+ tasks)

- [ ] Artifact 97: `send_test_activated_reminder` (`backend/transactional_email/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic task — sends reminder email to users who activated test but haven't taken sample in 4+ days

- [ ] Artifact 98: `send_ldt_test_sample_received_email` (`backend/transactional_email/tasks.py`)
  - Args: `test_hash`
  - Enqueue: `.delay(test.hash)` at `test_results/microgen/tasks.py:387`
  - Retry: none
  - Purpose: Sends "Sample Received at Lab" email to user for LDT tests (standard or comprehensive template)

- [ ] Artifact 99: `send_ldt_test_sample_sequencing_email` (`backend/transactional_email/tasks.py`)
  - Args: `test_hash`
  - Enqueue: `.delay(test.hash)` at `test_results/microgen/tasks.py:399`
  - Retry: none
  - Purpose: Sends "Sample Sequencing" update email to user; sends notification to MDX lab email

- [ ] Artifact 100: `send_pcr_test_results_ready` (`backend/transactional_email/tasks.py`)
  - Args: `test_hash`
  - Enqueue: `.delay(test_hash)` at `test_results/microgen/tasks.py:170`
  - Retry: none
  - Purpose: Sends "PCR Results Ready" email to user when preliminary PCR results are available

- [ ] Artifact 101: `send_treatments_shipped` (`backend/transactional_email/tasks.py`)
  - Args: `prescription_fill_id`
  - Enqueue: called from `shipping/precision/utils.py` webhook processing
  - Retry: raises on error
  - Purpose: Sends "Treatments Shipped" email with tracking link when prescription is shipped from Precision

- [ ] Artifact 102: `send_treatments_delivered` (`backend/transactional_email/tasks.py`)
  - Args: `prescription_fill_id`
  - Enqueue: called from `shipping/precision/utils.py` webhook processing
  - Retry: raises on error
  - Purpose: Sends "Treatments Delivered" email (chooses template based on refill vs initial vs bundle)

- [ ] Artifact 103: `send_consult_intake_reviewed_email` (`backend/transactional_email/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(consult_uid)` at `consults/wheel/tasks.py:163`
  - Retry: none
  - Purpose: Sends "Consult Intake Reviewed" email with message thread link after Wheel clinician reviews intake

- [ ] Artifact 104: `send_treatment_plan_ready_email` (`backend/transactional_email/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(consult.uid)` at `consults/signals.py:160`
  - Retry: none
  - Purpose: Sends "Treatment Plan Ready" email with treatment plan link

- [ ] Artifact 105: `send_eligible_for_care_1_for_test` (`backend/transactional_email/tasks.py`)
  - Args: `test_id`
  - Enqueue: `.delay(test.id)` at `test_results/tasks.py:206`
  - Retry: none
  - Purpose: Sends first care eligibility email immediately after results ready

- [ ] Artifact 106: `send_eligible_for_care_2` (`backend/transactional_email/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic task — sends second care eligibility email 6 days after results ready

- [ ] Artifact 107: `send_eligible_for_care_3` (`backend/transactional_email/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic task — sends third care eligibility email 12 days after results ready

- [ ] Artifact 108: `send_account_transfer_verification_email` (`backend/transactional_email/tasks.py`)
  - Args: `user_id: int, order_email: str, order_number: str`
  - Enqueue: `.delay(user.id, order.email, order_number)` at `ecomm/services/cart.py:705` and `:708`
  - Retry: raises on duplicate/invalid conditions
  - Purpose: Sends email with verification link to transfer an order from one email to another Evvy account

### consults wheel tasks (backend/consults/wheel/tasks.py — large file, 20+ tasks)

- [ ] Artifact 109: `submit_async_consult` (`backend/consults/wheel/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(consult.uid)` at `api/v1/views/consult.py:926`; `.delay(consult.uid)` at `consults/wheel/tasks.py:394` and `:407` (retry tasks)
  - Retry: none (but `retry_creating_async_consults` and `retry_errored_consult_creation` are healing tasks)
  - Purpose: Preps consult for Wheel — sets recommended prescriptions, checks if manual review is required, submits to Wheel or creates review record

- [ ] Artifact 110: `submit_consult_intake_to_wheel` (`backend/consults/wheel/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: called directly (not `.delay()`) from `submit_async_consult` at `consults/wheel/tasks.py:97`
  - Retry: none (raises; monitored by NewRelic)
  - Purpose: Submits the finalized consult intake to Wheel API for clinician review

- [ ] Artifact 111: `fetch_and_process_completed_consult_details` (`backend/consults/wheel/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(consult.uid)` at `consults/wheel/utils_webhook.py:157`; `.delay(consult.uid)` at `consults/wheel/tasks.py:366`; `.delay(obj.uid)` at `consults/admin.py:1103`
  - Retry: none
  - Purpose: Fetches finalized consult details from Wheel (clinician, diagnosis, prescription info), stores them, sets consult to COMPLETE

- [ ] Artifact 112: `fetch_and_process_completed_lab_order_details` (`backend/consults/wheel/tasks.py`)
  - Args: `lab_order_uid`
  - Enqueue: `.delay(lab_order_uid)` at `consults/wheel/utils_webhook.py:101`
  - Retry: none
  - Purpose: Fetches approved lab order details from Wheel, routes to Junction (UTI) or Microgen (vaginal test)

- [ ] Artifact 113: `retry_consult_detail_processing` (`backend/consults/wheel/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic healing task — retries fetching consult details from Wheel for consults stuck in IN_PROGRESS/SUBMITTED/ERROR status for 24+ hours

- [ ] Artifact 114: `retry_creating_async_consults` (`backend/consults/wheel/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic healing task — resubmits consults stuck in SUBMITTED status (submitted_at is null) for 1-5 days

- [ ] Artifact 115: `retry_errored_consult_creation` (`backend/consults/wheel/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic healing task — resubmits consults stuck in STATUS_ERROR

- [ ] Artifact 116: `fetch_and_process_referred_consult_details` (`backend/consults/wheel/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(consult.uid)` at `consults/wheel/utils_webhook.py:153`; `.delay(consult.uid)` at `consults/wheel/tasks.py:369`
  - Retry: none
  - Purpose: Fetches referral details for auto-referred-out consults; sets consult to REFERRED and sends referred-out email

- [ ] Artifact 117: `check_recommended_prescriptions_against_prescribed_and_send_prescriptions` (`backend/consults/wheel/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(consult_uid)` at `consults/wheel/tasks.py:267`
  - Retry: none
  - Purpose: Validates that Wheel's prescribed medications match recommended prescriptions; if match, sets consult COMPLETE and sends to Precision pharmacy

- [ ] Artifact 118: `check_recommended_prescriptions_against_prescribed` (`backend/consults/wheel/tasks.py`)
  - Args: `consult_uid, notify_admins=False`
  - Enqueue: called directly (not `.delay()`) from `check_recommended_prescriptions_against_prescribed_and_send_prescriptions` and from `shipping/precision/tasks.py:297`
  - Retry: none
  - Purpose: Compares recommended vs actual prescribed slugs; creates manual review if mismatch

- [ ] Artifact 119: `fetch_and_process_follow_up_consult_details` (`backend/consults/wheel/tasks.py`)
  - Args: `lab_order_uid: str, follow_up_external_id: str`
  - Enqueue: `.delay(lab_order.uid, follow_up.external_id)` at `consults/wheel/tasks.py:931`; `.delay(lab_order_uid, wheel_consult_id)` at `consults/wheel/utils_webhook.py:94`
  - Retry: none
  - Purpose: Fetches Wheel's interpretation of follow-up lab results (VNGS/UTI PCR); confirms or flags diagnosis; creates amendment tasks on disagreement

- [ ] Artifact 120: `submit_lab_order_to_wheel` (`backend/consults/wheel/tasks.py`)
  - Args: `lab_order_uid`
  - Enqueue: `.delay(lab_order.uid)` at `consults/wheel/tasks.py:637` and `:678`; `.apply_async((lab_order.uid,), countdown=300)` at `consults/utils.py:404` and `:406` (5-minute delay)
  - Retry: none
  - Purpose: Submits a lab order to Wheel for clinician requisition

- [ ] Artifact 121: `resubmit_stuck_lab_orders_to_wheel` (`backend/consults/wheel/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic healing task — resubmits lab orders stuck in CREATED/SUBMITTED status for 1+ hours (skips Canadian and manual-review states)

- [ ] Artifact 122: `resubmit_errored_lab_orders_to_wheel` (`backend/consults/wheel/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Periodic healing task — resubmits lab orders in STATUS_ERROR (skips Canadian and those with results already sent)

- [ ] Artifact 123: `resubmit_consult_photo_id_info_to_wheel` (`backend/consults/wheel/tasks.py`)
  - Args: `consult_uid`
  - Enqueue: `.delay(consult.uid)` at `api/v1/views/consult.py:912`
  - Retry: none
  - Purpose: Re-submits updated photo ID info to Wheel after ID verification failure and re-upload

- [ ] Artifact 124: `mark_wheel_consult_message_as_read` (`backend/consults/wheel/tasks.py`)
  - Args: `consult_uid, message_id`
  - Enqueue: `.delay(consult.uid, message_id)` at `consults/utils.py:495`
  - Retry: none
  - Purpose: Marks a Wheel consult message as read via the Wheel API

- [ ] Artifact 125: `send_notification_for_stuck_consults` (`backend/consults/wheel/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Sends admin alert for non-UTI consults in clinical review for 24+ hours and open manual reviews

- [ ] Artifact 126: `send_notification_for_stuck_uti_consults` (`backend/consults/wheel/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Sends UTI-specific admin alerts for UTI consults in review 24+ hours and open UTI manual reviews

- [ ] Artifact 127: `send_notification_for_diagnosis_pending_consults` (`backend/consults/wheel/tasks.py`)
  - Args: `hours_threshold=24`
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Sends admin alert for tests with diagnosis pending (follow-up not interpreted) for more than `hours_threshold` hours; separately tracks VHT and UTI counts

- [ ] Artifact 128: `send_notification_for_care_orders_in_bad_states` (`backend/consults/wheel/tasks.py`)
  - Args: none
  - Enqueue: Celery beat schedule
  - Retry: none
  - Purpose: Sends admin alerts for care orders without consults, completed consults without prescription fills, and ungated RX orders without consults

- [ ] Artifact 129: `issue_lab_results_to_wheel_for_lab_test` (`backend/consults/wheel/tasks.py`)
  - Args: `lab_test_id: str`
  - Enqueue: `.delay(str(lab_test.id))` at `test_results/signals.py:443`; `.delay(str(lab_test.id))` at `test_results/lab_services/providers/junction/results_processor.py:119`; `.delay(str(lab_test.id))` at `scripts/resend_lab_results_to_wheel.py:88`; `.delay(str(lab_test.id))` at `test_results/admin.py:1017`
  - Retry: none
  - Purpose: Issues lab results (VNGS/VPCR/Urine) to Wheel for clinician follow-up interpretation

---

## Enqueue Sites (Selected Representative .delay() and .apply_async() Calls)

### Webhook handlers

- `process_tracking_statuses.delay(...)` at `backend/api/v1/views/webhooks.py:253` — Berlin shipping webhook
- `process_lab_status_update_batch.delay(payload)` at `backend/api/v1/views/webhooks.py:296` — Microgen lab status webhook
- `process_precision_pharmacy_webhook.delay(payload)` at `backend/api/v1/views/webhooks.py:311` — Precision pharmacy webhook

### Order processing (ecomm/utils.py)

- `send_order_to_berlin_for_fulfillment.delay(payload, is_order_cancellation, order.id)` at `ecomm/utils.py:763`
- `void_share_a_sale_transaction.delay(order_number, order_date, note)` at `ecomm/utils.py:416`
- `send_ungated_rx_order_paid_event.delay(order.order_number)` at `ecomm/utils.py:691`
- `process_gift_cards.delay(order.id, payload)` at `ecomm/utils.py:740`
- `send_any_paid_event.delay(order.order_number)` at `ecomm/utils.py:744`
- `send_mpt_voucher_paid_event.delay(user.id)` at `ecomm/utils.py:1138`
- `send_prescription_refill_request.delay(order.id, prescription_fill.id)` at `ecomm/utils.py:2198`
- `create_unregistered_testkit_order_for_urine_test.delay(urine_test_ids, ecomm_order_id)` at `ecomm/utils.py:1236`
- `send_consult_paid_event.delay(consult.uid, order.provider_id)` at `ecomm/utils.py:1874`

### User registration / account

- `attach_unattached_orders_to_user.delay(user.id)` at `api/v1/views/register.py:144`
- `send_provider_registered_event.delay(user.id)` at `api/v1/views/register.py:238`
- `send_intake_completed_notifications.delay(user.email)` at `api/v1/views/account.py:253`

### Test results pipeline

- `post_process_test_results.delay(test_hash, release_results)` at `test_results/microgen/tasks.py:140`
- `process_microgen_test_results.delay(test_hash)` at `test_results/microgen/tasks.py:453`
- `process_microgen_test_results.apply_async(args=[test_hash], countdown=delay_seconds)` at `test_results/microgen/tasks.py:450` — load-balanced with random delay up to `RESULTS_PROCESSING_MAX_DELAY_MINUTES`
- `submit_lab_order_approval_to_junction.delay(lab_order.uid)` at `consults/wheel/tasks.py:320`
- `submit_lab_order_approval_to_microgen.delay(lab_order.uid)` at `test_results/microgen/tasks.py:92`
- `fetch_and_process_completed_consult_details.delay(consult.uid)` at `consults/wheel/utils_webhook.py:157`
- `fetch_and_process_junction_results.delay(external_order_id)` at `test_results/lab_services/lab_order_service.py:83`
- `issue_lab_results_to_wheel_for_lab_test.delay(str(lab_test.id))` at `test_results/signals.py:443`
- `send_results_ready_analytics_events.delay(test_hash, eligible_for_care, ineligible_reason)` at `test_results/utils.py:3252`

### Scheduling with apply_async (non-beat)

- `submit_lab_order_to_wheel.apply_async((lab_order.uid,), countdown=300)` at `consults/utils.py:404` and `:406` — 5-minute delay before submitting lab order to Wheel
- `create_or_reset_calendar_treatments.apply_async((treatment_plan_id,), countdown=X)` at `care/signals.py:121` and `:129`
- `summary_task.apply_async(countdown=cache_timeout)` at `test_results/microgen/tasks.py:317` — delayed summary emails with Redis dedup lock

---

## Tasks With Retry Configuration

| Task | Retry Mechanism | Details |
|------|----------------|---------|
| `void_share_a_sale_transaction` | `@retry` decorator (retrying library) | `stop_max_attempt_number=3, wait_exponential_multiplier=500` |
| `submit_lab_order_approval_to_junction` | Celery `bind=True, max_retries=3, default_retry_delay=60` | Exponential backoff: 60s→120s→240s; only on HTTP 5xx/Timeout; 4xx raises immediately; final failure fires signal handler |
| `fetch_and_process_junction_results` | Celery `bind=True, max_retries=3` | Exponential backoff: 60s→120s→240s, capped at 300s; all exceptions retried |
| `retry_failed_shopify_orders` | Soft time limit decorator | `soft_time_limit=600, time_limit=900` (not a retry, but a time-based guard) |

---

## Notes for Evaluators

1. **Total task count**: ~95 `@shared_task`-decorated functions across 14 task files (excluding worktrees and venv).
2. **Periodic (beat) tasks vs event-driven tasks**: The majority of "healing" and "notification summary" tasks are Celery beat scheduled; event-driven tasks are enqueued via `.delay()` from views, signals, or other tasks.
3. **Retry configurations are rare**: Only 2 tasks use native Celery retry (`submit_lab_order_approval_to_junction`, `fetch_and_process_junction_results`); 1 uses the `retrying` library (`void_share_a_sale_transaction`). Most tasks raise exceptions on failure without retrying.
4. **Fan-out pattern**: Several periodic tasks query for records and fan out to per-record tasks via `.delay()` (e.g., `update_eligible_shipping_statuses_async`, `send_treatment_ended_events_for_treatment_plans`).
5. **apply_async with countdown**: Used in 3 patterns — load balancing test result processing (random delay), scheduling lab order submission (5-min delay), and batching lab summary notifications (20-60 min delay with Redis lock).
