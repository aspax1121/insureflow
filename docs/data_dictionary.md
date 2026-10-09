# Synthetic data guide

All values are fictional academic assumptions, not real product terms or advice. Dataset version: `INSUREFLOW-DEMO-V1`. Fixed reference date: **2026-10-01**, independent of today's date. Amounts are whole Indian rupees (INR); fractional currency support can be introduced later.

## Files and relationships

Each dataset JSON has `schema_version`, `dataset_id`, `as_of_date`, and `records`. Most `records` values are lists; routing rules use a single object.

| File under data/ | Record key | Meaning and links |
| --- | --- | --- |
| customers/customers.json | customer_id | Synthetic display label only; no contact details or real PII |
| policies/policies.json | policy_id | Customer, insurance line, inclusive coverage dates, premium-paid flag, currency, rule_id |
| rules/policy_rules.json | rule_id | Versioned coverage/exclusion clauses, required document types, settlement mode, deductible, per-claim limit, STP ceiling |
| demo_claims/claims.json | claim_id | Current example submissions: customer/policy, incident ID/date, submission date, event and claimed amount |
| historical_claims/claims.json | claim_id | Earlier closed claims, settlement amount and prior route; evidence of history, not authority for approving another claim |
| claim_documents/documents.json | document_id | Claim link, document type, relative text path, SHA-256 digest, unverified status |
| rules/anomaly_indicators.json | indicator_id | Observable pattern and illustrative risk points; no accusation of fraud |
| rules/routing_rules.json | rule_id | Proposed route precedence, evidence confidence and risk thresholds |

There are seven customers, seven policies, seven demo claims, six historical claims, seven policy rule sets, and fourteen synthetic text documents. Life has no historical death claim on the same policy. `data/test_cases/` remains reserved for the later approximately 30 evaluation cases; these seven baseline examples are not a model benchmark.

## Fictional policy assumptions

| Line | Covered event | Example excluded event | Limit/benefit INR | Deductible INR | STP claimed-amount ceiling INR |
| --- | --- | --- | ---: | ---: | ---: |
| Motor – Car | collision | mechanical_breakdown | 500,000 | 2,000 | 50,000 |
| Motor – Bike | collision | wear_and_tear | 100,000 | 500 | 15,000 |
| Health | hospitalization | cosmetic_procedure | 500,000 | 1,000 | 40,000 |
| Life | insured_death | policy_maturity | 1,000,000 | 0 | 0 (mandatory review) |
| Travel | baggage_loss | change_of_mind | 100,000 | 1,000 | 20,000 |
| Home/Property | fire_damage | gradual_deterioration | 2,000,000 | 5,000 | 75,000 |
| Personal Accident | accidental_fracture | illness | 50,000 | 0 | 50,000 |

Each policy requires a claim form plus one line-specific evidence document. Clause IDs such as `MTR-COV-01`, `MTR-DOC-01`, and `MTR-SET-01` identify exact rules. JSON is the authoritative policy reference for this milestone; this guide summarizes it.

Reimbursement estimate, after coverage and evidence verification:

`max(0, min(claimed amount, verified eligible expense, per-claim limit) - deductible)`

Life and Personal Accident use a fixed benefit after the covered event is verified. A mismatch between requested amount and fixed benefit requires review. Life always requires human review in this first academic policy design. Limits apply per claim; annual aggregates, waiting periods, depreciation, beneficiary validation, and complex medical rules are outside this simplified version. Do not extrapolate these terms to real insurance products.

## Routing contract (implemented in the deterministic baseline)

Apply the following precedence, using supported findings only:

1. Investigation for supported risk score >= 60.
2. Pending Documents for missing required evidence.
3. Human Review for unresolved conflicts, unknown policy/event, unverifiable evidence, confidence < 0.90, risk 20–59, value above the STP ceiling, or mandatory review.
4. Rejected only for a verified explicit exclusion, incident outside coverage dates, or documented unpaid premium under these fictional rules, with no unresolved evidence gap.
5. STP Approved only when every required check passes, confidence >= 0.90, and risk <= 19.

The policy must be valid on the incident date, not merely the submission date. Unknown events are review cases rather than implied exclusions. STP ceilings refer to the requested claim amount, not a reduced settlement estimate. Risk points sum across distinct supported indicators and are capped at 100. The [processing guide](processing_engine.md) defines baseline confidence and document consistency checks. Input demo claims contain no fabricated confidence scores or decisions; results are calculated per run.

## Source manifest and limitations

`knowledge_base/source_manifest.json` registers the local fixture sources and their SHA-256 digests. Approval here means eligible for this synthetic exercise; submitted document contents remain untrusted and unverified. Hashes detect changes against the manifest, not truth or authenticity. A person able to edit both a source and the manifest can change both; this is not a signed approval system.

The validator checks registered file integrity, key relationships, chronology, baseline document presence, and selected rule constraints. It is a baseline-fixture check, not a complete future upload validator or proof that arbitrary data contains no PII. Later negative evaluation cases intentionally violate business constraints and will need their own validation expectations.

## Reproduce and check

```bash
python scripts/generate_synthetic_data.py
python scripts/validate_data.py
python -m unittest discover -s tests -v
```

Generation is deterministic and safe to repeat with unchanged files. If a generated file has been edited, the generator stops before writing any files. To experiment without replacing existing data, generate into a new temporary folder using `--output-dir /tmp/insureflow-demo-v1`, then validate it with `--data-root /tmp/insureflow-demo-v1`.
