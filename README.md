# INSUREFLOW

A Governed Agentic AI Framework for Straight-Through Multi-Insurance Claims Processing.

An MBA academic project for the fictional **AegisSure Insurance Ltd.** All records and documents must be synthetic.

## Current milestone: customer and management portals

The repository contains reproducible synthetic data for all seven insurance lines and a seven-stage Python processing engine with evidence checks, routing, settlement estimates, and local audit reports. The Customer Portal accepts new synthetic claims and text documents; the Management Portal displays their results and audits through the shared FastAPI backend. SQLite preserves customer submissions. The engine is deterministic; LLM agents and RAG are not implemented. No LLM is trained or called.

## Open in your browser

Activate `.venv`, then install `python -m pip install -r requirements.txt`.

In terminal 1:

```bash
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

In terminal 2, from the project directory with `.venv` activated:

```bash
python -m streamlit run frontend/app.py
```

Open [Customer Portal](http://localhost:8501/?portal=customer), [Management Portal](http://localhost:8501/?portal=management), and [backend API docs](http://localhost:8000/docs). See [the portal walkthrough](docs/portal_demo.md) and [local browser setup](docs/local_browser.md). Uploads currently support the synthetic UTF-8 text template format only.

## Process a claim

With the virtual environment activated:

```bash
python scripts/process_claim.py --claim-id CLM-000001
python scripts/process_claim.py --all
```

The first claim should receive simulated STP approval with an INR 23,000 estimate. Life requires Human Review. Each run writes a separate report to `runtime/runs/`. See the [processing guide](docs/processing_engine.md) for expected results, evidence/confidence definitions, and limitations.

## Generate and validate synthetic data

With the virtual environment activated:

```bash
python scripts/generate_synthetic_data.py
python scripts/validate_data.py
python -m unittest discover -s tests -v
```

Generation refuses to overwrite edited fixtures. Read the [data dictionary and fictional policy assumptions](docs/data_dictionary.md) and [business process design](docs/process_design.md). All examples use a fixed demo date of 2026-10-01. Seven baseline claims are included; the later 30-case model benchmark is not implemented yet.

## Run the setup check

From this project folder, on macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python scripts/check_setup.py
```

The check uses only the Python standard library, verifies the project folders, and checks SQLite using an in-memory database. It makes no network requests and writes no insurance records. Every check should display `PASS` and the command should exit successfully.

## Proposed simple stack

Python, FastAPI for the backend, and Streamlit for the two user interfaces. Baseline records and audit reports use JSON; customer submissions persist in SQLite. Explicit Python orchestration and deterministic policy rules provide the baseline. Add controlled retrieval and interchangeable model adapters later. Consider n8n only if it adds demonstrable value. Browser dependencies are pinned in `requirements.txt`.

## Project layout

- `frontend/`: claim submission and management dashboard.
- `backend/`: application services and future API.
- `agents/`: seven evidence-based processing stages.
- `data/`: synthetic customers, policies, historical claims, claim documents, rules, and test cases.
- `knowledge_base/`: approved internal policy documents and procedures.
- `workflows/`: orchestration definitions.
- `evaluation/`: standardized model comparisons and results.
- `docs/`: business analysis, architecture, governance, and demo guidance.
- `tests/`: behavioral tests as functionality is introduced.
- `scripts/`: local development checks and future data generation.

## Business principle

**No Evidence → No Decision.** Low-risk, evidence-complete claims may qualify for STP. Missing evidence results in Pending Documents or Human Review; ambiguous, high-value, suspicious, or low-confidence claims require human attention. Risk indicators are not accusations of fraud.

See [the project plan](docs/project_plan.md) and [governance requirements](docs/governance.md).

## Next milestone

Define and test management review actions, then introduce controlled retrieval and interchangeable model adapters with a separate standardized evaluation set.
