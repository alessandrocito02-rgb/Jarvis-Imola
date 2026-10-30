import os
import json
import feedparser
import requests
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC_MONDO")

client = genai.Client(api_key=GEMINI_API_KEY)

def main():
    # URL puliti senza apostrofi o caratteri speciali che bloccano il download
    argomenti = {
        "⚽ Napoli Calcio": "https://news.google.com/rss/search?q=SSC+Napoli+calcio&hl=it&gl=IT&ceid=IT:it",
        "📰 Italia": "https://news.google.com/rss/search?q=Italia+cronaca+notizie+oggi&hl=it&gl=IT&ceid=IT:it",
        "📱 Tecnologia": "https://news.google.com/rss/search?q=Tecnologia+innovazione+smartphones&hl=it&gl=IT&ceid=IT:it",
        "🤖 Intelligenza Artificiale": "https://news.google.com/rss/search?q=Intelligenza+Artificiale+OpenAI+Google&hl=it&gl=IT&ceid=IT:it",
        "🚗 Auto & Motori": "https://news.google.com/rss/search?q=Auto+novita+mercato+Ferrari+BMW+Audi&hl=it&gl=IT&ceid=IT:it"
    }
    
    testo_notizie = ""
    
    # Header per fingere di essere un browser vero ed evitare che Google blocchi GitHub Actions
    headers_rss = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    print("1. Scaricamento notizie da Google News...")
    
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

            # Filtro leggero contro notizie spazzatura
            titolo_lower = titolo.lower()
            if any(ban in titolo_lower for ban in ["oroscopo", "lotto", "superenalotto", "meteo"]):
                continue

            testo_temp += f"- TITOLO: {titolo}\n  URL: {link}\n"
            notizie_trovate += 1
            
            # Prendiamo le 3 notizie principali per OGNI categoria (totale 15 notizie)
            if notizie_trovate >= 3:
                break
                
        print(f"Categoria {categoria}: trovate {notizie_trovate} notizie.")
        if notizie_trovate > 0:
            testo_notizie += testo_temp

    if not testo_notizie:
        print("ERRORE: Nessuna notizia scaricata da internet.")
        return

    print("2. Invio notizie a Gemini per la creazione del briefing...")
    
    prompt = f"""
    Sei J.A.R.V.I.S., l'assistente virtuale. Analizza queste notizie divise per categoria:
    {testo_notizie}
    
    ISTRUZIONI OBBLIGATORIE PER LA SINTESI E IL DISCORSO:
    1. Crea ESATTAMENTE 5 elementi nella lista "frasi_hud", uno per ciascuna categoria (Napoli Calcio, Italia, Tecnologia, Intelligenza Artificiale, Auto & Motori).
    2. In ogni blocco, unisci le notizie principali di quella categoria in un unico testo scorrevole ma BREVE (massimo 2 frasi corte per categoria, circa 25-35 parole). Il briefing totale deve durare meno di 1 minuto quando letto ad alta voce.
    3. Rendilo un discorso continuo e collegato:
       - Nel primo blocco inizia salutando ("Buongiorno Signore. Per quanto riguarda il Napoli...")
       - Nei blocchi successivi usa transizioni naturali ("Passando alla cronaca in Italia...", "Sul fronte della tecnologia...", "Nel campo dell'intelligenza artificiale...", "Infine, per il settore auto e motori...").
    4. NON usare emoji, parentesi quadre o simboli dentro "testo", perché verrà letto da un sintetizzatore vocale. Scrivi solo parole pronunciabili.
    5. Nel campo "url" di ciascuno dei 5 blocchi, inserisci l'URL della notizia principale che hai citato per quella categoria.
    
    Restituisci ESCLUSIVAMENTE un oggetto JSON valido con questa struttura:
    {{
      "testo_notifica": "Riassunto telegrafico diviso per categorie con emoji per la notifica del telefono.",
      "frasi_hud": [
        {{
          "testo": "Buongiorno Signore. Per quanto riguarda il Napoli, la squadra si prepara alla prossima sfida mentre si valutano le condizioni degli infortunati.",
          "url": "https://..."
        }},
        {{
          "testo": "Passando alla cronaca in Italia, oggi l'attenzione è concentrata su...",
          "url": "https://..."
        }}
      ]
    }}
    """
    
    # Proviamo i modelli in ordine per sicurezza
    modelli = ["gemini-3.5-flash-lite", "gemini-3.6-flash"]
    dati = None
    
    for modello in modelli:
        try:
            print(f"Tentativo generazione con {modello}...")
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
                print(f"Successo! Generati {len(dati['frasi_hud'])} blocchi notizia per il sito.")
                break
        except Exception as e:
            print(f"Il modello {modello} ha dato errore: {e}")
            
    if not dati or "frasi_hud" not in dati:
        print("ERRORE CRITICO: Impossibile generare il JSON con Gemini.")
        return

    # 3. Salva briefing.json per il sito web
    with open("briefing.json", "w", encoding="utf-8") as f:
        json.dump(dati["frasi_hud"], f, ensure_ascii=False, indent=2)
    print("3. File briefing.json salvato correttamente!")

    # 4. Invia la notifica a Ntfy (senza parentesi quadre negli URL!)
    if NTFY_TOPIC:
        try:
            headers_ntfy = {
                "Title": "Jarvis - Rassegna Stampa 🌍".encode('utf-8'),
                "Priority": "default",
                "Actions": "view, Apri Dashboard, [https://alessandrocito02-rgb.github.io/Jarvis-Imola/](https://alessandrocito02-rgb.github.io/Jarvis-Imola/)"
            }
            requests.post(
                f"[https://ntfy.sh/](https://ntfy.sh/){NTFY_TOPIC}", 
                data=dati.get("testo_notifica", "Nuovo briefing disponibile.").encode('utf-8'), 
                headers=headers_ntfy
            )
            print("4. Notifica Ntfy inviata con successo!")
        except Exception as e_ntfy:
            print(f"Errore invio notifica Ntfy: {e_ntfy}")

if __name__ == "__main__":
    main()
