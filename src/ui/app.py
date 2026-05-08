# from __future__ import annotations

# import sys
# from datetime import datetime
# from pathlib import Path

# import streamlit as st

# PROJECT_ROOT = Path(__file__).resolve().parents[2]
# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# from src.ui.utils.api_client import APIClient


# API_BASE_URL = "http://127.0.0.1:8000"
# DOC_TYPES = ["auto", "policy", "procurement_policy", "gfr_rules", "audit_report", "tender_document"]


# st.set_page_config(page_title="INICAI Defence Chat", page_icon="IN", layout="wide")


# def inject_theme() -> None:
#     st.markdown(
#         """
# <style>
# :root {
#     --bg: #071018;
#     --panel: rgba(11, 22, 32, 0.96);
#     --line: rgba(104, 214, 224, 0.28);
#     --text: #eaf7f8;
#     --muted: #91a9b4;
#     --cyan: #64d6e0;
#     --green: #78e08a;
# }

# .stApp {
#     background:
#         linear-gradient(90deg, rgba(100, 214, 224, 0.04) 1px, transparent 1px),
#         linear-gradient(rgba(100, 214, 224, 0.03) 1px, transparent 1px),
#         var(--bg);
#     background-size: 44px 44px;
#     color: var(--text);
# }

# .block-container {
#     max-width: 1200px;
#     padding: 1.2rem 1.5rem 2rem;
# }

# [data-testid="stSidebar"], [data-testid="collapsedControl"] {
#     display: none;
# }

# h1, h2, h3, p, label, span, div {
#     letter-spacing: 0;
# }

# .topbar {
#     display: flex;
#     align-items: center;
#     justify-content: space-between;
#     padding: 13px 16px;
#     margin-bottom: 16px;
#     border: 1px solid var(--line);
#     background: rgba(7, 16, 24, 0.94);
# }

# .brand {
#     display: flex;
#     align-items: center;
#     gap: 12px;
# }

# .brand-mark {
#     width: 38px;
#     height: 38px;
#     display: grid;
#     place-items: center;
#     border: 1px solid rgba(104, 214, 224, 0.58);
#     color: var(--cyan);
#     font-weight: 900;
#     background: rgba(100, 214, 224, 0.12);
# }

# .brand-title {
#     color: var(--text);
#     font-size: 18px;
#     line-height: 1.05;
#     font-weight: 900;
# }

# .brand-subtitle {
#     margin-top: 4px;
#     color: var(--muted);
#     font-size: 11px;
#     text-transform: uppercase;
# }

# .status-pill {
#     display: inline-flex;
#     align-items: center;
#     gap: 8px;
#     padding: 8px 11px;
#     border: 1px solid var(--line);
#     color: var(--green);
#     background: rgba(120, 224, 138, 0.08);
#     font-size: 12px;
#     font-weight: 800;
# }

# .dot {
#     width: 8px;
#     height: 8px;
#     border-radius: 99px;
#     background: currentColor;
#     box-shadow: 0 0 12px currentColor;
# }

# .panel {
#     border: 1px solid var(--line);
#     background: var(--panel);
#     padding: 16px;
# }

# .panel-title {
#     color: var(--muted);
#     font-size: 11px;
#     text-transform: uppercase;
#     font-weight: 900;
#     margin-bottom: 12px;
# }

# .metric-row {
#     display: grid;
#     grid-template-columns: 1fr auto;
#     gap: 12px;
#     padding: 9px 0;
#     border-bottom: 1px solid rgba(104, 214, 224, 0.12);
# }

# .metric-row:last-child {
#     border-bottom: 0;
# }

# .metric-label {
#     color: var(--muted);
#     font-size: 12px;
# }

# .metric-value {
#     color: var(--cyan);
#     font-size: 13px;
#     font-weight: 900;
# }

# .chat-shell {
#     min-height: 69vh;
#     border: 1px solid var(--line);
#     background: rgba(8, 18, 27, 0.82);
#     padding: 18px;
# }

# div[data-testid="stChatMessage"] {
#     background: transparent;
# }

# div[data-testid="stChatMessageContent"] {
#     border: 1px solid rgba(104, 214, 224, 0.18);
#     background: rgba(15, 29, 41, 0.92);
#     padding: 12px 14px;
#     border-radius: 6px;
#     line-height: 1.65;
# }

# div[data-testid="stFileUploader"] {
#     border: 1px dashed rgba(104, 214, 224, 0.38);
#     background: rgba(9, 19, 28, 0.66);
#     padding: 8px;
# }

# .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
#     background: rgba(10, 21, 31, 0.96) !important;
#     border: 1px solid rgba(104, 214, 224, 0.28) !important;
#     color: var(--text) !important;
#     border-radius: 4px !important;
# }

# .stButton > button {
#     border-radius: 4px;
#     border: 1px solid rgba(104, 214, 224, 0.45);
#     background: rgba(100, 214, 224, 0.16);
#     color: var(--text);
#     font-weight: 900;
# }

