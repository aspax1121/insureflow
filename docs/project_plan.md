# Incremental project plan

## Scope

Insurance lines: Motor – Car, Motor – Bike, Health, Life, Travel, Home/Property, and Personal Accident.

The business problem is repeated manual work in policy validation, coverage checking, evidence verification, historical analysis, risk assessment, settlement calculation, and routing.

## Milestones

1. Foundation: separate repository, folders, governance requirements, offline setup check.
2. Business and data design: current/future process maps, data dictionary, synthetic records and explicit fictional insurance rules.
3. Processing baseline: Intake → Policy Validation → Coverage → Historical Claims → Fraud/Anomaly Detection → Settlement → Decision & Routing. Test evidence requirements and routing before adding LLMs.
4. User interfaces: claim submission/results and an operations dashboard with admin/knowledge-base tabs.
5. Controlled AI: approved-source retrieval, model adapters, confidence handling, evidence validation, audit logs, and prompt-injection tests. No initial LLM training.
6. Evaluation: approximately 30 identical synthetic cases, multiple models, governance testing, and documented expert feedback.
7. Demo: reproducible setup, limitations, results, and viva documentation.

## Routes

- STP Approved
- Human Review
- Investigation
- Rejected
- Pending Documents

Rejection must have affirmative policy/rule evidence. Lack of evidence alone must not justify rejection or approval. Define route precedence explicitly when implementing the rule engine.

## Dashboard requirements

Total claims; route percentages; processing time; total/average settlement; claims table and filters; insurance-line analytics; risk distribution; agent activity and audit trail; model performance and comparison; governance monitoring; knowledge-base status; historical analysis.

External source access counts must come from recorded tool activity, not a decorative hardcoded zero.

## Evaluation requirements

Cases must include valid claims, missing documents, expired policies, exclusions, duplicates, high values, suspicious patterns, conflicting information, low confidence, and edge cases.

Compare decision accuracy, evidence adherence, hallucination rate, rule adherence, false approvals/rejections, escalation accuracy, latency, and cost. Keep expected outcomes separate from model inputs. Label deterministic baseline results separately from actual model runs; never invent model scores or expert validation.
