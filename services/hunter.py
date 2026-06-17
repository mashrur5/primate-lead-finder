import requests

HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")

response = requests.get(
    "https://api.hunter.io/v2/email-finder",
    params={
        "domain": "reddit.com",
        "first_name": "Alexis",
        "last_name": "Ohanian",
        "api_key": HUNTER_API_KEY,
    },
    timeout=15,
)

