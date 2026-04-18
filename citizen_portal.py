import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uuid
import streamlit as st
from rag.gemini_scheme_chatbot import generate_answer
from ui.email_service import send_result_email, is_valid_email
import csv
import pytesseract
from PIL import Image
import re
import tempfile
import pickle
import numpy as np
import requests
import json
from datetime import datetime
from io import BytesIO

os.makedirs("datas", exist_ok=True)

# ════════════════════════════════════════════════════════════
# FIX 6: save_application now accepts decision_reason column
# ════════════════════════════════════════════════════════════
def save_application(data, prediction, confidence_score=0.0, decision_reason=""):
    file = "datas/applications.csv"
    file_exists = os.path.exists(file)
    row = {
        "app_id":            f"APP-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "submitted_at":      datetime.now().strftime("%d-%m-%Y %H:%M"),
        "name":              data.get("name", ""),
        "email":             data.get("email", ""),
        "phone":             data.get("phone", ""),
        "income":            data.get("income", 0),
        "employment":        data.get("employment", ""),
        "loan_amount":       data.get("loan_amount", 0),
        "loan_purpose":      data.get("loan_purpose", ""),
        "caste":             data.get("caste", ""),
        "state":             data.get("state", ""),
        "education":         data.get("education", ""),
        "assets":            data.get("assets", ""),
        "scheme_name":       data.get("selected_scheme", "General Loan Scheme"),
        "aadhar_verified":   data.get("aadhar_verified", False),
        "eligibility_score": round(confidence_score, 2),
        "status":            "Approved" if prediction == 1 else "Rejected",
        "rejection_reason":  "" if prediction == 1 else "Does not meet criteria",
        "decision_reason":   decision_reason,   # FIX 6: new column
        "agent_note":        ""
    }
    try:
        with open(file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        print(f"DEBUG: Failed to save application: {e}")


try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

KNOWN_SCHEMES = [
    "PM Kisan Samman Nidhi", "Kisan Credit Card", "PM Fasal Bima Yojana",
    "PM Awas Yojana", "PM Mudra Yojana", "Stand Up India", "PM SVANidhi",
    "National Education Loan", "Sukanya Samriddhi Yojana", "Atal Pension Yojana",
    "PM Jan Dhan Yojana", "Ayushman Bharat", "PM Kaushal Vikas Yojana",
    "Pradhan Mantri Rojgar Protsahan Yojana", "Soil Health Card Scheme",
    "Pradhan Mantri Shram-Yogi Maan-Dhan", "PM-SYM",
]


def generate_pdf_report(data: dict, approved: bool, reasons: list, recs: list, alternatives: list):
    if not REPORTLAB_AVAILABLE:
        return None
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles   = getSampleStyleSheet()
    BLUE     = colors.HexColor("#185FA5")
    GREEN    = colors.HexColor("#1a7a3f")
    RED      = colors.HexColor("#b91c1c")
    LIGHT_BG = colors.HexColor("#f0f6ff")
    GREY     = colors.HexColor("#6b7280")

    title_style = ParagraphStyle("title", parent=styles["Title"],   textColor=BLUE,  fontSize=20, spaceAfter=4)
    sub_style   = ParagraphStyle("sub",   parent=styles["Normal"],  textColor=GREY,  fontSize=10, spaceAfter=12)
    h2_style    = ParagraphStyle("h2",    parent=styles["Heading2"],textColor=BLUE,  fontSize=13, spaceBefore=14, spaceAfter=6)
    body_style  = ParagraphStyle("body",  parent=styles["Normal"],  fontSize=11, leading=16)
    status_ok   = ParagraphStyle("ok",    parent=styles["Normal"],  textColor=GREEN, fontSize=14, alignment=TA_CENTER, spaceBefore=8, spaceAfter=8)
    status_err  = ParagraphStyle("err",   parent=styles["Normal"],  textColor=RED,   fontSize=14, alignment=TA_CENTER, spaceBefore=8, spaceAfter=8)

    scheme   = data.get("selected_scheme", "Government Scheme")
    name     = data.get("name", "Applicant")
    date_str = datetime.now().strftime("%d %B %Y, %I:%M %p")
    story    = []

    story.append(Paragraph("SchemeAssist", title_style))
    story.append(Paragraph("Government Scheme Application Report", sub_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=BLUE, spaceAfter=10))
    story.append(Paragraph("APPLICATION APPROVED" if approved else "APPLICATION REJECTED",
                            status_ok if approved else status_err))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Applicant:</b> {name} &nbsp;&nbsp; | &nbsp;&nbsp; <b>Date:</b> {date_str}", body_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=10))
    story.append(Paragraph("Application Summary", h2_style))

    summary_data = [
        ["Field", "Details"],
        ["Scheme",           scheme],
        ["Annual Income",    f"Rs. {data.get('income', 0):,}"],
        ["Requested Amount", f"Rs. {data.get('loan_amount', 0):,}"],
        ["Purpose",          data.get("loan_purpose", "-")],
        ["Employment",       data.get("employment", "-")],
        ["Category",         data.get("caste", "-")],
        ["Education",        data.get("education", "-")],
        ["State",            data.get("state", "-")],
    ]
    tbl = Table(summary_data, colWidths=[70*mm, 100*mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  BLUE),
        ("TEXTCOLOR",     (0,0), (-1,0),  colors.white),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,0),  11),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, LIGHT_BG]),
        ("FONTNAME",      (0,1), (0,-1),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,1), (-1,-1), 10),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.lightgrey),
        ("ROWPADDING",    (0,0), (-1,-1), 7),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 14))

    if approved:
        story.append(Paragraph("Next Steps", h2_style))
        for r in recs:
            story.append(Paragraph(f"  - {r}", body_style))
    else:
        story.append(Paragraph("Reasons for Rejection", h2_style))
        for r in reasons:
            story.append(Paragraph(f"  - {r}", body_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph("How to Improve Your Chances", h2_style))
        for r in recs:
            story.append(Paragraph(f"  - {r}", body_style))

    if not approved and alternatives:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Alternative Schemes Suited to Your Profile", h2_style))
        for s in alternatives:
            alt_data = [
                [Paragraph(f"<b>{s.get('name','')}</b>", body_style)],
                [Paragraph(s.get("reason", ""), body_style)],
                [Paragraph(f"<i>Tip: {s.get('tip','')}</i>", body_style)],
            ]
            alt_tbl = Table(alt_data, colWidths=[170*mm])
            alt_tbl.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,-1), LIGHT_BG),
                ("LEFTPADDING",  (0,0), (-1,-1), 10),
                ("RIGHTPADDING", (0,0), (-1,-1), 10),
                ("TOPPADDING",   (0,0), (-1,-1), 6),
                ("BOTTOMPADDING",(0,-1),(-1,-1), 8),
                ("LINEAFTER",    (0,0), (0,-1),  3, BLUE),
                ("BOX",          (0,0), (-1,-1), 0.5, colors.lightgrey),
            ]))
            story.append(alt_tbl)
            story.append(Spacer(1, 8))

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This report was auto-generated by SchemeAssist. "
        "For assistance, visit your nearest Common Service Centre (CSC).",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=8, textColor=GREY, alignment=TA_CENTER)
    ))
    doc.build(story)
    return buffer.getvalue()


