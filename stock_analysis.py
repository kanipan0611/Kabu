"""銘柄チャートの取得・指標計算・初心者向けヒント表示。"""

import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

from secrets_utils import get_secret

PERIOD_PRESETS = {
    "1日": ("1d", "5m"),
    "1週間": ("5d", "15m"),
    "1ヶ月": ("1mo", "1d"),
    "3ヶ月": ("3mo", "1d"),
    "6ヶ月": ("6mo", "1d"),
    "1年": ("1y", "1d"),
    "2年": ("2y", "1d"),
}
SHORT_PERIOD_LABELS = {"1日", "1週間", "1ヶ月"}

MARKET_TICKERS = {
    "日経225": "^N225",
    "S&P500": "^GSPC",
    "NYダウ": "^DJI",
}

_JP_TICKER_RE = re.compile(r"^[0-9][0-9A-Z]{3}$")


def normalize_ticker(ticker: str) -> str:
    """4桁の日本株コードのみが入力された場合、yfinance用に「.T」を補う。"""
    code = ticker.strip().upper()
    if not code or "." in code:
        return code
    if _JP_TICKER_RE.match(code):
        return f"{code}.T"
    return code


@st.cache_data(ttl=60 * 5, show_spinner=False)
def fetch_price_history(ticker: str, period: str, interval: str = "1d") -> pd.DataFrame:
    """価格データを取得する。yfinanceが失敗した場合、日足に限り
    Alpha Vantage / J-Quants（secretsにキー設定時のみ）へ自動フォールバックする。"""
    code = normalize_ticker(ticker)
    error: Exception | None = None
    try:
        df = yf.Ticker(code).history(period=period, interval=interval)
    except Exception as e:
        error = e
        df = pd.DataFrame()

    if df.empty and interval == "1d":
        from data_sources import fetch_daily_fallback
        fallback = fetch_daily_fallback(code, period)
        if fallback is not None and not fallback.empty:
            return fallback

    if error is not None and df.empty:
        raise error
    return df


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_dividends(ticker: str) -> pd.Series:
    return yf.Ticker(normalize_ticker(ticker)).dividends


@st.cache_data(ttl=60 * 10, show_spinner=False)
def search_ticker_by_name(query: str) -> list[dict]:
    """企業名やキーワードから、候補となる銘柄コードをyfinance経由で検索する。"""
    query = query.strip()
    if not query:
        return []
    try:
        quotes = yf.Search(query, max_results=8, news_count=0, lists_count=0, enable_fuzzy_query=True).quotes
    except Exception:
        return []

    results = []
    for quote in quotes:
        symbol = quote.get("symbol")
        if not symbol:
            continue
        name = quote.get("shortname") or quote.get("longname") or symbol
        exchange = quote.get("exchange") or ""
        results.append({"symbol": symbol, "name": name, "exchange": exchange})
    return results


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_company_info(ticker: str) -> dict:
    """yfinanceの`.info`を1回だけ取得し、ファンダメンタルズ・業界情報の両方で共有する。"""
    try:
        return yf.Ticker(normalize_ticker(ticker)).info or {}
    except Exception:
        return {}


@st.cache_data(ttl=60 * 10, show_spinner=False)
def fetch_market_overview() -> dict:
    """主要3指数の現在値・前日比を取得する。"""
    result = {}
    for name, sym in MARKET_TICKERS.items():
        try:
            df = yf.Ticker(sym).history(period="2d", interval="1d")
            df = df[df["Close"].notna()]
            if len(df) >= 2:
                cur = float(df["Close"].iloc[-1])
                prev = float(df["Close"].iloc[-2])
                result[name] = {"price": cur, "chg_pct": (cur - prev) / prev * 100}
            elif len(df) == 1:
                result[name] = {"price": float(df["Close"].iloc[-1]), "chg_pct": None}
            else:
                result[name] = {"price": None, "chg_pct": None}
        except Exception:
            result[name] = {"price": None, "chg_pct": None}
    return result


