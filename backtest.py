"""バックテスト — 自分で立てた売買ルールを過去データで検証する学習ツール。

仮想売買タブと同じシグナルロジック（移動平均クロス＋RSI、損切り/利確）を
過去の株価に適用し、「そのルールで戦っていたらどうなっていたか」を確認する。

ルールの良し悪しを判断するのはAIではなく自分。ここでは
勝率・合計損益・最大ドローダウン・バイ＆ホールド比較という
「見るべき数字」を並べることに徹する。

注意（結果を過信しないための前提）:
- 手数料・スリッページ・税金は未考慮
- シグナルは当日の終値で判定し、翌営業日の始値で約定する想定（先読みなし）
- ファンダメンタルズフィルターは過去時点の指標が取得できないため適用されない
- 過去に勝ったルールが将来も勝つ保証はない（パラメータをいじりすぎると
  過去だけに最適化された「カーブフィッティング」になりやすい）
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from auto_trader import evaluate_signal
from stock_analysis import add_indicators, fetch_price_history, normalize_ticker

BACKTEST_PERIODS = {"1年": "1y", "2年": "2y", "5年": "5y", "10年": "10y"}


def run_backtest(
    df: pd.DataFrame,
    sma_short: int,
    sma_long: int,
    initial_capital: float,
    per_trade_max: float,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> dict | None:
    """日足データにルールを適用し、成績サマリーを返す。データ不足ならNone。

    先読み防止のため、シグナルはi日目の終値までの情報で判定し、
    約定はi+1日目の始値で行う。
    """
    df = df[df["Close"].notna()].copy()
    warmup = sma_long + 1
    if len(df) < warmup + 10:
        return None
    df = add_indicators(df, sma_short, sma_long)

    cash = float(initial_capital)
    shares = 0
    avg_price = 0.0
    trades: list[dict] = []
    pending: tuple[str, str] | None = None  # 翌営業日の始値で執行する注文
    equity_values: list[float] = []

    opens = df["Open"].astype(float).tolist()
    closes = df["Close"].astype(float).tolist()

    for i in range(len(df)):
        open_p, close_p = opens[i], closes[i]

        # 1. 前日に出た注文を今日の始値で執行
        if pending is not None:
            side, reason = pending
            pending = None
            if side == "buy" and shares == 0:
                qty = int(min(per_trade_max, cash) // open_p)
                if qty > 0:
                    cash -= qty * open_p
                    shares, avg_price = qty, open_p
                    trades.append({
                        "日付": df.index[i].date(), "売買": "買", "株数": qty,
                        "価格": round(open_p, 1), "損益": None, "理由": reason,
                    })
            elif side == "sell" and shares > 0:
                pl = (open_p - avg_price) * shares
                cash += shares * open_p
                trades.append({
                    "日付": df.index[i].date(), "売買": "売", "株数": shares,
                    "価格": round(open_p, 1), "損益": round(pl, 0), "理由": reason,
                })
                shares = 0

        # 2. 今日の終値でシグナルを判定（執行は翌営業日）
        if i >= warmup:
            if shares > 0:
                chg = (close_p - avg_price) / avg_price * 100
                if chg <= -stop_loss_pct:
                    pending = ("sell", f"損切りライン到達 {chg:+.1f}%")
                elif chg >= take_profit_pct:
                    pending = ("sell", f"利確ライン到達 {chg:+.1f}%")
                else:
                    sig, reasons = evaluate_signal(df.iloc[i - 1:i + 1])
                    if sig == "sell":
                        pending = ("sell", "売りシグナル: " + " / ".join(reasons))
            else:
                sig, reasons = evaluate_signal(df.iloc[i - 1:i + 1])
                if sig == "buy":
                    pending = ("buy", " / ".join(reasons))

        equity_values.append(cash + shares * close_p)

    equity = pd.Series(equity_values, index=df.index)
    buy_hold = pd.Series(
        [initial_capital / closes[0] * c for c in closes], index=df.index
    )

    sells = [t for t in trades if t["売買"] == "売"]
    wins = [t for t in sells if (t["損益"] or 0) > 0]
    drawdown = equity / equity.cummax() - 1

    return {
        "equity": equity,
        "buy_hold": buy_hold,
        "trades": trades,
        "final_equity": float(equity.iloc[-1]),
        "total_return_pct": (float(equity.iloc[-1]) / initial_capital - 1) * 100,
        "buy_hold_return_pct": (closes[-1] / closes[0] - 1) * 100,
        "n_trades": len(sells),
        "win_rate_pct": len(wins) / len(sells) * 100 if sells else None,
        "max_drawdown_pct": float(drawdown.min()) * 100,
        "open_position": shares > 0,
    }


def _one_point_advice(result: dict, stop_loss_pct: float, take_profit_pct: float) -> list[str]:
    """結果のパターンから「次に何を触るべきか」のヒントを最大2つ返す（ルールベース）。"""
    tips: list[str] = []
    ret = result["total_return_pct"]
    bh = result["buy_hold_return_pct"]
    n = result["n_trades"]
    win = result["win_rate_pct"]
    dd = result["max_drawdown_pct"]

    if n == 0:
        return ["一度も取引が発生していません。検証期間を伸ばすか、移動平均の日数を短くしてシグナルが出やすい条件から始めてみましょう。"]

    if ret < bh and win is not None and win < 40:
        tips.append(
            f"典型的な「往復ビンタ」型です。損切りライン（{stop_loss_pct:.0f}%）が銘柄の普段の振れ幅より狭いと、"
            "下がるたびに損切り→直後の反発を取り逃す、を繰り返します。"
            "損切りを広げるか、長期の移動平均でゆっくりしたトレンドだけを追ってみましょう。"
        )
    if ret < bh and win is not None and win >= 55:
        tips.append(
            f"勝率は高いのにトータルで負ける「コツコツドカン」型です。利確（+{take_profit_pct:.0f}%）が早すぎて"
            "利益が小さく、たまの大負けで全部持っていかれています。利確ラインを広げて損小利大に寄せましょう。"
        )
    if dd <= -30:
        tips.append(
            f"最大ドローダウン{dd:.0f}%は、実際のお金なら夜眠れないレベルです。"
            "1回の購入上限を初期資金の一部（例: 3分の1）に抑えると、同じルールでも下落が緩やかになります。"
        )
    if ret > bh and n >= 10:
        tips.append(
            "バイ＆ホールドに勝っています。ただしこの銘柄・この期間に偶然ハマっただけの可能性（過剰最適化）があるので、"
            "同じパラメータのまま別の銘柄と別の期間で再現するか必ず確認しましょう。再現したら本物に近づきます。"
        )
    if n < 10:
        tips.append(
            f"取引回数が{n}回では、結果は偶然の域を出ません。検証期間を5年・10年に伸ばして、"
            "最低でも20〜30回の取引でルールを評価しましょう。"
        )
    if not tips:
        tips.append(
            "大きな破綻のない結果です。ここからは一度に1つだけパラメータを変えて再実行し、"
            "「どの数字が結果に一番効くか」を体感してみましょう。感度が高すぎるルールは本番で脆くなります。"
        )
    return tips[:2]


def render_backtest_section() -> None:
    st.header("🧪 バックテスト — 自分のルールを過去データで検証する")
    st.caption(
        "仮想売買と同じルール（移動平均クロス＋RSI・損切り/利確）を過去の株価に当てはめ、"
        "「そのルールで戦っていたらどうなっていたか」を確認します。"
        "パラメータを自分で動かして、結果がどう変わるかを体感するのが目的です。"
    )

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        ticker = st.text_input(
            "検証する銘柄コード",
            value=st.session_state.get("last_analyzed_ticker", "7203.T"),
            key="bt_ticker",
        )
    with c2:
        period_label = st.selectbox("検証期間", list(BACKTEST_PERIODS.keys()), index=1, key="bt_period")
    with c3:
        initial_capital = st.number_input(
            "初期資金（円）", min_value=10_000, value=300_000, step=10_000, key="bt_capital"
        )

    p1, p2, p3 = st.columns(3)
    with p1:
        sma_short = st.number_input("短期移動平均(日)", 5, 60, 25, key="bt_sma_s")
        sma_long = st.number_input("長期移動平均(日)", 20, 200, 75, key="bt_sma_l")
    with p2:
        stop_loss = st.slider("損切りライン（%）", 3, 20, 8, key="bt_stop")
        take_profit = st.slider("利確ライン（%）", 5, 50, 15, key="bt_profit")
    with p3:
        per_trade_max = st.number_input(
            "1回の購入上限（円）", min_value=10_000, value=300_000, step=10_000, key="bt_per_trade"
        )

    if not st.button("▶ バックテストを実行", type="primary", key="bt_run"):
        return

    code = normalize_ticker(ticker)
    try:
        with st.spinner("過去データを取得して検証しています..."):
            df = fetch_price_history(code, BACKTEST_PERIODS[period_label], "1d")
            result = run_backtest(
                df, int(sma_short), int(sma_long),
                initial_capital, per_trade_max, stop_loss, take_profit,
            )
    except Exception as e:
        st.error(f"データ取得に失敗しました: {e}")
        return

    if result is None:
        st.warning("データが不足しています。検証期間を長くするか、長期移動平均を短くしてください。")
        return

    # ── 成績サマリー ──
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("最終資産", f"{result['final_equity']:,.0f}円",
                  delta=f"{result['total_return_pct']:+.1f}%")
    with m2:
        st.metric("バイ＆ホールドなら", f"{result['buy_hold_return_pct']:+.1f}%",
                  help="同じ資金で最初に買ってずっと持っていた場合のリターン。これに勝てないルールは複雑にする意味がありません。")
    with m3:
        win = result["win_rate_pct"]
        st.metric("勝率 / 取引回数",
                  f"{win:.0f}% / {result['n_trades']}回" if win is not None else f"— / {result['n_trades']}回")
    with m4:
        st.metric("最大ドローダウン", f"{result['max_drawdown_pct']:.1f}%",
                  help="資産が最高値からどれだけ落ち込んだか。自分が精神的に耐えられる下落幅かを確認しましょう。")

    # ── 資産推移チャート ──
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result["equity"].index, y=result["equity"],
                             name="このルール", line=dict(color="#2E8B57", width=2)))
    fig.add_trace(go.Scatter(x=result["buy_hold"].index, y=result["buy_hold"],
                             name="バイ＆ホールド", line=dict(color="#888", width=1.5, dash="dot")))
    fig.update_layout(
        height=380, yaxis_title="資産（円）",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=40, b=20), dragmode=False,
    )
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    st.plotly_chart(fig, use_container_width=True,
                    config={"scrollZoom": False, "displayModeBar": False})

    # ── 取引履歴 ──
    if result["trades"]:
        with st.expander(f"📜 取引履歴（{len(result['trades'])}件）"):
            st.dataframe(pd.DataFrame(result["trades"]), hide_index=True, use_container_width=True)
    else:
        st.info("この期間・パラメータでは一度も取引が発生しませんでした。期間を伸ばすか、条件を緩めてみてください。")
    if result["open_position"]:
        st.caption("※ 検証期間の最終日時点でポジションを保有したまま終了しています（含み損益は最終資産に反映済み）。")

    # ── ワンポイントアドバイス（結果に応じたルールベースのヒント）──
    for tip in _one_point_advice(result, stop_loss, take_profit):
        st.success(f"💡 **ワンポイントアドバイス**: {tip}")

    # ── 学習ガイド ──
    st.markdown("**🔎 結果の読み方（チェックリスト）**")
    st.markdown(
        "- **バイ＆ホールドに勝てているか？** 負けているなら、そのルールは「何もしない」より悪い\n"
        "- **取引回数は十分か？** 数回程度の勝ち負けは偶然。最低でも20〜30回はほしい\n"
        "- **勝率より損益とドローダウンを見る。** 勝率40%でも「勝ち大きく・負け小さく」なら資産は増える\n"
        "- **パラメータを1つ変えて再実行してみる。** 結果が激変するルールは脆い（過剰最適化のサイン）\n"
        "- **別の銘柄・別の期間でも試す。** 特定の銘柄・特定の相場でしか勝てないルールは本番で機能しにくい"
    )
    st.caption("手数料・スリッページ・税金は未考慮です。過去の成績は将来の利益を保証しません。")