def extract_schemes_from_answer(answer_text: str) -> list:
    """Extract scheme names — try AI first, fall back to regex pattern matching."""
    
    # ── Fallback: regex patterns that catch scheme names directly ──
    # These patterns catch "Scheme Name" style phrases from the response text
    regex_patterns = [
        r'\b(PM\s+[A-Z][A-Za-z\s\-]{2,40}(?:Yojana|Scheme|Nidhi|Bima|Yojna|Mission|Portal|Card))\b',
        r'\b(Pradhan\s+Mantri\s+[A-Za-z\s\-]{2,40})\b',
        r'\b([A-Z][A-Za-z\s\-]{2,40}(?:Yojana|Scheme|Nidhi|Bima|Yojna|Mission))\b',
        r'\b(Ayushman\s+Bharat)\b',
        r'\b(Stand\s+Up\s+India)\b',
        r'\b(Start\s+Up\s+India)\b',
        r'\b(Kisan\s+Credit\s+Card)\b',
        r'\b(Jan\s+Dhan\s+Yojana)\b',
        r'\b(Sukanya\s+Samriddhi\b[A-Za-z\s]*)\b',
    ]
    
    found = []
    seen  = set()
    for pattern in regex_patterns:
        matches = re.findall(pattern, answer_text)
        for m in matches:
            clean = m.strip()
            if clean and clean.lower() not in seen and len(clean) > 4:
                found.append(clean)
                seen.add(clean.lower())

    if found:
        return found[:5]  # max 5 schemes

    # ── Try AI only if regex found nothing ──
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 300,
                "messages": [{"role": "user", "content":
                    "Extract all Indian government scheme names mentioned in the text below. "
                    "Return ONLY a JSON array of scheme name strings, nothing else. "
                    "If no specific scheme names are found, return an empty array []. "
                    "Example output: [\"PM Kisan Samman Nidhi\", \"PM Mudra Yojana\"]\n\n"
                    f"Text:\n{answer_text}"
                }]
            },
            timeout=15
        )
        raw = resp.json()["content"][0]["text"].strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw)
        return result if isinstance(result, list) and result else []
    except Exception as e:
        print("Scheme extraction error:", e)
        return []

def format_answer_for_display(raw_answer: str) -> str:
    prompt = (
        "You are a friendly government scheme advisor helping ordinary Indian citizens. "
        "Below is raw retrieved data about government schemes. "
        "Rewrite it as a warm, conversational explanation — like a helpful friend who knows about these schemes. "
        "Rules:\n"
        "- Write in natural flowing sentences and short paragraphs (2-3 sentences each)\n"
        "- If multiple schemes are mentioned, give each scheme 1 short paragraph covering: "
        "what it is, who it helps, and the main benefit\n"
        "- Do NOT use database-style formatting like 'Scheme Name:', 'Category:', 'Target Group:' labels\n"
        "- Do NOT produce raw bullet point lists of fields\n"
        "- Keep the tone simple, warm, and helpful\n"
        "- End with a brief note about how to apply or get more help\n\n"
        f"Raw data to rewrite:\n{raw_answer}"
    )
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1200,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=25
        )
        text = resp.json()["content"][0]["text"].strip()
        return text if text else raw_answer
    except Exception as e:
        print("Format error:", e)
        return raw_answer