# button[kind="primary"] {
#     background: linear-gradient(135deg, #55cfd9, #78e08a) !important;
#     color: #061016 !important;
#     border: 0 !important;
# }
# </style>
#         """,
#         unsafe_allow_html=True,
#     )


# def init_state() -> None:
#     defaults = {
#         "logged_in": False,
#         "username": "",
#         "token": None,
#         "messages": [],
#         "doc_type": "auto",
#         "top_k": 5,
#         "last_ingest": None,
#     }
#     for key, value in defaults.items():
#         st.session_state.setdefault(key, value)


# def api_client() -> APIClient:
#     return APIClient(base_url=API_BASE_URL, token=st.session_state.token)


# def health() -> dict:
#     try:
#         return api_client().get_health() or {}
#     except Exception:
#         return {"status": "offline"}


# def total_indexed(h: dict) -> int:
#     return int(h.get("total_pages") or h.get("total_chunks_indexed") or h.get("total_documents") or 0)


# def render_topbar(h: dict) -> None:
#     status = str(h.get("status", "locked")).upper()
#     st.markdown(
#         f"""
# <div class="topbar">
#     <div class="brand">
#         <div class="brand-mark">IN</div>
#         <div>
#             <div class="brand-title">INICAI Defence Chat</div>
#             <div class="brand-subtitle">Direct question answering over uploaded documents</div>
#         </div>
#     </div>
#     <div class="status-pill"><span class="dot"></span>{status}</div>
# </div>
#         """,
#         unsafe_allow_html=True,
#     )


# def render_login() -> None:
#     render_topbar({"status": "locked"})
#     st.markdown("<div style='height: 8vh'></div>", unsafe_allow_html=True)
#     _, middle, _ = st.columns([1.25, 1, 1.25])
#     with middle:
#         st.markdown(
#             """
# <div class="panel">
#     <div class="brand">
#         <div class="brand-mark">IN</div>
#         <div>
#             <div class="brand-title">Enter Chat</div>
#             <div class="brand-subtitle">Temporary username and password</div>
#         </div>
#     </div>
# </div>
#             """,
#             unsafe_allow_html=True,
#         )
#         username = st.text_input("Username", placeholder="Enter username")
#         password = st.text_input("Password", type="password", placeholder="Enter password")
#         if st.button("Open Chat", type="primary", use_container_width=True):
#             if not username.strip() or not password.strip():
#                 st.error("Please enter username and password")
#                 return

#             # Temporary access: let the user in. If backend auth succeeds, keep the token too.
#             response = APIClient(base_url=API_BASE_URL).login(username.strip(), password)
#             st.session_state.token = response.get("access_token") if response else None
#             st.session_state.username = username.strip()
#             st.session_state.logged_in = True
#             st.session_state.messages = [
#                 {"role": "assistant", "content": "Ask your question. I will answer directly from the uploaded documents."}
#             ]
#             st.rerun()


# def render_controls(h: dict) -> None:
#     st.markdown('<div class="panel-title">Upload</div>', unsafe_allow_html=True)
#     uploaded = st.file_uploader("Document", type=["pdf", "docx", "txt"], label_visibility="collapsed")
#     upload_type = st.selectbox("Document type", DOC_TYPES, index=DOC_TYPES.index("auto"))

#     if st.button("Index Document", type="primary", use_container_width=True, disabled=uploaded is None):
#         try:
#             with st.spinner("Indexing"):
#                 result = api_client().ingest(
#                     file_bytes=uploaded.read(),
#                     filename=uploaded.name,
#                     metadata={
#                         "doc_type": upload_type,
#                         "classification_level": "UNCLASSIFIED",
#                         "issuing_authority": "",
#                         "effective_date": "",
#                     },
#                 )
#             st.session_state.last_ingest = result
#             st.rerun()
#         except Exception as exc:
#             st.error(f"Upload failed: {exc}")

#     if st.session_state.last_ingest:
#         result = st.session_state.last_ingest
#         units = result.get("pages_indexed") or result.get("chunks_created") or 0
#         st.success(f"Indexed {units} unit(s)")

#     st.markdown('<div style="height: 12px"></div><div class="panel-title">Chat</div>', unsafe_allow_html=True)
#     st.session_state.doc_type = st.selectbox("Search type", DOC_TYPES, index=DOC_TYPES.index(st.session_state.doc_type))
#     st.session_state.top_k = st.slider("Search depth", 1, 10, int(st.session_state.top_k))

#     st.markdown('<div style="height: 12px"></div><div class="panel-title">Status</div>', unsafe_allow_html=True)
#     st.markdown(
#         f"""
# <div class="metric-row"><span class="metric-label">Indexed</span><span class="metric-value">{total_indexed(h)}</span></div>
# <div class="metric-row"><span class="metric-label">Documents</span><span class="metric-value">{h.get("total_documents", "N/A")}</span></div>
# <div class="metric-row"><span class="metric-label">LLM</span><span class="metric-value">{"READY" if h.get("llm_service_ready") else "CONTEXT"}</span></div>
#         """,
#         unsafe_allow_html=True,
#     )

