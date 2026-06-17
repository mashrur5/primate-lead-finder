import math

import requests

from storage.seen import load_seen


ALGOLIA_APP = "7H67QR2EQS"
ALGOLIA_KEY = "8ded26f9a246dabcf3d5e17e01c43576"


def fetch_yc_companies(batches, max_per_source):
    seen = load_seen()
    results = []
    fetch_per_batch = math.ceil((max_per_source * 3) / max(1, len(batches)))

    for batch in batches:
        try:
            response = requests.post(
                f"https://{ALGOLIA_APP}-dsn.algolia.net/1/indexes/companies/query",
                json={
                    "hitsPerPage": fetch_per_batch,
                    "facetFilters": [[f"batch:{batch}"]],
                    "numericFilters": ["team_size_max <= 50"],
                    "attributesToRetrieve": [
                        "name",
                        "slug",
                        "one_liner",
                        "long_description",
                        "website",
                        "batch",
                        "team_size",
                        "industries",
                        "tags",
                    ],
                },
                headers={
                    "X-Algolia-Application-Id": ALGOLIA_APP,
                    "X-Algolia-API-Key": ALGOLIA_KEY,
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            response.raise_for_status()
        except requests.RequestException:
            continue

        for company in response.json().get("hits", []):
            company_id = f"yc_{company.get('slug')}"
            if company_id in seen:
                continue

            text = " ".join(
                [
                    company.get("one_liner") or "",
                    company.get("long_description") or "",
                    " ".join(company.get("industries") or []),
                    " ".join(company.get("tags") or []),
                ]
            ).lower()
            has_software = any(word in text for word in ["software", "saas", "developer", "api", "platform", "tool", "code", "engineer", "ai", "automation", "devops", "b2b"])
            is_not_consumer = not any(word in text for word in ["consumer", "food", "delivery", "fashion", "retail", "dating"])
            if not has_software or not is_not_consumer:
                continue

            results.append(
                {
                    "id": company_id,
                    "source": "YC",
                    "name": company.get("name") or "",
                    "slug": company.get("slug") or "",
                    "description": company.get("one_liner") or "",
                    "long_description": company.get("long_description") or "",
                    "website": company.get("website") or "",
                    "batch": company.get("batch") or "",
                    "team_size": company.get("team_size") or "",
                }
            )

    return results[:max_per_source]
