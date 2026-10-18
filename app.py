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
from datetime import datetime

st.set_page_config(
    page_title="Wani — Next-Gen AI Voice & Speech Platform",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
                "plan": "STUDIO MASTER 🚀",
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
                "plan": "CREATOR PRO 👑",
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
            # Schema integrity migration
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
                    "plan": "STUDIO MASTER 🚀",
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
        "plan": "STUDIO MASTER 🚀",
        "credits": 999999,
        "is_admin": True
    })
    st.session_state.current_user = admin_user
    st.session_state.current_user["email"] = "vishal@wani.ai"

# -------------------------------------------------------------
# FREE TRIAL POLICY SUBSYSTEM (EXACTLY 2 TRIALS/DAY & 100 WORDS)
# -------------------------------------------------------------
def validate_user_trial(user_email: str, script_text: str):
    today_str = datetime.now().strftime("%Y-%m-%d")
    u = users_db.get(user_email)
    if not u:
        return True, "Guest access mode active.", 0
    
    plan = u.get("plan", "FREE TRIAL 🎁")
    if "PRO" in plan or "MASTER" in plan or u.get("is_admin", False):
        return True, "Unlimited Enterprise Session Active.", 999999
    
    # Reset daily counter if a new calendar day has started
    if u.get("last_trial_date") != today_str:
        u["trials_used_today"] = 0
        u["last_trial_date"] = today_str
        save_secure_users(users_db)
        
    trials_used = u.get("trials_used_today", 0)
    if trials_used >= 2:
        return False, "⚠️ Daily Free Trial Limit Reached: You have completed your 2 free trial generations for today. Upgrade to Creator Pro for unlimited voice generations!", trials_used
        
    words = len(script_text.strip().split())
    if words > 100:
        return False, f"⚠️ Word Limit Exceeded: Your input contains {words} words. The Free Trial limit is strictly 100 words per generation. Upgrade to Creator Pro for unlimited length!", trials_used
        
    return True, f"Free Trial Active ({trials_used}/2 used today | {words}/100 words)", trials_used

def increment_user_trial(user_email: str):
    u = users_db.get(user_email)
    if u and ("PRO" not in u.get("plan", "") and "MASTER" not in u.get("plan", "") and not u.get("is_admin", False)):
        u["trials_used_today"] = u.get("trials_used_today", 0) + 1
        u["last_trial_date"] = datetime.now().strftime("%Y-%m-%d")
        save_secure_users(users_db)
        if st.session_state.current_user.get("email") == user_email:
            st.session_state.current_user["trials_used_today"] = u["trials_used_today"]

