import json

from bs4 import BeautifulSoup
import requests

from sources.github import github_headers


def scrape_yc_founders(slug):
    try:
        response = requests.get(
            f"https://www.ycombinator.com/companies/{slug}",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    script = soup.select_one("script#__NEXT_DATA__")
    if script and script.string:
        try:
            data = json.loads(script.string)
            founders = data.get("props", {}).get("pageProps", {}).get("company", {}).get("founders", [])
            if founders:
                return [
                    {
                        "name": founder.get("full_name") or founder.get("name") or "Founder",
                        "title": founder.get("title") or "Co-Founder",
                        "linkedin": founder.get("linkedin_url") or "",
                    }
                    for founder in founders
                ]
        except json.JSONDecodeError:
            pass

    founders = []
    for link in soup.select('a[href*="linkedin.com/in/"]'):
        name = link.get_text(strip=True)
        if name:
            founders.append({"name": name, "title": "Co-Founder", "linkedin": link.get("href", "")})
    return founders


def enrich_github_founder(company, token=""):
    login = company.get("owner_login") or ""
    try:
        response = requests.get(
            f"https://api.github.com/users/{login}",
            headers=github_headers(token),
            timeout=8,
        )
        response.raise_for_status()
        user = response.json()
        return {
            "name": user.get("name") or login,
            "title": f"Founder at {user.get('company')}" if user.get("company") else "Founder",
            "linkedin": "",
            "email": user.get("email") or "",
            "bio": user.get("bio") or "",
            "location": user.get("location") or "",
            "github": user.get("html_url") or "",
        }
    except requests.RequestException:
        return {"name": login or "Founder", "title": "Founder", "linkedin": "", "email": ""}
