"""分析メモのローカル保存（JSONファイル）。"""

import json
from datetime import datetime
from pathlib import Path

NOTES_FILE = Path(__file__).parent / "data" / "notes.json"


def _load_all() -> dict:
    if not NOTES_FILE.exists():
        return {}
    with NOTES_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_all(data: dict) -> None:
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with NOTES_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_note(ticker: str, memo: str) -> None:
    data = _load_all()
    entries = data.setdefault(ticker, [])
    entries.append({"timestamp": datetime.now().isoformat(timespec="seconds"), "memo": memo})
    _save_all(data)


def get_notes(ticker: str) -> list[dict]:
    return _load_all().get(ticker, [])
