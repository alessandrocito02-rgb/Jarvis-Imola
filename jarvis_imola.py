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
        headers["Click"] = url
    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=message.encode('utf-8'), headers=headers)

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
    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Errore analisi IA: {e}")
        return {"notify": False}

def generate_daily_summary(daily_log):
    """Chiede a Gemini di riassumere la giornata in modo discorsivo"""
    if not daily_log:
        events_text = "Nessuna notizia rilevata oggi."
    else:
        events_text = "\n".join(daily_log)
    
    prompt = f"""
    Sei Jarvis, assistente personale per i biglietti del GP di F1 a Imola.
    Scrivi un breve resoconto serale (massimo 3-4 righe) da inviare come notifica al tuo creatore.
    
    Ecco le notizie che hai analizzato oggi:
    {events_text}
    
    Se la lista è vuota o contiene solo notizie irrilevanti, rassicura il tuo creatore con un tono amichevole dicendo che non ci sono stati movimenti sui biglietti.
    Se invece nella lista ci sono stati allarmi importanti o novità rilevanti, riassumile in modo chiaro.
    Rispondi ESCLUSIVAMENTE con il testo del messaggio, senza altre introduzioni o formattazioni markdown strane.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"Errore IA nel report serale: {e}")
        return "Errore nella generazione del riassunto serale, ma nessun allarme critico oggi."

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
    time_limit = datetime.now(timezone.utc) - timedelta(days=1)

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

            new_seen.add(article_id)

    # 3. Report Serale (intorno alle ore 20:00 italiane)
    now_rome = datetime.now(ZoneInfo("Europe/Rome"))
    today_str = now_rome.strftime("%Y-%m-%d")

    if now_rome.hour >= 20 and state.get("last_daily_report") != today_str:
        if not any_new_alert:
            send_notification(
                title="Jarvis F1 Imola - Report Serale 🌙",
                message="Nessuna nuova news sui biglietti di Imola oggi. Tutto tranquillo!",
                url="https://www.ticketone.it"
            )
        state["last_daily_report"] = today_str

    state["seen"] = new_seen
    save_state(state)

if __name__ == "__main__":
    main()
