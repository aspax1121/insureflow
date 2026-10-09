# Run InsureFlow in your browser

The local Streamlit frontend calls the FastAPI backend; the backend runs the existing deterministic engine. Both listen on loopback only. No paid hosting, LLM credentials or external claims evidence is required. Downloading development packages during setup needs internet access; claim processing uses local sources.

## Install once

In the project terminal:

```bash
cd "/Users/anshuman/AIB Insuance Project/insureflow"
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If setting up a fresh copy, first create the environment with `python3 -m venv .venv`. This dependency set was tested with Python 3.14.2 on this Mac. Other Python versions may need a compatible environment rather than changing this existing project environment blindly.

## Terminal 1: backend

```bash
cd "/Users/anshuman/AIB Insuance Project/insureflow"
source .venv/bin/activate
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Open [API documentation](http://localhost:8000/docs). `/health` reports whether the server responds. It does not certify all evidence files; source integrity is checked when evidence is used and on the knowledge-base screen.

## Terminal 2: frontend

Open a second terminal using VS Code's **Terminal → New Terminal**:

```bash
cd "/Users/anshuman/AIB Insuance Project/insureflow"
source .venv/bin/activate
python -m streamlit run frontend/app.py
```

Open [InsureFlow](http://localhost:8501). Keep both terminals running. Stop each service with **Ctrl+C** in its terminal. If these ports already have the services running, use the existing browser links rather than launching duplicate servers. Do not terminate unrelated processes to free a port.

## Check the two interfaces

Open [Customer Portal](http://localhost:8501/?portal=customer) and [Management Portal](http://localhost:8501/?portal=management) in two tabs. In Customer Portal, save a synthetic claim, attach synthetic text documents (or explicitly choose generated demo documents), and run the seven stages. In Management Portal, click **Refresh dashboard** to see the new result and its audit.

See [the full portal walkthrough](portal_demo.md) for missing-document recovery, tracking, sample scenarios, and storage details. Original sample processing remains available through **Process all samples** in Management Portal.

Customer submissions persist in SQLite; results and per-run evidence snapshots persist under `runtime/`. Route metrics use the latest result per processed claim, so repeat runs do not inflate totals. Drafts awaiting document submission appear separately. Estimates are not paid settlements. Model comparisons and human approval actions are not implemented yet.

There is no user authentication in this local demo. Both servers bind to 127.0.0.1; this setup is intended for the local laptop rather than public deployment. No CORS relaxation is needed because Streamlit's Python process calls the API. Streamlit usage telemetry is disabled in `.streamlit/config.toml`.

## Tests and troubleshooting

```bash
python -m unittest discover -s tests -v
python scripts/validate_data.py
python -m pip check
```

- **Backend unavailable:** start Terminal 1, then refresh the frontend.
- **Module not found:** activate `.venv` and install `requirements.txt`.
- **Port already in use:** first check the existing browser link; a previous server may still be running.
- **Source integrity error:** review the changed synthetic file. Do not bypass the manifest check merely to force approval.
- **Unreadable report counter:** inspect the relevant local JSON under `runtime/runs/`; the dashboard excludes unreadable reports and reports their count.

Audit files persist in `runtime/runs/`, which is Git-ignored. Original synthetic files are read-only during processing. No existing project outside InsureFlow is modified.

Framework references: [FastAPI first steps](https://fastapi.tiangolo.com/tutorial/first-steps/) and [Streamlit basic concepts](https://docs.streamlit.io/get-started/fundamentals/main-concepts).
