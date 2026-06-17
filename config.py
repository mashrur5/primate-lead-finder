import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def load_env_file(path=BASE_DIR / ".env"):
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()


PORT = int(os.getenv("PORT", "3001"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
SEEN_FILE = BASE_DIR / "seen_companies.json"
EXPORT_FILE = BASE_DIR / "primate_leads.xlsx"
