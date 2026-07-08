"""yfinance以外の株価データソースへのフォールバック（Alpha Vantage / J-Quants）。

yfinanceがレート制限や障害でデータを返せない場合に、secretsにAPIキーが
設定されていれば自動的にこちらへ切り替える。キー未設定なら何もしない。

- ALPHAVANTAGE_API_KEY : Alpha Vantage（無料プランはリクエスト回数制限あり）
- JQUANTS_REFRESH_TOKEN: J-Quants（JPX公式。無料プランは12週間遅延データ）

JPX公式15分遅延APIは法人向け有料サービスのため対象外。
"""

import re

import pandas as pd
import requests
import streamlit as st

from secrets_utils import get_secret

_PERIOD_DAYS = {
    "1d": 1, "5d": 7, "1mo": 31, "3mo": 92, "6mo": 183, "1y": 366, "2y": 731,
}
_JQUANTS_BASE = "https://api.jquants.com/v1"


def _trim_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    days = _PERIOD_DAYS.get(period)
    if not days or df.empty:
        return df
    cutoff = df.index.max() - pd.Timedelta(days=days)
    return df[df.index >= cutoff]


@st.cache_data(ttl=60 * 10, show_spinner=False)
def fetch_daily_alpha_vantage(ticker: str, period: str) -> pd.DataFrame | None:
    """Alpha VantageのTIME_SERIES_DAILYから日足を取得する。キー未設定ならNone。"""
    api_key = get_secret("ALPHAVANTAGE_API_KEY")
    if not api_key:
        return None
    outputsize = "full" if period in ("1y", "2y") else "compact"
    try:
        resp = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "TIME_SERIES_DAILY",
                "symbol": ticker,
                "outputsize": outputsize,
                "apikey": api_key,
            },
            timeout=15,
        )
        series = resp.json().get("Time Series (Daily)")
        if not series:
            return None
        df = pd.DataFrame(series).T
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df = df.rename(columns={
            "1. open": "Open", "2. high": "High", "3. low": "Low",
            "4. close": "Close", "5. volume": "Volume",
        }).astype(float)
        return _trim_period(df[["Open", "High", "Low", "Close", "Volume"]], period)
    except Exception:
        return None


@st.cache_data(ttl=60 * 30, show_spinner=False)
def _jquants_id_token() -> str | None:
    refresh_token = get_secret("JQUANTS_REFRESH_TOKEN")
    if not refresh_token:
        return None
    try:
        resp = requests.post(
            f"{_JQUANTS_BASE}/token/auth_refresh",
            params={"refreshtoken": refresh_token},
            timeout=15,
        )
        return resp.json().get("idToken")
    except Exception:
        return None


@st.cache_data(ttl=60 * 10, show_spinner=False)
def fetch_daily_jquants(ticker: str, period: str) -> pd.DataFrame | None:
    """J-Quants（JPX公式）から日本株の日足を取得する。トークン未設定ならNone。

    無料プランは12週間遅延データのため、直近の値動きは含まれない点に注意。
    """
    code = ticker.split(".")[0]
    if not re.match(r"^[0-9][0-9A-Z]{3}$", code):
        return None  # J-Quantsは日本株のみ
    token = _jquants_id_token()
    if not token:
        return None
    try:
        resp = requests.get(
            f"{_JQUANTS_BASE}/prices/daily_quotes",
            params={"code": code},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        quotes = resp.json().get("daily_quotes")
        if not quotes:
            return None
        df = pd.DataFrame(quotes)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        keep = {"Open": "Open", "High": "High", "Low": "Low", "Close": "Close", "Volume": "Volume"}
        df = df[[c for c in keep if c in df.columns]].astype(float)
        df = df.dropna(subset=["Close"])
        return _trim_period(df, period)
    except Exception:
        return None


def fetch_daily_fallback(ticker: str, period: str) -> pd.DataFrame | None:
    """yfinance失敗時の日足フォールバック。使えたソースのDataFrameを返す。"""
    for fetcher in (fetch_daily_alpha_vantage, fetch_daily_jquants):
        df = fetcher(ticker, period)
        if df is not None and not df.empty:
            return df
    return None