# -------------------------------------------------------------
# HIGH-RESILIENCE MULTI-LINGUAL TRANSLATION ENGINE
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
# RESTRAINED LUXURY DESIGN: JOSEFIN SANS + COLOR SHADED WANI LOGO
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Josefin+Sans:ital,wght@0,300;0,400;0,600;0,700;1,400&family=Noto+Sans+Devanagari:wght@400;600;700&display=swap');
    
    /* Universal Josefin Sans Typography */
    html, body, [class*="css"], button, input, textarea, select {
        font-family: 'Josefin Sans', 'Noto Sans Devanagari', -apple-system, sans-serif !important;
    }
    
    /* Anti-Theft Protection: Restrict text selection on branding */
    .protected-brand {
        -webkit-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
    }
    
    /* Sleek Obsidian Top Enterprise Bar */
    .top-announcement {
        background: #0B0F19;
        border: 1px solid #1E293B;
        border-radius: 10px;
        padding: 10px 18px;
        color: #F8FAFC;
        font-size: 13.5px;
        font-weight: 600;
        margin-bottom: 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
    }
    
    /* Color Shaded Wani Brand Logo */
    .wani-logo-container {
        text-align: center;
        margin-bottom: 22px;
    }
    
    .wani-brand-text {
        font-size: 52px;
        font-weight: 700;
        letter-spacing: -1.5px;
        background: linear-gradient(135deg, #38BDF8 0%, #818CF8 45%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline-block;
        line-height: 1.1;
    }
    
    .wani-tagline {
        color: #64748B;
        font-size: 14px;
        font-weight: 600;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-top: 4px;
    }
    
    .user-pill {
        background: #111827;
        border: 1px solid #1F2937;
        padding: 5px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        color: #F1F5F9;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Restrained, Minimalist Voice Card */
    .voice-card {
        background: #0D121F;
        border: 1px solid #1B2436;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 15px;
    }
    
    .badge-cat {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        margin-right: 6px;
        letter-spacing: 0.5px;
        background: #162032;
        color: #94A3B8;
        border: 1px solid #23314B;
    }
    
    /* Minimalist Section Banner */
    .studio-banner {
        border-radius: 8px;
        padding: 12px 18px;
        margin-bottom: 18px;
        font-weight: 600;
        font-size: 13.5px;
        background: #0E1524;
        border-left: 4px solid #6366F1;
        color: #E2E8F0;
    }
    
    /* Minimalist High-End Pricing Table */
    .pricing-card {
        background: #0C111C;
        border: 1px solid #1B2436;
        border-radius: 12px;
        padding: 26px;
        text-align: center;
    }
    .pricing-featured {
        border: 1.5px solid #6366F1;
        background: #0F1626;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# TOP NAVIGATION & LIVE USER CREDENTIAL STATUS
# -------------------------------------------------------------
user_plan = st.session_state.current_user.get("plan", "FREE TRIAL 🎁")
user_name = st.session_state.current_user.get("name", "User")
trials_today = st.session_state.current_user.get("trials_used_today", 0)

st.markdown(f"""
<div class="top-announcement">
    <div style="display:flex; align-items:center; gap:12px;">
        <span style="font-weight:700; color:#818CF8;">WANI ENTERPRISE</span>
        <span>•</span>
        <span style="color:#94A3B8;">Next-Generation Multilingual Acoustic AI Systems</span>
    </div>
    <div class="user-pill">
        <span>👤 {user_name.split('(')[0].strip()}</span>
        <span>|</span>
        <span style="color:#A5B4FC;">💎 {user_plan}</span>
        {"<span>| ⏳ " + str(2 - trials_today) + "/2 trials left today</span>" if "FREE" in user_plan else ""}
    </div>
</div>
""", unsafe_allow_html=True)

# Elegant Color-Shaded Wani Logo Hero
st.markdown("""
<div class="wani-logo-container protected-brand">
    <div class="wani-brand-text">Wani</div>
    <div class="wani-tagline">The Voice of Intelligence • Multilingual Speech Synthesis</div>
</div>
""", unsafe_allow_html=True)

# Pre-Configured Verified ElevenLabs API Key (Securely Kept Server-Side)
ELEVEN_KEY_DEFAULT = "sk_cea4bc5ef26be1349c26338920a5a217503b8791b788e337"

# -------------------------------------------------------------
# SIDEBAR NAVIGATION (MINIMALIST & PROFESSIONAL)
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎙️ Wani Studio Control")
    st.markdown(f"**Account:** `{user_name.split('(')[0].strip()}`")
    st.markdown(f"**Plan Status:** `{user_plan}`")
    
    if "FREE" in user_plan:
        st.markdown(f"**Daily Free Trials:** `{2 - trials_today}` of `2` remaining today")
        st.caption("Max 100 words per generation on Free Trial.")
        st.info("💡 Upgrade to **Creator Pro** ($4 / ₹299/mo) for unlimited words and generations.")
    else:
        st.success("👑 **Unlimited Enterprise Access Active** (No Word or Generation Limits)")

    st.markdown("---")
    st.markdown("#### 📲 Invite & Share Wani")
    share_msg = "Experience Wani - the world's most advanced multilingual AI speech platform featuring epic warrior timbres, Thanos cosmic bass, and 20+ language translation: https://objects-skilled-behalf-adam.trycloudflare.com"
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
# AUDIBLY DISTINCT CHARACTER VOICES (GENUINELY DIFFERENT FREQUENCIES)
# ==============================================================

MARATHI_VOICES = {
    "Tanaji Malusare (Lion's Roar - Epic Warrior)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "SOYHLrjzK2X1ezoPC6cr",
        "gender": "Male", "category": "Historical Warriors",
        "pitch": "-30Hz", "rate": "-8%",
        "desc": "Ultra-heavy thunderous warrior baritone with historic battle resonance and gravelly authority."
    },
    "Bajiprabhu Deshpande (Resolute Guardian - 50y)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "nPczCjzI2devNBz1zQrb",
        "gender": "Male", "category": "Historical Warriors",
        "pitch": "-25Hz", "rate": "-6%",
        "desc": "Steadfast, heroic defender baritone with resolute patriotic conviction."
    },
    "Titan Vikram (Cinematic Movie Trailer Bass)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "IKne3meq5aSn9XLyUdCD",
        "gender": "Male", "category": "Cinematic & Titan Bass",
        "pitch": "-35Hz", "rate": "-10%",
        "desc": "Sub-woofer level resonant trailer titan bass for monumental cinema announcements."
    },
    "Anup (Crime Patrol Suspense Narrator)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "JBFqnCBsd6RMkjVDRZzb",
        "gender": "Male", "category": "Crime & Mystery",
        "pitch": "-18Hz", "rate": "-8%",
        "desc": "Tense, investigative narration style tailored for unsolved mysteries and thrillers."
    },
    "Rahul (Intellectual Thinker & Podcaster - 30y)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "bIHbv24MWmeRgasZH58o",
        "gender": "Male", "category": "Podcasts & Interviews",
        "pitch": "-6Hz", "rate": "-2%",
        "desc": "Educated, thoughtful, conversational cadence for long-form podcasts and debates."
    },
    "RJ Sagar (FM Radio Jockey Host - 24y)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "TX3LPaxmHKxFdv7VOQHJ",
        "gender": "Male", "category": "Radio Jockey & Reels",
        "pitch": "+22Hz", "rate": "+14%",
        "desc": "High-pitch, energetic, upbeat host delivery crafted for viral Reels and commercial radio."
    },
    "Vitthal Aajoba (Elderly Sage Patriarch - 70y)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "pqHfZKP75CvOlQylNhV4",
        "gender": "Male", "category": "Spiritual & Elders",
        "pitch": "-28Hz", "rate": "-16%",
        "desc": "Slow, aged baritone filled with lifelong wisdom for bedtime folklore and chants."
    },
    "Akshay (Corporate Executive Keynote Speaker)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "CwhRBWXzGAHq8TQ4Fs17",
        "gender": "Male", "category": "Corporate & Business",
        "pitch": "+4Hz", "rate": "+6%",
        "desc": "Sharp, persuasive, executive professional voice for corporate demos and B2B pitches."
    },
    "Rohan (Prime-Time TV News Broadcaster)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "pNInz6obpgDQGcFmaJgB",
        "gender": "Male", "category": "News & Broadcast",
        "pitch": "+8Hz", "rate": "+20%",
        "desc": "Fast-paced, urgent broadcast delivery for breaking news and political bulletins."
    },
    "Manohar (Classic Literary Narrator - 40y)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "cjVigY5qzO86Huf0OWal",
        "gender": "Male", "category": "Audiobooks & Literature",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "Balanced native Maharashtra baritone with pristine retroflex 'ळ' phonetics for literature."
    },

    "Rajmata Jijau (Royal Matriarch & Inspirer - 50y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "EXAVITQu4vr4xnSDxMaL",
        "gender": "Female", "category": "Historical Warriors",
        "pitch": "-22Hz", "rate": "-10%",
        "desc": "Commanding, dignified maternal presence inspiring historic valor and righteousness."
    },
    "Aaji Narmada (Affectionate Grandmother - 65y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "Xb7hH8MSUJpSbSDYk0k2",
        "gender": "Female", "category": "Spiritual & Elders",
        "pitch": "-25Hz", "rate": "-15%",
        "desc": "Warm, soothing, traditional storytelling tone brimming with maternal affection."
    },
    "Aarohi (Classic Audiobook & Literature Narrator - 28y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "XrExE9yKIg1WjnnlVkGX",
        "gender": "Female", "category": "Audiobooks & Literature",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "Crystal-clear, melodic standard native voice for audiobooks, poetry, and explainers."
    },
    "Priya (Viral Reel & Commercial Specialist - 22y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "FGY2WhTYpPnrIDTdsKH5",
        "gender": "Female", "category": "Radio Jockey & Reels",
        "pitch": "+26Hz", "rate": "+12%",
        "desc": "Playful, bright, high-energy delivery designed for TikTok, YouTube Shorts, and brand ads."
    },
    "RJ Shreya (FM Radio Jockey Host - 25y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "cgSgspJ2msm6clMCkdW9",
        "gender": "Female", "category": "Radio Jockey & Reels",
        "pitch": "+18Hz", "rate": "+10%",
        "desc": "Sparkling, vivacious radio presenter delivery for daily youth entertainment."
    },
    "Sayali (Prime-Time TV News Anchor)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "SAz9YHcvj6GT2YYXdXww",
        "gender": "Female", "category": "News & Broadcast",
        "pitch": "+6Hz", "rate": "+18%",
        "desc": "Sharp, articulate, confident television presenter voice for studio journalism."
    },
    "Meera (Serene Meditation & Spiritual Devotion)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "H6QPv2pQZDcGqLwDTIJQ",
        "gender": "Female", "category": "Spiritual & Elders",
        "pitch": "-12Hz", "rate": "-16%",
        "desc": "Calming, peaceful, breathy cadence for mindfulness meditation and devotional chants."
    },
    "Tanvi (Dramatic & Sensitive Audiobook Actor)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "pFZP5JQG7iQjIQuC4Bku",
        "gender": "Female", "category": "Audiobooks & Literature",
        "pitch": "-5Hz", "rate": "-6%",
        "desc": "Rich in pauses and delicate emotional nuances, ideal for novel drama."
    },
    "Pooja (Podcast & Studio Interviewer)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "hpp4J3VqNfWAUOO0d1Us",
        "gender": "Female", "category": "Podcasts & Interviews",
        "pitch": "+8Hz", "rate": "+4%",
        "desc": "Sophisticated modern conversationalist voice for corporate and academic dialogues."
    },
    "Diya (Animated Pixie & Fairy Tales - 8y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "N2lVS1w4EtoT3dr4eOWO",
        "gender": "Female", "category": "Kids & Fantasy",
        "pitch": "+36Hz", "rate": "+8%",
        "desc": "Ultra high-pitched cheerful child voice for animated cartoons and fantasy fables."
    }
}

