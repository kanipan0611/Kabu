"""ユーザー入力（資産配分・保有株・NISA枠・財務設定など）の永続化ヘルパー。

Streamlitのsession_stateはリロードで消えるため、毎回の再入力を避けるために
data/user_settings.json へ保存する。値が変わったときだけ書き込む。
"""

import json
import os

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_SETTINGS_FILE = os.path.join(_DATA_DIR, "user_settings.json")


def _load_all() -> dict:
    if not os.path.exists(_SETTINGS_FILE):
        return {}
    try:
        with open(_SETTINGS_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_setting(key: str, default=None):
    """保存済みのユーザー設定を返す。未保存ならdefault。"""
    return _load_all().get(key, default)


def set_setting(key: str, value) -> None:
    """ユーザー設定を保存する。値が変わっていなければ書き込まない。"""
    data = _load_all()
    if data.get(key) == value:
        return
    data[key] = value
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_SETTINGS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
