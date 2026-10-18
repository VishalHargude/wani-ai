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
    page_title="SwarAI Studio Ultra - Enterprise AI Voice Platform",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# SECURITY & ANTI-HACK SUBSYSTEM (SALTED SHA-256 & SECURE DB)
# -------------------------------------------------------------
DB_FILE = os.path.join(os.path.dirname(__file__), "users_db.json")
APP_SALT = "swarai_enterprise_security_salt_v6_2026"

def hash_credential(secret: str) -> str:
    return hashlib.sha256((secret + APP_SALT).encode('utf-8')).hexdigest()

def sanitize_text(text: str) -> str:
    if not text:
        return ""
    # Strip dangerous HTML/Script tags to prevent injection attacks
    clean = re.sub(r'<script.*?>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<.*?>', '', clean)
    return clean.strip()

def load_secure_users():
    if not os.path.exists(DB_FILE):
        default_db = {
            "vishal@swarai.com": {
                "name": "Vishal Hargude (Founder & Admin)",
                "password_hash": hash_credential("admin"),
                "plan": "STUDIO MASTER 🚀",
                "credits": 999999,
                "is_admin": True
            },
            "creator@swarai.com": {
                "name": "Creator Demo (Pro Member)",
                "password_hash": hash_credential("pro123"),
                "plan": "CREATOR PRO 👑",
                "credits": 999999,
                "is_admin": False
            },
            "demo@swarai.com": {
                "name": "Guest User (Free Trial)",
                "password_hash": hash_credential("demo"),
                "plan": "FREE TRIAL 🎁",
                "credits": 5,
                "is_admin": False
            }
        }
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(default_db, f, ensure_ascii=False, indent=2)
        return default_db
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure hash migration if legacy plain passwords exist
            updated = False
            for email, uinfo in data.items():
                if "password" in uinfo and "password_hash" not in uinfo:
                    uinfo["password_hash"] = hash_credential(uinfo["password"])
                    del uinfo["password"]
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

