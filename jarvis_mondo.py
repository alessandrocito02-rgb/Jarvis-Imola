import os
import json
import feedparser
import requests
from google import genai
from google.genai import types
from gtts import gTTS

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC_MONDO") or os.environ.get("NTFY_TOPIC")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
VOICE_ID = "uI37iVjOs9xsSHtLUP5f"

client = genai.Client(api_key=GEMINI_API_KEY)

def genera_file_audio(testo, nome_file):
    """Genera un MP3 con la tua voce di ElevenLabs (o usa Google TTS di backup)"""
    if ELEVENLABS_API_KEY:
        url_eleven = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        headers_eleven = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }
        data_eleven = {
            "text": testo,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.65,
                "similarity_boost": 0.85,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }
        try:
            resp = requests.post(url_eleven, json=data_eleven, headers=headers_eleven, timeout=30)
            if resp.status_code == 200:
                with open(nome_file, "wb") as f:
                    f.write(resp.content)
                print(f"Audio ElevenLabs salvato: {nome_file}")
                return True
            else:
                print(f"Errore ElevenLabs ({resp.status_code}): passo al Piano B (gTTS)")
        except Exception as e:
            print(f"Eccezione ElevenLabs: {e}")

    # Piano B automatico se ElevenLabs fallisce o finisce i crediti
    try:
        tts = gTTS(text=testo, lang='it')
        tts.save(nome_file)
        print(f"Audio di backup gTTS salvato: {nome_file}")
        return True
    except Exception as e_gtts:
        print(f"Errore generazione audio: {e_gtts}")
        return False
        
def send_notification(messaggio):
    """Gestisce l'invio della notifica ntfy fuori dal main"""
    if not NTFY_TOPIC:
        print("ATTENZIONE: Nessun topic Ntfy configurato.")
        return

    dashboard_url = "https://alessandrocito02-rgb.github.io/Jarvis-Imola/"
    headers_ntfy = {
        "Title": "Jarvis - Rassegna Stampa",
        "Priority": "high",
        "Tags": "earth_americas,newspaper",
        "Click": dashboard_url,
        "Actions": f"view, Apri Jarvis, {dashboard_url}"
    }
    
    try:
        risp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC.strip()}", 
            data=messaggio.encode('utf-8'), 
            headers=headers_ntfy,
            timeout=10
        )
        print(f"Notifica Ntfy inviata [{risp.status_code}]")
    except Exception as e_ntfy:
        print(f"Errore Ntfy: {e_ntfy}")