def extract_aadhar_details(uploaded_file) -> dict:
    result = {"aadhar_number": None, "name": None, "phone": None, "raw_text": ""}
    try:
        uploaded_file.seek(0)
        file_bytes = uploaded_file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(file_bytes)
            temp_path = tmp.name

        image    = Image.open(temp_path)
        all_text = ""
        for cfg in ["--psm 6", "--psm 4", "--psm 3 --oem 3", "--psm 11"]:
            try:
                all_text += " " + pytesseract.image_to_string(image, config=cfg)
            except Exception:
                pass

        try:
            os.unlink(temp_path)
        except Exception:
            pass

        all_text = all_text.replace("\n", " ")
        result["raw_text"] = all_text

        aadhar_matches = re.findall(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b", all_text)
        if aadhar_matches:
            result["aadhar_number"] = re.sub(r"[\s\-]", "", aadhar_matches[0])

        phone_matches = re.findall(r"\b(?:\+91[\s\-]?)?[6-9]\d{9}\b", all_text)
        if phone_matches:
            ph = re.sub(r"[\s\-\+]", "", phone_matches[0])
            if ph.startswith("91") and len(ph) == 12:
                ph = ph[2:]
            result["phone"] = ph

        name_match = re.search(
            r"(?:Name|नाम)[:\s]+([A-Z][a-zA-Z\s]{3,40})(?=\s|$)", all_text, re.IGNORECASE
        )
        if name_match:
            result["name"] = name_match.group(1).strip()
        else:
            cap_name = re.search(r"\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b", all_text)
            if cap_name:
                candidate = cap_name.group(1).strip()
                skip_words = {"Government", "India", "Date", "Issue", "Card", "Unique",
                              "Authority", "Address", "Male", "Female", "Download"}
                if not any(w in candidate for w in skip_words):
                    result["name"] = candidate

    except Exception as e:
        print("OCR Error:", e)

    return result


def run_model_prediction(data, decision_reason=""):
    try:
        model = pickle.load(open("models/trained_model.pkl", "rb"))
        n = model.n_features_in_
        all_features = [
            data.get("income", 0),
            data.get("loan_amount", 0),
            {"General": 0, "OBC": 1, "SC": 2, "ST": 3}.get(data.get("caste", "General"), 0),
            ["Below 10th","10th Pass","12th Pass","Graduate","Post Graduate"].index(
                data.get("education","10th Pass")
            ) if data.get("education","10th Pass") in [
                "Below 10th","10th Pass","12th Pass","Graduate","Post Graduate"
            ] else 0,
            ["Unemployed","Farmer","Student","Self-employed","Salaried","Other"].index(
                data.get("employment","Other")
            ) if data.get("employment","Other") in [
                "Unemployed","Farmer","Student","Self-employed","Salaried","Other"
            ] else 0,
        ]
        feature_list = (all_features + [0] * n)[:n]
        input_data   = np.array([feature_list])
        prediction   = model.predict(input_data)[0]
        try:
            confidence = model.predict_proba(input_data)[0][int(prediction)]
        except Exception:
            confidence = 1.0 if prediction == 1 else 0.0
        # FIX 6: pass decision_reason through
        save_application(data, prediction, confidence_score=confidence, decision_reason=decision_reason)
        return bool(prediction == 1), input_data
    except Exception:
        income      = data.get("income", 0)
        loan_amount = data.get("loan_amount", 0)
        approved    = income >= 150000 and (loan_amount == 0 or loan_amount <= income * 5)
        prediction  = 1 if approved else 0
        save_application(data, prediction, confidence_score=0.0, decision_reason=decision_reason)
        return approved, None


def get_ai_scheme_suggestions(data):
    profile = (
        f"Income: Rs.{data.get('income',0):,}/yr | Employment: {data.get('employment')} | "
        f"Category: {data.get('caste')} | Education: {data.get('education')} | "
        f"State: {data.get('state')} | Purpose: {data.get('loan_purpose')} | "
        f"Requested: Rs.{data.get('loan_amount',0):,} | Assets: {data.get('assets')} | "
        f"Rejected scheme: {data.get('selected_scheme')}"
    )
    prompt = (
        f"User profile: {profile}\n\n"
        f"Suggest exactly 3 alternative Indian government schemes this person is likely to qualify for. "
        f"Respond ONLY as a JSON array, no markdown, no extra text:\n"
        f'[{{"name":"...","reason":"1-2 sentences why they qualify","tip":"one actionable apply tip"}}]'
    )
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 800,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=20
        )
        raw    = resp.json()["content"][0]["text"].strip()
        raw    = re.sub(r"^```[a-z]*\n?", "", raw)
        raw    = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except Exception as e:
        print("AI suggestion error:", e)
        return []


