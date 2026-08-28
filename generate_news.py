import os
import json
import logging
from datetime import datetime, timedelta
import calendar
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
    summary: str = Field(description="Sintesi mattutina, esattamente 2 o 3 righe per la notizia")
    deep_dive: str = Field(description="Testo dettagliato di approfondimento (spiegazione di contesto, cause, impatti), stile mash-up")
    sources: list[str] = Field(description="Elenco esplicito dei link originali usati come fonte")

class CategoryNews(BaseModel):
    items: list[NewsItem] = Field(description="Lista delle notizie per questa categoria")

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_rss_feed(url, max_items):
    logging.info(f"Fetching RSS: {url}")
    feed = feedparser.parse(url)
    
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
            return text
    except Exception as e:
        logging.warning(f"Failed to scrape {url}: {e}")
    return None

def process_category(category_name, urls, max_rss_items, max_out_items, client):
    logging.info(f"Processing category: {category_name}")
    raw_articles = []
    
    for url in urls:
        entries = fetch_rss_feed(url, max_rss_items)
        for entry in entries:
            link = entry.link
            title = entry.title
            text = scrape_text(link)
            if text:
                raw_articles.append({
                    'url': link,
                    'title': title,
                    'text': text[:2500]  # truncate to avoid huge tokens
                })
    
    if not raw_articles:
        return []
    
    # Use Gemini to generate the structured output
    prompt = f"""
Sei un esperto giornalista. Ho raccolto diversi articoli per la categoria '{category_name}'.
Analizza i seguenti articoli e raggruppali nei {max_out_items} eventi di cronaca o argomenti più importanti.
Per ogni evento genera:
1. Un titolo (anti-clickbait, molto informativo)
2. Una sintesi di esattamente 2-3 righe
3. Un deep-dive (testo dettagliato, contesto, cause, impatti) basato sui testi forniti
4. I link originali delle fonti che hai usato per quel deep-dive tra quelli forniti.

Articoli forniti:
{json.dumps(raw_articles, ensure_ascii=False, indent=2)}
"""

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
        
        # Parse the JSON response
        category_news = CategoryNews.model_validate_json(response.text)
        return [item.model_dump() for item in category_news.items]
    except Exception as e:
        logging.error(f"Error generating content for {category_name}: {e}")
        return [{"title": "Error", "summary": str(e), "deep_dive": "", "sources": []}]

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logging.error("GEMINI_API_KEY is not set.")
        return
        
    client = genai.Client(api_key=api_key)
    config = load_config()
    
    max_items_per_feed = config.get("settings", {}).get("max_items_per_feed", 5)
    max_items_per_category = config.get("settings", {}).get("max_items_per_category", 3)
    
    final_output = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "categories": {}
    }
    
    for cat, feeds in config["categories"].items():
        items = process_category(cat, feeds, max_items_per_feed, max_items_per_category, client)
        if items:
            final_output["categories"][cat] = items
            
    # Save output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    logging.info("News generation completed successfully.")

if __name__ == "__main__":
    main()
