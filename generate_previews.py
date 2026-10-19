import os
import asyncio
import edge_tts
import imageio_ffmpeg
import subprocess
import base64
import json

CACHE_DIR = os.path.join(os.path.dirname(__file__), "previews_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()

# 25 PERSONAS CONFIGURATION — 100% DISTINCT VOICES & CHARACTER ACOUSTICS
PERSONAS = [
    # ==========================
    # 13 DISTINCT MALE PERSONAS
    # ==========================
    {
        "id": "aarav",
        "name": "Aarav",
        "gender": "Male",
        "pitch": "-18Hz",
        "rate": "-6%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "hi-IN-MadhurNeural",
            "en": "en-US-ChristopherNeural"
        },
        "scripts": {
            "mr": "नमस्कार! मी आरव. ऐतिहासिक पराक्रम आणि नेतृत्वाचा हा भारदस्त आवाज ऐका.",
            "hi": "प्रणाम! मैं आरव हूँ। ऐतिहासिक गरिमा और नेतृत्व की वाणी सुनिए।",
            "en": "Greetings. I am Aarav. Step into an era of historic authority and legendary voiceover."
        },
        "dsp": "bass=g=5:f=110"
    },
    {
        "id": "vikram",
        "name": "Vikram",
        "gender": "Male",
        "pitch": "-22Hz",
        "rate": "-10%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "hi-IN-MadhurNeural",
            "en": "en-US-EricNeural"
        },
        "scripts": {
            "mr": "चित्रपट सृष्टीत, मी विक्रम. हा थरारक सिनेमा ट्रेलर बास आवाज अनुभवा.",
            "hi": "सिनेमा की दुनिया में, मैं विक्रम हूँ। सब-वूफर ट्रेलर बास की शक्ति महसूस कीजिए।",
            "en": "In a world of sound, I am Vikram. Feel the ground-shaking cinema trailer bass."
        },
        "dsp": "bass=g=9:f=95,volume=1.2"
    },
    {
        "id": "marcus",
        "name": "Marcus",
        "gender": "Male",
        "pitch": "+0Hz",
        "rate": "+4%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "en-US-AndrewMultilingualNeural",
            "en": "en-US-GuyNeural"
        },
        "scripts": {
            "mr": "नमस्कार, मी मार्कस. कॉर्पोरेट आणि टेक सादरीकरणासाठी हा स्पष्ट आवाज ऐका.",
            "hi": "नमस्ते, मैं मार्कस हूँ। सिलिकॉन वैली के विज़नरी लीडर्स की स्पष्ट और मॉडर्न आवाज़।",
            "en": "Welcome. I am Marcus. Delivering high-impact keynote presentations for visionary founders."
        },
        "dsp": "treble=g=5:f=3500,highpass=f=100"
    },
    {
        "id": "kabir",
        "name": "Kabir",
        "gender": "Male",
        "pitch": "-14Hz",
        "rate": "-6%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "hi-IN-MadhurNeural",
            "en": "en-GB-RyanNeural"
        },
        "scripts": {
            "mr": "शौर्य आणि निष्ठा! मी कबीर, स्वाभिमान आणि दृढ निश्चयाचा हा घुमणारा आवाज.",
            "hi": "सत्य और शौर्य! मैं कबीर हूँ, राष्ट्रभक्ति और दृढ़ संकल्प की गूंजती आवाज़।",
            "en": "Honor and courage. I am Kabir, bringing resolute heritage and steadfast conviction."
        },
        "dsp": "aecho=0.8:0.7:30:0.25"
    },
    {
        "id": "anup",
        "name": "Anup",
        "gender": "Male",
        "pitch": "-10Hz",
        "rate": "-8%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "hi-IN-MadhurNeural",
            "en": "en-US-SteffanNeural"
        },
        "scripts": {
            "mr": "रहस्यांच्या गूढ जगात, मी अनुप. क्राईम आणि सस्पेंसचा हा थरारक आवाज ऐका.",
            "hi": "रहस्यों की गहराई में, मैं अनुप हूँ। सस्पेंस और थ्रिलर का रहस्यमयी स्वर।",
            "en": "The shadows conceal the truth. I am Anup, your guide into unsolved mysteries."
        },
        "dsp": "equalizer=f=300:width_type=h:width=200:g=4"
    },
    {
        "id": "rohan",
        "name": "Rohan",
        "gender": "Male",
        "pitch": "+4Hz",
        "rate": "+14%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "hi-IN-MadhurNeural",
            "en": "en-US-RogerNeural"
        },
        "scripts": {
            "mr": "या क्षणाची सर्वात मोठी बातमी! मी रोहन, थेट न्यूज डेस्कवरून वेगवान घडामोडी.",
            "hi": "ताज़ा बड़ी खबर इस वक्त! मैं रोहन हूँ, न्यूज़ डेस्क से लाइव और सबसे तेज़।",
            "en": "Breaking news right now. I am Rohan, delivering urgent headlines from the news desk."
        },
        "dsp": "volume=1.2,treble=g=4:f=3500"
    },
    {
        "id": "brian",
        "name": "Brian",
        "gender": "Male",
        "pitch": "-8Hz",
        "rate": "-6%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "hi-IN-MadhurNeural",
            "en": "en-GB-ThomasNeural"
        },
        "scripts": {
            "mr": "निसर्ग आणि इतिहासाच्या सफरीवर, मी ब्रायन, बीबीसी प्रतिष्ठित माहितीपटांचा अनुभव.",
            "hi": "प्रकृति और इतिहास के पन्नों पर, मैं ब्रायन हूँ, बीबीसी डॉक्यूमेंट्री का परिपक्व स्वर।",
            "en": "Across the vast landscapes of Earth. I am Brian, narrator of prestigious global documentaries."
        },
        "dsp": "equalizer=f=150:width_type=h:width=100:g=3"
    },
    {
        "id": "sagar",
        "name": "Sagar",
        "gender": "Male",
        "pitch": "+2Hz",
        "rate": "+10%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "hi-IN-MadhurNeural",
            "en": "en-IN-PrabhatNeural"
        },
        "scripts": {
            "mr": "नमस्कार लिसनर्स! आरजे सागर तुमच्या सोबतीला, भन्नाट एनर्जी आणि गाण्यांची मैफल घेऊन!",
            "hi": "हेलो लिसनर्स! आरजे सागर आपके साथ, सुपर एनर्जेटिक म्यूज़िक और गपशप लेकर!",
            "en": "What's up listeners! RJ Sagar here, bringing super energetic vibes to your radio dial!"
        },
        "dsp": "treble=g=5:f=3000,volume=1.15"
    },
    {
        "id": "christopher",
        "name": "Christopher",
        "gender": "Male",
        "pitch": "-16Hz",
        "rate": "-8%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "hi-IN-MadhurNeural",
            "en": "en-US-ChristopherNeural"
        },
        "scripts": {
            "mr": "प्रत्येक कथेची एक भव्य सुरुवात असते. मी ख्रिस्तोफर, तुमचा सिनेमॅटिक कथाकार.",
            "hi": "हर गाथा की एक शुरुआत होती है। मैं क्रिस्टोफर हूँ, आपका सिनेमाई कथाकार।",
            "en": "Every legend has a beginning. I am Christopher, your deep cinematic narrator."
        },
        "dsp": "bass=g=6:f=90"
    },
    {
        "id": "eshwar",
        "name": "Eshwar",
        "gender": "Male",
        "pitch": "-18Hz",
        "rate": "-12%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "hi-IN-MadhurNeural",
            "en": "en-US-BrianNeural"
        },
        "scripts": {
            "mr": "शांत चित्ताने ऐका मुलांनो. मी ईश्वर, पूर्वजांचे अनुभव आणि संस्कारांची ही जुनी वाणी.",
            "hi": "ध्यान से सुनो बच्चों। मैं ईश्वर हूँ, बुजुर्गों के अनुभवों और लोककथाओं की वाणी।",
            "en": "Listen closely, my children. I am Eshwar, sharing lifelong wisdom from the ancestors."
        },
        "dsp": "asetrate=24000*0.93,atempo=1/0.93"
    },
    {
        "id": "puck",
        "name": "Puck",
        "gender": "Male",
        "pitch": "+2Hz",
        "rate": "+4%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "en-US-AndrewMultilingualNeural",
            "en": "en-US-AndrewMultilingualNeural"
        },
        "scripts": {
            "mr": "नमस्कार! मी पक, गुगल एआय स्टुडिओ जेमिनी 2.0 चा हा आधुनिक आणि संभाषणात्मक आवाज.",
            "hi": "नमस्ते! मैं पक हूँ, गूगल एआई स्टूडियो जेमिनी 2.0 की मॉडर्न और दोस्ताना आवाज़।",
            "en": "Hey there! I am Puck, powered by Google AI Studio Gemini 2.0 with dynamic conversational flow."
        },
        "dsp": "treble=g=3:f=3200"
    },
    {
        "id": "charon",
        "name": "Charon",
        "gender": "Male",
        "pitch": "-16Hz",
        "rate": "-8%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "en-US-BrianMultilingualNeural",
            "en": "en-US-BrianMultilingualNeural"
        },
        "scripts": {
            "mr": "गूढ शांततेतून उमटलेला हा आवाज. मी कॅरॉन, गुगल एआय स्टुडिओचा अति-गंभीर बास.",
            "hi": "गहराइयों से उठता स्वर। मैं शैरॉन हूँ, गूगल एआई स्टूडियो का गहन गंभीर बास।",
            "en": "From the quiet depths. I am Charon, Google AI Studio's deep resonant bass architecture."
        },
        "dsp": "bass=g=7:f=110"
    },
    {
        "id": "fenrir",
        "name": "Fenrir",
        "gender": "Male",
        "pitch": "-14Hz",
        "rate": "-4%",
        "voices": {
            "mr": "mr-IN-ManoharNeural",
            "hi": "hi-IN-MadhurNeural",
            "en": "en-AU-WilliamMultilingualNeural"
        },
        "scripts": {
            "mr": "हिंमत आणि पराक्रम! मी फेनरिर, गुगल एआय स्टुडिओचा बुलंद आणि निर्भीड आवाज.",
            "hi": "साहस और पराक्रम! मैं फेनरिर हूँ, गूगल एआई स्टूडियो का निर्भीक और बुलंद स्वर।",
            "en": "Stand tall. I am Fenrir, the commanding titan voice of Google AI Studio."
        },
        "dsp": "volume=1.2,bass=g=4:f=140"
    },

    # ============================
    # 12 DISTINCT FEMALE PERSONAS
    # ============================
    {
        "id": "aarohi",
        "name": "Aarohi",
        "gender": "Female",
        "pitch": "+0Hz",
        "rate": "-4%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "hi-IN-SwaraNeural",
            "en": "en-IN-NeerjaExpressiveNeural"
        },
        "scripts": {
            "mr": "सन्मान आणि राजेशाही वैभव! मी आरोही, राजघराण्यातील स्वाभिमानी आणि प्रेमळ आवाज.",
            "hi": "सम्मान और राजसी वैभव! मैं आरोही हूँ, राजघराने और मातृत्व का गरिमामयी स्वर।",
            "en": "Grace and noble majesty. I am Aarohi, voice of royal dignity and maternal strength."
        },
        "dsp": "equalizer=f=2500:width_type=h:width=1000:g=2"
    },
    {
        "id": "jenny",
        "name": "Jenny",
        "gender": "Female",
        "pitch": "+4Hz",
        "rate": "+10%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "hi-IN-SwaraNeural",
            "en": "en-US-JennyNeural"
        },
        "scripts": {
            "mr": "ग्लोबल मार्केट्सचे थेट अपडेट्स! मी जेनी, अचूक वित्तीय आणि कॉर्पोरेट विश्लेषण.",
            "hi": "ग्लोबल मार्केट्स लाइव! मैं जेनी हूँ, वित्तीय विश्लेषकों के लिए सटीक कॉर्पोरेट रिपोर्टिंग।",
            "en": "Markets at the bell. I am Jenny, delivering executive financial news and global analysis."
        },
        "dsp": "treble=g=4:f=3500"
    },
    {
        "id": "ananya",
        "name": "Ananya",
        "gender": "Female",
        "pitch": "+6Hz",
        "rate": "+14%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "hi-IN-SwaraNeural",
            "en": "en-US-AvaNeural"
        },
        "scripts": {
            "mr": "आजच्या ठळक बातम्या! मी अनन्या, प्राईम टाईम बुलेटिनचा थेट आणि वेगवान आवाज.",
            "hi": "आज की सबसे बड़ी सुर्खियां! मैं अनन्या हूँ, प्राइम टाइम बुलेटिन की तेज़ और बेबाक आवाज़।",
            "en": "Top stories headlines. I am Ananya, bringing fast, fearless prime-time reporting."
        },
        "dsp": "volume=1.2,treble=g=4:f=3500"
    },
    {
        "id": "emma",
        "name": "Emma",
        "gender": "Female",
        "pitch": "+0Hz",
        "rate": "-4%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "hi-IN-SwaraNeural",
            "en": "en-GB-SoniaNeural"
        },
        "scripts": {
            "mr": "नाट्य आणि साहित्याच्या भव्य मंचावर! मी एम्मा, अभिजात काव्याचा भावस्पर्शी सूर.",
            "hi": "रंगमंच की पावन भूमि पर। मैं एम्मा हूँ, क्लासिकल साहित्य और नाटकों की भावपूर्ण आवाज़।",
            "en": "Upon this grand stage. I am Emma, bringing classical poetry and theatrical literature to life."
        },
        "dsp": "aecho=0.7:0.6:25:0.15"
    },
    {
        "id": "tara",
        "name": "Tara",
        "gender": "Female",
        "pitch": "+2Hz",
        "rate": "-8%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "hi-IN-SwaraNeural",
            "en": "en-IN-NeerjaNeural"
        },
        "scripts": {
            "mr": "शांत व्हा आणि दीर्घ श्वास घ्या. मी तारा, ध्यानधारणा आणि मनःशांतीचा कोमल सूर.",
            "hi": "गहरी सांस लें और शांत हो जाएं। मैं तारा हूँ, माइंडफुलनेस और ध्यान की कोमल ध्वनि।",
            "en": "Inhale peace, exhale tension. I am Tara, your gentle guide to mindfulness and calm."
        },
        "dsp": "lowpass=f=2800,volume=0.9"
    },
    {
        "id": "priya",
        "name": "Priya",
        "gender": "Female",
        "pitch": "+8Hz",
        "rate": "+12%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "en-US-AvaMultilingualNeural",
            "en": "en-US-AriaNeural"
        },
        "scripts": {
            "mr": "हाय फ्रेंड्स! मी प्रिया, सोशल मीडिया रील्स आणि पॉडकास्टसाठी सुपर एनर्जेटिक आवाज!",
            "hi": "हेलो फ्रेंड्स! मैं प्रिया हूँ, आपकी रील्स और पॉडकास्ट के लिए सुपर ट्रेंडी और चुलबुली आवाज़!",
            "en": "Hey besties! Priya here, bringing viral energy, trends, and lifestyle vibes to your feed!"
        },
        "dsp": "treble=g=5:f=4000,volume=1.15"
    },
    {
        "id": "sonia",
        "name": "Sonia",
        "gender": "Female",
        "pitch": "+0Hz",
        "rate": "-6%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "hi-IN-SwaraNeural",
            "en": "en-IN-NeerjaNeural"
        },
        "scripts": {
            "mr": "डोळे मिटा आणि विश्रांती घ्या. मी सोनिया, शांत झोपेसाठी अंगाईसारखा प्रेमळ आवाज.",
            "hi": "आँखें बंद कीजिए और विश्राम पाइए। मैं सोनिया हूँ, सुकून भरी नींद के लिए एक मीठी लोरी।",
            "en": "Close your eyes and drift away. I am Sonia, whispering bedtime stories for restful sleep."
        },
        "dsp": "equalizer=f=1200:width_type=h:width=600:g=-2,volume=0.92"
    },
    {
        "id": "shreya",
        "name": "Shreya",
        "gender": "Female",
        "pitch": "+2Hz",
        "rate": "-4%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "hi-IN-SwaraNeural",
            "en": "en-GB-MaisieNeural"
        },
        "scripts": {
            "mr": "जवळ या, एक छान गोष्ट सांगते. मी श्रेया, आजीच्या बटव्यातील गोड गोष्टींचा आवाज.",
            "hi": "आइए पास बैठिए। मैं श्रेया हूँ, पीढ़ियों से चली आ रही दादी-नानी की सुंदर कहानियों की आवाज़।",
            "en": "Gather around the warm hearth. I am Shreya, sharing timeless folklore and wisdom."
        },
        "dsp": "equalizer=f=800:width_type=h:width=400:g=2"
    },
    {
        "id": "gauri",
        "name": "Gauri",
        "gender": "Female",
        "pitch": "+0Hz",
        "rate": "+0%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "hi-IN-SwaraNeural",
            "en": "en-US-MichelleNeural"
        },
        "scripts": {
            "mr": "सह्याद्रीच्या डोंगररांगा आणि निसर्गाचे सौंदर्य. मी गौरी, माहितीपट आणि ट्रॅव्हल गाइडचा आवाज.",
            "hi": "जंगलों और पहाड़ों की असीम सुंदरता। मैं गौरी हूँ, वन्यजीव और यात्रा वृत्तचित्रों का स्वर।",
            "en": "Beneath the pristine canopy of the wild. I am Gauri, your travelogue and nature guide."
        },
        "dsp": "treble=g=3:f=3000"
    },
    {
        "id": "diya",
        "name": "Diya",
        "gender": "Female",
        "pitch": "+10Hz",
        "rate": "+8%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "hi-IN-SwaraNeural",
            "en": "en-US-AnaNeural"
        },
        "scripts": {
            "mr": "चला मित्रांनो! जादूच्या दुनियेत जाऊया! मी दिया, लहान मुलांची लाडकी परी!",
            "hi": "अरे वाह! चलो जादुई दुनिया में चलते हैं! मैं दीया हूँ, कार्टून और बच्चों की प्यारी सहेली!",
            "en": "Yay! Let's go on a magic adventure! I am Diya, the cheerful cartoon fairy!"
        },
        "dsp": "asetrate=24000*1.08,atempo=1/1.08"
    },
    {
        "id": "aoede",
        "name": "Aoede",
        "gender": "Female",
        "pitch": "+2Hz",
        "rate": "+4%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "en-US-AvaMultilingualNeural",
            "en": "en-US-AvaMultilingualNeural"
        },
        "scripts": {
            "mr": "अभिजात सौंदर्य आणि गोडवा. मी ऑइडी, गुगल एआय स्टुडिओ जेमिनी 2.0 चा लक्झरी आवाज.",
            "hi": "अभिजात्य सौंदर्य और लालित्य। मैं आयोइडी हूँ, गूगल एआई स्टूडियो जेमिनी 2.0 का लग्जरी स्वर।",
            "en": "Pure elegance redefined. I am Aoede, Google AI Studio Gemini 2.0 luxury narration."
        },
        "dsp": "treble=g=4:f=3200"
    },
    {
        "id": "kore",
        "name": "Kore",
        "gender": "Female",
        "pitch": "+0Hz",
        "rate": "-6%",
        "voices": {
            "mr": "mr-IN-AarohiNeural",
            "hi": "en-US-AvaMultilingualNeural",
            "en": "en-US-MichelleNeural"
        },
        "scripts": {
            "mr": "मनाला शांत करणारा हा अनुभव. मी कोरे, गुगल एआय स्टुडिओचा ध्यानमग्न आणि शीतल सूर.",
            "hi": "शांति का गहरा अनुभव। मैं कोरे हूँ, गूगल एआई स्टूडियो का शांत और ध्यानी स्वर।",
            "en": "Find your still center. I am Kore, Google AI Studio's meditative acoustic guide."
        },
        "dsp": "lowpass=f=3200"
    }
]

