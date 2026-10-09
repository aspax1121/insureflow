# Customer-to-management demo

Two portals share one local Streamlit application and one FastAPI backend:

- [Customer Portal](http://localhost:8501/?portal=customer)
- [Management Portal](http://localhost:8501/?portal=management)
- [Developer API documentation](http://localhost:8000/docs)

Open the customer and management links in separate browser tabs for the demo. Portal selection is navigation, not authentication. This local academic version has no separate user accounts; all claims are fictitious and shared across the demo.

## Customer journey

1. Select an insurance line and one of its registered synthetic policies. Customer ID comes from that policy; no personal information is collected.
2. Enter an incident reference/date/type and claimed amount. The fixed business date is 2026-10-01. Choose a distinct incident reference for a new incident.
3. Confirm synthetic data and click **Save claim and continue to documents**. A persistent ID such as `CLM-NEW-000001` is created. Management can already see it awaiting submission.
4. Choose an evidence mode:
   - **Upload synthetic files:** download each supported template, edit it if testing a scenario, then attach the UTF-8 `.txt` files. Maximum 16 KB per file. Only the required document types are supported.
   - **Use generated demo documents:** explicitly use fictional documents generated from the entered fields. This is a simulation convenience, not independent verification. The audit report records this mode.
   - **Submit without documents:** demonstrate the evidence gate and Pending Documents route.
5. Confirm the documents are synthetic and click **Submit documents & run seven agents**.
6. Read the route, policy/coverage findings, document completeness, risk, estimate, confidence and stage audit. All seven deterministic stages execute synchronously before the result appears. There is no background job or live-streamed agent progress yet.

Under **Track my demo claims**, select any saved claim after a page or server restart. To add evidence, submit the complete document set again. Each run creates a separate snapshot and audit report; it never erases a previous run. Claim details are fixed after creation in this version. Creating another claim for the same incident is a separate submission and may trigger an investigation indicator.

## Management journey

Click **Refresh dashboard** after a customer submission in another tab. The portal reads the shared backend and shows:

- Customer drafts awaiting document submission.
- Latest processed result per claim, including the new customer claims.
- Route percentages, timing, settlement estimates, insurance-line and risk charts.
- Agent activity, evidence and routing reasons in the audit tab.
- Governance counters, approved baseline source status, historical fixtures, and an honest unrun model-comparison tab.

**Process all samples** processes only the original seven fixtures; it does not submit or alter customer drafts. Route metrics use processed claims only. Drafts are shown separately. Repeated runs do not inflate claim counts. Management can inspect results but cannot manually approve, reject or override them yet.

## Suggested scenarios

| Input / evidence | Expected routing |
| --- | --- |
| Motor – Car, collision, INR 25,000, complete matching demo documents, new incident | STP Approved, INR 23,000 estimate |
| Same claim with no documents | Pending Documents |
| Motor – Car, collision, INR 60,000, complete matching documents | Human Review |
| Motor – Car, mechanical_breakdown, complete matching documents | Rejected under the fictional exclusion |
| Life with complete evidence | Human Review |
| Another submitted claim with the same policy and incident reference | Investigation |
| Uploaded evidence with conflicting date or extra instruction text | Human Review (or Investigation if combined risk reaches the threshold) |

Prior customer submissions contribute to duplicate/frequency signals. If you have already submitted three recent claims on the same policy, a new otherwise-valid claim can require review. This is intentional; demo results depend on persisted history. Do not delete the database to bypass a risk finding.

## Storage and closed-world design

- `runtime/submissions.sqlite3`: claim records, submitted text and latest result. Creation request IDs prevent duplicate records on a retried create request.
- `runtime/evidence/<snapshot-id>/`: per-run copies of hash-checked internal sources, submitted claim and raw untrusted documents. Earlier processed customer claims are added to the historical view for duplicate/frequency checks.
- `runtime/runs/<run-id>.json`: full results with `evidence_root`, allowing evidence paths to be resolved against the exact snapshot used.

Original `data/` files and their baseline manifest remain unchanged. Only validated application submissions are registered into a runtime manifest, and uploaded text keeps the untrusted-evidence scope. Hash registration is not document authentication. No web retrieval or LLM calls occur. Database writes and processing are serialized through SQLite for this local demo. This is not a signed or tamper-proof storage system.

No PDF, image OCR, real identity verification, human approval workflow, or trained model is included. The supplied agents are explicit Python stages; genuine LLM reasoning and model comparison remain later work. Their confidence score still measures synthetic evidence consistency, not real-world certainty.

## Start and test

Use the two-terminal commands in [Local browser setup](local_browser.md). If the servers are already running, open the links rather than starting duplicate processes on the same ports. Backend source changes require a backend restart unless you run with `--reload`.

```bash
python -m unittest discover -s tests -v
python scripts/validate_data.py
```

Tests use temporary databases and evidence folders. They cover creation, persistence, document validation, missing-document recovery, duplicate submissions, dashboard visibility, unchanged baseline fixtures, and the two-portal UI flow.
