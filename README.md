# Daily News PWA

Una Web App progressiva (PWA) moderna, statica e senza costi per la generazione di una rassegna stampa quotidiana automatizzata tramite AI (Google Gemini). 

## Come Funziona
1. Uno script Python (`generate_news.py`) viene eseguito ogni giorno alle 08:50 (ora italiana) tramite **GitHub Actions**.
2. Lo script scarica le notizie dai feed RSS configurati (`config.json`), ne estrae il testo (con `trafilatura`) e usa l'API di Gemini 2.5 Flash per:
   - Filtrare e raggruppare le notizie.
   - Generare titoli informativi (anti-clickbait).
   - Creare una sintesi di 2-3 righe.
   - Redigere un *deep-dive* dettagliato unendo più fonti.
3. Il risultato viene salvato in `public/data/news_today.json`.
4. GitHub Actions effettua il commit del file aggiornato.
5. Il commit innesca il deploy automatico su **Cloudflare Pages** (la cartella di pubblicazione è `public/`).

## Setup in Locale

1. Clona il repository:
```bash
git clone https://github.com/djiglio/daily_news.git
cd daily_news
```

2. Crea un ambiente virtuale e installa le dipendenze:
```bash
python -m venv .venv
source .venv/bin/activate  # Su Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3. Configura le variabili d'ambiente:
Copia `.env.example` in `.env` e inserisci la tua API Key di Google Gemini.

4. Avvia lo script per generare i dati locali:
```bash
python generate_news.py
```

5. Testa la PWA (usa un server HTTP semplice):
```bash
cd public
python -m http.server 8000
```
Apri il browser su `http://localhost:8000`.

## Cloudflare Pages e GitHub Actions

- In **GitHub**, vai nelle impostazioni del repository, sezione `Secrets and variables > Actions`, e aggiungi il secret `GEMINI_API_KEY`.
- In **Cloudflare Pages**, crea un nuovo progetto connesso al repository GitHub.
- Imposta la *Build command* vuota (o `npm run build` se aggiungerai framework in futuro, ma attualmente non è necessario in quanto statico) e la *Build output directory* su `public`.