def render_market_overview() -> None:
    """主要3指数をページ上部にコンパクトに表示する。"""
    data = fetch_market_overview()
    cols = st.columns(len(data) + 1)
    for col, (name, info) in zip(cols, data.items()):
        with col:
            price = info["price"]
            chg_pct = info["chg_pct"]
            if price is None:
                st.metric(name, "—")
            elif chg_pct is None:
                st.metric(name, f"{price:,.0f}")
            else:
                st.metric(name, f"{price:,.0f}", delta=f"{chg_pct:+.2f}%")
    with cols[-1]:
        if st.button("🔄", key="market_overview_refresh", help="指数を更新"):
            fetch_market_overview.clear()
            st.rerun()


def fetch_fundamentals(ticker: str) -> dict:
    """yfinanceからPER・PBR・ROEを自動取得する（最終的な評価・判断は自分で行う）。"""
    info = fetch_company_info(ticker)
    roe = info.get("returnOnEquity")
    return {
        "per": info.get("trailingPE"),
        "pbr": info.get("priceToBook"),
        "roe": roe * 100 if roe is not None else None,
    }


def fetch_company_profile(ticker: str) -> dict:
    """セクター・業種・事業概要を自動取得する。"""
    info = fetch_company_info(ticker)
    return {
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "summary": info.get("longBusinessSummary"),
    }


@st.cache_data(ttl=60 * 15, show_spinner=False)
def fetch_company_news(ticker: str, limit: int = 5) -> list[dict]:
    """直近の関連ニュース見出しを自動取得する（yfinance経由）。"""
    try:
        raw_news = yf.Ticker(normalize_ticker(ticker)).news or []
    except Exception:
        return []

    items = []
    for entry in raw_news[:limit]:
        if not isinstance(entry, dict):
            continue
        content = entry.get("content", entry)
        if not isinstance(content, dict):
            continue
        title = content.get("title")
        if not title:
            continue

        provider = content.get("provider")
        publisher = provider.get("displayName") if isinstance(provider, dict) else content.get("publisher")

        link_field = content.get("canonicalUrl")
        link = link_field.get("url") if isinstance(link_field, dict) else content.get("link")

        items.append({"title": title, "publisher": publisher or "", "link": link or ""})
    return items


def claude_news_commentary(api_key: str, ticker: str, profile: dict, news_items: list[dict]) -> tuple[str, str]:
    from claude_client import call_claude

    headlines = "\n".join(f"- {n['title']}（{n['publisher']}）" for n in news_items) or "(関連ニュースなし)"
    prompt = (
        "あなたは投資初心者向けのファイナンス教育アシスタントです。"
        "以下の銘柄に関する直近のニュース見出しと業界情報をもとに、"
        "株価に影響しそうな着目点を、初心者にも分かりやすい日本語で300字程度にまとめてください。"
        "あくまで一つの「参考的な見方」として提示し、"
        "「買い」「売り」のような断定的な助言は避けてください。\n\n"
        f"銘柄: {ticker}\n"
        f"セクター: {profile.get('sector') or '不明'}\n"
        f"業種: {profile.get('industry') or '不明'}\n"
        f"直近のニュース見出し:\n{headlines}\n"
    )
    return call_claude(api_key, prompt, max_tokens=500)


def render_news_section(ticker: str, key_prefix: str) -> None:
    st.markdown("**📰 関連ニュース & 業界情報（自動取得）**")

    profile = fetch_company_profile(ticker)
    if profile.get("sector") or profile.get("industry"):
        st.caption(f"セクター: {profile.get('sector') or '不明'} ／ 業種: {profile.get('industry') or '不明'}")

    news_items = fetch_company_news(ticker)
    if not news_items:
        st.caption("関連ニュースを取得できませんでした。")
    else:
        for item in news_items:
            if item["link"]:
                st.markdown(f"- [{item['title']}]({item['link']}) 　_{item['publisher']}_")
            else:
                st.markdown(f"- {item['title']} 　_{item['publisher']}_")

    if st.button("🧭 ニュース・業界情報をもとに見解を生成", key=f"{key_prefix}_news_view_{ticker}"):
        api_key = get_secret("ANTHROPIC_API_KEY")
        if api_key:
            try:
                with st.spinner("Claudeが見解を作成しています..."):
                    commentary, model_used = claude_news_commentary(api_key, ticker, profile, news_items)
                st.info(commentary)
                st.caption(f"生成モデル: {model_used}")
            except Exception as e:
                st.warning(f"Claude APIの呼び出しに失敗しました（{e}）")
        else:
            st.caption(
                "ANTHROPIC_API_KEY が未設定のため見解を生成できません。"
                "上記のニュース見出しを自分で読んで、自分なりの見解を考えてみましょう。"
            )
    st.caption("これはあくまで参考的な一つの見方であり、投資助言ではありません。最終判断は自己責任で行ってください。")