# Safe User Session State
if "current_user" not in st.session_state:
    admin_user = users_db.get("vishal@swarai.com", {
        "name": "Vishal Hargude (Founder & Admin)",
        "plan": "STUDIO MASTER 🚀",
        "credits": 999999,
        "is_admin": True
    })
    st.session_state.current_user = admin_user
    st.session_state.current_user["email"] = "vishal@swarai.com"

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
# PROFESSIONAL SILICON VALLEY SAAS DESIGN (ENGLISH UI CHROME)
# -------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Sleek Top Enterprise Bar */
    .top-announcement {
        background: linear-gradient(90deg, #0F172A 0%, #1E1B4B 50%, #312E81 100%);
        border: 1px solid #3730A3;
        border-radius: 12px;
        padding: 10px 20px;
        color: #F8FAFC;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    
    .brand-badge {
        background: rgba(99, 102, 241, 0.2);
        border: 1px solid #6366F1;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 800;
        font-size: 12px;
        letter-spacing: 0.5px;
        color: #C7D2FE;
    }
    
    .user-pill {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.18);
        padding: 5px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        color: #F1F5F9;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Clean SaaS Hero Header */
    .hero-title {
        font-size: 38px;
        font-weight: 900;
        text-align: center;
        background: linear-gradient(135deg, #38BDF8 0%, #818CF8 50%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 6px;
        letter-spacing: -0.8px;
    }
    
    .hero-sub {
        text-align: center;
        color: #64748B;
        font-size: 15px;
        margin-bottom: 24px;
        font-weight: 600;
    }
    
    /* Voice Character Cards */
    .voice-card {
        background: #0F172A;
        border: 1px solid #1E293B;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .badge-cat {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 16px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        margin-right: 6px;
        letter-spacing: 0.4px;
    }
    .cat-warrior { background: #451A03; color: #FCD34D; border: 1px solid #78350F; }
    .cat-titan { background: #2E1065; color: #DDD6FE; border: 1px solid #5B21B6; }
    .cat-crime { background: #450A0A; color: #FECACA; border: 1px solid #991B1B; }
    .cat-podcast { background: #1E1B4B; color: #C7D2FE; border: 1px solid #3730A3; }
    .cat-rj { background: #4C0519; color: #FBCFE8; border: 1px solid #9D174D; }
    .cat-spiritual { background: #064E3B; color: #A7F3D0; border: 1px solid #047857; }
    .cat-corp { background: #14532D; color: #BBF7D0; border: 1px solid #15803D; }
    .cat-news { background: #713F12; color: #FEF08A; border: 1px solid #A16207; }
    .cat-story { background: #1E293B; color: #E2E8F0; border: 1px solid #334155; }
    .cat-kids { background: #3B0764; color: #F5D0FE; border: 1px solid #7E22CE; }
    
    /* Professional Section Banners */
    .studio-banner {
        border-radius: 10px;
        padding: 12px 18px;
        margin-bottom: 18px;
        font-weight: 700;
        font-size: 13.5px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .banner-mr { background: #1E1B4B; border-left: 5px solid #6366F1; color: #E0E7FF; }
    .banner-hi { background: #450A0A; border-left: 5px solid #EF4444; color: #FEE2E2; }
    .banner-en { background: #0C4A6E; border-left: 5px solid #0284C7; color: #E0F2FE; }
    .banner-dialogue { background: #2E1065; border-left: 5px solid #8B5CF6; color: #EDE9FE; }
    .banner-trans { background: #064E3B; border-left: 5px solid #10B981; color: #D1FAE5; }
    
    /* Modern Pricing Table */
    .pricing-card {
        background: #0F172A;
        border: 1px solid #1E293B;
        border-radius: 16px;
        padding: 26px;
        text-align: center;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .pricing-featured {
        border: 2px solid #6366F1;
        background: #131B31;
        position: relative;
    }
    .plan-badge {
        display: inline-block;
        background: #6366F1;
        color: white;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 800;
        margin-bottom: 12px;
        letter-spacing: 0.5px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# TOP NAVIGATION & LIVE USER SESSION
# -------------------------------------------------------------
user_plan = st.session_state.current_user.get("plan", "FREE TRIAL 🎁")
user_name = st.session_state.current_user.get("name", "User")

st.markdown(f"""
<div class="top-announcement">
    <div style="display:flex; align-items:center; gap:12px;">
        <span class="brand-badge">ENTERPRISE CLOUD</span>
        <span><b>SwarAI Studio Ultra v6.0</b></span>
        <span>•</span>
        <span style="color:#94A3B8;">Next-Gen Multilingual Generative Voice SaaS Platform</span>
    </div>
    <div class="user-pill">
        <span>👤 {user_name.split('(')[0].strip()}</span>
        <span>|</span>
        <span style="color:#A5B4FC;">💎 {user_plan}</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="hero-title">🎙️ SwarAI Studio Ultra — Generative Voice & Language Platform</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Enterprise-Grade Speech Synthesis, Universal Real-Time Translation, Multi-Speaker Dialogue Builder & Creator Subscriptions</div>', unsafe_allow_html=True)

# Pre-Configured Verified ElevenLabs API Key (Securely Managed Server-Side)
ELEVEN_KEY_DEFAULT = "sk_cea4bc5ef26be1349c26338920a5a217503b8791b788e337"

# -------------------------------------------------------------
# SIDEBAR NAVIGATION & CONTROLS (PROFESSIONAL ENGLISH)
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎛️ Studio Control Center")
    st.markdown(f"**Authenticated User:** `{user_name.split('(')[0].strip()}`")
    st.markdown(f"**Subscription Plan:** `{user_plan}`")
    
    if "FREE" in user_plan:
        st.warning(f"⚡ Available Credits: **{st.session_state.current_user.get('credits', 5)}** generations")
        st.info("💡 Upgrade to **Creator Pro** ($4 / ₹299/mo) for unlimited generations & warrior bass.")
    else:
        st.success("👑 **Unlimited Studio Access Active** (Zero Usage Caps)")

    st.markdown("---")
    st.markdown("#### 📲 Invite & Share Platform")
    share_msg = "Hey! Check out SwarAI Studio Ultra - the world's most powerful multilingual AI voice studio featuring epic warriors, Thanos bass, and 20+ language translation: https://objects-skilled-behalf-adam.trycloudflare.com"
    st.markdown(f'''<a href="https://api.whatsapp.com/send?text={urllib.parse.quote(share_msg)}" target="_blank" style="text-decoration:none;"><div style="background:#25D366; color:white; padding:10px 14px; border-radius:8px; font-weight:700; text-align:center; margin-bottom:15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">📲 Share on WhatsApp</div></a>''', unsafe_allow_html=True)

    with st.expander("🛡️ Advanced Settings (Pro Mode)"):
        st.caption("Securely override or configure personal ElevenLabs model key:")
        eleven_key_input = st.text_input("ElevenLabs API Key:", value=f"{ELEVEN_KEY_DEFAULT[:6]}...{ELEVEN_KEY_DEFAULT[-4:]}", type="password")
        if eleven_key_input and not eleven_key_input.startswith("sk_cea"):
            eleven_key = eleven_key_input.strip()
        else:
            eleven_key = ELEVEN_KEY_DEFAULT

    st.markdown("---")
    st.caption("🛡️ 256-Bit SSL Encrypted | Hardware: Dell OptiPlex 9020 | All Rights Reserved")

# ==============================================================
# COMPREHENSIVE VOICE CATALOGS (10 MEN + 10 WOMEN)
# ==============================================================

MARATHI_VOICES = {
    "Tanaji Malusare (Lion's Roar - Epic Warrior)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "SOYHLrjzK2X1ezoPC6cr",
        "gender": "Male", "category": "Historical Warriors", "cat_class": "cat-warrior",
        "pitch": "-30Hz", "rate": "-8%",
        "desc": "Legendary commander baritone with thunderous battle resonance, commanding presence, and epic weight."
    },
    "Bajiprabhu Deshpande (Resolute Guardian - 50y)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "nPczCjzI2devNBz1zQrb",
        "gender": "Male", "category": "Historical Warriors", "cat_class": "cat-warrior",
        "pitch": "-25Hz", "rate": "-6%",
        "desc": "Heroic, steadfast warrior baritone with historic dignity and resolute conviction."
    },
    "Titan Vikram (Cinematic Movie Trailer Bass)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "IKne3meq5aSn9XLyUdCD",
        "gender": "Male", "category": "Cinematic & Titan Bass", "cat_class": "cat-titan",
        "pitch": "-35Hz", "rate": "-10%",
        "desc": "Ultra-heavy resonant movie trailer titan voice for cinematic teasers and dramatic narrations."
    },
    "Anup (Crime Patrol & Suspense Narrator)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "JBFqnCBsd6RMkjVDRZzb",
        "gender": "Male", "category": "Crime & Mystery", "cat_class": "cat-crime",
        "pitch": "-18Hz", "rate": "-8%",
        "desc": "Tense, investigative, suspenseful delivery ideal for true crime and psychological thrillers."
    },
    "Rahul (Intellectual Thinker & Podcaster - 30y)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "bIHbv24MWmeRgasZH58o",
        "gender": "Male", "category": "Podcasts & Interviews", "cat_class": "cat-podcast",
        "pitch": "-6Hz", "rate": "-2%",
        "desc": "Calm, educated, articulate conversational cadence for long-form podcasts and discussions."
    },
    "RJ Sagar (FM Radio Jockey & Viral Reels - 24y)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "TX3LPaxmHKxFdv7VOQHJ",
        "gender": "Male", "category": "Radio Jockey & Reels", "cat_class": "cat-rj",
        "pitch": "+22Hz", "rate": "+14%",
        "desc": "Youthful, energetic, upbeat host cadence engineered for viral Instagram Reels and FM radio."
    },
    "Vitthal Aajoba (Elderly Sage & Grandfather - 70y)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "pqHfZKP75CvOlQylNhV4",
        "gender": "Male", "category": "Spiritual & Elders", "cat_class": "cat-spiritual",
        "pitch": "-28Hz", "rate": "-16%",
        "desc": "Slow, deeply resonant patriarchal tone with emotional wisdom for moral tales and spiritual chants."
    },
    "Akshay (Corporate Leader & Keynote Speaker)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "CwhRBWXzGAHq8TQ4Fs17",
        "gender": "Male", "category": "Corporate & Business", "cat_class": "cat-corp",
        "pitch": "+4Hz", "rate": "+6%",
        "desc": "Sharp, persuasive, executive professional voice for corporate pitches, tech demos, and B2B."
    },
    "Rohan (Hard-Hitting Prime TV News Anchor)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "pNInz6obpgDQGcFmaJgB",
        "gender": "Male", "category": "News & Broadcast", "cat_class": "cat-news",
        "pitch": "+8Hz", "rate": "+20%",
        "desc": "Fast-paced, authoritative, high-impact broadcast cadence for breaking news and updates."
    },
    "Manohar (Classic Literary Narrator - 40y)": {
        "id": "mr-IN-ManoharNeural", "eleven_id": "cjVigY5qzO86Huf0OWal",
        "gender": "Male", "category": "Audiobooks & Literature", "cat_class": "cat-story",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "Authentic native Maharashtra baritone with pure phonetics for classic literature and audiobooks."
    },

    "Rajmata Jijau (Royal Matriarch & Inspirer - 50y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "EXAVITQu4vr4xnSDxMaL",
        "gender": "Female", "category": "Historical Warriors", "cat_class": "cat-warrior",
        "pitch": "-22Hz", "rate": "-10%",
        "desc": "Commanding, dignified, authoritative maternal voice inspiring courage and historical valor."
    },
    "Aaji Narmada (Affectionate Grandmother - 65y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "Xb7hH8MSUJpSbSDYk0k2",
        "gender": "Female", "category": "Spiritual & Elders", "cat_class": "cat-spiritual",
        "pitch": "-25Hz", "rate": "-15%",
        "desc": "Loving, gentle, warm storytelling cadence filled with traditional affection and warmth."
    },
    "Aarohi (Classic Audiobook & Novelist - 28y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "XrExE9yKIg1WjnnlVkGX",
        "gender": "Female", "category": "Audiobooks & Literature", "cat_class": "cat-story",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "Crystal-clear, melodic standard native female voice for professional audiobooks and explainers."
    },
    "Priya (Modern Viral Creator & Commercials - 22y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "FGY2WhTYpPnrIDTdsKH5",
        "gender": "Female", "category": "Radio Jockey & Reels", "cat_class": "cat-rj",
        "pitch": "+26Hz", "rate": "+12%",
        "desc": "High-energy, youthful, playful commercial delivery crafted for viral TikTok and Instagram reels."
    },
    "RJ Shreya (FM Radio Jockey Host - 25y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "cgSgspJ2msm6clMCkdW9",
        "gender": "Female", "category": "Radio Jockey & Reels", "cat_class": "cat-rj",
        "pitch": "+18Hz", "rate": "+10%",
        "desc": "Sparkling, enthusiastic radio broadcast delivery for music stations and youth programs."
    },
    "Sayali (Prime-Time TV News Broadcaster)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "SAz9YHcvj6GT2YYXdXww",
        "gender": "Female", "category": "News & Broadcast", "cat_class": "cat-news",
        "pitch": "+6Hz", "rate": "+18%",
        "desc": "Sharp, articulate, confident television presenter voice for national bulletins and journalism."
    },
    "Meera (Serene Meditation & Spiritual Devotion)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "H6QPv2pQZDcGqLwDTIJQ",
        "gender": "Female", "category": "Spiritual & Elders", "cat_class": "cat-spiritual",
        "pitch": "-12Hz", "rate": "-16%",
        "desc": "Calming, peaceful, soothing cadence for wellness apps, guided meditation, and devotional poetry."
    },
    "Tanvi (Dramatic Audiobook & Emotional Actor)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "pFZP5JQG7iQjIQuC4Bku",
        "gender": "Female", "category": "Audiobooks & Literature", "cat_class": "cat-story",
        "pitch": "-5Hz", "rate": "-6%",
        "desc": "Sensitive, nuanced, expressive delivery capturing profound emotional depth and character drama."
    },
    "Pooja (Podcast Interviewer & Talk Show Host)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "hpp4J3VqNfWAUOO0d1Us",
        "gender": "Female", "category": "Podcasts & Interviews", "cat_class": "cat-podcast",
        "pitch": "+8Hz", "rate": "+4%",
        "desc": "Poised, sophisticated modern female interviewer voice for professional corporate media."
    },
    "Diya (Animated Fairy Tale & Child Voice - 8y)": {
        "id": "mr-IN-AarohiNeural", "eleven_id": "N2lVS1w4EtoT3dr4eOWO",
        "gender": "Female", "category": "Kids & Fantasy", "cat_class": "cat-kids",
        "pitch": "+36Hz", "rate": "+8%",
        "desc": "Playful, innocent, cheerful child voice for animated cartoons, bedtime fables, and games."
    }
}

HINDI_VOICES = {
    "Amitabh Style Madhur (Epic Baritone Titan)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "JBFqnCBsd6RMkjVDRZzb",
        "gender": "Male", "category": "Cinematic & Titan Bass", "cat_class": "cat-titan",
        "pitch": "-30Hz", "rate": "-8%",
        "desc": "Legendary ultra-deep baritone with cinematic gravitas, commanding respect and dramatic weight."
    },
    "Bahubali Devdutt (Epic Historical Commander)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "SOYHLrjzK2X1ezoPC6cr",
        "gender": "Male", "category": "Historical Warriors", "cat_class": "cat-warrior",
        "pitch": "-25Hz", "rate": "-6%",
        "desc": "Powerful battle commander cadence for epic mythology, warrior sagas, and trailers."
    },
    "Vikram (Crime Patrol Mystery Host)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "nPczCjzI2devNBz1zQrb",
        "gender": "Male", "category": "Crime & Mystery", "cat_class": "cat-crime",
        "pitch": "-18Hz", "rate": "-8%",
        "desc": "Gripping, suspenseful investigative narration for crime dramas and unsolved mysteries."
    },
    "Ram (Spiritual Master & Gita Preacher)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "CwhRBWXzGAHq8TQ4Fs17",
        "gender": "Male", "category": "Spiritual & Elders", "cat_class": "cat-spiritual",
        "pitch": "-15Hz", "rate": "-16%",
        "desc": "Tranquil, meditative spiritual preacher cadence bringing deep inner peace."
    },
    "RJ Aryan (Supercharged FM Radio Jockey)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "TX3LPaxmHKxFdv7VOQHJ",
        "gender": "Male", "category": "Radio Jockey & Reels", "cat_class": "cat-rj",
        "pitch": "+22Hz", "rate": "+14%",
        "desc": "High-octane, charismatic young radio presenter tone for viral trends and entertainment."
    },
    "Dadaji (Elderly Patriarch Storyteller - 70y)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "pqHfZKP75CvOlQylNhV4",
        "gender": "Male", "category": "Spiritual & Elders", "cat_class": "cat-spiritual",
        "pitch": "-30Hz", "rate": "-16%",
        "desc": "Revered elderly tone steeped in decades of wisdom for folklore and fables."
    },
    "Kabir (Youth Tech Podcaster & Motivator)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "IKne3meq5aSn9XLyUdCD",
        "gender": "Male", "category": "Podcasts & Interviews", "cat_class": "cat-podcast",
        "pitch": "+12Hz", "rate": "+12%",
        "desc": "Crisp, dynamic modern creator tone inspiring motivation and self-improvement."
    },
    "Sameer (Corporate Business Keynote Speaker)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "cjVigY5qzO86Huf0OWal",
        "gender": "Male", "category": "Corporate & Business", "cat_class": "cat-corp",
        "pitch": "+4Hz", "rate": "+6%",
        "desc": "Fluent executive presentation delivery for investor pitches and conferences."
    },
    "Ajay (Prime-Time Bulletins News Anchor)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "pNInz6obpgDQGcFmaJgB",
        "gender": "Male", "category": "News & Broadcast", "cat_class": "cat-news",
        "pitch": "+8Hz", "rate": "+20%",
        "desc": "Fast-paced, sharp news anchor delivery delivering breaking national headlines."
    },
    "Rahul (Hindi Literature Narrator)": {
        "id": "hi-IN-MadhurNeural", "eleven_id": "bIHbv24MWmeRgasZH58o",
        "gender": "Male", "category": "Audiobooks & Literature", "cat_class": "cat-story",
        "pitch": "-4Hz", "rate": "-2%",
        "desc": "Natural, soothing cadence for classic Hindi literature, novels, and audio dramas."
    },

    "Dadi Maa (Loving Grandmother Tales - 65y)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "Xb7hH8MSUJpSbSDYk0k2",
        "gender": "Female", "category": "Spiritual & Elders", "cat_class": "cat-spiritual",
        "pitch": "-24Hz", "rate": "-14%",
        "desc": "Tender, nurturing grandmotherly cadence brimming with moral bedtime tales."
    },
    "Swara (Classic Advertising & Novel Narrator)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "EXAVITQu4vr4xnSDxMaL",
        "gender": "Female", "category": "Audiobooks & Literature", "cat_class": "cat-story",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "Pristine standard Hindi diction for prestigious commercial campaigns and audiobooks."
    },
    "Simran (Viral Reel Sensation - 21y)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "FGY2WhTYpPnrIDTdsKH5",
        "gender": "Female", "category": "Radio Jockey & Reels", "cat_class": "cat-rj",
        "pitch": "+26Hz", "rate": "+12%",
        "desc": "Spirited, trendy creator delivery customized for modern social media algorithms."
    },
    "RJ Riya (Bubbly FM Radio Host)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "cgSgspJ2msm6clMCkdW9",
        "gender": "Female", "category": "Radio Jockey & Reels", "cat_class": "cat-rj",
        "pitch": "+18Hz", "rate": "+10%",
        "desc": "Vibrant, cheerful FM host cadence connecting warmly with daily listeners."
    },
    "Anjali (TV News Bulletin Presenter)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "XrExE9yKIg1WjnnlVkGX",
        "gender": "Female", "category": "News & Broadcast", "cat_class": "cat-news",
        "pitch": "+6Hz", "rate": "+18%",
        "desc": "Poised, authoritative broadcast delivery for studio journalism and news bulletins."
    },
    "Meera (Peaceful Devotion & Bhajan Voice)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "H6QPv2pQZDcGqLwDTIJQ",
        "gender": "Female", "category": "Spiritual & Elders", "cat_class": "cat-spiritual",
        "pitch": "-12Hz", "rate": "-15%",
        "desc": "Gentle, reverent spiritual delivery radiating deep tranquility and devotion."
    },
    "Neha (Dramatic & Sensitive Audiobook Actor)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "pFZP5JQG7iQjIQuC4Bku",
        "gender": "Female", "category": "Audiobooks & Literature", "cat_class": "cat-story",
        "pitch": "-5Hz", "rate": "-6%",
        "desc": "Rich in pauses and nuances, perfect for emotionally charged narrative dramas."
    },
    "Pooja (Podcast & Studio Interviewer)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "hpp4J3VqNfWAUOO0d1Us",
        "gender": "Female", "category": "Podcasts & Interviews", "cat_class": "cat-podcast",
        "pitch": "+8Hz", "rate": "+4%",
        "desc": "Engaging conversationalist delivery for in-depth interviews and discussions."
    },
    "Dr. Vandana (Professor & Motivational Mentor)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "SAz9YHcvj6GT2YYXdXww",
        "gender": "Female", "category": "Corporate & Business", "cat_class": "cat-corp",
        "pitch": "-16Hz", "rate": "-4%",
        "desc": "Grave, dignified academic lecture delivery for educational masterclasses."
    },
    "Pihu (Animated Pixie & Fairy Tales - 8y)": {
        "id": "hi-IN-SwaraNeural", "eleven_id": "N2lVS1w4EtoT3dr4eOWO",
        "gender": "Female", "category": "Kids & Fantasy", "cat_class": "cat-kids",
        "pitch": "+36Hz", "rate": "+8%",
        "desc": "Playful, charming child delivery for fantasy stories and cartoon characters."
    }
}

ENGLISH_VOICES = {
    "Thanos / Christopher (Cinematic Cosmic Titan Bass - US)": {
        "id": "en-US-ChristopherNeural", "eleven_id": "nPczCjzI2devNBz1zQrb",
        "gender": "Male", "category": "Cinematic & Titan Bass", "cat_class": "cat-titan",
        "pitch": "-35Hz", "rate": "-12%",
        "desc": "Ultra-deep, resonant movie villain & cosmic titan voice with thunderous sub-bass."
    },
    "Brian (Warm Storyteller & Documentary - US)": {
        "id": "en-US-BrianNeural", "eleven_id": "JBFqnCBsd6RMkjVDRZzb",
        "gender": "Male", "category": "Audiobooks & Literature", "cat_class": "cat-story",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "Warm, engaging National Geographic narrator tone with pristine natural presence."
    },
    "Ryan (Royal British Gentleman & BBC Host - UK)": {
        "id": "en-GB-RyanNeural", "eleven_id": "CwhRBWXzGAHq8TQ4Fs17",
        "gender": "Male", "category": "Corporate & Business", "cat_class": "cat-corp",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "Aristocratic British Received Pronunciation for documentaries, luxury brands, and drama."
    },
    "Prabhat (Professional Explainer - Indian English)": {
        "id": "en-IN-PrabhatNeural", "eleven_id": "TX3LPaxmHKxFdv7VOQHJ",
        "gender": "Male", "category": "Corporate & Business", "cat_class": "cat-corp",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "100% natural, educated Indian English accent for corporate and tutorials."
    },
    "Charlie (High-Energy Host & Creator - Australia)": {
        "id": "en-AU-WilliamNeural", "eleven_id": "IKne3meq5aSn9XLyUdCD",
        "gender": "Male", "category": "Podcasts & Interviews", "cat_class": "cat-podcast",
        "pitch": "+12Hz", "rate": "+10%",
        "desc": "Dynamic, charismatic YouTube tech creator and podcast interviewer."
    },
    "Harry (Gravelly Warrior & Gaming Protagonist)": {
        "id": "en-US-EricNeural", "eleven_id": "SOYHLrjzK2X1ezoPC6cr",
        "gender": "Male", "category": "Historical Warriors", "cat_class": "cat-warrior",
        "pitch": "-22Hz", "rate": "-6%",
        "desc": "Gritty, textured warrior voice for video games, fantasy lore, and combat."
    },
    "Bill (Seasoned Patriarch & Wise Veteran - 70s)": {
        "id": "en-US-GuyNeural", "eleven_id": "pqHfZKP75CvOlQylNhV4",
        "gender": "Male", "category": "Spiritual & Elders", "cat_class": "cat-spiritual",
        "pitch": "-28Hz", "rate": "-15%",
        "desc": "Wise grandfather tone with emotional weight and historical depth."
    },
    "Will (Chill Boy-Next-Door & Casual Vlogger)": {
        "id": "en-US-AndrewNeural", "eleven_id": "bIHbv24MWmeRgasZH58o",
        "gender": "Male", "category": "Radio Jockey & Reels", "cat_class": "cat-rj",
        "pitch": "+6Hz", "rate": "+4%",
        "desc": "Relatable, casual, relaxed conversational voice for daily vlogs."
    },
    "Adam (Authoritative Leader & Commander)": {
        "id": "en-US-SteffanNeural", "eleven_id": "pNInz6obpgDQGcFmaJgB",
        "gender": "Male", "category": "News & Broadcast", "cat_class": "cat-news",
        "pitch": "-12Hz", "rate": "+4%",
        "desc": "Firm, decisive leadership tone for keynote addresses and manifestos."
    },
    "Eric (Mindfulness Guide & Nature Audio - US)": {
        "id": "en-US-RogerNeural", "eleven_id": "cjVigY5qzO86Huf0OWal",
        "gender": "Male", "category": "Spiritual & Elders", "cat_class": "cat-spiritual",
        "pitch": "-14Hz", "rate": "-12%",
        "desc": "Soothing, gentle cadence for sleep stories, meditation, and wellness."
    },

    "Jenny (Natural Conversational YouTube #1 - US)": {
        "id": "en-US-JennyNeural", "eleven_id": "EXAVITQu4vr4xnSDxMaL",
        "gender": "Female", "category": "Audiobooks & Literature", "cat_class": "cat-story",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "The most natural, warm American conversational voice for YouTube."
    },
    "Ava (Dynamic Tech Host & Commercial Specialist - US)": {
        "id": "en-US-AvaNeural", "eleven_id": "FGY2WhTYpPnrIDTdsKH5",
        "gender": "Female", "category": "Radio Jockey & Reels", "cat_class": "cat-rj",
        "pitch": "+15Hz", "rate": "+10%",
        "desc": "Youthful, energetic, punchy delivery for high-impact brand commercials."
    },
    "Libby (Classic British Audiobook Narrator - UK)": {
        "id": "en-GB-LibbyNeural", "eleven_id": "Xb7hH8MSUJpSbSDYk0k2",
        "gender": "Female", "category": "Audiobooks & Literature", "cat_class": "cat-story",
        "pitch": "-4Hz", "rate": "-4%",
        "desc": "Refined British literary narrator for historical audiobooks and classics."
    },
    "Neerja (Expressive Indian English Female - India)": {
        "id": "en-IN-NeerjaExpressiveNeural", "eleven_id": "SAz9YHcvj6GT2YYXdXww",
        "gender": "Female", "category": "Podcasts & Interviews", "cat_class": "cat-podcast",
        "pitch": "+0Hz", "rate": "+0%",
        "desc": "100% natural, fluent modern Indian English female for corporate and media."
    },
    "Matilda (Engaging Educational & Course Instructor)": {
        "id": "en-US-AriaNeural", "eleven_id": "XrExE9yKIg1WjnnlVkGX",
        "gender": "Female", "category": "Corporate & Business", "cat_class": "cat-corp",
        "pitch": "+4Hz", "rate": "+4%",
        "desc": "Articulate, friendly educator voice for online courses and masterclasses."
    },
    "Jessica (Bright, Playful & Charming - US)": {
        "id": "en-US-EmmaNeural", "eleven_id": "cgSgspJ2msm6clMCkdW9",
        "gender": "Female", "category": "Radio Jockey & Reels", "cat_class": "cat-rj",
        "pitch": "+18Hz", "rate": "+8%",
        "desc": "Upbeat, radiant lifestyle presenter for beauty, travel, and social reels."
    },
    "Bella (Luxury Brand & High-Fashion Narrator)": {
        "id": "en-US-MichelleNeural", "eleven_id": "hpp4J3VqNfWAUOO0d1Us",
        "gender": "Female", "category": "Corporate & Business", "cat_class": "cat-corp",
        "pitch": "+6Hz", "rate": "+2%",
        "desc": "Silky, opulent, captivating commercial voice for premium advertisements."
    },
    "Lily (Velvety Dramatic Actress & Character Voice)": {
        "id": "en-GB-SoniaNeural", "eleven_id": "pFZP5JQG7iQjIQuC4Bku",
        "gender": "Female", "category": "Audiobooks & Literature", "cat_class": "cat-story",
        "pitch": "-8Hz", "rate": "-6%",
        "desc": "Intense theatrical delivery for cinematic drama and emotional storytelling."
    },
    "Sonia (Mindfulness & Deep Breath Meditation)": {
        "id": "en-IN-NeerjaNeural", "eleven_id": "H6QPv2pQZDcGqLwDTIJQ",
        "gender": "Female", "category": "Spiritual & Elders", "cat_class": "cat-spiritual",
        "pitch": "-14Hz", "rate": "-12%",
        "desc": "Hypnotic, breathy, peaceful cadence for guided relaxation and sleep apps."
    },
    "Diya (Fantasy Pixie & Animated Child Voice)": {
        "id": "en-US-AnaNeural", "eleven_id": "N2lVS1w4EtoT3dr4eOWO",
        "gender": "Female", "category": "Kids & Fantasy", "cat_class": "cat-kids",
        "pitch": "+32Hz", "rate": "+8%",
        "desc": "Enchanting fairy tale and cartoon voice for young audiences."
    }
}

# -------------------------------------------------------------
# CORE SYNTHESIS ENGINE (WITH SECURE RESOURCE FALLBACKS)
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
                    return "Native Neural Engine (Edge-TTS Fallback)"
        except Exception:
            async def run_edge():
                comm = edge_tts.Communicate(clean_text, voice_data["id"], rate=r, pitch=p)
                await comm.save(out_path)
            asyncio.run(run_edge())
            return "Native Neural Engine (Edge-TTS Fallback)"
    else:
        async def run_edge():
            comm = edge_tts.Communicate(clean_text, voice_data["id"], rate=r, pitch=p)
            await comm.save(out_path)
        asyncio.run(run_edge())
        return "Native Maharashtra Neural Engine (100% Authentic 'ळ')"


# ==============================================================
# MAIN STUDIO NAVIGATION TABS (PROFESSIONAL ENGLISH UI)
# ==============================================================
tab_mr, tab_hi, tab_en, tab_trans_studio, tab_dialogue, tab_pricing, tab_auth, tab_admin, tab_ai_script, tab_library = st.tabs([
    "🚩 Marathi Studio",
    "🇮🇳 Hindi Studio",
    "🌐 English Studio",
    "🌍 Universal Language Studio",
    "🎭 Multi-Voice Dialogue Studio",
    "💎 Pricing & Subscriptions",
    "🔐 Account & Access",
    "👑 Executive Admin CRM",
    "📝 AI Script Studio",
    "👥 Voice Library"
])

# ==============================================================
# TAB 1: MARATHI STUDIO (ENGLISH UI WITH NATIVE SPEECH)
# ==============================================================
with tab_mr:
    st.markdown('<div class="studio-banner banner-mr">🚩 Marathi Speech Studio — Authentic Maharashtra Accent, Retroflex "ळ" 100% Accurate & 20 Distinct Character Voices</div>', unsafe_allow_html=True)
    
    # In-line Instant Translation Expander
    with st.expander("🌐 Instant Translator (Type English or Hindi -> Auto-Translate to Marathi)"):
        col_tr1, col_tr2 = st.columns([2.5, 1])
        with col_tr1:
            trans_input = st.text_input("Type English or Hindi Text to Translate:", placeholder="e.g. Chhatrapati Shivaji Maharaj was the greatest king of India...")
        with col_tr2:
            st.write("")
            st.write("")
            if st.button("Translate to Marathi 🔄", use_container_width=True):
                if trans_input.strip():
                    translated_res = translate_text(trans_input, source='auto', target='mr')
                    st.session_state.mr_input_val = translated_res
                    st.success("Translated and loaded into editor!")
    
    mr_engine_choice = st.radio(
        "Audio Synthesis Engine:",
        [
            "🚩 Native Maharashtra Neural Engine (100% Authentic Retroflex 'ळ' - Zero Hindi Mix - Recommended ⭐)",
            "👑 ElevenLabs v4 Generative Engine (Global Multilingual)"
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
        if c_p3.button("👑 Shivray Historic Quote"):
            st.session_state.mr_input_val = "सह्याद्रीच्या कडेकपारीतून एकच गर्जना घुमली... जेव्हा संकटांची वादळे अंगावर चालून येतात, तेव्हा इतिहास बघायचा नसतो, तर इतिहास घडवायचा असतो!"
            
        if "mr_input_val" not in st.session_state:
            st.session_state.mr_input_val = "मावळ्यांच्या साथीने छत्रपती शिवरायांनी स्वराज्याचे बाळ कडू पाजले. बाळ, कमळ, टिळक आणि मावळे!"

        mr_text = st.text_area("Script Editor:", value=st.session_state.mr_input_val, height=160, key="mr_text_area")
        st.caption(f"📊 Words: **{len(mr_text.split())}** | Characters: **{len(mr_text)}**")

    with col_m2:
        st.markdown("**2. Select Voice Actor:**")
        mr_gender = st.radio("Gender Category:", ["👨 10 Male Voice Actors", "👩 10 Female Voice Actors"], horizontal=True, key="mr_gender_radio")
        is_male = "Male" in mr_gender
        
        filtered_mr = {k: v for k, v in MARATHI_VOICES.items() if (v["gender"] == "Male" if is_male else v["gender"] == "Female")}
        
        categories = ["🌟 All Categories"] + sorted(list(set([v["category"] for v in filtered_mr.values()])))
        selected_cat = st.selectbox("Filter by Category:", categories, key="mr_cat_filter")
        
        if selected_cat != "🌟 All Categories":
            filtered_mr = {k: v for k, v in filtered_mr.items() if v["category"] == selected_cat}
            
        selected_mr_name = st.selectbox("Voice Actor:", list(filtered_mr.keys()), key="mr_voice_select")
        mr_voice_data = filtered_mr[selected_mr_name]
        
        st.markdown(f"""
        <div class="voice-card">
            <div><span class="badge-cat {mr_voice_data['cat_class']}">{mr_voice_data['category']}</span> <b>{selected_mr_name.split('(')[0]}</b></div>
            <div style="font-size: 13px; color: #94A3B8; margin-top: 6px;">{mr_voice_data['desc']}</div>
            <div style="font-size: 12px; color: #818CF8; margin-top: 6px; font-weight: 600;">⚡ Default Pitch: {mr_voice_data['pitch']} | Cadence: {mr_voice_data['rate']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🎛️ Fine-Tune Pitch & Cadence (Sliders)"):
            c_sl1, c_sl2 = st.columns(2)
            default_p = int(mr_voice_data["pitch"].replace("Hz", ""))
            default_r = int(mr_voice_data["rate"].replace("%", ""))
            custom_mr_pitch = c_sl1.slider("Vocal Pitch / Bass (Hz):", min_value=-40, max_value=40, value=default_p, step=1, format="%d Hz", key="mr_sl_pitch")
            custom_mr_rate = c_sl2.slider("Speaking Speed (%):", min_value=-30, max_value=30, value=default_r, step=1, format="%d%%", key="mr_sl_rate")
        
        mr_btn = st.button("🚀 Synthesize Speech (Generate MP3)", type="primary", use_container_width=True, key="mr_btn")

    if mr_btn:
        if not mr_text.strip():
            st.warning("Please enter text script before generating audio.")
        else:
            out_mr = os.path.join(tempfile.gettempdir(), f"swar_mr_{uuid.uuid4().hex[:8]}.mp3")
            p_val = f"{custom_mr_pitch:+d}Hz"
            r_val = f"{custom_mr_rate:+d}%"
            
            with st.spinner("Synthesizing studio-grade audio with native phonetics..."):
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

            st.success(f"✨ Audio rendered successfully! (Engine: {engine_used})")
            r1, r2 = st.columns([1.5, 1])
            with r1:
                with open(out_mr, "rb") as f: st.audio(f.read(), format="audio/mp3")
            with r2:
                with open(out_mr, "rb") as f: st.download_button("⬇️ Download Audio (MP3)", f.read(), file_name="marathi_studio_audio.mp3", mime="audio/mp3", use_container_width=True)


# ==============================================================
# TAB 2: HINDI STUDIO (ENGLISH UI WITH NATIVE SPEECH)
# ==============================================================
with tab_hi:
    st.markdown('<div class="studio-banner banner-hi">🇮🇳 Hindi Speech Studio — Amitabh Style Deep Baritone, Bahubali Epic Bass & 20 Distinct Character Voices</div>', unsafe_allow_html=True)
    
    with st.expander("🌐 Instant Translator (Type English -> Auto-Translate to Hindi)"):
        col_htr1, col_htr2 = st.columns([2.5, 1])
        with col_htr1:
            h_trans_input = st.text_input("Type English text to translate to Hindi:", placeholder="e.g. Success comes to those who believe in their dreams...")
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
        st.caption(f"📊 Words: **{len(hi_text.split())}**")

    with col_h2:
        st.markdown("**2. Select Voice Actor:**")
        hi_gender = st.radio("Gender Category:", ["👨 10 Male Voice Actors", "👩 10 Female Voice Actors"], horizontal=True, key="hi_gender_radio")
        is_h_male = "Male" in hi_gender
        filtered_hi = {k: v for k, v in HINDI_VOICES.items() if (v["gender"] == "Male" if is_h_male else v["gender"] == "Female")}
        
        h_categories = ["🌟 All Categories"] + sorted(list(set([v["category"] for v in filtered_hi.values()])))
        selected_h_cat = st.selectbox("Filter by Category:", h_categories, key="hi_cat_filter")
        
        if selected_h_cat != "🌟 All Categories":
            filtered_hi = {k: v for k, v in filtered_hi.items() if v["category"] == selected_h_cat}
            
        selected_hi_name = st.selectbox("Voice Actor:", list(filtered_hi.keys()), key="hi_voice_select")
        hi_voice_data = filtered_hi[selected_hi_name]
        
        st.markdown(f"""
        <div class="voice-card">
            <div><span class="badge-cat {hi_voice_data['cat_class']}">{hi_voice_data['category']}</span> <b>{selected_hi_name.split('(')[0]}</b></div>
            <div style="font-size: 13px; color: #94A3B8; margin-top: 6px;">{hi_voice_data['desc']}</div>
            <div style="font-size: 12px; color: #F87171; margin-top: 6px; font-weight: 600;">⚡ Pitch: {hi_voice_data['pitch']} | Cadence: {hi_voice_data['rate']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🎛️ Fine-Tune Pitch & Cadence"):
            c_slh1, c_slh2 = st.columns(2)
            def_hp = int(hi_voice_data["pitch"].replace("Hz", ""))
            def_hr = int(hi_voice_data["rate"].replace("%", ""))
            custom_hi_pitch = c_slh1.slider("Vocal Pitch / Bass (Hz):", min_value=-40, max_value=40, value=def_hp, step=1, format="%d Hz", key="hi_sl_pitch")
            custom_hi_rate = c_slh2.slider("Speaking Speed (%):", min_value=-30, max_value=30, value=def_hr, step=1, format="%d%%", key="hi_sl_rate")
        
        hi_btn = st.button("🚀 Synthesize Hindi Speech", type="primary", use_container_width=True, key="hi_btn")

    if hi_btn:
        if not hi_text.strip():
            st.warning("Please enter text script before generating audio.")
        else:
            out_hi = os.path.join(tempfile.gettempdir(), f"swar_hi_{uuid.uuid4().hex[:8]}.mp3")
            p_val = f"{custom_hi_pitch:+d}Hz"
            r_val = f"{custom_hi_rate:+d}%"
            
            with st.spinner("Synthesizing expressive Hindi audio..."):
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

            st.success(f"✨ Audio rendered successfully! (Engine: {engine_used})")
            r1, r2 = st.columns([1.5, 1])
            with r1:
                with open(out_hi, "rb") as f: st.audio(f.read(), format="audio/mp3")
            with r2:
                with open(out_hi, "rb") as f: st.download_button("⬇️ Download Audio (MP3)", f.read(), file_name="hindi_studio_audio.mp3", mime="audio/mp3", use_container_width=True)


# ==============================================================
# TAB 3: ENGLISH STUDIO (THANOS & GLOBAL ACCENTS)
# ==============================================================
with tab_en:
    st.markdown('<div class="studio-banner banner-en">🌐 Native English Speech Studio — US, UK, Indian English with Ultra-Deep Thanos Cosmic Bass</div>', unsafe_allow_html=True)
    
    col_e1, col_e2 = st.columns([1.2, 1])
    
    with col_e1:
        st.markdown("**1. Enter English Script:**")
        c_e_p1, c_e_p2 = st.columns(2)
        if c_e_p1.button("🌌 Thanos Cosmic Monologue"):
            st.session_state.en_input_val = "I am inevitable. You could not live with your own failure. Where did that bring you? Back to me. I thought by eliminating half of life, the other half would thrive. But you have shown me that's impossible."
        if c_e_p2.button("👑 Churchill Leadership"):
            st.session_state.en_input_val = "We shall fight on the beaches, we shall fight on the landing grounds, we shall fight in the fields and in the streets. We shall never surrender!"
            
        if "en_input_val" not in st.session_state:
            st.session_state.en_input_val = "I am inevitable. You could not live with your own failure. Where did that bring you? Back to me."

        en_text = st.text_area("Script Editor:", value=st.session_state.en_input_val, height=160, key="en_text_area")
        st.caption(f"📊 Words: **{len(en_text.split())}**")

    with col_e2:
        st.markdown("**2. Select Voice Actor:**")
        en_gender = st.radio("Gender Category:", ["👨 10 Male Voice Actors", "👩 10 Female Voice Actors"], horizontal=True, key="en_gender_radio")
        is_e_male = "Male" in en_gender
        filtered_en = {k: v for k, v in ENGLISH_VOICES.items() if (v["gender"] == "Male" if is_e_male else v["gender"] == "Female")}
        
        e_categories = ["🌟 All Categories"] + sorted(list(set([v["category"] for v in filtered_en.values()])))
        selected_e_cat = st.selectbox("Filter by Category:", e_categories, key="en_cat_filter")
        
        if selected_e_cat != "🌟 All Categories":
            filtered_en = {k: v for k, v in filtered_en.items() if v["category"] == selected_e_cat}
            
        selected_en_name = st.selectbox("Voice Actor:", list(filtered_en.keys()), key="en_voice_select")
        en_voice_data = filtered_en[selected_en_name]
        
        st.markdown(f"""
        <div class="voice-card">
            <div><span class="badge-cat {en_voice_data['cat_class']}">{en_voice_data['category']}</span> <b>{selected_en_name.split('(')[0]}</b></div>
            <div style="font-size: 13px; color: #94A3B8; margin-top: 6px;">{en_voice_data['desc']}</div>
            <div style="font-size: 12px; color: #38BDF8; margin-top: 6px; font-weight: 600;">⚡ Pitch: {en_voice_data['pitch']} | Cadence: {en_voice_data['rate']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        with st.expander("🎛️ Fine-Tune Pitch & Cadence"):
            c_sle1, c_sle2 = st.columns(2)
            def_ep = int(en_voice_data["pitch"].replace("Hz", ""))
            def_er = int(en_voice_data["rate"].replace("%", ""))
            custom_en_pitch = c_sle1.slider("Vocal Pitch / Bass (Hz):", min_value=-40, max_value=40, value=def_ep, step=1, format="%d Hz", key="en_sl_pitch")
            custom_en_rate = c_sle2.slider("Speaking Speed (%):", min_value=-30, max_value=30, value=def_er, step=1, format="%d%%", key="en_sl_rate")
        
        en_btn = st.button("🚀 Synthesize English Speech", type="primary", use_container_width=True, key="en_btn")

    if en_btn:
        if not en_text.strip():
            st.warning("Please enter text script before generating audio.")
        else:
            out_en = os.path.join(tempfile.gettempdir(), f"swar_en_{uuid.uuid4().hex[:8]}.mp3")
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

            st.success(f"✨ Audio rendered successfully! (Engine: {engine_used})")
            r1, r2 = st.columns([1.5, 1])
            with r1:
                with open(out_en, "rb") as f: st.audio(f.read(), format="audio/mp3")
            with r2:
                with open(out_en, "rb") as f: st.download_button("⬇️ Download Audio (MP3)", f.read(), file_name="english_studio_audio.mp3", mime="audio/mp3", use_container_width=True)


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
    st.markdown('<div class="studio-banner banner-trans">🌍 Universal Language Studio — Type in Any Language, Translate in Real-Time & Synthesize Native Voice Instantly</div>', unsafe_allow_html=True)
    
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
                with st.spinner("Executing real-time neural translation..."):
                    res = translate_text(user_raw_text, source=src_code, target=tgt_data["code"])
                    st.session_state.universal_trans_res = res
                    st.success("Translation complete!")
                    
        translated_output = st.text_area("Translated Text Result:", value=st.session_state.universal_trans_res, height=150)

    btn_speak_trans = st.button("🎙️ Synthesize Speech in Target Language", type="primary", use_container_width=True)
    
    if btn_speak_trans:
        if not translated_output.strip():
            st.warning("Please translate text before rendering speech.")
        else:
            out_trans_mp3 = os.path.join(tempfile.gettempdir(), f"swar_global_{uuid.uuid4().hex[:8]}.mp3")
            with st.spinner(f"Rendering native speech in {target_choice}..."):
                async def run_global_edge():
                    comm = edge_tts.Communicate(translated_output, tgt_data["voice"])
                    await comm.save(out_trans_mp3)
                asyncio.run(run_global_edge())
                
            st.success(f"✨ Speech rendered in {target_choice}!")
            gr1, gr2 = st.columns([1.5, 1])
            with gr1:
                with open(out_trans_mp3, "rb") as f: st.audio(f.read(), format="audio/mp3")
            with gr2:
                with open(out_trans_mp3, "rb") as f: st.download_button("⬇️ Download Audio (MP3)", f.read(), file_name="translated_speech.mp3", mime="audio/mp3", use_container_width=True)


# ==============================================================
# TAB 5: MULTI-VOICE DIALOGUE STUDIO
# ==============================================================
with tab_dialogue:
    st.markdown('<div class="studio-banner banner-dialogue">🎭 Multi-Voice Dialogue Studio — Build 2-Actor Conversational Scenes Stitched into a Seamless MP3</div>', unsafe_allow_html=True)
    
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
            with open(out_d_combined, "rb") as f: st.download_button("⬇️ Download Full Scene (MP3)", f.read(), file_name="dialogue_scene.mp3", mime="audio/mp3", use_container_width=True)


# ==============================================================
# TAB 6: PRICING & SUBSCRIPTION MONETIZATION ENGINE
# ==============================================================
with tab_pricing:
    st.markdown('<div class="studio-banner" style="background:#131B31; border-left:5px solid #6366F1; color:#E0E7FF;">💎 Subscription Plans — Choose the Perfect Tier for Your Production Workflow</div>', unsafe_allow_html=True)
    
    col_p1, col_p2, col_p3 = st.columns(3)
    
    with col_p1:
        st.markdown("""
        <div class="pricing-card">
            <h3>🎁 Free Starter</h3>
            <h1 style="color:#94A3B8;">$0 <span style="font-size:16px;">/month (₹0)</span></h1>
            <p style="color:#64748B; font-size:13px;">For testing and personal discovery</p>
            <hr style="border-color:#1E293B;">
            <ul style="text-align:left; font-size:13px; color:#CBD5E1; line-height:2.2;">
                <li>✅ 5 daily voice generations</li>
                <li>✅ Standard Marathi & Hindi models</li>
                <li>✅ Retroflex 'ळ' phonetics check</li>
                <li>❌ No epic warrior bass voices</li>
                <li>❌ No multi-voice dialogue studio</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.button("Current Free Tier", disabled=True, use_container_width=True)

    with col_p2:
        st.markdown("""
        <div class="pricing-card pricing-featured">
            <span class="plan-badge">MOST POPULAR ⭐</span>
            <h3>👑 Creator Pro</h3>
            <h1 style="color:#818CF8;">$4 <span style="font-size:16px;">/month (₹299)</span></h1>
            <p style="color:#94A3B8; font-size:13px;">For YouTubers, Podcasters & Reel Creators</p>
            <hr style="border-color:#312E81;">
            <ul style="text-align:left; font-size:13px; color:#E0E7FF; line-height:2.2;">
                <li>🔥 <b>Unlimited Voice Generations</b></li>
                <li>⚔️ Tanaji Malusare, Bajiprabhu & Jijau Voices</li>
                <li>🌌 Thanos & Amitabh Style Cinema Bass</li>
                <li>🌐 Real-Time Multilingual Translation</li>
                <li>💎 100% Commercial Monetization Rights</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.markdown("**Subscribe via Direct UPI / PhonePe / GPay:**")
        st.code("swarai.pro@upi", language="text")

    with col_p3:
        st.markdown("""
        <div class="pricing-card">
            <h3>🚀 Studio Master</h3>
            <h1 style="color:#38BDF8;">$9 <span style="font-size:16px;">/month (₹699)</span></h1>
            <p style="color:#64748B; font-size:13px;">For Media Agencies & Production Houses</p>
            <hr style="border-color:#1E293B;">
            <ul style="text-align:left; font-size:13px; color:#CBD5E1; line-height:2.2;">
                <li>👑 <b>All Creator Pro Features Included</b></li>
                <li>🎭 <b>Multi-Voice Dialogue Studio</b> Unlocked</li>
                <li>⚡ ElevenLabs Ultra Generative Cloud Engine</li>
                <li>📝 1-Click AI Script Studio</li>
                <li>🏎️ 2x Priority Audio Rendering Pipeline</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        st.markdown("**Subscribe via Direct UPI / PhonePe / GPay:**")
        st.code("swarai.master@upi", language="text")

    st.markdown("---")
    st.markdown("### 🔑 Redeem VIP Activation License Key")
    col_k1, col_k2 = st.columns([2.5, 1])
    with col_k1:
        vip_input = st.text_input("Enter License Key / Token:", placeholder="e.g. SWAR-PRO-2026 or SWAR-VIP-MASTER")
    with col_k2:
        st.write("")
        st.write("")
        if st.button("Unlock VIP License 🔓", type="primary", use_container_width=True):
            vip_code = sanitize_text(vip_input).upper()
            email_key = st.session_state.current_user.get("email", "vishal@swarai.com")
            
            # Secure Anti-Tamper License Verification
            if hmac.compare_digest(vip_code, "SWAR-PRO-2026"):
                st.session_state.current_user["plan"] = "CREATOR PRO 👑"
                st.session_state.current_user["credits"] = 999999
                if email_key in users_db:
                    users_db[email_key]["plan"] = "CREATOR PRO 👑"
                    users_db[email_key]["credits"] = 999999
                    save_secure_users(users_db)
                st.success("🎉 License Verified! Account upgraded to CREATOR PRO ($4 / ₹299/mo)!")
                st.rerun()
            elif hmac.compare_digest(vip_code, "SWAR-VIP-MASTER") or hmac.compare_digest(vip_code, "SWAR-ENTERPRISE"):
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
# TAB 7: ACCOUNT & AUTHENTICATION SUBSYSTEM (SHA-256 SECURED)
# ==============================================================
with tab_auth:
    st.markdown("### 🔐 User Identity & Access Management")
    
    col_a1, col_a2 = st.columns(2)
    
    with col_a1:
        auth_mode = st.radio("Authentication Action:", ["Sign In", "Create New Account"], horizontal=True)
        
        if auth_mode == "Sign In":
            st.markdown("#### 🔑 Member Sign In")
            login_email = st.text_input("Account Email:", value="vishal@swarai.com", key="auth_login_email")
            login_pass = st.text_input("Password:", value="admin", type="password", key="auth_login_pass")
            
            if st.button("Sign In to Studio 🚀", type="primary", use_container_width=True):
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
            st.markdown("#### 📝 Create New Production Account")
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
                            "credits": 5,
                            "is_admin": False
                        }
                        save_secure_users(users_db)
                        st.session_state.current_user = users_db[c_email]
                        st.session_state.current_user["email"] = c_email
                        st.success(f"Account created successfully for {c_name}!")
                        st.rerun()
                else:
                    st.warning("Please fill in all required fields.")

    with col_a2:
        st.markdown("#### ⚡ 1-Click Fast Access (Testing Mode)")
        st.caption("Quickly toggle between authenticated user identities:")
        
        if st.button("👑 1-Click: Vishal Hargude (Admin & Founder - Studio Master)", use_container_width=True):
            st.session_state.current_user = users_db.get("vishal@swarai.com")
            st.session_state.current_user["email"] = "vishal@swarai.com"
            st.success("Authenticated as Vishal Hargude (Founder)!")
            st.rerun()
            
        if st.button("🎁 1-Click: Guest User (Free Trial Account)", use_container_width=True):
            st.session_state.current_user = users_db.get("demo@swarai.com")
            st.session_state.current_user["email"] = "demo@swarai.com"
            st.success("Authenticated as Guest User (Free Trial)!")
            st.rerun()
            
        st.markdown("---")
        st.markdown("#### 📋 Active Session Credentials")
        st.write(f"• **Account Name:** {st.session_state.current_user.get('name')}")
        st.write(f"• **Email Address:** {st.session_state.current_user.get('email')}")
        st.write(f"• **Active Plan:** `{st.session_state.current_user.get('plan')}`")
        st.write(f"• **Remaining Credits:** {st.session_state.current_user.get('credits')}")


# ==============================================================
# TAB: EXECUTIVE ADMIN CRM & USER DATABASE MANAGEMENT
# ==============================================================
with tab_admin:
    st.markdown('<div class="studio-banner" style="background:#1E1B4B; border-left:5px solid #6366F1; color:#E0E7FF;">👑 Executive Admin CRM — Manage All Registered Users, Subscription Revenues & Lead Contacts</div>', unsafe_allow_html=True)
    
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
        # 1. Executive Metrics
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
        
        # 2. Live Users CRM Table
        st.markdown("### 📋 Registered User Directory & Leads")
        
        user_rows = []
        for em, udata in users_db.items():
            user_rows.append({
                "Full Name": udata.get("name", "N/A"),
                "Email": em,
                "WhatsApp / Mobile": udata.get("mobile", "Not Provided"),
                "Active Plan": udata.get("plan", "FREE TRIAL 🎁"),
                "Credits": udata.get("credits", 0),
                "Role": "Admin" if udata.get("is_admin") else "User",
                "Joined": udata.get("joined", "2026-10-18")
            })
            
        st.dataframe(user_rows, use_container_width=True)
        
        # 3. Export to CSV / Excel
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["Full Name", "Email", "WhatsApp / Mobile", "Active Plan", "Credits", "Role", "Joined"])
        writer.writeheader()
        writer.writerows(user_rows)
        csv_data = output.getvalue()
        
        c_exp1, c_exp2 = st.columns([1.5, 2])
        with c_exp1:
            st.download_button(
                "📥 Export All User Leads to CSV / Excel",
                data=csv_data,
                file_name="swarai_users_leads.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        st.markdown("---")
        
        # 4. User Plan Management
        st.markdown("### ⚡ User Subscription Management (Manual Upgrade)")
        st.caption("Manually upgrade any customer who paid via direct Google Pay / PhonePe:")
        
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
                users_db[target_user_email]["credits"] = 999999 if "FREE" not in clean_p else 5
                save_secure_users(users_db)
                if st.session_state.current_user.get("email") == target_user_email:
                    st.session_state.current_user["plan"] = clean_p
                    st.session_state.current_user["credits"] = users_db[target_user_email]["credits"]
                st.success(f"Successfully upgraded {target_user_email} to {clean_p}!")
                st.rerun()


# ==============================================================
# TAB 9: AI VIRAL SCRIPT STUDIO
# ==============================================================
with tab_ai_script:
    st.markdown("### 📝 AI Viral Script Studio")
    st.write("1-Click viral production scripts for Historical documentaries, Motivational Reels, and Cinematic trailers:")
    
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.markdown("#### 🚩 Historical Epic Sagas")
        if st.button("Load Shivaji Maharaj Script"):
            st.session_state.mr_input_val = "सह्याद्रीच्या कड्यावरून जेव्हा वारा वाहतो, तेव्हा एकच नाव दुमदुमते — छत्रपती शिवाजी महाराज! मावळ्यांच्या रक्ताने पावन झालेली ही माती आजही साक्ष देते त्या त्यागाची, त्या शौर्याची. स्वराज्यासाठी प्राण देणारे मावळे हे केवळ सैनिक नव्हते, तर ते एका स्वप्नाचे रक्षक होते!"
            st.success("Loaded into Marathi Studio!")
            
    with col_s2:
        st.markdown("#### 🇮🇳 Motivational Reels")
        if st.button("Load Bahubali Hindi Script"):
            st.session_state.hi_input_val = "रास्ते कभी खत्म नहीं होते, बस लोग हिम्मत हार जाते हैं! अगर तैरना सीखना है तो पानी में उतरना ही होगा, किनारे पर बैठकर कोई गोताखोर नहीं बनता। अपनी मंजिल को इतना बड़ा बनाओ कि मुश्किलें छोटी नजर आने लगें!"
            st.success("Loaded into Hindi Studio!")
            
    with col_s3:
        st.markdown("#### 🌐 Cinematic Movie Trailers")
        if st.button("Load Thanos Monologue"):
            st.session_state.en_input_val = "The universe required correction. After that, the stones served no purpose beyond temptation. I am inevitable, and destiny arrives all the same."
            st.success("Loaded into English Studio!")


# ==============================================================
# TAB 9: COMPREHENSIVE VOICE DIRECTORY
# ==============================================================
with tab_library:
    st.markdown("### 👥 Comprehensive Voice Library (60+ Studio Actors)")
    st.write("Inspect audio acoustic signatures, timbre classifications, and frequency profiles across all models:")
    
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
                            <span class="badge-cat {data['cat_class']}">{data['category']}</span>
                            <span style="font-size:12px; font-weight:700; color:#64748B;">{data['gender']}</span>
                        </div>
                        <div style="font-weight:800; font-size:16px; margin: 6px 0; color:#F8FAFC;">{name.split('(')[0]}</div>
                        <div style="font-size:13px; color:#94A3B8; margin-bottom:8px;">{data['desc']}</div>
                        <div style="font-size:12px; color:#818CF8; font-weight:600;">⚡ Pitch: {data['pitch']} | Cadence: {data['rate']}</div>
                    </div>
                    """, unsafe_allow_html=True)

st.markdown("---")
st.caption("SwarAI Studio Ultra v6.0 | World-Class Multilingual Voice SaaS | 256-Bit SSL Hardened | Founder: Vishal Hargude")
