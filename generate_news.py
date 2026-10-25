import os
import json
import logging
import re
from datetime import datetime, timedelta
import calendar
import time
from concurrent.futures import ThreadPoolExecutor
import feedparser
import trafilatura
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG_PATH = 'config.json'
OUTPUT_PATH = 'public/data/news_today.json'

# Modelli candidati: gemini-3.8-flash e il modello principale raccomandato da Google
CANDIDATE_MODELS = ['gemini-3.8-flash', 'gemini-3.6-flash']

# --- PYDANTIC SCHEMAS FOR PHASE 1 ---
class PlannedItem(BaseModel):
    title: str = Field(description="Titolo informativo e chiaro")
    global_importance_score: int = Field(description="Da 1 a 100")
    sources: list[str] = Field(description="URL originali degli articoli usati")
    image_url: str = Field(description="URL dell'immagine, vuoto se non disponibile")

class CategoryPlan(BaseModel):
    items: list[PlannedItem] = Field(description="Esattamente 5 notizie")

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
    title: str = Field(description="Il titolo esatto che ti e stato fornito nella scaletta")
    summary: str = Field(description="Sintesi ultrabreve (max 15-20 parole)")
    deep_dive: str = Field(description="Testo lungo, approfondito, in paragrafi divisi da \\n\\n, con grassetti.")

class CategoryDrafts(BaseModel):
    drafts: list[DraftedItem] = Field(description="Lista delle 5 bozze scritte")

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def clean_html(raw_html):
    if not raw_html:
        return ""
    clean = re.sub(r'<[^>]+>', ' ', raw_html)
    return ' '.join(clean.split())

def extract_image_from_entry(entry):
    if 'media_content' in entry:
        for media in entry['media_content']:
            if media.get('url'):
                return media['url']
    if 'media_thumbnail' in entry and len(entry['media_thumbnail']) > 0:
        return entry['media_thumbnail'][0].get('url', '')
    if 'enclosures' in entry:
        for enc in entry['enclosures']:
            if 'image' in enc.get('type', '') or enc.get('href', '').endswith(('.jpg', '.jpeg', '.png', '.webp')):
                return enc.get('href') or enc.get('url', '')
    if 'links' in entry:
        for link in entry['links']:
            if 'image' in link.get('type', ''):
                return link.get('href', '')
    return ""

def fetch_single_feed(url, max_items):
    entries_data = []
    try:
        feed = feedparser.parse(url, agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        now = datetime.utcnow()
        for entry in feed.entries:
            entry_time_struct = entry.get('published_parsed') or entry.get('updated_parsed')
            if entry_time_struct:
                entry_dt = datetime.utcfromtimestamp(calendar.timegm(entry_time_struct))
                if now - entry_dt > timedelta(days=1):
                    continue
            link = getattr(entry, 'link', '')
            title = getattr(entry, 'title', '')
            if not link or not title:
                continue
            
            raw_summary = entry.get('summary', '') or entry.get('description', '')
            clean_summary = clean_html(raw_summary)[:300]
            img = extract_image_from_entry(entry)
            
            entries_data.append({
                'url': link,
                'title': title,
                'image': img,
                'text': clean_summary
            })
            if len(entries_data) >= max_items:
                break
    except Exception as e:
        logging.warning(f"Error fetching feed {url}: {e}")
    return entries_data

def fetch_all_global_news(config, max_items_per_feed):
    logging.info("--- INIZIO RACCOLTA NOTIZIE DAI FEED RSS (PARALLELA) ---")
    all_feed_urls = set()
    for feeds in config["categories"].values():
        for url in feeds:
            all_feed_urls.add(url)
            
    global_articles = []
    seen_urls = set()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_single_feed, url, max_items_per_feed) for url in all_feed_urls]
        for f in futures:
            for item in f.result():
                if item['url'] not in seen_urls:
                    seen_urls.add(item['url'])
                    global_articles.append(item)
                    
    logging.info(f"--- RACCOLTA COMPLETATA: {len(global_articles)} notizie trovate istantaneamente ---")
    return global_articles

def generate_content_resilient(client, prompt, schema=None, temperature=0.2):
    last_error = None
    for model_name in CANDIDATE_MODELS:
        for attempt in range(1, 4):
            try:
                logging.info(f"Chiamata Gemini ({model_name}) - Tentativo {attempt}/3...")
                config_args = {"temperature": temperature}
                if schema:
                    config_args["response_mime_type"] = "application/json"
                    config_args["response_schema"] = schema
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_args)
                )
                return response
            except Exception as e:
                last_error = e
                err_str = str(e)
                logging.warning(f"Errore con {model_name} (Tentativo {attempt}/3): {err_str}")
                
                if "404" in err_str or "NOT_FOUND" in err_str or "not found" in err_str.lower():
                    logging.info(f"Modello {model_name} non disponibile, passo al successivo.")
                    break
                    
                wait_time = attempt * 15
                logging.info(f"Attesa di {wait_time}s prima di riprovare...")
                time.sleep(wait_time)
                
    raise Exception(f"Tutti i modelli hanno fallito. Ultimo errore: {last_error}")

