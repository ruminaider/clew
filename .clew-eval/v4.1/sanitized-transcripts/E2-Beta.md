# E2 — Agent Beta

I now have a complete picture of all Celery tasks in the codebase. Here is the comprehensive inventory:

---

## Complete Celery Task Inventory

### `analytics/tasks.py`

**1. `send_custom_analytics_event_to_fullstory_async`**
- **Args:** `user_id`, `event_name`, `event_properties`, `use_recent_session`
- **Enqueued via:** `.delay()` — called from `send_custom_analytics_event_to_destinations()`
- **Retry config:** None
- **Purpose:** Generic async wrapper for sending a custom event to Fullstory

**2. `send_custom_analytics_event_to_klaviyo_async`**
- **Args:** `payload` (dict)
- **Enqueued via:** `.delay()` — called from `send_custom_analytics_event_to_destinations()`
- **Retry config:** None
- **Purpose:** Generic async wrapper for sending a custom event to Klaviyo

**3. `send_sample_sequencing_provider_klaviyo_event`**
- **Args:** `test_hash: str`, `provider_test_order_id: int`
- **Enqueued via:** `.delay()` — called from `test_results/microgen/tasks.py`
- **Retry config:** None
- **Purpose:** Notifies a provider via Klaviyo that their patient's sample is being sequenced

**4. `send_pcr_test_results_ready_provider_klaviyo_event`**
- **Args:** `test_hash: str`, `provider_test_order_id: int`
- **Enqueued via:** `.delay()` — called from `test_results/microgen/tasks.py`
- **Retry config:** None
- **Purpose:** Notifies a provider via Klaviyo that preliminary PCR results are ready

**5. `send_results_ready_analytics_events`**
- **Args:** `test_hash: str`, `eligible_for_care: bool`, `ineligible_reason: str | None`
- **Enqueued via:** `.delay()` — called from test result release flow (not in a tasks.py)
- **Retry config:** None
- **Purpose:** Fires "Results Ready" events to Fullstory, Klaviyo, and Braze; creates `CareEligible` DB records with bundle and a-la-care eligibility details

**6. `send_urine_test_results_ready_analytics_events`**
- **Args:** `urine_test_hash: str`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Creates `CareEligible` record with UTI care eligibility info for a urine test

**7. `send_care_checkout_created_event`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Sends "Care Checkout Created" event to Fullstory when a user begins the care checkout

**8. `send_ungated_rx_order_paid_event`**
- **Args:** `order_number: str`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Ungated Paid" event to Fullstory and `URX_PURCHASE` event to Braze for ungated RX orders

**9. `send_mpt_voucher_paid_event`**
- **Args:** `user_id`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "MPT Voucher Paid" event to Fullstory, Klaviyo, and Braze

**10. `send_consult_paid_event`**
- **Args:** `consult_uid`, `order_number`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Care Paid" event (and UTI-specific variant) to Fullstory, Klaviyo, Braze when care order is paid

**11. `send_any_paid_event`**
- **Args:** `order_number: str`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Any Paid" Fullstory event categorizing the order type (test, care, refill, ungated rx, etc.)

**12. `send_prescription_refills_paid_event`**
- **Args:** `prescription_refill_id`, `order_number`
- **Enqueued via:** `.delay()` — called from `ecomm/tasks.py`
- **Retry config:** None
- **Purpose:** Fires "Prescription Refills Paid" event to Fullstory

**13. `send_additional_tests_checkout_created_event`**
- **Args:** `test_hash`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Additional Tests Checkout Created" event to Fullstory

**14. `send_additional_tests_paid_event`**
- **Args:** `test_hash`, `order_number`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Additional Tests Paid" event to Fullstory

**15. `send_consult_intake_ineligible_event`**
- **Args:** `consult_uid`, `refer_out_reason`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Consult Intake Ineligible" event to Fullstory when user is referred out

**16. `send_rx_order_attached_to_account_klaviyo_event`**
- **Args:** `consult_uid`, `order_number`
- **Enqueued via:** `.delay()` — called from `ecomm/tasks.py`
- **Retry config:** None
- **Purpose:** Sends "RX Attached to Account" event to Klaviyo when an ungated RX order is linked to a consult

**17. `send_consult_intake_submitted_event`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()` — called from `consults/wheel/tasks.py`
- **Retry config:** None
- **Purpose:** Fires "Consult Intake Submitted" event to Fullstory, Klaviyo, and Braze (with UTI variant)

**18. `send_coaching_call_completed_event`**
- **Args:** `test_hash`, `coaching_call_notes_id=None`, `num_calls=None`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Coaching Call Completed" event to Fullstory

**19. `send_treatment_delivered_event`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()` — called from `send_treatment_probably_delivered_events_for_treatment_plans`
- **Retry config:** None
- **Purpose:** Sends "Treatment Delivered" event to Klaviyo with treatment dates and SKUs

