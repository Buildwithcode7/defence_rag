"""
doc_viewer.py — Document Viewer panel (browse ingested documents).
"""

import streamlit as st


def render_doc_viewer(client):
    st.title("📄 Document Viewer")
    st.caption("Browse ingested documents, view chunk-level annotations, and flag problematic ingestions.")
    st.divider()

    st.info(
        "Document browser requires a metadata API endpoint. "
        "Connect to /api/v1/documents (to be added in v1.1) to list and browse chunks. "
        "For now, use the Admin Panel to check ingestion status."
    )

    # Placeholder UI
    st.subheader("Search Documents")
    search = st.text_input("Search by document name or ID")
    if search:
        st.warning(f"Document search for '{search}' — endpoint pending.")

    st.subheader("Recently Ingested")
    st.table(
        {
            "Document": ["DPP_2020.pdf", "GFR_2017.pdf", "MoD_Circular_2023.pdf"],
            "Type": ["procurement_policy", "gfr_rules", "ministry_circular"],
            "Status": ["indexed", "indexed", "indexed"],
            "Chunks": [847, 1203, 312],
        }
    )