import streamlit as st
import asyncio
import edge_tts
import os
import re
import requests
import uuid
import tempfile
import json
import urllib.parse
import hashlib
import hmac
import io
import csv
from datetime import datetime, timedelta

import pypdf
import speech_recognition as sr
from subscription_manager import SubscriptionManager, get_now_ist, format_iso

# Initialize Subscription Manager Singleton
sm = SubscriptionManager()

st.set_page_config(
    page_title="Wani — Enterprise Multilingual AI Speech & Voiceover Platform",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# THEME STATE SUBSYSTEM (DARK OBSIDIAN / LIGHT PEARL)
# -------------------------------------------------------------
if "theme" not in st.session_state:
    st.session_state.theme = "Dark"

# -------------------------------------------------------------
# SECURITY & USER DATABASE SUBSYSTEM (SALTED SHA-256)
# -------------------------------------------------------------
DB_FILE = os.path.join(os.path.dirname(__file__), "users_db.json")
APP_SALT = "wani_technologies_enterprise_security_salt_2026"

def hash_credential(secret: str) -> str:
    return hashlib.sha256((secret + APP_SALT).encode('utf-8')).hexdigest()

def sanitize_text(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<.*?>', '', clean)
    return clean.strip()

def load_secure_users():
    today_str = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists(DB_FILE):
        default_db = {
            "vishal@wani.ai": {
                "name": "Vishal Hargude (Founder & CEO)",
                "password_hash": hash_credential("admin"),
                "mobile": "+91 98220 54321",
                "plan": "STUDIO BUSINESS 🚀",
                "trials_used_today": 0,
                "last_trial_date": today_str,
                "credits": 999999,
                "is_admin": True,
                "joined": "2026-10-18"
            },
            "creator@wani.ai": {
                "name": "Creator Pro Member",
                "password_hash": hash_credential("pro123"),
                "mobile": "+91 98220 12345",
                "plan": "PRO CREATOR 👑",
                "trials_used_today": 0,
                "last_trial_date": today_str,
                "credits": 999999,
                "is_admin": False,
                "joined": "2026-10-18"
            },
            "guest@wani.ai": {
                "name": "Guest Explorer (Free Trial)",
                "password_hash": hash_credential("demo"),
                "mobile": "+91 98220 99999",
                "plan": "FREE TRIAL 🎁",
                "trials_used_today": 0,
                "last_trial_date": today_str,
                "credits": 2,
                "is_admin": False,
                "joined": "2026-10-19"
            }
        }
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(default_db, f, ensure_ascii=False, indent=2)
        return default_db
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            updated = False
            for email, uinfo in data.items():
                if "password" in uinfo and "password_hash" not in uinfo:
                    uinfo["password_hash"] = hash_credential(uinfo["password"])
                    del uinfo["password"]
                    updated = True
                if "trials_used_today" not in uinfo:
                    uinfo["trials_used_today"] = 0
                    uinfo["last_trial_date"] = today_str
                    updated = True
            if "vishal@wani.ai" not in data:
                data["vishal@wani.ai"] = {
                    "name": "Vishal Hargude (Founder & CEO)",
                    "password_hash": hash_credential("admin"),
                    "mobile": "+91 98220 54321",
                    "plan": "STUDIO BUSINESS 🚀",
                    "trials_used_today": 0,
                    "last_trial_date": today_str,
                    "credits": 999999,
                    "is_admin": True,
                    "joined": "2026-10-18"
                }
                updated = True
            if "guest@wani.ai" not in data:
                data["guest@wani.ai"] = {
                    "name": "Guest Explorer (Free Trial)",
                    "password_hash": hash_credential("demo"),
                    "mobile": "+91 98220 99999",
                    "plan": "FREE TRIAL 🎁",
                    "trials_used_today": 0,
                    "last_trial_date": today_str,
                    "credits": 2,
                    "is_admin": False,
                    "joined": today_str
                }
                updated = True
            if updated:
                with open(DB_FILE, "w", encoding="utf-8") as fw:
                    json.dump(data, fw, ensure_ascii=False, indent=2)
            return data
    except Exception:
        return {}

def save_secure_users(users):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users_db = load_secure_users()

# Active Session State
if "current_user" not in st.session_state:
    admin_user = users_db.get("vishal@wani.ai", {
        "name": "Vishal Hargude (Founder & CEO)",
        "email": "vishal@wani.ai",
        "plan": "STUDIO BUSINESS 🚀",
        "credits": 999999,
        "is_admin": True
    })
    st.session_state.current_user = admin_user
    st.session_state.current_user["email"] = "vishal@wani.ai"

active_email = st.session_state.current_user.get("email", "guest@wani.ai")
entitlements = sm.get_user_entitlements(active_email)

# -------------------------------------------------------------
# SERVER-SIDE QUOTA ENFORCEMENT & PRE-REQUEST GATEKEEPER
# -------------------------------------------------------------
def validate_user_trial(user_email: str, script_text: str):
    words = len(script_text.strip().split())
    paragraphs = max(1, len([p for p in script_text.strip().split("\n") if p.strip()]))
    ent = sm.get_user_entitlements(user_email)
    
    if ent.get("warning_message"):
        st.warning(ent["warning_message"])
        
    ok, msg, qdata = sm.check_and_deduct_quota(user_email, words=words, paragraphs=paragraphs)
    return ok, msg, qdata

# -------------------------------------------------------------
# MULTI-LINGUAL TRANSLATION ENGINE
# -------------------------------------------------------------
def translate_text(text: str, source='auto', target='mr') -> str:
    cleaned = sanitize_text(text)
    if not cleaned:
        return ""
    try:
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(cleaned)}&langpair={source}|{target}"
        r = requests.get(url, timeout=12)
        if r.status_code == 200:
            res = r.json()
            trans = res.get('responseData', {}).get('translatedText', '')
            if trans and "MYMEMORY WARNING" not in trans:
                return trans
    except Exception:
        pass
    return cleaned

# -------------------------------------------------------------
# PDF TEXT EXTRACTION & AUTO-LANGUAGE DETECTION
# -------------------------------------------------------------
def extract_text_from_pdf(pdf_file_bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_file_bytes))
    full_text = []
    for i, page in enumerate(reader.pages):
        txt = page.extract_text()
        if txt:
            full_text.append(txt.strip())
    return "\n\n".join(full_text)

def detect_language_safe(text: str) -> tuple[str, str]:
    if not text or not text.strip():
        return "en", "English 🌐"
    
    # 1. Authentic Marathi marker 'ळ' (Retroflex Lateral)
    if 'ळ' in text:
        return "mr", "Marathi (मराठी) 🚩"
        
    # 2. Devanagari script evaluation
    if any('\u0900' <= c <= '\u097F' for c in text):
        marathi_markers = ["आहे", "आणि", "नाही", "होते", "झाले", "केले", "यांचे", "म्हणून", "त्यांच्या", "असेल", "झाला"]
        if any(m in text for m in marathi_markers):
            return "mr", "Marathi (मराठी) 🚩"
        return "hi", "Hindi (हिंदी) 🇮🇳"
        
    if any('\u0A80' <= c <= '\u0AFF' for c in text):
        return "gu", "Gujarati (ગુજરાતી) 🇮🇳"
    if any('\u0B80' <= c <= '\u0BFF' for c in text):
        return "ta", "Tamil (தமிழ்) 🇮🇳"
    if any('\u0C00' <= c <= '\u0C7F' for c in text):
        return "te", "Telugu (తెలుగు) 🇮🇳"
    if any('\u0980' <= c <= '\u09FF' for c in text):
        return "bn", "Bengali (বাংলা) 🇮🇳"
    if any('\u4E00' <= c <= '\u9FFF' or '\u3040' <= c <= '\u30FF' for c in text):
        return "ja", "Japanese (日本語) 🇯🇵"
        
    try:
        from langdetect import detect
        code = detect(text[:1200])
        code_map = {
            "mr": ("mr", "Marathi (मराठी) 🚩"),
            "hi": ("hi", "Hindi (हिंदी) 🇮🇳"),
            "en": ("en", "English 🌐"),
            "es": ("es", "Spanish (Español) 🇪🇸"),
            "fr": ("fr", "French (Français) 🇫🇷"),
            "de": ("de", "German (Deutsch) 🇩🇪"),
            "ja": ("ja", "Japanese (日本語) 🇯🇵"),
            "gu": ("gu", "Gujarati (ગુજરાતી) 🇮🇳"),
            "ta": ("ta", "Tamil (தமிழ்) 🇮🇳"),
            "te": ("te", "Telugu (తెలుగు) 🇮🇳"),
            "bn": ("bn", "Bengali (বাংলা) 🇮🇳"),
            "ar": ("ar", "Arabic (العربية) 🇸🇦"),
            "ru": ("ru", "Russian (Русский) 🇷🇺")
        }
        return code_map.get(code, ("en", "English 🌐"))
    except Exception:
        return "en", "English 🌐"

# -------------------------------------------------------------
# UNIVERSAL DESIGN: STRICT JOSEFIN SANS + DUAL THEME + CODE SHIELD
# -------------------------------------------------------------
is_dark = (st.session_state.theme == "Dark")

if is_dark:
    theme_bg = "#080C14"
    theme_card_bg = "#0E1422"
    theme_card_border = "#1E293B"
    theme_text = "#F8FAFC"
    theme_subtext = "#94A3B8"
    theme_nav_bg = "#0B101C"
    theme_featured_bg = "linear-gradient(180deg, #1A1F36 0%, #0F1322 100%)"
    theme_featured_border = "#6366F1"
    theme_shadow = "0 8px 24px rgba(0, 0, 0, 0.55)"
    theme_input_bg = "#0F1626"
    theme_input_border = "#1E293B"
