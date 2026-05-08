"""
compliance_panel.py — Streamlit Compliance Dashboard panel.

Displays the structured compliance report from the last query result:
  - Traffic-light status indicator
  - Applicable rules tree
  - Gap list with severity badges
  - Remedial steps
"""

import streamlit as st
from typing import Optional


def render_compliance_panel(result: Optional[dict]):
    st.title("✅ Compliance Dashboard")
    st.caption("Structured compliance analysis for the last submitted query.")
    st.divider()

    if not result:
        st.info("No query result yet. Run a query in the Query Console first.")
        return

    status = result.get("compliance_status", "UNKNOWN")
    gaps = result.get("compliance_gaps", [])
    rules = result.get("applicable_rules", [])

    # Traffic-light status
    status_config = {
        "COMPLIANT": ("🟢", "green", "All applicable rules satisfied."),
        "NON-COMPLIANT": ("🔴", "red", "Critical compliance gaps detected. Do NOT proceed without remediation."),
        "REVIEW REQUIRED": ("🟡", "orange", "Some gaps found. Review and resolve before proceeding."),
        "INSUFFICIENT_BASIS": ("⚫", "grey", "Insufficient policy documents found to make a compliance determination."),
    }
    emoji, color, message = status_config.get(status, ("❓", "grey", "Unknown status."))

    st.markdown(
        f"""
        <div style="background: #1a1a2e; border-left: 6px solid {color}; padding: 16px; border-radius: 4px;">
            <h2 style="color: {color}; margin: 0">{emoji} {status}</h2>
            <p style="color: #ccc; margin: 4px 0 0 0">{message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # Two columns
    col_rules, col_gaps = st.columns(2)

    with col_rules:
        st.subheader("📋 Applicable Rules")
        if rules:
            for rule in rules:
                st.markdown(f"- `{rule}`")
        else:
            st.caption("No specific rules mapped.")

    with col_gaps:
        st.subheader("🚨 Compliance Gaps")
        if gaps:
            critical = [g for g in gaps if g.get("severity") == "CRITICAL"]
            warnings = [g for g in gaps if g.get("severity") == "WARNING"]
            info = [g for g in gaps if g.get("severity") == "INFO"]

            for gap in critical:
                st.error(
                    f"🔴 **CRITICAL** — {gap.get('rule_id', '')}\n\n"
                    f"{gap.get('description', '')}"
                )
            for gap in warnings:
                st.warning(
                    f"🟡 **WARNING** — {gap.get('rule_id', '')}\n\n"
                    f"{gap.get('description', '')}"
                )
            for gap in info:
                st.info(
                    f"🔵 **INFO** — {gap.get('rule_id', '')}\n\n"
                    f"{gap.get('description', '')}"
                )
        else:
            st.success("✅ No compliance gaps detected.")

    # Remedial steps
    remedial = [g.get("remediation", "") for g in gaps if g.get("remediation")]
    if remedial:
        st.divider()
        st.subheader("🔧 Remedial Steps")
        for i, step in enumerate(remedial, 1):
            st.markdown(f"**{i}.** {step}")

    # Audit info
    audit_id = result.get("audit_id", "")
    if audit_id:
        st.divider()
        st.caption(f"🔐 Audit ID: `{audit_id}` | Confidence: `{result.get('confidence_score', 0):.2f}`")