import streamlit as st
import os
import pandas as pd

st.set_page_config(
    page_title="SchemeAssist — XAI Platform",
    page_icon="🏛️",
    layout="centered",
)

# ── Detect current file's directory so paths always resolve ──
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CITIZEN_PORTAL = os.path.join(BASE_DIR, "citizen_portal.py")
AGENT_PORTAL   = os.path.join(BASE_DIR, "agent_portal.py")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

#MainMenu, footer, header { visibility: hidden; }

.stApp {
    background: #0a0f1e;
    background-image:
        radial-gradient(ellipse 80% 60% at 50% -10%, rgba(24, 95, 165, 0.35) 0%, transparent 70%),
        radial-gradient(ellipse 40% 30% at 80% 80%, rgba(99, 179, 237, 0.08) 0%, transparent 60%);
    min-height: 100vh;
}

.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
        linear-gradient(rgba(24, 95, 165, 0.06) 1px, transparent 1px),
        linear-gradient(90deg, rgba(24, 95, 165, 0.06) 1px, transparent 1px);
    background-size: 48px 48px;
    pointer-events: none;
    z-index: 0;
}

.hero-wrapper {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 72px 24px 40px;
    text-align: center;
}

.badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(24, 95, 165, 0.18);
    border: 1px solid rgba(99, 179, 237, 0.3);
    border-radius: 100px;
    padding: 6px 18px;
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #63b3ed;
    margin-bottom: 32px;
    animation: fadeSlideDown 0.6s ease both;
}

.main-title {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: clamp(2.2rem, 5vw, 3.4rem);
    font-weight: 900;
    line-height: 1.12;
    color: #ffffff;
    margin: 0 0 8px;
    animation: fadeSlideDown 0.7s ease both;
    animation-delay: 0.1s;
}

.main-title .accent {
    background: linear-gradient(135deg, #63b3ed 0%, #4299e1 40%, #185FA5 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.subtitle {
    font-size: 1rem;
    font-weight: 300;
    color: rgba(226, 232, 240, 0.55);
    max-width: 500px;
    line-height: 1.7;
    margin: 16px auto 48px;
    animation: fadeSlideDown 0.8s ease both;
    animation-delay: 0.2s;
}

.section-label {
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: rgba(226, 232, 240, 0.35);
    text-align: center;
    margin-bottom: 20px;
    animation: fadeSlideUp 0.8s ease both;
    animation-delay: 0.3s;
}

/* ── Make Streamlit buttons look like portal cards ── */
div[data-testid="stButton"] > button {
    all: unset !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    gap: 10px !important;
    width: 100% !important;
    cursor: pointer !important;
    background: rgba(15, 25, 50, 0.75) !important;
    border: 1px solid rgba(99, 179, 237, 0.18) !important;
    border-radius: 20px !important;
    padding: 36px 24px 32px !important;
    transition: all 0.3s cubic-bezier(0.23, 1, 0.32, 1) !important;
    backdrop-filter: blur(12px) !important;
    box-sizing: border-box !important;
    text-align: center !important;
    color: #e2e8f0 !important;
    line-height: 1.6 !important;
    white-space: pre-wrap !important;
}

div[data-testid="stButton"] > button:hover {
    transform: translateY(-6px) !important;
    border-color: rgba(99, 179, 237, 0.5) !important;
    box-shadow: 0 24px 48px rgba(0,0,0,0.45), 0 0 0 1px rgba(99,179,237,0.15) !important;
    background: rgba(20, 35, 70, 0.9) !important;
}

/* Agent card green hover */
div[data-testid="stHorizontalBlock"] > div:nth-child(2) div[data-testid="stButton"] > button:hover {
    border-color: rgba(16, 185, 129, 0.5) !important;
    box-shadow: 0 24px 48px rgba(0,0,0,0.45), 0 0 0 1px rgba(16,185,129,0.12) !important;
}

div[data-testid="stButton"] > button:focus {
    outline: none !important;
    box-shadow: 0 0 0 2px rgba(99,179,237,0.4) !important;
}

.footer-text {
    font-size: 0.72rem;
    color: rgba(226, 232, 240, 0.22);
    text-align: center;
    margin-top: 52px;
    letter-spacing: 0.06em;
}

@keyframes fadeSlideDown {
    from { opacity: 0; transform: translateY(-16px); }
    to   { opacity: 1; transform: translateY(0); }
}

@keyframes fadeSlideUp {
    from { opacity: 0; transform: translateY(20px); }
    to   { opacity: 1; transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)

# ── Portal routing — runs BEFORE rendering home page ─────────
portal = st.session_state.get("portal", None)

def run_portal(filepath):
    # Back to home button at the very top
    if st.sidebar.button("🏠 Back to Home", key="back_home"):
        st.session_state.pop("portal")
        st.rerun()

    with open(filepath, encoding="utf-8") as f:
        code = f.read()
    import re
    code = re.sub(
        r'st\.set_page_config\s*\(.*?\)',
        '',
        code,
        flags=re.DOTALL
    )
    exec(code, {"__file__": filepath})
    st.stop()

if portal == "citizen":
    run_portal(CITIZEN_PORTAL)

elif portal == "agent":
    run_portal(AGENT_PORTAL)

# ── Hero section ─────────────────────────────────────────────
st.markdown("""
<div class="hero-wrapper">
    <div class="badge">⚡ Powered by Explainable AI</div>
    <h1 class="main-title">
        <span class="accent">SchemeAssist</span><br>
        Transparent AI for<br>Government Schemes
    </h1>
    <p class="subtitle">
        AI-powered eligibility decisions you can trust and understand —
        every approval and rejection explained clearly to citizens and officers alike.
    </p>
</div>
<div class="section-label">Choose your portal</div>
""", unsafe_allow_html=True)

# ── Two portal cards ──────────────────────────────────────────
col1, col2 = st.columns(2, gap="large")

CITIZEN_LABEL = """🏛️


Citizen Portal


Check scheme eligibility, apply for government loans & grants, and get instant AI-powered decisions.


→  Enter Portal"""

AGENT_LABEL = """🏢


Agent Portal


Officer dashboard to review applications, add notes, and get AI-powered insights on trends.


→  Enter Portal"""

with col1:
    if st.button(CITIZEN_LABEL, key="citizen_card", use_container_width=True):
        st.session_state["portal"] = "citizen"
        st.rerun()

with col2:
    if st.button(AGENT_LABEL, key="agent_card", use_container_width=True):
        st.session_state["portal"] = "agent"
        st.rerun()

# ── Footer ────────────────────────────────────────────────────
st.markdown("""
<div class="footer-text">
    SchemeAssist &nbsp;·&nbsp; Explainable AI for Transparent Decision Systems &nbsp;·&nbsp; Built for Citizens &amp; Officers
</div>
""", unsafe_allow_html=True)