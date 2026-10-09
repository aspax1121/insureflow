# Governance requirements

Status: partially implemented in the deterministic baseline. Local source allowlisting, hash checks, strict synthetic-document parsing, escalation rules, and per-run audit reports are implemented and tested. See [the engine guide](processing_engine.md). Real upload controls, model integration, calibrated confidence, dashboard monitoring and production-grade protection remain future work.

## Synthetic data only

Use fictitious customers, policies, claims, and documents. Example identifiers: CUST-000001, POL-MTR-000001, CLM-000001. Do not submit real personal information, insurance records, passwords, API keys, or confidential company documents as project data. Minimize fields collected even in synthetic examples.

## Closed-world evidence

Agents may use only approved synthetic policy records, historical claims, policy documents, internal rules, and application-submitted synthetic claim documents. No web search, scraping, arbitrary URLs, or external retrieval tools may provide claim evidence.

Future hosted model use requires a deliberate provider/configuration choice and synthetic, minimized inputs. A model response is not itself an authorized evidence source.

## No Evidence → No Decision

Important decisions must identify authorized source records/documents, relevant policy clauses/rules, reasons, and confidence. Missing or conflicting evidence must trigger a suitable non-final route. Confidence must not override missing mandatory evidence or policy constraints.

Only low-risk, evidence-complete claims within defined limits may qualify for autonomous STP. High-value, ambiguous, low-confidence, or suspicious cases require human review/investigation. Settlement estimates are simulated; this project makes no real payments.

## Safeguards to implement

- Source allowlist and restricted local retrieval.
- Document provenance and evidence references validated against authorized records.
- Submitted document text treated as untrusted data, never agent instructions.
- Upload file-type/size checks and safe local storage.
- Explicit route rules, confidence thresholds, and human escalation.
- Agent action logs, rule/model versions, decisions, and timestamps.
- Tests for missing evidence, prompt injection, unauthorized retrieval, and unsupported approvals.
- Dashboard metrics computed from recorded events.

The anomaly stage reports risk indicators and supporting evidence. It must not independently accuse a claimant of fraud.
