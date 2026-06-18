"""銘柄チャートの取得・指標計算・初心者向けヒント表示。"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_price_history(ticker: str, period: str) -> pd.DataFrame:
    return yf.Ticker(ticker).history(period=period)


def calculate_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def add_indicators(df: pd.DataFrame, sma_short: int, sma_long: int) -> pd.DataFrame:
    df = df.copy()
    df["SMA_short"] = df["Close"].rolling(sma_short).mean()
    df["SMA_long"] = df["Close"].rolling(sma_long).mean()
    df["RSI"] = calculate_rsi(df["Close"])
    return df


def build_chart(df: pd.DataFrame, sma_short: int, sma_long: int, ticker: str) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.06,
        subplot_titles=(f"{ticker} ローソク足チャート", "RSI (14)"),
    )
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
            name="価格",
        ),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["SMA_short"], name=f"SMA{sma_short}", line=dict(width=1)),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["SMA_long"], name=f"SMA{sma_long}", line=dict(width=1)),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(width=1, color="purple")),
        row=2, col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)
    fig.update_layout(
        height=650,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=60, b=20),
    )
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
        period = st.selectbox(
            "表示期間", ["3mo", "6mo", "1y", "2y"], index=1, key=f"{key_prefix}_period"
        )
    with col3:
        sma_short = st.number_input(
            "短期移動平均(日)", min_value=5, max_value=60, value=25, key=f"{key_prefix}_sma_short"
        )
    with col4:
        sma_long = st.number_input(
            "長期移動平均(日)", min_value=20, max_value=200, value=75, key=f"{key_prefix}_sma_long"
        )

    result = {"ticker": ticker, "per": None, "pbr": None, "roe": None}

    if not ticker:
        st.info("銘柄コードを入力してください。")
        return result

    try:
        df = fetch_price_history(ticker, period)
    except Exception as e:
        st.error(f"データ取得に失敗しました: {e}")
        return result

    if df.empty:
        st.warning("データが見つかりませんでした。銘柄コードを確認してください。")
        return result

    df = add_indicators(df, sma_short, sma_long)
    st.plotly_chart(build_chart(df, sma_short, sma_long, ticker), use_container_width=True)

    st.markdown("**🔎 初心者向けヒント**")
    st.info(f"トレンド: {trend_hint(df)}")
    st.info(f"RSI: {rsi_hint(df)}")

    if show_fundamentals:
        st.markdown("**📋 財務指標（手入力・比較用）**")
        c1, c2, c3 = st.columns(3)
        with c1:
            result["per"] = st.number_input(
                "PER（倍）", min_value=0.0, value=0.0, step=0.1, key=f"{key_prefix}_per"
            )
        with c2:
            result["pbr"] = st.number_input(
                "PBR（倍）", min_value=0.0, value=0.0, step=0.1, key=f"{key_prefix}_pbr"
            )
        with c3:
            result["roe"] = st.number_input(
                "ROE（%）", min_value=0.0, value=0.0, step=0.1, key=f"{key_prefix}_roe"
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
                "指標": ["PER（倍）", "PBR（倍）", "ROE（%）"],
                result_a["ticker"] or "銘柄A": [result_a["per"], result_a["pbr"], result_a["roe"]],
                result_b["ticker"] or "銘柄B": [result_b["per"], result_b["pbr"], result_b["roe"]],
            }
        )
        st.dataframe(compare_df, hide_index=True, use_container_width=True)

    st.caption("これは教育目的の参考情報であり、投資助言ではありません。最終判断は自己責任で行ってください。")
    return result_a["ticker"]