def rule_based_alternatives(data):
    alts  = []
    inc   = data.get("income", 0)
    emp   = data.get("employment", "")
    caste = data.get("caste", "")
    purp  = data.get("loan_purpose", "")
    skip  = data.get("selected_scheme", "")
    candidates = [
        (inc < 300000,
         {"name":"PM Jan Dhan Yojana","reason":"Basic banking & financial inclusion for low-income households.","tip":"Visit any nationalised bank with Aadhar to open a zero-balance account."}),
        (emp == "Farmer" and "PM Kisan" not in skip,
         {"name":"PM Kisan Samman Nidhi","reason":"Rs.6,000/year direct income support for farmers.","tip":"Register on the PM-Kisan portal with land records and Aadhar."}),
        (emp == "Farmer" and "Fasal Bima" not in skip,
         {"name":"PM Fasal Bima Yojana","reason":"Crop insurance protecting farmers from natural calamity losses.","tip":"Apply before crop season through your nearest bank or insurance office."}),
        (caste in ["SC","ST"] and "Stand Up" not in skip,
         {"name":"Stand Up India","reason":"Loans Rs.10L to Rs.1Cr for SC/ST entrepreneurs.","tip":"Apply via Stand Up India portal with business plan and Aadhar."}),
        (emp in ["Self-employed","Unemployed"] and "Mudra" not in skip,
         {"name":"PM Mudra Yojana","reason":"Micro-loans up to Rs.10L for small business/self-employment.","tip":"Visit nearest bank with a simple business plan to apply."}),
        (emp == "Student" and "Education Loan" not in skip,
         {"name":"National Education Loan","reason":"Subsidised loans for students in higher education.","tip":"Apply on Vidya Lakshmi Portal with your college admission letter."}),
        (purp == "Housing" and "Awas" not in skip,
         {"name":"PM Awas Yojana","reason":"Housing subsidy for eligible households.","tip":"Check eligibility on the PMAY portal with Aadhar and income details."}),
        (True,
         {"name":"PM Mudra Yojana","reason":"Micro-loans available for a wide range of income groups and purposes.","tip":"Visit nearest bank with a simple business plan to apply."}),
    ]
    for condition, scheme in candidates:
        if condition and scheme not in alts:
            alts.append(scheme)
        if len(alts) == 3:
            break
    return alts


def get_rejection_reasons(data):
    reasons, recs = [], []
    income = data.get("income", 0)
    loan   = data.get("loan_amount", 0)
    emp    = data.get("employment", "")
    edu    = data.get("education", "")
    scheme = data.get("selected_scheme", "")
    if income < 150000:
        reasons.append("Annual income is below the minimum threshold (Rs.1,50,000)")
        recs.append("Explore BPL-targeted schemes like PM Jan Dhan Yojana or Ayushman Bharat")
    if income > 0 and loan > income * 5:
        reasons.append(f"Requested Rs.{loan:,} is too high vs income Rs.{income:,} (max ~5x income)")
        recs.append(f"Consider requesting Rs.{int(income*3):,} or less")
    if emp == "Unemployed":
        reasons.append("Unemployed status lowers approval for most loan schemes")
        recs.append("First complete PM Kaushal Vikas Yojana training, then reapply")
    if edu == "Below 10th" and "education" in scheme.lower():
        reasons.append("Education schemes require at least 10th pass qualification")
        recs.append("Enrol in adult education / open schooling to improve qualification")
    if loan == 0:
        reasons.append("No loan/grant amount was entered")
    if not reasons:
        reasons.append("Profile does not fully match this scheme's eligibility criteria")
        recs.append("Review official scheme guidelines and reapply with updated information")
    return reasons, recs


def get_approval_recommendations(data):
    scheme = data.get("selected_scheme", "this scheme")
    return [
        "Keep Aadhar and PAN ready for final bank verification",
        f"Visit your nearest bank or Common Service Centre (CSC) to complete the {scheme} application",
        "Link your bank account to Aadhar for Direct Benefit Transfer (DBT)",
        "Track your application on the official portal or DigiLocker app",
    ]


# ════════════════════════════════════════════════════════════
# PAGE CONFIG & CSS
# ════════════════════════════════════════════════════════════
st.set_page_config(page_title="SchemeAssist", page_icon="🏛️", layout="centered")

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.bot-bubble {
    background:#f0f2f6; border-radius:14px 14px 14px 4px;
    padding:12px 16px; margin:8px 0; font-size:14px; line-height:1.7; color:#1a1a1a;
}
.user-bubble {
    background:#185FA5; color:white; border-radius:14px 14px 4px 14px;
    padding:12px 16px; margin:8px 0; font-size:14px; line-height:1.6; text-align:right;
}
.scheme-alt-card {
    background:#f8faff; border-left:4px solid #185FA5;
    border-radius:8px; padding:12px 16px; margin:8px 0; font-size:14px;
}
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# FIX 1: DISCLAIMER — shown on every page at the very top
# ════════════════════════════════════════════════════════════
st.warning(
    "⚠️ This system provides AI-based recommendations using limited data. "
    "Final eligibility depends on official government rules. "
    "Please verify details before applying."
)

