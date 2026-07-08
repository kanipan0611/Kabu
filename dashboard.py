"""ホームダッシュボード — 開いた瞬間に資産状況と市場の動きを1画面で確認する。

保存済みのユーザー入力（資産配分・保有株・NISA）と現在株価から、
「今日の状況」をまとめて表示する。詳細な操作は各タブで行う。
"""

from datetime import date

import pandas as pd
import streamlit as st

from auto_trader import _load_state as load_paper_state
from nisa_planner import LIFETIME_TOTAL, TSUMITATE_ANNUAL
from stock_analysis import fetch_price_history
from user_store import get_setting
from watchlist import get_watchlist


_DAILY_TIPS = [
    "「安くなったから買う」の前に「なぜ安くなったか」を調べる。理由のない下落はほぼ存在しません。",
    "積立投資の最大の敵は暴落ではなく「途中でやめること」。相場が荒れた日ほど自動積立の設定を触らない。",
    "配当利回りが異常に高い銘柄は、株価が下がって利回りが「見かけ上」上がっているだけのことが多い。分子より分母を疑う。",
    "PERは業種によって相場が違う。IT企業と銀行のPERを直接比べても意味がない。同業他社と比べる。",
    "損切りラインは買う前に決める。買った後に決めようとすると、人間は必ず先延ばしにする。",
    "取引記録をつけた人とつけない人では、1年後の上達がまるで違う。負けた取引ほどメモを残す。",
    "ニュースで話題になった時点で、その情報は株価に織り込まれていることが多い。飛びつく前に一晩置く。",
    "手数料と税金はリターンを確実に削る唯一の要素。売買回数を減らすことは、それ自体が有効な戦略。",
    "複利の効果は最初の数年ほとんど見えない。10年目から急に効いてくる。やめないことが最大の戦略。",
    "生活防衛資金（生活費の6ヶ月分）ができるまでは、投資額を増やさない。暴落時に売らずに済む人はここが違う。",
    "「みんなが強気のとき」が一番危ない。逆に悲観一色のときに淡々と積み立てた人が報われてきたのが市場の歴史。",
    "個別株で市場平均（インデックス）に勝ち続けるのはプロでも難しい。まず土台をインデックスで作り、個別株は学習と楽しみの範囲で。",
    "上がった理由を説明できない株は、下がった理由もわからないまま狼狽売りすることになる。買う前に一言で説明できるか自問する。",
    "バックテストで完璧な成績のルールほど疑う。過去に合わせ込んだだけのルールは、未来では機能しないことが多い。",
]


def _price_and_change(ticker: str) -> tuple[float | None, float | None]:
    """現在値と前日比(%)を返す。取得できなければ(None, None)。"""
    try:
        df = fetch_price_history(ticker, "5d", "1d")
        df = df[df["Close"].notna()]
        if df.empty:
            return None, None
        price = float(df["Close"].iloc[-1])
        if len(df) >= 2:
            prev = float(df["Close"].iloc[-2])
            return price, (price - prev) / prev * 100
        return price, None
    except Exception:
        return None, None


