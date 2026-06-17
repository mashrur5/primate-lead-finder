import os
from urllib.parse import urlparse

import requests


HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")


def get_domain(website):
    if not website:
        return ""

    if not website.startswith(("http://", "https://")):
        website = f"https://{website}"

    hostname = urlparse(website).hostname or ""
    return hostname.removeprefix("www.")


def get_founder_names(founder):
    first_name = founder.get("first_name") or ""
    last_name = founder.get("last_name") or ""

    if first_name and last_name:
        return first_name, last_name

    parts = [part for part in (founder.get("name") or "").strip().split() if part]
    if len(parts) < 2:
        return first_name, last_name

    return parts[0], parts[-1]


def resolve_email(founder, company):
    source_email = founder.get("email") or ""

    if source_email:
        return {"email": source_email, "status": "found", "source": "source_profile"}
    else:
        domain = get_domain(company.get("website") or "")
        first_name, last_name = get_founder_names(founder)

        if domain and first_name and last_name and HUNTER_API_KEY:
            try:
                response = requests.get(
                    "https://api.hunter.io/v2/email-finder",
                    params={
                        "domain": domain,
                        "first_name": first_name,
                        "last_name": last_name,
                        "api_key": HUNTER_API_KEY,
                    },
                    timeout=8,
                )
                response.raise_for_status()
                data = response.json()
                email = (data.get("data") or {}).get("email")

                if email:
                    return {
                        "name": f"{first_name} {last_name}",
                        "email": email,
                        "status": "found",
                        "source": "hunter",
                    }
            except requests.RequestException:
                print("Hunter email search failed for domain:", domain)

    return {"email": "", "status": "unavailable", "source": ""}
