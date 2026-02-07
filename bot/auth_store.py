import json
import os
from pathlib import Path

_DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
_FILE = Path(_DATA_DIR) / "authenticated_users.json"


def _load() -> set[int]:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _FILE.exists():
        return set()
    with open(_FILE) as f:
        return set(json.load(f))


def _save(users: set[int]) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_FILE, "w") as f:
        json.dump(list(users), f)


def add(user_id: int) -> None:
    users = _load()
    users.add(user_id)
    _save(users)


def remove(user_id: int) -> None:
    users = _load()
    users.discard(user_id)
    _save(users)


def is_authenticated(user_id: int) -> bool:
    return user_id in _load()


def get_all() -> set[int]:
    return _load()