def render_dashboard() -> None:
    st.header("🏠 ホーム")

    tip = _DAILY_TIPS[date.today().toordinal() % len(_DAILY_TIPS)]
    st.info(f"💡 **今日のワンポイント**: {tip}")

    alloc = get_setting("portfolio_allocation", {})
    holdings = [
        h for h in get_setting("holdings", [])
        if h.get("株数") and str(h.get("銘柄コード") or "").strip()
    ]

    # ── 保有株の評価額と本日の損益 ──────────────────────────
    stock_value = 0.0
    today_pl = 0.0
    total_cost = 0.0
    has_price = False
    holding_rows = []
    for h in holdings:
        code, shares = h["銘柄コード"], h["株数"]
        price, chg_pct = _price_and_change(code)
        if price is None:
            holding_rows.append({"銘柄": code, "株数": shares, "現在値": None, "前日比(%)": None})
            continue
        has_price = True
        value = price * shares
        stock_value += value
        if chg_pct is not None:
            prev_value = value / (1 + chg_pct / 100)
            today_pl += value - prev_value
        if h.get("購入単価"):
            total_cost += h["購入単価"] * shares
        holding_rows.append({
            "銘柄": code, "株数": shares,
            "現在値": round(price, 1),
            "前日比(%)": round(chg_pct, 2) if chg_pct is not None else None,
        })

    cash = float(alloc.get("現金", 0))
    fund = float(alloc.get("インデックス投信", 0))
    stocks_input = float(alloc.get("個別株", 0))
    # 個別株はライブ評価額を優先し、価格が取れなければ入力値を使う
    total_assets = cash + fund + (stock_value if has_price else stocks_input)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("総資産（概算）", f"{total_assets:,.0f}円",
                  help="現金 + インデックス投信（入力値）+ 保有株のライブ評価額")
    with m2:
        st.metric("保有株 本日の損益", f"{today_pl:+,.0f}円" if has_price else "—",
                  delta=f"{today_pl / stock_value * 100:+.2f}%" if has_price and stock_value else None)
    with m3:
        if total_cost > 0 and has_price:
            pl = stock_value - total_cost
            st.metric("保有株 評価損益（取得比）", f"{pl:+,.0f}円",
                      delta=f"{pl / total_cost * 100:+.2f}%")
        else:
            st.metric("保有株 評価損益（取得比）", "—",
                      help="資産管理タブで購入単価を入力すると表示されます")

    if not holdings and not alloc:
        st.info("「💼 資産管理」タブで資産配分と保有株を入力すると、ここに資産状況が表示されます。")

    # ── 保有株・ウォッチリストの動き ────────────────────────
    watch = get_watchlist()
    watch_rows = []
    for code in watch:
        if any(r["銘柄"] == code for r in holding_rows):
            continue  # 保有株と重複表示しない
        price, chg_pct = _price_and_change(code)
        watch_rows.append({
            "銘柄": code, "株数": None,
            "現在値": round(price, 1) if price is not None else None,
            "前日比(%)": round(chg_pct, 2) if chg_pct is not None else None,
        })

    if holding_rows or watch_rows:
        st.markdown("**📋 保有株・ウォッチリストの動き**")
        df = pd.DataFrame(holding_rows + watch_rows)
        df.insert(1, "区分", ["保有"] * len(holding_rows) + ["ウォッチ"] * len(watch_rows))
        st.dataframe(
            df, hide_index=True, use_container_width=True,
            column_config={
                "前日比(%)": st.column_config.NumberColumn(format="%+.2f%%"),
            },
        )

    # ── NISA進捗 ─────────────────────────────────────────────
    nisa = get_setting("nisa", {})
    ts_used = float(nisa.get("ts_used", 0))
    lifetime_used = float(nisa.get("lifetime_used", 0))
    if ts_used > 0 or lifetime_used > 0:
        st.markdown("**🌱 NISA進捗**")
        st.progress(min(1.0, ts_used / TSUMITATE_ANNUAL),
                    text=f"つみたて投資枠 今年: {ts_used:,.0f}円 / {TSUMITATE_ANNUAL:,.0f}円")
        st.progress(min(1.0, lifetime_used / LIFETIME_TOTAL),
                    text=f"生涯非課税限度額: {lifetime_used:,.0f}円 / {LIFETIME_TOTAL:,.0f}円")

    # ── 仮想売買の状況 ───────────────────────────────────────
    paper = load_paper_state()
    if paper:
        n_pos = len(paper.get("positions", {}))
        initial = paper.get("initial_budget") or 0
        cash_p = paper.get("cash", 0)
        st.markdown("**🤖 仮想売買の状況**")
        st.caption(
            f"現金 {cash_p:,.0f}円 ／ 保有 {n_pos}銘柄 ／ 取引履歴 {len(paper.get('history', []))}件"
            f"（初期予算 {initial:,.0f}円）— 詳細は「🤖 仮想売買」タブへ"
        )
