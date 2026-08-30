import os
import json
import logging
from datetime import datetime, timedelta
import calendar
import time
import feedparser
import trafilatura
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG_PATH = 'config.json'
OUTPUT_PATH = 'public/data/news_today.json'

class NewsItem(BaseModel):
    title: str = Field(description="Titolo informativo, chiaro e rigorosamente anti-clickbait")
    summary: str = Field(description="Sintesi ultrabreve e concisa, massimo 1 frase ad alto impatto (max 15-20 parole).")
    deep_dive: str = Field(description="Testo lungo (4-5 paragrafi), approfondito e formattato. Usa paragrafi separati da doppio a capo (\\n\\n) ed evidenzia in **grassetto** solo i nomi, i numeri o le parole chiave principali di ogni paragrafo.")
    image_url: str = Field(description="URL di un'immagine pertinente, scelto tra gli 'image' forniti negli articoli del gruppo. Usa una stringa vuota se non c'è.")
    sources: list[str] = Field(description="Elenco esplicito dei link originali usati come fonte")

class CategoryNews(BaseModel):
    items: list[NewsItem] = Field(description="Lista delle notizie per questa categoria")

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_rss_feed(url, max_items):
    logging.info(f"Fetching RSS: {url}")
    feed = feedparser.parse(url, agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    
    recent_entries = []
    now = datetime.utcnow()
    
    for entry in feed.entries:
        entry_time_struct = entry.get('published_parsed') or entry.get('updated_parsed')
        if entry_time_struct:
            entry_dt = datetime.utcfromtimestamp(calendar.timegm(entry_time_struct))
            if now - entry_dt <= timedelta(days=1):
                recent_entries.append(entry)
        else:
            recent_entries.append(entry)
            
        if len(recent_entries) >= max_items:
            break
            
    return recent_entries

def scrape_text(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            metadata = trafilatura.extract_metadata(downloaded)
            image = metadata.image if metadata else ""
            return text, image
    except Exception as e:
        logging.warning(f"Failed to scrape {url}: {e}")
    return None, ""

def fetch_all_global_news(config, max_items_per_feed):
    logging.info("--- INIZIO RACCOLTA GLOBALE DELLE NOTIZIE ---")
    global_articles = []
    seen_urls = set()
    
    # Collect all unique URLs from all categories
    all_feed_urls = set()
    for feeds in config["categories"].values():
        for url in feeds:
            all_feed_urls.add(url)
            
    for url in all_feed_urls:
        entries = fetch_rss_feed(url, max_items_per_feed)
        for entry in entries:
            link = entry.link
            if link in seen_urls:
                continue
                
            seen_urls.add(link)
            title = entry.title
            text, image_url = scrape_text(link)
            if text:
                global_articles.append({
                    'url': link,
                    'title': title,
                    'image': image_url or "",
                    'text': text[:1500]  # truncate to save tokens but keep essence
                })
                
    logging.info(f"--- RACCOLTA COMPLETATA: {len(global_articles)} articoli grezzi trovati ---")
    return global_articles

def process_category(category_name, global_articles, max_out_items, client):
    logging.info(f"Processing category: {category_name} using global news pool")
    
    if not global_articles:
        return []
    
    # Use Gemini to generate the structured output based on the new editorial line
    prompt = f"""
Sei il Direttore Responsabile di una testata giornalistica premium e indipendente. 
Ti sto fornendo un enorme archivio di articoli grezzi pubblicati in tutto il mondo nelle ultime 24 ore.

IL TUO COMPITO:
Esamina l'intero archivio globale fornito e scrivi ESATTAMENTE {max_out_items} notizie destinate alla sezione '{category_name}' del nostro giornale.
Sei libero di usare e incrociare QUALSIASI articolo dell'archivio, indipendentemente dalla sua fonte originale, per creare un quadro completo (Cross-pollination).

LINEA EDITORIALE RIGOROSA (Mix Istituzionale e Geopolitico):
Seleziona e ordina le 8 notizie seguendo questa priorità:
1. PRIORITÀ MASSIMA (Apertura): Eventi di altissimo impatto geopolitico e macroeconomico, grandi crisi internazionali, istituzioni, guerre, elezioni nazionali o decisioni che cambiano la società.
2. PRIORITÀ MEDIA (Primo Piano): Politica interna (solo se strutturale, ignora le polemiche da talk-show), riforme, grandi scoperte tecnologiche o scientifiche, macro-trend sociali.
3. PRIORITÀ BASSA (Spalla): Cronaca locale, costume, gossip o dichiarazioni di poco conto. (Scartale se ci sono notizie più importanti).

Per ogni notizia genera:
1. Un titolo (anti-clickbait, estremamente informativo).
2. Una sintesi ultrabreve (massimo 1 frase diretta e concisa, 15-20 parole).
3. Un deep-dive molto esteso. Esplora a fondo il background, incrocia le fonti, spiega le cause e gli impatti. Usa paragrafi separati da doppio a capo (\\n\\n).
4. I link originali delle fonti che hai usato per quel deep-dive tra quelli forniti nell'archivio.
5. L'URL di un'immagine rappresentativa (sceglilo tra le chiavi 'image' degli articoli forniti).

Archivio Globale Fornito:
{json.dumps(global_articles, ensure_ascii=False, indent=2)}
"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CategoryNews,
                    temperature=0.3
                ),
            )
            
            category_news = CategoryNews.model_validate_json(response.text)
            return [item.model_dump() for item in category_news.items]
        except Exception as e:
            logging.error(f"Error generating content for {category_name} (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                sleep_time = 15 * (attempt + 1)
                logging.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                return [{"title": "Servizio Temporaneamente Non Disponibile", "summary": f"Errore AI: {str(e)}", "deep_dive": "L'Intelligenza Artificiale non è riuscita a generare questa sezione. Riprova più tardi.", "image_url": "", "sources": []}]

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logging.error("GEMINI_API_KEY is not set.")
        return
        
    client = genai.Client(api_key=api_key)
    config = load_config()
    
    max_items_per_feed = config.get("settings", {}).get("max_items_per_feed", 10) # reduced slightly for global fetch
    max_items_per_category = config.get("settings", {}).get("max_items_per_category", 8)
    
    # 1. FETCH ALL GLOBAL NEWS ONCE
    global_articles = fetch_all_global_news(config, max_items_per_feed)
    
    final_output = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "categories": {}
    }
    
    # 2. PROCESS CATEGORIES USING THE GLOBAL POOL
    for cat in config["categories"].keys():
        items = process_category(cat, global_articles, max_items_per_category, client)
        if items:
            final_output["categories"][cat] = items
        logging.info("Sleeping for 15 seconds to avoid API rate limits...")
        time.sleep(15)
            
    # Save output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    logging.info("News generation completed successfully.")

if __name__ == "__main__":
    main()
