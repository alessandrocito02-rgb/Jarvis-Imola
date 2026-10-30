import os
import feedparser
import requests
from google import genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")

client = genai.Client(api_key=GEMINI_API_KEY)

def main():
    # Ricerche RSS mirate per i tuoi interessi specifici
    argomenti = {
        "⚽ Napoli Calcio": "https://news.google.com/rss/search?q=SSC+Napoli+calcio+ultime+notizie&hl=it&gl=IT&ceid=IT:it",
        "🏟️ Calcio (Top News)": "https://news.google.com/rss/search?q=Calcio+Serie+A+Champions+League+ufficiale&hl=it&gl=IT&ceid=IT:it",
        "🇮🇹 Italia": "https://news.google.com/rss/search?q=Italia+notizie+primo+piano+cronaca&hl=it&gl=IT&ceid=IT:it",
        "📱 Tecnologia": "https://news.google.com/rss/search?q=Tecnologia+innovazione+IT&hl=it&gl=IT&ceid=IT:it",
        "🤖 Intelligenza Artificiale": "https://news.google.com/rss/search?q=Intelligenza+Artificiale+AI+OpenAI+Google&hl=it&gl=IT&ceid=IT:it",
        "🚗 Auto & Motori": "https://news.google.com/rss/search?q=Auto+novità+mercato+BMW+Audi+Ferrari+ufficiale&hl=it&gl=IT&ceid=IT:it"
    }
    
    testo_notizie = ""
    
    # Raccoglie i primi 4 titoli per ogni argomento
    for categoria, url in argomenti.items():
        feed = feedparser.parse(url)
        testo_notizie += f"\nCATEGORIA: {categoria}\n"
        for entry in feed.entries[:4]:
            testo_notizie += f"- {entry.title}\n"
            
    prompt = f"""
    Sei Jarvis. Leggi i titoli delle notizie di oggi, divisi per categoria:
    {testo_notizie}
    
    Scrivi un riassunto mattutino da inviare al tuo creatore. 
    Regole fondamentali di filtraggio:
    - Per "Napoli Calcio", "Italia", "Tecnologia" e "Intelligenza Artificiale", riassumi brevemente le novità principali.
    - Per "Calcio (Top News)" e "Auto & Motori", usa un filtro SEVERISSIMO: scrivi qualcosa SOLO se ci sono notizie veramente di primo piano (es. uscite di nuovi modelli di punta dei grandi marchi, annunci storici, risultati cruciali, infortuni gravi). Ignora i piccoli rumor, le dichiarazioni inutili o i modelli di auto minori.
    
    Struttura il messaggio dividendo chiaramente gli argomenti con le rispettive emoji. Usa 1 o 2 frasi molto sintetiche per categoria, andando dritto al punto. Se per una categoria i titoli non riportano nulla di oggettivamente rilevante, scrivi semplicemente: "Nessuna novità di rilievo."
    """
    
    try:
        print("Chiedo a Gemini di preparare la rassegna stampa personalizzata...")
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )
        summary = response.text.strip()
        
        # Invia la notifica
        headers = {
            "Title": "Jarvis - Il tuo Daily Briefing ☕".encode('utf-8'),
            "Priority": "default"
        }
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=summary.encode('utf-8'), headers=headers)
        print("Rassegna stampa inviata con successo!")
        
    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    main()