#     if st.button("Clear Chat", use_container_width=True):
#         st.session_state.messages = []
#         st.rerun()


# def direct_question(user_question: str) -> str:
#     return (
#         f"{user_question}\n\n"
#         "Give only the direct answer. Do not include retrieved sources, evidence snippets, confidence, "
#         "or explanation of how you searched. If the answer has multiple parts, use concise bullet points."
#     )


# def ask_backend(question: str) -> str:
#     filters = {"doc_type": st.session_state.doc_type} if st.session_state.doc_type != "auto" else None
#     result = api_client().query(direct_question(question), filters=filters, top_k=st.session_state.top_k)
#     return result.get("answer") or result.get("annotated_answer") or "No answer returned."


# def render_chat() -> None:
#     st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
#     for message in st.session_state.messages:
#         with st.chat_message(message["role"]):
#             st.markdown(message["content"])
#     st.markdown("</div>", unsafe_allow_html=True)

#     prompt = st.chat_input("Ask a question")
#     if not prompt:
#         return

#     st.session_state.messages.append({"role": "user", "content": prompt})
#     try:
#         with st.spinner("Answering"):
#             answer = ask_backend(prompt)
#     except Exception as exc:
#         answer = f"I could not answer that question: {exc}"
#     st.session_state.messages.append({"role": "assistant", "content": answer})
#     st.rerun()


# def render_main() -> None:
#     h = health()
#     render_topbar(h)

#     user_col, logout_col = st.columns([5, 1])
#     with user_col:
#         st.caption(f"Signed in as {st.session_state.username} | {datetime.now().strftime('%d %b %Y %H:%M')}")
#     with logout_col:
#         if st.button("Logout", use_container_width=True):
#             st.session_state.logged_in = False
#             st.session_state.token = None
#             st.session_state.messages = []
#             st.rerun()

#     left, main = st.columns([1, 3.2], gap="large")
#     with left:
#         st.markdown('<div class="panel">', unsafe_allow_html=True)
#         render_controls(h)
#         st.markdown("</div>", unsafe_allow_html=True)
#     with main:
#         render_chat()


# inject_theme()
# init_state()

# if st.session_state.logged_in:
#     render_main()
# else:
#     render_login()
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.utils.api_client import APIClient


API_BASE_URL = "http://127.0.0.1:8000"
DOC_TYPES = ["auto", "policy", "procurement_policy", "gfr_rules", "audit_report", "tender_document"]

st.set_page_config(page_title="INICAI Defence Chat", page_icon="🛡️", layout="wide")


# ─────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────
def inject_theme() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
    --bg:           #050816;
    --bg-2:         #080d1f;
    --card:         rgba(15,23,42,0.78);
    --card-border:  rgba(0,210,255,0.18);
    --primary:      #00D2FF;
    --primary-glow: rgba(0,210,255,0.25);
    --secondary:    #7C3AED;
    --sec-glow:     rgba(124,58,237,0.3);
    --green:        #10b981;
    --amber:        #f59e0b;
    --red:          #ef4444;
    --text:         #F8FAFC;
    --muted:        #94A3B8;
    --border-soft:  rgba(148,163,184,0.08);
    --border-mid:   rgba(0,210,255,0.22);
    --font: 'Inter','Space Grotesk',system-ui,sans-serif;
    --mono: 'Space Grotesk',monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

.stApp {
    background: var(--bg) !important;
    font-family: var(--font) !important;
    color: var(--text) !important;
    min-height: 100vh;
}

[data-testid="stSidebar"],
[data-testid="collapsedControl"],
header[data-testid="stHeader"],
footer { display: none !important; }

.block-container { max-width: 100% !important; padding: 0 !important; }

/* ════════ LOGIN BG ════════ */
.login-bg {
    position: fixed; inset: 0;
    background: var(--bg);
    overflow: hidden; z-index: 0;
}
.login-bg .orb1 {
    position: absolute;
    width: 700px; height: 700px; border-radius: 50%;
    background: radial-gradient(circle,rgba(0,210,255,0.18) 0%,transparent 70%);
    top: -200px; left: -150px;
    animation: drift1 12s ease-in-out infinite alternate;
}
.login-bg .orb2 {
    position: absolute;
    width: 600px; height: 600px; border-radius: 50%;
    background: radial-gradient(circle,rgba(124,58,237,0.22) 0%,transparent 70%);
    bottom: -180px; right: -120px;
    animation: drift2 14s ease-in-out infinite alternate;
}
.login-bg .orb3 {
    position: absolute;
    width: 350px; height: 350px; border-radius: 50%;
    background: radial-gradient(circle,rgba(0,210,255,0.08) 0%,transparent 70%);
    top: 45%; left: 55%;
    animation: drift3 9s ease-in-out infinite alternate;
}
@keyframes drift1{from{transform:translate(0,0)}to{transform:translate(60px,80px)}}
@keyframes drift2{from{transform:translate(0,0)}to{transform:translate(-50px,-60px)}}
@keyframes drift3{from{transform:translate(0,0)}to{transform:translate(30px,-40px)}}
.login-bg .grid {
    position: absolute; inset: 0;
    background-image:
        linear-gradient(rgba(0,210,255,0.04) 1px,transparent 1px),
        linear-gradient(90deg,rgba(0,210,255,0.04) 1px,transparent 1px);
    background-size: 60px 60px;
}
.login-bg .neural { position: absolute; inset: 0; opacity: 0.16; }

