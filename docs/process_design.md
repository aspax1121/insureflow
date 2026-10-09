# Business process redesign

This is an academic proposed process, not a measured study of an actual insurer. Expert validation and operational performance measurements are pending.

## Current process hypothesis

Submission → manual policy lookup → manual coverage interpretation → document checking → historical review → anomaly assessment → settlement calculation → supervisor routing.

Repeated handoffs may create queues, duplicate data entry, inconsistent interpretations, and weak evidence traceability. These are hypotheses to discuss with an insurance expert, not established findings about AegisSure or any real company.

## Proposed process

Submission → Intake → Policy Validation → Coverage → Historical Claims → Anomaly Detection → Settlement → Decision & Routing.

Each stage will produce structured findings with evidence references and rule IDs. The routing stage combines findings under explicit precedence rules. Low-risk complete claims can reach simulated STP approval. Missing evidence requests documents; uncertainty and high values require human review; supported risk indicators can trigger investigation. A rejection needs affirmative policy evidence.

| Stage | Business responsibility | Evidence |
| --- | --- | --- |
| Intake | Validate submission and document presence | Claim and document metadata |
| Policy Validation | Resolve policy, ownership, premium and incident-date validity | Policy and customer records |
| Coverage | Match covered events and explicit exclusions | Versioned coverage clauses |
| Historical Claims | Identify earlier related claims | Historical claim records and incident IDs |
| Anomaly Detection | Report supported indicators | Findings plus internal indicator rules |
| Settlement | Estimate reimbursement or fixed benefit | Verified claim evidence and settlement clauses |
| Decision & Routing | Apply gates and explain route | Findings, confidence, risk and routing rules |

## Measuring the redesign later

Use all processed claims as the denominator for route percentages and report the sample size. Keep pending claims visible. Define processing time from submission to initial routing; measure human queue time separately. Distinguish estimated, approved and historical paid settlements. Model benchmarking must use identical cases with separate expected outcomes and recorded latency/cost. No business benefit, model score or human expert endorsement is claimed in this milestone.
