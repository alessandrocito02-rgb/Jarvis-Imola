import os
import json
import feedparser
import requests
import time
from datetime import datetime, timedelta, timezone
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC_MONDO")
SEEN_FILE = "viste_mondo.json" # La memoria di Jarvis per il mondo

client = genai.Client(api_key=GEMINI_API_KEY)

def load_state():
    """Carica lo stato salvato (memoria delle notizie lette)"""
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {"seen": set(data)}
                return {"seen": set(data.get("seen", []))}
        except Exception as e:
            print(f"Errore lettura file memoria: {e}")
    return {"seen": set()}

def save_state(state):
    """Salva lo stato aggiornato"""
    with open(SEEN_FILE, "w") as f:
        json.dump({"seen": list(state["seen"])}, f, indent=2)

def main():
    argomenti = {
        "⚽ Napoli Calcio": "https://news.google.com/rss/search?q=SSC+Napoli+calcio+ultime+notizie&hl=it&gl=IT&ceid=IT:it",
        "📰 Italia": "https://news.google.com/rss/search?q=Italia+cronaca+oggi+notizie+ultim'ora+quotidianità+proteste&hl=it&gl=IT&ceid=IT:it",
        "📱 Tecnologia": "https://news.google.com/rss/search?q=Tecnologia+innovazione+IT&hl=it&gl=IT&ceid=IT:it",
        "🤖 AI": "https://news.google.com/rss/search?q=Intelligenza+Artificiale+AI+OpenAI+Google&hl=it&gl=IT&ceid=IT:it",
        "🚗 Motori": "https://news.google.com/rss/search?q=Auto+novità+mercato+BMW+Audi+Ferrari+ufficiale&hl=it&gl=IT&ceid=IT:it"
    }
    
    state = load_state()
    new_seen = set(state["seen"])
    
    testo_nuove_notizie = ""
    time_limit = datetime.now(timezone.utc) - timedelta(days=2)
    
    print("Ricerca nuove notizie in corso...")
    
    for categoria, url in argomenti.items():
        feed = feedparser.parse(url)
        testo_temp = f"\nCATEGORIA: {categoria}\n"
        notizie_trovate = 0
        
        for entry in feed.entries[:8]: # Controlla le prime 8
            link = getattr(entry, 'link', '')
            titolo = entry.title
            
            # 1. Controlla la memoria: se l'abbiamo già letta, la salta
            if link in new_seen:
                continue
                
            # 2. Controlla la data
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                article_date = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
                if article_date < time_limit:
                    continue

            # 3. Filtro banalità
            titolo_lower = titolo.lower()
            if any(ban in titolo_lower for ban in ["oroscopo", "meteo", "scopri come", "clicca qui", "indiscrezione"]):
                continue

            # Se passa tutti i controlli, è una NUOVA VERA NOTIZIA!
            testo_temp += f"- {titolo} | URL: {link}\n"
            new_seen.add(link)
            notizie_trovate += 1
            
            if notizie_trovate >= 3: # Prende max 3 novità per categoria
                break
                
        if notizie_trovate > 0:
            testo_nuove_notizie += testo_temp

    # Se non ci sono novità, il programma si ferma qui (come fa Imola)
    if not testo_nuove_notizie:
        print("Nessuna nuova notizia rilevante. Jarvis va in standby.")
        return

    print("Trovate nuove notizie! Invio a Gemini per l'analisi...")
    
    prompt = f"""
    Sei Jarvis. Leggi queste NUOVE notizie appena uscite:
    {testo_nuove_notizie}
    
    Regole:
    1. Elabora le notizie in modo accattivante, inserendo curiosità o dettagli rilevanti (3-4 frasi per notizia).
    2. Crea un blocco separato per ogni singola notizia nell'array "frasi_hud".
    
    Restituisci ESCLUSIVAMENTE un file JSON valido con questa struttura esatta:
    {{
      "testo_notifica": "Stringa sintetica di tutte le novità con emoji.",
      "frasi_hud": [
        {{
          "testo": "Riassunto dettagliato e interessante della notizia...",
          "url": "URL della notizia"
        }}
      ]
    }}
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        # Pulisce il testo da eventuali markdown di troppo
        testo_risposta = response.text.strip()
        if testo_risposta.startswith("```"):
            testo_risposta = testo_risposta.strip("`").replace("json\n", "", 1).strip()
            
        dati = json.loads(testo_risposta)
        
        # 1. Salva il file per il sito web
        with open("briefing.json", "w", encoding="utf-8") as f:
            json.dump(dati["frasi_hud"], f, ensure_ascii=False, indent=2)
            
        # 2. Invia la notifica Ntfy
        headers = {
            "Title": "Jarvis - Nuove Notizie 🌍".encode('utf-8'),
            "Priority": "default",
            "Actions": "view, Apri Dashboard, [https://alessandrocito02-rgb.github.io/Jarvis-Imola/](https://alessandrocito02-rgb.github.io/Jarvis-Imola/)"
        }
        requests.post(f"[https://ntfy.sh/](https://ntfy.sh/){NTFY_TOPIC}", data=dati["testo_notifica"].encode('utf-8'), headers=headers)
        
        # 3. Aggiorna la memoria in modo da non rileggere queste notizie al prossimo avvio!
        state["seen"] = new_seen
        save_state(state)
        
        print("Ciclo completato! Memoria aggiornata, file salvato e notifica inviata.")
        
    except Exception as e:
        print(f"Errore durante la generazione o il salvataggio: {e}")

if __name__ == "__main__":
    main()