def main():
    argomenti = {
        "⚽ Napoli Calcio": "https://news.google.com/rss/search?q=SSC+Napoli+calcio&hl=it&gl=IT&ceid=IT:it",
        "📰 Italia": "https://news.google.com/rss/search?q=Italia+cronaca+notizie+oggi&hl=it&gl=IT&ceid=IT:it",
        "📱 Tecnologia": "https://news.google.com/rss/search?q=Tecnologia+innovazione+smartphones&hl=it&gl=IT&ceid=IT:it",
        "🤖 Intelligenza Artificiale": "https://news.google.com/rss/search?q=Intelligenza+Artificiale+OpenAI+Google&hl=it&gl=IT&ceid=IT:it",
        "🚗 Auto & Motori": "https://news.google.com/rss/search?q=Auto+novita+mercato+Ferrari+BMW+Audi&hl=it&gl=IT&ceid=IT:it"
    }
    
    testo_notizie = ""
    headers_rss = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    print("1. Scaricamento notizie...")
    for categoria, url in argomenti.items():
        try:
            resp = requests.get(url, headers=headers_rss, timeout=10)
            feed = feedparser.parse(resp.content)
        except Exception as e:
            print(f"Errore download {categoria}: {e}")
            continue
            
        testo_temp = f"\n=== CATEGORIA: {categoria} ===\n"
        notizie_trovate = 0
        
        for entry in feed.entries[:10]:
            link = getattr(entry, 'link', '')
            titolo = getattr(entry, 'title', '')
            if not titolo or not link:
                continue
            if any(ban in titolo.lower() for ban in ["oroscopo", "lotto", "superenalotto", "meteo"]):
                continue

            testo_temp += f"- TITOLO: {titolo}\n  URL: {link}\n"
            notizie_trovate += 1
            if notizie_trovate >= 3:
                break
                
        if notizie_trovate > 0:
            testo_notizie += testo_temp

    if not testo_notizie:
        print("Nessuna notizia scaricata.")
        return

    prompt = f"""
    Sei J.A.R.V.I.S., l'assistente virtuale. Analizza queste notizie divise per categoria:
    {testo_notizie}
    
    ISTRUZIONI OBBLIGATORIE:
    1. Crea ESATTAMENTE 5 elementi nella lista "frasi_hud", uno per ciascuna categoria (Napoli Calcio, Italia, Tecnologia, Intelligenza Artificiale, Auto & Motori).
    2. In ogni blocco, unisci le notizie principali di quella categoria in un unico testo scorrevole ma BREVE (massimo 2 frasi corte per categoria, circa 25-30 parole).
    3. Rendilo un discorso continuo e collegato:
       - Nel primeiro blocco inizia salutando ("Buongiorno Signore. Per quanto riguarda il Napoli...")
       - Nei blocchi successivi usa transizioni naturali ("Passando alla cronaca in Italia...", "Sul fronte della tecnologia...", "Nel campo dell'intelligenza artificiale...", "Infine, per il settore auto e motori...").
    4. NON usare emoji, parentesi quadre o simboli dentro "testo". Scrivi solo parole pronunciabili.
    5. Nel campo "url" di ciascuno dei 5 blocchi, inserisci l'URL della notizia principale citata.
    
    Restituisci ESCLUSIVAMENTE un oggetto JSON valido con questa struttura:
    {{
      "testo_notifica": "Stringa sintetica divisa per categorie con emoji per la notifica del telefono.",
      "frasi_hud": [
        {{
          "testo": "Buongiorno Signore. Per quanto riguarda il Napoli...",
          "url": "https://..."
        }}
      ]
    }}
    """
    
    # Modelli corretti e funzionanti
    modelli = ["gemini-3.6-flash-lite", "gemini-3.5-flash"]
    dati = None
    for modello in modelli:
        try:
            response = client.models.generate_content(
                model=modello,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            testo_risposta = response.text.strip()
            if testo_risposta.startswith("```"):
                testo_risposta = testo_risposta.strip("`").replace("json\n", "", 1).strip()
            dati = json.loads(testo_risposta)
            if "frasi_hud" in dati and len(dati["frasi_hud"]) > 0:
                break
        except Exception as e:
            print(f"Errore modello {modello}: {e}")
            
    if not dati or "frasi_hud" not in dati:
        print("Impossibile generare il JSON.")
        return

    # 2. Genera i file audio MP3 dentro la cartella "audio"
    print("2. Generazione audio ElevenLabs per l'interfaccia web...")
    os.makedirs("audio", exist_ok=True)
    
    for i, item in enumerate(dati["frasi_hud"]):
        percorso_mp3 = f"audio/audio_{i}.mp3"
        genera_file_audio(item["testo"], percorso_mp3)
        item["audio"] = percorso_mp3

    # 3. Salva briefing.json
    with open("briefing.json", "w", encoding="utf-8") as f:
        json.dump(dati["frasi_hud"], f, ensure_ascii=False, indent=2)

    # 4. Prepara ed invia la notifica tramite la funzione esterna
    notifica_raw = dati.get("testo_notifica", "Nuovo briefing disponibile.")
    if isinstance(notifica_raw, list):
        messaggio = "\n".join(str(x) for x in notifica_raw)
    elif isinstance(notifica_raw, dict):
        messaggio = "\n".join(f"{k}: {v}" for k, v in notifica_raw.items())
    else:
        messaggio = str(notifica_raw)

    send_notification(messaggio)

if __name__ == "__main__":
    main()
