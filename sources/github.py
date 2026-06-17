import time

import requests

from storage.seen import load_seen


SEARCHES = [
    "topic:developer-tools topic:saas stars:20..400 pushed:>2024-01-01 fork:false",
    "topic:devtools topic:startup stars:10..300 pushed:>2024-01-01 fork:false",
    "frontend testing automation tool stars:30..500 pushed:>2024-01-01 language:typescript fork:false",
    "qa automation platform saas stars:10..200 pushed:>2024-01-01 fork:false",
]


def github_headers(token=""):
    headers = {
        "User-Agent": "PrimatePipeline/1.0",
        "Accept": "application/vnd.github.v3+json",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def fetch_github_leads(max_per_source, token=""):
    seen = load_seen()
    results = []

    for query in SEARCHES:
        if len(results) >= max_per_source * 2:
            break
        try:
            response = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "per_page": 15, "sort": "updated"},
                headers=github_headers(token),
                timeout=10,
            )
            if response.status_code == 403:
                break
            response.raise_for_status()
        except requests.RequestException:
            continue

        for repo in response.json().get("items", []):
            repo_id = f"gh_{repo.get('full_name')}"
            if repo_id in seen:
                continue
            if not repo.get("homepage") and not repo.get("description"):
                continue

            owner = repo.get("owner") or {}
            if owner.get("type") == "Organization" and repo.get("size", 0) < 50:
                continue

            description = (repo.get("description") or "").lower()
            is_library = any(word in description for word in ["library", "framework", "boilerplate", "template", "starter", "awesome", "list", "tutorial"])
            if is_library:
                continue

            name = (repo.get("name") or "").replace("-", " ").title()
            results.append(
                {
                    "id": repo_id,
                    "source": "GitHub",
                    "name": name,
                    "slug": repo.get("full_name") or "",
                    "description": repo.get("description") or "",
                    "long_description": repo.get("description") or "",
                    "website": repo.get("homepage") or f"https://github.com/{repo.get('full_name')}",
                    "batch": "GitHub",
                    "team_size": "small org" if owner.get("type") == "Organization" else "solo/small",
                    "owner_login": owner.get("login") or "",
                    "owner_type": owner.get("type") or "",
                    "stars": repo.get("stargazers_count") or 0,
                    "language": repo.get("language") or "",
                }
            )

        time.sleep(1.2)

    return results[:max_per_source]
