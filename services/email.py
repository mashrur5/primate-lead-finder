from urllib.parse import urlparse


def guess_email(name, website):
    try:
        parsed = urlparse(website if website.startswith(("http://", "https://")) else f"https://{website}")
        domain = parsed.hostname.replace("www.", "") if parsed.hostname else ""
        parts = [part for part in name.lower().strip().split() if part]
        first = parts[0] if parts else ""
        last = parts[-1] if parts else ""
        if not first or not last or not domain or "github.com" in domain:
            return ""
        return f"{first}.{last}@{domain}"
    except Exception:
        return ""


def resolve_email(founder, company):
    source_email = founder.get("email") or ""
    if source_email:
        return {"email": source_email, "status": "found", "source": "source_profile"}

    guessed = guess_email(founder.get("name", ""), company.get("website", ""))
    if guessed:
        return {"email": guessed, "status": "guessed", "source": "pattern"}

    return {"email": "", "status": "unavailable", "source": ""}
