import os
import asyncio
import edge_tts
import hashlib

CACHE_DIR = os.path.join(os.path.dirname(__file__), "previews_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# 25 PERSONAS CONFIGURATION — STRICT GENDER FIDELITY
PERSONAS = [
    # 13 MALE (Range: -22Hz to +4Hz)
    {"id": "aarav", "name": "Aarav", "gender": "Male", "pitch": "-18Hz", "rate": "-6%"},
    {"id": "vikram", "name": "Vikram", "gender": "Male", "pitch": "-22Hz", "rate": "-10%"},
    {"id": "marcus", "name": "Marcus", "gender": "Male", "pitch": "+0Hz", "rate": "+4%"},
    {"id": "kabir", "name": "Kabir", "gender": "Male", "pitch": "-14Hz", "rate": "-6%"},
    {"id": "anup", "name": "Anup", "gender": "Male", "pitch": "-10Hz", "rate": "-8%"},
    {"id": "rohan", "name": "Rohan", "gender": "Male", "pitch": "+4Hz", "rate": "+14%"},
    {"id": "brian", "name": "Brian", "gender": "Male", "pitch": "-8Hz", "rate": "-6%"},
    {"id": "sagar", "name": "Sagar", "gender": "Male", "pitch": "+2Hz", "rate": "+10%"},
    {"id": "christopher", "name": "Christopher", "gender": "Male", "pitch": "-16Hz", "rate": "-8%"},
    {"id": "eshwar", "name": "Eshwar", "gender": "Male", "pitch": "-18Hz", "rate": "-12%"},
    {"id": "puck", "name": "Puck", "gender": "Male", "pitch": "+2Hz", "rate": "+4%"},
    {"id": "charon", "name": "Charon", "gender": "Male", "pitch": "-16Hz", "rate": "-8%"},
    {"id": "fenrir", "name": "Fenrir", "gender": "Male", "pitch": "-14Hz", "rate": "-4%"},

    # 12 FEMALE (Range: +0Hz to +10Hz, Never negative to prevent male distortion)
    {"id": "aarohi", "name": "Aarohi", "gender": "Female", "pitch": "+0Hz", "rate": "-4%"},
    {"id": "jenny", "name": "Jenny", "gender": "Female", "pitch": "+4Hz", "rate": "+10%"},
    {"id": "ananya", "name": "Ananya", "gender": "Female", "pitch": "+6Hz", "rate": "+14%"},
    {"id": "emma", "name": "Emma", "gender": "Female", "pitch": "+0Hz", "rate": "-4%"},
    {"id": "tara", "name": "Tara", "gender": "Female", "pitch": "+2Hz", "rate": "-8%"},
    {"id": "priya", "name": "Priya", "gender": "Female", "pitch": "+8Hz", "rate": "+12%"},
    {"id": "sonia", "name": "Sonia", "gender": "Female", "pitch": "+0Hz", "rate": "-6%"},
    {"id": "shreya", "name": "Shreya", "gender": "Female", "pitch": "+2Hz", "rate": "-4%"},
    {"id": "gauri", "name": "Gauri", "gender": "Female", "pitch": "+0Hz", "rate": "+0%"},
    {"id": "diya", "name": "Diya", "gender": "Female", "pitch": "+10Hz", "rate": "+8%"},
    {"id": "aoede", "name": "Aoede", "gender": "Female", "pitch": "+2Hz", "rate": "+4%"},
    {"id": "kore", "name": "Kore", "gender": "Female", "pitch": "+0Hz", "rate": "-6%"}
]

VOICE_CODES = {
    "Male": {
        "mr": "mr-IN-ManoharNeural",
        "hi": "hi-IN-MadhurNeural",
        "en": "en-US-ChristopherNeural"
    },
    "Female": {
        "mr": "mr-IN-AarohiNeural",
        "hi": "hi-IN-SwaraNeural",
        "en": "en-US-JennyNeural"
    }
}

SCRIPTS = {
    "Male": {
        "mr": "नमस्कार! मी {name}. हा माझा भारदस्त आवाज वाणी स्टुडिओमध्ये ऐका.",
        "hi": "नमस्ते! मैं {name} हूँ। वाणी स्टूडियो में मेरी दमदार आवाज़ सुनिए।",
        "en": "Hello! I am {name}. Experience my authentic male voice on Wani AI Studio."
    },
    "Female": {
        "mr": "नमस्कार! मी {name}. हा माझा मधुर आवाज वाणी स्टुडिओमध्ये ऐका.",
        "hi": "नमस्ते! मैं {name} हूँ। वाणी स्टूडियो में मेरी खूबसूरत आवाज़ सुनिए।",
        "en": "Hello! I am {name}. Experience my crystal clear voice on Wani AI Studio."
    }
}

async def generate_single(p, lang):
    out_file = os.path.join(CACHE_DIR, f"{p['id']}_{lang}.mp3")
    gender = p["gender"]
    voice_code = VOICE_CODES[gender][lang]
    text = SCRIPTS[gender][lang].format(name=p["name"])
    pitch = p["pitch"]
    rate = p["rate"]
    try:
        comm = edge_tts.Communicate(text, voice_code, pitch=pitch, rate=rate)
        await comm.save(out_file)
        print(f"Generated: {p['id']}_{lang}.mp3 ({gender} • {pitch})")
    except Exception as e:
        print(f"Failed {p['id']}_{lang}: {e}")

async def main():
    sem = asyncio.Semaphore(8)
    async def worker(p, lang):
        async with sem:
            await generate_single(p, lang)

    tasks = []
    for p in PERSONAS:
        for lang in ["mr", "hi", "en"]:
            tasks.append(worker(p, lang))
    await asyncio.gather(*tasks)
    print("Done generating all preview clips!")

    # Generate previews_base64.json
    import base64
    import json
    b64_map = {}
    for p in PERSONAS:
        pid = p["id"]
        b64_map[pid] = {}
        for lang in ["mr", "hi", "en"]:
            fpath = os.path.join(CACHE_DIR, f"{pid}_{lang}.mp3")
            if os.path.exists(fpath):
                with open(fpath, "rb") as af:
                    enc = base64.b64encode(af.read()).decode("utf-8")
                    b64_map[pid][lang] = f"data:audio/mp3;base64,{enc}"
    
    out_json = os.path.join(os.path.dirname(__file__), "previews_base64.json")
    with open(out_json, "w", encoding="utf-8") as jf:
        json.dump(b64_map, jf)
    print(f"Successfully exported {len(b64_map)} personas to {out_json} (size: {os.path.getsize(out_json)} bytes)!")

if __name__ == "__main__":
    asyncio.run(main())
