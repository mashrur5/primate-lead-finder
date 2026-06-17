import json

from config import SEEN_FILE


def load_seen():
    try:
        if SEEN_FILE.exists():
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        pass
    return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(sorted(seen)), encoding="utf-8")


def mark_seen(ids):
    seen = load_seen()
    seen.update(ids)
    save_seen(seen)


def get_seen_count():
    return len(load_seen())


def reset_seen():
    save_seen(set())