/* ════════ LOGIN PAGE ════════ */
.login-page {
    position: relative; z-index: 1;
    min-height: 100vh;
    display: flex; align-items: center; justify-content: center;
    padding: 2rem 1rem;
    animation: fadeUp 0.65s cubic-bezier(.22,.84,.44,1) both;
}
@keyframes fadeUp{
    from{opacity:0;transform:translateY(30px)}
    to{opacity:1;transform:translateY(0)}
}

/* glass card */
.glass-card {
    width: 100%; max-width: 440px;
    background: var(--card);
    backdrop-filter: blur(28px);
    -webkit-backdrop-filter: blur(28px);
    border: 1px solid var(--card-border);
    border-radius: 20px;
    box-shadow:
        0 0 0 1px rgba(0,210,255,0.05),
        0 32px 64px rgba(0,0,0,0.6),
        0 0 100px rgba(0,210,255,0.06),
        inset 0 1px 0 rgba(255,255,255,0.06);
    padding: 40px 36px 36px;
    position: relative;
    overflow: hidden;
}
.glass-card::before {
    content: '';
    display: block; height: 1px;
    background: linear-gradient(90deg,transparent,rgba(0,210,255,0.7),rgba(124,58,237,0.55),transparent);
    margin: -40px -36px 36px;
    border-radius: 20px 20px 0 0;
}

/* subtle shimmer at bottom */
.glass-card::after {
    content: '';
    position: absolute; bottom: 0; left: 0; right: 0; height: 80px;
    background: linear-gradient(to top,rgba(124,58,237,0.05),transparent);
    pointer-events: none;
}

