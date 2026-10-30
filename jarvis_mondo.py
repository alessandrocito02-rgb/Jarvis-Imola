import os
import json
import feedparser
import requests
import time
from datetime import datetime, timedelta, timezone
from google import genai
from google.genai import types
from gtts import gTTS

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC_MONDO")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

def send_jarvis_voice_ntfy(title, text_message, url=""):
    audio_filename = "jarvis_mondo_briefing.mp3"
    voice_id = "uI37iVjOs9xsSHtLUP5f"

    def usa_piano_b_gtts():
        print("Avvio Piano B: generazione voce con Google TTS...")
        try:
            tts = gTTS(text=text_message, lang='it')
            tts.save(audio_filename)
            
            headers_ntfy = {
                "Title": title.encode('utf-8'),
                "Priority": "default",
                "Tags": "earth_americas,newspaper",
                "Filename": "Jarvis_Mondo_Backup.mp3"
            }
            if url:
                headers_ntfy["Actions"] = f"view, Apri Dashboard, {url}"

            with open(audio_filename, "rb") as audio_file:
                requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=audio_file, headers=headers_ntfy)
        except Exception as e_gtts:
            print(f"Errore critico Piano B: {e_gtts}")

    if not ELEVENLABS_API_KEY:
        print("API Key ElevenLabs mancante.")
        usa_piano_b_gtts()
        return

    url_eleven = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers_eleven = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }
    data_eleven = {
        "text": text_message,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.65,
            "similarity_boost": 0.85,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }

    try:
        response = requests.post(url_eleven, json=data_eleven, headers=headers_eleven)
        if response.status_code == 200:
            with open(audio_filename, "wb") as f:
                f.write(response.content)
            
            headers_ntfy = {
                "Title": title.encode('utf-8'),
                "Priority": "default",
                "Tags": "earth_americas,newspaper",
                "Filename": "Jarvis_Mondo_Briefing.mp3"
            }
            if url:
                headers_ntfy["Actions"] = f"view, Apri Dashboard, {url}"

            with open(audio_filename, "rb") as audio_file:
                requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=audio_file, headers=headers_ntfy)
        else:
            print(f"Errore ElevenLabs: {response.status_code}")
            usa_piano_b_gtts()
    except Exception as e:
        print(f"Eccezione ElevenLabs: {e}")
        usa_piano_b_gtts()
    finally:
        if os.path.exists(audio_filename):
            os.remove(audio_filename)

def main():
    argomenti = {
        "⚽ Napoli Calcio": "https://news.google.com/rss/search?q=SSC+Napoli+calcio+ultime+notizie&hl=it&gl=IT&ceid=IT:it",
        "📰 Italia (Quotidianità)": "https://news.google.com/rss/search?q=Italia+cronaca+oggi+notizie+ultim'ora+quotidianità+proteste&hl=it&gl=IT&ceid=IT:it",
        "📱 Tecnologia": "https://news.google.com/rss/search?q=Tecnologia+innovazione+IT&hl=it&gl=IT&ceid=IT:it",
        "🤖 Intelligenza Artificiale": "https://news.google.com/rss/search?q=Intelligenza+Artificiale+AI+OpenAI+Google&hl=it&gl=IT&ceid=IT:it",
        "🚗 Auto & Motori": "https://news.google.com/rss/search?q=Auto+novità+mercato+BMW+Audi+Ferrari+ufficiale&hl=it&gl=IT&ceid=IT:it"
    }
    
    testo_notizie = ""
    # Filtro rigoroso: solo notizie delle ultime 24 ore
    time_limit = datetime.now(timezone.utc) - timedelta(days=1)
    
    for categoria, url in argomenti.items():
        feed = feedparser.parse(url)
        notizie_valide = 0
        testo_temp = f"\nCATEGORIA: {categoria}\n"
        
        for entry in feed.entries[:8]:
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                article_date = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
                if article_date < time_limit:
                    continue
            testo_temp += f"- {entry.title}\n"
            notizie_valide += 1
            if notizie_valide >= 4:
                break
                
        if notizie_valide > 0:
            testo_notizie += testo_temp
            
    prompt = f"""
    Sei Jarvis. Leggi i titoli delle notizie delle ultime 24 ore:
    {testo_notizie}
    
    Regola fondamentale: Usa ESATTAMENTE le stesse notizie per il testo scritto e per la voce. Non inventare o omettere discrepanze tra i due formati.
    
    Restituisci ESCLUSIVAMENTE un oggetto JSON con:
    1. "testo_notifica": Una stringa sintetica divisa per categorie (con emoji) da leggere a colpo d'occhio.
    2. "frasi_hud": Lista di stringhe con le identiche notizie, scritte in italiano naturale, fluido e formale per l'interfaccia web.
    3. "testo_vocale": Un'unica stringa che unisce le 'frasi_hud' in un discorso continuo, progettato per essere letto ad alta voce dalla tua sintesi vocale. Inizia con "Buongiorno signore, ecco la rassegna stampa."
    """
    
    try:
        print("Elaborazione dati e allineamento formati...")
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        dati = json.loads(response.text)
        
        # 1. Salva su GitHub per il sito web
        with open("briefing.json", "w", encoding="utf-8") as f:
            json.dump(dati["frasi_hud"], f, ensure_ascii=False, indent=2)
            
        # 2. Invia l'audio ElevenLabs tramite ntfy
        send_jarvis_voice_ntfy(
            title="Jarvis - Rassegna Stampa 🌍",
            text_message=dati["testo_vocale"],
            url="https://alessandrocito02-rgb.github.io/Jarvis-Imola/"
        )
        
        # 3. Invia il testo sintetico in un'altra notifica
        headers = {
            "Title": "Dettaglio Notizie 📰".encode('utf-8'),
            "Priority": "default"
        }
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=dati["testo_notifica"].encode('utf-8'), headers=headers)
        
        print("Ciclo completato con successo!")
        
    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    main()
