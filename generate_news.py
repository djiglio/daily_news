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

# --- PYDANTIC SCHEMAS FOR PHASE 1 ---
class PlannedItem(BaseModel):
    title: str = Field(description="Titolo informativo e chiaro")
    global_importance_score: int = Field(description="Da 1 a 100")
    sources: list[str] = Field(description="URL originali degli articoli usati")
    image_url: str = Field(description="URL dell'immagine, vuoto se non disponibile")

class CategoryPlan(BaseModel):
    items: list[PlannedItem] = Field(description="Esattamente 8 notizie")

class MasterPlan(BaseModel):
    Italia: CategoryPlan
    Mondo: CategoryPlan
    Calcio_Sport: CategoryPlan = Field(alias="Calcio & Sport")
    Politica: CategoryPlan
    Economia: CategoryPlan
    Attualita: CategoryPlan = Field(alias="Attualità")
    Scienze_Tecnologia: CategoryPlan = Field(alias="Scienze e Tecnologia")

# --- PYDANTIC SCHEMAS FOR PHASE 2 ---
class DraftedItem(BaseModel):
    title: str = Field(description="Il titolo esatto che ti è stato fornito nella scaletta")
    summary: str = Field(description="Sintesi ultrabreve (max 15-20 parole)")
    deep_dive: str = Field(description="Testo lungo, approfondito, in paragrafi divisi da \\n\\n, con grassetti.")

class CategoryDrafts(BaseModel):
    drafts: list[DraftedItem] = Field(description="Lista delle 8 bozze scritte")

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
            text, image_url = scrape_text(link)
            if text:
                global_articles.append({
                    'url': link,
                    'title': entry.title,
                    'image': image_url or "",
                    'text': text[:1000]  # truncate strictly to fit large JSON in prompt
                })
                
    logging.info(f"--- RACCOLTA COMPLETATA: {len(global_articles)} articoli trovati ---")
    return global_articles

def generate_master_plan(global_articles, client):
    logging.info("--- FASE 1: GENERAZIONE MASTER PLAN ---")
    prompt = f"""
Sei il Direttore Responsabile di una redazione giornalistica. Ti fornisco un enorme archivio di articoli grezzi delle ultime 24 ore.
Devi creare la "Scaletta" della giornata per le seguenti 7 categorie: Italia, Mondo, Politica, Economia, Calcio & Sport, Attualità, Scienze e Tecnologia.

REGOLE TASSATIVE:
1. Scegli ESATTAMENTE 8 notizie per ogni categoria (56 notizie uniche in totale).
2. NON CI DEVONO ESSERE DOPPIONI. Ogni notizia può appartenere a UNA E UNA SOLA categoria. 
3. CROSS-POLLINATION: Puoi combinare più URL grezzi per comporre un singolo evento.
4. GLOBAL SCORING: Assegna a ciascuna delle 56 notizie un "global_importance_score" da 1 a 100 in base al suo reale impatto geopolitico o istituzionale. Usa voti alti (90-100) per crisi mondiali, guerre, elezioni, riforme economiche epocali. Usa voti bassi (1-30) per gossip, sport o cronaca minore.
5. Per l'immagine, scegli un URL valido tra le chiavi 'image' degli articoli che stai usando per quella notizia.

Archivio Globale:
{json.dumps(global_articles, ensure_ascii=False)}
"""
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MasterPlan,
            temperature=0.2
        ),
    )
    return MasterPlan.model_validate_json(response.text)

def generate_category_drafts(category_name, planned_items, client):
    logging.info(f"--- FASE 2: SCRITTURA BOZZE PER {category_name} ---")
    
    planned_json = [i.model_dump() for i in planned_items]
    
    prompt = f"""
Sei un esperto giornalista. Il tuo Direttore ti ha assegnato 8 notizie per la categoria '{category_name}'.
Per ciascuna delle 8 notizie fornite, devi scrivere:
1. Il titolo (copialo identico da quello fornito).
2. Una sintesi ultrabreve (max 15-20 parole).
3. Un deep-dive (approfondimento) molto esteso. Esplora il background e gli impatti futuri. Usa paragrafi separati da doppio a capo (\\n\\n) ed evidenzia in **grassetto** solo i concetti chiave.

Ecco le notizie assegnate:
{json.dumps(planned_json, ensure_ascii=False, indent=2)}
"""
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=CategoryDrafts,
                    temperature=0.3
                ),
            )
            return CategoryDrafts.model_validate_json(response.text)
        except Exception as e:
            logging.error(f"Errore scrittura {category_name} (Tentativo {attempt+1}): {e}")
            time.sleep(15)
    return None

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logging.error("GEMINI_API_KEY is not set.")
        return
        
    client = genai.Client(api_key=api_key)
    config = load_config()
    max_items_per_feed = config.get("settings", {}).get("max_items_per_feed", 10)
    
    global_articles = fetch_all_global_news(config, max_items_per_feed)
    
    master_plan = None
    try:
        master_plan = generate_master_plan(global_articles, client)
    except Exception as e:
        logging.error(f"Failed to generate Master Plan: {e}")
        return
        
    final_output = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "categories": {}
    }
    
    all_final_items = []
    
    # Mappatura plan_fields a stringhe categoria
    cat_map = {
        "Italia": master_plan.Italia.items,
        "Mondo": master_plan.Mondo.items,
        "Politica": master_plan.Politica.items,
        "Economia": master_plan.Economia.items,
        "Calcio & Sport": master_plan.Calcio_Sport.items,
        "Attualità": master_plan.Attualita.items,
        "Scienze e Tecnologia": master_plan.Scienze_Tecnologia.items
    }
    
    for cat_name, planned_items in cat_map.items():
        if not planned_items:
            continue
            
        drafts_obj = generate_category_drafts(cat_name, planned_items, client)
        if drafts_obj:
            cat_list = []
            # Combina dati di pianificazione (score, img, sources) con quelli redatti (summary, deep_dive)
            for plan in planned_items:
                draft = next((d for d in drafts_obj.drafts if d.title == plan.title), None)
                if draft:
                    combined = {
                        "title": plan.title,
                        "summary": draft.summary,
                        "deep_dive": draft.deep_dive,
                        "image_url": plan.image_url,
                        "sources": plan.sources,
                        "global_importance_score": plan.global_importance_score
                    }
                    cat_list.append(combined)
                    all_final_items.append(combined)
            
            # Ordinamento della categoria per punteggio
            cat_list.sort(key=lambda x: x["global_importance_score"], reverse=True)
            final_output["categories"][cat_name] = cat_list
            
        time.sleep(15) # rate limit
        
    # --- FASE 3: GENERAZIONE TOP NEWS ---
    # Ordina TUTTE le 56 notizie per punteggio globale decrescente
    all_final_items.sort(key=lambda x: x["global_importance_score"], reverse=True)
    
    # Prendi le prime 8 in assoluto per le "Top News"
    top_news = all_final_items[:8]
    
    # Inseriamo Top News come prima categoria nel dizionario finale (Python 3.7+ mantiene l'ordine di inserimento)
    new_categories = {"Top News": top_news}
    new_categories.update(final_output["categories"])
    final_output["categories"] = new_categories
            
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    logging.info("News generation completed successfully.")

if __name__ == "__main__":
    main()