/* logo */
.logo-ring {
    width: 54px; height: 54px;
    border-radius: 14px;
    background: linear-gradient(135deg,rgba(0,210,255,0.18),rgba(124,58,237,0.18));
    border: 1px solid rgba(0,210,255,0.38);
    display: flex; align-items: center; justify-content: center;
    margin-bottom: 22px;
    box-shadow: 0 0 28px rgba(0,210,255,0.14);
}
.logo-ring span {
    font-family: var(--mono); font-size: 16px; font-weight: 700;
    background: linear-gradient(135deg,#00D2FF,#7C3AED);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
    letter-spacing: 1px;
}

.card-title {
    font-size: 24px; font-weight: 700; letter-spacing: -0.4px;
    color: var(--text); margin-bottom: 6px; line-height: 1.2;
}
.card-sub { font-size: 13.5px; color: var(--muted); margin-bottom: 26px; line-height: 1.5; }

.row-opts {
    display: flex; align-items: center; justify-content: space-between;
    margin: 4px 0 20px; font-size: 12.5px;
}
.remember-label {
    display: flex; align-items: center; gap: 7px;
    color: var(--muted); cursor: pointer; user-select: none;
}
.remember-label input[type="checkbox"] {
    width: 14px; height: 14px; accent-color: var(--primary); cursor: pointer;
}
.forgot-link { color: var(--primary); text-decoration: none; font-weight: 500; cursor: pointer; }

.sep {
    display: flex; align-items: center; gap: 12px;
    margin: 22px 0 16px;
}
.sep-line { flex: 1; height: 1px; background: var(--border-soft); }
.sep-text { font-size: 11px; color: var(--muted); white-space: nowrap; }

.sys-tags { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-top: 2px; }
.sys-tag { font-size: 10.5px; font-weight: 500; padding: 4px 11px; border-radius: 99px; letter-spacing: 0.3px; }
.sys-tag.cyan   { background:rgba(0,210,255,0.1);  color:var(--primary); border:1px solid rgba(0,210,255,0.2); }
.sys-tag.violet { background:rgba(124,58,237,0.1); color:#a78bfa;        border:1px solid rgba(124,58,237,0.25); }
.sys-tag.green  { background:rgba(16,185,129,0.1); color:#34d399;        border:1px solid rgba(16,185,129,0.2); }

/* ── LOGIN INPUT OVERRIDES ── */
.login-page .stTextInput>div>div {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(148,163,184,0.16) !important;
    border-radius: 10px !important;
    transition: border-color 0.22s, box-shadow 0.22s !important;
}
.login-page .stTextInput>div>div:focus-within {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-glow) !important;
}
.login-page .stTextInput input {
    color: var(--text) !important;
    font-family: var(--font) !important;
    font-size: 14px !important;
    background: transparent !important;
    padding: 11px 14px !important;
}
.login-page .stTextInput input::placeholder { color: rgba(148,163,184,0.45) !important; }
.login-page label, .login-page .stTextInput label {
    color: var(--muted) !important; font-size: 12.5px !important;
    font-weight: 500 !important; letter-spacing: 0.3px !important;
}

/* ── GRADIENT LOGIN BUTTON ── */
.login-page .stButton>button {
    width: 100% !important; padding: 13px 0 !important;
    border-radius: 10px !important; border: none !important;
    background: linear-gradient(135deg,#00D2FF 0%,#7C3AED 100%) !important;
    color: #fff !important;
    font-family: var(--font) !important; font-size: 14.5px !important;
    font-weight: 600 !important; letter-spacing: 0.3px !important;
    transition: transform 0.18s, box-shadow 0.18s, opacity 0.18s !important;
    box-shadow: 0 4px 24px rgba(0,210,255,0.28), 0 4px 24px rgba(124,58,237,0.2) !important;
}
.login-page .stButton>button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 36px rgba(0,210,255,0.38), 0 8px 36px rgba(124,58,237,0.28) !important;
    opacity: 0.94 !important;
}
.login-page .stButton>button:active { transform: translateY(0) !important; opacity: 0.84 !important; }

.login-page .stAlert {
    border-radius: 10px !important; font-size: 13px !important;
    border: 1px solid rgba(239,68,68,0.3) !important;
    background: rgba(239,68,68,0.08) !important;
}

/* ════════ DASHBOARD ════════ */

.topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 13px 28px;
    background: rgba(8,13,31,0.94);
    backdrop-filter: blur(16px);
    border-bottom: 1px solid var(--border-mid);
    position: sticky; top: 0; z-index: 100;
}
.topbar::after {
    content: '';
    position: absolute; bottom: 0; left: 8%; right: 8%; height: 1px;
    background: linear-gradient(90deg,transparent,var(--primary),var(--secondary),transparent);
    opacity: 0.35;
}
.brand { display: flex; align-items: center; gap: 12px; }
.brand-hex {
    width: 36px; height: 36px; border-radius: 9px;
    background: linear-gradient(135deg,rgba(0,210,255,0.18),rgba(124,58,237,0.18));
    border: 1px solid rgba(0,210,255,0.38);
    display: grid; place-items: center;
}
.brand-hex span {
    font-family: var(--mono); font-size: 11px; font-weight: 700;
    background: linear-gradient(135deg,#00D2FF,#7C3AED);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
}
.brand-name { font-family: var(--mono); font-size: 14px; font-weight: 700; color: var(--text); letter-spacing: 2.5px; text-transform: uppercase; }
.brand-tag  { font-size: 10px; color: var(--muted); letter-spacing: 1.5px; text-transform: uppercase; font-family: var(--mono); margin-top: 2px; }

.status-pill {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 5px 14px; border-radius: 99px;
    background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3);
    font-family: var(--mono); font-size: 10px; font-weight: 700;
    letter-spacing: 2px; color: #34d399; text-transform: uppercase;
}
.status-pill.offline { background:rgba(239,68,68,0.1); border-color:rgba(239,68,68,0.3); color:#f87171; }
.pulse {
    width: 7px; height: 7px; border-radius: 50%;
    background: currentColor; flex-shrink: 0;
    animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse{
    0%,100%{box-shadow:0 0 0 0 currentColor;}
    50%{box-shadow:0 0 0 4px transparent;opacity:0.6;}
}

.user-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 28px 0; margin-bottom: 4px;
}
.user-meta { display: flex; align-items: center; gap: 10px; }
.user-avi {
    width: 30px; height: 30px; border-radius: 50%;
    background: linear-gradient(135deg,rgba(0,210,255,0.2),rgba(124,58,237,0.2));
    border: 1px solid rgba(0,210,255,0.3);
    display: grid; place-items: center;
    font-family: var(--mono); font-size: 10px; font-weight: 700; color: var(--primary);
}
.user-name-tag { font-family: var(--mono); font-size: 11px; color: var(--muted); letter-spacing: 1px; }
.timestamp     { font-family: var(--mono); font-size: 10px; color: rgba(148,163,184,0.42); letter-spacing: 0.8px; }

.panel {
    background: rgba(15,23,42,0.6);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(0,210,255,0.1);
    border-radius: 14px; padding: 20px; position: relative; overflow: hidden;
}
.panel::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg,transparent,rgba(0,210,255,0.4),transparent);
}

.section-label {
    font-family: var(--mono); font-size: 9px; letter-spacing: 3px; text-transform: uppercase;
    color: var(--primary); margin-bottom: 12px;
    display: flex; align-items: center; gap: 8px;
}
.section-label::after { content:''; flex:1; height:1px; background:rgba(0,210,255,0.12); }

.metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.metric-card {
    background: rgba(0,0,0,0.25); border: 1px solid rgba(0,210,255,0.1);
    border-radius: 10px; padding: 12px 14px; transition: border-color 0.2s;
}
.metric-card:hover { border-color: rgba(0,210,255,0.25); }
.m-label { font-family:var(--mono); font-size:9px; letter-spacing:2px; text-transform:uppercase; color:var(--muted); margin-bottom:5px; }
.m-value { font-family:var(--mono); font-size:22px; font-weight:700; color:var(--primary); line-height:1; }
.m-value.g { color:#34d399; }
.m-value.a { color:#fbbf24; }
.m-value.sm{ font-size:13px; letter-spacing:1px; }

.ingest-ok {
    background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.25);
    border-radius: 8px; padding: 8px 12px;
    font-family: var(--mono); font-size: 11px; color: #34d399;
    letter-spacing: 0.5px; margin-top: 8px;
}

.chat-shell {
    background: rgba(15,23,42,0.5); backdrop-filter: blur(10px);
    border: 1px solid rgba(0,210,255,0.1); border-radius: 14px;
    min-height: 66vh; padding: 20px 18px; position: relative; overflow: hidden;
}
.chat-shell::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg,transparent,rgba(0,210,255,0.45),rgba(124,58,237,0.3),transparent);
}

div[data-testid="stChatMessage"] { background: transparent !important; }
div[data-testid="stChatMessageContent"] {
    background: rgba(0,0,0,0.28) !important;
    border: 1px solid rgba(0,210,255,0.1) !important;
    border-radius: 10px !important; padding: 13px 16px !important;
    line-height: 1.75 !important; font-size: 14px !important;
    color: var(--text) !important; font-family: var(--font) !important;
}

.stTextInput input,
.stSelectbox div[data-baseweb="select"]>div {
    background: rgba(0,0,0,0.3) !important;
    border: 1px solid rgba(0,210,255,0.2) !important;
    border-radius: 8px !important; color: var(--text) !important;
    font-family: var(--font) !important; font-size: 13px !important;
}
.stTextInput input:focus,
.stSelectbox div[data-baseweb="select"]>div:focus-within {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-glow) !important;
}

div[data-testid="stFileUploader"] {
    background: rgba(0,0,0,0.25) !important;
    border: 1px dashed rgba(0,210,255,0.22) !important;
    border-radius: 8px !important; padding: 10px !important; transition: border-color 0.2s;
}
div[data-testid="stFileUploader"]:hover { border-color: rgba(0,210,255,0.42) !important; }

.stButton>button {
    border-radius: 8px !important; border: 1px solid rgba(0,210,255,0.22) !important;
    background: rgba(0,210,255,0.07) !important; color: var(--text) !important;
    font-family: var(--mono) !important; font-size: 11px !important;
    letter-spacing: 1.5px !important; text-transform: uppercase !important;
    font-weight: 700 !important; transition: all 0.2s !important;
}
.stButton>button:hover {
    border-color: var(--primary) !important;
    background: rgba(0,210,255,0.13) !important;
    color: var(--primary) !important;
    box-shadow: 0 0 18px rgba(0,210,255,0.1) !important;
}
button[kind="primary"] {
    background: linear-gradient(135deg,rgba(0,210,255,0.18),rgba(124,58,237,0.15)) !important;
    border-color: rgba(0,210,255,0.38) !important;
}
button[kind="primary"]:hover {
    background: linear-gradient(135deg,rgba(0,210,255,0.28),rgba(124,58,237,0.22)) !important;
    box-shadow: 0 4px 22px rgba(0,210,255,0.2) !important;
}

[data-testid="stChatInput"] textarea {
    background: rgba(0,0,0,0.3) !important;
    border: 1px solid rgba(0,210,255,0.2) !important;
    border-radius: 10px !important; color: var(--text) !important;
    font-size: 14px !important; font-family: var(--font) !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px var(--primary-glow) !important;
}

[data-baseweb="slider"] [role="slider"] { background: var(--primary) !important; border-color: var(--primary) !important; }
[data-baseweb="popover"] {
    z-index: 9999 !important;
    background: rgba(15,23,42,0.96) !important;
    border: 1px solid rgba(0,210,255,0.2) !important;
    border-radius: 10px !important;
    backdrop-filter: blur(16px) !important;
}
[data-baseweb="menu"] li { color: var(--text) !important; font-size: 13px !important; }
[data-baseweb="menu"] li:hover { background: rgba(0,210,255,0.07) !important; }

