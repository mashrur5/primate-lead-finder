# 🐒 Primate Lead Pipeline

A full lead enrichment pipeline that:
1. **Fetches** real companies from the YC directory (W25, S24, W24, etc.)
2. **Scrapes** founder names + LinkedIn from each company page
3. **Validates** fit against Primate's ICP using Ollama (local AI)
4. **Writes** a personalized cold email opener per founder
5. **Exports** everything to a `.xlsx` spreadsheet

100% free — no API keys, runs locally.

## Requirements

- [Node.js](https://nodejs.org) v18+
- [Ollama](https://ollama.com) with `llama3` pulled

## Setup

```bash
# 1. Install dependencies
npm install

# 2. Copy env file (no edits needed unless you change ports)
cp .env.example .env

# 3. Make sure Ollama is running
ollama serve   # (skip if already running)

# 4. Start the pipeline server
npm start
```

Open **http://localhost:3001**

## Usage

1. Select which YC batches to scan (W25, S24, W24, etc.)
2. Set max companies to process (start with 10–15)
3. Pick your Ollama model (`llama3` recommended)
4. Click **Run Pipeline**
5. Watch leads appear in real-time as they're processed
6. Click **Download Spreadsheet** when done

## Spreadsheet columns

| Column | Description |
|---|---|
| Founder Name | Full name scraped from YC page |
| Title | Co-Founder / CTO etc. |
| Email | Guessed from name + domain |
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
- Emails are guessed (firstname.lastname@domain) — verify before sending
