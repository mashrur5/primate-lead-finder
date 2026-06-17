import json

import requests

from config import OLLAMA_URL


def ollama_enrich(company, founder, model):
    prompt = f"""You are a sales researcher for Primate, an AI-powered frontend QA platform that reviews GitHub pull requests by launching the real app in a browser, catching visual regressions, broken flows, and UI bugs that code review misses. Perfect for small teams shipping fast. The ICP is early-stage startups with 1-20 employees, building a user facing product.

Company: {company.get("name")}
Source: {company.get("source")}
Description: {company.get("description")}. {company.get("long_description") or ""}
Founder: {founder.get("name")}, {founder.get("title") or "Founder"}
{("Bio: " + founder.get("bio")) if founder.get("bio") else ""}

Tasks:
1. Score fit for Primate: "Strong fit", "Good fit", or "Weak fit"
2. Write a 1-sentence reason why they fit (or not)
3. Write a personalized cold email opening line for {founder.get("name")} that references something specific about what they're building based on web and social media search. Sound human and researched, not templated. 2 sentences max. Don't mention Primate yet.

Return ONLY this JSON (no markdown, no backticks, no explanation):
{{"score":"Strong fit","fit_reason":"...","email_opener":"..."}}"""

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0.7}},
            timeout=90,
        )
        response.raise_for_status()
        text = response.json().get("response") or ""
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON returned by Ollama")
        return json.loads(text[start : end + 1])
    except Exception:
        return {
            "score": "Good fit",
            "fit_reason": "Small software team shipping products that benefit from automated QA.",
            "email_opener": f"I came across {company.get('name')} and liked what you're building.",
        }
