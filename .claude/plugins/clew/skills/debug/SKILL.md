# Debug Trace

Trace a bug from an error symptom to its root cause using semantic search and relationship traversal.

## When to Use

- You have an error message, stack trace, or symptom and need to find the root cause
- You need to understand the error handling path for a specific operation
- You're tracing how data flows through a pipeline to find where it breaks

## When NOT to Use

- The error message contains a clear file path and line number (just use Read)
- You need to search for a literal error string (use grep for exact matches)
- You're exploring the codebase without a specific bug (use the discover or onboard skills)

## Workflow

### Step 1: Search for the Error

Start with the error symptom. Use `intent="debug"` to bias results toward error handling code.

```
search(query="timeout when calling payment API", intent="debug")
search(query="prescription validation fails with invalid date", intent="debug")
```

If you have an error class name, search for that too:

```
search(query="PaymentTimeoutError handling and retry logic", intent="debug")
```

### Step 2: Read the Error Handler

Read the full source of the most relevant result to understand the error path.

```
Read file_path="app/payments/client.py", offset=45, limit=30
```

Look for: what triggers the error, what catches it, what gets logged, what gets returned to the caller.

### Step 3: Trace Callers

Find who calls the function that raises or handles the error. This reveals the full call chain.

```
trace(entity="app/payments/client.py::PaymentClient.charge", direction="inbound")
```

This shows every code path that can trigger the error -- the bug may be in how a caller invokes this code, not in the function itself.

### Step 4: Search for Related Error Handling

Search for related error handling patterns -- the same error may be caught or handled inconsistently.

```
search(query="PaymentTimeoutError catch retry fallback")
search(query="payment error handling across services")
```

### Step 5: Trace Dependencies (if needed)

If the bug involves incorrect data, trace outbound from the data source.

```
trace(entity="app/models.py::Prescription.calculate_dose", direction="outbound")
```

This reveals what external data or services the function depends on -- any of which could be the source of bad data.

## Example: Debugging a 500 Error on Checkout

1. `search(query="checkout order processing failure", intent="debug")` -- find the checkout flow
2. Read `app/views.py::CheckoutView.post` to see the main handler
3. `trace(entity="app/views.py::CheckoutView.post", direction="outbound")` -- see all dependencies
4. `search(query="inventory check stock validation", intent="debug")` -- the trace revealed an inventory call
5. Read the inventory service to find it doesn't handle the out-of-stock case
6. `trace(entity="app/inventory.py::check_stock", direction="inbound")` -- verify no other callers handle this

## Tips

- Use `intent="debug"` -- it biases results toward error handling, logging, and exception code
- Trace inbound first (who calls the broken code?) before tracing outbound (what does it depend on?)
- Search for both the error name and the behavior ("times out" vs "TimeoutError")
- If search returns too many results, add filters: `filters={"language": "python"}` or `filters={"layer": "service"}`
- When the root cause spans multiple files, use explain to get a synthesized summary:
  ```
  explain(file_path="app/payments/client.py", question="Why might charge() time out?")
  ```