.stSuccess { background: rgba(16,185,129,0.08) !important; border-radius: 8px !important; }
.stError   { background: rgba(239,68,68,0.08) !important; border-radius: 8px !important; }
label, .stCaption { color: var(--muted) !important; font-size: 12px !important; font-family: var(--font) !important; }
</style>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
#  STATE
# ─────────────────────────────────────────────
def init_state() -> None:
    defaults = {
        "logged_in": False,
        "username": "",
        "token": None,
        "messages": [],
        "doc_type": "auto",
        "top_k": 5,
        "last_ingest": None,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


# ─────────────────────────────────────────────
#  BACKEND HELPERS  ← zero changes
# ─────────────────────────────────────────────
def api_client() -> APIClient:
    return APIClient(base_url=API_BASE_URL, token=st.session_state.token)


def health() -> dict:
    try:
        return api_client().get_health() or {}
    except Exception:
        return {"status": "offline"}


def total_indexed(h: dict) -> int:
    return int(h.get("total_pages") or h.get("total_chunks_indexed") or h.get("total_documents") or 0)


def direct_question(user_question: str) -> str:
    return (
        f"{user_question}\n\n"
        "Give only the direct answer. Do not include retrieved sources, evidence snippets, confidence, "
        "or explanation of how you searched. If the answer has multiple parts, use concise bullet points."
    )


def ask_backend(question: str) -> str:
    filters = {"doc_type": st.session_state.doc_type} if st.session_state.doc_type != "auto" else None
    result = api_client().query(direct_question(question), filters=filters, top_k=st.session_state.top_k)
    return result.get("answer") or result.get("annotated_answer") or "No answer returned."


# ─────────────────────────────────────────────
#  LOGIN PAGE
# ─────────────────────────────────────────────
def render_login() -> None:
    st.markdown(
        """
<div class="login-bg">
  <div class="orb1"></div><div class="orb2"></div><div class="orb3"></div>
  <div class="grid"></div>
  <svg class="neural" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
    <g stroke="#00D2FF" stroke-width="0.6" opacity="0.35">
      <line x1="120" y1="180" x2="360" y2="280"/><line x1="120" y1="180" x2="360" y2="450"/>
      <line x1="120" y1="420" x2="360" y2="280"/><line x1="120" y1="420" x2="360" y2="450"/>
      <line x1="120" y1="420" x2="360" y2="620"/><line x1="120" y1="650" x2="360" y2="450"/>
      <line x1="120" y1="650" x2="360" y2="620"/>
      <line x1="360" y1="280" x2="600" y2="200"/><line x1="360" y1="280" x2="600" y2="380"/>
      <line x1="360" y1="450" x2="600" y2="380"/><line x1="360" y1="450" x2="600" y2="540"/>
      <line x1="360" y1="620" x2="600" y2="540"/><line x1="360" y1="620" x2="600" y2="700"/>
      <line x1="600" y1="200" x2="840" y2="310"/><line x1="600" y1="380" x2="840" y2="310"/>
      <line x1="600" y1="380" x2="840" y2="480"/><line x1="600" y1="540" x2="840" y2="480"/>
      <line x1="600" y1="540" x2="840" y2="650"/><line x1="600" y1="700" x2="840" y2="650"/>
      <line x1="840" y1="310" x2="1080" y2="250"/><line x1="840" y1="310" x2="1080" y2="430"/>
      <line x1="840" y1="480" x2="1080" y2="430"/><line x1="840" y1="480" x2="1080" y2="600"/>
      <line x1="840" y1="650" x2="1080" y2="600"/><line x1="840" y1="650" x2="1080" y2="750"/>
      <line x1="1080" y1="250" x2="1320" y2="380"/><line x1="1080" y1="430" x2="1320" y2="380"/>
      <line x1="1080" y1="430" x2="1320" y2="520"/><line x1="1080" y1="600" x2="1320" y2="520"/>
      <line x1="1080" y1="600" x2="1320" y2="680"/><line x1="1080" y1="750" x2="1320" y2="680"/>
    </g>
    <g fill="none">
      <circle cx="120" cy="180" r="5"  stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="120" cy="420" r="5"  stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="120" cy="650" r="5"  stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="360" cy="280" r="5"  stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="360" cy="450" r="5"  stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="360" cy="620" r="5"  stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="600" cy="200" r="5"  stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="600" cy="380" r="5"  stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="600" cy="540" r="5"  stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="600" cy="700" r="5"  stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="840" cy="310" r="6"  stroke="#7C3AED" stroke-width="1.5" opacity="0.8"/>
      <circle cx="840" cy="480" r="6"  stroke="#7C3AED" stroke-width="1.5" opacity="0.8"/>
      <circle cx="840" cy="650" r="6"  stroke="#7C3AED" stroke-width="1.5" opacity="0.8"/>
      <circle cx="1080" cy="250" r="5" stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="1080" cy="430" r="5" stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="1080" cy="600" r="5" stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="1080" cy="750" r="5" stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="1320" cy="380" r="5" stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="1320" cy="520" r="5" stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
      <circle cx="1320" cy="680" r="5" stroke="#00D2FF" stroke-width="1.2" opacity="0.7"/>
    </g>
  </svg>
</div>

<div class="login-page">
  <div class="glass-card">
    <div class="logo-ring"><span>IN</span></div>
    <div class="card-title">Welcome Back</div>
    <div class="card-sub">Secure access to your AI workspace</div>
        """,
        unsafe_allow_html=True,
    )

    username = st.text_input("Username", placeholder="Enter your username")
    password = st.text_input("Password", type="password", placeholder="••••••••••••")

    st.markdown(
        """
<div class="row-opts">
  <label class="remember-label"><input type="checkbox"> Remember me</label>
  <span class="forgot-link">Forgot password?</span>
</div>
        """,
        unsafe_allow_html=True,
    )

    # ── ORIGINAL AUTH LOGIC — UNCHANGED ──
    if st.button("Sign in to INICAI", type="primary", use_container_width=True):
        if not username.strip() or not password.strip():
            st.error("Please enter your username and password.")
        else:
            response = APIClient(base_url=API_BASE_URL).login(username.strip(), password)
            st.session_state.token = response.get("access_token") if response else None
            st.session_state.username = username.strip()
            st.session_state.logged_in = True
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": "System ready. Ask your question — I will answer directly from indexed documents.",
                }
            ]
            st.rerun()

    st.markdown(
        """
    <div class="sep">
      <div class="sep-line"></div>
      <span class="sep-text">Defence Intelligence Platform</span>
      <div class="sep-line"></div>
    </div>
    <div class="sys-tags">
      <span class="sys-tag cyan">RAG-Powered</span>
      <span class="sys-tag violet">AI Secured</span>
      <span class="sys-tag green">End-to-End Encrypted</span>
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────────
def render_topbar(h: dict) -> None:
    status = str(h.get("status", "offline")).upper()
    pill_cls = "status-pill" if status not in ("OFFLINE", "LOCKED") else "status-pill offline"
    st.markdown(
        f"""
<div class="topbar">
  <div class="brand">
    <div class="brand-hex"><span>IN</span></div>
    <div>
      <div class="brand-name">INICAI</div>
      <div class="brand-tag">Defence Intelligence Chat</div>
    </div>
  </div>
  <div class="{pill_cls}"><span class="pulse"></span>{status}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_controls(h: dict) -> None:
    st.markdown('<div class="section-label">Upload Document</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Document", type=["pdf", "docx", "txt"], label_visibility="collapsed")
    upload_type = st.selectbox("Document type", DOC_TYPES, index=DOC_TYPES.index("auto"))
    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

    if st.button("⬆  Index Document", type="primary", use_container_width=True, disabled=uploaded is None):
        try:
            with st.spinner("Indexing document…"):
                result = api_client().ingest(
                    file_bytes=uploaded.read(),
                    filename=uploaded.name,
                    metadata={
                        "doc_type": upload_type,
                        "classification_level": "UNCLASSIFIED",
                        "issuing_authority": "",
                        "effective_date": "",
                    },
                )
            st.session_state.last_ingest = result
            st.rerun()
        except Exception as exc:
            st.error(f"Index failed: {exc}")

    if st.session_state.last_ingest:
        result = st.session_state.last_ingest
        units = result.get("pages_indexed") or result.get("chunks_created") or 0
        st.markdown(f'<div class="ingest-ok">✓ {units} unit(s) indexed successfully</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Search Config</div>', unsafe_allow_html=True)
    st.session_state.doc_type = st.selectbox(
        "Filter type", DOC_TYPES, index=DOC_TYPES.index(st.session_state.doc_type)
    )
    st.session_state.top_k = st.slider("Depth (top-k)", 1, 10, int(st.session_state.top_k))

    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">System Status</div>', unsafe_allow_html=True)
    llm_ready = h.get("llm_service_ready", False)
    llm_label = "READY" if llm_ready else "CTX"
    llm_cls   = "m-value g sm" if llm_ready else "m-value a sm"

    st.markdown(
        f"""
<div class="metric-grid">
  <div class="metric-card"><div class="m-label">Indexed</div><div class="m-value">{total_indexed(h)}</div></div>
  <div class="metric-card"><div class="m-label">Docs</div><div class="m-value">{h.get("total_documents","–")}</div></div>
  <div class="metric-card" style="grid-column:1/-1"><div class="m-label">LLM Service</div><div class="{llm_cls}">{llm_label}</div></div>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    if st.button("✕  Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


def render_chat() -> None:
    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    st.markdown("</div>", unsafe_allow_html=True)

    prompt = st.chat_input("Ask a question about indexed documents…")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    try:
        with st.spinner("Retrieving answer…"):
            answer = ask_backend(prompt)
    except Exception as exc:
        answer = f"Could not retrieve answer: {exc}"
    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.rerun()


def render_main() -> None:
    h = health()
    render_topbar(h)

    initials = st.session_state.username[:2].upper() if st.session_state.username else "??"
    user_col, logout_col = st.columns([6, 1])
    with user_col:
        st.markdown(
            f"""
<div class="user-bar">
  <div class="user-meta">
    <div class="user-avi">{initials}</div>
    <span class="user-name-tag">{st.session_state.username.upper()}</span>
  </div>
  <span class="timestamp">{datetime.now().strftime('%d %b %Y · %H:%M')}</span>
</div>
            """,
            unsafe_allow_html=True,
        )
    with logout_col:
        st.markdown('<div style="padding-top:10px; padding-right:28px">', unsafe_allow_html=True)
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.token = None
            st.session_state.messages = []
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div style="padding: 0 28px">', unsafe_allow_html=True)
    left, main = st.columns([1, 3.4], gap="large")
    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        render_controls(h)
        st.markdown("</div>", unsafe_allow_html=True)
    with main:
        render_chat()
    st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  ENTRY
# ─────────────────────────────────────────────
inject_theme()
init_state()

if st.session_state.logged_in:
    render_main()
else:
    render_login()