"""分析メモの保存。Notionデータベースが設定されていればそちらに保存し、
未設定時やAPI呼び出し失敗時はローカルJSON（data/notes.json）にフォールバックする。
"""

import json
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

LOCAL_NOTES_FILE = Path(__file__).parent / "data" / "notes.json"

NOTION_TICKER_PROPERTY = "銘柄コード"
NOTION_MEMO_PROPERTY = "メモ"
NOTION_DATE_PROPERTY = "保存日時"


def get_notion_config() -> tuple[str, str]:
    def _get(key: str) -> str:
        try:
            return st.secrets[key]
        except Exception:
            return os.environ.get(key, "")

    return _get("NOTION_API_KEY"), _get("NOTION_DATABASE_ID")


def _notion_client():
    from notion_client import Client

    api_key, _ = get_notion_config()
    return Client(auth=api_key)


def save_note(ticker: str, memo: str) -> None:
    api_key, database_id = get_notion_config()
    if api_key and database_id:
        try:
            _notion_client().pages.create(
                parent={"database_id": database_id},
                properties={
                    NOTION_TICKER_PROPERTY: {"title": [{"text": {"content": ticker}}]},
                    NOTION_MEMO_PROPERTY: {"rich_text": [{"text": {"content": memo}}]},
                    NOTION_DATE_PROPERTY: {"date": {"start": datetime.now().isoformat()}},
                },
            )
            return
        except Exception as e:
            st.warning(f"Notionへの保存に失敗したため、ローカルに保存します（{e}）")

    _save_local(ticker, memo)


def get_notes(ticker: str) -> list[dict]:
    api_key, database_id = get_notion_config()
    if api_key and database_id:
        try:
            response = _notion_client().databases.query(
                database_id=database_id,
                filter={"property": NOTION_TICKER_PROPERTY, "title": {"equals": ticker}},
                sorts=[{"property": NOTION_DATE_PROPERTY, "direction": "descending"}],
            )
            notes = []
            for page in response.get("results", []):
                props = page["properties"]
                memo_rich = props[NOTION_MEMO_PROPERTY]["rich_text"]
                memo = memo_rich[0]["text"]["content"] if memo_rich else ""
                date = props[NOTION_DATE_PROPERTY]["date"]
                timestamp = date["start"] if date else ""
                notes.append({"timestamp": timestamp, "memo": memo})
            return notes
        except Exception as e:
            st.warning(f"Notionからの読み込みに失敗したため、ローカルのメモを表示します（{e}）")

    return _get_local(ticker)


def _load_all_local() -> dict:
    if not LOCAL_NOTES_FILE.exists():
        return {}
    with LOCAL_NOTES_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_all_local(data: dict) -> None:
    LOCAL_NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCAL_NOTES_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _save_local(ticker: str, memo: str) -> None:
    data = _load_all_local()
    entries = data.setdefault(ticker, [])
    entries.append({"timestamp": datetime.now().isoformat(timespec="seconds"), "memo": memo})
    _save_all_local(data)


def _get_local(ticker: str) -> list[dict]:
    return _load_all_local().get(ticker, [])