def calculate_trailing_dividend_yield(ticker: str, current_price: float | None = None) -> dict:
    """直近1年間の配当合計と、現在株価から算出した配当利回り(%)を返す。

    current_priceを渡せば、すでに取得済みの価格データを再利用してyfinanceへの
    追加リクエストを避けられる（チャート表示時の重複取得・レート制限対策）。
    """
    try:
        dividends = fetch_dividends(ticker)
    except Exception:
        return {"annual_dividend": 0.0, "price": None, "yield_pct": None}

    price = current_price
    if price is None:
        try:
            price_df = fetch_price_history(ticker, "5d")
        except Exception:
            return {"annual_dividend": 0.0, "price": None, "yield_pct": None}
        price_df = price_df[price_df["Close"].notna()]
        if price_df.empty:
            return {"annual_dividend": 0.0, "price": None, "yield_pct": None}
        price = price_df["Close"].iloc[-1]

    if dividends.empty:
        return {"annual_dividend": 0.0, "price": price, "yield_pct": 0.0}

    cutoff = pd.Timestamp.now(tz=dividends.index.tz) - pd.Timedelta(days=365)
    annual_dividend = dividends[dividends.index >= cutoff].sum()
    yield_pct = (annual_dividend / price * 100) if price else None
    return {"annual_dividend": annual_dividend, "price": price, "yield_pct": yield_pct}


def dividend_hint(yield_pct: float) -> str:
    if yield_pct == 0:
        return "直近1年の配当実績はありません（無配当）。配当より株価成長を重視するタイプの銘柄かもしれません。"
    if yield_pct < 2:
        return f"配当利回り{yield_pct:.2f}%は市場平均よりやや低めです。"
    if yield_pct <= 4:
        return f"配当利回り{yield_pct:.2f}%は標準的な水準です。"
    return (
        f"配当利回り{yield_pct:.2f}%は高配当とされる水準です。"
        "ただし株価下落によって利回りが見かけ上高くなっているケースもあるため、理由を確認しましょう。"
    )


def calculate_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def add_indicators(
    df: pd.DataFrame,
    sma_short: int,
    sma_long: int,
    show_bb: bool = False,
    show_macd: bool = False,
) -> pd.DataFrame:
    df = df.copy()
    df["SMA_short"] = df["Close"].rolling(sma_short).mean()
    df["SMA_long"] = df["Close"].rolling(sma_long).mean()
    df["RSI"] = calculate_rsi(df["Close"])
    if show_bb:
        bb_window = 20
        df["BB_mid"] = df["Close"].rolling(bb_window).mean()
        bb_std = df["Close"].rolling(bb_window).std()
        df["BB_upper"] = df["BB_mid"] + 2 * bb_std
        df["BB_lower"] = df["BB_mid"] - 2 * bb_std
    if show_macd:
        ema12 = df["Close"].ewm(span=12, adjust=False).mean()
        ema26 = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = ema12 - ema26
        df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
    return df


