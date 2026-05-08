"""
admin_panel.py — Admin Panel: document ingestion, system health, audit log viewer.
All logged-in users can ingest documents in this build.
"""

import streamlit as st


def render_admin_panel(client):
    st.title("⚙️ Admin Panel")
    st.caption("Upload documents, monitor the pipeline, and review audit logs.")
    st.divider()

    tab_ingest, tab_health, tab_audit = st.tabs(
        ["📥 Ingest Document", "🩺 System Health", "🔐 Audit Log"]
    )

    # ------------------------------------------------------------------
    # Tab 1: Ingest
    # ------------------------------------------------------------------
    with tab_ingest:
        st.subheader("Upload Policy Document")
        st.info(
            "**Supported formats:** PDF, DOCX, TXT\n\n"
            "Upload a document and the system will automatically:\n"
            "1. Extract text  2. Split into chunks  "
            "3. Generate embeddings  4. Store in vector index"
        )

        uploaded_file = st.file_uploader(
            "Select document", type=["pdf", "docx", "txt"], help="Max 50 MB"
        )

        col1, col2 = st.columns(2)
        with col1:
            doc_type = st.selectbox(
                "Document Type",
                ["auto", "procurement_policy", "gfr_rules", "audit_report",
                 "tender_document", "ministry_circular"],
            )
            classification = st.selectbox(
                "Classification Level",
                ["UNCLASSIFIED", "RESTRICTED", "CONFIDENTIAL"],
            )
        with col2:
            issuing_authority = st.text_input("Issuing Authority", placeholder="e.g. Ministry of Defence")
            effective_date = st.text_input("Effective Date", placeholder="e.g. 2020-01-01")

        if uploaded_file:
            st.write(f"**Selected:** `{uploaded_file.name}` ({uploaded_file.size/1024:.1f} KB)")

        if st.button("🚀 Upload & Ingest", type="primary", disabled=(uploaded_file is None)):
            with st.spinner(f"Processing `{uploaded_file.name}`..."):
                try:
                    result = client.ingest(
                        file_bytes=uploaded_file.read(),
                        filename=uploaded_file.name,
                        metadata={
                            "doc_type": doc_type,
                            "classification_level": classification,
                            "issuing_authority": issuing_authority,
                            "effective_date": effective_date,
                        },
                    )
                    if result.get("status") == "complete":
                        st.success(result.get("message", "✅ Ingested successfully!"))
                        st.metric("Chunks Created", result.get("chunks_created", "N/A"))
                        st.caption(f"Doc ID: `{result.get('doc_id', 'N/A')}`")
                    else:
                        st.warning(result.get("message", "Queued."))
                except Exception as e:
                    st.error(f"❌ Ingest failed: {e}")

    # ------------------------------------------------------------------
    # Tab 2: Health
    # ------------------------------------------------------------------
    with tab_health:
        st.subheader("System Health")
        _show_health(client)
        if st.button("🔄 Refresh"):
            st.rerun()

    # ------------------------------------------------------------------
    # Tab 3: Audit
    # ------------------------------------------------------------------
    with tab_audit:
        st.subheader("Audit Log Lookup")
        audit_id_input = st.text_input("Audit ID")
        if audit_id_input and st.button("Fetch Entry"):
            entry = client.get_audit_entry(audit_id_input)
            st.json(entry) if entry else st.warning("Not found.")

        st.divider()
        if st.button("🔗 Verify Hash Chain"):
            with st.spinner("Verifying..."):
                result = client.verify_audit_chain()
            if result.get("chain_intact"):
                st.success(result.get("message", "Chain intact"))
            else:
                st.error(result.get("message", "Integrity failure"))


def _show_health(client):
    try:
        h = client.get_health()
        st.success("🟢 HEALTHY") if h.get("status") == "healthy" else st.warning(f"🟡 {h.get('status','?').upper()}")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Chunks Indexed", h.get("total_chunks_indexed", "N/A"))
            st.metric("Embedding Model", "✅" if h.get("embedding_model_ready") else "❌")
        with col2:
            st.metric("FAISS Index", "✅" if h.get("faiss_index_loaded") else "❌")
            st.metric("LLM Backend", "✅" if h.get("llm_service_ready") else "⚠️ context-only")
        if not h.get("llm_service_ready"):
            st.info("💡 No LLM configured. Set `LLM_BACKEND=ollama` or `LLM_BACKEND=openai` for synthesised answers.")
    except Exception as e:
        st.error(f"❌ API unreachable: {e}")
        st.info("Make sure `python dev_server.py` is running in another terminal.")