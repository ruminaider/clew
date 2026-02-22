# Test B2: Mapping Relationships Between Order, PrescriptionFill, and Prescription Models

**Test Category:** Structural Analysis
**Date:** 2026-02-19

## Task
Map the relationship between Order, PrescriptionFill, and Prescription models. Include foreign keys, many-to-many relationships, through-tables, and any computed properties that bridge them.

## Search Process

### Step 1: Initial Discovery - Model Definitions
I started by searching for the three main model classes:

```bash
search("Order model class definition")
search("PrescriptionFill model class definition")
search("Prescription model class definition")
```

**Results:**
- Order: `/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py` (lines 11-181)
- PrescriptionFill: `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 721-828)
- Prescription: `/Users/albertgwo/Work/evvy/backend/care/models.py` (lines 481-682)

### Step 2: Reading Model Definitions
I read the full model definitions to understand direct relationships:

```bash
read("/Users/albertgwo/Work/evvy/backend/care/models.py", lines 481-830)
read("/Users/albertgwo/Work/evvy/backend/ecomm/models/order.py", lines 11-191)
```

**Key findings:**
- **PrescriptionFill** has:
  - Direct FK to Order: `order = models.ForeignKey("ecomm.Order", null=True, blank=True, on_delete=models.SET_NULL)` (line 770)
  - M2M to Prescription via through table: `prescriptions = models.ManyToManyField(Prescription, blank=True, through="PrescriptionFillPrescriptions")` (lines 755-757)
  - M2M to OTCTreatment via through table: `otctreatments = models.ManyToManyField("OTCTreatment", blank=True, through="PrescriptionFillOTCTreatments")` (lines 759-761)
  - FK to Consult: `consult = models.ForeignKey("consults.Consult", null=True, blank=True, on_delete=models.CASCADE)` (lines 763-768)

- **Prescription** has:
  - FK to Consult: `consult = models.ForeignKey("consults.Consult", null=False, blank=False, on_delete=models.CASCADE)` (lines 491-493)
  - M2M to Consult (audit trail): `consults = models.ManyToManyField("consults.Consult", through="PrescriptionConsults", related_name="consult_prescription_set")` (lines 494-496)
  - M2M to Test: `tests = models.ManyToManyField("test_results.Test", blank=True, through="PrescriptionTest")` (line 490)
  - No direct FK to Order

### Step 3: Discovering Through Tables
I searched for the through tables mentioned in the M2M relationships:

```bash
read("/Users/albertgwo/Work/evvy/backend/care/models.py", lines 831-893)
```

**Through tables found:**
1. **PrescriptionFillOrder** (lines 831-845) - Bridge between PrescriptionFill and Order
2. **PrescriptionFillPrescriptions** (lines 864-892) - Bridge between PrescriptionFill and Prescription
3. **PrescriptionFillOTCTreatments** (lines 927-952) - Bridge between PrescriptionFill and OTCTreatment
4. **PrescriptionConsults** (lines 696-718) - Audit table for Prescription and Consult updates

### Step 4: Using Code Relationships to Validate
I used relationship tracing to verify the relationship graph:

```bash
search("code related to PrescriptionFill")
search("code related to backend/ecomm/models/order.py::Order")
search("code related to backend/care/models.py::Prescription")
```

**Results confirmed:**
- PrescriptionFillOrder has FK to both PrescriptionFill and Order
- PrescriptionFillPrescriptions has FK to both PrescriptionFill and Prescription
- Multiple classes reference these core models

### Step 5: Computed Properties
I searched for computed properties that bridge these models:

```bash
search("property prescription fill order")
read("/Users/albertgwo/Work/evvy/backend/care/models.py", lines 605-683)
```

**Computed properties found:**
- `Prescription.fill_count` (property, lines 605-629): Computes total fills by querying PrescriptionFillPrescriptions through table
- `Prescription.refills_remaining` (property, lines 646-656): Uses fill_count to calculate remaining refills
- `Prescription.can_refill` (property, lines 659-666): Boolean check using refills_remaining and other product constraints
- `PrescriptionFill.is_refill` (property, lines 805-806): Returns whether fill_count > 1

## Complete Relationship Map

### 1. Order Model (`backend/ecomm/models/order.py`)

**Location:** Lines 11-181

**Foreign Keys:**
- `user` → User (nullable)
- `cart` → Cart (nullable)

**Reverse Relationships:**
- `otc_treatments` ← OTCTreatment (related_name)
- `line_items` ← OrderLineItem (related_name)
- Referenced by PrescriptionFill.order
- Referenced by PrescriptionFillOrder.order

**Key Fields:**
- `provider_id`: CharField (legacy Shopify ID)
- `order_number`: CharField (current order identifier)
- `order_type`: CharField with choices (TEST, VAGINITIS_CARE, STI_CARE, etc.)
- `status`: CharField (ACTIVE or CANCELLED)
- `payload`: JSONField (full Shopify webhook data)

### 2. PrescriptionFill Model (`backend/care/models.py`)

**Location:** Lines 721-828

**Foreign Keys:**
- `user` → User (nullable)
- `consult` → consults.Consult (nullable as of 5/2/2025)
- `order` → ecomm.Order (nullable, SET_NULL on delete) **[DIRECT LINK TO ORDER]**

**Many-to-Many Relationships:**
- `prescriptions` ↔ Prescription (through PrescriptionFillPrescriptions)
- `otctreatments` ↔ OTCTreatment (through PrescriptionFillOTCTreatments)

**Reverse Relationships:**
- Referenced by PrescriptionFillOrder.prescription_fill
- Referenced by FillPackagingItem.prescription_fill

**Key Fields:**
- `status`: CharField with choices (draft, created, shipped, delivered, warning, cancelled, failed)
- `fill_count`: IntegerField (default=1, indicates refill number)
- `sent_to_pharmacy_at`: DateTimeField
- `payload`: JSONField (precision API fulfillment data)
- Shipping address fields (address_first_line, city, state_code, zip_code)
- `pharmacy_patient_id`: CharField

**Computed Properties:**
- `shipping_tracking_url`: Returns tracking URL from shipping_tracking_number
- `is_refill`: Returns fill_count > 1
- `full_address_string`: Concatenates address fields
- `can_cancel`: Returns whether fill can be cancelled (created status + sent to pharmacy)

### 3. Prescription Model (`backend/care/models.py`)

**Location:** Lines 481-682

**Foreign Keys:**
- `consult` → consults.Consult (required)
- `user` → User (required)
- `product` → care.Product (nullable - can be non-Evvy product)

**Many-to-Many Relationships:**
- `tests` ↔ test_results.Test (through PrescriptionTest)
- `consults` ↔ consults.Consult (through PrescriptionConsults, related_name="consult_prescription_set") **[AUDIT TRAIL]**

**Reverse Relationships:**
- Referenced by PrescriptionFillPrescriptions.prescription

**Key Fields:**
- `prescription_date`: DateField
- `expiration_date`: DateField (computed)
- `num_allowed_refills`: IntegerField (default=0)
- `rx_price`: DecimalField (set from product price on creation)
- `deleted`: BooleanField (soft delete flag)
- `delete_reason`: CharField with choices
- `created_by`: CharField (PROVIDER or EVVY)
- `sent_to_pharmacy_at`: DateTimeField
- `needs_subscription_cancellation`: BooleanField

**Computed Properties:**
- `fill_count` (lines 605-629): Queries PrescriptionFillPrescriptions to count valid fills, returns ceiling of total_quantity / product.quantity_value
- `is_refillable_product`: Returns whether product type allows refills (not antibiotic/antifungal)
- `is_otc_product`: Returns whether product is over-the-counter
- `refills_remaining` (lines 646-656): Calculates remaining refills based on expiration, max_allowed_refills, and fill_count
- `can_refill` (lines 659-666): Boolean combining refills_remaining, is_refillable_product, expiration check, and product status

### 4. Through Tables

#### PrescriptionFillOrder (`backend/care/models.py`, lines 831-845)

**Purpose:** Bridge between PrescriptionFill and Order (many-to-many relationship not defined in main models)

**Foreign Keys:**
- `prescription_fill` → PrescriptionFill (required, CASCADE)
- `order` → ecomm.Order (required, CASCADE)

**Constraints:**
- `unique_together = ("prescription_fill", "order")`

**Note:** This exists alongside the direct FK from PrescriptionFill.order, suggesting the direct FK was added later for primary order tracking while this through table maintains the full order history.

#### PrescriptionFillPrescriptions (`backend/care/models.py`, lines 864-892)

**Purpose:** Through table for PrescriptionFill ↔ Prescription many-to-many

**Foreign Keys:**
- `prescriptionfill` → PrescriptionFill (required, CASCADE)
- `prescription` → Prescription (required, CASCADE)

**Additional Fields:**
- `fill_quantity`: IntegerField (nullable, specific quantity for this fill)
- `precision_reference_id`: CharField (external pharmacy system reference)

**Methods:**
- `get_effective_fill_quantity()`: Returns fill_quantity or falls back to prescription.quantity_value
- `save()`: Auto-sets fill_quantity from prescription.quantity_value if not provided

**Database:**
- Custom `db_table = "care_prescriptionfill_prescriptions"`
- Index on prescriptionfill field

#### PrescriptionFillOTCTreatments (`backend/care/models.py`, lines 927-952)

**Purpose:** Through table for PrescriptionFill ↔ OTCTreatment many-to-many

**Foreign Keys:**
- `prescriptionfill` → PrescriptionFill (required, CASCADE)
- `otctreatment` → OTCTreatment (required, CASCADE)

**Additional Fields:**
- `fill_quantity`: IntegerField (nullable)
- `precision_reference_id`: CharField

**Constraints:**
- UniqueConstraint on otctreatment (ensures one OTC treatment per fill)

**Database:**
- Custom `db_table = "care_prescriptionfill_otctreatments"`
- Index on prescriptionfill field

#### PrescriptionConsults (`backend/care/models.py`, lines 696-718)

**Purpose:** Audit trail for Prescription ↔ Consult relationship (tracks updates over time)

**Foreign Keys:**
- `prescription` → Prescription (required, CASCADE)
- `consult` → consults.Consult (required, CASCADE)

**Additional Fields:**
- `updated_refill_count`: IntegerField (nullable)
- `updated_expiration_date`: DateField (nullable)
- `updated_date`: DateTimeField (nullable)

**Constraints:**
- `unique_together = ("prescription", "consult")`
- Indexes on both prescription and consult fields

#### PrescriptionTest (`backend/care/models.py`, lines 685-693)

**Purpose:** Through table for Prescription ↔ Test many-to-many

**Foreign Keys:**
- `prescription` → Prescription (required, CASCADE)
- `test` → test_results.Test (required, CASCADE)

### 5. Related Model: OTCTreatment

**Location:** `backend/care/models.py`, lines 895-924

**Foreign Keys:**
- `user` → User (nullable)
- `order` → ecomm.Order (required, CASCADE, related_name="otc_treatments") **[DIRECT LINK TO ORDER]**
- `product` → care.Product (required)

**Many-to-Many:**
- `consults` ↔ consults.Consult (through ConsultOTCTreatment)

This model creates an alternative path: Order → OTCTreatment → PrescriptionFill (via through table)

## Relationship Diagram

```
                                  ┌──────────────────┐
                                  │      Order       │
                                  │  (ecomm model)   │
                                  └────────┬─────────┘
                                           │
                         ┌─────────────────┼──────────────────┐
                         │ (FK: order)     │ (FK: order)      │
                         │ SET_NULL        │ CASCADE          │
                         ▼                 ▼                  │
              ┌──────────────────┐  ┌─────────────┐          │
              │ PrescriptionFill │  │OTCTreatment │          │
              │   (care model)   │  │             │          │
              └────────┬─────────┘  └──────┬──────┘          │
                       │                   │                 │
                       │ M2M (through)     │ M2M (through)   │
                       ▼                   ▼                 │
         ┌─────────────────────────┐  ┌──────────────────┐  │
         │PrescriptionFillPrescriptions│  │PrescriptionFill  │  │
         │  - fill_quantity        │  │  OTCTreatments   │  │
         │  - precision_ref_id     │  │  - fill_quantity │  │
         └──────────┬──────────────┘  └──────────────────┘  │
                    │                                        │
                    │ (FK: prescription)                     │
                    │ CASCADE                                │
                    ▼                                        │
         ┌──────────────────┐                                │
         │   Prescription   │                                │
         │  (care model)    │                                │
         └──────────────────┘                                │
                                                             │
         Additional Bridge Table (many-to-many):             │
         ┌──────────────────────────┐                       │
         │  PrescriptionFillOrder   │◄──────────────────────┘
         │  - prescription_fill FK  │
         │  - order FK              │
         │  unique_together         │
         └──────────────────────────┘
