import os
import feedparser
import requests
from google import genai

# Usa le stesse chiavi segrete che hai già impostato per la F1!
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")

client = genai.Client(api_key=GEMINI_API_KEY)

def main():
    # Prende il feed delle notizie generali in primo piano in Italia/Mondo
    rss_url = "https://news.google.com/rss?hl=it&gl=IT&ceid=IT:it"
    feed = feedparser.parse(rss_url)
    
    # Raccoglie i primi 10 titoli
    news_list = []
    for entry in feed.entries[:10]:
        news_list.append(f"- {entry.title}")
        
    news_text = "\n".join(news_list)
    
    prompt = f"""
    Sei Jarvis. Leggi questi titoli delle principali notizie di oggi in Italia e nel mondo:
    {news_text}
    
    Scrivi un riassunto mattutino (massimo 3 punti elenco brevi) con le notizie più importanti della giornata per aggiornare il tuo creatore. Sii conciso, chiaro e usa un tono professionale ma amichevole.
    """
    
    try:
        print("Chiedo a Gemini di riassumere il mondo...")
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )
        summary = response.text.strip()
        
        # Invia la notifica (Priorità standard, non alta come la F1)
        headers = {
            "Title": "Jarvis - Buongiorno Mondo 🌍".encode('utf-8'),
            "Priority": "default"
        }
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=summary.encode('utf-8'), headers=headers)
        print("Notiziario inviato con successo!")
        
    except Exception as e:
        print(f"Errore: {e}")

if __name__ == "__main__":
    main()
