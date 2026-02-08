"""Persisted in-progress jobs: chat_id, user_id, url for long-running flows."""

import json
import os
from pathlib import Path

_DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
_FILE = Path(_DATA_DIR) / "processing_jobs.json"


def _load() -> list[dict]:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _FILE.exists():
        return []
    with open(_FILE) as f:
        return json.load(f)


def _save(jobs: list[dict]) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_FILE, "w") as f:
        json.dump(jobs, f)


def add(chat_id: int, user_id: int, url: str) -> None:
    jobs = _load()
    jobs.append({"chat_id": chat_id, "user_id": user_id, "url": url})
    _save(jobs)


def update_paths(chat_id: int, url: str, video_path: str, srt_path: str | None) -> None:
    jobs = _load()
    for j in jobs:
        if j["chat_id"] == chat_id and j["url"] == url:
            j["video_path"] = video_path
            j["srt_path"] = srt_path
            break
    _save(jobs)


def get_job(chat_id: int, url: str) -> dict | None:
    for j in _load():
        if j["chat_id"] == chat_id and j["url"] == url:
            return j
    return None


def remove(chat_id: int, url: str) -> None:
    jobs = [j for j in _load() if not (j["chat_id"] == chat_id and j["url"] == url)]
    _save(jobs)


def get_by_user(user_id: int) -> list[dict]:
    return [j for j in _load() if j["user_id"] == user_id]