async def generate_single(p, lang):
    out_file = os.path.join(CACHE_DIR, f"{p['id']}_{lang}.mp3")
    tmp_file = os.path.join(CACHE_DIR, f"tmp_{p['id']}_{lang}.mp3")
    gender = p["gender"]
    voice_code = p["voices"][lang]
    text = p["scripts"][lang]
    pitch = p["pitch"]
    rate = p["rate"]
    dsp = p.get("dsp")
    
    try:
        comm = edge_tts.Communicate(text, voice_code, pitch=pitch, rate=rate)
        await comm.save(tmp_file)
        
        cmd = [
            FFMPEG_BIN, "-y", "-i", tmp_file
        ]
        if dsp:
            cmd.extend(["-af", dsp])
        cmd.extend(["-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k", out_file])
        
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass
        print(f"Generated: {p['id']}_{lang}.mp3 ({gender} • {voice_code} • {pitch})")
    except Exception as e:
        print(f"Failed {p['id']}_{lang}: {e}")

async def main():
    sem = asyncio.Semaphore(6)
    async def worker(p, lang):
        async with sem:
            await generate_single(p, lang)

    tasks = []
    for p in PERSONAS:
        for lang in ["mr", "hi", "en"]:
            tasks.append(worker(p, lang))
    await asyncio.gather(*tasks)
    print("Done generating all distinct persona preview clips!")

    # Export base64 json
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