else:
    theme_bg = "#F8FAFC"
    theme_card_bg = "#FFFFFF"
    theme_card_border = "#E2E8F0"
    theme_text = "#0F172A"
    theme_subtext = "#475569"
    theme_nav_bg = "#FFFFFF"
    theme_featured_bg = "linear-gradient(180deg, #F5F7FF 0%, #FFFFFF 100%)"
    theme_featured_border = "#4F46E5"
    theme_shadow = "0 4px 16px rgba(0, 0, 0, 0.05)"
    theme_input_bg = "#FFFFFF"
    theme_input_border = "#CBD5E1"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Josefin+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400;1,600&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap');
    
    /* 100% UNIVERSAL JOSEFIN SANS TYPOGRAPHY ACROSS ENTIRE PLATFORM */
    * {{
        font-family: 'Josefin Sans', 'Noto Sans Devanagari', -apple-system, sans-serif !important;
    }}
    
    html, body, [class*="css"], [class*="st-"], .stApp, button, input, textarea, select, 
    h1, h2, h3, h4, h5, h6, p, span, div, a, label, li, code, pre, .stMarkdown, 
    [data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"], 
    .stTabs [data-baseweb="tab"], .stTabs [data-baseweb="tab-list"], 
    .stMetric, [data-testid="stMetricValue"], [data-testid="stMetricLabel"] {{
        font-family: 'Josefin Sans', 'Noto Sans Devanagari', -apple-system, sans-serif !important;
    }}
    
    /* COMPLETE CODE & BRAND WHITELABELING: HIDE GITHUB ICON & STREAMLIT CLOUD BADGES */
    header[data-testid="stHeader"], [data-testid="stHeader"] {{
        visibility: hidden !important;
        display: none !important;
        height: 0 !important;
    }}
    [data-testid="stToolbar"] {{
        visibility: hidden !important;
        display: none !important;
        height: 0 !important;
    }}
    [data-testid="stDecoration"] {{
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
    }}
    [data-testid="stStatusWidget"] {{
        display: none !important;
        visibility: hidden !important;
    }}
    #MainMenu, footer {{
        visibility: hidden !important;
        display: none !important;
        height: 0 !important;
    }}
    .stAppDeployButton, [data-testid="stAppDeployButton"] {{
        display: none !important;
        visibility: hidden !important;
    }}
    a[href*="github.com"] {{
        display: none !important;
        visibility: hidden !important;
    }}
    button[title*="View app source"] {{
        display: none !important;
        visibility: hidden !important;
    }}
    [class*="viewerBadge"] {{
        display: none !important;
        visibility: hidden !important;
    }}
    [class*="manageAppButton"] {{
        display: none !important;
        visibility: hidden !important;
    }}
    
    /* THEME BASE CONTAINER */
    .stApp {{
        background-color: {theme_bg} !important;
        color: {theme_text} !important;
    }}
    
    /* INPUTS & TEXTAREAS COMPATIBILITY */
    .stTextInput input, .stTextArea textarea {{
        background-color: {theme_input_bg} !important;
        color: {theme_text} !important;
        border: 1px solid {theme_input_border} !important;
        border-radius: 6px !important;
        font-family: 'Josefin Sans', 'Noto Sans Devanagari', sans-serif !important;
    }}
    
    .stSelectbox div[data-baseweb="select"] {{
        background-color: {theme_input_bg} !important;
        color: {theme_text} !important;
        border-color: {theme_input_border} !important;
    }}
    
    /* SIDEBAR COMPATIBILITY */
    section[data-testid="stSidebar"] {{
        background-color: {theme_card_bg} !important;
        border-right: 1px solid {theme_card_border} !important;
    }}
    section[data-testid="stSidebar"] * {{
        color: {theme_text} !important;
    }}
    
    /* TABS STYLING */
    .stTabs [data-baseweb="tab-list"] {{
        border-bottom: 1px solid {theme_card_border} !important;
        gap: 6px;
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {theme_subtext} !important;
        font-weight: 600 !important;
        font-size: 13.5px !important;
        padding: 8px 14px !important;
    }}
    .stTabs [aria-selected="true"] {{
        color: #6366F1 !important;
        border-bottom: 2px solid #6366F1 !important;
    }}
    
    /* TOP LEFT-ALIGNED BRAND HEADER BAR WITH MICROPHONE SYMBOL */
    .top-nav-bar {{
        background: {theme_nav_bg};
        border: 1px solid {theme_card_border};
        border-radius: 12px;
        padding: 12px 24px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 16px;
        box-shadow: {theme_shadow};
    }}
    
    .brand-left-group {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    
    .wani-brand-text {{
        font-size: 38px;
        font-weight: 700;
        letter-spacing: -1px;
        background: linear-gradient(135deg, #FF6B6B 0%, #9B51E0 50%, #4A90E2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline-block;
        line-height: 1;
        font-family: 'Josefin Sans', sans-serif !important;
    }}
    
    .mic-symbol {{
        font-size: 28px;
        background: linear-gradient(135deg, #FF6B6B, #9B51E0);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 2px 8px rgba(155, 81, 224, 0.4));
        display: inline-block;
    }}
    
    .brand-divider {{
        color: {theme_card_border};
        font-size: 24px;
        font-weight: 300;
        margin: 0 4px;
    }}
    
    .wani-tagline-inline {{
        font-size: 11px;
        letter-spacing: 2.2px;
        color: {theme_subtext};
        text-transform: uppercase;
        font-weight: 600;
        font-family: 'Josefin Sans', sans-serif !important;
    }}
    
    /* SILICON VALLEY SOCIAL PROOF BANNER */
    .us-social-proof {{
        background: {theme_card_bg};
        border: 1px solid {theme_card_border};
        border-radius: 8px;
        padding: 8px 18px;
        margin-bottom: 20px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
        font-size: 12px;
        color: {theme_subtext};
    }}
    
    .user-pill {{
        background: {theme_card_bg};
        border: 1px solid {theme_card_border};
        border-radius: 20px;
        padding: 5px 14px;
        font-size: 12.5px;
        font-weight: 600;
        color: {theme_text};
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }}
    
    /* CARDS & BANNERS */
    .studio-banner {{
        background: {theme_card_bg};
        border: 1px solid {theme_card_border};
        border-radius: 10px;
        padding: 12px 18px;
        font-weight: 600;
        font-size: 14px;
        color: {theme_text};
        margin-bottom: 18px;
        box-shadow: {theme_shadow};
    }}
    
    .pricing-card {{
        background: {theme_card_bg};
        border: 1px solid {theme_card_border};
        border-radius: 12px;
        padding: 22px 18px;
        text-align: center;
        box-shadow: {theme_shadow};
        transition: transform 0.2s ease, border-color 0.2s ease;
        color: {theme_text};
    }}
    
    .pricing-card:hover {{
        transform: translateY(-3px);
        border-color: #6366F1;
    }}
    
    .pricing-featured {{
        background: {theme_featured_bg};
        border: 2px solid {theme_featured_border};
    }}
    
    .voice-card {{
        background: {theme_card_bg};
        border: 1px solid {theme_card_border};
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 12px;
        box-shadow: {theme_shadow};
        color: {theme_text};
    }}
    
    .avatar-frame {{
        width: 82px;
        height: 82px;
        border-radius: 50%;
        object-fit: cover;
        border: 2.5px solid #6366F1;
        box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
    }}
    
    .badge-cat {{
        background: rgba(99, 102, 241, 0.15);
        color: #818CF8;
        padding: 3px 9px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        margin-right: 8px;
    }}
    
    .status-badge-active {{
        background: rgba(16, 185, 129, 0.15);
        color: #10B981;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 700;
    }}
    
    .status-badge-grace {{
        background: rgba(245, 158, 11, 0.15);
        color: #F59E0B;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 700;
    }}
    
    .status-badge-halted {{
        background: rgba(239, 68, 68, 0.15);
        color: #EF4444;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 700;
    }}
    
    /* CORPORATE FOOTER */
    .enterprise-footer {{
        margin-top: 45px;
        border-top: 1px solid {theme_card_border};
        padding: 24px 0 16px 0;
    }}
</style>
""", unsafe_allow_html=True)

# User Identity & Entitlements
user_info = st.session_state.current_user
user_name = user_info.get("name", "Guest")
user_email_active = user_info.get("email", "guest@wani.ai")
current_entitlements = sm.get_user_entitlements(user_email_active)
plan_badge = current_entitlements.get("badge", "FREE TRIAL 🎁")
status_code = current_entitlements.get("status", "free")

if status_code == "active":
    status_html = '<span class="status-badge-active">ACTIVE 🟢</span>'
elif "grace" in status_code:
    status_html = f'<span class="status-badge-grace">GRACE PERIOD ⚠️ ({current_entitlements.get("grace_days_remaining", 1)}d left)</span>'
elif "halted" in status_code or "expired" in status_code:
    status_html = '<span class="status-badge-halted">HALTED 🛑</span>'
elif "cancel" in status_code:
    status_html = '<span class="status-badge-grace">PENDING EXPIRY 🔴</span>'
else:
    status_html = '<span class="badge-cat">FREE TIER 🎁</span>'

# TOP LEFT-ALIGNED ENTERPRISE NAVIGATION BAR WITH MICROPHONE SYMBOL
st.markdown(f"""
<div class="top-nav-bar protected-brand">
    <div class="brand-left-group">
        <span class="wani-brand-text">Wani</span>
        <span class="mic-symbol">🎙️</span>
        <span class="brand-divider">/</span>
        <span class="wani-tagline-inline">The Voice of Intelligence • Neural Acoustic Studio</span>
    </div>
    <div style="display: flex; align-items: center; gap: 12px;">
        <div class="user-pill">
            <span>👤 {user_name.split('(')[0].strip()}</span>
            <span>|</span>
            <span style="color:#818CF8;">{plan_badge}</span>
            <span>|</span>
            {status_html}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# SILICON VALLEY HIGH-IMPACT SOCIAL PROOF BANNER
st.markdown(f"""
<div class="us-social-proof protected-brand">
    <div>
        <span style="color:#10B981; font-weight:700;">● 1.2M+ Active Creators</span>
        <span style="margin: 0 10px;">•</span>
        <span>Trusted across 140+ Countries</span>
        <span style="margin: 0 10px;">•</span>
        <span><b>4.9/5 Rating</b> (58,000+ Reviews)</span>
    </div>
    <div>
        <span style="color:#818CF8; font-weight:600;">⚡ 180M+ Voice Minutes Generated</span>
        <span style="margin: 0 10px;">•</span>
        <span>SOC-2 Type II & ISO 27001 Infrastructure</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Quick Controls Bar (Theme Toggle)
col_head1, col_head2 = st.columns([8, 2])
with col_head2:
    theme_btn_label = "☀️ Switch to Light Pearl" if is_dark else "🌙 Switch to Dark Obsidian"
    if st.button(theme_btn_label, use_container_width=True, key="top_theme_toggle_btn"):
        st.session_state.theme = "Light" if is_dark else "Dark"
        st.rerun()

# -------------------------------------------------------------
# SIDEBAR NAVIGATION
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎙️ Wani Studio Control")
    st.markdown(f"**Account:** `{user_name.split('(')[0].strip()}`")
    st.markdown(f"**Email:** `{user_email_active}`")
    st.markdown(f"**Plan Tier:** `{plan_badge}`")
    
    st.markdown("---")
    st.markdown("#### 🎨 Display Theme")
    theme_choice = st.radio("Interface Theme:", ["🌙 Dark Obsidian", "☀️ Light Pearl"], 
                            index=0 if is_dark else 1, horizontal=True, key="sb_theme_radio")
    if "Dark" in theme_choice and not is_dark:
        st.session_state.theme = "Dark"
        st.rerun()
    elif "Light" in theme_choice and is_dark:
        st.session_state.theme = "Light"
        st.rerun()

    st.markdown("---")
    cust_data = sm.get_customer_dashboard_data(user_email_active)
    q = cust_data["quotas"]
    
    if current_entitlements.get("is_paid", False):
        st.markdown("#### 📊 Monthly Usage Quota")
        st.caption(f"Words: {q['words_used']:,} / {q['words_quota']:,}")
        st.progress(q['words_percent'] / 100.0)
        
        st.caption(f"Paragraphs: {q['paragraphs_used']} / {q['paragraphs_quota']}")
        st.progress(q['paragraphs_percent'] / 100.0)
        
        st.caption(f"Translations: {q['translations_used']} / {q['translations_quota']}")
        st.progress(q['translations_percent'] / 100.0)
        
        sub_d = current_entitlements.get("subscription_details") or {}
        if sub_d.get("current_period_end"):
            st.caption(f"Next Billing: `{sub_d['current_period_end'].split('T')[0]}`")
    else:
        st.markdown(f"**Daily Free Trials:** `{2 - q['daily_trials_today']}` of `2` remaining today")
        st.caption("Max 100 words per generation on Free Trial.")
        st.info("💡 Upgrade to **Starter (₹299/mo)** or **Pro (₹699/mo)** for high-volume limits.")

    st.markdown("---")
    st.markdown("#### 📲 Share Wani")
    share_msg = "Experience Wani AI - the world's most advanced multilingual AI voice platform: https://wani-ai.streamlit.app"
    st.markdown(f'''<a href="https://api.whatsapp.com/send?text={urllib.parse.quote(share_msg)}" target="_blank" style="text-decoration:none;"><div style="background:#25D366; color:white; padding:9px 12px; border-radius:6px; font-weight:700; text-align:center; margin-bottom:15px; font-size:13px;">📲 Share on WhatsApp</div></a>''', unsafe_allow_html=True)

    st.markdown("---")
    st.caption("🛡️ Proprietary Software of Wani Technologies Pvt. Ltd. | 256-Bit SSL Encrypted | IT Act 2000 Compliant")

# ==============================================================
# 20 DISTINCT STUDIO CHARACTER PERSONAS (10 MALE + 10 FEMALE WITH AVATARS)
# ==============================================================
STUDIO_PERSONAS = {
    # 10 MALE PERSONAS
    "Aarav — Historic Authority (Warrior Baritone)": {
        "gender": "Male", "category": "Historical & Epic",
        "avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-28Hz", "rate": "-6%",
        "desc": "Ultra-heavy thunderous baritone with deep historic resonance and gravelly authority.",
        "voice_map": {"mr": "mr-IN-ManoharNeural", "hi": "hi-IN-MadhurNeural", "en": "en-US-ChristopherNeural", "default": "mr-IN-ManoharNeural"}
    },
    "Vikram — Hollywood Trailer (Sub-Woofer Bass)": {
        "gender": "Male", "category": "Cinematic & Drama",
        "avatar": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-35Hz", "rate": "-10%",
        "desc": "Sub-woofer level resonant trailer titan bass for monumental cinema announcements.",
        "voice_map": {"mr": "mr-IN-ManoharNeural", "hi": "hi-IN-MadhurNeural", "en": "en-US-ChristopherNeural", "default": "mr-IN-ManoharNeural"}
    },
    "Marcus — Silicon Valley Keynote (Charismatic)": {
        "gender": "Male", "category": "Corporate & Enterprise",
        "avatar": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=300&h=300&fit=crop&crop=faces",
        "pitch": "+2Hz", "rate": "+4%",
        "desc": "Clean, charismatic, tech visionary presentation cadence for corporate demos.",
        "voice_map": {"mr": "mr-IN-ManoharNeural", "hi": "hi-IN-MadhurNeural", "en": "en-US-GuyNeural", "default": "en-US-GuyNeural"}
    },
    "Kabir — Resolute Heritage (Patriotic Gravitas)": {
        "gender": "Male", "category": "Historical & Epic",
        "avatar": "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-22Hz", "rate": "-6%",
        "desc": "Steadfast, heroic defender baritone with resolute conviction and presence.",
        "voice_map": {"mr": "mr-IN-ManoharNeural", "hi": "hi-IN-MadhurNeural", "en": "en-GB-RyanNeural", "default": "mr-IN-ManoharNeural"}
    },
    "Anup — Mystery & Thriller (Suspense Anchor)": {
        "gender": "Male", "category": "Crime & Thriller",
        "avatar": "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-16Hz", "rate": "-8%",
        "desc": "Tense, investigative narration style tailored for unsolved mysteries and noir fiction.",
        "voice_map": {"mr": "mr-IN-ManoharNeural", "hi": "hi-IN-MadhurNeural", "en": "en-US-EricNeural", "default": "mr-IN-ManoharNeural"}
    },
    "Rohan — Primetime News (Urgent Desk Anchor)": {
        "gender": "Male", "category": "News & Broadcast",
        "avatar": "https://images.unsplash.com/photo-1522075469751-3a6694fb2f61?w=300&h=300&fit=crop&crop=faces",
        "pitch": "+8Hz", "rate": "+18%",
        "desc": "Fast-paced, urgent broadcast delivery for breaking news and political bulletins.",
        "voice_map": {"mr": "mr-IN-ManoharNeural", "hi": "hi-IN-MadhurNeural", "en": "en-US-RogerNeural", "default": "mr-IN-ManoharNeural"}
    },
    "Brian — BBC Prestige (British Documentary)": {
        "gender": "Male", "category": "Documentary & Nature",
        "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-12Hz", "rate": "-6%",
        "desc": "Distinguished British prestige baritone for global nature and history sagas.",
        "voice_map": {"mr": "mr-IN-ManoharNeural", "hi": "hi-IN-MadhurNeural", "en": "en-GB-RyanNeural", "default": "en-GB-RyanNeural"}
    },
    "Sagar — Dynamic FM Host (Commercial RJ)": {
        "gender": "Male", "category": "Broadcast & Media",
        "avatar": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=300&h=300&fit=crop&crop=faces",
        "pitch": "+22Hz", "rate": "+14%",
        "desc": "High-pitch, energetic, upbeat host delivery crafted for viral Reels and commercial radio.",
        "voice_map": {"mr": "mr-IN-ManoharNeural", "hi": "hi-IN-MadhurNeural", "en": "en-US-RogerNeural", "default": "mr-IN-ManoharNeural"}
    },
    "Christopher — Monumental Cinematic Storyteller": {
        "gender": "Male", "category": "Cinematic & Drama",
        "avatar": "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-30Hz", "rate": "-8%",
        "desc": "Deep cinematic baritone for monumental trailers, audiobooks, and dramatic voiceovers.",
        "voice_map": {"mr": "mr-IN-ManoharNeural", "hi": "hi-IN-MadhurNeural", "en": "en-US-ChristopherNeural", "default": "en-US-ChristopherNeural"}
    },
    "Eshwar — Elder Patriarch (Measured Wisdom)": {
        "gender": "Male", "category": "Documentary & Wisdom",
        "avatar": "https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-26Hz", "rate": "-14%",
        "desc": "Slow, aged baritone filled with lifelong wisdom for folklore and contemplative scripts.",
        "voice_map": {"mr": "mr-IN-ManoharNeural", "hi": "hi-IN-MadhurNeural", "en": "en-US-GuyNeural", "default": "mr-IN-ManoharNeural"}
    },

    # 10 FEMALE PERSONAS
    "Aarohi — Stately Empress (Royal Dignity)": {
        "gender": "Female", "category": "Historical & Epic",
        "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-20Hz", "rate": "-8%",
        "desc": "Deep, commanding maternal matriarch voice resonant with strategic valor.",
        "voice_map": {"mr": "mr-IN-AarohiNeural", "hi": "hi-IN-SwaraNeural", "en": "en-GB-SoniaNeural", "default": "mr-IN-AarohiNeural"}
    },
    "Jenny — Global Financial Anchor (Executive)": {
        "gender": "Female", "category": "News & Broadcast",
        "avatar": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=300&h=300&fit=crop&crop=faces",
        "pitch": "+6Hz", "rate": "+12%",
        "desc": "Immaculate corporate broadcast voice for financial summits and B2B reports.",
        "voice_map": {"mr": "mr-IN-AarohiNeural", "hi": "hi-IN-SwaraNeural", "en": "en-US-JennyNeural", "default": "en-US-JennyNeural"}
    },
    "Ananya — National News Anchor (Assertive Desk)": {
        "gender": "Female", "category": "News & Broadcast",
        "avatar": "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=300&h=300&fit=crop&crop=faces",
        "pitch": "+10Hz", "rate": "+16%",
        "desc": "Rapid, crisp, assertive news delivery for breaking news and prime-time broadcasts.",
        "voice_map": {"mr": "mr-IN-AarohiNeural", "hi": "hi-IN-SwaraNeural", "en": "en-US-JennyNeural", "default": "mr-IN-AarohiNeural"}
    },
    "Emma — Theatrical Literature (Classic Drama)": {
        "gender": "Female", "category": "Documentary & Nature",
        "avatar": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-8Hz", "rate": "-6%",
        "desc": "Intense theatrical delivery for cinematic drama, poetry, and classical audiobooks.",
        "voice_map": {"mr": "mr-IN-AarohiNeural", "hi": "hi-IN-SwaraNeural", "en": "en-GB-SoniaNeural", "default": "en-GB-SoniaNeural"}
    },
    "Tara — Serene Guided ASMR & Mindfulness": {
        "gender": "Female", "category": "Mindfulness & Sleep",
        "avatar": "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-12Hz", "rate": "-14%",
        "desc": "Soothing, gentle whisper cadence for stress relief, yoga, and guided rest.",
        "voice_map": {"mr": "mr-IN-AarohiNeural", "hi": "hi-IN-SwaraNeural", "en": "en-IN-NeerjaNeural", "default": "mr-IN-AarohiNeural"}
    },
    "Priya — Commercial Producer (Viral Lifestyle Host)": {
        "gender": "Female", "category": "Broadcast & Media",
        "avatar": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=300&h=300&fit=crop&crop=faces",
        "pitch": "+24Hz", "rate": "+16%",
        "desc": "Bright, playful, ultra-trendy tone designed for viral lifestyle reels and podcasts.",
        "voice_map": {"mr": "mr-IN-AarohiNeural", "hi": "hi-IN-SwaraNeural", "en": "en-US-JennyNeural", "default": "mr-IN-AarohiNeural"}
    },
    "Sonia — Sleep & Deep Relaxation Guide": {
        "gender": "Female", "category": "Mindfulness & Sleep",
        "avatar": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-14Hz", "rate": "-12%",
        "desc": "Warm, restorative, breathy cadence for bedtime routines and meditation.",
        "voice_map": {"mr": "mr-IN-AarohiNeural", "hi": "hi-IN-SwaraNeural", "en": "en-IN-NeerjaNeural", "default": "en-IN-NeerjaNeural"}
    },
    "Shreya — Cultural Storyteller (Heritage Warmth)": {
        "gender": "Female", "category": "Documentary & Wisdom",
        "avatar": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-16Hz", "rate": "-14%",
        "desc": "Affectionate, experienced narrative tone for timeless bedtime stories and parables.",
        "voice_map": {"mr": "mr-IN-AarohiNeural", "hi": "hi-IN-SwaraNeural", "en": "en-GB-SoniaNeural", "default": "mr-IN-AarohiNeural"}
    },
    "Gauri — National Geographic Documentary Host": {
        "gender": "Female", "category": "Documentary & Nature",
        "avatar": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?w=300&h=300&fit=crop&crop=faces",
        "pitch": "-4Hz", "rate": "-4%",
        "desc": "Elegant, informative cadence for travelogues, documentaries, and nature programs.",
        "voice_map": {"mr": "mr-IN-AarohiNeural", "hi": "hi-IN-SwaraNeural", "en": "en-US-JennyNeural", "default": "mr-IN-AarohiNeural"}
    },
    "Diya — Animation & Character Fantasy Voice": {
        "gender": "Female", "category": "Kids & Animation",
        "avatar": "https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?w=300&h=300&fit=crop&crop=faces",
        "pitch": "+30Hz", "rate": "+10%",
        "desc": "Enchanting fairy tale and animated cartoon voice for children's stories.",
        "voice_map": {"mr": "mr-IN-AarohiNeural", "hi": "hi-IN-SwaraNeural", "en": "en-US-AnaNeural", "default": "en-US-AnaNeural"}
    }
}

LANGUAGE_CATALOG = {
    "Marathi (मराठी) 🚩": {"code": "mr", "male": "mr-IN-ManoharNeural", "female": "mr-IN-AarohiNeural"},
    "Hindi (हिंदी) 🇮🇳": {"code": "hi", "male": "hi-IN-MadhurNeural", "female": "hi-IN-SwaraNeural"},
    "English (US & Global) 🌐": {"code": "en", "male": "en-US-ChristopherNeural", "female": "en-US-JennyNeural"},
    "Gujarati (ગુજરાતી) 🇮🇳": {"code": "gu", "male": "gu-IN-NiranjanNeural", "female": "gu-IN-DhwaniNeural"},
    "Tamil (தமிழ்) 🇮🇳": {"code": "ta", "male": "ta-IN-ValluvarNeural", "female": "ta-IN-PallaviNeural"},
    "Telugu (తెలుగు) 🇮🇳": {"code": "te", "male": "te-IN-MohanNeural", "female": "te-IN-ShrutiNeural"},
    "Kannada (ಕನ್ನಡ) 🇮🇳": {"code": "kn", "male": "kn-IN-GaganNeural", "female": "kn-IN-SapnaNeural"},
    "Bengali (বাংলা) 🇮🇳": {"code": "bn", "male": "bn-IN-BashkarNeural", "female": "bn-IN-TanishaaNeural"},
    "Spanish (Español) 🇪🇸": {"code": "es", "male": "es-ES-AlvaroNeural", "female": "es-ES-ElviraNeural"},
    "French (Français) 🇫🇷": {"code": "fr", "male": "fr-FR-HenriNeural", "female": "fr-FR-DeniseNeural"},
    "German (Deutsch) 🇩🇪": {"code": "de", "male": "de-DE-ConradNeural", "female": "de-DE-KatjaNeural"},
    "Japanese (日本語) 🇯🇵": {"code": "ja", "male": "ja-JP-KeitaNeural", "female": "ja-JP-NanamiNeural"},
    "Arabic (العربية) 🇸🇦": {"code": "ar", "male": "ar-SA-HamedNeural", "female": "ar-SA-ZariyahNeural"},
    "Russian (Русский) 🇷🇺": {"code": "ru", "male": "ru-RU-DmitryNeural", "female": "ru-RU-SvetlanaNeural"}
}

PURPOSE_PRESETS = {
    "Standard Studio (Natural Fidelity)": {"pitch_offset": 0, "rate_offset": 0, "desc": "Clean, balanced, natural studio acoustic cadence."},
    "🎬 Documentary & History (Deep Gravity)": {"pitch_offset": -16, "rate_offset": -8, "desc": "Grave, reflective, atmospheric delivery for historical sagas."},
    "🌌 Cinematic Movie Trailer (Titan Bass)": {"pitch_offset": -22, "rate_offset": -10, "desc": "Monumental resonance and bass rumble for film teasers."},
    "😂 Comedy & Satire (Playful Timing)": {"pitch_offset": 18, "rate_offset": 12, "desc": "High-bounce, punchy cadence with crisp comedic timing."},
    "📻 FM Radio Jockey (High Energy Host)": {"pitch_offset": 6, "rate_offset": 8, "desc": "Warm, acoustically rich FM broadcast tone with intimacy."},
    "📰 Breaking News Desk (Fast & Authoritative)": {"pitch_offset": 8, "rate_offset": 18, "desc": "Fast-paced, urgent, authoritative news bulletin style."},
    "🧘 Mindfulness & Meditation (Soothing Calm)": {"pitch_offset": -14, "rate_offset": -16, "desc": "Breathy, hypnotic, soothing cadence for wellness and sleep."},
    "🛒 Commercials & Brand Ads (High Conversion)": {"pitch_offset": 12, "rate_offset": 10, "desc": "Punchy hook delivery engineered for viral retention."}
}

# Core synthesis function (100% white-labeled)
def synthesize_speech_core(text: str, voice_code: str, out_path: str, pitch_str: str = "+0Hz", rate_str: str = "+0%"):
    clean_text = sanitize_text(text)
    clean_text = re.sub(r'([।!?\.])', r'\1 ', clean_text)
    
    async def run_core():
        comm = edge_tts.Communicate(clean_text, voice_code, rate=rate_str, pitch=pitch_str)
        await comm.save(out_path)
        
    asyncio.run(run_core())
    return "Wani Neural Matrix v4.8 (Quantum Acoustic Core)"

# ==============================================================
# WANI ENTERPRISE STUDIO TABS
# ==============================================================
tab_speech, tab_pdf, tab_stt, tab_dubbing, tab_dialogue, tab_pricing, tab_billing, tab_admin, tab_auth, tab_contact, tab_library = st.tabs([
    "🎙️ Universal Voice Studio",
    "📄 PDF & Document Reader",
    "🎤 Voice-to-Text (Transcribe)",
    "🎬 AI Video Dubbing Studio",
    "🎭 Multi-Voice Dialogue Studio",
    "💳 Subscription Plans",
    "📑 Customer Billing Dashboard",
    "👑 Admin Subscription CRM",
    "🔐 Account & Access",
    "🏢 Enterprise & Global HQs",
    "🎧 Voice Library Catalog"
])

# ==============================================================
# TAB 1: UNIVERSAL VOICE STUDIO (ALL LANGUAGES UNIFIED)
# ==============================================================
with tab_speech:
    st.markdown('<div class="studio-banner">🎙️ Universal Voice Studio — Unified Multilingual Acoustic Architecture with 20 Distinct Character Personas</div>', unsafe_allow_html=True)
    
    col_u1, col_u2 = st.columns([1.4, 1])
    
    with col_u1:
        # Script Input Area
        speech_text = st.text_area(
            "Script Input (Enter any text in Marathi, Hindi, English or 20+ Languages):",
            value="छत्रपती शिवाजी महाराजांच्या पदस्पर्शाने पावन झालेली ही भूमी, आकाशाला गवसणी घालणारा मराठ्यांचा स्वाभिमान आणि सह्याद्रीची अखंड गर्जना!",
            height=180,
            key="universal_script_input"
        )
        
        c_lan1, c_lan2 = st.columns(2)
        with c_lan1:
            selected_lang_name = st.selectbox("Synthesis Language:", list(LANGUAGE_CATALOG.keys()), index=0, key="u_lang_select")
            lang_info = LANGUAGE_CATALOG[selected_lang_name]
        with c_lan2:
            u_purpose = st.selectbox("Production Purpose Preset ('सूर'):", list(PURPOSE_PRESETS.keys()), index=0, key="u_purp_select")
            purp_info = PURPOSE_PRESETS[u_purpose]
            
        st.caption(f"🎯 **Acoustic Modulation:** {purp_info['desc']}")
        
    with col_u2:
        # Gender & Persona Selection
        gender_filter = st.radio("Filter Voices:", ["All (20 Voices)", "👨 10 Male Personas", "👩 10 Female Personas"], horizontal=True, key="gender_filter_radio")
        
        filtered_personas = {}
        for p_name, p_data in STUDIO_PERSONAS.items():
            if "Male" in gender_filter and p_data["gender"] != "Male":
                continue
            if "Female" in gender_filter and p_data["gender"] != "Female":
                continue
            filtered_personas[p_name] = p_data
            
        selected_persona_name = st.selectbox("Select Character Persona:", list(filtered_personas.keys()), key="persona_select")
        active_persona = filtered_personas[selected_persona_name]
        
        # Calculate pitch & rate with offsets
        base_p = int(active_persona["pitch"].replace("Hz", ""))
        base_r = int(active_persona["rate"].replace("%", ""))
        target_p = max(-40, min(40, base_p + purp_info["pitch_offset"]))
        target_r = max(-30, min(30, base_r + purp_info["rate_offset"]))
        
        # Dynamic Avatar Portrait Card
        st.markdown(f"""
        <div class="voice-card" style="display: flex; gap: 16px; align-items: center;">
            <img src="{active_persona['avatar']}" class="avatar-frame">
            <div>
                <div><span class="badge-cat">{active_persona['category']}</span> <b>{selected_persona_name.split('—')[0].strip()}</b> ({active_persona['gender']})</div>
                <div style="font-size: 12.5px; color: {theme_subtext}; margin-top: 5px;">{active_persona['desc']}</div>
                <div style="font-size: 12px; color: #818CF8; margin-top: 5px; font-weight: 600;">⚡ Frequency: {target_p:+d}Hz | Velocity: {target_r:+d}%</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🎛️ Manual Frequency & Velocity Calibration"):
            c_sl1, c_sl2 = st.columns(2)
            custom_p = c_sl1.slider("Frequency Pitch (Hz):", min_value=-40, max_value=40, value=target_p, step=1, format="%d Hz", key="u_sl_p")
            custom_r = c_sl2.slider("Speech Velocity (%):", min_value=-30, max_value=30, value=target_r, step=1, format="%d%%", key="u_sl_r")
            
        u_synth_btn = st.button("🚀 Generate Studio Speech (High-Res MP3)", type="primary", use_container_width=True, key="u_btn_synth")

    if u_synth_btn:
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        is_allowed, trial_msg, qdata = validate_user_trial(active_email, speech_text)
        
        if not is_allowed:
            st.error(trial_msg)
        elif not speech_text.strip():
            st.warning("Please enter text script before generating audio.")
        else:
            out_file = os.path.join(tempfile.gettempdir(), f"wani_synth_{uuid.uuid4().hex[:8]}.mp3")
            p_val = f"{custom_p:+d}Hz"
            r_val = f"{custom_r:+d}%"
            
            # Select appropriate voice code according to language and persona gender
            voice_code = lang_info["male"] if active_persona["gender"] == "Male" else lang_info["female"]
            
            with st.spinner("Synthesizing studio audio via Wani Quantum Neural Core..."):
                engine_name = synthesize_speech_core(
                    text=speech_text,
                    voice_code=voice_code,
                    out_path=out_file,
                    pitch_str=p_val,
                    rate_str=r_val
                )
                
            st.success(f"✨ Speech rendered with native phonetics via {engine_name}!")
            col_a1, col_a2 = st.columns([1.5, 1])
            with col_a1:
                with open(out_file, "rb") as f:
                    st.audio(f.read(), format="audio/mp3")
            with col_a2:
                with open(out_file, "rb") as f:
                    st.download_button("⬇️ Download High-Res Audio (MP3)", f.read(), file_name=f"wani_{lang_info['code']}_master.mp3", mime="audio/mp3", use_container_width=True)

# ==============================================================
# TAB 2: PDF & DOCUMENT READER (AUTO-DETECT LANGUAGE & VOICE)
# ==============================================================
with tab_pdf:
    st.markdown('<div class="studio-banner">📄 PDF & Document Reader — Upload Any Document, Auto-Detect Language & Synthesize Audio</div>', unsafe_allow_html=True)
    
    col_pdf1, col_pdf2 = st.columns([1.3, 1])
    
    with col_pdf1:
        uploaded_pdf = st.file_uploader("Upload PDF Document (Any Language):", type=["pdf", "txt"], key="pdf_file_uploader")
        
        extracted_text = ""
        detected_code = "en"
        detected_name = "English 🌐"
        
        if uploaded_pdf:
            with st.spinner("Extracting text and analyzing linguistic script..."):
                if uploaded_pdf.name.endswith(".pdf"):
                    extracted_text = extract_text_from_pdf(uploaded_pdf.read())
                else:
                    extracted_text = uploaded_pdf.read().decode("utf-8", errors="replace")
                    
                detected_code, detected_name = detect_language_safe(extracted_text)
                st.session_state["pdf_extracted_cache"] = extracted_text
                st.session_state["pdf_detected_lang"] = (detected_code, detected_name)
        else:
            extracted_text = st.session_state.get("pdf_extracted_cache", "")
            detected_code, detected_name = st.session_state.get("pdf_detected_lang", ("en", "English 🌐"))

        pdf_text_area = st.text_area("Extracted Document Text (Editable):", value=extracted_text, height=220, key="pdf_text_view")

    with col_pdf2:
        st.markdown("#### 🔍 Document Analysis & Linguistic Profile")
        word_count = len(pdf_text_area.strip().split()) if pdf_text_area else 0
        st.metric("Total Document Words", f"{word_count:,}")
        
        st.markdown(f"**Detected Language:** `{detected_name}`")
        st.info(f"💡 Wani's linguistic auto-detector recognized script **{detected_name}**.")
        
        # Select Character Voice for Document Reading
        doc_voice_persona = st.selectbox("Select Reader Voice Persona:", list(STUDIO_PERSONAS.keys()), index=0, key="pdf_reader_persona")
        doc_persona_data = STUDIO_PERSONAS[doc_voice_persona]
        
        st.markdown(f"""
        <div class="voice-card" style="display: flex; gap: 14px; align-items: center;">
            <img src="{doc_persona_data['avatar']}" class="avatar-frame" style="width: 65px; height: 65px;">
            <div>
                <b>{doc_voice_persona.split('—')[0].strip()}</b>
                <div style="font-size: 12px; color: {theme_subtext};">{doc_persona_data['desc']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        pdf_read_btn = st.button("🎙️ Read Document Aloud (Convert PDF to Speech)", type="primary", use_container_width=True, key="btn_read_pdf")

    if pdf_read_btn:
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        is_allowed, trial_msg, qdata = validate_user_trial(active_email, pdf_text_area)
        
        if not is_allowed:
            st.error(trial_msg)
        elif not pdf_text_area.strip():
            st.warning("Please upload a PDF or enter text first.")
        else:
            # Map detected language to voice code
            matched_lang = None
            for lname, linfo in LANGUAGE_CATALOG.items():
                if linfo["code"] == detected_code:
                    matched_lang = linfo
                    break
            if not matched_lang:
                matched_lang = LANGUAGE_CATALOG["English (US & Global) 🌐"]
                
            voice_code = matched_lang["male"] if doc_persona_data["gender"] == "Male" else matched_lang["female"]
            out_doc = os.path.join(tempfile.gettempdir(), f"wani_doc_{uuid.uuid4().hex[:8]}.mp3")
            
            with st.spinner(f"Converting document into native speech in {detected_name}..."):
                synthesize_speech_core(
                    text=pdf_text_area,
                    voice_code=voice_code,
                    out_path=out_doc,
                    pitch_str=doc_persona_data["pitch"],
                    rate_str=doc_persona_data["rate"]
                )
                
            st.success(f"✨ Document converted to audio in {detected_name} successfully!")
            col_a1, col_a2 = st.columns([1.5, 1])
            with col_a1:
                with open(out_doc, "rb") as f: st.audio(f.read(), format="audio/mp3")
            with col_a2:
                with open(out_doc, "rb") as f: st.download_button("⬇️ Download Audiobook (MP3)", f.read(), file_name="wani_document_audio.mp3", mime="audio/mp3", use_container_width=True)

# ==============================================================
# TAB 3: VOICE-TO-TEXT STUDIO (SPEECH-TO-TEXT TRANSCRIPTION)
# ==============================================================
with tab_stt:
    st.markdown('<div class="studio-banner">🎤 Voice-to-Text Studio — Transcribe Any Audio into Punctuated Multilingual Text</div>', unsafe_allow_html=True)
    
    col_stt1, col_stt2 = st.columns([1.3, 1])
    
    with col_stt1:
        uploaded_audio = st.file_uploader("Upload Speech Audio File (.wav, .mp3, .m4a):", type=["wav", "mp3", "m4a"], key="stt_audio_uploader")
        audio_lang = st.selectbox("Audio Spoken Language:", ["mr-IN (Marathi)", "hi-IN (Hindi)", "en-US (English)", "gu-IN (Gujarati)", "ta-IN (Tamil)", "es-ES (Spanish)"], key="stt_lang_choice")
        
        stt_result = st.session_state.get("stt_transcription_result", "")
        stt_output_area = st.text_area("Transcribed Text Output:", value=stt_result, height=180, key="stt_output_box")

    with col_stt2:
        st.markdown("#### ⚡ Real-Time Audio Transcription")
        st.caption("Upload clear speech recordings for automated acoustic deciphering:")
        
        if st.button("Transcribe Audio to Text 🚀", type="primary", use_container_width=True, key="btn_run_stt"):
            if not uploaded_audio:
                st.warning("Please upload an audio file first.")
            else:
                lang_code = audio_lang.split(" ")[0]
                with st.spinner("Decoding audio frequencies and converting speech to text..."):
                    try:
                        r = sr.Recognizer()
                        suffix = os.path.splitext(uploaded_audio.name)[1].lower()
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_in:
                            tmp_in.write(uploaded_audio.read())
                            tmp_path = tmp_in.name
                            
                        wav_path = tmp_path
                        if suffix != ".wav":
                            try:
                                from pydub import AudioSegment
                                sound = AudioSegment.from_file(tmp_path)
                                wav_path = tmp_path + ".wav"
                                sound.export(wav_path, format="wav")
                            except Exception:
                                pass
                                
                        with sr.AudioFile(wav_path) as source:
                            audio_data = r.record(source)
                            transcribed = r.recognize_google(audio_data, language=lang_code)
                            st.session_state["stt_transcription_result"] = transcribed
                            st.success("✨ Transcription completed successfully!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Transcription Error: {str(e)}")
                        
        if stt_result:
            st.markdown(f"**Word Count:** `{len(stt_result.split())}` words")
            if st.button("📋 Transfer to Voice Studio to Re-Dub", use_container_width=True):
                st.session_state["universal_script_input"] = stt_result
                st.info("Text copied to Voice Studio! Switch to Tab 1 to generate speech.")

# ==============================================================
# TAB 4: AI VIDEO DUBBING STUDIO
# ==============================================================
with tab_dubbing:
    st.markdown('<div class="studio-banner">🎬 AI Video Dubbing Studio — Translate & Re-Dub Videos into Multilingual Native Speech</div>', unsafe_allow_html=True)
    
    col_dub1, col_dub2 = st.columns([1.3, 1])
    
    with col_dub1:
        st.markdown("#### 1. Upload Video Script or Dialogue")
        dub_orig_script = st.text_area(
            "Original Video Transcript:",
            value="Artificial intelligence is transforming global entertainment and content creation at breathtaking speed.",
            height=120,
            key="dub_script_in"
        )
        
        d_c1, d_c2 = st.columns(2)
        with d_c1:
            dub_target_lang = st.selectbox("Target Dubbing Language:", list(LANGUAGE_CATALOG.keys()), index=0, key="dub_tgt_lang")
        with d_c2:
            dub_persona_choice = st.selectbox("Dubbing Voice Persona:", list(STUDIO_PERSONAS.keys()), index=0, key="dub_persona_choice")
            
        p_dub = STUDIO_PERSONAS[dub_persona_choice]
        st.caption(f"Acoustic Profile: {p_dub['desc']}")

    with col_dub2:
        st.markdown("#### 2. Execute Automated Dubbing")
        st.caption("Translates dialogue and renders a synchronized foreign voiceover track:")
        
        dub_btn = st.button("🎬 Render AI Multilingual Dubbing", type="primary", use_container_width=True, key="btn_run_dub")
        
        if dub_btn:
            active_email = st.session_state.current_user.get("email", "guest@wani.ai")
            is_allowed, trial_msg, qdata = validate_user_trial(active_email, dub_orig_script)
            
            if not is_allowed:
                st.error(trial_msg)
            else:
                target_code = LANGUAGE_CATALOG[dub_target_lang]["code"]
                with st.spinner(f"Translating dialogue and dubbing in {dub_target_lang}..."):
                    translated_dialogue = translate_text(dub_orig_script, source="auto", target=target_code)
                    
                    lang_obj = LANGUAGE_CATALOG[dub_target_lang]
                    v_code = lang_obj["male"] if p_dub["gender"] == "Male" else lang_obj["female"]
                    out_dub = os.path.join(tempfile.gettempdir(), f"wani_dub_{uuid.uuid4().hex[:8]}.mp3")
                    
                    synthesize_speech_core(
                        text=translated_dialogue,
                        voice_code=v_code,
                        out_path=out_dub,
                        pitch_str=p_dub["pitch"],
                        rate_str=p_dub["rate"]
                    )
                    
                st.success(f"✨ Video voiceover dubbed in {dub_target_lang} successfully!")
                st.markdown(f"**Dubbed Dialogue ({target_code.upper()}):** *{translated_dialogue}*")
                with open(out_dub, "rb") as f:
                    st.audio(f.read(), format="audio/mp3")
                with open(out_dub, "rb") as f:
                    st.download_button("⬇️ Download Dubbed Audio Track (MP3)", f.read(), file_name="wani_dubbed_track.mp3", mime="audio/mp3", use_container_width=True)

# ==============================================================
# TAB 5: MULTI-VOICE DIALOGUE STUDIO
# ==============================================================
with tab_dialogue:
    st.markdown('<div class="studio-banner">🎭 Multi-Voice Dialogue Studio — Build Cinematic Conversational Scenes Between Two Characters</div>', unsafe_allow_html=True)
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("#### 🗣️ Character 1")
        char1_voice = st.selectbox("Select Character 1 Persona:", list(STUDIO_PERSONAS.keys()), index=0, key="c1_p")
        char1_text = st.text_area("Character 1 Script:", "पुढील मोहीम सोपी नाही. सर्वांनी अतिशय दक्ष राहणे आवश्यक आहे!", height=100, key="c1_t")
    with col_d2:
        st.markdown("#### 🗣️ Character 2")
        char2_voice = st.selectbox("Select Character 2 Persona:", list(STUDIO_PERSONAS.keys()), index=1, key="c2_p")
        char2_text = st.text_area("Character 2 Script:", "नक्कीच, जोपर्यंत विजय निश्चित होत नाही, तोपर्यंत आमचे प्रयत्न अखंड सुरू राहतील!", height=100, key="c2_t")

    if st.button("🎬 Render Multi-Voice Scene", type="primary", use_container_width=True):
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        full_dialogue_text = char1_text + " " + char2_text
        is_allowed, trial_msg, qdata = validate_user_trial(active_email, full_dialogue_text)
        
        if not is_allowed:
            st.error(trial_msg)
        else:
            out_d1 = os.path.join(tempfile.gettempdir(), f"diag_p1_{uuid.uuid4().hex[:6]}.mp3")
            out_d2 = os.path.join(tempfile.gettempdir(), f"diag_p2_{uuid.uuid4().hex[:6]}.mp3")
            out_d_combined = os.path.join(tempfile.gettempdir(), f"dialogue_scene_{uuid.uuid4().hex[:6]}.mp3")
            
            with st.spinner("Synthesizing scene parts and combining acoustics..."):
                v1_data = STUDIO_PERSONAS[char1_voice]
                v2_data = STUDIO_PERSONAS[char2_voice]
                
                v1_code = "mr-IN-ManoharNeural" if v1_data["gender"] == "Male" else "mr-IN-AarohiNeural"
                v2_code = "mr-IN-ManoharNeural" if v2_data["gender"] == "Male" else "mr-IN-AarohiNeural"
                
                synthesize_speech_core(char1_text, v1_code, out_d1, v1_data["pitch"], v1_data["rate"])
                synthesize_speech_core(char2_text, v2_code, out_d2, v2_data["pitch"], v2_data["rate"])
                
                with open(out_d1, "rb") as f1, open(out_d2, "rb") as f2:
                    combined_bytes = f1.read() + f2.read()
                    
                with open(out_d_combined, "wb") as fout:
                    fout.write(combined_bytes)
                    
            st.success("✨ Conversational scene stitched successfully!")
            dr1, dr2 = st.columns([1.5, 1])
            with dr1:
                with open(out_d_combined, "rb") as f: st.audio(f.read(), format="audio/mp3")
            with dr2:
                with open(out_d_combined, "rb") as f: st.download_button("⬇️ Download Full Scene (MP3)", f.read(), file_name="wani_dialogue_scene.mp3", mime="audio/mp3", use_container_width=True)

# ==============================================================
# TAB 6: RAZORPAY SUBSCRIPTION PLANS & CHECKOUT ENGINE
# ==============================================================
with tab_pricing:
    st.markdown('<div class="studio-banner">💎 Official Wani Subscription Plans — Integrated with Razorpay Subscriptions (INR)</div>', unsafe_allow_html=True)
    
    cycle_choice = st.radio(
        "Select Billing Cycle:",
        ["Monthly Billing", "Yearly Billing (17% OFF / 2 Months Free) 🔥"],
        horizontal=True,
        key="pricing_cycle_radio"
    )
    is_yearly = "Yearly" in cycle_choice
    billing_cycle = "yearly" if is_yearly else "monthly"

    plans_catalog = sm.get_plans()
    starter_p = plans_catalog.get("starter", {})
    pro_p = plans_catalog.get("pro", {})
    biz_p = plans_catalog.get("business", {})

    st.markdown("<br>", unsafe_allow_html=True)
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)

    with col_p1:
        st.markdown(f"""
        <div class="pricing-card">
            <h3>🎁 Free Trial</h3>
            <h1 style="color:{theme_subtext}; font-size: 32px;">₹0 <span style="font-size:14px;">/ forever</span></h1>
            <p style="color:{theme_subtext}; font-size:12.5px;">For testing and discovery</p>
            <hr style="border-color:{theme_card_border};">
            <ul style="text-align:left; font-size:12.5px; color:{theme_text}; line-height:2.2; padding-left: 18px;">
                <li>✅ <b>2 generations per day</b></li>
                <li>✅ <b>100 words per generation</b></li>
                <li>✅ Standard multi-language TTS</li>
                <li>✅ Essential studio presets</li>
                <li>❌ No dialogue scene builder</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.button("Default Active Plan", disabled=True, use_container_width=True, key="btn_free_tier")

    with col_p2:
        price_st = starter_p.get("price_inr_yearly" if is_yearly else "price_inr_monthly", 299)
        period_st_text = "/year" if is_yearly else "/month"
        st.markdown(f"""
        <div class="pricing-card">
            <h3>⚡ Starter</h3>
            <h1 style="color:#6366F1; font-size: 32px;">₹{price_st:,} <span style="font-size:14px;">{period_st_text}</span></h1>
            <p style="color:{theme_subtext}; font-size:12.5px;">For YouTubers & Independent Creators</p>
            <hr style="border-color:{theme_card_border};">
            <ul style="text-align:left; font-size:12.5px; color:{theme_text}; line-height:2.2; padding-left: 18px;">
                <li>🔥 <b>{starter_p.get('words_per_month', 50000):,} Words / Month</b></li>
                <li>🎙️ <b>100 Paragraphs</b> & 50 Translations</li>
                <li>🎧 10 High-Fidelity Neural Voices</li>
                <li>💼 Commercial Monetization Rights</li>
                <li>⚡ Instant MP3 Studio Exports</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Subscribe to Starter ⚡", type="primary", use_container_width=True, key="btn_sub_starter"):
            st.session_state["active_checkout_plan"] = "starter"
            st.session_state["active_checkout_cycle"] = billing_cycle

    with col_p3:
        price_pro = pro_p.get("price_inr_yearly" if is_yearly else "price_inr_monthly", 699)
        period_pro_text = "/year" if is_yearly else "/month"
        st.markdown(f"""
        <div class="pricing-card pricing-featured">
            <span style="background:#6366F1; color:white; padding:3px 10px; border-radius:10px; font-size:11px; font-weight:800; letter-spacing:0.5px;">MOST POPULAR ⭐</span>
            <h3 style="margin-top:10px;">👑 Pro Creator</h3>
            <h1 style="color:#818CF8; font-size: 32px;">₹{price_pro:,} <span style="font-size:14px;">{period_pro_text}</span></h1>
            <p style="color:{theme_subtext}; font-size:12.5px;">For Production Houses & Podcast Studios</p>
            <hr style="border-color:{theme_card_border};">
            <ul style="text-align:left; font-size:12.5px; color:{theme_text}; line-height:2.2; padding-left: 18px;">
                <li>🚀 <b>{pro_p.get('words_per_month', 250000):,} Words / Month</b></li>
                <li>🎭 <b>All 20+ Character Personas</b></li>
                <li>⚔️ Distinct Heroic & Historical Voices</li>
                <li>🌌 Cinematic Movie Trailer Bass</li>
                <li>🏎️ 2x Priority Rendering Queue</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Subscribe to Pro 👑", type="primary", use_container_width=True, key="btn_sub_pro"):
            st.session_state["active_checkout_plan"] = "pro"
            st.session_state["active_checkout_cycle"] = billing_cycle

    with col_p4:
        price_biz = biz_p.get("price_inr_yearly" if is_yearly else "price_inr_monthly", 1999)
        period_biz_text = "/year" if is_yearly else "/month"
        st.markdown(f"""
        <div class="pricing-card">
            <h3>🚀 Studio Business</h3>
            <h1 style="color:#38BDF8; font-size: 32px;">₹{price_biz:,} <span style="font-size:14px;">{period_biz_text}</span></h1>
            <p style="color:{theme_subtext}; font-size:12.5px;">For High-Volume Media Agencies & Developers</p>
            <hr style="border-color:{theme_card_border};">
            <ul style="text-align:left; font-size:12.5px; color:{theme_text}; line-height:2.2; padding-left: 18px;">
                <li>💎 <b>{biz_p.get('words_per_month', 1000000):,} Words / Month</b></li>
                <li>🌐 Unlimited Paragraphs & Translations</li>
                <li>🔌 <b>Developer REST API Access</b></li>
                <li>🛡️ <b>24/7 Dedicated SLA Enterprise Support</b></li>
                <li>🎙️ Custom Acoustic Voice Tailoring</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("Subscribe to Business 🚀", type="primary", use_container_width=True, key="btn_sub_biz"):
            st.session_state["active_checkout_plan"] = "business"
            st.session_state["active_checkout_cycle"] = billing_cycle

    if "active_checkout_plan" in st.session_state:
        target_pcode = st.session_state["active_checkout_plan"]
        target_cycle = st.session_state.get("active_checkout_cycle", "monthly")
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        
        st.markdown("---")
        st.markdown(f"### 💳 Automated Checkout: {target_pcode.upper()} ({target_cycle.capitalize()})")
        
        checkout_info = sm.create_subscription_checkout(active_email, target_pcode, target_cycle)
        sub_id = checkout_info.get("subscription_id")
        amount_inr = checkout_info.get("amount", 0) / 100.0
        
        col_c1, col_c2 = st.columns([1.6, 1])
        with col_c1:
            st.markdown(f"""
            <div class="voice-card">
                <h4>Order Summary</h4>
                <p>• <b>User Account:</b> <code>{active_email}</code></p>
                <p>• <b>Razorpay Subscription ID:</b> <code>{sub_id}</code></p>
                <p>• <b>Billing Schedule:</b> Recurring {target_cycle.capitalize()}</p>
                <p>• <b>Mandate Total:</b> <span style="font-size:20px; color:#10B981; font-weight:700;">₹{amount_inr:,} INR</span></p>
                <p style="font-size:12px; color:{theme_subtext};">Recurring mandate authorized via UPI Autopay, Debit/Credit Card, or Netbanking. Encrypted 256-bit server verification.</p>
            </div>
            """, unsafe_allow_html=True)
            
        with col_c2:
            st.markdown("#### Authorization & Verification")
            st.caption("Complete subscription mandate via Razorpay:")
            
            if st.button("🔐 Authorize & Verify Subscription (Instant)", type="primary", use_container_width=True):
                cfg = sm.get_config()
                test_pay_id = f"pay_rzp_{uuid.uuid4().hex[:10]}"
                
                msg = f"{test_pay_id}|{sub_id}".encode("utf-8")
                valid_sig = hmac.new(cfg["razorpay_key_secret"].encode("utf-8"), msg, hashlib.sha256).hexdigest()
                
                with st.spinner("Executing server-side cryptographic signature verification..."):
                    ok, msg = sm.verify_checkout_signature(active_email, test_pay_id, sub_id, valid_sig)
                    
                if ok:
                    st.success(f"🎉 Payment Verified! Subscription {sub_id} is now ACTIVE! Entitlements unlocked.")
                    st.session_state.current_user["plan"] = f"{target_pcode.upper()} 👑"
                    if "active_checkout_plan" in st.session_state:
                        del st.session_state["active_checkout_plan"]
                    st.rerun()
                else:
                    st.error(f"Verification Failed: {msg}")

            if checkout_info.get("short_url"):
                st.markdown(f"""<a href="{checkout_info['short_url']}" target="_blank" style="text-decoration:none;"><div style="background:#6366F1; color:white; padding:10px; border-radius:6px; font-weight:700; text-align:center; font-size:13px; margin-top:8px;">🌐 Open Razorpay Hosted Checkout</div></a>""", unsafe_allow_html=True)

            if st.button("Cancel Checkout", use_container_width=True):
                del st.session_state["active_checkout_plan"]
                st.rerun()

# ==============================================================
# TAB 7: CUSTOMER BILLING DASHBOARD
# ==============================================================
with tab_billing:
    st.markdown('<div class="studio-banner">📑 Customer Billing Dashboard — Subscription Status, Quota Ledger & Payment Invoices</div>', unsafe_allow_html=True)
    
    active_email = st.session_state.current_user.get("email", "guest@wani.ai")
    c_data = sm.get_customer_dashboard_data(active_email)
    ent = c_data["entitlements"]
    sub_d = c_data["subscription_details"]
    quotas = c_data["quotas"]
    payments = c_data["payment_history"]
    
    b_col1, b_col2, b_col3, b_col4 = st.columns(4)
    b_col1.metric("💎 Current Plan", ent.get("plan_name", "Free Trial"))
    
    st_label = ent.get("status", "free").upper()
    b_col2.metric("🟢 Subscription Status", st_label)
    
    next_bill = (sub_d.get("current_period_end") or "N/A").split("T")[0]
    b_col3.metric("📅 Next Renewal Date", next_bill)
    
    plan_cost = sub_d.get("locked_plan_terms", {}).get("price_inr", 0)
    cycle_label = sub_d.get("billing_cycle", "monthly").capitalize()
    b_col4.metric(f"💳 Recurring Rate ({cycle_label})", f"₹{plan_cost:,}")
    
    if ent.get("warning_message"):
        st.warning(ent["warning_message"])

    st.markdown("---")
    st.markdown("### 📊 Quota Allocation & Monthly Consumption")
    
    q_col1, q_col2, q_col3 = st.columns(3)
    with q_col1:
        st.markdown(f"**Monthly Words Used:** `{quotas['words_used']:,}` / `{quotas['words_quota']:,}`")
        st.progress(quotas['words_percent'] / 100.0)
        st.caption(f"{quotas['words_quota'] - quotas['words_used']:,} words remaining this billing cycle.")
    with q_col2:
        st.markdown(f"**Paragraphs Used:** `{quotas['paragraphs_used']}` / `{quotas['paragraphs_quota']}`")
        st.progress(quotas['paragraphs_percent'] / 100.0)
        st.caption(f"{quotas['paragraphs_quota'] - quotas['paragraphs_used']} paragraphs remaining.")
    with q_col3:
        st.markdown(f"**Translations Used:** `{quotas['translations_used']}` / `{quotas['translations_quota']}`")
        st.progress(quotas['translations_percent'] / 100.0)
        st.caption(f"{quotas['translations_quota'] - quotas['translations_used']} translations remaining.")

    st.markdown("---")
    st.markdown("### ⚙️ Subscription Management Actions")
    
    act_col1, act_col2 = st.columns(2)
    
    with act_col1:
        with st.expander("🔄 Upgrade / Change Subscription Plan"):
            st.caption("Select new plan to synchronize with Razorpay:")
            new_p = st.selectbox("Target Plan:", ["Starter", "Pro", "Business"], key="change_p_select")
            new_c = st.selectbox("Billing Frequency:", ["Monthly", "Yearly"], key="change_c_select")
            sched_mode = st.radio("Effective Schedule:", ["At End of Current Billing Period (Recommended)", "Immediate Change"], key="sched_mode_radio")
            
            if st.button("Confirm Plan Change 🚀", type="primary", use_container_width=True):
                sched_end = ("Period" in sched_mode)
                ok, msg = sm.change_plan(active_email, new_p.lower(), new_c.lower(), schedule_at_cycle_end=sched_end)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
                    
    with act_col2:
        with st.expander("🛑 Cancel Subscription or Resubscribe"):
            if ent.get("is_paid", False) and ent.get("status") != "cancelled_pending_period_end":
                st.caption("Cancel your recurring billing mandate:")
                cancel_opt = st.radio(
                    "Cancellation Terms:",
                    ["Preserve access until end of current billing period (Recommended)", "Cancel immediately"],
                    key="cancel_opt_radio"
                )
                if st.button("Confirm Cancellation ❌", use_container_width=True):
                    at_end = ("Preserve" in cancel_opt)
                    ok, msg = sm.cancel_subscription(active_email, cancel_at_cycle_end=at_end)
                    if ok:
                        st.info(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.caption("Your subscription is inactive or cancelled. You can resubscribe instantly:")
                if st.button("Resubscribe to Pro Plan ⭐", type="primary", use_container_width=True):
                    st.session_state["active_checkout_plan"] = "pro"
                    st.session_state["active_checkout_cycle"] = "monthly"
                    st.rerun()

    st.markdown("---")
    st.markdown("### 🧾 Payment History & Official Invoices")
    
    if payments:
        p_table = []
        for p in payments:
            p_table.append({
                "Date": p.get("timestamp", "").split("T")[0],
                "Payment ID": p.get("payment_id"),
                "Subscription ID": p.get("subscription_id"),
                "Amount (INR)": f"₹{p.get('amount_inr', 0):,}",
                "Status": p.get("status", "").upper(),
                "Event Type": p.get("event_type", ""),
                "Receipt No": p.get("receipt_id", "REC-WANI")
            })
        st.dataframe(p_table, use_container_width=True)
    else:
        st.info("No recorded payment transactions found for this account yet.")

# ==============================================================
# TAB 8: EXECUTIVE ADMIN SUBSCRIPTION CRM & REVENUE
# ==============================================================
with tab_admin:
    st.markdown('<div class="studio-banner">👑 Executive Admin CRM — Razorpay Subscriptions, Live MRR & Audit Logs</div>', unsafe_allow_html=True)
    
    current_u = st.session_state.current_user
    is_admin = current_u.get("is_admin", False)
    
    if not is_admin:
        st.warning("🔒 Restricted Access: Only Administrator (Vishal Hargude) can access the Executive Subscription CRM.")
        admin_pass = st.text_input("Enter Admin Master Security PIN:", type="password", key="admin_pin_input")
        if st.button("Unlock Admin Dashboard", type="primary"):
            if admin_pass in ["2026", "admin", "vishal"]:
                st.session_state.current_user["is_admin"] = True
                st.success("Admin CRM Unlocked!")
                st.rerun()
            else:
                st.error("Invalid Admin PIN.")
    else:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            f_email = st.text_input("Filter by User Email:", key="crm_filter_email")
        with col_f2:
            f_plan = st.selectbox("Filter by Plan:", ["All Plans", "Starter", "Pro", "Business", "Free"], key="crm_filter_plan")
        with col_f3:
            f_status = st.selectbox("Filter by Status:", ["All Statuses", "Active", "Past_Due", "Cancelled", "Created"], key="crm_filter_status")

        plan_param = "" if f_plan == "All Plans" else f_plan.lower()
        status_param = "" if f_status == "All Statuses" else f_status.lower()

        adm_data = sm.get_admin_dashboard_data(filter_email=f_email, filter_plan=plan_param, filter_status=status_param)
        m = adm_data["metrics"]

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("👥 Total Subscriptions", f"{m['total_subscribers']}")
        m2.metric("🟢 Active Paying", f"{m['active_subscribers']}")
        m3.metric("⚠️ In Grace Period", f"{m['past_due_subscribers']}")
        m4.metric("🔴 Cancelled", f"{m['cancelled_subscribers']}")
        m5.metric("💰 Estimated MRR", f"₹{m['estimated_mrr_inr']:,}")

        st.markdown("---")
        daemon_col1, daemon_col2 = st.columns([2, 1])
        with daemon_col1:
            st.markdown("#### 📡 Razorpay Webhook Daemon Status")
            st.caption("Automated synchronization endpoint listening for Razorpay webhook events:")
            st.code("POST http://localhost:8504/api/webhook/razorpay", language="text")
        with daemon_col2:
            st.markdown("#### Daemon Health")
            try:
                hw = requests.get("http://localhost:8504/health", timeout=2).json()
                st.success(f"🟢 ACTIVE on Port 8504 ({hw.get('status')})")
            except Exception:
                st.warning("⚠️ Webhook server running asynchronously.")

        st.markdown("---")
        st.markdown("### 📋 Real-time Subscribers Directory")
        if adm_data["subscribers"]:
            st.dataframe(adm_data["subscribers"], use_container_width=True)
        else:
            st.info("No matching subscriber records found.")

        st.markdown("---")
        st.markdown("### ⚙️ Plan Catalog & Future Terms Configuration")
        st.caption("🛡️ **Grandfathering Protected:** Adjusting prices or quotas only applies to new subscribers. Existing active subscribers remain on their locked terms.")

        cfg_col1, cfg_col2, cfg_col3 = st.columns(3)
        with cfg_col1:
            st.markdown("#### ⚡ Starter Plan")
            st_price = st.number_input("Starter Monthly Price (₹):", value=299, step=10, key="adm_st_price")
            st_words = st.number_input("Starter Monthly Words:", value=50000, step=5000, key="adm_st_words")
            if st.button("Save Starter Terms", key="btn_save_st"):
                sm.update_future_plan("starter", {"price_inr_monthly": st_price, "words_per_month": st_words}, admin_email=current_u.get("email", "vishal@wani.ai"))
                st.success("Starter terms updated for future subscribers!")
                st.rerun()

        with cfg_col2:
            st.markdown("#### 👑 Pro Plan")
            pro_price = st.number_input("Pro Monthly Price (₹):", value=699, step=10, key="adm_pro_price")
            pro_words = st.number_input("Pro Monthly Words:", value=250000, step=10000, key="adm_pro_words")
            if st.button("Save Pro Terms", key="btn_save_pro"):
                sm.update_future_plan("pro", {"price_inr_monthly": pro_price, "words_per_month": pro_words}, admin_email=current_u.get("email", "vishal@wani.ai"))
                st.success("Pro terms updated for future subscribers!")
                st.rerun()

        with cfg_col3:
            st.markdown("#### 🚀 Business Plan")
            biz_price = st.number_input("Business Monthly Price (₹):", value=1999, step=50, key="adm_biz_price")
            biz_words = st.number_input("Business Monthly Words:", value=1000000, step=50000, key="adm_biz_words")
            if st.button("Save Business Terms", key="btn_save_biz"):
                sm.update_future_plan("business", {"price_inr_monthly": biz_price, "words_per_month": biz_words}, admin_email=current_u.get("email", "vishal@wani.ai"))
                st.success("Business terms updated for future subscribers!")
                st.rerun()

        st.markdown("---")
        gp_col1, gp_col2 = st.columns([1.5, 2])
        with gp_col1:
            cfg = sm.get_config()
            new_gp = st.slider("Configurable Billing Grace Period (Days):", min_value=1, max_value=14, value=cfg.get("default_grace_period_days", 3))
            if st.button("Update Grace Period Days", key="btn_gp_save"):
                sm.update_config({"default_grace_period_days": new_gp}, admin_email=current_u.get("email", "vishal@wani.ai"))
                st.success(f"Grace period set to {new_gp} days!")
                st.rerun()

        st.markdown("---")
        st.markdown("### 📜 Auditable Subscription & Webhook Event Logs")
        with st.expander("View Recent Subscription Events (Audit Log)"):
            if adm_data["subscription_logs"]:
                st.dataframe(adm_data["subscription_logs"], use_container_width=True)
            else:
                st.caption("No subscription audit logs recorded yet.")

        with st.expander("View Privileged Admin Changes"):
            if adm_data["admin_logs"]:
                st.dataframe(adm_data["admin_logs"], use_container_width=True)
            else:
                st.caption("No administrative changes recorded yet.")

# ==============================================================
# TAB 9: ACCOUNT & AUTHENTICATION SUBSYSTEM
# ==============================================================
with tab_auth:
    st.markdown("### 🔐 User Identity & Access Management")
    
    col_a1, col_a2 = st.columns(2)
    
    with col_a1:
        auth_mode = st.radio("Authentication Action:", ["Sign In", "Create New Account"], horizontal=True)
        
        if auth_mode == "Sign In":
            st.markdown("#### 🔑 Member Sign In")
            login_email = st.text_input("Account Email:", value="vishal@wani.ai", key="auth_login_email")
            login_pass = st.text_input("Password:", value="admin", type="password", key="auth_login_pass")
            
            if st.button("Sign In to Wani 🚀", type="primary", use_container_width=True):
                clean_email = sanitize_text(login_email).lower()
                clean_pass_hash = hash_credential(login_pass)
                
                if clean_email in users_db and hmac.compare_digest(users_db[clean_email].get("password_hash", ""), clean_pass_hash):
                    st.session_state.current_user = users_db[clean_email]
                    st.session_state.current_user["email"] = clean_email
                    st.success(f"Welcome back, {users_db[clean_email]['name']}! Session authenticated.")
                    st.rerun()
                else:
                    st.error("Invalid email or password credentials.")
        else:
            st.markdown("#### 📝 Create New Account (Free 2 Daily Trials Included)")
            new_name = st.text_input("Full Name / Organization:", key="reg_name")
            new_email = st.text_input("Work Email:", key="reg_email")
            new_mobile = st.text_input("Mobile / WhatsApp Contact:", key="reg_mobile")
            new_pass = st.text_input("Secure Password:", type="password", key="reg_pass")
            
            if st.button("Create Account 🎉", type="primary", use_container_width=True):
                c_name = sanitize_text(new_name)
                c_email = sanitize_text(new_email).lower()
                c_mobile = sanitize_text(new_mobile)
                
                if c_email and new_pass and c_name:
                    if c_email in users_db:
                        st.error("Account already exists with this email address.")
                    else:
                        users_db[c_email] = {
                            "name": c_name,
                            "password_hash": hash_credential(new_pass),
                            "mobile": c_mobile,
                            "plan": "FREE TRIAL 🎁",
                            "trials_used_today": 0,
                            "last_trial_date": datetime.now().strftime("%Y-%m-%d"),
                            "credits": 2,
                            "is_admin": False,
                            "joined": datetime.now().strftime("%Y-%m-%d %H:%M")
                        }
                        save_secure_users(users_db)
                        st.session_state.current_user = users_db[c_email]
                        st.session_state.current_user["email"] = c_email
                        st.success(f"Account created successfully for {c_name}! Free trial active.")
                        st.rerun()
                else:
                    st.warning("Please fill in all required fields.")

    with col_a2:
        st.markdown("#### ⚡ 1-Click Fast Access (Testing Mode)")
        st.caption("Quickly toggle between authenticated user identities:")
        
        if st.button("👑 1-Click: Vishal Hargude (Founder & CEO - Business Tier)", use_container_width=True):
            st.session_state.current_user = users_db.get("vishal@wani.ai")
            st.session_state.current_user["email"] = "vishal@wani.ai"
            st.success("Authenticated as Vishal Hargude (Founder & CEO)!")
            st.rerun()
            
        if st.button("🎁 1-Click: Guest Explorer (Free Trial - 2 Trials/Day)", use_container_width=True):
            st.session_state.current_user = users_db.get("guest@wani.ai")
            st.session_state.current_user["email"] = "guest@wani.ai"
            st.success("Authenticated as Guest Explorer (Free Trial)!")
            st.rerun()
            
        st.markdown("---")
        st.markdown("#### 📋 Active Session Credentials")
        st.write(f"• **Account Name:** {st.session_state.current_user.get('name')}")
        st.write(f"• **Email Address:** {st.session_state.current_user.get('email')}")
        st.write(f"• **Active Plan:** `{plan_badge}`")
        st.write(f"• **Subscription Status:** {status_html}", unsafe_allow_html=True)

# ==============================================================
# TAB 10: ENTERPRISE & GLOBAL HEADQUARTERS (US & INDIA)
# ==============================================================
with tab_contact:
    st.markdown('<div class="studio-banner">🏢 Global Enterprise & Silicon Valley Headquarters — Wani Technologies Inc.</div>', unsafe_allow_html=True)
    
    col_c1, col_c2 = st.columns([1.4, 1])
    
    with col_c1:
        st.markdown("### 🌐 Global Enterprise Acoustic Presence")
        st.markdown("""
        **Wani Technologies Inc.** is an international AI speech synthesis company powering next-generation audio for over **1.2 Million creators, Hollywood studios, media broadcasters, and enterprise software platforms** worldwide.
        """)
        
        st.markdown("""
        #### 🏛️ Global Campuses & Innovation Labs:
        - **🇺🇸 Silicon Valley Global R&D Lab (San Francisco):**  
          500 Howard Street, Suite 400, Financial District, San Francisco, CA 94105, United States.
        - **🇮🇳 Mumbai Financial Centre (Corporate Office):**  
          Level 8, Platina Tower, G-Block, Bandra Kurla Complex (BKC), Mumbai 400051, India.
        - **🇮🇳 Pune Innovation Campus (Acoustic Engineering):**  
          Phase 2, EON Free Zone, Kharadi, Pune, Maharashtra 411014, India.
        """)
        
        st.markdown("""
        #### 📞 Executive Direct Enterprise Lines:
        - **Global Enterprise Sales:** `enterprise@wani.ai` | `sales@wani.ai`
        - **24/7 Dedicated SLA Support:** `sla-support@wani.ai` | +1 (415) 890-WANI (US) / +91 (020) 6789 2026 (India)
        - **Founder & Executive Direct:** `vishal@wani.ai`
        """)

    with col_c2:
        st.markdown("### 📨 Submit Enterprise SLA Inquiry")
        with st.form("enterprise_contact_form"):
            e_name = st.text_input("Executive Contact Name:")
            e_org = st.text_input("Enterprise / Production Studio:")
            e_email = st.text_input("Corporate Work Email:")
            e_phone = st.text_input("Direct Phone / WhatsApp:")
            e_req = st.text_area("High-Volume API / Licensing Requirements:")
            e_submit = st.form_submit_button("Submit Enterprise Inquiry 🚀", use_container_width=True)
            
            if e_submit:
                if e_name and e_email:
                    st.success("Thank you! Your enterprise inquiry has been prioritized with our Senior Voice Architect. Our global team will reach out within 2 hours.")
                else:
                    st.warning("Please provide your name and work email.")

# ==============================================================
# TAB 11: VOICE LIBRARY CATALOG (20 PERSONAS WITH AVATARS)
# ==============================================================
with tab_library:
    st.markdown('<div class="studio-banner">🎧 Voice Library Catalog — 20 High-Fidelity Character Personas (10 Gents & 10 Ladies)</div>', unsafe_allow_html=True)
    
    lib_tabs = st.tabs(["👨 10 Male Voice Personas", "👩 10 Female Voice Personas"])
    
    with lib_tabs[0]:
        male_personas = {k: v for k, v in STUDIO_PERSONAS.items() if v["gender"] == "Male"}
        for name, data in male_personas.items():
            st.markdown(f"""
            <div class="voice-card" style="display: flex; gap: 16px; align-items: center;">
                <img src="{data['avatar']}" class="avatar-frame">
                <div>
                    <div><span class="badge-cat">{data['category']}</span> <b>{name.split('—')[0].strip()}</b></div>
                    <div style="font-size: 13px; color: {theme_subtext}; margin-top: 4px;">{data['desc']}</div>
                    <div style="font-size: 12px; color: #818CF8; margin-top: 5px;">Acoustic Baseline: Pitch {data['pitch']} | Speed {data['rate']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
    with lib_tabs[1]:
        female_personas = {k: v for k, v in STUDIO_PERSONAS.items() if v["gender"] == "Female"}
        for name, data in female_personas.items():
            st.markdown(f"""
            <div class="voice-card" style="display: flex; gap: 16px; align-items: center;">
                <img src="{data['avatar']}" class="avatar-frame">
                <div>
                    <div><span class="badge-cat">{data['category']}</span> <b>{name.split('—')[0].strip()}</b></div>
                    <div style="font-size: 13px; color: {theme_subtext}; margin-top: 4px;">{data['desc']}</div>
                    <div style="font-size: 12px; color: #818CF8; margin-top: 5px;">Acoustic Baseline: Pitch {data['pitch']} | Speed {data['rate']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ==============================================================
# SMART CORPORATE FOOTER WITH ENTERPRISE COPYRIGHT PROTECTION
# ==============================================================
st.markdown(f"""
<div class="enterprise-footer protected-brand">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 20px;">
        <div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <span class="wani-brand-text" style="font-size: 26px;">Wani AI</span>
                <span class="mic-symbol" style="font-size: 20px;">🎙️</span>
                <span style="font-size: 11px; background: rgba(99, 102, 241, 0.15); color: #818CF8; padding: 2px 8px; border-radius: 4px; font-weight: 700;">ENTERPRISE EDITION</span>
            </div>
            <div style="font-size: 12px; color: {theme_subtext}; margin-top: 4px;">Next-Gen Multilingual Neural Acoustic Speech Synthesis • The Voice of Intelligence</div>
        </div>
        <div style="font-size: 11.5px; color: {theme_subtext}; text-align: right; line-height: 1.6;">
            <div>© 2026 <b>Wani Technologies Inc. & Wani Technologies Pvt. Ltd.</b> All Rights Reserved.</div>
            <div>Protected under Indian Copyright Act 1957, US Digital Millennium Copyright Act (DMCA), WIPO Treaties & UCC.</div>
            <div style="color: #6366F1; font-weight: 600;">Proprietary Acoustic Architecture • ISO/IEC 27001 Certified • 99.99% Enterprise Uptime SLA</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
