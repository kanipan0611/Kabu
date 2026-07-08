"""仮想自動売買（ペーパートレード）エンジン。

実際の証券口座への発注は一切行わない。ウォッチリストの銘柄に対して
テクニカル指標（移動平均のクロス・RSI）から売買シグナルを判定し、
決めた予算の範囲内で仮想的に売買して損益を記録する学習用の仕組み。

将来、公式APIを提供する証券会社（auカブコム証券 kabuステーションAPI等）に
接続する場合も、このシグナル判定・リスク管理ロジックはそのまま流用できる。
"""

import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st

from scoring import compute_value_score
from stock_analysis import add_indicators, fetch_fundamentals, fetch_price_history, normalize_ticker
from watchlist import get_watchlist

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_STATE_FILE = os.path.join(_DATA_DIR, "paper_trading.json")


# ── 状態の保存・読み込み ──────────────────────────────────────

def _load_state() -> dict | None:
    if not os.path.exists(_STATE_FILE):
        return None
    try:
        with open(_STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _save_state(state: dict) -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _new_state(budget: float) -> dict:
    return {"initial_budget": budget, "cash": budget, "positions": {}, "history": []}


# ── シグナル判定 ──────────────────────────────────────────────

def evaluate_signal(
    df: pd.DataFrame, rsi_buy: float = 30, rsi_sell: float = 70
) -> tuple[str, list[str]]:
    """テクニカル指標から 'buy' / 'sell' / 'hold' と判定理由を返す。

    dfはadd_indicators適用済み（SMA_short / SMA_long / RSI列あり）を前提とする。
    """
    reasons: list[str] = []
    if len(df) < 2:
        return "hold", ["データ不足"]

    last, prev = df.iloc[-1], df.iloc[-2]
    sma_ok = not (
        pd.isna(last["SMA_short"]) or pd.isna(last["SMA_long"])
        or pd.isna(prev["SMA_short"]) or pd.isna(prev["SMA_long"])
    )
    rsi = last.get("RSI")

    buy_votes = sell_votes = 0

    if sma_ok:
        if prev["SMA_short"] <= prev["SMA_long"] and last["SMA_short"] > last["SMA_long"]:
            buy_votes += 1
            reasons.append("ゴールデンクロス（短期線が長期線を上抜け）")
        elif prev["SMA_short"] >= prev["SMA_long"] and last["SMA_short"] < last["SMA_long"]:
            sell_votes += 1
            reasons.append("デッドクロス（短期線が長期線を下抜け）")

    if rsi is not None and not pd.isna(rsi):
        if rsi <= rsi_buy:
            buy_votes += 1
            reasons.append(f"RSI {rsi:.0f} — 売られすぎ水準")
        elif rsi >= rsi_sell:
            sell_votes += 1
            reasons.append(f"RSI {rsi:.0f} — 買われすぎ水準")

    if buy_votes > 0 and sell_votes == 0:
        return "buy", reasons
    if sell_votes > 0 and buy_votes == 0:
        return "sell", reasons
    return "hold", reasons or ["明確なシグナルなし"]


# ── 売買実行（仮想） ──────────────────────────────────────────

def run_paper_trading(
    state: dict,
    tickers: list[str],
    per_trade_max: float,
    stop_loss_pct: float,
    take_profit_pct: float,
    sma_short: int,
    sma_long: int,
    fundamental_min: float | None = None,
) -> tuple[dict, list[dict]]:
    """各銘柄のシグナルを評価し、仮想売買を実行した新しい状態と実行ログを返す。

    fundamental_minを指定すると、テクニカルの買いシグナルが出ても
    PER/PBR/ROEによるバリュー評価がその点数未満の銘柄は購入しない
    （ファンダメンタル分析＋テクニカル分析の併用）。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    actions: list[dict] = []

    for ticker in tickers:
        code = normalize_ticker(ticker)
        try:
            df = fetch_price_history(code, "6mo", "1d")
            df = df[df["Close"].notna()]
            if df.empty:
                actions.append({"銘柄": code, "判定": "スキップ", "理由": "価格データなし"})
                continue
            df = add_indicators(df, sma_short, sma_long)
        except Exception:
            actions.append({"銘柄": code, "判定": "スキップ", "理由": "データ取得失敗"})
            continue

        price = float(df["Close"].iloc[-1])
        signal, reasons = evaluate_signal(df)
        position = state["positions"].get(code)

        # ── 保有中: 損切り・利確・売りシグナル ──
        if position:
            avg = position["avg_price"]
            change_pct = (price - avg) / avg * 100
            sell_reason = None
            if change_pct <= -stop_loss_pct:
                sell_reason = f"損切りライン（-{stop_loss_pct}%）到達: {change_pct:+.1f}%"
            elif change_pct >= take_profit_pct:
                sell_reason = f"利確ライン（+{take_profit_pct}%）到達: {change_pct:+.1f}%"
            elif signal == "sell":
                sell_reason = "売りシグナル: " + " / ".join(reasons)

            if sell_reason:
                proceeds = price * position["shares"]
                pl = proceeds - avg * position["shares"]
                state["cash"] += proceeds
                del state["positions"][code]
                state["history"].append({
                    "日時": now, "銘柄": code, "売買": "売", "株数": position["shares"],
                    "価格": round(price, 1), "損益": round(pl, 0), "理由": sell_reason,
                })
                actions.append({"銘柄": code, "判定": "売却", "理由": sell_reason})
            else:
                actions.append({
                    "銘柄": code, "判定": "保有継続",
                    "理由": f"損益{change_pct:+.1f}% / " + " / ".join(reasons),
                })
            continue

        # ── 未保有: 買いシグナル ──
        if signal == "buy":
            # ファンダメンタルズフィルター（PER/PBR/ROEのバリュー評価）
            if fundamental_min is not None:
                fund = fetch_fundamentals(code)
                value_score = compute_value_score(fund["per"], fund["pbr"], fund["roe"])
                if value_score is not None and value_score < fundamental_min:
                    actions.append({
                        "銘柄": code, "判定": "見送り",
                        "理由": (
                            f"買いシグナルはあるが、バリュー評価{value_score:.0f}点が"
                            f"基準（{fundamental_min:.0f}点）未満のため購入せず"
                        ),
                    })
                    continue
                if value_score is not None:
                    reasons.append(f"バリュー評価{value_score:.0f}点（PER/PBR/ROE）")
                else:
                    reasons.append("ファンダ指標データなし（テクニカルのみで判定）")

            shares = int(min(per_trade_max, state["cash"]) // price)
            if shares <= 0:
                actions.append({"銘柄": code, "判定": "見送り", "理由": "予算不足"})
                continue
            cost = shares * price
            state["cash"] -= cost
            state["positions"][code] = {"shares": shares, "avg_price": price}
            state["history"].append({
                "日時": now, "銘柄": code, "売買": "買", "株数": shares,
                "価格": round(price, 1), "損益": None,
                "理由": "買いシグナル: " + " / ".join(reasons),
            })
            actions.append({"銘柄": code, "判定": "購入", "理由": " / ".join(reasons)})
        else:
            actions.append({"銘柄": code, "判定": "見送り", "理由": " / ".join(reasons)})

    return state, actions


# ── UI ────────────────────────────────────────────────────────

def render_auto_trader_section(safe_budget: float = 0.0) -> None:
    st.header("🤖 仮想自動売買（ペーパートレード）")
    st.caption(
        "ウォッチリストの銘柄に対して、テクニカル分析（移動平均のクロス・RSI）と"
        "ファンダメンタル分析（PER/PBR/ROEのバリュー評価）を組み合わせて売買シグナルを判定し、"
        "決めた予算の範囲内で**仮想的に**売買します。実際の注文は一切行いません。"
        "自動売買の仕組み（シグナル・予算管理・損切り/利確）を、お金を賭けずに学ぶための機能です。"
    )

    tickers = get_watchlist()
    if not tickers:
        st.info("まず「資産管理」タブのウォッチリストに銘柄を登録してください。対象銘柄はウォッチリストから読み込みます。")
        return

    st.caption(f"対象銘柄（ウォッチリスト）: {', '.join(tickers)}")

    # ── 設定 ──
    c1, c2, c3 = st.columns(3)
    with c1:
        budget = st.number_input(
            "仮想予算（円）", min_value=10_000, value=max(int(safe_budget) * 12, 300_000),
            step=10_000, key="pt_budget",
            help="この金額の範囲内でのみ仮想売買を行います。",
        )
        per_trade_max = st.number_input(
            "1銘柄あたりの上限（円）", min_value=10_000, value=100_000, step=10_000,
            key="pt_per_trade",
        )
    with c2:
        stop_loss = st.slider("損切りライン（%下落で売却）", 3, 20, 8, key="pt_stop")
        take_profit = st.slider("利確ライン（%上昇で売却）", 5, 50, 15, key="pt_profit")
    with c3:
        sma_short = st.number_input("短期移動平均(日)", 5, 60, 25, key="pt_sma_s")
        sma_long = st.number_input("長期移動平均(日)", 20, 200, 75, key="pt_sma_l")

    use_fund = st.checkbox(
        "🧾 ファンダメンタルズフィルターを使う（PER/PBR/ROEのバリュー評価が低い銘柄は買わない）",
        value=True, key="pt_use_fund",
    )
    fundamental_min = None
    if use_fund:
        fundamental_min = st.slider(
            "バリュー評価の最低ライン（点）", 0, 100, 40, key="pt_fund_min",
            help="PER・PBR・ROEから算出する0〜100点の評価。40点未満は割高・低効率とみなして購入を見送ります。",
        )

    state = _load_state()

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("📊 シグナルをチェックして仮想売買を実行", type="primary", key="pt_run"):
            if state is None:
                state = _new_state(budget)
            with st.spinner("各銘柄のシグナルを判定しています..."):
                state, actions = run_paper_trading(
                    state, tickers, per_trade_max, stop_loss, take_profit,
                    int(sma_short), int(sma_long),
                    fundamental_min=fundamental_min,
                )
            _save_state(state)
            st.session_state["pt_last_actions"] = actions
    with btn_col2:
        if st.button("🔄 仮想ポートフォリオをリセット", key="pt_reset"):
            _save_state(_new_state(budget))
            st.session_state.pop("pt_last_actions", None)
            st.rerun()

    actions = st.session_state.get("pt_last_actions")
    if actions:
        st.markdown("**今回の判定結果**")
        st.dataframe(pd.DataFrame(actions), hide_index=True, use_container_width=True)

    state = _load_state()
    if state is None:
        st.info("「シグナルをチェックして仮想売買を実行」を押すと、仮想ポートフォリオが作成されます。")
        return

    # ── 現在の仮想ポートフォリオ ──
    st.markdown("---")
    st.subheader("💼 仮想ポートフォリオの状況")

    position_value = 0.0
    rows = []
    for code, pos in state["positions"].items():
        try:
            df = fetch_price_history(code, "5d", "1d")
            df = df[df["Close"].notna()]
            price = float(df["Close"].iloc[-1]) if not df.empty else pos["avg_price"]
        except Exception:
            price = pos["avg_price"]
        value = price * pos["shares"]
        position_value += value
        pl_pct = (price - pos["avg_price"]) / pos["avg_price"] * 100
        rows.append({
            "銘柄": code, "株数": pos["shares"],
            "取得単価": round(pos["avg_price"], 1), "現在値": round(price, 1),
            "評価額": round(value, 0), "損益(%)": round(pl_pct, 2),
        })

    total = state["cash"] + position_value
    initial = state["initial_budget"]
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("総資産（現金+評価額）", f"{total:,.0f}円",
                  delta=f"{(total - initial) / initial * 100:+.2f}%" if initial else None)
    with m2:
        st.metric("現金", f"{state['cash']:,.0f}円")
    with m3:
        st.metric("保有銘柄の評価額", f"{position_value:,.0f}円")

    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    else:
        st.caption("現在、仮想保有中の銘柄はありません。")

    if state["history"]:
        with st.expander(f"📜 売買履歴（{len(state['history'])}件）"):
            st.dataframe(
                pd.DataFrame(reversed(state["history"])),
                hide_index=True, use_container_width=True,
            )

    st.caption(
        "⚠️ これは学習用の仮想売買です。実際の株式の発注は行いません。"
        "シグナルは一般的なテクニカル指標に基づく機械的な判定であり、利益を保証するものではありません。"
        "また、Streamlitアプリは画面を開いている間のみ動作するため、24時間の自動監視はできません"
        "（ボタンを押したタイミングでシグナルを評価します）。"
    )
