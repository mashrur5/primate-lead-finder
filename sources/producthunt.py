import re

import requests

from storage.seen import load_seen


def fetch_product_hunt_leads(max_per_source):
    seen = load_seen()
    results = []

    try:
        response = requests.post(
            "https://www.producthunt.com/frontend/graphql",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-requested-with": "XMLHttpRequest",
            },
            json={
                "operationName": "TopicPosts",
                "query": 'query TopicPosts { topic(slug: "developer-tools") { posts(first: 20, order: NEWEST) { edges { node { name tagline website makers { name username } } } } } }',
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        return results

    posts = response.json().get("data", {}).get("topic", {}).get("posts", {}).get("edges", [])
    for edge in posts:
        post = edge.get("node") or {}
        slug = re.sub(r"\s+", "-", (post.get("name") or "").lower())
        product_id = f"ph_{slug}"
        if not slug or product_id in seen:
            continue
        results.append(
            {
                "id": product_id,
                "source": "Product Hunt",
                "name": post.get("name") or "",
                "slug": product_id,
                "description": post.get("tagline") or "",
                "long_description": post.get("tagline") or "",
                "website": post.get("website") or "",
                "batch": "Product Hunt",
                "team_size": "small",
                "maker": (post.get("makers") or [None])[0],
            }
        )

    return results[:max_per_source]
