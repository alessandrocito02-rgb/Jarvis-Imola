import json
import os
import feedparser
import requests
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
SEEN_FILE = "seen_articles.json"

RSS_URLS = [
    "https://news.google.com/rss/search?q=Formula+1+Imola+biglietti&hl=it&gl=IT&ceid=IT:it",
    "https://news.google.com/rss/search?q=GP+Imola+F1+conferma+calendario&hl=it&gl=IT&ceid=IT:it",
    "https://news.google.com/rss/search?q=TicketOne+Formula+1+Imola&hl=it&gl=IT&ceid=IT:it",
    # --- NUOVE RICERCHE ---
    "https://news.google.com/rss/search?q=Autodromo+Imola+Formula+1&hl=it&gl=IT&ceid=IT:it",
    "https://news.google.com/rss/search?q=F1+Imola+Domenicali+ACI&hl=it&gl=IT&ceid=IT:it",
    "https://news.google.com/rss/search?q=rinnovo+contratto+Imola+F1&hl=it&gl=IT&ceid=IT:it"
]

client = genai.Client(api_key=GEMINI_API_KEY)

def load_state():
    """Carica lo stato salvato (articoli visti, data ultimo report e diario giornaliero)"""
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {"seen": set(data), "last_daily_report": "", "daily_log": []}
                return {
                    "seen": set(data.get("seen", [])),
                    "last_daily_report": data.get("last_daily_report", ""),
                    "daily_log": data.get("daily_log", []) # NUOVO: carica il diario
                }
        except Exception as e:
            print(f"Errore lettura file memoria: {e}")
    return {"seen": set(), "last_daily_report": "", "daily_log": []}

def save_state(state):
    """Salva lo stato aggiornato"""
    with open(SEEN_FILE, "w") as f:
        json.dump({
            "seen": list(state["seen"]),
            "last_daily_report": state["last_daily_report"],
            "daily_log": state.get("daily_log", []) # NUOVO: salva il diario
        }, f, indent=2)

def send_notification(title, message, url=""):
    headers = {
        "Title": title.encode('utf-8'),
        "Priority": "high",
        "Tags": "racing_car,ticket"
    }
    if url:
        # Usa 'Actions' invece di 'Click' per creare un bottone separato
        headers_ntfy["Actions"] = f"view, Apri Link, {url}"
    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=message.encode('utf-8'), headers=headers)

def send_jarvis_voice_ntfy(title, text_message, url=""):
    audio_filename = "jarvis_briefing.mp3"
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    
    # INCOLLA QUI IL VOICE ID DI ELEVENLABS
    voice_id = "IL_TUO_VOICE_ID_QUI" 
    
    if not api_key:
        print("Errore: ELEVENLABS_API_KEY non trovata. Invio solo testo.")
        send_notification(title, text_message, url)
        return

    url_eleven = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers_eleven = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
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
                "Priority": "high",
                "Tags": "robot,racing_car",
                "Filename": "Jarvis_Briefing.mp3"
            }
            
            if url:
                # Crea un comodo pulsante separato al posto di far cliccare l'intera notifica
                headers_ntfy["Actions"] = f"view, Apri Link, {url}"

            with open(audio_filename, "rb") as audio_file:
                requests.post(
                    f"https://ntfy.sh/{NTFY_TOPIC}",
                    data=audio_file,
                    headers=headers_ntfy
                )
            print("Briefing vocale stile Jarvis inviato con successo via ElevenLabs!")
            
        else:
            print(f"Errore API ElevenLabs ({response.status_code}): {response.text}")
            # Fallback sicuro: se l'API vocale fallisce, ti manda la notifica testuale
            send_notification(title, text_message, url)
            
    except Exception as e:
        print(f"Errore durante la generazione dell'audio: {e}")
        send_notification(title, text_message, url)
        
    finally:
        if os.path.exists(audio_filename):
            os.remove(audio_filename)


