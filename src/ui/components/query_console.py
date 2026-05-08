"""
query_console.py — Streamlit Query Console panel.

Features:
  - Question input with doc-type filter dropdown
  - Answer display with inline citation chips
  - Source chunk expander panel
  - Confidence indicator (red/amber/green)
  - CoT indicator
"""

from __future__ import annotations
import streamlit as st
from typing import Optional


DOC_TYPE_OPTIONS = [
    "auto",
    "procurement_policy",
    "gfr_rules",
    "audit_report",
    "tender_document",
    "ministry_circular",
]


def render_query_console(client):
    st.title("🔍 Query Console")
    st.caption("Ask any procurement or policy question. Every answer traces to a source clause.")
    st.divider()

    # Input row
    col_q, col_filter = st.columns([4, 1])
    with col_q:
        question = st.text_area(
            "Enter your query",
            placeholder="e.g. What is the financial limit for procurement under Fast Track Procedure?",
            height=80,
            key="query_input",
        )
    with col_filter:
        doc_type_filter = st.selectbox("Doc Type", DOC_TYPE_OPTIONS, key="doc_type_filter")
        top_k = st.slider("Max Sources", 1, 10, 5, key="top_k")

    col_btn, col_clear = st.columns([1, 6])
    with col_btn:
        submit = st.button("🔎 Search", type="primary", use_container_width=True)
    with col_clear:
        if st.button("Clear", use_container_width=False):
            st.session_state.last_result = None
            st.rerun()

    if submit and question.strip():
        filters = {"doc_type": doc_type_filter} if doc_type_filter != "auto" else None
        with st.spinner("Retrieving and reasoning over policy documents..."):
            try:
                result = client.query(
                    question=question.strip(),
                    filters=filters,
                    top_k=top_k,
                )
                st.session_state.last_result = result
            except Exception as e:
                st.error(f"❌ Query failed: {e}")
                return

    result = st.session_state.get("last_result")
    if not result:
        st.info("Enter a query above to get started.")
        return

    st.divider()
    _render_result(result)


def _render_result(result: dict):
    # Confidence banner
    conf_score = result.get("confidence_score", 0)
    conf_level = result.get("confidence_level", "LOW")
    conf_color = {"HIGH": "green", "MEDIUM": "orange", "LOW": "red"}.get(conf_level, "red")
    conf_emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}.get(conf_level, "🔴")

    st.markdown(
        f"**Confidence:** {conf_emoji} `{conf_level}` — score: `{conf_score:.2f}` &nbsp;&nbsp; "
        f"**Compliance:** `{result.get('compliance_status', 'N/A')}` &nbsp;&nbsp; "
        f"**CoT Applied:** `{'Yes' if result.get('cot_applied') else 'No'}`",
        unsafe_allow_html=True,
    )

    if conf_level == "LOW":
        st.error("⚠️ LOW CONFIDENCE — Verify against original policy documents before acting.")
    elif conf_level == "MEDIUM":
        st.warning("⚡ MEDIUM CONFIDENCE — Cross-check key claims against source documents.")

    # Answer
    st.subheader("Answer")
    answer_text = result.get("annotated_answer") or result.get("answer", "No answer generated.")
    st.markdown(answer_text)

    # Compliance gaps (if any)
    gaps = result.get("compliance_gaps", [])
    if gaps:
        st.subheader("⚠️ Compliance Gaps Detected")
        for gap in gaps:
            sev = gap.get("severity", "WARNING")
            icon = "🔴" if sev == "CRITICAL" else "🟡"
            with st.expander(f"{icon} [{sev}] {gap.get('rule_id', '')} — {gap.get('description', '')[:80]}"):
                st.write(gap.get("description", ""))
                st.info(f"**Remediation:** {gap.get('remediation', '')}")

    # Source citations
    citations = result.get("citations", [])
    if citations:
        st.subheader(f"📚 Source Passages ({len(citations)})")
        for cit in citations:
            label = cit.get("label", "SOURCE")
            verified = "✓" in (cit.get("label", "") + result.get("annotated_answer", ""))
            border_color = "#00c851" if verified else "#ff4444"
            with st.expander(
                f"[{label}] {cit.get('doc_id', '')} | {cit.get('section', '')} | "
                f"Score: {cit.get('score', 0):.3f}"
            ):
                st.markdown(
                    f"""
                    <div style="border-left: 3px solid {border_color}; padding-left: 10px;">
                    {cit.get('text_snippet', '')}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"Doc: {cit.get('doc_id')} | "
                    f"Section: {cit.get('section')} | "
                    f"Page: {cit.get('page', 'N/A')} | "
                    f"Chunk ID: {cit.get('chunk_id')}"
                )

    # Audit ID
    audit_id = result.get("audit_id", "")
    if audit_id:
        st.caption(f"🔐 Audit ID: `{audit_id}`")