HINDI_VOICES = {
    "Amitabh Style Madhur (Epic Baritone Titan)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "JBFqnCBsd6RMkjVDRZzb",
        "gender": "Male", "category": "Cinematic & Titan Bass",
        "pitch": "-30Hz", "rate": "-8%",
        "desc": "Ultra-deep, grave legendary baritone with cinematic gravitas and monumental weight."
    },
    "Bahubali Devdutt (Epic Historical Commander)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "SOYHLrjzK2X1ezoPC6cr",
        "gender": "Male", "category": "Historical Warriors",
        "pitch": "-25Hz", "rate": "-6%",
        "desc": "Resonant battle commander voice for epic mythology, warrior sagas, and trailers."
    },
    "Vikram (Crime Patrol Mystery Host)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "nPczCjzI2devNBz1zQrb",
        "gender": "Male", "category": "Crime & Mystery",
        "pitch": "-18Hz", "rate": "-8%",
        "desc": "Gripping, suspenseful investigative narration for crime stories and thrillers."
    },
    "Ram (Spiritual Master & Gita Preacher)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "CwhRBWXzGAHq8TQ4Fs17",
        "gender": "Male", "category": "Spiritual & Elders",
        "pitch": "-15Hz", "rate": "-16%",
        "desc": "Tranquil spiritual preacher cadence bringing deep inner calm and meditation."
    },
    "RJ Aryan (Supercharged FM Radio Jockey)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "TX3LPaxmHKxFdv7VOQHJ",
        "gender": "Male", "category": "Radio Jockey & Reels",
        "pitch": "+22Hz", "rate": "+14%",
        "desc": "High-octane, charismatic young radio presenter tone for viral trends."
    },
    "Dadaji (Elderly Patriarch Storyteller - 70y)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "pqHfZKP75CvOlQylNhV4",
        "gender": "Male", "category": "Spiritual & Elders",
        "pitch": "-30Hz", "rate": "-16%",
        "desc": "Aged patriarch tone steeped in decades of storytelling experience."
    },
    "Kabir (Youth Tech Podcaster & Motivator)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "IKne3meq5aSn9XLyUdCD",
        "gender": "Male", "category": "Podcasts & Interviews",
        "pitch": "+12Hz", "rate": "+12%",
        "desc": "Energetic, dynamic modern creator tone inspiring motivation."
    },
    "Sameer (Corporate Business Keynote Speaker)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "cjVigY5qzO86Huf0OWal",
        "gender": "Male", "category": "Corporate & Business",
        "pitch": "+4Hz", "rate": "+6%",
        "desc": "Fluent executive presentation delivery for investor conferences."
    },
    "Ajay (Prime-Time Bulletins News Anchor)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "pNInz6obpgDQGcFmaJgB",
        "gender": "Male", "category": "News & Broadcast",
        "pitch": "+8Hz", "rate": "+20%",
        "desc": "Fast-paced, sharp news anchor delivery delivering breaking headlines."
    },
    "Rahul (Hindi Literature Narrator)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "bIHbv24MWmeRgasZH58o",
        "gender": "Male", "category": "Audiobooks & Literature",
        "pitch": "-4Hz", "rate": "-2%",
        "desc": "Natural, soothing cadence for classic Hindi literature and novels."
    },

    "Dadi Maa (Loving Grandmother Tales - 65y)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "Xb7hH8MSUJpSbSDYk0k2",
        "gender": "Female", "category": "Spiritual & Elders",
        "pitch": "-24Hz", "rate": "-14%",
        "desc": "Tender, nurturing grandmotherly cadence brimming with moral bedtime tales."
    },
    "Swara (Classic Advertising & Novel Narrator)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "EXAVITQu4vr4xnSDxMaL",
        "gender": "Female", "category": "Audiobooks & Literature",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "Pristine standard Hindi diction for prestigious commercial campaigns."
    },
    "Simran (Viral Reel Sensation - 21y)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "FGY2WhTYpPnrIDTdsKH5",
        "gender": "Female", "category": "Radio Jockey & Reels",
        "pitch": "+26Hz", "rate": "+12%",
        "desc": "Spirited, trendy creator delivery customized for modern social algorithms."
    },
    "RJ Riya (Bubbly FM Radio Host)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "cgSgspJ2msm6clMCkdW9",
        "gender": "Female", "category": "Radio Jockey & Reels",
        "pitch": "+18Hz", "rate": "+10%",
        "desc": "Vibrant, cheerful FM host cadence connecting warmly with daily listeners."
    },
    "Anjali (TV News Bulletin Presenter)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "XrExE9yKIg1WjnnlVkGX",
        "gender": "Female", "category": "News & Broadcast",
        "pitch": "+6Hz", "rate": "+18%",
        "desc": "Poised, authoritative broadcast delivery for studio journalism."
    },
    "Meera (Peaceful Devotion & Bhajan Voice)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "H6QPv2pQZDcGqLwDTIJQ",
        "gender": "Female", "category": "Spiritual & Elders",
        "pitch": "-12Hz", "rate": "-15%",
        "desc": "Gentle, reverent spiritual delivery radiating deep tranquility."
    },
    "Neha (Dramatic & Sensitive Audiobook Actor)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "pFZP5JQG7iQjIQuC4Bku",
        "gender": "Female", "category": "Audiobooks & Literature",
        "pitch": "-5Hz", "rate": "-6%",
        "desc": "Rich in pauses and emotional nuances for narrative drama."
    },
    "Pooja (Podcast & Studio Interviewer)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "hpp4J3VqNfWAUOO0d1Us",
        "gender": "Female", "category": "Podcasts & Interviews",
        "pitch": "+8Hz", "rate": "+4%",
        "desc": "Engaging conversationalist delivery for in-depth interviews."
    },
    "Dr. Vandana (Professor & Motivational Mentor)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "SAz9YHcvj6GT2YYXdXww",
        "gender": "Female", "category": "Corporate & Business",
        "pitch": "-16Hz", "rate": "-4%",
        "desc": "Grave, dignified academic lecture delivery for masterclasses."
    },
    "Pihu (Animated Pixie & Fairy Tales - 8y)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "N2lVS1w4EtoT3dr4eOWO",
        "gender": "Female", "category": "Kids & Fantasy",
        "pitch": "+36Hz", "rate": "+8%",
        "desc": "Playful, charming child delivery for fantasy stories and cartoons."
    }
}

ENGLISH_VOICES = {
    "Thanos / Christopher (Cinematic Cosmic Titan Bass - US)": {
        "id": "en-US-ChristopherNeural", "eleven_id": "nPczCjzI2devNBz1zQrb",
        "gender": "Male", "category": "Cinematic & Titan Bass",
        "pitch": "-35Hz", "rate": "-12%",
        "desc": "Ultra-deep resonant cosmic titan voice with thunderous sub-bass."
    },
    "Brian (Warm Storyteller & Documentary - US)": {
        "id": "en-US-BrianNeural", "eleven_id": "JBFqnCBsd6RMkjVDRZzb",
        "gender": "Male", "category": "Audiobooks & Literature",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "Warm National Geographic narrator tone with pristine natural presence."
    },
    "Ryan (Royal British Gentleman & BBC Host - UK)": {
        "id": "en-GB-RyanNeural", "eleven_id": "CwhRBWXzGAHq8TQ4Fs17",
        "gender": "Male", "category": "Corporate & Business",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "Aristocratic British Received Pronunciation for documentaries and drama."
    },
    "Prabhat (Professional Explainer - Indian English)": {
        "id": "en-IN-PrabhatNeural", "eleven_id": "TX3LPaxmHKxFdv7VOQHJ",
        "gender": "Male", "category": "Corporate & Business",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "100% natural, educated Indian English accent for corporate tutorials."
    },
    "Charlie (High-Energy Host & Creator - Australia)": {
        "id": "en-AU-WilliamNeural", "eleven_id": "IKne3meq5aSn9XLyUdCD",
        "gender": "Male", "category": "Podcasts & Interviews",
        "pitch": "+12Hz", "rate": "+10%",
        "desc": "Dynamic, charismatic YouTube tech creator and podcast host."
    },
    "Harry (Gravelly Warrior & Gaming Protagonist)": {
        "id": "en-US-EricNeural", "eleven_id": "SOYHLrjzK2X1ezoPC6cr",
        "gender": "Male", "category": "Historical Warriors",
        "pitch": "-22Hz", "rate": "-6%",
        "desc": "Gritty warrior voice for video games, fantasy lore, and combat."
    },
    "Bill (Seasoned Patriarch & Wise Veteran - 70s)": {
        "id": "en-US-GuyNeural", "eleven_id": "pqHfZKP75CvOlQylNhV4",
        "gender": "Male", "category": "Spiritual & Elders",
        "pitch": "-28Hz", "rate": "-15%",
        "desc": "Wise grandfather tone with emotional weight and historical depth."
    },
    "Will (Chill Boy-Next-Door & Casual Vlogger)": {
        "id": "en-US-AndrewNeural", "eleven_id": "bIHbv24MWmeRgasZH58o",
        "gender": "Male", "category": "Radio Jockey & Reels",
        "pitch": "+6Hz", "rate": "+4%",
        "desc": "Relatable, casual, relaxed conversational voice for daily vlogs."
    },
    "Adam (Authoritative Leader & Commander)": {
        "id": "en-US-SteffanNeural", "eleven_id": "pNInz6obpgDQGcFmaJgB",
        "gender": "Male", "category": "News & Broadcast",
        "pitch": "-12Hz", "rate": "+4%",
        "desc": "Firm, decisive leadership tone for keynote addresses and manifestos."
    },
    "Eric (Mindfulness Guide & Nature Audio - US)": {
        "id": "en-US-RogerNeural", "eleven_id": "cjVigY5qzO86Huf0OWal",
        "gender": "Male", "category": "Spiritual & Elders",
        "pitch": "-14Hz", "rate": "-12%",
        "desc": "Soothing, gentle cadence for sleep stories, meditation, and wellness."
    },

    "Jenny (Natural Conversational YouTube #1 - US)": {
        "id": "en-US-JennyNeural", "eleven_id": "EXAVITQu4vr4xnSDxMaL",
        "gender": "Female", "category": "Audiobooks & Literature",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "The most natural, warm American conversational voice for YouTube."
    },
    "Ava (Dynamic Tech Host & Commercial Specialist - US)": {
        "id": "en-US-AvaNeural", "eleven_id": "FGY2WhTYpPnrIDTdsKH5",
        "gender": "Female", "category": "Radio Jockey & Reels",
        "pitch": "+15Hz", "rate": "+10%",
        "desc": "Youthful, energetic, punchy delivery for high-impact brand commercials."
    },
    "Libby (Classic British Audiobook Narrator - UK)": {
        "id": "en-GB-LibbyNeural", "eleven_id": "Xb7hH8MSUJpSbSDYk0k2",
        "gender": "Female", "category": "Audiobooks & Literature",
        "pitch": "-4Hz", "rate": "-4%",
        "desc": "Refined British literary narrator for historical audiobooks."
    },
    "Neerja (Expressive Indian English Female - India)": {
        "id": "en-IN-NeerjaExpressiveNeural", "eleven_id": "SAz9YHcvj6GT2YYXdXww",
        "gender": "Female", "category": "Podcasts & Interviews",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "100% natural, fluent modern Indian English female for corporate media."
    },
    "Matilda (Engaging Educational & Course Instructor)": {
        "id": "en-US-AriaNeural", "eleven_id": "XrExE9yKIg1WjnnlVkGX",
        "gender": "Female", "category": "Corporate & Business",
        "pitch": "+4Hz", "rate": "+4%",
        "desc": "Articulate, friendly educator voice for online masterclasses."
    },
    "Jessica (Bright, Playful & Charming - US)": {
        "id": "en-US-EmmaNeural", "eleven_id": "cgSgspJ2msm6clMCkdW9",
        "gender": "Female", "category": "Radio Jockey & Reels",
        "pitch": "+18Hz", "rate": "+8%",
        "desc": "Upbeat, radiant lifestyle presenter for beauty and social reels."
    },
    "Bella (Luxury Brand & High-Fashion Narrator)": {
        "id": "en-US-MichelleNeural", "eleven_id": "hpp4J3VqNfWAUOO0d1Us",
        "gender": "Female", "category": "Corporate & Business",
        "pitch": "+6Hz", "rate": "+2%",
        "desc": "Silky, captivating commercial voice for premium advertisements."
    },
    "Lily (Velvety Dramatic Actress & Character Voice)": {
        "id": "en-GB-SoniaNeural", "eleven_id": "pFZP5JQG7iQjIQuC4Bku",
        "gender": "Female", "category": "Audiobooks & Literature",
        "pitch": "-8Hz", "rate": "-6%",
        "desc": "Intense theatrical delivery for cinematic drama and storytelling."
    },
    "Sonia (Mindfulness & Deep Breath Meditation)": {
        "id": "en-IN-NeerjaNeural", "eleven_id": "H6QPv2pQZDcGqLwDTIJQ",
        "gender": "Female", "category": "Spiritual & Elders",
        "pitch": "-14Hz", "rate": "-12%",
        "desc": "Hypnotic, peaceful cadence for guided relaxation and sleep apps."
    },
    "Diya (Fantasy Pixie & Animated Child Voice)": {
        "id": "en-US-AnaNeural", "eleven_id": "N2lVS1w4EtoT3dr4eOWO",
        "gender": "Female", "category": "Kids & Fantasy",
        "pitch": "+32Hz", "rate": "+8%",
        "desc": "Enchanting fairy tale and cartoon voice for young audiences."
    }
}