def build_chart(
    df: pd.DataFrame,
    sma_short: int,
    sma_long: int,
    ticker: str,
    period_label: str,
    show_bb: bool = False,
    show_macd: bool = False,
) -> go.Figure:
    n_rows = 3 if show_macd else 2
    row_heights = [0.55, 0.2, 0.25] if show_macd else [0.7, 0.3]
    subplot_titles = (
        (f"{ticker} ローソク足チャート", "RSI (14)", "MACD (12/26/9)")
        if show_macd
        else (f"{ticker} ローソク足チャート", "RSI (14)")
    )
    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        vertical_spacing=0.05,
        subplot_titles=subplot_titles,
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name="価格",
        ),
        row=1, col=1,
    )
    # SMA lines
    fig.add_trace(
        go.Scatter(x=df.index, y=df["SMA_short"], name=f"SMA{sma_short}", line=dict(width=1)),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["SMA_long"], name=f"SMA{sma_long}", line=dict(width=1)),
        row=1, col=1,
    )

    # Bollinger Bands — upper first, then lower with fill="tonexty" to shade between them
    if show_bb and "BB_upper" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["BB_upper"], name="BB上限",
                line=dict(dash="dash", color="rgba(128,128,128,0.6)", width=1),
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["BB_lower"], name="BB下限",
                line=dict(dash="dash", color="rgba(128,128,128,0.6)", width=1),
                fill="tonexty", fillcolor="rgba(128,128,128,0.1)",
            ),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df["BB_mid"], name="BB中心(20)",
                line=dict(dash="dot", color="rgba(128,128,128,0.8)", width=1),
            ),
            row=1, col=1,
        )

    # RSI
    fig.add_trace(
        go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(width=1, color="purple")),
        row=2, col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

    # MACD
    if show_macd and "MACD" in df.columns:
        hist_colors = [
            "#2ca02c" if v >= 0 else "#d62728"
            for v in df["MACD_hist"].fillna(0)
        ]
        fig.add_trace(
            go.Bar(x=df.index, y=df["MACD_hist"], name="ヒストグラム", marker_color=hist_colors),
            row=3, col=1,
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(color="#1f77b4", width=1)),
            row=3, col=1,
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df["MACD_signal"], name="シグナル", line=dict(color="#ff7f0e", width=1)),
            row=3, col=1,
        )

    chart_height = 750 if show_macd else 650
    fig.update_layout(
        height=chart_height,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60, b=20),
        dragmode=False,
    )
    tickformat = "%-d日" if period_label in SHORT_PERIOD_LABELS else "%-m月"
    fig.update_xaxes(fixedrange=True, tickformat=tickformat)
    fig.update_yaxes(fixedrange=True)
    fig.update_yaxes(range=[0, 100], row=2, col=1)
    return fig


def trend_hint(df: pd.DataFrame) -> str:
    latest = df.iloc[-1]
    price, sma_short, sma_long = latest["Close"], latest["SMA_short"], latest["SMA_long"]
    if pd.isna(sma_short) or pd.isna(sma_long):
        return "表示期間が短く移動平均線を計算できません。期間を長くしてみましょう。"
    if price > sma_short > sma_long:
        return (
            "価格・短期線・長期線がこの順で並ぶ「上昇トレンド」です。"
            "ただしすでに上昇した後の可能性もあるため、高値で慌てて買わないように注意しましょう。"
        )
    if price < sma_short < sma_long:
        return (
            "価格・短期線・長期線が逆順に並ぶ「下降トレンド」です。"
            "初心者はトレンドが落ち着くまで待つのが無難です。"
        )
    return "移動平均線が交錯しており方向感がはっきりしません。トレンドが定まるまで様子を見るのも一つの選択です。"


def rsi_hint(df: pd.DataFrame) -> str:
    rsi = df["RSI"].iloc[-1]
    if pd.isna(rsi):
        return "RSIを計算するにはもう少しデータが必要です。"
    if rsi >= 70:
        return f"RSIは{rsi:.1f}で「買われすぎ」とされる水域です。すぐに飛びつかず、いったん落ち着くのを待つのが無難です。"
    if rsi <= 30:
        return f"RSIは{rsi:.1f}で「売られすぎ」とされる水域です。反発が期待できる場面ですが、さらに下落するリスクもあるため慎重に判断しましょう。"
    return f"RSIは{rsi:.1f}で中立的な範囲です。過熱も悲観もしていない平常の状態です。"