# ════════════════════════════════════════════════════════════
# SESSION STATE
# ════════════════════════════════════════════════════════════
DEFAULTS = {
    "messages":            [{"role":"assistant","content":"Hello! Ask me about any government scheme — loans, education, housing, and more."}],
    "page":                "chat",
    "form_data":           {},
    "detected_schemes":    [],
    "selected_scheme":     "",
    "fab_messages":        [{"role":"assistant","content":"Hi! Ask me anything about this scheme or any other. 😊"}],
    "fab_key":             0,
    "fab_detected":        [],
    "result_pdf_bytes":    None,
    "result_approved":     None,
    "result_reasons":      [],
    "result_recs":         [],
    "result_alternatives": [],
    "email_sent":          False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ════════════════════════════════════════════════════════════
# FLOATING CHATBOT WIDGET
# ════════════════════════════════════════════════════════════
def render_fab():
    st.markdown("""
    <style>
    .fab-fixed {
        position:fixed; bottom:24px; right:24px; z-index:9999;
        background:#185FA5; color:white; border-radius:50%;
        width:56px; height:56px; font-size:24px;
        display:flex; align-items:center; justify-content:center;
        box-shadow:0 4px 16px rgba(24,95,165,0.45);
        cursor:pointer; user-select:none;
    }
    </style>
    <div class="fab-fixed" title="Scheme Assistant">💬</div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("## 💬 Scheme Assistant")
        st.caption("Ask about schemes, eligibility, documents…")
        st.divider()

        for msg in st.session_state.fab_messages:
            if msg["role"] == "assistant":
                st.markdown(
                    f'<div class="bot-bubble" style="font-size:13px;">🤖 {msg["content"]}</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div class="user-bubble" style="font-size:13px;">👤 {msg["content"]}</div>',
                    unsafe_allow_html=True
                )

        if st.session_state.fab_detected:
            st.divider()
            st.markdown("**📝 Apply for a scheme:**")
            for idx, s in enumerate(st.session_state.fab_detected):
                if st.button(f"🚀 Apply — {s}", key=f"fab_apply_{idx}_{s[:15]}"):
                    st.session_state.selected_scheme = s
                    st.session_state.fab_detected    = []
                    st.session_state.form_data       = {}
                    st.session_state.result_approved = None
                    st.session_state.email_sent      = False
                    st.session_state.page            = "form"
                    st.rerun()

        st.divider()
        fab_q = st.text_input(
            "Ask a question",
            key=f"fab_q_{st.session_state.fab_key}",
            placeholder="e.g. Who can apply for PM Kisan?",
            label_visibility="collapsed"
        )
        col1, col2 = st.columns([4, 1])
        with col1:
            send = st.button("Send ➤", key="fab_send", use_container_width=True)
        with col2:
            if st.button("🗑️", key="fab_clear", help="Clear chat"):
                st.session_state.fab_messages = [{"role":"assistant","content":"Hi! Ask me anything about this scheme or any other. 😊"}]
                st.session_state.fab_detected = []
                st.session_state.fab_key     += 1
                st.rerun()

        if send and fab_q.strip():
            st.session_state.fab_messages.append({"role": "user", "content": fab_q.strip()})
            with st.spinner("Thinking..."):
                raw_reply = generate_answer(fab_q.strip())
                reply     = format_answer_for_display(raw_reply)
            st.session_state.fab_messages.append({"role": "assistant", "content": reply})
            found = extract_schemes_from_answer(raw_reply)
            st.session_state.fab_detected = found if found else []
            st.session_state.fab_key     += 1
            st.rerun()


# ════════════════════════════════════════════════════════════
# PAGE 1 — MAIN CHATBOT
# ════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════
# PAGE 1 — MAIN CHATBOT
# ════════════════════════════════════════════════════════════
if st.session_state.page == "chat":

    st.markdown("## 🏛️ SchemeAssist")
    st.caption("Find government schemes and check your eligibility")
    st.divider()

    for msg in st.session_state.messages:
        if msg["role"] == "assistant":
            st.markdown(f'<div class="bot-bubble">🤖 {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="user-bubble">👤 {msg["content"]}</div>', unsafe_allow_html=True)

    # ── Show action buttons if schemes were detected ──────────
    if st.session_state.detected_schemes:
        st.divider()
        st.markdown("#### 💡 What would you like to do?")

        if st.button("📖 Tell me more about these schemes", use_container_width=True):
            followup = "Explain in more detail: " + ", ".join(st.session_state.detected_schemes)
            st.session_state.messages.append({"role": "user", "content": followup})
            with st.spinner("Fetching details..."):
                raw    = generate_answer(followup)
                answer = format_answer_for_display(raw)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            # keep detected_schemes so apply buttons remain
            more_schemes = extract_schemes_from_answer(raw + " " + answer)
            if more_schemes:
                st.session_state.detected_schemes = list(dict.fromkeys(
                    st.session_state.detected_schemes + more_schemes
                ))
            st.rerun()

        st.markdown("#### 📝 Apply for a scheme:")
        for idx, scheme in enumerate(st.session_state.detected_schemes):
            if st.button(f"🚀 Apply for {scheme}", key=f"main_apply_{idx}_{scheme[:20]}", use_container_width=True):
                st.session_state.selected_scheme  = scheme
                st.session_state.form_data        = {}
                st.session_state.result_approved  = None
                st.session_state.email_sent       = False
                st.session_state.page             = "form"
                st.rerun()

    st.divider()
    user_input = st.chat_input("Ask about a government scheme or say 'I want to apply for PM Kisan'...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.spinner("Searching schemes..."):
            raw_answer       = generate_answer(user_input)
            formatted_answer = format_answer_for_display(raw_answer)

        st.session_state.messages.append({"role": "assistant", "content": formatted_answer})

        # Extract from BOTH raw and formatted to maximise detection
        combined_text = user_input + " " + raw_answer + " " + formatted_answer
        found = extract_schemes_from_answer(combined_text)
        # Also check if user directly said "apply for X" or "I want X"
        apply_match = re.search(
            r"(?:apply for|want to apply|interested in|apply|get)\s+([A-Z][A-Za-z\s\-]{3,60})",
            user_input, re.IGNORECASE
        )
        if apply_match:
            direct_scheme = apply_match.group(1).strip()
            # Ask AI to confirm/clean the scheme name
            try:
                confirm_resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 100,
                        "messages": [{"role": "user", "content":
                            f"Is '{direct_scheme}' an Indian government scheme name? "
                            f"If yes, return just the correct official scheme name as plain text. "
                            f"If no, return 'NO'."
                        }]
                    },
                    timeout=10
                )
                confirmed = confirm_resp.json()["content"][0]["text"].strip()
                if confirmed != "NO" and len(confirmed) < 80:
                    found = list(dict.fromkeys([confirmed] + found))
            except Exception:
                if direct_scheme not in found:
                    found.append(direct_scheme)

        st.session_state.detected_schemes = found
        st.rerun()


# ════════════════════════════════════════════════════════════
# PAGE 2 — APPLICATION FORM
# ════════════════════════════════════════════════════════════
elif st.session_state.page == "form":

    scheme_name = st.session_state.selected_scheme or "Government Scheme"
    st.markdown("## 📋 Application Form")
    st.info(f"📌 Applying for: **{scheme_name}**")
    st.caption("Fill in your details to check eligibility and apply")
    st.divider()

    # ── FIX 2: DATA PRIVACY STATEMENT ────────────────────────
    st.info(
        "🔒 Your data is used only for processing this application and is not shared externally. "
        "Sensitive documents are validated securely."
    )

    # ── FIX 3: FAIRNESS STATEMENT ────────────────────────────
    st.info(
        "⚖️ The system aims to provide fair recommendations. "
        "However, outcomes may vary due to data limitations. "
        "No discrimination is intentionally applied."
    )

    with st.form("application_form"):
        st.markdown("### 👤 Personal Details")
        c1, c2 = st.columns(2)
        with c1:
            name   = st.text_input("Full Name *")
            dob    = st.date_input("Date of Birth *")
            gender = st.selectbox("Gender *", ["Select","Male","Female","Other"])
        with c2:
            email  = st.text_input("Email Address *", placeholder="you@example.com")
            phone  = st.text_input("Phone Number *")
            aadhar = st.text_input("Aadhar Number *", placeholder="XXXX XXXX XXXX")

        st.divider()
        st.markdown("### 💰 Financial Details")
        c3, c4 = st.columns(2)
        with c3:
            income     = st.number_input("Annual Income (Rs.) *", min_value=0, step=1000)
            employment = st.selectbox("Employment Type *", ["Select","Salaried","Self-employed","Farmer","Student","Unemployed","Other"])
        with c4:
            loan_amount  = st.number_input("Loan / Grant Amount Requested (Rs.) *", min_value=0, step=1000)
            loan_purpose = st.selectbox("Purpose *", ["Select","Agriculture","Education","Housing","Business","Medical","Other"])

        st.divider()
        st.markdown("### 🏠 Background Details")
        c5, c6 = st.columns(2)
        with c5:
            caste = st.selectbox("Category *", ["Select","General","OBC","SC","ST"])
            state = st.selectbox("State *", ["Select","Tamil Nadu","Maharashtra","Karnataka","Uttar Pradesh","Rajasthan","Gujarat","Other"])
        with c6:
            education = st.selectbox("Education Level *", ["Select","Below 10th","10th Pass","12th Pass","Graduate","Post Graduate"])
            assets    = st.selectbox("Do you own land / property? *", ["Select","Yes","No"])

        st.divider()
        st.markdown("### 📎 Document Upload")
        c7, c8 = st.columns(2)
        with c7:
            aadhar_file = st.file_uploader("Aadhar Card * (JPG/PNG)", type=["jpg","jpeg","png"])
            pan_file    = st.file_uploader("PAN Card", type=["pdf","jpg","jpeg","png"])
        with c8:
            license_file  = st.file_uploader("Driving License", type=["pdf","jpg","jpeg","png"])
            income_proof  = st.file_uploader("Income Proof", type=["pdf","jpg","jpeg","png"])
            passport_file = st.file_uploader("Passport", type=["pdf","jpg","jpeg","png"])

        st.divider()

        # ── FIX 5: USER CONSENT CHECKBOX ─────────────────────
        consent = st.checkbox(
            "✅ I agree to the use of my data for AI-based evaluation and have read the privacy notice above."
        )

        submitted = st.form_submit_button("🚀 Submit Application", type="primary", use_container_width=True)

        if submitted:
            # ── FIX 5: Block if no consent ───────────────────
            if not consent:
                st.warning("⚠️ Please provide consent to continue.")
            else:
                errors = []
                if not name.strip():            errors.append("Full Name is required")
                if gender == "Select":          errors.append("Gender is required")
                if not email.strip():           errors.append("Email Address is required")
                elif not is_valid_email(email): errors.append("Email Address is not valid (e.g. you@example.com)")
                if employment == "Select":      errors.append("Employment Type is required")
                if loan_purpose == "Select":    errors.append("Purpose is required")
                if caste == "Select":           errors.append("Category is required")
                if state == "Select":           errors.append("State is required")
                if education == "Select":       errors.append("Education Level is required")
                if assets == "Select":          errors.append("Land/property ownership is required")
                if not aadhar_file:             errors.append("Aadhar document is mandatory")

                aadhar_clean = re.sub(r"[\s\-]", "", aadhar)
                if aadhar_clean and not re.fullmatch(r"\d{12}", aadhar_clean):
                    errors.append("Aadhar number must be exactly 12 digits")

                phone_clean = re.sub(r"[\s\-\(\)]", "", phone)
                if phone_clean and not re.fullmatch(r"[6-9]\d{9}", phone_clean):
                    errors.append("Phone number must be a valid 10-digit Indian mobile number")

                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")
                else:
                    ocr_details          = extract_aadhar_details(aadhar_file)
                    aadhar_ok            = False
                    aadhar_verified_flag = False

                    extracted_aadhar = ocr_details.get("aadhar_number")
                    extracted_name   = ocr_details.get("name")
                    extracted_phone  = ocr_details.get("phone")

                    # ── HARD BLOCK OCR — all 3 must pass ─────
                    if not extracted_aadhar:
                        st.error(
                            "❌ Could not read any details from the Aadhar image. "
                            "Please upload a clear, well-lit image of your Aadhar card."
                        )

                    else:
                        ocr_passed = True

                        # Hard check 1 — Aadhar number must match exactly
                        if extracted_aadhar != aadhar_clean:
                            st.error(
                                f"❌ Aadhar number entered (**{aadhar_clean}**) does not match "
                                f"the document (**{extracted_aadhar}**). Please re-check."
                            )
                            ocr_passed = False

                        # Hard check 2 — Name must have at least one word matching
                        if extracted_name:
                            entered_words   = set(name.strip().lower().split())
                            extracted_words = set(extracted_name.strip().lower().split())
                            if not entered_words.intersection(extracted_words):
                                st.error(
                                    f"❌ Name entered (**{name.strip()}**) does not match "
                                    f"the Aadhar document (**{extracted_name}**). Please re-check."
                                )
                                ocr_passed = False
                        else:
                            st.error(
                                "❌ Could not read name from Aadhar image. "
                                "Please upload a clearer image."
                            )
                            ocr_passed = False

                        # Hard check 3 — Phone must match
                        if extracted_phone:
                            if extracted_phone != phone_clean:
                                st.error(
                                    f"❌ Phone number entered (**{phone_clean}**) does not match "
                                    f"the Aadhar document (**{extracted_phone}**). Please re-check."
                                )
                                ocr_passed = False
                        else:
                            st.error(
                                "❌ Could not read phone number from Aadhar image. "
                                "Please upload a clearer image."
                            )
                            ocr_passed = False

                        if ocr_passed:
                            aadhar_verified_flag = True
                            aadhar_ok            = True
                            st.success("✅ Aadhar fully verified — number, name, and phone all match.")

                    if aadhar_ok:
                        st.session_state.form_data = {
                            "name":            name.strip(),
                            "dob":             str(dob),
                            "gender":          gender,
                            "email":           email.strip(),
                            "phone":           phone_clean,
                            "aadhar":          aadhar_clean,
                            "income":          income,
                            "employment":      employment,
                            "loan_amount":     loan_amount,
                            "loan_purpose":    loan_purpose,
                            "caste":           caste,
                            "state":           state,
                            "education":       education,
                            "assets":          assets,
                            "selected_scheme": scheme_name,
                            "aadhar_verified": aadhar_verified_flag,
                            "documents": {
                                "aadhar":       aadhar_file.name if aadhar_file else None,
                                "pan":          pan_file.name if pan_file else None,
                                "license":      license_file.name if license_file else None,
                                "income_proof": income_proof.name if income_proof else None,
                                "passport":     passport_file.name if passport_file else None,
                            }
                        }
                        st.session_state.result_pdf_bytes    = None
                        st.session_state.result_approved     = None
                        st.session_state.result_reasons      = []
                        st.session_state.result_recs         = []
                        st.session_state.result_alternatives = []
                        st.session_state.email_sent          = False
                        st.session_state.page                = "result"
                        st.rerun()

    st.divider()
    if st.button("⬅️ Back to Chatbot"):
        st.session_state.page = "chat"
        st.rerun()

    render_fab()

# ════════════════════════════════════════════════════════════
# PAGE 3 — RESULT
# ════════════════════════════════════════════════════════════
elif st.session_state.page == "result":

    if not st.session_state.form_data:
        st.warning("⚠️ Please fill the application form first.")
        if st.button("⬅️ Go to Form"):
            st.session_state.page = "form"
            st.rerun()

    else:
        data   = st.session_state.form_data
        scheme = data.get("selected_scheme", "Government Scheme")

        if st.session_state.result_approved is None:

            # ── FIX 6: Build decision_reason before calling model ──
            pre_reasons, _ = get_rejection_reasons(data)
            decision_reason_str = " | ".join(pre_reasons) if pre_reasons else "Meets eligibility criteria"

            approved, input_data = run_model_prediction(data, decision_reason=decision_reason_str)

            if approved:
                reasons = []
                recs    = get_approval_recommendations(data)
            else:
                reasons, recs = get_rejection_reasons(data)

            alternatives = []
            if not approved:
                with st.spinner("🤖 Finding best-matching schemes using AI…"):
                    ai_alts      = get_ai_scheme_suggestions(data)
                alternatives = ai_alts if ai_alts else rule_based_alternatives(data)

            pdf_bytes = generate_pdf_report(data, approved, reasons, recs, alternatives)

            if not st.session_state.email_sent:
                ok, msg = send_result_email(
                    data, approved, reasons, recs,
                    alternatives=alternatives,
                    pdf_bytes=pdf_bytes
                )
                st.session_state.email_sent = True
                if ok:
                    st.toast(f"📧 Result emailed to {data.get('email','')}", icon="✅")
                else:
                    st.toast(f"⚠️ Email not sent: {msg}", icon="⚠️")

            st.session_state.result_approved     = approved
            st.session_state.result_reasons      = reasons
            st.session_state.result_recs         = recs
            st.session_state.result_alternatives = alternatives
            st.session_state.result_pdf_bytes    = pdf_bytes

        approved     = st.session_state.result_approved
        reasons      = st.session_state.result_reasons
        recs         = st.session_state.result_recs
        alternatives = st.session_state.result_alternatives
        pdf_bytes    = st.session_state.result_pdf_bytes

        header_col, dl_col = st.columns([3, 1])
        with header_col:
            st.markdown("## 🎯 Application Result")
        with dl_col:
            if pdf_bytes:
                safe_name = scheme.replace(" ", "_")
                st.download_button(
                    label="📥 Download Report",
                    data=pdf_bytes,
                    file_name=f"{safe_name}_Report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            elif not REPORTLAB_AVAILABLE:
                st.caption("Install `reportlab` to enable PDF download.")

        st.divider()
        st.info(f"Thank you, **{data['name']}**! 🎉\n\nYour application for **{scheme}** is being processed.")

        st.markdown("### 📝 Application Summary")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Scheme", scheme)
            st.metric("Annual Income", f"Rs.{data['income']:,}")
        with c2:
            st.metric("Requested Amount", f"Rs.{data['loan_amount']:,}")
            st.metric("Purpose", data['loan_purpose'])
        with c3:
            st.metric("Employment", data['employment'])
            st.metric("Category", data['caste'])

        aadhar_verified = data.get("aadhar_verified", False)
        if isinstance(aadhar_verified, str):
            aadhar_verified = aadhar_verified.lower() == "true"

        if aadhar_verified:
            st.success("✅ Aadhar Verified")
        else:
            st.warning("⚠️ Aadhar Not Verified — This application is flagged for officer review.")

        st.divider()

        st.markdown("### 🏦 Decision")
        if approved:
            st.success(f"✅ **Application Approved** — You are eligible for **{scheme}**!")
        else:
            st.error(f"❌ **Application Rejected** — Your profile does not currently meet the eligibility criteria for **{scheme}**.")

        # ── FIX 4: MODEL LIMITATION NOTE ─────────────────────
        st.caption(
            "Note: This decision is based on a trained ML model and may not reflect actual "
            "government approval criteria. Please verify with official sources before proceeding."
        )

        st.divider()

        st.markdown("### 📊 Decision Explanation")
        income = data.get("income", 0)
        loan   = data.get("loan_amount", 0)

        shap_shown = False
        if SHAP_AVAILABLE and st.session_state.get("_input_data") is not None:
            try:
                m2          = pickle.load(open("models/trained_model.pkl","rb"))
                explainer   = shap.Explainer(m2, st.session_state["_input_data"])
                shap_values = explainer(st.session_state["_input_data"])
                vals        = shap_values.values[0]
                fnames      = ["Income","Loan Amount","Category","Education","Employment"][:len(vals)]
                for fn, fv in zip(fnames, vals):
                    icon = "🟢" if fv > 0 else "🔴"
                    st.write(f"- **{fn}**: {icon} `{fv:+.2f}` ({'positive' if fv>0 else 'negative'} impact)")
                shap_shown = True
            except Exception:
                pass

        if not shap_shown:
            if income >= 300000:
                st.write("🟢 Income is within an acceptable range for most schemes")
            elif income >= 150000:
                st.write("🟡 Income is at the lower threshold — some schemes may need higher income")
            else:
                st.write("🔴 Income below Rs.1,50,000 significantly reduces approval chances")

            if loan == 0:
                st.write("⚠️ No loan amount was specified")
            elif loan <= income * 3:
                st.write("🟢 Requested amount is reasonable relative to your income")
            elif loan <= income * 5:
                st.write("🟡 Loan amount is slightly high relative to income")
            else:
                st.write("🔴 Requested amount is too high relative to your income")

        st.divider()

        if approved:
            st.markdown("### 🌟 Next Steps & Recommendations")
            for rec in recs:
                st.write(f"➡️ {rec}")
        else:
            st.markdown("### ❌ Reasons for Rejection")
            for r in reasons:
                st.write(f"🔴 {r}")

            st.markdown("### 💡 How to Improve Your Chances")
            for rec in recs:
                st.write(f"✅ {rec}")

            st.divider()
            st.markdown("### 🔍 Alternative Schemes Suited to Your Profile")

            if alternatives:
                for idx, s in enumerate(alternatives):
                    name_s   = s.get("name", "")
                    reason_s = s.get("reason", "")
                    tip_s    = s.get("tip", "")
                    st.markdown(f"""
<div class="scheme-alt-card">
  <strong>📌 {name_s}</strong><br>
  <span style="color:#333;">{reason_s}</span><br>
  <span style="color:#185FA5; font-size:13px;">💡 <em>Tip:</em> {tip_s}</span>
</div>
""", unsafe_allow_html=True)
                    if st.button(f"🚀 Apply for {name_s}", key=f"result_alt_{idx}_{name_s[:15]}"):
                        st.session_state.selected_scheme = name_s
                        st.session_state.form_data       = {}
                        st.session_state.result_approved = None
                        st.session_state.email_sent      = False
                        st.session_state.page            = "form"
                        st.rerun()
            else:
                st.info(
                    "No specific alternative schemes matched your current profile. "
                    "You can reapply with updated information or visit your nearest "
                    "**Common Service Centre (CSC)** for personalised guidance."
                )

        st.divider()
        b1, b2 = st.columns(2)
        with b1:
            if st.button("📝 Apply for Another Scheme", use_container_width=True):
                st.session_state.page             = "chat"
                st.session_state.form_data        = {}
                st.session_state.selected_scheme  = ""
                st.session_state.detected_schemes = []
                st.session_state.result_approved  = None
                st.session_state.email_sent       = False
                st.rerun()
        with b2:
            if st.button("🔄 Re-apply with Different Details", use_container_width=True):
                st.session_state.form_data       = {}
                st.session_state.result_approved = None
                st.session_state.email_sent      = False
                st.session_state.page            = "form"
                st.rerun()

        render_fab()