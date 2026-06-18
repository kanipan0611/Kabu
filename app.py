"""投資学習 & 財務管理ダッシュボード。

セクション構成：
  1. マイ・ファイナンス設定（サイドバー）
  2. ポートフォリオ可視化
  3. インタラクティブ・チャート分析（1銘柄 / 2銘柄比較モード）
  4. 分析ノート & ファンダメンタルズ入力
"""

import streamlit as st

from finance_planner import render_finance_sidebar
from fundamentals import render_fundamentals_section
from portfolio import render_portfolio_section
from stock_analysis import render_stock_section

st.set_page_config(page_title="Nest Egg — 投資学習ダッシュボード", page_icon="🥚", layout="wide")

st.markdown(
    '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">',
    unsafe_allow_html=True,
)

st.title("🥚 Nest Egg — 投資学習 & 財務管理ダッシュボード")
st.caption(
    "社会人1年目に向けて、投資の分析スキルを自分で磨くための学習用ツールです。"
    "表示内容は教育目的の参考情報であり、投資助言ではありません。"
)

render_finance_sidebar()

with st.container(border=True):
    render_portfolio_section()

st.write("")

with st.container(border=True):
    ticker = render_stock_section()

st.write("")

with st.container(border=True):
    render_fundamentals_section(default_ticker=ticker or "7203.T")