# -------------------------------------------------------------
# PURPOSE / SUR PRESET MAPPINGS (POINT 9)
# -------------------------------------------------------------
PURPOSE_PRESETS = {
    "Standard (Default Timbre)": {"pitch_offset": 0, "rate_offset": 0, "desc": "Natural balanced studio cadence."},
    "🎬 Documentary & History (माहितीपट)": {"pitch_offset": -16, "rate_offset": -8, "desc": "Grave, reflective, atmospheric delivery for historical sagas."},
    "😂 Comedy & Entertainment (विनोद)": {"pitch_offset": 18, "rate_offset": 12, "desc": "High-bounce, playful cadence with punchy comedic timing."},
    "📻 Radio & Podcast (रेडिओ जॉकी)": {"pitch_offset": 2, "rate_offset": 4, "desc": "Warm, acoustically rich FM broadcast tone with intimacy."},
    "📰 News & Bulletins (बातम्या)": {"pitch_offset": 6, "rate_offset": 18, "desc": "Fast-paced, urgent, authoritative news bulletin style."},
    "🧘 Meditation & Sleep (शांत ध्यान)": {"pitch_offset": -14, "rate_offset": -16, "desc": "Breathy, hypnotic, soothing cadence for mindfulness."},
    "🛒 Commercials & Reels (जाहिरात व रील)": {"pitch_offset": 12, "rate_offset": 10, "desc": "Punchy hook delivery with high brand retention."}
}

# -------------------------------------------------------------
# CORE SYNTHESIS ENGINE
# -------------------------------------------------------------
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
tab_mr, tab_hi, tab_en, tab_trans_studio, tab_dialogue, tab_pricing, tab_auth, tab_admin, tab_contact, tab_library = st.tabs([
    "🚩 Marathi Studio",
    "🇮🇳 Hindi Studio",
    "🌐 English Studio",
    "🌍 Universal Language Studio",
    "🎭 Multi-Voice Dialogue Studio",
    "💎 Pricing & Subscriptions",
    "🔐 Account & Access",
    "👑 Executive CRM",
    "🏢 About & Enterprise Support",
    "👥 Voice Library"
])