**20. `send_estimated_treatment_started_events`** (Celery Beat: daily at 7:15 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Fan-out task — queries treatment plans where today is the estimated start date, dispatches `send_estimated_treatment_started_event` for each

**21. `send_estimated_treatment_started_event`**
- **Args:** `treatment_plan_id: int`
- **Enqueued via:** `.delay()` — called from `send_estimated_treatment_started_events`
- **Retry config:** None
- **Purpose:** Fires "Treatment Started" event to Klaviyo for a specific treatment plan

**22. `send_test_delivered_klaviyo_event`**
- **Args:** `test_hash`
- **Enqueued via:** `.delay()` — called from `shipping/utils.py`
- **Retry config:** None
- **Purpose:** Sends "Test Kit Delivered" event to Klaviyo using the order email

**23. `send_health_history_completed_klaviyo_event`**
- **Args:** `test_hash`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Health History Completed" event to Klaviyo

**24. `send_updated_treatment_start_date_event`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Updated Treatment Start Date" event to Klaviyo when user changes their start date

**25. `send_treatment_ended_event`**
- **Args:** `treatment_plan_id: int`
- **Enqueued via:** `.delay()` — called from `send_treatment_ended_events_for_treatment_plans`
- **Retry config:** None
- **Purpose:** Fires "Treatment Ended" event to Klaviyo and Braze when treatment end date arrives

**26. `send_treatment_ended_events_for_treatment_plans`** (Celery Beat: daily at 2:15 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Queries treatment plans with end date today or yesterday, dispatches `send_treatment_ended_event` for each

**27. `send_treatment_probably_delivered_events_for_treatment_plans`** (Celery Beat: daily at 6:15 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Sends "Treatment Delivered" events for plans that have no `treatment_delivered_at` but were created N days ago (average fulfillment days)

**28. `send_provider_registered_event`**
- **Args:** `provider_id`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Provider Registered" event to Klaviyo

**29. `send_provider_verified_event`**
- **Args:** `provider_id`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "[Provider] Provider Verified" event to Klaviyo

**30. `send_provider_ordered_test_klaviyo_event`**
- **Args:** `provider_id`, `provider_test_order_ids`, `payer`, `add_expanded_pcr=False`, `patient_email=None`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Sends Klaviyo events to both the provider ("[Provider] Provider Ordered a Test") and patient ("Provider Ordered A Test for User") including a checkout link

**31. `send_provider_reminded_patient_klaviyo_event`**
- **Args:** `provider_id`, `patient_email`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Provider Reminded User to Purchase Test" Klaviyo event to patient with checkout link

**32. `send_viewed_plan_klaviyo_event`**
- **Args:** `test_id`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Viewed Plan" Klaviyo event when a user views their test plan

**33. `send_consult_intake_started_klaviyo_event`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fires "Consult Intake Started" Klaviyo event

**34. `send_three_weeks_after_treatment_delivered_klaviyo`** (Celery Beat: daily at 7:15 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Finds consults eligible for refill (3+ weeks post-delivery), sends "Consult Eligible for Refill" Klaviyo event for each

---

### `ecomm/tasks.py`

**35. `send_patient_ordered_provider_test_notification`**
- **Args:** `patient_email`, `order_sku`, `order_provider_id`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Sends an internal admin email (FYI) when a patient pays for a provider-ordered test

**36. `void_share_a_sale_transaction`**
- **Args:** `order_number`, `order_date`, `reason`
- **Enqueued via:** `.delay()`
- **Retry config:** `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` — 3 attempts with exponential backoff starting at 500ms
- **Purpose:** Voids a Share-A-Sale affiliate commission transaction via their API (used for order refunds/cancellations)

**37. `send_prescription_refill_request`**
- **Args:** `order_id`, `prescription_fill_id`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Full orchestration of a prescription refill: validates state restrictions, checks refill availability, creates patient/prescription/OTC records in Precision pharmacy, sends fill request

**38. `send_otc_treatment_fill_request`**
- **Args:** `order_id: int`, `prescription_fill_id: int`
- **Enqueued via:** `.delay()` — called from `care/tasks.py`
- **Retry config:** None
- **Purpose:** Sends OTC-only fill requests to Precision pharmacy (no state restrictions or consult requirements)

**39. `attach_unattached_orders_to_user`**
- **Args:** `user_id: int`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Finds orders matching the user's email and attaches them to the user account; handles OTC treatment and ungated RX consult creation

**40. `add_order_treatments_to_latest_existing_consult_if_exists_or_create_consult`**
- **Args:** `user_id: int`, `order_number: str`
- **Enqueued via:** Called directly (not `.delay()`) from `attach_unattached_orders_to_user` and Celery Beat
- **Retry config:** None
- **Purpose:** Attaches ungated RX order treatments to an existing in-progress consult, or creates a new ungated RX consult if none exists

**41. `create_consults_for_ungated_rx_orders_with_users_but_no_consult`** (Celery Beat: daily at 7:15 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Healing task — finds ungated RX orders that have a user but no consult, creates the missing consults

**42. `process_gift_card_redemptions`**
- **Args:** `order_id: int`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Processes gift card redemptions for a specific order using `GiftCardRedemptionService`

**43. `process_gift_cards`**
- **Args:** `order_id: int`, `payload: dict = None`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Processes both gift card purchases and redemptions for an order; if no Shopify payload provided, only processes redemptions

**44. `reprocess_subscription_refill_orders_daily`** (Celery Beat: daily at 4:00 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Reprocesses subscription refill orders from the last 24 hours that were incorrectly routed

---

### `subscriptions/tasks.py`

**45. `cancel_expired_prescription_subscriptions`** (Celery Beat: daily at 3:00 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Cancels Recharge subscriptions for prescriptions that have run out of refills

---

### `shipping/tasks.py`

**46. `update_individual_shipping_status`**
- **Args:** `status_id`
- **Enqueued via:** `.delay()` — called from `update_eligible_shipping_statuses_async`
- **Retry config:** None
- **Purpose:** Polls USPS/FedEx API to update the shipping status record for one test kit or sample

**47. `update_eligible_shipping_statuses_async`** (Celery Beat: daily at 8:30 AM, 4:30 PM, 1:30 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Fan-out task — finds all open shipping statuses (kit/sample) with varying polling frequencies, dispatches `update_individual_shipping_status` for each

**48. `send_daily_express_orders_email`** (Celery Beat: daily at 9:30 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Emails ops team a list of all express shipping orders placed in the last 24 hours and adds them to a Google Sheet

**49. `process_tracking_statuses`**
- **Args:** `test_hash: str`, `order_number: str`, `kit_tracking_number: str`, `sample_tracking_number: str`, `mode=MODE_ALL`, `from_csv=False`
- **Enqueued via:** `.delay()` — called from Berlin fulfillment webhook
- **Retry config:** None
- **Purpose:** Associates a test with its Shopify order, creates kit/sample shipping status records, and marks the order fulfilled in Shopify when Berlin sends tracking info

**50. `send_order_to_berlin_for_fulfillment`**
- **Args:** `shopify_payload: Dict[str, Any]`, `is_order_cancellation: bool`, `order_id: int`
- **Enqueued via:** `.delay()` — called from Shopify webhook processing and `retry_failed_berlin_order_fulfillments`
- **Retry config:** None (exceptions propagate for Celery's default behavior)
- **Purpose:** Sends a test kit order (or cancellation) to the Berlin fulfillment partner API

**51. `retry_failed_berlin_order_fulfillments`** (Celery Beat: every 6 hours)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Finds orders not yet sent to Berlin since integration launched (3/27/2024), retries `send_order_to_berlin_for_fulfillment` for each

**52. `alert_if_no_orders_sent_to_berlin`** (Celery Beat: daily at 10 AM, 4 PM, 10 PM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Raises an alert if no orders have been fulfilled by Berlin in the last 6 hours

**53. `alert_if_no_orders_created`** (Celery Beat: daily at 10 AM, 4 PM, 10 PM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Raises an alert if no new orders have been created in the last 6 hours (Shopify connectivity check)

---

### `shipping/precision/tasks.py`

**54. `process_precision_pharmacy_webhook`**
- **Args:** `payload` (dict with `type`, `reference_id`)
- **Enqueued via:** `.delay()` — called from Precision webhook endpoint
- **Retry config:** None
- **Purpose:** Routes Precision pharmacy webhooks: "shipped" → `process_precision_shipped_webhook`, "delivered" → `process_precision_delivered_webhook`

**55. `send_prescription_to_precision`**
- **Args:** `consult_uid`, `skip_set_sent_to_pharmacy=False`
- **Enqueued via:** `.delay()` — called from `consults/wheel/tasks.py`
- **Retry config:** None
- **Purpose:** Creates patient + prescriptions in Precision pharmacy and submits the fill; fires `CONSULT_ELIGIBLE_FOR_REFILLS` Braze event if eligible

**56. `send_create_patient_request_to_precision`**
- **Args:** `prescription_fill_id: int`, `consult_uid: str = None`, `user_id: int = None`, `order_id: int = None`
- **Enqueued via:** Called directly (synchronously) from `ecomm/tasks.py`
- **Retry config:** None
- **Purpose:** Creates (or retrieves) a patient record in Precision pharmacy and stores the `pharmacy_patient_id` on the prescription fill

**57. `send_create_prescription_request_to_precision`**
- **Args:** `prescription_uid`, `fill_quantity=None`, `prescription_fill_prescription=None`
- **Enqueued via:** Called directly from `ecomm/tasks.py`
- **Retry config:** None
- **Purpose:** Creates a prescription record in Precision; sets fill status to WARNING on failure

**58. `send_create_otc_treatment_request_to_precision`**
- **Args:** `otc_treatment_uid: str`, `prescription_fill_otc_treatment_id: int`
- **Enqueued via:** Called directly from `ecomm/tasks.py`
- **Retry config:** None
- **Purpose:** Creates an OTC treatment record in Precision; sets fill status to WARNING on failure

**59. `send_fill_request_to_precision`**
- **Args:** `fill_uid`, `order_shipping_address=None`
- **Enqueued via:** Called directly from `ecomm/tasks.py`
- **Retry config:** None
- **Purpose:** Triggers the actual prescription fill dispatch to Precision pharmacy; sets fill status to WARNING and clears `sent_to_pharmacy_at` on failure

**60. `send_cancel_fill_request_to_precision`**
- **Args:** `fill_uid`
- **Enqueued via:** Called directly from `ecomm/tasks.py`
- **Retry config:** None
- **Purpose:** Cancels an in-progress fill request in Precision pharmacy (rejects if already shipped/delivered)

**61. `send_missing_prescriptions_to_precision`** (Celery Beat: daily at 1:15 AM and 7:15 PM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Healing task — finds completed Precision consults from the last 2 days that were never sent to pharmacy, dispatches `send_prescription_to_precision` for each

**62. `retry_failed_prescription_fills`** (Celery Beat: daily at 2:30 AM, 10:30 AM, 6:30 PM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Retries up to 10 prescription fills in WARNING status; marks fills as FAILED after 3 days of failures

**63. `send_notification_for_stuck_prescriptions`** (Celery Beat: daily at 10:00 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Sends admin email listing refill prescription fills that have been stuck in CREATED status for more than 3 business days

---

### `care/tasks.py`

**64. `update_treatment_end_date`**
- **Args:** `treatment_plan_id: int`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Computes and saves the treatment end date for a treatment plan

**65. `create_or_reset_calendar_treatments`**
- **Args:** `treatment_plan_id: int`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Deletes and rebuilds the treatment calendar (daily regimen entries) for a treatment plan

**66. `heal_prescription_fill_orders`** (Celery Beat: daily at 2 AM, 10 AM, 6 PM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Healing task — creates missing `PrescriptionFillOrder` join records for fills modified in the last 24 hours that have an associated order

**67. `heal_otc_treatment_only_orders`** (Celery Beat: daily at 2:15 AM, 10:15 AM, 6:15 PM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Healing task — finds OTC-only orders whose OTC treatments were never sent to Precision pharmacy, creates prescription fill records, and dispatches `send_otc_treatment_fill_request`

---

### `consults/wheel/tasks.py`

**68. `submit_async_consult`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Prepares a consult for Wheel submission: sets recommended prescriptions, checks if manual review is needed; if not, calls `submit_consult_intake_to_wheel`

**69. `submit_consult_intake_to_wheel`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()` — called from `submit_async_consult` and from retry tasks
- **Retry config:** None
- **Purpose:** Submits the finalized consult intake to the Wheel telehealth API; fires intake submitted event and sends intake reviewed email on success

**70. `issue_lab_results_to_wheel_for_lab_test`**
- **Args:** `lab_test_id: str`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Issues lab results back to Wheel for a completed lab test (VNGS/VPCR/Urine) so the clinician can interpret them

**71. `resubmit_consult_photo_id_info_to_wheel`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Re-submits updated photo ID info to Wheel after an ID verification failure

**72. `fetch_and_process_completed_consult_details`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()` — called from `retry_consult_detail_processing` and Wheel webhooks
- **Retry config:** None
- **Purpose:** Fetches finalized consult data (clinician, diagnosis, prescription details) from Wheel, stores it locally, sets consult to complete, sends to Precision pharmacy

**73. `fetch_and_process_completed_lab_order_details`**
- **Args:** `lab_order_uid`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Fetches approved lab order details from Wheel, stores clinician info, then routes to the appropriate lab (Junction for urine, Microgen for vaginal)

**74. `retry_consult_detail_processing`** (Celery Beat: daily at 6:15 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Healing task — finds consults stuck in IN_PROGRESS/SUBMITTED/ERROR for >24 hours, checks Wheel for completion, dispatches `fetch_and_process_completed_consult_details` or `fetch_and_process_referred_consult_details`

**75. `retry_creating_async_consults`** (Celery Beat: daily at 10:00 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Finds consults stuck in SUBMITTED status with no `submitted_at` (failed to reach Wheel), retries `submit_async_consult`

**76. `retry_errored_consult_creation`** (Celery Beat: daily at 10:00 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Finds consults in ERROR status with no `submitted_at`, retries `submit_async_consult`

**77. `fetch_and_process_follow_up_consult_details`**
- **Args:** `lab_order_uid: str`, `follow_up_external_id: str`
- **Enqueued via:** `.delay()` — called from `send_notification_for_diagnosis_pending_consults`
- **Retry config:** None
- **Purpose:** Fetches follow-up consult details from Wheel after results are sent, stores interpretation and patient instructions, confirms diagnosis if interpretable; creates an amendment task if there's a disagreement

**78. `check_recommended_prescriptions_against_prescribed_and_send_prescriptions`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()` — called from `fetch_and_process_completed_consult_details`
- **Retry config:** None
- **Purpose:** Validates that the prescriptions Wheel wrote match what Evvy recommended; if they match, marks consult COMPLETE, fires `CONSULT_COMPLETED` Braze event, sends to Precision

**79. `check_recommended_prescriptions_against_prescribed`**
- **Args:** `consult_uid`, `notify_admins=False`
- **Enqueued via:** `.delay()` — called from `send_missing_prescriptions_to_precision`
- **Retry config:** None
- **Purpose:** Compares recommended vs actual prescription slugs; creates a manual review if they don't match

**80. `fetch_and_process_referred_consult_details`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()` — called from `retry_consult_detail_processing` and Wheel webhooks
- **Retry config:** None
- **Purpose:** Handles consults where the clinician referred the patient out; stores referral info, creates a task, sets consult to REFERRED, sends referral email

**81. `submit_lab_order_to_wheel`**
- **Args:** `lab_order_uid`
- **Enqueued via:** `.delay()` — called from `resubmit_stuck_lab_orders_to_wheel` and `resubmit_errored_lab_orders_to_wheel`
- **Retry config:** None
- **Purpose:** Submits a lab order to Wheel for clinical requisition (skips if already approved/submitted)

**82. `resubmit_stuck_lab_orders_to_wheel`** (Celery Beat: daily at 11:30 PM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Healing task — finds lab orders in CREATED/SUBMITTED status that have a provider ID and intake submitted >1 hour ago, clears provider ID and resubmits (skips Canadian and manual-review states)

**83. `resubmit_errored_lab_orders_to_wheel`** (Celery Beat: daily at 11:15 PM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Healing task — finds lab orders in ERROR status and resubmits them to Wheel (skips Canadian and already-results-sent orders)

**84. `mark_wheel_consult_message_as_read`**
- **Args:** `consult_uid`, `message_id`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Marks a Wheel consult message as read via the Wheel API

**85. `send_notification_for_stuck_consults`** (Celery Beat: daily at 10:00 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Sends admin email summaries of non-UTI consults stuck in clinical review >24 hours, stuck lab orders, and open manual reviews

**86. `send_notification_for_stuck_uti_consults`** (Celery Beat: daily at 10:05 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Sends admin email for UTI consults specifically stuck in review >24 hours and open UTI manual reviews

**87. `send_notification_for_diagnosis_pending_consults`** (Celery Beat: daily at 10:10 AM)
- **Args:** `hours_threshold=24`
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Alerts on both VHT and UTI tests where lab results were sent to Wheel but diagnosis hasn't been confirmed after `hours_threshold` hours; also retries fetching follow-up details

**88. `send_notification_for_care_orders_in_bad_states`** (Celery Beat: daily at 10:15 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Sends admin alerts for care orders missing a consult, completed consults missing prescription fills, and ungated RX orders missing a consult

**89. `attach_latest_otc_treatment_to_consult`**
- **Args:** `consult: Consult`
- **Enqueued via:** `.delay()` — called from `_post_prescription_fetch_and_process_consult_details`
- **Retry config:** None
- **Purpose:** Attaches the latest OTC probiotic treatment to a consult if the user has an active probiotic subscription

---

### `test_results/microgen/tasks.py`

**90. `submit_lab_order_approval_to_microgen`**
- **Args:** `lab_order_uid`
- **Enqueued via:** `.delay()` — called from `consults/wheel/tasks.py` and Celery Beat
- **Retry config:** None
- **Purpose:** Submits an approved lab order's data to the Microgen API for NGS processing (vaginal microbiome tests)

**91. `submit_research_sample_lab_order_to_microgen`**
- **Args:** `test_hash`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Submits electronic lab order data to Microgen for a research sample test

**92. `submit_missing_lab_order_approvals_to_microgen`** (Celery Beat: daily at 1:15 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Healing task — finds approved lab orders from the last 60 days that were never submitted to Microgen, dispatches `submit_lab_order_approval_to_microgen` for each

**93. `process_test_results_stuck_in_sequencing_status`** (Celery Beat: daily at 1:00 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Finds tests stuck in sequencing status for 7+ days (but < 60 days), attempts to re-fetch results from S3

**94. `process_microgen_test_results`**
- **Args:** `test_hash`, `report_errors=True`, `read_from_staging=False`, `release_results=True`, `bypass_ready_check=False`, `force_update_result_value=False`
- **Enqueued via:** `.delay()` or `.apply_async(countdown=...)` — called from `process_lab_status_update` with optional random delay for load balancing
- **Retry config:** None
- **Purpose:** Processes NGS results file from S3, then dispatches `post_process_test_results` for downstream processing

**95. `process_microgen_test_results_if_exists_in_s3`**
- **Args:** `test_hash`
- **Enqueued via:** `.delay()` — called from `process_test_results_stuck_in_sequencing_status`
- **Retry config:** None
- **Purpose:** Wrapper around `process_microgen_test_results` that silently swallows S3 NoSuchKey errors

**96. `process_microgen_vag_pcr_test_results`**
- **Args:** `test_hash`
- **Enqueued via:** `.delay()` — called from `process_lab_status_update`
- **Retry config:** None
- **Purpose:** Processes vaginal PCR panel results from S3; re-scores the test if full results are ready; triggers PCR results ready email and Braze event

**97. `send_summary_tests_entered_sequencing`**
- **Args:** None
- **Enqueued via:** `.apply_async(countdown=3600)` — triggered by `_queue_summary_notification` using Redis cache as a debounce lock
- **Retry config:** None
- **Purpose:** Sends ops team a summary of tests that entered sequencing in the last 2 hours

**98. `send_summary_vpcr_results_processed`**
- **Args:** None
- **Enqueued via:** `.apply_async(countdown=1200)` — triggered by `_queue_summary_notification`
- **Retry config:** None
- **Purpose:** Sends ops team a summary of PCR results processed in the last 2 hours

**99. `send_summary_vngs_results_processed`**
- **Args:** None
- **Enqueued via:** `.apply_async(countdown=1200)` — triggered by `_queue_summary_notification`
- **Retry config:** None
- **Purpose:** Sends ops team a summary of NGS results processed in the last 2 hours

**100. `process_lab_status_update_batch`**
- **Args:** `payload` (dict with `status_updates` list)
- **Enqueued via:** `.delay()` — called from MDX/Microgen webhook
- **Retry config:** None
- **Purpose:** Iterates a batch of lab status updates and calls `process_lab_status_update` for each (synchronous fan-out within the task)

---

### `test_results/tasks.py`

**101. `create_test_result_tagset`**
- **Args:** `test_hash: str`
- **Enqueued via:** Called directly from `post_process_test_results` (not via `.delay()`)
- **Retry config:** None
- **Purpose:** Generates a `TestResultTagSet` with pregnancy, menopause, symptoms, pathogen, and health context tags from the health history

**102. `post_process_test_results`**
- **Args:** `test_hash`, `release_results=True`
- **Enqueued via:** `.delay()` — called from `process_microgen_test_results`
- **Retry config:** None
- **Purpose:** Master post-processing orchestrator: updates Valencia type, computes test scores, creates fertility module, captures infection state, creates tag set, assigns plan profile, creates recommended treatment program, checks auto-release eligibility, releases results if eligible

**103. `assign_suspected_yeast_flag_to_test_result`**
- **Args:** `test_hash: str`
- **Enqueued via:** Called directly from `post_process_test_results`
- **Retry config:** None
- **Purpose:** Sets `suspected_yeast=True` on a test result if yeast was detected or the user reported yeast infection in the last year

**104. `send_results_ready_emails`**
- **Args:** `test_hash: str`
- **Enqueued via:** `.delay()` — called from `release_test_results`
- **Retry config:** None
- **Purpose:** Sends "Results Ready" email to user; triggers care eligibility email 1 or a-la-care email based on eligibility

**105. `send_test_status_duration_alert`** (Celery Beat: daily at 6:15 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Sends ops email listing tests stuck in RECEIVED, SEQUENCING, or PROCESSING status beyond configured thresholds (7 days for received/sequencing, 4 days for processing)

**106. `send_lab_test_status_duration_alert`** (Celery Beat: daily at 6:15 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Retry config:** None
- **Purpose:** Sends ops email listing PCR lab tests stuck in AT_LAB status for more than 3 days

**107. `send_vip_test_status_update`**
- **Args:** `test_hash`, `previous_status`, `new_status`
- **Enqueued via:** `.delay()`
- **Retry config:** None
- **Purpose:** Sends admin email notification when a VIP (provider-ordered) test changes status

---

### `test_results/lab_services/providers/junction/tasks.py`

**108. `create_unregistered_testkit_order_for_urine_test`**
- **Args:** `urine_test_ids: list[int]`, `ecomm_order_id: int`
- **Enqueued via:** `.delay()` — called during order processing when urine tests are created
- **Retry config:** None
- **Purpose:** Creates unregistered testkit orders in Junction API for each urine test in an order; pre-populates `LabOrderIntake` address from shipping address

**109. `submit_lab_order_approval_to_junction`**
- **Args:** `lab_order_uid: str`
- **Enqueued via:** `.delay()` — called from `consults/wheel/tasks.py` after Wheel approves the lab order
- **Retry config:** `bind=True, max_retries=3, default_retry_delay=60`; exponential backoff on 5xx errors (60s, 120s, 240s); 4xx errors are not retried; on final failure, fires `handle_junction_submission_failure` signal
- **Purpose:** Registers the previously-created unregistered testkit with Junction API after Wheel has approved the lab order and provided clinician NPI

**110. `fetch_and_process_junction_results`**
- **Args:** `external_order_id: str`
- **Enqueued via:** `.delay()` — called from Junction results webhook handler
- **Retry config:** `bind=True, max_retries=3`; exponential backoff: 60s, 120s, 240s (capped at 300s)
- **Purpose:** Fetches lab results from Junction API and processes them through the `LabServicesOrchestrator` (async so the webhook returns immediately)

**111. `fulfill_uti_order_in_shopify`**
- **Args:** `urine_test_id: int`, `tracking_number: str`, `courier: str`
- **Enqueued via:** `.delay()` — called from Junction webhook for `transit_customer` status
- **Retry config:** None
- **Purpose:** Marks the UTI test kit line items as fulfilled in Shopify with tracking info from Junction when the kit ships to the customer

---

### `transactional_email/tasks.py`

**112. `send_test_activated_reminder`** (Celery Beat: daily at 9:00 AM)
- **Args:** None
- **Enqueued via:** Celery Beat schedule
- **Purpose:** Sends reminder email to users who activated their test 4+ days ago but haven't yet taken their sample

**113. `send_tests_in_transit_through_usps_and_fedex_emails`** (DISABLED in Celery Beat)
- **Args:** None
- **Purpose:** Sends "test in transit" email to users whose sample entered IN_TRANSIT status in the last 3 days

**114. `send_tests_in_transit_hh_incomplete`** (Celery Beat: daily at 11 AM and 5 PM)
- **Args:** None
- **Purpose:** Sends reminder email to complete health history when sample is in transit but HH is incomplete

**115. `send_tests_received_at_lab_hh_incomplete`** (Celery Beat: daily at 11 AM and 5 PM)
- **Args:** None
- **Purpose:** Sends reminder email to complete health history when sample was received at the lab but HH is incomplete

**116. `send_ldt_test_sample_received_email`**
- **Args:** `test_hash`
- **Enqueued via:** `.delay()` — called from `test_results/microgen/tasks.py`
- **Purpose:** Sends "sample received at lab" email to user (different templates for standard vs comprehensive LDT)

**117. `send_ldt_test_sample_sequencing_email`**
- **Args:** `test_hash`
- **Enqueued via:** `.delay()` — called from `test_results/microgen/tasks.py`
- **Purpose:** Sends "sample is being sequenced" update email to user

**118. `send_ldt_tests_results_almost_ready`** (DISABLED in Celery Beat)
- **Args:** None
- **Purpose:** Sends "results almost ready" email to users whose tests have been in sequencing for ~10 days

**119. `send_pcr_test_results_ready`**
- **Args:** `test_hash`
- **Enqueued via:** `.delay()` — called from `test_results/microgen/tasks.py`
- **Purpose:** Sends "PCR preliminary results ready" notification email

**120. `send_expert_call_emails`** (Celery Beat: daily at 8:00 AM)
- **Args:** None
- **Purpose:** Sends coaching call offer email 1 day after results ready to users who have not yet purchased care

**121. `send_view_unread_plan_emails`** (DISABLED in Celery Beat)
- **Args:** None
- **Purpose:** Sends "view your unread plan" email 3 days after results viewed if plan has not been viewed

**122. `send_eligible_for_care_1_for_test`**
- **Args:** `test_id`
- **Enqueued via:** `.delay()` — called from `test_results/tasks.py`
- **Purpose:** Sends first care eligibility email to user immediately when results are ready

**123. `send_eligible_for_a_la_care_not_treatment_program`**
- **Args:** `test_id`
- **Enqueued via:** `.delay()` — called from `test_results/tasks.py`
- **Purpose:** Sends a-la-care eligibility email for users eligible for individual treatments but not the full bundle

**124. `send_a_la_care_treatments_ready`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends "individual treatments ready" email when a-la-care consult treatment plan is ready

**125. `send_eligible_for_care_2`** (Celery Beat: daily at 9:45 AM)
- **Args:** None
- **Purpose:** Sends second care eligibility email 6 days after results ready for users still not in care

**126. `send_eligible_for_care_3`** (Celery Beat: daily at 10:15 AM)
- **Args:** None
- **Purpose:** Sends third care eligibility email 12 days after results ready for users still not in care

**127. `send_treatments_shipped`**
- **Args:** `prescription_fill_id`
- **Enqueued via:** `.delay()` — called from Precision webhook processing
- **Purpose:** Sends "treatments shipped" email with tracking link

**128. `send_treatments_delivered`**
- **Args:** `prescription_fill_id`
- **Enqueued via:** `.delay()` — called from Precision webhook processing
- **Purpose:** Sends "treatments delivered" confirmation email (different templates for a-la-care vs bundle vs refill)

**129. `send_consult_intake_abandonment_reminder`** (DISABLED in Celery Beat)
- **Args:** None
- **Purpose:** Sends consult intake abandonment reminder email 2–6 hours after care paid but intake not submitted

**130. `send_consult_intake_abandonment_reminder_2`** (DISABLED in Celery Beat)
- **Args:** None
- **Purpose:** Sends second consult intake abandonment reminder 24–48 hours after care paid

**131. `send_sti_consult_intake_abandonment_reminder`** (Celery Beat: daily at 10:30 AM, 4:30 PM, 10:30 PM)
- **Args:** None
- **Purpose:** Sends STI-specific consult intake abandonment reminder 24–36 hours after care paid

**132. `send_sti_prescription_sent_to_pharmacy_email`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends email to STI consult user with local pharmacy pickup details when prescription is sent

**133. `send_email_organon_prescriptions_ready`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends email when Organon-sourced prescriptions are ready for pharmacy pickup

**134. `send_consult_intake_reviewed_email`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()` — called from `submit_consult_intake_to_wheel`
- **Purpose:** Sends "intake has been reviewed by a clinician" email with message thread link

**135. `send_treatment_plan_ready_email`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends "treatment plan is ready" email with link to treatment plan

**136. `send_lab_order_rejected_email`**
- **Args:** `lab_order_uid`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends email when a lab order is rejected by the clinician

**137. `send_id_verification_failed_email`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends email with instructions to re-upload photo ID after verification failure

**138. `send_care_referred_out_email`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()` — called from `fetch_and_process_referred_consult_details`
- **Purpose:** Sends email when a clinician auto-refers the patient out due to disqualifying responses

**139. `send_new_consult_message_email`**
- **Args:** `consult_uid`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends notification email when a new message arrives in the consult thread

**140. `send_care_first_check_in_email`**
- **Args:** None (scheduled)
- **Enqueued via:** Celery Beat (though not currently listed in active schedule)
- **Purpose:** Sends first care check-in email 4 hours after treatment plan ready for bundle care users

**141. `send_prescription_refills_available`** (Celery Beat: daily at 7:15 AM)
- **Args:** None
- **Purpose:** Sends "refills available" email to consults eligible for prescription refills

**142. `send_sample_taken_but_not_in_transit_reminder`** (DISABLED in Celery Beat)
- **Args:** None
- **Purpose:** Sends reminder to mail the sample back when sample has been taken for 5+ days but not yet in transit

**143. `send_test_sample_at_lab_but_not_activated`**
- **Args:** `test_hash`
- **Enqueued via:** `.delay()` — called from `test_results/microgen/tasks.py`
- **Purpose:** Sends activation reminder email for tests that arrived at the lab without being activated

**144. `send_test_sample_received_at_lab_but_not_activated`** (Celery Beat: daily at 4:00 PM)
- **Args:** None
- **Purpose:** Sends activation reminder to all tests in RECEIVED status without an associated user

**145. `send_account_transfer_verification_email`**
- **Args:** `user_id: int`, `order_email: str`, `order_number: str`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends verification email when a user tries to transfer an order placed under a different email to their account

---

### `providers/tasks.py`

**146. `send_intake_completed_notifications`** (from `accounts/tasks.py`)
- **File:** `/Users/albertgwo/Work/evvy/backend/accounts/tasks.py`
- **Args:** `provider_email`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends internal admin email when a provider completes their registration intake (different messages for NY state and "Other" state providers)

**147. `send_provider_ordered_single_test_notifications`**
- **File:** `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`
- **Args:** `provider_email`, `patient_email`, `provider_test_order_id`, `payer`, `add_expanded_pcr=False`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends internal admin FYI email when a provider orders a single test for a patient

**148. `send_provider_bulk_ordered_tests_notification`**
- **File:** `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`
- **Args:** `provider_email`, `num_ordered`, `provider_test_order_ids`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends internal admin FYI email when a provider initiates a bulk test order (pending payment)

**149. `send_provider_bulk_order_paid_notification`**
- **File:** `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`
- **Args:** `ecomm_order_id`, `provider_email`, `quantity`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends internal admin FYI email when a provider bulk order is paid

**150. `send_provider_test_results_ready`**
- **File:** `/Users/albertgwo/Work/evvy/backend/providers/tasks.py`
- **Args:** `provider_email`
- **Enqueued via:** `.delay()`
- **Purpose:** Sends "results ready" email to a provider when their patient's test results are available

---

### `ecomm/shopify/tasks.py`

**151. `retry_failed_shopify_orders`** (Celery Beat: daily at 1:00 AM)
- **File:** `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py`
- **Args:** None
- **Retry config:** `soft_time_limit=600, time_limit=900` (10-minute soft limit, 15-minute hard limit)
- **Purpose:** Fetches Shopify orders from the last 3 days that are missing in the Evvy DB and reprocesses them (up to 1000 orders across 50 pages)

---

### `app/tasks.py` (referenced in Celery Beat but not detailed above)

`clean_log_entries` is referenced in the schedule (`app.tasks.clean_log_entries`, daily at midnight) — a housekeeping task in `/Users/albertgwo/Work/evvy/backend/app/tasks.py`.

---

## Summary by Category

| Category | Task Count |
|---|---|
| Analytics / event tracking (Fullstory, Klaviyo, Braze) | ~34 |
| Transactional email | ~34 |
| Consult workflow (Wheel telehealth integration) | ~22 |
| Pharmacy fulfillment (Precision) | ~10 |
| Lab processing (Microgen NGS, Junction UTI) | ~12 |
| Test kit shipping & fulfillment (Berlin, Shopify) | ~8 |
| ecomm / order management | ~7 |
| Care / treatment calendar | ~4 |
| Subscriptions | ~1 |
| Provider notifications | ~5 |
| Accounts | ~1 |

**Total: ~151 Celery tasks** across 14 task files, with approximately 40 scheduled via Celery Beat and the remainder enqueued on-demand via `.delay()` or `.apply_async()`.

### Tasks with Retry Configuration
- `/Users/albertgwo/Work/evvy/backend/ecomm/tasks.py` — `void_share_a_sale_transaction`: `@retry(stop_max_attempt_number=3, wait_exponential_multiplier=500)` via the `retrying` library
- `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py` — `submit_lab_order_approval_to_junction`: `max_retries=3`, exponential backoff 60s/120s/240s on 5xx; final failure handled via `task_failure` signal
- `/Users/albertgwo/Work/evvy/backend/test_results/lab_services/providers/junction/tasks.py` — `fetch_and_process_junction_results`: `max_retries=3`, exponential backoff 60s/120s/240s capped at 300s
- `/Users/albertgwo/Work/evvy/backend/ecomm/shopify/tasks.py` — `retry_failed_shopify_orders`: `soft_time_limit=600, time_limit=900` (time limits, not retry counts)