def generate_master_plan(global_articles, client):
    logging.info("--- FASE 1: GENERAZIONE MASTER PLAN ---")
    
    lightweight_articles = [
        {
            'url': a['url'],
            'title': a['title'],
            'image': a.get('image', ''),
            'text': a['text'][:300]
        }
        for a in global_articles
    ]
    
    prompt = f"""
Sei il Direttore Responsabile di una redazione giornalistica. Ti fornisco un archivio di notizie delle ultime 24 ore.
Devi creare la "Scaletta" della giornata per le seguenti 7 categorie: Italia, Mondo, Politica, Economia, Calcio & Sport, Attualita, Scienze e Tecnologia.

REGOLE TASSATIVE:
1. Scegli ESATTAMENTE 5 notizie per ogni categoria (35 notizie uniche in totale).
2. NON CI DEVONO ESSERE DOPPIONI. Ogni notizia puo appartenere a UNA E UNA SOLA categoria. 
3. CROSS-POLLINATION: Puoi combinare piu URL grezzi per comporre un singolo evento.
4. GLOBAL SCORING: Assegna a ciascuna delle 35 notizie un "global_importance_score" da 1 a 100 in base al suo reale impatto geopolitico o istituzionale. Usa voti alti (90-100) per crisi mondiali, guerre, elezioni, riforme economiche epocali. Usa voti bassi (1-30) per gossip, sport o cronaca minore.
5. Per l'immagine, scegli un URL valido tra le chiavi 'image' degli articoli che stai usando per quella notizia (se presente).

Archivio Notizie:
{json.dumps(lightweight_articles, ensure_ascii=False)}
"""
    response = generate_content_resilient(client, prompt, schema=MasterPlan, temperature=0.2)
    return MasterPlan.model_validate_json(response.text)

def scrape_single_url(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded) or ""
            metadata = trafilatura.extract_metadata(downloaded)
            image = metadata.image if metadata else ""
            return url, text[:2500], image
    except Exception as e:
        logging.warning(f"Failed to scrape {url}: {e}")
    return url, "", ""

def scrape_selected_articles(urls):
    logging.info(f"--- FASE 1.5: SCRAPING PARALLELO DI {len(urls)} ARTICOLI SCELTI ---")
    scraped_data = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(scrape_single_url, urls)
        for url, text, image in results:
            scraped_data[url] = {"text": text, "image": image}
    logging.info("--- SCRAPING PARALLELO COMPLETATO ---")
    return scraped_data

def generate_category_drafts(category_name, planned_items, scraped_data, client):
    logging.info(f"--- FASE 2: SCRITTURA BOZZE PER {category_name} ---")
    
    planned_json = [i.model_dump() for i in planned_items]
    
    assigned_texts = []
    for item in planned_items:
        for url in item.sources:
            if url in scraped_data and scraped_data[url]["text"]:
                assigned_texts.append({
                    "url": url,
                    "text": scraped_data[url]["text"]
                })
    
    prompt = f"""
Sei un esperto giornalista. Il tuo Direttore ti ha assegnato 5 notizie per la categoria '{category_name}'.
Per ciascuna delle 5 notizie fornite, devi scrivere:
1. Il titolo (copialo identico da quello fornito).
2. Una sintesi ultrabreve (max 15-20 parole).
3. Un deep-dive (approfondimento) ESTREMAMENTE LUNGO E DETTAGLIATO (minimo 4-5 paragrafi densi di informazioni).
Non fare riassuntini. Spiega il contesto, i numeri, le citazioni e i retroscena attingendo dai testi grezzi che ti fornisco.
Usa paragrafi separati da doppio a capo (\\n\\n) ed evidenzia in **grassetto** solo i concetti chiave.
4. Fai un CONTROLLO RIGOROSO DI GRAMMATICA E ORTOGRAFIA prima di finalizzare il testo: assicurati che l'italiano sia impeccabile, senza refusi o errori sintattici.

=== LE 5 NOTIZIE DA SCRIVERE (SCALETTA) ===
{json.dumps(planned_json, ensure_ascii=False, indent=2)}

=== TESTI GREZZI DALLE AGENZIE STAMPA (FONTI DA USARE) ===
{json.dumps(assigned_texts, ensure_ascii=False, indent=2)}
"""
    try:
        response = generate_content_resilient(client, prompt, schema=CategoryDrafts, temperature=0.3)
        return CategoryDrafts.model_validate_json(response.text)
    except Exception as e:
        logging.error(f"Errore scrittura {category_name}: {e}")
        return None

