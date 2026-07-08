"""投資学習 & 財務管理ダッシュボード。

タブ構成：
  1. 📈 チャート     — インタラクティブ銘柄チャート・自動スコアリング
  2. 💼 資産管理    — ポートフォリオ可視化・楽天証券CSV・ウォッチリスト
  3. 🌱 新NISA     — 枠管理・複利シミュレーション
  4. 🔬 分析ツール   — ファンダメンタルズ・投資シミュレーター
  5. 🤖 仮想売買    — シグナル判定によるペーパートレード（実発注なし）
"""

import streamlit as st

from auto_trader import render_auto_trader_section
from finance_planner import render_finance_sidebar
from fundamentals import render_fundamentals_section
from nisa_planner import render_nisa_section
from portfolio import render_portfolio_section, render_rakuten_import_section
from simulator import render_simulator_section
from stock_analysis import render_market_overview, render_stock_section
from watchlist import render_watchlist_section

st.set_page_config(page_title="Nest Egg — 投資学習ダッシュボード", page_icon="🥚", layout="wide")

st.markdown(
    '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">',
    unsafe_allow_html=True,
)

st.title("🥚 Nest Egg — 投資学習 & 財務管理ダッシュボード")
st.caption(
    "社会人1年目に向けて、投資の分析スキルを自分で磨くための学習用ツールです。"
    "表示内容は教育目的の参考情報であり、投資助言ではありません。"
    "💾 各タブの入力値（資産配分・保有株・NISA枠・財務設定）は自動保存され、次回開いたときに復元されます。"
)

# ── サイドバー（財務設定）──────────────────────────────────────
finance_result = render_finance_sidebar()
safe_budget = finance_result.get("safe_budget", 0.0) if finance_result else 0.0
monthly_budget = finance_result.get("monthly_surplus", 30_000) if finance_result else 30_000

# ── マーケット概況（常時表示）─────────────────────────────────
with st.container(border=True):
    st.caption("📊 マーケット概況")
    render_market_overview()

st.write("")

# ── メインタブ ─────────────────────────────────────────────────
tab_chart, tab_assets, tab_nisa, tab_analysis, tab_auto = st.tabs(
    ["📈 チャート", "💼 資産管理", "🌱 新NISA", "🔬 分析ツール", "🤖 仮想売買"]
)

with tab_chart:
    with st.container(border=True):
        render_stock_section()

with tab_assets:
    with st.container(border=True):
        render_portfolio_section(safe_budget=safe_budget)
    st.write("")
    with st.container(border=True):
        render_rakuten_import_section()
    st.write("")
    with st.container(border=True):
        render_watchlist_section()

with tab_nisa:
    with st.container(border=True):
        render_nisa_section(monthly_budget=monthly_budget)

with tab_analysis:
    default_ticker = st.session_state.get("last_analyzed_ticker", "7203.T")
    with st.container(border=True):
        render_fundamentals_section(default_ticker=default_ticker)
    st.write("")
    with st.container(border=True):
        render_simulator_section()

with tab_auto:
    with st.container(border=True):
        render_auto_trader_section(safe_budget=safe_budget)
