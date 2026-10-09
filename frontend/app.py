"""Two local views backed exclusively by the InsureFlow HTTP API."""

import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener, Request

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frontend.customer_portal import render_customer

import os

API = os.getenv(
    "INSUREFLOW_API_URL",
    "http://127.0.0.1:8000"
).rstrip("/")
st.set_page_config(page_title='InsureFlow | AegisSure', page_icon='🛡️', layout='wide')
st.markdown('''<style>
.block-container {padding-top:2rem; max-width:1450px;}
[data-testid="stMetric"] {background:#f0f5fa;border:1px solid #dce5ef;border-radius:10px;padding:16px;}
[data-testid="stMetricLabel"], [data-testid="stMetricValue"] {color:#16324f;}
</style>''', unsafe_allow_html=True)


def api(path, method='GET', payload=None):
    # Loopback only; ignore system proxies for local requests.
    data = json.dumps(payload).encode() if payload is not None else (b'' if method == 'POST' else None)
    request = Request(API + path, method=method, data=data, headers={'Content-Type': 'application/json'})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        try:
            message = json.load(error).get('detail', str(error))
        except ValueError:
            message = str(error)
        st.error(f'API request failed: {message}')
    except (URLError, TimeoutError, ValueError) as error:
        st.error('Backend unavailable. Start it in another terminal:')
        st.code('python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000')
    st.stop()


def money(value):
    return 'Withheld' if value is None else f'₹{value:,.0f}'


def show_result(result, key_prefix='result'):
    st.subheader(f"{result['claim_id']} · {result['route']}")
    st.write('; '.join(result['reasons']))
    if result.get('evidence_mode') == 'generated_demo':
        st.caption('This run used generated synthetic demo documents, not independent incident evidence.')
    cols = st.columns(4)
    cols[0].metric('Estimated settlement', money(result['estimated_settlement_inr']))
    cols[1].metric('Risk score / 100', result['risk_score'] if result['risk_score'] is not None else 'Unknown')
    cols[2].metric('Evidence confidence', f"{result['confidence']:.0%}")
    cols[3].metric('Processing time', f"{result['processing_time_ms']:.1f} ms")
    st.caption('Confidence is a binary synthetic-evidence consistency score, not a model probability. Estimates are not payments.')
    st.write(f"Policy: **{result['policy_validation']}** · Coverage: **{result['coverage_status']}** · Documents complete: **{result['document_completeness']}**")
    if result['escalation_reason']:
        st.warning(result['escalation_reason'])
    for stage in result['agent_audit_trail']:
        with st.expander(f"{stage['stage']} — {stage['status']}"):
            st.write(stage['reason'])
            st.json(stage)
    st.download_button('Download full audit report', json.dumps(result, indent=2, ensure_ascii=False),
                       file_name=f"{result['run_id']}.json", mime='application/json', key=f"{key_prefix}-download-{result['run_id']}")


st.sidebar.title('🛡️ INSUREFLOW')
st.sidebar.caption('AEGISSURE INSURANCE LTD.')
view = st.sidebar.radio('Portal', ['Customer Portal', 'Management Portal'],
                        index=1 if st.query_params.get('portal') == 'management' else 0)
st.query_params['portal'] = 'management' if view == 'Management Portal' else 'customer'
st.sidebar.divider()
st.sidebar.info('Academic demo · Synthetic data only\n\nNo Evidence → No Decision')
st.sidebar.caption('Fixed business date: 1 October 2026\n\nRules baseline · No LLM connected')
st.sidebar.link_button('Backend API documentation', API + '/docs')
api('/health')

if view == 'Customer Portal':
    render_customer(api, show_result)