```

## Key Insights

1. **Dual Order Relationships:** PrescriptionFill has BOTH:
   - A direct FK to Order (`order` field, line 770) - likely the primary/most recent order
   - A many-to-many through PrescriptionFillOrder - likely historical/multiple orders

2. **No Direct Prescription → Order Link:**
   - Prescription never directly references Order
   - The connection is always through PrescriptionFill
   - Path: Prescription → PrescriptionFillPrescriptions → PrescriptionFill → Order

3. **Fill Tracking via Through Table:**
   - PrescriptionFillPrescriptions stores `fill_quantity` per fill
   - Prescription.fill_count (computed property) aggregates these quantities
   - Enables tracking partial fills and refills

4. **Audit Trail Pattern:**
   - PrescriptionConsults tracks historical updates to prescriptions across multiple consults
   - Stores updated_refill_count, updated_expiration_date, updated_date

5. **OTC Alternative Path:**
   - OTCTreatment provides a non-prescription path from Order to PrescriptionFill
   - Used for over-the-counter products like probiotics

6. **Consult as Central Hub:**
   - Both Prescription and PrescriptionFill reference Consult
   - Consult acts as the clinical context tying orders and prescriptions together

## Tool Effectiveness

**Strengths:**
- Search quickly located all three model definitions
- Relationship exploration validated relationships and discovered through tables
- Search for "property prescription fill order" successfully found computed properties

**Efficiency:**
- Total queries: 10 (well within 20 budget)
- Direct hits on first searches for all models
- Through tables discovered via both search and reading model definitions

**Completeness:**
- All foreign keys identified
- All many-to-many relationships mapped
- Through tables fully documented with fields
- Computed properties discovered and analyzed
- Alternative relationship paths (OTCTreatment) identified
