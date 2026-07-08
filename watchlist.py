"""ウォッチリスト — 複数銘柄の現在値・前日比を一覧表示する。"""

import json
import os

import pandas as pd
import streamlit as st

from stock_analysis import fetch_price_history, normalize_ticker

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_WATCHLIST_FILE = os.path.join(_DATA_DIR, "watchlist.json")


def _load() -> list[str]:
    if not os.path.exists(_WATCHLIST_FILE):
        return []
    try:
        with open(_WATCHLIST_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _save(tickers: list[str]) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_WATCHLIST_FILE, "w") as f:
        json.dump(tickers, f)


def render_watchlist_section() -> None:
    st.header("👁️ ウォッチリスト")
    st.caption("気になる銘柄を登録しておくと、現在値と前日比をまとめて確認できます。")

    tickers = _load()

    add_col, btn_col = st.columns([4, 1])
    with add_col:
        new_t = st.text_input(
            "追加する銘柄コード（例: 6981.T）",
            key="watchlist_add_input",
            label_visibility="collapsed",
            placeholder="銘柄コードを入力…",
        )
    with btn_col:
        if st.button("＋ 追加", key="watchlist_add_btn", use_container_width=True):
            code = normalize_ticker(new_t)
            if code and code not in tickers:
                tickers.append(code)
                _save(tickers)
                st.rerun()

    if not tickers:
        st.info("銘柄コードを入力して「＋ 追加」を押してください。")
        return

    rows = []
    for ticker in tickers:
        try:
            df = fetch_price_history(ticker, "2d", "1d")
            df = df[df["Close"].notna()]
            price = df["Close"].iloc[-1] if not df.empty else None
            if price is not None and len(df) >= 2:
                prev = df["Close"].iloc[-2]
                chg_pct = (price - prev) / prev * 100
                chg_yen = price - prev
            else:
                chg_pct = chg_yen = None
        except Exception:
            price = chg_pct = chg_yen = None
        rows.append({
            "_ticker": ticker,
            "銘柄コード": ticker,
            "現在値（円）": round(float(price), 1) if price is not None else None,
            "前日比(%)": round(float(chg_pct), 2) if chg_pct is not None else None,
            "前日比(円)": round(float(chg_yen), 1) if chg_yen is not None else None,
        })

    header = st.columns([3, 3, 2, 2, 1])
    for col, label in zip(header, ["銘柄コード", "現在値（円）", "前日比(%)", "前日比(円)", ""]):
        col.markdown(f"**{label}**")

    for row in rows:
        ticker = row["_ticker"]
        c1, c2, c3, c4, c5 = st.columns([3, 3, 2, 2, 1])
        with c1:
            st.write(ticker)
        with c2:
            p = row["現在値（円）"]
            st.write(f"¥{p:,.1f}" if p is not None else "取得失敗")
        with c3:
            pct = row["前日比(%)"]
            if pct is not None:
                arrow = "▲" if pct >= 0 else "▼"
                color = "green" if pct >= 0 else "red"
                st.markdown(f":{color}[{arrow} {abs(pct):.2f}%]")
        with c4:
            yen = row["前日比(円)"]
            if yen is not None:
                sign = "+" if yen >= 0 else ""
                st.write(f"{sign}{yen:,.1f}")
        with c5:
            if st.button("✕", key=f"wl_del_{ticker}", help="削除"):
                tickers.remove(ticker)
                _save(tickers)
                st.rerun()

    if st.button("🔄 データ更新", key="watchlist_refresh"):
        fetch_price_history.clear()
        st.rerun()