def render_single_stock_panel(
    key_prefix: str, default_ticker: str, show_fundamentals: bool = False
) -> dict:
    """1銘柄分のチャート＋ヒントを描画する。比較モードでは左右に並べて2回呼び出す。"""
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        ticker = st.text_input(
            "銘柄コード（例: 7203.T トヨタ, AAPL アップル）",
            value=default_ticker,
            key=f"{key_prefix}_ticker",
        )
    with col2:
        period_label = st.selectbox(
            "表示期間", list(PERIOD_PRESETS.keys()), index=4, key=f"{key_prefix}_period"
        )
    with col3:
        sma_short = st.number_input(
            "短期移動平均(本)", min_value=5, max_value=60, value=25, key=f"{key_prefix}_sma_short"
        )
    with col4:
        sma_long = st.number_input(
            "長期移動平均(本)", min_value=20, max_value=200, value=75, key=f"{key_prefix}_sma_long"
        )

    # Indicator toggles
    ind_col1, ind_col2 = st.columns(2)
    with ind_col1:
        show_bb = st.checkbox("ボリンジャーバンド(20)", value=False, key=f"{key_prefix}_show_bb")
    with ind_col2:
        show_macd = st.checkbox("MACD(12/26/9)", value=False, key=f"{key_prefix}_show_macd")

    period, interval = PERIOD_PRESETS[period_label]

    with st.popover("🔍 銘柄コードが分からない場合は企業名で検索"):
        name_query = st.text_input("企業名（例: トヨタ, Apple）", key=f"{key_prefix}_name_query")
        if name_query:
            candidates = search_ticker_by_name(name_query)
            if not candidates:
                st.caption("候補が見つかりませんでした。別のキーワードで試してみてください。")
            for candidate in candidates:
                label = f"{candidate['symbol']} — {candidate['name']}"
                if candidate["exchange"]:
                    label += f"（{candidate['exchange']}）"
                if st.button(label, key=f"{key_prefix}_pick_{candidate['symbol']}"):
                    st.session_state[f"{key_prefix}_ticker"] = candidate["symbol"]
                    st.rerun()

    result = {"ticker": ticker, "per": None, "pbr": None, "roe": None, "dividend_yield": None}

    if not ticker:
        st.info("銘柄コードを入力してください。")
        return result

    try:
        df = fetch_price_history(ticker, period, interval)
    except Exception as e:
        st.error(f"データ取得に失敗しました: {e}")
        return result

    df = df[df["Close"].notna()]
    if df.empty:
        st.warning("データが見つかりませんでした。銘柄コードを確認してください。")
        return result

    # Save for cross-tab use (e.g. analysis notes tab default ticker)
    st.session_state["last_analyzed_ticker"] = ticker

    df = add_indicators(df, sma_short, sma_long, show_bb=show_bb, show_macd=show_macd)
    st.plotly_chart(
        build_chart(df, sma_short, sma_long, ticker, period_label, show_bb=show_bb, show_macd=show_macd),
        use_container_width=True,
        config={"scrollZoom": False, "displayModeBar": False, "doubleClickDelay": 1000},
    )

    st.markdown("**🔎 初心者向けヒント**")
    st.info(f"トレンド: {trend_hint(df)}")
    st.info(f"RSI: {rsi_hint(df)}")

    st.markdown("**💴 配当情報（自動取得）**")
    div_info = calculate_trailing_dividend_yield(ticker, current_price=df["Close"].iloc[-1])
    div_yield = None
    if div_info["yield_pct"] is None:
        st.caption("配当データを取得できませんでした。")
    else:
        div_yield = div_info["yield_pct"]
        result["dividend_yield"] = div_yield
        st.metric("配当利回り（直近1年実績）", f"{div_yield:.2f}%")
        st.caption(dividend_hint(div_yield))

    # Auto scoring — always fetch fundamentals silently for rule-based analysis
    auto_fund = fetch_fundamentals(ticker)
    result["per"] = auto_fund["per"]
    result["pbr"] = auto_fund["pbr"]
    result["roe"] = auto_fund["roe"]

    from scoring import render_auto_analysis
    render_auto_analysis(df, auto_fund["per"], auto_fund["pbr"], auto_fund["roe"], div_yield)

    render_news_section(ticker, key_prefix)

    if show_fundamentals:
        st.markdown("**📋 財務指標（自動取得・比較用）**")
        st.caption("初期値はyfinanceからの自動取得値です。気になる場合は書き換えて構いません。")
        c1, c2, c3 = st.columns(3)
        with c1:
            result["per"] = st.number_input(
                "PER（倍）", min_value=0.0, value=float(auto_fund["per"] or 0.0), step=0.1,
                key=f"{key_prefix}_per_{ticker}",
            )
        with c2:
            result["pbr"] = st.number_input(
                "PBR（倍）", min_value=0.0, value=float(auto_fund["pbr"] or 0.0), step=0.1,
                key=f"{key_prefix}_pbr_{ticker}",
            )
        with c3:
            result["roe"] = st.number_input(
                "ROE（%）", min_value=0.0, value=float(auto_fund["roe"] or 0.0), step=0.1,
                key=f"{key_prefix}_roe_{ticker}",
            )

    return result


