import os
import feedparser
import requests
import json
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC_MONDO")

client = genai.Client(api_key=GEMINI_API_KEY)

def main():
    argomenti = {
        "⚽ Napoli Calcio": "https://news.google.com/rss/search?q=SSC+Napoli+calcio+ultime+notizie&hl=it&gl=IT&ceid=IT:it",
        "🏟️ Calcio (Top News)": "https://news.google.com/rss/search?q=Calcio+Serie+A+Champions+League+ufficiale&hl=it&gl=IT&ceid=IT:it",
        "🇮🇹 Italia": "https://news.google.com/rss/search?q=Italia+notizie+primo+piano+cronaca&hl=it&gl=IT&ceid=IT:it",
        "📱 Tecnologia": "https://news.google.com/rss/search?q=Tecnologia+innovazione+IT&hl=it&gl=IT&ceid=IT:it",
        "🤖 Intelligenza Artificiale": "https://news.google.com/rss/search?q=Intelligenza+Artificiale+AI+OpenAI+Google&hl=it&gl=IT&ceid=IT:it",
        "🚗 Auto & Motori": "https://news.google.com/rss/search?q=Auto+novità+mercato+BMW+Audi+Ferrari+ufficiale&hl=it&gl=IT&ceid=IT:it"
    }
    
    testo_notizie = ""
    for categoria, url in argomenti.items():
        feed = feedparser.parse(url)
        testo_notizie += f"\nCATEGORIA: {categoria}\n"
        for entry in feed.entries[:4]:
            testo_notizie += f"- {entry.title}\n"
            
    prompt = f"""
    Sei Jarvis. Leggi i titoli delle notizie di oggi:
    {testo_notizie}
    
    Restituisci ESCLUSIVAMENTE un oggetto JSON con queste due chiavi:
    1. "testo_notifica": Una singola stringa con il riassunto diviso per categorie usando le emoji (per la notifica sul telefono). Ignora i rumor minori.
    2. "frasi_hud": Una lista (array) di stringhe. Ogni stringa è una singola frase che la tua voce leggerà ad alta voce nell'interfaccia HUD. Scrivile in un italiano naturale, fluido e professionale, senza emoji o elenchi puntati. Inizia sempre con "Buongiorno signore, ecco l'aggiornamento richiesto."
    """
    
    try:
        print("Chiedo a Gemini di preparare i dati...")
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        dati = json.loads(response.text)
        
        # 1. Salva i dati per l'interfaccia HUD
        with open("briefing.json", "w", encoding="utf-8") as f:
            json.dump(dati["frasi_hud"], f, ensure_ascii=False, indent=2)
            
        # 2. Invia la solita notifica sul telefono
        headers = {
            "Title": "Jarvis - Il tuo Daily Briefing ☕".encode('utf-8'),
            "Priority": "default"
        }
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=dati["testo_notifica"].encode('utf-8'), headers=headers)
        print("Dati HUD salvati e notifica inviata con successo!")
        
    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    main()
