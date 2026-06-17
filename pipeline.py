import random
import time

from config import GITHUB_TOKEN, OLLAMA_MODEL
from services.ai import ollama_enrich
from services.email import resolve_email
from services.exporter import export_to_xlsx
from services.people import enrich_github_founder, scrape_yc_founders
from sources.github import fetch_github_leads
from sources.producthunt import fetch_product_hunt_leads
from sources.yc import fetch_yc_companies
from storage.seen import get_seen_count, mark_seen
from utils.sse import sse_event


def _split_arg(value, fallback):
    raw = value or fallback
    return [item.strip() for item in raw.split(",") if item.strip()]


def run_pipeline(args):
    batches = _split_arg(args.get("batches"), "W24,S23")
    max_total = int(args.get("max", 15))
    model = args.get("model") or OLLAMA_MODEL
    sources = _split_arg(args.get("sources"), "yc,github")
    github_token = args.get("ghtoken") or GITHUB_TOKEN
    max_per_source = max(1, -(-max_total // max(1, len(sources))))

    leads = []
    processed_ids = []

    try:
        all_companies = []

        if "yc" in sources:
            yield sse_event("progress", {"step": 1, "message": f"[YC] Fetching companies from batches: {', '.join(batches)}..."})
            yc_companies = fetch_yc_companies(batches=batches, max_per_source=max_per_source)
            yield sse_event("progress", {"step": 1, "message": f"[YC] Found {len(yc_companies)} new companies", "ok": True})
            all_companies.extend(yc_companies)

        if "github" in sources:
            yield sse_event("progress", {"step": 1, "message": "[GitHub] Searching for dev-tool startups..."})
            github_companies = fetch_github_leads(max_per_source=max_per_source, token=github_token)
            yield sse_event("progress", {"step": 1, "message": f"[GitHub] Found {len(github_companies)} repos", "ok": True})
            all_companies.extend(github_companies)

        if "producthunt" in sources:
            yield sse_event("progress", {"step": 1, "message": "[Product Hunt] Fetching dev tool launches..."})
            ph_companies = fetch_product_hunt_leads(max_per_source=max_per_source)
            yield sse_event("progress", {"step": 1, "message": f"[Product Hunt] Found {len(ph_companies)} products", "ok": True})
            all_companies.extend(ph_companies)

        random.shuffle(all_companies)
        all_companies = all_companies[:max_total]

        if not all_companies:
            yield sse_event("error", {"message": "No new companies found across all sources. Try resetting seen or adding more batches."})
            return

        yield sse_event("progress", {"step": 1, "message": f"Processing {len(all_companies)} companies total..."})

        for index, company in enumerate(all_companies, start=1):
            yield sse_event(
                "progress",
                {
                    "step": 2,
                    "message": f"[{index}/{len(all_companies)}] [{company['source']}] {company['name']}",
                    "progress": round((index / len(all_companies)) * 100),
                },
            )

            founder = {"name": "Founder", "title": "Co-Founder", "linkedin": "", "email": ""}

            if company["source"] == "YC":
                yield sse_event("progress", {"step": 2, "message": "  -> Scraping YC page for founders..."})
                founders = scrape_yc_founders(company["slug"])
                if founders:
                    founder = founders[0]
            elif company["source"] == "GitHub":
                yield sse_event("progress", {"step": 2, "message": f"  -> Fetching GitHub profile for {company.get('owner_login', '')}..."})
                founder = enrich_github_founder(company, token=github_token)
                time.sleep(0.8)
            elif company["source"] == "Product Hunt" and company.get("maker"):
                founder = {
                    "name": company["maker"].get("name") or "Founder",
                    "title": "Maker",
                    "linkedin": "",
                    "email": "",
                }

            email_result = resolve_email(founder, company)

            yield sse_event("progress", {"step": 3, "message": "  -> Scoring fit + writing personalized opener..."})
            enriched = ollama_enrich(company, founder, model)
            processed_ids.append(company["id"])

            if enriched.get("score") == "Weak fit":
                yield sse_event("progress", {"step": 3, "message": f"  Skipping {company['name']} (weak fit)"})
                continue

            lead = {
                "source": company["source"],
                "founder_name": founder.get("name") or "Founder",
                "founder_title": founder.get("title") or "Co-Founder",
                "email": email_result["email"],
                "email_status": email_result["status"],
                "email_source": email_result["source"],
                "linkedin": founder.get("linkedin") or "",
                "github": founder.get("github") or "",
                "company_name": company["name"],
                "website": company.get("website") or "",
                "batch": company.get("batch") or "",
                "team_size": company.get("team_size") or "",
                "description": company.get("description") or "",
                "score": enriched.get("score") or "Good fit",
                "fit_reason": enriched.get("fit_reason") or "",
                "email_opener": enriched.get("email_opener") or "",
            }

            leads.append(lead)
            yield sse_event("lead", {"lead": lead})

        mark_seen(processed_ids)

        if leads:
            yield sse_event("progress", {"step": 5, "message": f"Exporting {len(leads)} leads to spreadsheet..."})
            export_to_xlsx(leads)
            yield sse_event("done", {"count": len(leads), "totalSeen": get_seen_count()})
        else:
            yield sse_event("error", {"message": "No qualifying leads found. Try resetting seen or different sources."})
    except Exception as exc:
        yield sse_event("error", {"message": str(exc)})