def render_stock_section() -> str | None:
    st.header("📈 インタラクティブ・チャート分析")

    compare_mode = st.toggle("🔁 2銘柄比較モード", value=False, key="compare_mode")

    if not compare_mode:
        result = render_single_stock_panel("single", "7203.T")
        st.caption("これは教育目的の参考情報であり、投資助言ではありません。最終判断は自己責任で行ってください。")
        return result["ticker"]

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("銘柄A")
        result_a = render_single_stock_panel("cmp_a", "7203.T", show_fundamentals=True)
    with col_b:
        st.subheader("銘柄B")
        result_b = render_single_stock_panel("cmp_b", "6758.T", show_fundamentals=True)

    if any(
        v is not None and v > 0
        for v in (result_a["per"], result_a["pbr"], result_a["roe"], result_b["per"], result_b["pbr"], result_b["roe"])
    ):
        st.markdown("**📊 財務指標の比較**")
        compare_df = pd.DataFrame(
            {
                "指標": ["PER（倍）", "PBR（倍）", "ROE（%）", "配当利回り（%・自動取得）"],
                result_a["ticker"] or "銘柄A": [
                    result_a["per"], result_a["pbr"], result_a["roe"], result_a["dividend_yield"]
                ],
                result_b["ticker"] or "銘柄B": [
                    result_b["per"], result_b["pbr"], result_b["roe"], result_b["dividend_yield"]
                ],
            }
        )
        st.dataframe(compare_df, hide_index=True, use_container_width=True)

        # ── 比較講評（Claude・オンデマンド） ──
        if st.button("🧭 2銘柄の比較講評を生成（Claude）", key="cmp_commentary"):
            api_key = get_secret("ANTHROPIC_API_KEY")
            if not api_key:
                st.caption("ANTHROPIC_API_KEY が未設定のため講評を生成できません。")
            else:
                def _fmt(r):
                    div = r["dividend_yield"]
                    div_str = f"{div:.2f}" if div is not None else "不明"
                    return (
                        f"PER {r['per'] or '不明'}倍 / PBR {r['pbr'] or '不明'}倍 / "
                        f"ROE {r['roe'] or '不明'}% / 配当利回り {div_str}%"
                    )
                prompt = (
                    "あなたは投資初心者向けのファイナンス教育アシスタントです。"
                    "以下の2銘柄の財務指標を比較して、それぞれどんなタイプの銘柄か、"
                    "どういう視点で選び分けるとよいかを、初心者にも分かりやすい日本語で"
                    "400字程度で講評してください。"
                    "「どちらを買うべき」のような断定的な助言は避けてください。\n\n"
                    f"銘柄A（{result_a['ticker']}）: {_fmt(result_a)}\n"
                    f"銘柄B（{result_b['ticker']}）: {_fmt(result_b)}\n"
                )
                try:
                    from claude_client import call_claude
                    with st.spinner("比較講評を作成しています..."):
                        commentary, model_used = call_claude(api_key, prompt, max_tokens=800)
                    st.info(commentary)
                    st.caption(f"生成モデル: {model_used} ／ 投資助言ではありません。")
                except Exception as e:
                    st.warning(f"講評の生成に失敗しました（{e}）")

    st.caption("これは教育目的の参考情報であり、投資助言ではありません。最終判断は自己責任で行ってください。")
    return result_a["ticker"]