def analyze_with_jarvis(title, summary):
    prompt = f"""
    Sei Jarvis, un assistente che monitora il Gran Premio di Formula 1 di Imola.
    Analizza questa notizia:
    Titolo: {title}
    Dettagli: {summary}

    Avvisami (notify = true) SE la notizia riguarda uno di questi temi:
    1. Vendite o prevendite di biglietti (Urgenza: ALTA)
    2. Conferma, annullamento o rinnovo del contratto per il GP a Imola (Urgenza: ALTA)
    3. Dichiarazioni di ACI, Stefano Domenicali o politici locali sul futuro del GP (Urgenza: MEDIA)
    4. Lavori di ammodernamento all'Autodromo Enzo e Dino Ferrari (Urgenza: MEDIA)

    Rispondi ESCLUSIVAMENTE in JSON:
    {{
        "notify": true/false,
        "urgency": "ALTA" o "MEDIA",
        "short_message": "Riassunto chiaro in italiano (max 2 righe)"
    }}
    """
    
    modelli_da_provare = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]
    
    for nome_modello in modelli_da_provare:
        try:
            response = client.models.generate_content(
                model=nome_modello,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Modello {nome_modello} irraggiungibile ({e}), passo al successivo...")
            time.sleep(1)
            
    print("Tutti i modelli sono attualmente sovraccarichi.")
    return {"notify": False}

def generate_daily_summary(daily_log):
    """Chiede a Gemini di creare un report vocale nello stile autentico di Jarvis"""
    if not daily_log:
        events_text = "Nessun movimento rilevato sui canali ufficiali o di rassegna stampa."
    else:
        events_text = "\n".join(daily_log)
    
    prompt = f"""
    Sei Jarvis, l'intelligenza artificiale personale e maggiordomo di bordo.
    Il tuo compito è fornire un resoconto vocale rapido e impeccabile al tuo creatore riguardo il GP di Formula 1 di Imola e la disponibilità dei biglietti.

    Ecco i dati raccolti nelle ultime ore:
    {events_text}

    Istruzioni per lo stile (INCONFONDIBILE STILE JARVIS):
    - Esordisci con un saluto formale e distinto in italiano (es. "Signore,", "Buondì, Signore.", "Ammiraglio,").
    - Usa un tono composto, estremamente educato, britannico ed efficiente.
    - Se non ci sono novità, rassicuralo dicendo che i sistemi sono operativi, tutto tace sul fronte biglietti e che continuerai a monitorare.
    - Se ci sono novità importanti, sintetizzale con estrema precisione e chiarezza chirurgica.
    - Chiudi con una frase di congedo breve ed elegante (es. "Resto in attesa di ulteriori sviluppi.", "Sistemi in stand-by.").
    - Lunghezza massima: 3-4 frasi da leggere a voce. Rispondi ESCLUSIVAMENTE con il testo che dovrai pronunciare.
    """
    
    modelli_da_provare = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]

    for nome_modello in modelli_da_provare:
        try:
            response = client.models.generate_content(
                model=nome_modello,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            print(f"Errore generazione report con {nome_modello}: {e}")
            time.sleep(1)

    return "Signore, i sistemi di analisi hanno riscontrato un'anomalia di rete. Tuttavia, non risultano allarmi critici per i biglietti di Imola."

def check_ticketone_direct():
    """Controlla direttamente TicketOne. Se bloccato da anti-bot, fallisce rapidamente in 3s."""
    search_url = "https://www.ticketone.it/search/?searchterm=formula+1+imola"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(search_url, headers=headers, timeout=3)
        print(f"TicketOne HTTP Status: {resp.status_code}")
        
        if resp.status_code == 200:
            text = resp.text.lower()
            print("TicketOne: risposta 200 OK ricevuta.")
            if "biglietti disponibili" in text or "acquista ora" in text or "compra ora" in text:
                return True, search_url
    except requests.exceptions.Timeout:
        print("TicketOne: Timeout (filtro anti-bot attivo sui server cloud). Si prosegue con i feed RSS.")
    except Exception as e:
        print(f"TicketOne non raggiungibile: {e}")
    return False, ""

def main():

    # --- RIGA DI TEST DA AGGIUNGERE ---
    #send_notification("Test Jarvis", "Test funzionante", "https://www.ticketone.it/artist/formula-1-imola/")
    # ----------------------------------
    
    state = load_state()
    new_seen = set(state["seen"])
    any_new_alert = False

    # 1. Controllo diretto TicketOne
    print("Controllo diretto su TicketOne...")
    t1_found, t1_url = check_ticketone_direct()
    if t1_found and t1_url not in new_seen:
        send_notification(
            title="Jarvis F1 Imola (ALTA)",
            message="Rilevati biglietti o eventi attivi direttamente sul sito TicketOne!",
            url=t1_url
        )
        new_seen.add(t1_url)
        any_new_alert = True

    # 2. Controllo Feed RSS con Gemini
    print("Controllo Feed RSS con Jarvis...")
    
    # Imposta il limite: scarta articoli più vecchi di 1 giorno fa rispetto a ora
    time_limit = datetime.now(timezone.utc) - timedelta(days=2)

    for rss_url in RSS_URLS:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]:
            article_id = entry.link
            
            # --- NUOVO CONTROLLO DATA ---
            # Verifica che il feed abbia una data di pubblicazione
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                # Converte il formato data del feed in un formato confrontabile (UTC)
                article_date = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
                
                if article_date < time_limit:
                    print(f"Scartato (Troppo vecchio): {entry.title}")
                    continue # Salta e passa al prossimo articolo
            # ----------------------------

            if article_id in new_seen:
                continue

            print(f"Analizzo: {entry.title}")
            result = analyze_with_jarvis(entry.title, entry.get("summary", ""))

            if result.get("notify"):
                send_notification(
                    title=f"Jarvis F1 Imola ({result.get('urgency', 'INFO')})",
                    message=result.get("short_message", entry.title),
                    url=entry.link
                )
                any_new_alert = True

            # --- NUOVO: Appunta la notizia nel diario di oggi ---
            log_entry = f"- {entry.title}"
            if result.get("notify"):
                log_entry += f" [RITENUTA IMPORTANTE: {result.get('short_message')}]"
            state["daily_log"].append(log_entry)
            # ----------------------------------------------------

            new_seen.add(article_id)

   # 3. Report Periodici (09:30, 15:00, 20:00)
    now_rome = datetime.now(ZoneInfo("Europe/Rome"))
    today_str = now_rome.strftime("%Y-%m-%d")

    # Identifica la fascia oraria corrente
    current_report_id = None
    if now_rome.hour >= 20:
        current_report_id = f"{today_str}_2000"
    elif now_rome.hour >= 15:
        current_report_id = f"{today_str}_1500"
    elif now_rome.hour > 9 or (now_rome.hour == 9 and now_rome.minute >= 30):
        current_report_id = f"{today_str}_0930"

    # Se siamo in una fascia valida e non abbiamo ancora mandato QUESTO report
    if current_report_id and state.get("last_daily_report") != current_report_id:
        print(f"Jarvis sta preparando il briefing vocale ({current_report_id})...")
        
        if "0930" in current_report_id:
            titolo_report = "Jarvis | Briefing Mattutino ☕"
        elif "1500" in current_report_id:
            titolo_report = "Jarvis | Aggiornamento Pomeridiano ☀️"
        else:
            titolo_report = "Jarvis | Resoconto Serale 🌙"

        summary_message = generate_daily_summary(state.get("daily_log", []))
        
        # Invia la notifica con l'audio integrato
        send_jarvis_voice_ntfy(
            title=titolo_report,
            text_message=summary_message,
            url="https://www.ticketone.it"
        )
        
        state["last_daily_report"] = current_report_id
        state["daily_log"] = []
 

    # --- QUESTE DUE RIGHE DEVONO RIMANERE ALLA FINE DEL MAIN ---
    state["seen"] = new_seen
    save_state(state)

if __name__ == "__main__":
    main()
