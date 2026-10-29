import json
import os
import feedparser
import requests
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
SEEN_FILE = "seen_articles.json"

RSS_URLS = [
    "https://news.google.com/rss/search?q=Formula+1+Imola+biglietti&hl=it&gl=IT&ceid=IT:it",
    "https://news.google.com/rss/search?q=GP+Imola+F1+conferma+calendario&hl=it&gl=IT&ceid=IT:it",
    "https://news.google.com/rss/search?q=TicketOne+Formula+1+Imola&hl=it&gl=IT&ceid=IT:it"
]

client = genai.Client(api_key=GEMINI_API_KEY)

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen_set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_set), f, indent=2)

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

    Avvisami (notify = true) SOLO SE la notizia riguarda:
    1. L'apertura delle vendite, prevendite o date imminenti di uscita dei biglietti per la F1 a Imola (es. su TicketOne o sito ufficiale).
    2. Notizie ufficiali o molto concrete sul fatto che il GP di Imola è confermato o è stato annullato definitivamente.

    Rispondi ESCLUSIVAMENTE in JSON:
    {{
        "notify": true/false,
        "urgency": "ALTA" o "MEDIA",
        "short_message": "Riassunto chiaro in italiano (max 2 righe)"
    }}
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Errore analisi IA: {e}")
        return {"notify": False}

def main():
    seen = load_seen()
    new_seen = set(seen)

    for rss_url in RSS_URLS:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:5]:
            article_id = entry.link
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

            new_seen.add(article_id)

    save_seen(new_seen)

if __name__ == "__main__":
    main()
