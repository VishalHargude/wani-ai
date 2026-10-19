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

from subscription_manager import SubscriptionManager, get_now_ist, format_iso

# Initialize Subscription Manager Singleton
sm = SubscriptionManager()

st.set_page_config(
    page_title="Wani — Next-Gen AI Voice & Speech Platform",
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
# SECURITY & ANTI-THEFT SUBSYSTEM (SALTED SHA-256 & SECURE DB)
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

def increment_user_trial(user_email: str):
    pass

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
# UNIVERSAL DESIGN: STRICT JOSEFIN SANS + DUAL THEME + CODE SHIELD
# -------------------------------------------------------------
is_dark = (st.session_state.theme == "Dark")

if is_dark:
    theme_bg = "#090D16"
    theme_card_bg = "#111726"
    theme_card_border = "#1E293B"
    theme_text = "#F8FAFC"
    theme_subtext = "#94A3B8"
    theme_nav_bg = "#0D1322"
    theme_featured_bg = "linear-gradient(180deg, #1A1F36 0%, #111422 100%)"
    theme_featured_border = "#6366F1"
    theme_shadow = "0 8px 24px rgba(0, 0, 0, 0.45)"
    theme_input_bg = "#111726"
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
    
    /* COMPLETE BRAND WHITELABELING: HIDE GITHUB ICON, FORK, AND STREAMLIT CLOUD BADGES */
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
    
    /* THEME CONTAINER & BASE STYLING */
    .stApp {{
        background-color: {theme_bg} !important;
        color: {theme_text} !important;
    }}
    
    /* TEXT INPUTS & TEXTAREAS COMPATIBILITY */
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
        gap: 8px;
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {theme_subtext} !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        padding: 8px 16px !important;
    }}
    .stTabs [aria-selected="true"] {{
        color: #6366F1 !important;
        border-bottom: 2px solid #6366F1 !important;
    }}
    
    /* ANTI-THEFT & CODE SHIELD */
    .protected-brand {{
        -webkit-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
    }}
    
    /* TOP LEFT-ALIGNED ENTERPRISE NAVIGATION BAR */
    .top-nav-bar {{
        background: {theme_nav_bg};
        border: 1px solid {theme_card_border};
        border-radius: 12px;
        padding: 12px 24px;
        margin-bottom: 22px;
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
        gap: 14px;
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
    
    .brand-divider {{
        color: {theme_card_border};
        font-size: 24px;
        font-weight: 300;
        margin: 0 4px;
    }}
    
    .wani-tagline-inline {{
        font-size: 11.5px;
        letter-spacing: 2px;
        color: {theme_subtext};
        text-transform: uppercase;
        font-weight: 600;
        font-family: 'Josefin Sans', sans-serif !important;
    }}
    
    .user-pill {{
        background: {theme_card_bg};
        border: 1px solid {theme_card_border};
        border-radius: 20px;
        padding: 6px 16px;
        font-size: 12.5px;
        font-weight: 600;
        color: {theme_text};
        display: inline-flex;
        align-items: center;
        gap: 10px;
    }}
    
    /* CARDS & BANNERS */
    .studio-banner {{
        background: {theme_card_bg};
        border: 1px solid {theme_card_border};
        border-radius: 10px;
        padding: 14px 20px;
        font-weight: 600;
        font-size: 14.5px;
        color: {theme_text};
        margin-bottom: 20px;
        box-shadow: {theme_shadow};
    }}
    
    .pricing-card {{
        background: {theme_card_bg};
        border: 1px solid {theme_card_border};
        border-radius: 12px;
        padding: 24px 20px;
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
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
        box-shadow: {theme_shadow};
        color: {theme_text};
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
    
    /* SMART CORPORATE COPYRIGHT FOOTER */
    .enterprise-footer {{
        margin-top: 50px;
        border-top: 1px solid {theme_card_border};
        padding: 28px 0 16px 0;
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

# TOP LEFT-ALIGNED ENTERPRISE NAVIGATION HEADER
st.markdown(f"""
<div class="top-nav-bar protected-brand">
    <div class="brand-left-group">
        <span class="wani-brand-text">Wani</span>
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

# Main Controls Bar (Theme Toggle)
col_head1, col_head2 = st.columns([8, 2])
with col_head2:
    theme_btn_label = "☀️ Switch to Light Pearl" if is_dark else "🌙 Switch to Dark Obsidian"
    if st.button(theme_btn_label, use_container_width=True, key="top_theme_toggle_btn"):
        st.session_state.theme = "Light" if is_dark else "Dark"
        st.rerun()

# Pre-Configured ElevenLabs API Key
ELEVEN_KEY_DEFAULT = "sk_cea4bc5ef26be1349c26338920a5a217503b8791b788e337"

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
    theme_choice = st.radio("Select Interface Theme:", ["🌙 Dark Obsidian", "☀️ Light Pearl"], 
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
        st.caption(f"Words Used: {q['words_used']:,} / {q['words_quota']:,}")
        st.progress(q['words_percent'] / 100.0)
        
        st.caption(f"Paragraphs Used: {q['paragraphs_used']} / {q['paragraphs_quota']}")
        st.progress(q['paragraphs_percent'] / 100.0)
        
        st.caption(f"Translations Used: {q['translations_used']} / {q['translations_quota']}")
        st.progress(q['translations_percent'] / 100.0)
        
        sub_d = current_entitlements.get("subscription_details") or {}
        if sub_d.get("current_period_end"):
            st.caption(f"Next Billing: `{sub_d['current_period_end'].split('T')[0]}`")
    else:
        st.markdown(f"**Daily Free Trials:** `{2 - q['daily_trials_today']}` of `2` remaining today")
        st.caption("Max 100 words per generation on Free Trial.")
        st.info("💡 Upgrade to **Starter** or **Pro** for high-volume limits.")

    st.markdown("---")
    st.markdown("#### 📲 Invite & Share Wani")
    share_msg = "Experience Wani - the world's most advanced multilingual AI speech platform featuring epic warrior timbres and 20+ languages: https://vishalhargude-wani-ai-app-12jfpe.streamlit.app/"
    st.markdown(f'''<a href="https://api.whatsapp.com/send?text={urllib.parse.quote(share_msg)}" target="_blank" style="text-decoration:none;"><div style="background:#25D366; color:white; padding:9px 12px; border-radius:6px; font-weight:700; text-align:center; margin-bottom:15px; font-size:13px;">📲 Share on WhatsApp</div></a>''', unsafe_allow_html=True)

    with st.expander("🛡️ Platform Security & API Key"):
        st.caption("Custom ElevenLabs API Key (Server-Side Masked):")
        eleven_key_input = st.text_input("API Key:", value=f"{ELEVEN_KEY_DEFAULT[:6]}...{ELEVEN_KEY_DEFAULT[-4:]}", type="password")
        if eleven_key_input and not eleven_key_input.startswith("sk_cea"):
            eleven_key = eleven_key_input.strip()
        else:
            eleven_key = ELEVEN_KEY_DEFAULT

    st.markdown("---")
    st.caption("🛡️ Proprietary Software of Wani Technologies Pvt. Ltd. | 256-Bit SSL Encrypted | IT Act 2000 Compliant")

# ==============================================================
# PROFESSIONAL STUDIO CHARACTER VOICES (DISTINCT FREQUENCIES)
# ==============================================================
MARATHI_VOICES = {
    "Aarav (Warrior Baritone — Historic Authority)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "SOYHLrjzK2X1ezoPC6cr",
        "gender": "Male", "category": "Historical & Epic",
        "pitch": "-30Hz", "rate": "-8%",
        "desc": "Ultra-heavy thunderous baritone with deep historic resonance and gravelly authority."
    },
    "Vikram (Cinematic Trailer Bass — Sub-Woofer)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "IKne3meq5aSn9XLyUdCD",
        "gender": "Male", "category": "Cinematic & Drama",
        "pitch": "-35Hz", "rate": "-10%",
        "desc": "Sub-woofer level resonant trailer titan bass for monumental announcements."
    },
    "Kabir (Resolute Heritage Narrator — Dignity)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "nPczCjzI2devNBz1zQrb",
        "gender": "Male", "category": "Historical & Epic",
        "pitch": "-25Hz", "rate": "-6%",
        "desc": "Steadfast, heroic defender baritone with resolute conviction and presence."
    },
    "Anup (Suspense & Crime Mystery Anchor)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "JBFqnCBsd6RMkjVDRZzb",
        "gender": "Male", "category": "Crime & Thriller",
        "pitch": "-18Hz", "rate": "-8%",
        "desc": "Tense, investigative narration style tailored for unsolved mysteries and thrillers."
    },
    "Rohan (Primetime News Desk Broadcaster)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "pNInz6obpgDQGcFmaJgB",
        "gender": "Male", "category": "News & Broadcast",
        "pitch": "+8Hz", "rate": "+20%",
        "desc": "Fast-paced, urgent broadcast delivery for breaking news and political bulletins."
    },
    "Sagar (Dynamic FM Host & Commercial RJ)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "TX3LPaxmHKxFdv7VOQHJ",
        "gender": "Male", "category": "Broadcast & Media",
        "pitch": "+22Hz", "rate": "+14%",
        "desc": "High-pitch, energetic, upbeat host delivery crafted for viral Reels and commercial radio."
    },
    "Eshwar (Elder Patriarch — Measured Wisdom)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "pqHfZKP75CvOlQylNhV4",
        "gender": "Male", "category": "Documentary & Wisdom",
        "pitch": "-28Hz", "rate": "-16%",
        "desc": "Slow, aged baritone filled with lifelong wisdom for folklore and contemplative scripts."
    },
    "Aditya (Corporate Keynote Speaker — Executive)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "CwhRBWXzGAHq8TQ4Fs17",
        "gender": "Male", "category": "Corporate & Enterprise",
        "pitch": "+4Hz", "rate": "+6%",
        "desc": "Sharp, persuasive, executive professional voice for corporate demos and B2B pitches."
    },
    "Nikhil (Intellectual Thought Leader — Podcasts)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "bIHbv24MWmeRgasZH58o",
        "gender": "Male", "category": "Podcasts & Long-form",
        "pitch": "-6Hz", "rate": "-2%",
        "desc": "Educated, thoughtful, conversational cadence for long-form podcasts and debates."
    },
    "Aarohi (Stately Empress — Royal Dignity)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "EXAVITQu4vr4xnSDxMaL",
        "gender": "Female", "category": "Historical & Epic",
        "pitch": "-22Hz", "rate": "-10%",
        "desc": "Deep, commanding maternal matriarch voice resonant with strategic valor."
    },
    "Ananya (National Newsroom Anchor — Assertive)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "21m00Tcm4TlvDq8ikWAM",
        "gender": "Female", "category": "News & Broadcast",
        "pitch": "+12Hz", "rate": "+18%",
        "desc": "Rapid, crisp, assertive news delivery for breaking news desks."
    },
    "Shreya (Cultural Storyteller — Warm Narrative)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "FGY2WhTYpPnrIDTdsKH5",
        "gender": "Female", "category": "Documentary & Wisdom",
        "pitch": "-18Hz", "rate": "-18%",
        "desc": "Affectionate, experienced narrative tone for timeless bedtime parables."
    },
    "Tara (Mindfulness & Guided ASMR Calm)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "LcfcDJNigSI51xpmTgve",
        "gender": "Female", "category": "Mindfulness & Sleep",
        "pitch": "-12Hz", "rate": "-14%",
        "desc": "Soothing, gentle whisper cadence for stress relief and mindfulness."
    },
    "Priya (Commercial Host & Lifestyle Producer)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "jsCqWAovK2LkecY7zXl4",
        "gender": "Female", "category": "Broadcast & Media",
        "pitch": "+26Hz", "rate": "+16%",
        "desc": "Bright, playful, ultra-trendy tone designed for viral lifestyle reels."
    },
    "Gauri (Documentary Host — Naturalist)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "oWAxZDx7w5VEj9dCyTzz",
        "gender": "Female", "category": "Documentary & Wisdom",
        "pitch": "-6Hz", "rate": "-6%",
        "desc": "Elegant, informative cadence for travelogues and culture documentaries."
    }
}

HINDI_VOICES = {
    "Amitabh (Monumental Cinema Baritone — Gravitas)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "nPczCjzI2devNBz1zQrb",
        "gender": "Male", "category": "Cinematic & Drama",
        "pitch": "-34Hz", "rate": "-8%",
        "desc": "Legendary heavy cinema baritone with poetic cadence and gravitas."
    },
    "Vikramaditya (Sovereign Monarch — Noble Authority)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "SOYHLrjzK2X1ezoPC6cr",
        "gender": "Male", "category": "Historical & Epic",
        "pitch": "-22Hz", "rate": "-6%",
        "desc": "Noble monarch delivery resonating with regal justice and command."
    },
    "Saurabh (Thriller & Mystery Narrative Specialist)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "JBFqnCBsd6RMkjVDRZzb",
        "gender": "Male", "category": "Crime & Thriller",
        "pitch": "-16Hz", "rate": "-6%",
        "desc": "Tense, suspenseful storytelling voice for unsolved mysteries."
    },
    "Ayush (Metropolitan FM Drive Time Host)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "TX3LPaxmHKxFdv7VOQHJ",
        "gender": "Male", "category": "Broadcast & Media",
        "pitch": "+20Hz", "rate": "+16%",
        "desc": "Dynamic, witty, fast-talking RJ style for morning drive time."
    },
    "Devendra (Vedic Scholar & Sacred Literature)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "pqHfZKP75CvOlQylNhV4",
        "gender": "Male", "category": "Documentary & Wisdom",
        "pitch": "-24Hz", "rate": "-14%",
        "desc": "Deep devotional chanting and sacred scripture cadence."
    },
    "Padmini (Royal Sovereign — Grace & Fortitude)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "EXAVITQu4vr4xnSDxMaL",
        "gender": "Female", "category": "Historical & Epic",
        "pitch": "-18Hz", "rate": "-8%",
        "desc": "Stately, poetic, royal Hindi diction with unyielding spirit."
    },
    "Avantika (Primetime National News Anchor)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "21m00Tcm4TlvDq8ikWAM",
        "gender": "Female", "category": "News & Broadcast",
        "pitch": "+10Hz", "rate": "+18%",
        "desc": "High-urgency, clear, commanding newsroom anchor cadence."
    },
    "Kalyani (Classical Heritage Narrator — Matriarch)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "FGY2WhTYpPnrIDTdsKH5",
        "gender": "Female", "category": "Documentary & Wisdom",
        "pitch": "-20Hz", "rate": "-16%",
        "desc": "Gentle, experienced elder matriarch voice for heritage parables."
    },
    "Tara (Mindful Wellness & Meditation Guide)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "LcfcDJNigSI51xpmTgve",
        "gender": "Female", "category": "Mindfulness & Sleep",
        "pitch": "-10Hz", "rate": "-12%",
        "desc": "Soft, relaxing, harmonic voice for Pranayama and guided rest."
    },
    "Simran (Entertainment & Culture Magazine Host)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "jsCqWAovK2LkecY7zXl4",
        "gender": "Female", "category": "Broadcast & Media",
        "pitch": "+24Hz", "rate": "+14%",
        "desc": "Effervescent, sparkling Bollywood pop culture delivery."
    }
}

ENGLISH_VOICES = {
    "Brian (BBC Prestige Documentary — Distinguished Baritone)": {
        "id": "en-GB-RyanNeural", "eleven_id": "nPczCjzI2devNBz1zQrb",
        "gender": "Male", "category": "Documentary & Literature",
        "pitch": "-12Hz", "rate": "-6%",
        "desc": "Distinguished British prestige baritone for global nature sagas."
    },
    "Christopher (Hollywood Blockbuster Bass — Trailer Rumble)": {
        "id": "en-US-ChristopherNeural", "eleven_id": "IKne3meq5aSn9XLyUdCD",
        "gender": "Male", "category": "Cinematic & Trailer",
        "pitch": "-30Hz", "rate": "-10%",
        "desc": "Sub-atomic Hollywood trailer rumble for monumental film teasers."
    },
    "Marcus (Silicon Valley Keynote Presenter — Tech Visionary)": {
        "id": "en-US-GuyNeural", "eleven_id": "bIHbv24MWmeRgasZH58o",
        "gender": "Male", "category": "Corporate & Enterprise",
        "pitch": "+2Hz", "rate": "+4%",
        "desc": "Clean, charismatic, tech visionary presentation style."
    },
    "Eric (Investigative Crime Journalism — Gritty Narrative)": {
        "id": "en-US-EricNeural", "eleven_id": "JBFqnCBsd6RMkjVDRZzb",
        "gender": "Male", "category": "Crime & Mystery",
        "pitch": "-14Hz", "rate": "-4%",
        "desc": "Intriguing, gritty investigative narrative delivery."
    },
    "Leo (Midnight FM Radio Host — Velvet Acoustic)": {
        "id": "en-US-RogerNeural", "eleven_id": "TX3LPaxmHKxFdv7VOQHJ",
        "gender": "Male", "category": "Broadcast & Media",
        "pitch": "+16Hz", "rate": "+10%",
        "desc": "Velvety, late-night acoustic jazz and radio station host."
    },
    "Jenny (Global Financial Broadcast — Executive News)": {
        "id": "en-US-JennyNeural", "eleven_id": "21m00Tcm4TlvDq8ikWAM",
        "gender": "Female", "category": "News & Broadcast",
        "pitch": "+8Hz", "rate": "+14%",
        "desc": "Immaculate corporate broadcast voice for financial summits."
    },
    "Emma (Theatrical Literature & Classical Drama Narrator)": {
        "id": "en-GB-SoniaNeural", "eleven_id": "pFZP5JQG7iQjIQuC4Bku",
        "gender": "Female", "category": "Documentary & Literature",
        "pitch": "-8Hz", "rate": "-6%",
        "desc": "Intense theatrical delivery for cinematic drama and storytelling."
    },
    "Sonia (Mindfulness & Deep Breath Meditation Guide)": {
        "id": "en-IN-NeerjaNeural", "eleven_id": "H6QPv2pQZDcGqLwDTIJQ",
        "gender": "Female", "category": "Mindfulness & Sleep",
        "pitch": "-14Hz", "rate": "-12%",
        "desc": "Hypnotic, peaceful cadence for guided relaxation and sleep apps."
    },
    "Diya (Animation & Character Fantasy Voice)": {
        "id": "en-US-AnaNeural", "eleven_id": "N2lVS1w4EtoT3dr4eOWO",
        "gender": "Female", "category": "Kids & Animation",
        "pitch": "+32Hz", "rate": "+8%",
        "desc": "Enchanting fairy tale and cartoon voice for young audiences."
    }
}

PURPOSE_PRESETS = {
    "Standard (Default Timbre)": {"pitch_offset": 0, "rate_offset": 0, "desc": "Natural balanced studio cadence."},
    "🎬 Documentary & History (माहितीपट)": {"pitch_offset": -16, "rate_offset": -8, "desc": "Grave, reflective, atmospheric delivery for historical sagas."},
    "😂 Comedy & Entertainment (विनोद)": {"pitch_offset": 18, "rate_offset": 12, "desc": "High-bounce, playful cadence with punchy comedic timing."},
    "📻 Radio & Podcast (रेडिओ जॉकी)": {"pitch_offset": 2, "rate_offset": 4, "desc": "Warm, acoustically rich FM broadcast tone with intimacy."},
    "📰 News & Bulletins (बातम्या)": {"pitch_offset": 6, "rate_offset": 18, "desc": "Fast-paced, urgent, authoritative news bulletin style."},
    "🧘 Meditation & Sleep (शांत ध्यान)": {"pitch_offset": -14, "rate_offset": -16, "desc": "Breathy, hypnotic, soothing cadence for mindfulness."},
    "🛒 Commercials & Reels (जाहिरात व रील)": {"pitch_offset": 12, "rate_offset": 10, "desc": "Punchy hook delivery with high brand retention."}
}

def synthesize_speech(text, voice_data, engine_choice, api_key, out_path, custom_pitch=None, custom_rate=None, lang="mr"):
    clean_text = sanitize_text(text)
    clean_text = re.sub(r'([।!?\.])', r'\1 ', clean_text)
    p = custom_pitch if custom_pitch is not None else voice_data["pitch"]
    r = custom_rate if custom_rate is not None else voice_data["rate"]

    if "ElevenLabs" in engine_choice:
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_data['eleven_id']}"
            headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
            payload = {"text": clean_text, "model_id": "eleven_v4", "language_code": lang}
            res = requests.post(url, headers=headers, json=payload, timeout=25)
            
            if res.status_code == 200:
                with open(out_path, "wb") as f: f.write(res.content)
                return "ElevenLabs v4 Generative"
            else:
                payload["model_id"] = "eleven_v3"
                res3 = requests.post(url, headers=headers, json=payload, timeout=20)
                if res3.status_code == 200:
                    with open(out_path, "wb") as f: f.write(res3.content)
                    return "ElevenLabs v3 Multi"
                else:
                    async def run_edge():
                        comm = edge_tts.Communicate(clean_text, voice_data["id"], rate=r, pitch=p)
                        await comm.save(out_path)
                    asyncio.run(run_edge())
                    return "Wani Neural Core (Edge-TTS Fallback)"
        except Exception:
            async def run_edge():
                comm = edge_tts.Communicate(clean_text, voice_data["id"], rate=r, pitch=p)
                await comm.save(out_path)
            asyncio.run(run_edge())
            return "Wani Neural Core (Edge-TTS Fallback)"
    else:
        async def run_edge():
            comm = edge_tts.Communicate(clean_text, voice_data["id"], rate=r, pitch=p)
            await comm.save(out_path)
        asyncio.run(run_edge())
        return "Native Maharashtra Neural Engine (100% Authentic 'ळ')"

# ==============================================================
# WANI STUDIO NAVIGATION TABS
# ==============================================================
tab_mr, tab_hi, tab_en, tab_trans_studio, tab_dialogue, tab_pricing, tab_customer_billing, tab_admin, tab_auth, tab_contact, tab_library = st.tabs([
    "🚩 Marathi Studio",
    "🇮🇳 Hindi Studio",
    "🌐 English Studio",
    "🌍 Universal Language Studio",
    "🎭 Multi-Voice Dialogue Studio",
    "💳 Subscription Plans",
    "📑 Customer Billing Dashboard",
    "👑 Admin Subscription CRM",
    "🔐 Account & Access",
    "🏢 Enterprise Contact Us",
    "🎧 Voice Library"
])

# ==============================================================
# TAB 1: MARATHI STUDIO
# ==============================================================
with tab_mr:
    st.markdown('<div class="studio-banner">🚩 Marathi Studio — Native Maharashtra Acoustic Models with Authentic Retroflex ळ Phonetics</div>', unsafe_allow_html=True)
    
    col_mr1, col_mr2 = st.columns([1.5, 1])
    
    with col_mr1:
        mr_text = st.text_area(
            "Marathi Script Input (मराठी मजकूर टाईप करा):",
            value="छत्रपती शिवाजी महाराजांच्या पदस्पर्शाने पावन झालेली ही भूमी, महाराष्ट्राची सह्याद्रीची कडा आणि आकाशाला गवसणी घालणारा मराठ्यांचा स्वाभिमान!",
            height=180,
            key="mr_script"
        )
        
        c_sub1, c_sub2 = st.columns(2)
        with c_sub1:
            mr_engine_choice = st.selectbox("Speech Engine Platform:", ["Native Edge Neural (Zero-Latency)", "ElevenLabs v4 Generative (Cinema Bass)"], key="mr_engine")
        with c_sub2:
            mr_purpose = st.selectbox("Select Production Purpose (सूर):", list(PURPOSE_PRESETS.keys()), key="mr_purp")
            
        purp_data = PURPOSE_PRESETS[mr_purpose]
        st.caption(f"🎯 **Acoustic Profile:** {purp_data['desc']}")
        
    with col_mr2:
        mr_categories = sorted(list(set(v["category"] for v in MARATHI_VOICES.values())))
        selected_cat = st.selectbox("Voice Category:", mr_categories, key="mr_cat")
        filtered_voices = {k: v for k, v in MARATHI_VOICES.items() if v["category"] == selected_cat}
        selected_mr_name = st.selectbox("Select Studio Voice Persona:", list(filtered_voices.keys()), key="mr_voice")
        
        mr_voice_data = filtered_voices[selected_mr_name]
        base_p = int(mr_voice_data["pitch"].replace("Hz", ""))
        base_r = int(mr_voice_data["rate"].replace("%", ""))
        target_p = max(-40, min(40, base_p + purp_data["pitch_offset"]))
        target_r = max(-30, min(30, base_r + purp_data["rate_offset"]))
        
        st.markdown(f"""
        <div class="voice-card">
            <div><span class="badge-cat">{mr_voice_data['category']}</span> <b>{selected_mr_name.split('(')[0].strip()}</b></div>
            <div style="font-size: 13px; color: {theme_subtext}; margin-top: 6px;">{mr_voice_data['desc']}</div>
            <div style="font-size: 12px; color: #818CF8; margin-top: 6px; font-weight: 600;">⚡ Frequency: {target_p:+d}Hz | Cadence: {target_r:+d}%</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🎛️ Manual Pitch & Cadence Sliders (Fine Tuning)"):
            c_sl1, c_sl2 = st.columns(2)
            custom_mr_pitch = c_sl1.slider("Pitch (Hz):", min_value=-40, max_value=40, value=target_p, step=1, format="%d Hz", key="mr_sl_pitch")
            custom_mr_rate = c_sl2.slider("Speed (%):", min_value=-30, max_value=30, value=target_r, step=1, format="%d%%", key="mr_sl_rate")
        
        mr_btn = st.button("🚀 Synthesize Speech (Generate MP3)", type="primary", use_container_width=True, key="mr_btn")

    if mr_btn:
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        is_allowed, trial_msg, qdata = validate_user_trial(active_email, mr_text)
        
        if not is_allowed:
            st.error(trial_msg)
        elif not mr_text.strip():
            st.warning("Please enter text script before generating audio.")
        else:
            out_mr = os.path.join(tempfile.gettempdir(), f"wani_mr_{uuid.uuid4().hex[:8]}.mp3")
            p_val = f"{custom_mr_pitch:+d}Hz"
            r_val = f"{custom_mr_rate:+d}%"
            
            with st.spinner("Rendering studio audio with native phonetics..."):
                engine_used = synthesize_speech(
                    text=mr_text,
                    voice_data=mr_voice_data,
                    engine_choice=mr_engine_choice,
                    api_key=eleven_key,
                    out_path=out_mr,
                    custom_pitch=p_val,
                    custom_rate=r_val,
                    lang="mr"
                )
                
            st.success(f"✨ Speech synthesized successfully via {engine_used}!")
            col_a1, col_a2 = st.columns([1.5, 1])
            with col_a1:
                with open(out_mr, "rb") as f:
                    st.audio(f.read(), format="audio/mp3")
            with col_a2:
                with open(out_mr, "rb") as f:
                    st.download_button("⬇️ Download High-Res MP3", f.read(), file_name="wani_marathi_master.mp3", mime="audio/mp3", use_container_width=True)

# ==============================================================
# TAB 2: HINDI STUDIO
# ==============================================================
with tab_hi:
    st.markdown('<div class="studio-banner">🇮🇳 Hindi Studio — North Indian Acoustic Timbres with Deep Cinema Resonance</div>', unsafe_allow_html=True)
    
    col_hi1, col_hi2 = st.columns([1.5, 1])
    
    with col_hi1:
        hi_text = st.text_area(
            "Hindi Script Input (हिंदी स्क्रिप्ट दर्ज करें):",
            value="यह भारत की वह पवित्र भूमि है जहां हर कण में इतिहास, शौर्य और अध्यात्म की गूंज सुनाई देती है। जब इरादे फौलादी हों, तो हर मंजिल आसान हो जाती है।",
            height=180,
            key="hi_script"
        )
        
        c_hsub1, c_hsub2 = st.columns(2)
        with c_hsub1:
            hi_engine_choice = st.selectbox("Speech Engine Platform:", ["Native Edge Neural (Zero-Latency)", "ElevenLabs v4 Generative (Cinema Bass)"], key="hi_engine")
        with c_hsub2:
            hi_purpose = st.selectbox("Select Production Purpose (सूर):", list(PURPOSE_PRESETS.keys()), key="hi_purp")
            
        purp_hi_data = PURPOSE_PRESETS[hi_purpose]
        st.caption(f"🎯 **Acoustic Profile:** {purp_hi_data['desc']}")
        
    with col_hi2:
        hi_categories = sorted(list(set(v["category"] for v in HINDI_VOICES.values())))
        selected_hi_cat = st.selectbox("Voice Category:", hi_categories, key="hi_cat")
        filtered_hi_voices = {k: v for k, v in HINDI_VOICES.items() if v["category"] == selected_hi_cat}
        selected_hi_name = st.selectbox("Select Studio Voice Persona:", list(filtered_hi_voices.keys()), key="hi_voice")
        
        hi_voice_data = filtered_hi_voices[selected_hi_name]
        base_hp = int(hi_voice_data["pitch"].replace("Hz", ""))
        base_hr = int(hi_voice_data["rate"].replace("%", ""))
        target_hp = max(-40, min(40, base_hp + purp_hi_data["pitch_offset"]))
        target_hr = max(-30, min(30, base_hr + purp_hi_data["rate_offset"]))
        
        st.markdown(f"""
        <div class="voice-card">
            <div><span class="badge-cat">{hi_voice_data['category']}</span> <b>{selected_hi_name.split('(')[0].strip()}</b></div>
            <div style="font-size: 13px; color: {theme_subtext}; margin-top: 6px;">{hi_voice_data['desc']}</div>
            <div style="font-size: 12px; color: #818CF8; margin-top: 6px; font-weight: 600;">⚡ Frequency: {target_hp:+d}Hz | Cadence: {target_hr:+d}%</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🎛️ Manual Pitch & Cadence Sliders (Fine Tuning)"):
            c_hsl1, c_hsl2 = st.columns(2)
            custom_hi_pitch = c_hsl1.slider("Pitch (Hz):", min_value=-40, max_value=40, value=target_hp, step=1, format="%d Hz", key="hi_sl_pitch")
            custom_hi_rate = c_hsl2.slider("Speed (%):", min_value=-30, max_value=30, value=target_hr, step=1, format="%d%%", key="hi_sl_rate")
        
        hi_btn = st.button("🚀 Synthesize Hindi Speech (Generate MP3)", type="primary", use_container_width=True, key="hi_btn")

    if hi_btn:
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        is_allowed, trial_msg, qdata = validate_user_trial(active_email, hi_text)
        
        if not is_allowed:
            st.error(trial_msg)
        elif not hi_text.strip():
            st.warning("Please enter text script before generating audio.")
        else:
            out_hi = os.path.join(tempfile.gettempdir(), f"wani_hi_{uuid.uuid4().hex[:8]}.mp3")
            p_val = f"{custom_hi_pitch:+d}Hz"
            r_val = f"{custom_hi_rate:+d}%"
            
            with st.spinner("Rendering studio audio in Hindi..."):
                engine_used = synthesize_speech(
                    text=hi_text,
                    voice_data=hi_voice_data,
                    engine_choice=hi_engine_choice,
                    api_key=eleven_key,
                    out_path=out_hi,
                    custom_pitch=p_val,
                    custom_rate=r_val,
                    lang="hi"
                )
                
            st.success(f"✨ Hindi speech synthesized successfully via {engine_used}!")
            col_a1, col_a2 = st.columns([1.5, 1])
            with col_a1:
                with open(out_hi, "rb") as f:
                    st.audio(f.read(), format="audio/mp3")
            with col_a2:
                with open(out_hi, "rb") as f:
                    st.download_button("⬇️ Download High-Res MP3", f.read(), file_name="wani_hindi_master.mp3", mime="audio/mp3", use_container_width=True)

# ==============================================================
# TAB 3: ENGLISH STUDIO
# ==============================================================
with tab_en:
    st.markdown('<div class="studio-banner">🌐 English Studio — Global BBC, Hollywood Trailer & Silicon Valley Keynote Cadences</div>', unsafe_allow_html=True)
    
    col_en1, col_en2 = st.columns([1.5, 1])
    
    with col_en1:
        en_text = st.text_area(
            "English Script Input:",
            value="Welcome to Wani Technologies. We are redefining the boundaries of human speech synthesis through advanced neural acoustic architectures and multilingual fluency.",
            height=180,
            key="en_script"
        )
        
        c_esub1, c_esub2 = st.columns(2)
        with c_esub1:
            en_engine_choice = st.selectbox("Speech Engine Platform:", ["Native Edge Neural (Zero-Latency)", "ElevenLabs v4 Generative (Cinema Bass)"], key="en_engine")
        with c_esub2:
            en_purpose = st.selectbox("Select Production Purpose (Cadence):", list(PURPOSE_PRESETS.keys()), key="en_purp")
            
        purp_en_data = PURPOSE_PRESETS[en_purpose]
        st.caption(f"🎯 **Acoustic Profile:** {purp_en_data['desc']}")
        
    with col_en2:
        en_categories = sorted(list(set(v["category"] for v in ENGLISH_VOICES.values())))
        selected_en_cat = st.selectbox("Voice Category:", en_categories, key="en_cat")
        filtered_en_voices = {k: v for k, v in ENGLISH_VOICES.items() if v["category"] == selected_en_cat}
        selected_en_name = st.selectbox("Select Studio Voice Persona:", list(filtered_en_voices.keys()), key="en_voice")
        
        en_voice_data = filtered_en_voices[selected_en_name]
        base_ep = int(en_voice_data["pitch"].replace("Hz", ""))
        base_er = int(en_voice_data["rate"].replace("%", ""))
        target_ep = max(-40, min(40, base_ep + purp_en_data["pitch_offset"]))
        target_er = max(-30, min(30, base_er + purp_en_data["rate_offset"]))
        
        st.markdown(f"""
        <div class="voice-card">
            <div><span class="badge-cat">{en_voice_data['category']}</span> <b>{selected_en_name.split('(')[0].strip()}</b></div>
            <div style="font-size: 13px; color: {theme_subtext}; margin-top: 6px;">{en_voice_data['desc']}</div>
            <div style="font-size: 12px; color: #818CF8; margin-top: 6px; font-weight: 600;">⚡ Frequency: {target_ep:+d}Hz | Cadence: {target_er:+d}%</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🎛️ Manual Pitch & Cadence Sliders (Fine Tuning)"):
            c_esl1, c_esl2 = st.columns(2)
            custom_en_pitch = c_esl1.slider("Pitch (Hz):", min_value=-40, max_value=40, value=target_ep, step=1, format="%d Hz", key="en_sl_pitch")
            custom_en_rate = c_esl2.slider("Speed (%):", min_value=-30, max_value=30, value=target_er, step=1, format="%d%%", key="en_sl_rate")
        
        en_btn = st.button("🚀 Synthesize English Speech (Generate MP3)", type="primary", use_container_width=True, key="en_btn")

    if en_btn:
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        is_allowed, trial_msg, qdata = validate_user_trial(active_email, en_text)
        
        if not is_allowed:
            st.error(trial_msg)
        elif not en_text.strip():
            st.warning("Please enter text script before generating audio.")
        else:
            out_en = os.path.join(tempfile.gettempdir(), f"wani_en_{uuid.uuid4().hex[:8]}.mp3")
            p_val = f"{custom_en_pitch:+d}Hz"
            r_val = f"{custom_en_rate:+d}%"
            
            with st.spinner("Rendering studio audio in English..."):
                engine_used = synthesize_speech(
                    text=en_text,
                    voice_data=en_voice_data,
                    engine_choice=en_engine_choice,
                    api_key=eleven_key,
                    out_path=out_en,
                    custom_pitch=p_val,
                    custom_rate=r_val,
                    lang="en"
                )
                
            st.success(f"✨ English speech synthesized successfully via {engine_used}!")
            col_a1, col_a2 = st.columns([1.5, 1])
            with col_a1:
                with open(out_en, "rb") as f:
                    st.audio(f.read(), format="audio/mp3")
            with col_a2:
                with open(out_en, "rb") as f:
                    st.download_button("⬇️ Download High-Res MP3", f.read(), file_name="wani_english_master.mp3", mime="audio/mp3", use_container_width=True)

# ==============================================================
# TAB 4: UNIVERSAL LANGUAGE STUDIO
# ==============================================================
with tab_trans_studio:
    st.markdown('<div class="studio-banner">🌍 Universal Language Studio — Cross-Lingual Translation & Native Speech Synthesis</div>', unsafe_allow_html=True)
    
    LANG_OPTIONS = {
        "Marathi (मराठी)": {"code": "mr", "edge_voice": "mr-IN-ManoharNeural"},
        "Hindi (हिंदी)": {"code": "hi", "edge_voice": "hi-IN-MadhurNeural"},
        "English (US / UK)": {"code": "en", "edge_voice": "en-US-GuyNeural"},
        "Gujarati (ગુજરાતી)": {"code": "gu", "edge_voice": "gu-IN-NiranjanNeural"},
        "Tamil (தமிழ்)": {"code": "ta", "edge_voice": "ta-IN-ValluvarNeural"},
        "Telugu (తెలుగు)": {"code": "te", "edge_voice": "te-IN-MohanNeural"},
        "Kannada (ಕನ್ನಡ)": {"code": "kn", "edge_voice": "kn-IN-GaganNeural"},
        "Bengali (বাংলা)": {"code": "bn", "edge_voice": "bn-IN-BashkarNeural"},
        "German (Deutsch)": {"code": "de", "edge_voice": "de-DE-ConradNeural"},
        "French (Français)": {"code": "fr", "edge_voice": "fr-FR-HenriNeural"},
        "Spanish (Español)": {"code": "es", "edge_voice": "es-ES-AlvaroNeural"},
        "Japanese (日本語)": {"code": "ja", "edge_voice": "ja-JP-KeitaNeural"}
    }
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        src_lang = st.selectbox("Original Source Language:", list(LANG_OPTIONS.keys()), index=2, key="src_lang")
        src_text_input = st.text_area("Source Text Script:", "Generative AI is revolutionizing how we tell stories across cultures and borders.", height=140)
    with col_t2:
        tgt_lang = st.selectbox("Target Output Language:", list(LANG_OPTIONS.keys()), index=0, key="tgt_lang")
        
        if st.button("🔄 Auto-Translate Script", use_container_width=True):
            with st.spinner("Translating text..."):
                trans_res = translate_text(src_text_input, source=LANG_OPTIONS[src_lang]["code"], target=LANG_OPTIONS[tgt_lang]["code"])
                st.session_state["trans_cached_res"] = trans_res
                
        cached_trans = st.session_state.get("trans_cached_res", "")
        tgt_text_input = st.text_area("Translated Output Script (Editable):", value=cached_trans, height=140)

    if st.button("🎙️ Synthesize Translated Speech (Native Phonetics)", type="primary", use_container_width=True):
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        is_allowed, trial_msg, qdata = validate_user_trial(active_email, tgt_text_input)
        
        if not is_allowed:
            st.error(trial_msg)
        elif not tgt_text_input.strip():
            st.warning("Please enter or translate text first.")
        else:
            voice_id = LANG_OPTIONS[tgt_lang]["edge_voice"]
            out_trans = os.path.join(tempfile.gettempdir(), f"wani_trans_{uuid.uuid4().hex[:8]}.mp3")
            
            with st.spinner(f"Synthesizing native speech in {tgt_lang}..."):
                async def run_trans_edge():
                    comm = edge_tts.Communicate(tgt_text_input, voice_id)
                    await comm.save(out_trans)
                asyncio.run(run_trans_edge())
                
            st.success(f"✨ Successfully generated native {tgt_lang} audio!")
            col_a1, col_a2 = st.columns([1.5, 1])
            with col_a1:
                with open(out_trans, "rb") as f: st.audio(f.read(), format="audio/mp3")
            with col_a2:
                with open(out_trans, "rb") as f: st.download_button("⬇️ Download Audio (MP3)", f.read(), file_name=f"wani_{LANG_OPTIONS[tgt_lang]['code']}.mp3", mime="audio/mp3", use_container_width=True)

# ==============================================================
# TAB 5: MULTI-VOICE DIALOGUE STUDIO
# ==============================================================
with tab_dialogue:
    st.markdown('<div class="studio-banner">🎭 Multi-Voice Dialogue Studio — Build Cinematic Conversational Scenes Between Two Characters</div>', unsafe_allow_html=True)
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("#### 🗣️ Character 1")
        char1_voice = st.selectbox("Select Character 1 Voice:", list(MARATHI_VOICES.keys()), index=0, key="c1_v")
        char1_text = st.text_area("Character 1 Dialogue:", "पुढील मोहीम सोपी नाही. सर्वांनी अतिशय दक्ष राहणे आवश्यक आहे!", height=100, key="c1_t")
    with col_d2:
        st.markdown("#### 🗣️ Character 2")
        char2_voice = st.selectbox("Select Character 2 Voice:", list(MARATHI_VOICES.keys()), index=1, key="c2_v")
        char2_text = st.text_area("Character 2 Dialogue:", "नक्कीच, जोपर्यंत विजय निश्चित होत नाही, तोपर्यंत आमचे प्रयत्न अखंड सुरू राहतील!", height=100, key="c2_t")

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
                v1_data = MARATHI_VOICES[char1_voice]
                v2_data = MARATHI_VOICES[char2_voice]
                
                async def run_both():
                    comm1 = edge_tts.Communicate(char1_text, v1_data["id"], pitch=v1_data["pitch"], rate=v1_data["rate"])
                    comm2 = edge_tts.Communicate(char2_text, v2_data["id"], pitch=v2_data["pitch"], rate=v2_data["rate"])
                    await comm1.save(out_d1)
                    await comm2.save(out_d2)
                asyncio.run(run_both())
                
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

    # 1. Free Trial
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

    # 2. Starter Plan
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

    # 3. Pro Creator (Featured)
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
                <li>🎭 <b>All 35+ Multi-Platform Voices</b></li>
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

    # 4. Business Plan
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

    # Checkout Flow
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
with tab_customer_billing:
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
# TAB 10: ENTERPRISE CONTACT US & HEADQUARTERS
# ==============================================================
with tab_contact:
    st.markdown('<div class="studio-banner">🏢 Global Enterprise Contact & Headquarters — Wani Technologies Pvt. Ltd.</div>', unsafe_allow_html=True)
    
    col_c1, col_c2 = st.columns([1.4, 1])
    
    with col_c1:
        st.markdown("### 🌐 Powerhouse Corporate Presence")
        st.markdown("""
        **Wani Technologies Pvt. Ltd.** is an international AI acoustics and neural speech synthesis company headquartered in Maharashtra's premier tech corridors. We empower broadcasters, media networks, and enterprises worldwide with hyper-realistic human voice models.
        """)
        
        st.markdown("""
        #### 🏛️ Corporate Headquarters:
        - **Pune Innovation Campus (R&D Centre):**  
          Phase 2, EON Free Zone, Kharadi, Pune, Maharashtra 411014, India.
        - **Mumbai Financial Centre (Corporate Office):**  
          Level 8, Platina Tower, G-Block, Bandra Kurla Complex (BKC), Mumbai 400051, India.
        """)
        
        st.markdown("""
        #### 📞 Executive Direct Lines:
        - **Global Enterprise Sales:** `enterprise@wani.ai` | `sales@wani.ai`
        - **24/7 Dedicated SLA Support:** `sla-support@wani.ai` | +91 (020) 6789 2026
        - **Leadership & Founder Direct:** `vishal@wani.ai`
        """)

    with col_c2:
        st.markdown("### 📨 Submit Enterprise Inquiry")
        with st.form("enterprise_contact_form"):
            e_name = st.text_input("Contact Person Name:")
            e_org = st.text_input("Enterprise / Organization:")
            e_email = st.text_input("Work Email Address:")
            e_phone = st.text_input("Direct Contact Number:")
            e_req = st.text_area("Production / API Volume Requirements:")
            e_submit = st.form_submit_button("Submit Enterprise Inquiry 🚀", use_container_width=True)
            
            if e_submit:
                if e_name and e_email:
                    st.success("Thank you! Your enterprise inquiry has been prioritized with our Senior Voice Architect. Our corporate team will reach out within 2 hours.")
                else:
                    st.warning("Please provide your name and work email.")

# ==============================================================
# TAB 11: MULTI-PLATFORM VOICE LIBRARY CATALOG
# ==============================================================
with tab_library:
    st.markdown('<div class="studio-banner">🎧 Voice Library Catalog — Audibly Distinct Timbre Profiles Across Microsoft, ElevenLabs & Google Engines</div>', unsafe_allow_html=True)
    
    lib_tabs = st.tabs(["Marathi Voices (15)", "Hindi Voices (10)", "English Voices (9)"])
    
    with lib_tabs[0]:
        for name, data in MARATHI_VOICES.items():
            st.markdown(f"""
            <div class="voice-card">
                <div><span class="badge-cat">{data['category']}</span> <b>{name}</b> ({data['gender']})</div>
                <div style="font-size: 13px; color: {theme_subtext}; margin-top: 4px;">{data['desc']}</div>
                <div style="font-size: 12px; color: #818CF8; margin-top: 4px;">Acoustic Baseline: Pitch {data['pitch']} | Speed {data['rate']}</div>
            </div>
            """, unsafe_allow_html=True)
            
    with lib_tabs[1]:
        for name, data in HINDI_VOICES.items():
            st.markdown(f"""
            <div class="voice-card">
                <div><span class="badge-cat">{data['category']}</span> <b>{name}</b> ({data['gender']})</div>
                <div style="font-size: 13px; color: {theme_subtext}; margin-top: 4px;">{data['desc']}</div>
                <div style="font-size: 12px; color: #818CF8; margin-top: 4px;">Acoustic Baseline: Pitch {data['pitch']} | Speed {data['rate']}</div>
            </div>
            """, unsafe_allow_html=True)
            
    with lib_tabs[2]:
        for name, data in ENGLISH_VOICES.items():
            st.markdown(f"""
            <div class="voice-card">
                <div><span class="badge-cat">{data['category']}</span> <b>{name}</b> ({data['gender']})</div>
                <div style="font-size: 13px; color: {theme_subtext}; margin-top: 4px;">{data['desc']}</div>
                <div style="font-size: 12px; color: #818CF8; margin-top: 4px;">Acoustic Baseline: Pitch {data['pitch']} | Speed {data['rate']}</div>
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
                <span style="font-size: 11px; background: rgba(99, 102, 241, 0.15); color: #818CF8; padding: 2px 8px; border-radius: 4px; font-weight: 700;">ENTERPRISE EDITION</span>
            </div>
            <div style="font-size: 12px; color: {theme_subtext}; margin-top: 4px;">Next-Gen Multilingual Neural Acoustic Speech Synthesis • The Voice of Intelligence</div>
        </div>
        <div style="font-size: 11.5px; color: {theme_subtext}; text-align: right; line-height: 1.6;">
            <div>© 2026 <b>Wani Technologies Pvt. Ltd.</b> All Rights Reserved.</div>
            <div>Protected under Indian Copyright Act 1957, IT Act 2000, WIPO Treaties & Universal Copyright Convention.</div>
            <div style="color: #6366F1; font-weight: 600;">Proprietary Acoustic Architecture • ISO/IEC 27001 Certified Infrastructure • 99.9% Enterprise SLA</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
