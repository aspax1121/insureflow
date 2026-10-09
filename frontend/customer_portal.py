"""Customer-facing synthetic claim entry, evidence upload and status tracking."""

from datetime import date
from uuid import uuid4

import streamlit as st


def render_customer(api, show_result):
    st.title('Customer Portal')
    st.caption('Submit a synthetic insurance claim and follow its processing result.')
    create_tab, tracking_tab = st.tabs(['New claim & documents', 'Track my demo claims'])
    with create_tab:
        st.info('Academic demonstration only. Use fictitious records. Business date: 1 October 2026.')
        active = st.session_state.get('active_submission')
        if not active:
            policies = api('/policies')
            line = st.selectbox('Insurance type', list(dict.fromkeys(p['insurance_line'] for p in policies)))
            policy = st.selectbox('Policy number', [p for p in policies if p['insurance_line'] == line],
                                  format_func=lambda p: p['policy_id'])
            rule = policy['rule']
            st.caption(f"Synthetic customer: {policy['customer_id']}")
            st.session_state.setdefault('submission_request_id', str(uuid4()))
            st.session_state.setdefault('incident_reference', 'INC-' + uuid4().hex[:12].upper())
            with st.form('new_claim_form'):
                incident_id = st.text_input('Incident reference', value=st.session_state['incident_reference'],
                                            help='Use the same reference for the same incident; a repeated incident may require investigation.')
                incident_date = st.date_input('Incident date', value=date(2026, 9, 20), max_value=date(2026, 10, 1))
                event = st.selectbox('Incident / claim type', rule['covered_events'] + rule['excluded_events'] + ['other_event'],
                                     format_func=lambda x: x.replace('_', ' ').title())
                default_amount = rule['fixed_benefit_inr'] if rule['settlement_mode'] == 'fixed_benefit' else rule['stp_claim_ceiling_inr'] // 2
                amount = st.number_input('Claimed amount (INR)', min_value=1, max_value=100000000, value=default_amount, step=500)
                confirmed = st.checkbox('I confirm this claim and its documents are entirely synthetic.')
                create = st.form_submit_button('Save claim and continue to documents', type='primary')
            if create:
                if not confirmed:
                    st.error('Confirm synthetic data before submitting.')
                else:
                    claim = api('/submissions', 'POST', {
                        'request_id': st.session_state['submission_request_id'], 'policy_id': policy['policy_id'],
                        'insurance_line': line, 'incident_id': incident_id, 'incident_date': incident_date.isoformat(),
                        'event_type': event, 'claimed_amount_inr': amount, 'synthetic_confirmed': True})
                    st.session_state['active_submission'] = claim['claim_id']
                    st.rerun()
        else:
            st.success(f'Claim saved: {active}')
            _documents(api, show_result, active, 'new')
            if st.button('Start another synthetic claim'):
                for key in ('active_submission', 'submission_request_id', 'incident_reference'):
                    st.session_state.pop(key, None)
                st.rerun()
    with tracking_tab:
        submitted = [c for c in api('/claims') if c['claim_id'].startswith('CLM-NEW-')]
        st.caption('Shared local demo: this list shows all synthetic customer submissions. Separate customer accounts are not implemented.')
        if not submitted:
            st.info('Your saved claims will appear here.')
        else:
            claim = st.selectbox('Claim to track', submitted, format_func=lambda c: f"{c['claim_id']} · {c['insurance_line']}")
            st.button('Refresh claim status')
            _documents(api, show_result, claim['claim_id'], 'track')


def _documents(api, show_result, claim_id, prefix):
    detail = api('/submissions/' + claim_id)
    claim = detail['claim']
    st.write(f"**{claim['insurance_line']}** · Policy **{claim['policy_id']}** · Requested **₹{claim['claimed_amount_inr']:,}**")
    with st.expander('Claim details'):
        st.json(claim)
    st.subheader('Supporting documents')
    st.caption('Plain UTF-8 .txt files only, up to 16 KB each. The templates below use the supported academic format. PDF/OCR support is not included.')
    mode = st.radio('Evidence source', ['Upload synthetic files', 'Use generated demo documents', 'Submit without documents'],
                    key=f'{prefix}-mode-{claim_id}')
    documents = []
    for template in detail['templates']:
        kind = template['document_type']
        with st.expander(kind.replace('_', ' ').title()):
            st.download_button('Download synthetic template', template['text'], file_name=kind + '.txt',
                               mime='text/plain', key=f'{prefix}-template-{claim_id}-{kind}')
            if mode == 'Upload synthetic files':
                upload = st.file_uploader('Attach ' + kind.replace('_', ' '), type=['txt'],
                                          key=f'{prefix}-upload-{claim_id}-{kind}')
                if upload:
                    if upload.size > 16000:
                        st.error('This file exceeds the 16 KB limit.')
                        st.stop()
                    try:
                        text = upload.getvalue().decode('utf-8')
                    except UnicodeError:
                        st.error('Please provide a UTF-8 text file.')
                        st.stop()
                    documents.append({'document_type': kind, 'text': text})
            elif mode == 'Use generated demo documents':
                st.code(template['text'], language=None)
                documents.append({'document_type': kind, 'text': template['text']})
    if mode == 'Use generated demo documents':
        st.warning('These documents are generated from your entered details for testing. They are not independent proof of an incident.')
    st.caption('Each run uses only the documents selected above. To add evidence to a pending claim, attach the complete document set and process again. Previous runs remain in the audit history.')
    confirmed = st.checkbox('All attached evidence is synthetic.', key=f'{prefix}-confirm-{claim_id}')
    if st.button('Submit documents & run seven agents', type='primary', key=f'{prefix}-process-{claim_id}', disabled=not confirmed):
        with st.spinner('Running intake → policy → coverage → history → risk → settlement → routing…'):
            api('/submissions/' + claim_id + '/process', 'POST', {
                'documents': documents, 'synthetic_confirmed': True,
                'evidence_mode': {'Upload synthetic files': 'uploaded', 'Use generated demo documents': 'generated_demo',
                                  'Submit without documents': 'none'}[mode]})
        st.rerun()
    if detail['result']:
        st.divider()
        show_result(detail['result'], key_prefix=prefix)
    else:
        st.info('Awaiting submission: add evidence or submit without documents to see how the agents route your claim.')