else:
    st.title('Management Portal')
    st.caption('Customer submissions, processing results and evidence audit. Use Refresh dashboard to load new claims from the Customer Portal.')
    controls = st.columns([1, 1, 4])
    if controls[0].button('Process all samples', type='primary'):
        with st.spinner('Processing seven synthetic claims…'):
            api('/claims/process-all', 'POST')
        st.success('Sample claims processed. Dashboard refreshed.')
    controls[1].button('Refresh dashboard')
    dashboard = api('/dashboard')
    cols = st.columns(4)
    cols[0].metric('Processed claims', dashboard['processed_claims'])
    cols[1].metric('STP rate', f"{dashboard['route_percentages']['STP Approved']}%")
    cols[2].metric('Avg processing', f"{dashboard['average_processing_ms']:.1f} ms")
    cols[3].metric('Total estimated settlement', money(dashboard['total_estimated_settlement_inr']))
    cols = st.columns(5)
    for col, route in zip(cols, ['Human Review', 'Investigation', 'Rejected', 'Pending Documents']):
        col.metric(route, f"{dashboard['route_percentages'][route]}%")
    cols[4].metric('Avg estimate', money(dashboard['average_estimated_settlement_inr']))
    st.caption(f"{dashboard['registered_claims']} registered claims · {dashboard['total_runs']} saved runs · Estimates include reviewed claims, not paid settlements. Average estimate uses {dashboard['estimate_count']} non-null estimates.")
    operations, audit, governance, knowledge, models = st.tabs(['Claims & analytics', 'Agent activity & audit', 'Governance', 'Knowledge base & history', 'Model comparison'])
    frame = pd.DataFrame(dashboard['claims'])
    if dashboard['awaiting_submission']:
        st.subheader('Saved customer claims awaiting document submission')
        st.dataframe(dashboard['awaiting_submission'], hide_index=True, width='stretch')
    with operations:
        if frame.empty:
            st.info('Submit a claim from the Customer Portal, or choose Process all samples to try the original fixtures.')
        else:
            columns = st.columns(2)
            selected_lines = columns[0].multiselect('Filter insurance lines', sorted(frame.insurance_line.unique()))
            selected_routes = columns[1].multiselect('Filter routes', sorted(frame.route.unique()))
            filtered = frame
            if selected_lines:
                filtered = filtered[filtered.insurance_line.isin(selected_lines)]
            if selected_routes:
                filtered = filtered[filtered.route.isin(selected_routes)]
            st.dataframe(filtered, hide_index=True, width='stretch')
            st.caption('Filters affect this table and charts; summary metrics above remain portfolio-wide.')
            columns = st.columns(2)
            columns[0].subheader('Claims by insurance line')
            columns[0].bar_chart(filtered.groupby('insurance_line').size())
            columns[1].subheader('Risk distribution')
            risk = filtered.risk_score.apply(lambda value: 'Unknown' if pd.isna(value) else ('Low (0–19)' if value <= 19 else 'Review (20–59)' if value < 60 else 'High (60+)'))
            columns[1].bar_chart(risk.value_counts())
    with audit:
        if dashboard['agent_activity']:
            activity = pd.DataFrame(dashboard['agent_activity'])
            st.dataframe(activity[['claim_id', 'stage', 'status', 'confidence', 'duration_ms']], hide_index=True, width='stretch')
            selected = st.selectbox('Inspect claim audit', dashboard['claims'], format_func=lambda row: f"{row['claim_id']} · {row['route']}")
            show_result(api('/runs/' + selected['run_id']))
        else:
            st.info('No processing activity yet.')
    with governance:
        cols = st.columns(3)
        cols[0].metric('External sources accessed', dashboard['external_sources_accessed'])
        cols[1].metric('Blocked processing runs', dashboard['blocked_runs'])
        cols[2].metric('Unreadable audit reports', dashboard['unreadable_reports'])
        st.write('Source allowlist · File integrity checks · Strict synthetic-document parser · Human escalation · Per-stage evidence references')
        st.caption('These counters cover saved engine runs. They are not operating-system network monitoring. Audit files and the source manifest are local development artifacts, not tamper-proof records.')
    kb = api('/knowledge-base')
    with knowledge:
        st.subheader('Approved local sources')
        st.dataframe(kb['sources'], hide_index=True, width='stretch')
        with st.expander('Fictional policy rules'):
            st.json(kb['rules'])
        st.subheader('Synthetic historical claims')
        history = pd.DataFrame(kb['history'])
        st.dataframe(history, hide_index=True, width='stretch')
        if not history.empty:
            st.bar_chart(history.groupby('policy_id')['settled_amount_inr'].sum())
    with models:
        st.info('Model comparison has not been run. This application currently uses deterministic-v1 only.')
        st.write('Later evaluation: decision accuracy, evidence adherence, hallucination rate, rule adherence, false approvals/rejections, escalation accuracy, latency and cost.')
        st.caption('No model scores or expert endorsements are fabricated.')
