# Primate Lead Pipeline

A full lead enrichment pipeline that:
1. **Fetches** real companies from the YC directory (W25, S24, W24, etc.)
2. **Scrapes** founder names + LinkedIn from each company page
3. **Validates** fit against Primate's ICP using Ollama (local AI)
4. **Writes** a personalized cold email opener per founder
5. **Exports** everything to a `.xlsx` spreadsheet

Runs locally as a FastAPI backend. There is intentionally no frontend right now.

## Requirements

- Python 3.10+
- Ollama with `llama3` pulled

## Setup

```bash
# 1. Create and activate a virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env file (no edits needed unless you change ports)
cp .env.example .env

# 4. Make sure Ollama is running
ollama serve   # (skip if already running)

# 5. Start the pipeline server
python src/app.py
```

API root: **http://localhost:3001**

## Usage

Run the pipeline over Server-Sent Events:

```bash
curl -N "http://localhost:3001/api/pipeline?sources=yc,github&batches=W25,S24,W24&max=15&model=llama3"
```

Useful endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/pipeline` | Runs the lead pipeline and streams progress |
| `GET /api/status` | Checks Ollama availability and installed models |
| `GET /api/seen` | Returns the seen-company count |
| `POST /api/seen/reset` | Clears seen-company history |
| `GET /download/leads` | Downloads the latest spreadsheet |

## Spreadsheet columns

| Column | Description |
|---|---|
| Founder Name | Full name scraped from YC page |
| Title | Co-Founder / CTO etc. |
| Email | Found or guessed from name + domain |
| Email Status | found / guessed / unavailable |
| LinkedIn | Profile URL if available |
| Company | Company name |
| Website | Company URL |
| YC Batch | e.g. W24 |
| Team Size | From YC data |
| Description | One-liner from YC |
| Fit Score | Strong fit / Good fit |
| Fit Reason | Why they're a Primate prospect |
| Personalized Email Opener | AI-written first line tailored to their company |

## Tips

- Process 10–15 companies at a time for best results
- `llama3` or `mistral` give best output quality
- Each company takes ~20–40s (scraping + Ollama generation)
- Emails are guessed unless a source provides one. Add a verification provider before sending at scale.