def generate_briefing(top_news, client):
    logging.info("--- FASE 4: GENERAZIONE BRIEFING AUDIO ---")
    
    news_list = "\n".join([f"- {item['title']}: {item['summary']}" for item in top_news])
    
    prompt = f"""
Sei uno speaker radiofonico e conduttore di un telegiornale. Ti fornisco le 7 notizie principali di oggi.
Devi scrivere un copione fluido, dinamico e accattivante (max 1 minuto di lettura, circa 120-150 parole) che riassuma questi eventi, esattamente come i titoli di testa di un telegiornale.
Usa un tono professionale ma diretto. Metti in sequenza logica le notizie (es. parti dalle piu gravi).
NON USARE formattazioni, markdown, asterischi o elenchi puntati: scrivi un testo normale, discorsivo, pronto per essere letto ad alta voce da un sintetizzatore vocale.

Le notizie principali:
{news_list}
"""
    try:
        response = generate_content_resilient(client, prompt, schema=None, temperature=0.4)
        testo = response.text.replace('*', '')
        return testo.strip()
    except Exception as e:
        logging.error(f"Failed to generate briefing: {e}")
        return "Buongiorno. Le notizie principali di oggi sono in fase di elaborazione. Restate con noi per i prossimi aggiornamenti."

def get_candidate_models(client):
    preferred = ['gemini-3.8-flash', 'gemini-3.6-flash']
    try:
        discovered = []
        for m in client.models.list():
            name = m.name.replace("models/", "")
            if "flash" in name and "generateContent" in (m.supported_actions or []):
                discovered.append(name)
        discovered = [m for m in discovered if not m.startswith('gemini-2.')]
        result = [m for m in preferred if m in discovered]
        for m in discovered:
            if m not in result:
                result.append(m)
        if result:
            logging.info(f"Modelli Gemini disponibili rilevati da API: {result}")
            return result
    except Exception as e:
        logging.warning(f"Impossibile elencare i modelli via API: {e}")
    return preferred

def main():
    global CANDIDATE_MODELS
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logging.error("GEMINI_API_KEY is not set.")
        return
        
    client = genai.Client(api_key=api_key)
    discovered = get_candidate_models(client)
    if discovered:
        CANDIDATE_MODELS = discovered

    config = load_config()
    max_items_per_feed = config.get("settings", {}).get("max_items_per_feed", 10)
    
    global_articles = fetch_all_global_news(config, max_items_per_feed)
    
    import sys
    master_plan = None
    try:
        master_plan = generate_master_plan(global_articles, client)
    except Exception as e:
        logging.error(f"Failed to generate Master Plan: {e}")
        sys.exit(1)
        
    final_output = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "categories": {}
    }
    
    cat_map = {
        "Italia": master_plan.Italia.items,
        "Mondo": master_plan.Mondo.items,
        "Politica": master_plan.Politica.items,
        "Economia": master_plan.Economia.items,
        "Calcio & Sport": master_plan.Calcio_Sport.items,
        "Attualità": master_plan.Attualita.items,
        "Scienze e Tecnologia": master_plan.Scienze_Tecnologia.items
    }
    
    # Raccogli tutti gli URL unici scelti dal Master Plan per fare scraping solo di questi
    all_chosen_urls = set()
    for planned_items in cat_map.values():
        for item in planned_items:
            for url in item.sources:
                all_chosen_urls.add(url)
                
    scraped_data = scrape_selected_articles(all_chosen_urls)
    
    # Backfill delle immagini se il Master Plan non ne aveva trovata una
    for planned_items in cat_map.values():
        for item in planned_items:
            if not item.image_url:
                for url in item.sources:
                    if url in scraped_data and scraped_data[url]["image"]:
                        item.image_url = scraped_data[url]["image"]
                        break
                        
    all_final_items = []
    
    for cat_name, planned_items in cat_map.items():
        if not planned_items:
            continue
            
        drafts_obj = generate_category_drafts(cat_name, planned_items, scraped_data, client)
        if drafts_obj:
            cat_list = []
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
            
            cat_list.sort(key=lambda x: x["global_importance_score"], reverse=True)
            final_output["categories"][cat_name] = cat_list
            
        time.sleep(3) # Pausa breve per stare sotto 15 RPM senza sprecare minuti
        
    # --- FASE 3: GENERAZIONE TOP NEWS ---
    all_final_items.sort(key=lambda x: x["global_importance_score"], reverse=True)
    top_news = all_final_items[:7]
    
    new_categories = {"Top News": top_news}
    new_categories.update(final_output["categories"])
    final_output["categories"] = new_categories
    
    # Genera il briefing
    briefing_text = generate_briefing(top_news, client)
    final_output["briefing_text"] = briefing_text
            
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    logging.info("News generation completed successfully.")

if __name__ == "__main__":
    main()
