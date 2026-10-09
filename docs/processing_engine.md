# Running the claims-processing baseline

## Purpose and limits

This milestone implements seven deterministic Python stages with controlled local evidence and explicit routing. It is the testable foundation for later agentic LLM orchestration, not a trained model or an autonomous LLM system. No model or network tools are connected. There are no real payouts.

The CLI processes the original registered samples. The browser additionally accepts new synthetic submissions stored in SQLite and synthetic text documents, using isolated snapshots to feed this same engine. See [the portal guide](portal_demo.md). PDF uploads, human-review actions, and model comparison remain later milestones.

## Run

From the project directory:

```bash
source .venv/bin/activate
python scripts/process_claim.py --claim-id CLM-000001
python scripts/process_claim.py --all
python -m unittest discover -s tests -v
```

Each invocation saves a new JSON audit report under `runtime/runs/`. The folder is ignored by Git. Reports contain a unique run ID, engine version, actual UTC execution timestamps, stage timings, evidence references, source access events, confidence, risk, settlement estimate, and routing explanation. The business reference date stays 2026-10-01 for reproducibility. Repeat runs are independent simulations, not additional insurance claims; do not count reports as unique claims in a future dashboard.

The CLI exits with status 1 when processing is blocked by malformed or unavailable internal evidence/configuration. A completed review, pending-documents, investigation, or rejected route exits with status 0 because routing itself succeeded. Each saved report is created exclusively to avoid overwriting another run; the audit files are not tamper-proof.

## Expected baseline results

| Claim | Line | Route | Estimated settlement INR |
| --- | --- | --- | ---: |
| CLM-000001 | Motor – Car | STP Approved | 23,000 |
| CLM-000002 | Motor – Bike | STP Approved | 7,000 |
| CLM-000003 | Health | STP Approved | 19,000 |
| CLM-000004 | Life | Human Review | 1,000,000 |
| CLM-000005 | Travel | STP Approved | 9,000 |
| CLM-000006 | Home/Property | STP Approved | 32,500 |
| CLM-000007 | Personal Accident | STP Approved | 50,000 |

An estimate on a reviewed or investigated claim is not approval. Insufficient evidence, invalid policy or excluded coverage withholds the estimate (`null`).

## Seven stages

1. **Intake (`INTAKE-01`):** required fields, positive integer INR amount, valid incident/submission chronology, and document presence.
2. **Policy Validation (`POL-VALID-01`):** policy/customer/line matching, paid premium, and inclusive validity on the incident date. The explicit unpaid-premium and date rules are academic engine assumptions documented here; they are not real legal insurance terms.
3. **Coverage (`EVIDENCE-01` plus policy clause IDs):** covered/excluded event matching and synthetic-template document checks. Unknown events require review.
4. **Historical Claims (`HISTORY-01`):** previous registered claims on the same policy, including same-day entries conservatively because the source has dates rather than submission times. Future entries are ignored for this claim's risk assessment.
5. **Anomaly Detection (`RISK-01` and indicator IDs):** duplicate policy/incident, at least three historical entries within 90 days (including same-day entries), and conflicting document incident dates. Scores are summed once per supported indicator and capped at 100. The wording describes risk, never a fraud verdict.
6. **Settlement (policy settlement clause):** calculate the documented reimbursement or fixed-benefit formula only after sufficient consistent evidence. A fixed-benefit amount mismatch or zero payable estimate requires review.
7. **Decision & Routing (`ROUTE-01`):** Investigation → Pending Documents → Human Review → Rejected → STP Approved, using the thresholds and constraints in the routing and policy records. High confidence does not bypass mandatory review or value/risk gates.

Policy clause IDs come from registered policy rules. Generic IDs such as `INTAKE-01` identify these engine procedures; they are not additional retrieved policy documents. Evidence references identify the actual record or document examined.

## What verification and confidence mean

Documents remain marked `unverified` in the immutable input fixtures. During a run the engine validates the registered file hash and document metadata hash, exact template, claim/policy identifiers, type, incident date, event, and claimed amount. Reimbursement evidence must provide a positive supported expense. Duplicate/unknown fields, unexpected documents, arbitrary instructions, and contradictory values require review.

This is **synthetic-template consistency verification**, not authentication of hospital records, invoices, identities or deaths. A forged but consistent synthetic template can pass; real-world use would require stronger independent checks. Document text is never executed or treated as instructions.

The current confidence score is binary: 1.0 means the required synthetic evidence is present and consistent; 0.0 means unresolved or incomplete evidence. It is not a calibrated probability, accuracy score, or LLM self-assessment. Both are compared with the configured 0.90 threshold. Graded or model confidence will need its own evaluation later.

## Closed-world implementation

`backend/evidence.py` permits only relative, manifest-listed local sources with the correct source scope and digest; absolute paths, URLs, path escapes and unauthorized files are blocked. Claim documents remain a distinct untrusted-evidence scope. There is no network tool in the engine. Reported external sources accessed is calculated from engine source-access events, not from operating-system network monitoring.

The manifest is a local development trust anchor, not a signed approval service. Anyone who can modify both the manifest and files can change the accepted fixtures. All required internal datasets are checked at load time; a corrupt dependency blocks processing rather than risking approval. A missing or unsupported submitted document results in pending documents or review, as appropriate.

Tests create their own temporary approved synthetic scenarios, so they do not modify baseline datasets. They cover routes, settlement values, missing/conflicting evidence, exclusions, invalid policies, high values, risk signals, prompt injection, source restrictions, integrity failures, and report preservation. These tests are not the later approximately 30-case multi-model benchmark.