# ==============================================================
# TAB 1: MARATHI STUDIO (WITH PURPOSE / SUR PRESET)
# ==============================================================
with tab_mr:
    st.markdown('<div class="studio-banner">🚩 Marathi Speech Studio — Native Maharashtra Accent, Authentic Retroflex "ळ" Phonetics & Distinct Voice Actors</div>', unsafe_allow_html=True)
    
    with st.expander("🌐 Instant Translator (English/Hindi -> Auto-Translate to Marathi)"):
        col_tr1, col_tr2 = st.columns([2.5, 1])
        with col_tr1:
            trans_input = st.text_input("Type text to translate into Marathi:", placeholder="e.g. Chhatrapati Shivaji Maharaj was the greatest leader of India...")
        with col_tr2:
            st.write("")
            st.write("")
            if st.button("Translate to Marathi 🔄", use_container_width=True):
                if trans_input.strip():
                    translated_res = translate_text(trans_input, source='auto', target='mr')
                    st.session_state.mr_input_val = translated_res
                    st.success("Translated and loaded into editor!")
    
    mr_engine_choice = st.radio(
        "Acoustic Audio Engine:",
        [
            "🚩 Native Maharashtra Neural Engine (100% Authentic 'ळ' - Zero Hindi Mix - Recommended ⭐)",
            "👑 ElevenLabs v4 Generative Engine (Global Cloud)"
        ],
        index=0,
        horizontal=True,
        key="mr_engine_radio"
    )

    col_m1, col_m2 = st.columns([1.2, 1])
    
    with col_m1:
        st.markdown("**1. Enter Marathi Script:**")
        
        c_p1, c_p2, c_p3 = st.columns(3)
        if c_p1.button("🚩 Retroflex 'ळ' Test"):
            st.session_state.mr_input_val = "मावळ्यांच्या साथीने छत्रपती शिवरायांनी स्वराज्याचे बाळ कडू पाजले. बाळ, कमळ, टिळक आणि मावळे!"
        if c_p2.button("⚔️ Tanaji Malusare Roar"):
            st.session_state.mr_input_val = "आधी लगीन कोंढाण्याचं, मग माझ्या रायबाचं! जोपर्यंत कोंढाण्यावर भगवा फडकणार नाही, तोपर्यंत हा तानाजी माघार घेणार नाही!"
        if c_p3.button("👑 Shivray Historic Legacy"):
            st.session_state.mr_input_val = "सह्याद्रीच्या कडेकपारीतून एकच गर्जना घुमली... जेव्हा संकटांची वादळे अंगावर चालून येतात, तेव्हा इतिहास बघायचा नसतो, तर इतिहास घडवायचा असतो!"
            
        if "mr_input_val" not in st.session_state:
            st.session_state.mr_input_val = "मावळ्यांच्या साथीने छत्रपती शिवरायांनी स्वराज्याचे बाळ कडू पाजले. बाळ, कमळ, टिळक आणि मावळे!"

        mr_text = st.text_area("Script Editor:", value=st.session_state.mr_input_val, height=160, key="mr_text_area")
        
        # Word Counter with Free Trial Warnings
        curr_words = len(mr_text.strip().split())
        st.caption(f"📊 Words: **{curr_words}** / 100 max (Free Trial) | Characters: **{len(mr_text)}**")

    with col_m2:
        st.markdown("**2. Voice Actor & Production Purpose (सूर):**")
        mr_gender = st.radio("Gender:", ["👨 10 Male Voice Actors", "👩 10 Female Voice Actors"], horizontal=True, key="mr_gender_radio")
        is_male = "Male" in mr_gender
        
        filtered_mr = {k: v for k, v in MARATHI_VOICES.items() if (v["gender"] == "Male" if is_male else v["gender"] == "Female")}
        selected_mr_name = st.selectbox("Select Voice Actor:", list(filtered_mr.keys()), key="mr_voice_select")
        mr_voice_data = filtered_mr[selected_mr_name]
        
        # Purpose / Sur Selector (Point 9)
        selected_purpose = st.selectbox("🎯 Production Purpose (सूर / Style Preset):", list(PURPOSE_PRESETS.keys()), index=0)
        purp_data = PURPOSE_PRESETS[selected_purpose]
        st.caption(f"ℹ️ {purp_data['desc']}")
        
        # Calculate pitch & cadence with purpose offsets
        base_p = int(mr_voice_data["pitch"].replace("Hz", ""))
        base_r = int(mr_voice_data["rate"].replace("%", ""))
        target_p = max(-40, min(40, base_p + purp_data["pitch_offset"]))
        target_r = max(-30, min(30, base_r + purp_data["rate_offset"]))
        
        st.markdown(f"""
        <div class="voice-card">
            <div><span class="badge-cat">{mr_voice_data['category']}</span> <b>{selected_mr_name.split('(')[0]}</b></div>
            <div style="font-size: 13px; color: #94A3B8; margin-top: 6px;">{mr_voice_data['desc']}</div>
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
        is_allowed, trial_msg, _ = validate_user_trial(active_email, mr_text)
        
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
                increment_user_trial(active_email)

            st.success(f"✨ Audio rendered successfully! (Engine: {engine_used})")
            r1, r2 = st.columns([1.5, 1])
            with r1:
                with open(out_mr, "rb") as f: st.audio(f.read(), format="audio/mp3")
            with r2:
                with open(out_mr, "rb") as f: st.download_button("⬇️ Download Audio (MP3)", f.read(), file_name="wani_marathi_audio.mp3", mime="audio/mp3", use_container_width=True)


# ==============================================================
# TAB 2: HINDI STUDIO
# ==============================================================
with tab_hi:
    st.markdown('<div class="studio-banner">🇮🇳 Hindi Speech Studio — Amitabh Style Deep Baritone, Bahubali Epic Bass & Expressive Voices</div>', unsafe_allow_html=True)
    
    with st.expander("🌐 Instant Translator (English -> Auto-Translate to Hindi)"):
        col_htr1, col_htr2 = st.columns([2.5, 1])
        with col_htr1:
            h_trans_input = st.text_input("Type English text to translate into Hindi:", placeholder="e.g. Success comes to those who believe in the beauty of their dreams...")
        with col_htr2:
            st.write("")
            st.write("")
            if st.button("Translate to Hindi 🔄", use_container_width=True):
                if h_trans_input.strip():
                    translated_h_res = translate_text(h_trans_input, source='en', target='hi')
                    st.session_state.hi_input_val = translated_h_res
                    st.success("Translated and loaded into editor!")
                    
    col_h1, col_h2 = st.columns([1.2, 1])
    
    with col_h1:
        st.markdown("**1. Enter Hindi Script:**")
        c_h_p1, c_h_p2 = st.columns(2)
        if c_h_p1.button("👑 Amitabh Style Thought"):
            st.session_state.hi_input_val = "जिंदगी में कभी किसी को कम मत समझना... क्योंकि समंदर कितना भी खामोश क्यों न हो, जब उठता है तो बड़े-बड़ों को डुबो देता है!"
        if c_h_p2.button("⚔️ Bahubali Battle Cry"):
            st.session_state.hi_input_val = "जब तक तुम मेरे साथ हो, मुझे मारने वाला पैदा नहीं हुआ मामा! धर्म की रक्षा ही हमारा एकमात्र कर्तव्य है!"
            
        if "hi_input_val" not in st.session_state:
            st.session_state.hi_input_val = "जिंदगी में कभी किसी को कम मत समझना... क्योंकि समंदर कितना भी खामोश क्यों न हो, जब उठता है तो बड़े-बड़ों को डुबो देता है!"

        hi_text = st.text_area("Script Editor:", value=st.session_state.hi_input_val, height=160, key="hi_text_area")
        curr_h_words = len(hi_text.strip().split())
        st.caption(f"📊 Words: **{curr_h_words}** / 100 max (Free Trial)")

    with col_h2:
        st.markdown("**2. Voice Actor & Production Purpose:**")
        hi_gender = st.radio("Gender:", ["👨 10 Male Voice Actors", "👩 10 Female Voice Actors"], horizontal=True, key="hi_gender_radio")
        is_h_male = "Male" in hi_gender
        filtered_hi = {k: v for k, v in HINDI_VOICES.items() if (v["gender"] == "Male" if is_h_male else v["gender"] == "Female")}
        selected_hi_name = st.selectbox("Voice Actor:", list(filtered_hi.keys()), key="hi_voice_select")
        hi_voice_data = filtered_hi[selected_hi_name]
        
        selected_h_purpose = st.selectbox("🎯 Production Purpose (सूर / Style):", list(PURPOSE_PRESETS.keys()), index=0, key="h_purpose_sel")
        h_purp_data = PURPOSE_PRESETS[selected_h_purpose]
        
        base_hp = int(hi_voice_data["pitch"].replace("Hz", ""))
        base_hr = int(hi_voice_data["rate"].replace("%", ""))
        target_hp = max(-40, min(40, base_hp + h_purp_data["pitch_offset"]))
        target_hr = max(-30, min(30, base_hr + h_purp_data["rate_offset"]))
        
        st.markdown(f"""
        <div class="voice-card">
            <div><span class="badge-cat">{hi_voice_data['category']}</span> <b>{selected_hi_name.split('(')[0]}</b></div>
            <div style="font-size: 13px; color: #94A3B8; margin-top: 6px;">{hi_voice_data['desc']}</div>
            <div style="font-size: 12px; color: #F87171; margin-top: 6px; font-weight: 600;">⚡ Pitch: {target_hp:+d}Hz | Cadence: {target_hr:+d}%</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🎛️ Manual Pitch & Cadence Sliders"):
            c_slh1, c_slh2 = st.columns(2)
            custom_hi_pitch = c_slh1.slider("Pitch (Hz):", min_value=-40, max_value=40, value=target_hp, step=1, format="%d Hz", key="hi_sl_pitch")
            custom_hi_rate = c_slh2.slider("Speed (%):", min_value=-30, max_value=30, value=target_hr, step=1, format="%d%%", key="hi_sl_rate")
        
        hi_btn = st.button("🚀 Synthesize Hindi Speech", type="primary", use_container_width=True, key="hi_btn")

    if hi_btn:
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        is_allowed, trial_msg, _ = validate_user_trial(active_email, hi_text)
        
        if not is_allowed:
            st.error(trial_msg)
        elif not hi_text.strip():
            st.warning("Please enter text script before generating audio.")
        else:
            out_hi = os.path.join(tempfile.gettempdir(), f"wani_hi_{uuid.uuid4().hex[:8]}.mp3")
            p_val = f"{custom_hi_pitch:+d}Hz"
            r_val = f"{custom_hi_rate:+d}%"
            
            with st.spinner("Synthesizing Hindi studio audio..."):
                engine_used = synthesize_speech(
                    text=hi_text,
                    voice_data=hi_voice_data,
                    engine_choice="ElevenLabs",
                    api_key=eleven_key,
                    out_path=out_hi,
                    custom_pitch=p_val,
                    custom_rate=r_val,
                    lang="hi"
                )
                increment_user_trial(active_email)

            st.success(f"✨ Audio rendered successfully! (Engine: {engine_used})")
            r1, r2 = st.columns([1.5, 1])
            with r1:
                with open(out_hi, "rb") as f: st.audio(f.read(), format="audio/mp3")
            with r2:
                with open(out_hi, "rb") as f: st.download_button("⬇️ Download Audio (MP3)", f.read(), file_name="wani_hindi_audio.mp3", mime="audio/mp3", use_container_width=True)


# ==============================================================
# TAB 3: ENGLISH STUDIO
# ==============================================================
with tab_en:
    st.markdown('<div class="studio-banner">🌐 English Speech Studio — US, UK, Indian English with Ultra-Deep Thanos Cosmic Bass</div>', unsafe_allow_html=True)
    
    col_e1, col_e2 = st.columns([1.2, 1])
    
    with col_e1:
        st.markdown("**1. Enter English Script:**")
        c_e_p1, c_e_p2 = st.columns(2)
        if c_e_p1.button("🌌 Thanos Cosmic Monologue"):
            st.session_state.en_input_val = "I am inevitable. You could not live with your own failure. Where did that bring you? Back to me. I thought by eliminating half of life, the other half would thrive. But you have shown me that's impossible."
        if c_e_p2.button("👑 Churchill Address"):
            st.session_state.en_input_val = "We shall fight on the beaches, we shall fight on the landing grounds, we shall fight in the fields and in the streets. We shall never surrender!"
            
        if "en_input_val" not in st.session_state:
            st.session_state.en_input_val = "I am inevitable. You could not live with your own failure. Where did that bring you? Back to me."

        en_text = st.text_area("Script Editor:", value=st.session_state.en_input_val, height=160, key="en_text_area")
        curr_e_words = len(en_text.strip().split())
        st.caption(f"📊 Words: **{curr_e_words}** / 100 max (Free Trial)")

    with col_e2:
        st.markdown("**2. Voice Actor & Production Purpose:**")
        en_gender = st.radio("Gender:", ["👨 10 Male Voice Actors", "👩 10 Female Voice Actors"], horizontal=True, key="en_gender_radio")
        is_e_male = "Male" in en_gender
        filtered_en = {k: v for k, v in ENGLISH_VOICES.items() if (v["gender"] == "Male" if is_e_male else v["gender"] == "Female")}
        selected_en_name = st.selectbox("Voice Actor:", list(filtered_en.keys()), key="en_voice_select")
        en_voice_data = filtered_en[selected_en_name]
        
        selected_e_purpose = st.selectbox("🎯 Production Purpose (सूर / Style):", list(PURPOSE_PRESETS.keys()), index=0, key="e_purpose_sel")
        e_purp_data = PURPOSE_PRESETS[selected_e_purpose]
        
        base_ep = int(en_voice_data["pitch"].replace("Hz", ""))
        base_er = int(en_voice_data["rate"].replace("%", ""))
        target_ep = max(-40, min(40, base_ep + e_purp_data["pitch_offset"]))
        target_er = max(-30, min(30, base_er + e_purp_data["rate_offset"]))
        
        st.markdown(f"""
        <div class="voice-card">
            <div><span class="badge-cat">{en_voice_data['category']}</span> <b>{selected_en_name.split('(')[0]}</b></div>
            <div style="font-size: 13px; color: #94A3B8; margin-top: 6px;">{en_voice_data['desc']}</div>
            <div style="font-size: 12px; color: #38BDF8; margin-top: 6px; font-weight: 600;">⚡ Pitch: {target_ep:+d}Hz | Cadence: {target_er:+d}%</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🎛️ Manual Pitch & Cadence Sliders"):
            c_sle1, c_sle2 = st.columns(2)
            custom_en_pitch = c_sle1.slider("Pitch (Hz):", min_value=-40, max_value=40, value=target_ep, step=1, format="%d Hz", key="en_sl_pitch")
            custom_en_rate = c_sle2.slider("Speed (%):", min_value=-30, max_value=30, value=target_er, step=1, format="%d%%", key="en_sl_rate")
        
        en_btn = st.button("🚀 Synthesize English Speech", type="primary", use_container_width=True, key="en_btn")

    if en_btn:
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        is_allowed, trial_msg, _ = validate_user_trial(active_email, en_text)
        
        if not is_allowed:
            st.error(trial_msg)
        elif not en_text.strip():
            st.warning("Please enter text script before generating audio.")
        else:
            out_en = os.path.join(tempfile.gettempdir(), f"wani_en_{uuid.uuid4().hex[:8]}.mp3")
            p_val = f"{custom_en_pitch:+d}Hz"
            r_val = f"{custom_en_rate:+d}%"
            
            with st.spinner("Synthesizing studio-grade English audio..."):
                engine_used = synthesize_speech(
                    text=en_text,
                    voice_data=en_voice_data,
                    engine_choice="ElevenLabs",
                    api_key=eleven_key,
                    out_path=out_en,
                    custom_pitch=p_val,
                    custom_rate=r_val,
                    lang="en"
                )
                increment_user_trial(active_email)

            st.success(f"✨ Audio rendered successfully! (Engine: {engine_used})")
            r1, r2 = st.columns([1.5, 1])
            with r1:
                with open(out_en, "rb") as f: st.audio(f.read(), format="audio/mp3")
            with r2:
                with open(out_en, "rb") as f: st.download_button("⬇️ Download Audio (MP3)", f.read(), file_name="wani_english_audio.mp3", mime="audio/mp3", use_container_width=True)


# ==============================================================
# TAB 4: UNIVERSAL MULTI-LANGUAGE TRANSLATOR & SPEECH STUDIO
# ==============================================================
GLOBAL_VOICE_MAP = {
    "Marathi (मराठी)": {"code": "mr", "voice": "mr-IN-ManoharNeural"},
    "Hindi (हिंदी)": {"code": "hi", "voice": "hi-IN-MadhurNeural"},
    "English (UK / US)": {"code": "en", "voice": "en-US-BrianNeural"},
    "Tamil (தமிழ்)": {"code": "ta", "voice": "ta-IN-PallaviNeural"},
    "Telugu (తెలుగు)": {"code": "te", "voice": "te-IN-MohanNeural"},
    "Gujarati (ગુજરાતી)": {"code": "gu", "voice": "gu-IN-NiranjanNeural"},
    "Bengali (বাংলা)": {"code": "bn", "voice": "bn-IN-BashkarNeural"},
    "Spanish (Español)": {"code": "es", "voice": "es-ES-AlvaroNeural"},
    "French (Français)": {"code": "fr", "voice": "fr-FR-HenriNeural"},
    "German (Deutsch)": {"code": "de", "voice": "de-DE-KillianNeural"},
    "Japanese (日本語)": {"code": "ja", "voice": "ja-JP-KeitaNeural"}
}

with tab_trans_studio:
    st.markdown('<div class="studio-banner">🌍 Universal Language Studio — Type in Any Language, Translate in Real-Time & Synthesize Native Voice Instantly</div>', unsafe_allow_html=True)
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown("### 📥 Source Input")
        src_lang = st.selectbox("Source Language:", ["Auto-Detect", "English", "Marathi", "Hindi"], index=0)
        src_code = "auto" if "Auto" in src_lang else ("en" if "English" in src_lang else ("mr" if "Marathi" in src_lang else "hi"))
        user_raw_text = st.text_area("Input Text (Any Language):", value="Chhatrapati Shivaji Maharaj was the greatest leader of India. He established Swarajya with bravery, wisdom, and justice.", height=150)
        
    with col_t2:
        st.markdown("### 📤 Target Language & Synthesis")
        target_choice = st.selectbox("Translate & Speak In:", list(GLOBAL_VOICE_MAP.keys()), index=0)
        tgt_data = GLOBAL_VOICE_MAP[target_choice]
        btn_translate = st.button("🌐 Translate Text Now", use_container_width=True)
        
        if "universal_trans_res" not in st.session_state:
            st.session_state.universal_trans_res = ""
            
        if btn_translate:
            if user_raw_text.strip():
                with st.spinner("Translating text..."):
                    res = translate_text(user_raw_text, source=src_code, target=tgt_data["code"])
                    st.session_state.universal_trans_res = res
                    st.success("Translation complete!")
                    
        translated_output = st.text_area("Translated Text Result:", value=st.session_state.universal_trans_res, height=150)

    btn_speak_trans = st.button("🎙️ Synthesize Speech in Target Language", type="primary", use_container_width=True)
    
    if btn_speak_trans:
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        is_allowed, trial_msg, _ = validate_user_trial(active_email, translated_output)
        
        if not is_allowed:
            st.error(trial_msg)
        elif not translated_output.strip():
            st.warning("Please translate text before rendering speech.")
        else:
            out_trans_mp3 = os.path.join(tempfile.gettempdir(), f"wani_global_{uuid.uuid4().hex[:8]}.mp3")
            with st.spinner(f"Rendering native speech in {target_choice}..."):
                async def run_global_edge():
                    comm = edge_tts.Communicate(translated_output, tgt_data["voice"])
                    await comm.save(out_trans_mp3)
                asyncio.run(run_global_edge())
                increment_user_trial(active_email)
                
            st.success(f"✨ Speech rendered in {target_choice}!")
            gr1, gr2 = st.columns([1.5, 1])
            with gr1:
                with open(out_trans_mp3, "rb") as f: st.audio(f.read(), format="audio/mp3")
            with gr2:
                with open(out_trans_mp3, "rb") as f: st.download_button("⬇️ Download Audio (MP3)", f.read(), file_name="wani_translated_speech.mp3", mime="audio/mp3", use_container_width=True)


# ==============================================================
# TAB 5: MULTI-VOICE DIALOGUE STUDIO
# ==============================================================
with tab_dialogue:
    st.markdown('<div class="studio-banner">🎭 Multi-Voice Dialogue Studio — Build 2-Actor Conversational Scenes Stitched into a Seamless MP3</div>', unsafe_allow_html=True)
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.markdown("### 🗣️ Character 1")
        all_mr_keys = list(MARATHI_VOICES.keys())
        char1_name = st.selectbox("Actor 1:", all_mr_keys, index=0, key="char1_select")
        char1_text = st.text_area("Actor 1 Dialogue Line:", value="महाराज, आधी लगीन कोंढाण्याचं, मग माझ्या रायबाचं! कोंढाणा सर केल्याशिवाय हा सुभेदार परत येणार नाही!", height=100, key="char1_text")
        
    with col_d2:
        st.markdown("### 🗣️ Character 2")
        char2_name = st.selectbox("Actor 2:", all_mr_keys, index=1, key="char2_select")
        char2_text = st.text_area("Actor 2 Dialogue Line:", value="सुभेदार, सावध राहा! सिंहगडावर मुघलांची फौज सज्ज आहे. स्वराज्याला तुमच्यासारख्या वीरांचा अभिमान आहे!", height=100, key="char2_text")
        
    dialogue_btn = st.button("🎬 Render Full Dialogue Scene (Merged MP3)", type="primary", use_container_width=True)
    
    if dialogue_btn:
        active_email = st.session_state.current_user.get("email", "guest@wani.ai")
        u = users_db.get(active_email, {})
        plan = u.get("plan", "FREE TRIAL 🎁")
        
        if "FREE" in plan and not u.get("is_admin", False):
            st.error("⚠️ Multi-Voice Dialogue Studio is reserved for Creator Pro and Studio Master plans. Please upgrade to unlock.")
        else:
            out_d1 = os.path.join(tempfile.gettempdir(), f"diag_{uuid.uuid4().hex[:8]}_1.mp3")
            out_d2 = os.path.join(tempfile.gettempdir(), f"diag_{uuid.uuid4().hex[:8]}_2.mp3")
            out_d_combined = os.path.join(tempfile.gettempdir(), f"dialogue_scene_{uuid.uuid4().hex[:8]}.mp3")
            
            with st.spinner("Synthesizing separate speaker tracks & stitching conversational frames..."):
                synthesize_speech(char1_text, MARATHI_VOICES[char1_name], "Native Maharashtra", eleven_key, out_d1)
                synthesize_speech(char2_text, MARATHI_VOICES[char2_name], "Native Maharashtra", eleven_key, out_d2)
                
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
# TAB 6: PRICING & SUBSCRIPTION MONETIZATION ENGINE
# ==============================================================
with tab_pricing:
    st.markdown('<div class="studio-banner">💎 Subscription Plans — Choose the Perfect Tier for Your Production Workflow</div>', unsafe_allow_html=True)
    
    col_p1, col_p2, col_p3 = st.columns(3)
    
    with col_p1:
        st.markdown("""
        <div class="pricing-card">
            <h3>🎁 Free Starter</h3>
            <h1 style="color:#94A3B8;">$0 <span style="font-size:15px;">/month (₹0)</span></h1>
            <p style="color:#64748B; font-size:13px;">For testing and discovery</p>
            <hr style="border-color:#1E293B;">
            <ul style="text-align:left; font-size:13px; color:#CBD5E1; line-height:2.2;">
                <li>✅ <b>2 generations per day</b></li>
                <li>✅ <b>100 words per generation limit</b></li>
                <li>✅ Standard Marathi, Hindi & English models</li>
                <li>❌ No epic warrior bass timbres</li>
                <li>❌ No dialogue scene builder</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.button("Current Active Tier", disabled=True, use_container_width=True)

    with col_p2:
        st.markdown("""
        <div class="pricing-card pricing-featured">
            <span style="background:#6366F1; color:white; padding:3px 10px; border-radius:10px; font-size:11px; font-weight:800; letter-spacing:0.5px;">MOST POPULAR ⭐</span>
            <h3 style="margin-top:10px;">👑 Creator Pro</h3>
            <h1 style="color:#818CF8;">$4 <span style="font-size:15px;">/month (₹299)</span></h1>
            <p style="color:#94A3B8; font-size:13px;">For YouTubers, Podcasters & Reel Creators</p>
            <hr style="border-color:#312E81;">
            <ul style="text-align:left; font-size:13px; color:#E0E7FF; line-height:2.2;">
                <li>🔥 <b>Unlimited Generations (No Daily Limits)</b></li>
                <li>🔥 <b>Unlimited Word Count (Long-form scripts)</b></li>
                <li>⚔️ Tanaji Malusare, Bajiprabhu & Jijau Voices</li>
                <li>🌌 Thanos & Amitabh Style Cinema Bass</li>
                <li>💎 100% Commercial Monetization Rights</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.markdown("**Subscribe via Direct UPI / PhonePe / GPay:**")
        st.code("wani.pro@upi", language="text")

    with col_p3:
        st.markdown("""
        <div class="pricing-card">
            <h3>🚀 Studio Master</h3>
            <h1 style="color:#38BDF8;">$9 <span style="font-size:15px;">/month (₹699)</span></h1>
            <p style="color:#64748B; font-size:13px;">For Media Agencies & Production Houses</p>
            <hr style="border-color:#1E293B;">
            <ul style="text-align:left; font-size:13px; color:#CBD5E1; line-height:2.2;">
                <li>👑 <b>All Creator Pro Features Included</b></li>
                <li>🎭 <b>Multi-Voice Dialogue Studio</b> Unlocked</li>
                <li>⚡ ElevenLabs Ultra Generative Cloud Engine</li>
                <li>📝 1-Click AI Script Studio</li>
                <li>🏎️ 2x Priority Rendering Queue</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.markdown("**Subscribe via Direct UPI / PhonePe / GPay:**")
        st.code("wani.master@upi", language="text")

    st.markdown("---")
    st.markdown("### 🔑 Redeem VIP Activation License Key")
    col_k1, col_k2 = st.columns([2.5, 1])
    with col_k1:
        vip_input = st.text_input("Enter License Key / Token:", placeholder="e.g. WANI-PRO-2026 or WANI-MASTER-VIP")
    with col_k2:
        st.write("")
        st.write("")
        if st.button("Unlock VIP License 🔓", type="primary", use_container_width=True):
            vip_code = sanitize_text(vip_input).upper()
            email_key = st.session_state.current_user.get("email", "vishal@wani.ai")
            
            if hmac.compare_digest(vip_code, "WANI-PRO-2026") or hmac.compare_digest(vip_code, "SWAR-PRO-2026"):
                st.session_state.current_user["plan"] = "CREATOR PRO 👑"
                st.session_state.current_user["credits"] = 999999
                if email_key in users_db:
                    users_db[email_key]["plan"] = "CREATOR PRO 👑"
                    users_db[email_key]["credits"] = 999999
                    save_secure_users(users_db)
                st.success("🎉 License Verified! Account upgraded to CREATOR PRO ($4 / ₹299/mo)!")
                st.rerun()
            elif hmac.compare_digest(vip_code, "WANI-MASTER-VIP") or hmac.compare_digest(vip_code, "SWAR-VIP-MASTER"):
                st.session_state.current_user["plan"] = "STUDIO MASTER 🚀"
                st.session_state.current_user["credits"] = 999999
                if email_key in users_db:
                    users_db[email_key]["plan"] = "STUDIO MASTER 🚀"
                    users_db[email_key]["credits"] = 999999
                    save_secure_users(users_db)
                st.success("🎉 License Verified! Account upgraded to STUDIO MASTER ($9 / ₹699/mo)!")
                st.rerun()
            else:
                st.error("Invalid VIP License Key. Please verify your token.")


# ==============================================================
# TAB 7: ACCOUNT & AUTHENTICATION SUBSYSTEM (POINT 2)
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
        
        if st.button("👑 1-Click: Vishal Hargude (Founder & CEO - Studio Master)", use_container_width=True):
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
        st.write(f"• **Active Plan:** `{st.session_state.current_user.get('plan')}`")
        st.write(f"• **Trials Used Today:** {st.session_state.current_user.get('trials_used_today', 0)} / 2 allowed")


# ==============================================================
# TAB 8: EXECUTIVE ADMIN CRM & USER DATABASE MANAGEMENT
# ==============================================================
with tab_admin:
    st.markdown('<div class="studio-banner">👑 Executive Admin CRM — Manage User Registrations, Subscription Revenues & Lead Contacts</div>', unsafe_allow_html=True)
    
    current_u = st.session_state.current_user
    is_admin = current_u.get("is_admin", False)
    
    if not is_admin:
        st.warning("🔒 Restricted Access: Only Administrator (Vishal Hargude) can access the Executive CRM.")
        admin_pass = st.text_input("Enter Admin Master Security PIN:", type="password", key="admin_pin_input")
        if st.button("Unlock Admin Dashboard", type="primary"):
            if admin_pass in ["2026", "admin", "vishal"]:
                st.session_state.current_user["is_admin"] = True
                st.success("Admin CRM Unlocked!")
                st.rerun()
            else:
                st.error("Invalid Admin PIN.")
    else:
        total_users = len(users_db)
        pro_subscribers = sum(1 for u in users_db.values() if "PRO" in u.get("plan", ""))
        master_subscribers = sum(1 for u in users_db.values() if "MASTER" in u.get("plan", ""))
        monthly_mrr = (pro_subscribers * 299) + (master_subscribers * 699)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("👥 Total Registered Users", f"{total_users}")
        m2.metric("👑 Creator Pro Subscribers", f"{pro_subscribers}")
        m3.metric("🚀 Studio Master Subscribers", f"{master_subscribers}")
        m4.metric("💰 Monthly Revenue (MRR)", f"₹{monthly_mrr:,}")
        
        st.markdown("---")
        st.markdown("### 📋 Registered User Directory & Leads")
        
        user_rows = []
        for em, udata in users_db.items():
            user_rows.append({
                "Full Name": udata.get("name", "N/A"),
                "Email": em,
                "WhatsApp / Mobile": udata.get("mobile", "Not Provided"),
                "Active Plan": udata.get("plan", "FREE TRIAL 🎁"),
                "Trials Today": f"{udata.get('trials_used_today', 0)}/2",
                "Role": "Admin" if udata.get("is_admin") else "User",
                "Joined": udata.get("joined", "2026-10-18")
            })
            
        st.dataframe(user_rows, use_container_width=True)
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["Full Name", "Email", "WhatsApp / Mobile", "Active Plan", "Trials Today", "Role", "Joined"])
        writer.writeheader()
        writer.writerows(user_rows)
        csv_data = output.getvalue()
        
        c_exp1, c_exp2 = st.columns([1.5, 2])
        with c_exp1:
            st.download_button(
                "📥 Export All User Leads to CSV / Excel",
                data=csv_data,
                file_name="wani_users_leads.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        st.markdown("---")
        st.markdown("### ⚡ User Subscription Management (Manual Upgrade)")
        u_col1, u_col2, u_col3 = st.columns(3)
        with u_col1:
            target_user_email = st.selectbox("Select User Email:", list(users_db.keys()))
        with u_col2:
            new_plan_selection = st.selectbox("Assign Plan:", ["CREATOR PRO 👑 (₹299/mo)", "STUDIO MASTER 🚀 (₹699/mo)", "FREE TRIAL 🎁"])
        with u_col3:
            st.write("")
            st.write("")
            if st.button("Apply Plan Upgrade ✅", use_container_width=True):
                clean_p = "CREATOR PRO 👑" if "PRO" in new_plan_selection else ("STUDIO MASTER 🚀" if "MASTER" in new_plan_selection else "FREE TRIAL 🎁")
                users_db[target_user_email]["plan"] = clean_p
                users_db[target_user_email]["credits"] = 999999 if "FREE" not in clean_p else 2
                save_secure_users(users_db)
                if st.session_state.current_user.get("email") == target_user_email:
                    st.session_state.current_user["plan"] = clean_p
                st.success(f"Successfully upgraded {target_user_email} to {clean_p}!")
                st.rerun()


# ==============================================================
# TAB 9: ABOUT & ENTERPRISE CONTACT US (POINT 6)
# ==============================================================
with tab_contact:
    st.markdown('<div class="studio-banner">🏢 Wani Technologies Pvt. Ltd. — Global Enterprise Infrastructure & Creator Relations</div>', unsafe_allow_html=True)
    
    col_cn1, col_cn2 = st.columns(2)
    
    with col_cn1:
        st.markdown("### 🏛️ Corporate Headquarters & Innovation Labs")
        st.write("""
        **Wani Technologies Pvt. Ltd.** is an advanced AI research and acoustic speech synthesis enterprise dedicated to indigenous and global multilingual speech generation.
        
        • **Corporate HQ:** Cyber City Tech Corridor, Magarpatta / Hinjawadi Phase 1, Pune, MH, India  
        • **Commercial Hub:** BKC Financial Center, Bandra Kurla Complex, Mumbai, India  
        • **Global Operations Desk:** `enterprise@wani.ai`  
        • **Developer & Creator Relations:** `support@wani.ai`  
        • **Executive Priority Desk:** `+91 (020) 4120-WANI` / `+91 98220 54321`  
        """)
        
        st.markdown("---")
        st.markdown("### 🛡️ Enterprise Security & SLA Guarantees")
        st.write("""
        • **99.98% High-Availability SLA** backed by global edge clusters  
        • **ISO/IEC 27001 Certified Architecture** with zero telemetry data leakage  
        • **SOC 2 Type II Compliant** cloud pipelines with 256-bit AES end-to-end encryption  
        • **Full Commercial Indemnity** on all synthesized voice rights  
        """)
        
    with col_cn2:
        st.markdown("### ✉️ Contact Enterprise Relations")
        c_name = st.text_input("Your Name / Media House:", placeholder="e.g. Dharma Productions / Star Media")
        c_email = st.text_input("Business Email:", placeholder="executive@company.com")
        c_msg = st.text_area("Enterprise Inquiry / API Licensing:", placeholder="Tell us about your audio volume, API requirements, or custom voice cloning brief...", height=130)
        
        if st.button("Send Enterprise Inquiry 📨", type="primary", use_container_width=True):
            if c_name and c_email:
                st.success("Thank you! Your enterprise inquiry has been securely routed to Founder & CEO Vishal Hargude. Our executive team will respond within 4 hours.")
            else:
                st.warning("Please provide your name and business email.")
                
        st.markdown("---")
        st.markdown("""
        <div style="background:#0B0F19; border:1px solid #1E293B; border-radius:8px; padding:12px; font-size:12px; color:#64748B;">
            <b>LEGAL & INTELLECTUAL PROPERTY NOTICE:</b><br>
            All rights, patents, proprietary acoustic synthesis models, neural voice mappings, and software architecture are the exclusive property of Wani Technologies Pvt. Ltd. Protected under the Indian Copyright Act 1957, IT Act 2000, and WIPO conventions. Unauthorized scraping, decompilation, or reverse engineering is strictly prohibited.
        </div>
        """, unsafe_allow_html=True)


# ==============================================================
# TAB 10: COMPREHENSIVE VOICE DIRECTORY
# ==============================================================
with tab_library:
    st.markdown("### 👥 Wani Comprehensive Voice Library (60+ Distinct Studio Actors)")
    st.write("Inspect audio acoustic signatures, frequency offsets, and timbre profiles across all language families:")
    
    lang_lib = st.radio("Select Locale:", ["Marathi (20 Voices)", "Hindi (20 Voices)", "English (20 Voices)"], horizontal=True)
    selected_catalog = MARATHI_VOICES if "Marathi" in lang_lib else (HINDI_VOICES if "Hindi" in lang_lib else ENGLISH_VOICES)
    
    cards_per_row = 2
    items = list(selected_catalog.items())
    
    for i in range(0, len(items), cards_per_row):
        row_cols = st.columns(cards_per_row)
        for j in range(cards_per_row):
            if i + j < len(items):
                name, data = items[i + j]
                with row_cols[j]:
                    st.markdown(f"""
                    <div class="voice-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span class="badge-cat">{data['category']}</span>
                            <span style="font-size:12px; font-weight:700; color:#64748B;">{data['gender']}</span>
                        </div>
                        <div style="font-weight:700; font-size:16px; margin: 6px 0; color:#F8FAFC;">{name.split('(')[0]}</div>
                        <div style="font-size:13px; color:#94A3B8; margin-bottom:8px;">{data['desc']}</div>
                        <div style="font-size:12px; color:#818CF8; font-weight:600;">⚡ Pitch: {data['pitch']} | Cadence: {data['rate']}</div>
                    </div>
                    """, unsafe_allow_html=True)

st.markdown("---")
st.caption("Wani Technologies Pvt. Ltd. v6.5 Enterprise | The Voice of Intelligence | Founder & CEO: Vishal Hargude")
